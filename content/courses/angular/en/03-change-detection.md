# Change detection

## Theory

### What actually gets checked

Change detection (CD) answers the question "when should the template's `update` function run and sync the DOM". What gets checked is not "a component" but a **view**: a component's template plus the embedded views created by `@if`, `@for` and `@defer`. Class instances are never recreated in the process — only the binding update code runs.

Traversal goes from the root downwards, but not across the whole tree. When something marks a component dirty, Angular marks the **path from the root to it** as needing traversal; branches the marking never touched are not visited.

```
App                              traversed: it sits on the path to a dirty component
├── AppHeader                    skipped: OnPush, same inputs, no events
├── TicketList                   checked: a signal read in its template changed
│   ├── TicketFilters            skipped: its inputs did not change
│   ├── TicketCard #101          checked: the selected input changed
│   └── TicketCard #102 … #106   skipped: same inputs
└── AppFooter                    skipped
```

### OnPush and Eager

Since v22 `OnPush` is the default strategy: a component with no `changeDetection` field behaves exactly that way. The former `Default` was renamed to `ChangeDetectionStrategy.Eager` and means "check on every traversal that reaches this component".

An `OnPush` component is checked when:

- at least one of its inputs changed (Angular compares the previous and the new binding value — the comparison is shallow, so for objects it is a reference comparison);
- an event was handled in its subtree — a template event binding, a host listener, an output of a child component;
- `ChangeDetectorRef.markForCheck()` was called — including from inside `AsyncPipe`, which does it on every `emit`;
- a signal **read in its template** changed;
- an input was set programmatically via `ComponentRef.setInput()`;
- the view was reattached after having been marked dirty.

One case people routinely forget: if you write to a child component's fields directly through `viewChild`, no inputs changed and no event happened — that component needs an explicit `markForCheck()`.

### How it used to work: zone.js

Historically Angular had no explicit notifications and solved the problem differently: `zone.js` patched every asynchronous browser API — `setTimeout`, `addEventListener`, `Promise`, `XHR` — and told the framework "an async operation finished, application state *might* have changed". When the microtask queue drained, Angular ran `tick()` — a walk of the entire tree.

The model worked without developer involvement, and that was its value: you wrote an ordinary `setTimeout`, mutated a class field, and the DOM updated. The price:

- **Redundancy.** The zone has no idea whether anything actually changed. Any mouse move with a listener, any timer, any network response triggered a check of the whole tree.
- **Size and magic.** An extra package in the bundle, patches around platform APIs, bloated debugger stacks, and `async/await` that landed inside or outside the zone depending on the compilation target.
- **A false sense of reliability.** "It just updates" stopped being true exactly where a callback came from an unpatched source — and then the cause was anything but obvious.

### How it works now: zoneless

Since v21, zoneless is the default for new projects; `zone.js` is simply absent from them. Angular relies on notifications from its own APIs:

```
┌─────────────────────────────────┬─────────────────────────────────────┬───────────────────────────────────┐
│ what happened                   │ zone.js (before v21)                │ zoneless (today)                  │
├─────────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────┤
│ a click on a template button    │ the zone caught the event → tick()  │ the listener notifies directly    │
├─────────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────┤
│ signal.set read in a template   │ a tree walk after the microtasks    │ marks the path, checks that path  │
├─────────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────┤
│ setTimeout writes a class field │ the zone caught the timer → tick()  │ NOTHING: there is no notification │
├─────────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────┤
│ a fetch/promise callback        │ the zone caught it → tick()         │ needs a signal or markForCheck    │
├─────────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────┤
│ an emit picked up by AsyncPipe  │ the zone + markForCheck in the pipe │ markForCheck in the pipe          │
├─────────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────┤
│ a third-party library callback  │ the zone, if the API was patched    │ needs a signal or markForCheck    │
└─────────────────────────────────┴─────────────────────────────────────┴───────────────────────────────────┘
```

Signals are what made this model practical. Previously "explicit notifications" meant a manual `markForCheck` in every async callback; a signal notifies on its own, because it knows which templates read it. That is precisely why signals and zoneless landed in the same release cycle: either one without the other would have been awkward.

What breaks in older code during the transition:

- `NgZone.onMicrotaskEmpty` and `NgZone.onStable` no longer emit, and `NgZone.isStable` is always `true`. Any logic waiting for "application stability" silently stops working.
- Updating state from an unpatched source does not update the DOM: a `setTimeout` writing a plain field, a third-party library callback, a manual subscription without `AsyncPipe`.
- Reactive Forms: `setValue`/`patchValue` change form state and emit their Observables, but do not by themselves trigger a template check (this resurfaces in chapter 10).
- For SSR and tests, "stability" is now expressed through `PendingTasks`: `inject(PendingTasks).run(async () => …)` or the `pendingUntilEvent()` helper, which keeps the application unstable until the Observable emits or completes.

### Diagnosis

```
                               Diagnosis: symptom → cause → what to look with
┌─────────────────────────────────┬─────────────────────────────────────┬─────────────────────────────────┐
│ symptom                         │ cause                               │ tool                            │
├─────────────────────────────────┼─────────────────────────────────────┼─────────────────────────────────┤
│ fresh data, stale DOM           │ the source never notified Angular   │ provideCheckNoChangesConfig     │
├─────────────────────────────────┼─────────────────────────────────────┼─────────────────────────────────┤
│ a click anywhere fixes the view │ same cause; the click forces a walk │ same + DevTools profiler        │
├─────────────────────────────────┼─────────────────────────────────────┼─────────────────────────────────┤
│ more checks than changes        │ an Eager component, a method call   │ DevTools profiler               │
├─────────────────────────────────┼─────────────────────────────────────┼─────────────────────────────────┤
│ NG0100 right after first render │ a value changes during the check    │ the error stack: whose template │
├─────────────────────────────────┼─────────────────────────────────────┼─────────────────────────────────┤
│ a test sees an empty DOM        │ no await fixture.whenStable()       │ the test itself (chapter 13)    │
└─────────────────────────────────┴─────────────────────────────────────┴─────────────────────────────────┘
                        NG0100 exists in dev only: production runs no second check,
                                    so the inconsistency stays invisible
```

Three tools worth knowing:

1. **`provideCheckNoChangesConfig({ interval, exhaustive: true })`** — a periodic dev check: Angular re-verifies bindings (with `exhaustive: true` treating all views as `Eager`) and throws `ExpressionChangedAfterItHasBeenCheckedError` when it finds a value that changed without a notification. It is the way to catch exactly "the data changed but nobody told Angular" — the class of bug that zoneless makes silent.
2. **Angular DevTools, the Profiler tab** — records CD cycles: which components were checked, how many times, and at what cost. This is where "why does it update so often" gets answered.
3. **`NG0100` (`ExpressionChangedAfterItHasBeenChecked`)** — in dev mode Angular checks the template a second time and compares the results. The error means an expression changed *during* the check: typically writing state from a lifecycle hook after the check, from `afterNextRender`, or from a getter with a side effect. Production runs no such check, so the inconsistency is not diagnosed at all.

### Working with the DOM after render

Reading or writing the DOM inside `effect` is a bad idea: it runs before rendering, so you observe the previous layout. There are dedicated APIs for this:

```ts
// once, after the next render
afterNextRender(() => this.chart = new Chart(this.canvas().nativeElement));

// reactively: re-runs when the signals it read change
afterRenderEffect({
  read: () => { /* layout measurements */ },
  write: () => { /* DOM mutations */ },
});
```

`afterRenderEffect` is stable and has four phases — `earlyRead`, `write`, `mixedReadWrite`, `read` — which run in that order and only when the effect is dirty. Splitting phases exists to avoid layout thrashing: all reads first, then all writes. The documentation advises avoiding `mixedReadWrite` and `earlyRead`.

## React parallels

- **The unit of work differs.** In React, `setState` initiates a re-render of the component and, by default, a walk of its subtree; the component function runs again. In Angular nothing is "re-rendered": the path to the dirty component is marked and the `update` functions of the affected templates run. The component as an object is never recreated.
- **`memo` versus `OnPush`.** `React.memo` is a wrapper that compares props and may skip a re-render; `OnPush` is a property of the component itself that affects its entire subtree. Both comparisons are shallow, hence the identical symptom: pass a mutated object and no update happens.
- **StrictMode versus the dev check.** StrictMode's double render catches impure renders; Angular's double check in dev catches something else — a value that changed between two checks of one cycle (`NG0100`). The shared idea: dev mode is deliberately stricter than production, and "it doesn't crash in prod" is not a defence.
- **Scheduling the update.** React batches `setState` and updates the DOM on its own schedule. Angular collects notifications and runs one synchronization rather than one per `set` — so three `set` calls in a row produce a single pass. The difference is that a signal's value is readable immediately, not "after the re-render".
- **Where the habit breaks:** `await fetch(...)` → assign a field → "in React this would update". In zoneless Angular nothing happens, because there was no notification. And in the other direction: a React developer used to "cheap" computation in JSX brings methods into the template — where they run on every check, and the number of checks is decided by CD, not by the developer.

## What you will see in legacy code

- **`zone.js` in `polyfills`** and/or `provideZoneChangeDetection({ eventCoalescing: true })` in the app config — the project lives in the old model, and `eventCoalescing` is there precisely to mute some of the redundant checks.
- **`NgZone` as a working tool:** `this.zone.run(() => …)` around a third-party callback, `this.zone.runOutsideAngular(() => …)` around animations and timers, subscriptions to `zone.onStable`. In zoneless all of this is either unnecessary or non-functional.
- **`ChangeDetectorRef` in the constructor:** `private cdr = inject(ChangeDetectorRef)` with a `cdr.markForCheck()` after every async operation; sometimes `cdr.detectChanges()` — "check right now" — sometimes `detach()`/`reattach()` for manual control. With signals this stays only for integrating non-reactive code.
- **`setTimeout(() => …, 0)` as a way "to make it update"** and `ApplicationRef.tick()` called from a service — both patterns mean the author never found the real cause of the missed check.
- **`ChangeDetectionStrategy.Default`** in older components' decorators; after migrating to v22 they will carry an explicit `Eager` — not a pessimization but a way to preserve the previous behaviour when the default changed.
- **`state$ | async` with a `BehaviorSubject`** — a variant that worked both in the zone model and in zoneless, because `AsyncPipe` calls `markForCheck` itself. That is why older code using the `async` pipe survives the move to zoneless better than code using plain class fields.

## What we add to the project

Support Desk gains a counter of new tickets updated from a timer — that is, from a source Angular knows nothing about. We build it "the React way" first and watch the silence, then fix it two different ways and compare. On top of that we enable dev diagnostics and auto-scroll to the selected card via `afterRenderEffect`.

## Exercise

**Input:** the project from chapter 02 (signals, filters, selection through `linkedSignal`).
**Output:** a working counter fed by an external source, dev diagnostics enabled, auto-scroll to the selected card — and an understanding of why each piece is built the way it is.

Requirements:

1. Write a `NewTicketsFeed` service that simulates an external source: every 3 seconds it increments the number of "new tickets since page load". **First** implement it the React way: a plain class field, `setInterval`, and a template reading the field. Record what you see on screen and explain it.
2. Fix #1 — a signal: the same field becomes a `signal`. Confirm the counter now ticks and explain what exactly notifies Angular.
3. Fix #2 — manual: go back to a plain field but add `ChangeDetectorRef.markForCheck()` inside the timer callback. Does it work? Describe the difference from the signal version: what happens to the tree in each case.
4. The timer must stop when things are destroyed. Do it via `DestroyRef` (or via `effect` + `onCleanup` if you think that fits — justify the choice).
5. Enable `provideCheckNoChangesConfig({ interval: 1000, exhaustive: true })` in dev builds only. Bring back the "broken" version from step 1 for a minute and see what the diagnostics report.
6. Add a component with `changeDetection: ChangeDetectionStrategy.Eager` (say, an `AppFooter` showing the current time) and use the Angular DevTools Profiler to compare its check count with the `OnPush` components while you type in the search field. Then move it to `OnPush` and achieve the same behaviour correctly.
7. Auto-scroll: selecting a ticket must scroll its card into view. Use `afterRenderEffect` and a signal-based `viewChildren`. Explain in a comment why this is not an `effect`.

Edge cases to think about:

- Why is `setInterval` inside an `effect` a bad idea, and what happens if that same effect also reads a signal?
- You called `markForCheck()` on a component deep in the tree. Which components will be checked and which will not?
- What does `NgZone.isStable` return in your application, and why can nothing be built on that answer?
- A child receives an object via `[filters]="filtersObject"` and you mutate one of its fields. What does the `OnPush` child see? And what if it reads a signal stored inside that object?
- Why does `NG0100` never appear in production, and why is that not a reason to consider the problem non-existent?

## Solution walkthrough

`src/app/tickets/new-tickets-feed.ts` — the external source. The correct version comes first; the broken one from step 1 is dissected after the code:

```ts
import { DestroyRef, Injectable, inject, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class NewTicketsFeed {
  // A signal instead of a plain field: it notifies Angular itself that the
  // templates which read it need re-checking
  private readonly newCount = signal(0);
  readonly count = this.newCount.asReadonly();

  constructor() {
    const timer = setInterval(() => {
      // set() from a timer callback is the only "integration" we need:
      // no NgZone.run, no markForCheck
      this.newCount.update((n) => n + 1);
    }, 3000);

    // DestroyRef instead of ngOnDestroy: a service is not a component,
    // yet the cleanup requirement is exactly the same
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }

  reset(): void {
    this.newCount.set(0);
  }
}
```

The broken version from step 1 differs by one line — and that line is precisely what makes the mechanism visible:

```ts
// WHAT HAPPENS WITH THE "REACT WAY" VERSION
export class NewTicketsFeed {
  count = 0;                                   // a plain field

  constructor() {
    setInterval(() => this.count++, 3000);     // the value grows
  }
}
// The field grows, but the template keeps showing 0: there is no zone.js,
// the timer notifies nobody, the template is never checked. The first
// click on any button triggers a traversal — and the number "catches up".
// Hence the most recognizable symptom: "it only updates if I click something"
```

The manual fix (step 3), for comparison, is what all async code looked like before signals:

```ts
export class ManualFeed {
  count = 0;
  private readonly cdr = inject(ChangeDetectorRef);
  // ...
  // in the callback: this.count++; this.cdr.markForCheck();
}
```

The difference is fundamental. `markForCheck()` marks **one specific component** — the one whose `ChangeDetectorRef` was injected — and the path to the root, which is why it is the wrong tool for a service: the service does not know who reads it, and a `ChangeDetectorRef` in a root service does not point where you would want. A signal marks **all of its readers**, wherever they are: one source, any number of consumers, no references to components at all.

`src/app/app.config.ts` — dev diagnostics:

```ts
import {
  ApplicationConfig,
  isDevMode,
  provideBrowserGlobalErrorListeners,
  provideCheckNoChangesConfig,
} from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // Periodically re-verifies bindings and throws NG0100 when it finds a
    // value that changed without a notification. exhaustive: true treats all
    // views as Eager, so it also catches what OnPush would usually hide.
    // Dev only: in production this is pure overhead on every interval
    ...(isDevMode()
      ? [provideCheckNoChangesConfig({ interval: 1000, exhaustive: true })]
      : []),
  ],
};
```

With this provider in place, the broken counter from step 1 stops being a silent bug: a second after the first divergence the application throws `ExpressionChangedAfterItHasBeenCheckedError` and points at the template expression — the diagnostics find the un-notified source for you.

`src/app/tickets/ticket-list.ts` — auto-scroll and reading the counter:

```ts
import {
  Component,
  ElementRef,
  afterRenderEffect,
  computed,
  inject,
  linkedSignal,
  signal,
  viewChildren,
} from '@angular/core';
import { NewTicketsFeed } from './new-tickets-feed';
import { Ticket, TicketStatus } from './ticket';
import { TicketCard } from './ticket-card';
import { TicketFilters } from './ticket-filters';

@Component({
  selector: 'app-ticket-list',
  imports: [TicketCard, TicketFilters],
  templateUrl: './ticket-list.html',
  styleUrl: './ticket-list.css',
})
export class TicketList {
  private readonly feed = inject(NewTicketsFeed);

  // reading the service's signal straight in the template is enough
  // to make this component one of that signal's consumers
  protected readonly newCount = this.feed.count;

  // ... state and computed values from chapter 02 ...

  // A signal query: updates itself, needs no ngAfterViewInit
  private readonly cardElements = viewChildren<ElementRef<HTMLElement>>('cardRef');

  constructor() {
    // Not an effect: effects run BEFORE rendering, so on the very first
    // selection the node is not in the DOM yet (or still sits at its old
    // position). afterRenderEffect runs after render and re-runs when the
    // signals it reads change
    afterRenderEffect({
      write: () => {
        const id = this.selectedId();
        if (id === null) return;

        const target = this.cardElements().find(
          (ref) => ref.nativeElement.dataset['ticketId'] === String(id),
        );
        // scrollIntoView both reads layout and writes; on a hot path
        // such work gets split across the read/write phases
        target?.nativeElement.scrollIntoView({ block: 'nearest' });
      },
    });
  }
}
```

The matching template fragment — the cards need a local reference and an attribute to find them by:

```html
@for (ticket of filtered(); track ticket.id) {
  <li #cardRef [attr.data-ticket-id]="ticket.id">
    <app-ticket-card
      [ticket]="ticket"
      [selected]="ticket.id === selectedId()"
      (selectTicket)="select($event)"
    />
  </li>
}
```

And the header with the counter:

```html
<p class="ticket-list__feed">
  {{ newCount() }} new since page load
  @if (newCount() > 0) {
    <button type="button" (click)="feed.reset()">Mark as seen</button>
  }
</p>
```

The demonstration from step 6 — a component deliberately checked every time:

```ts
@Component({
  selector: 'app-footer',
  template: `<small>rendered at {{ renderedAt() }}</small>`,
  // Eager = the former Default: checked on every traversal that reaches here.
  // The effect is literally visible: the time changes on any activity in the app
  changeDetection: ChangeDetectionStrategy.Eager,
})
export class AppFooter {
  protected renderedAt(): string {
    return new Date().toLocaleTimeString();
  }
}
```

In the Profiler you can clearly see this component joining every cycle while you type in the search box, even though its data depends on nothing. The correct version is `OnPush` (that is, simply dropping the `changeDetection` field) plus a signal if the time genuinely needs to update:

```ts
export class AppFooter {
  // the update source is explicit, the interval is obvious, no extra checks
  protected readonly renderedAt = signal(new Date().toLocaleTimeString());
}
```

Answers to the edge cases:

- `setInterval` inside an `effect` is bad because the effect re-runs when the signals it read change: every re-run creates **another** interval unless the old one is cleared in `onCleanup`. And if such an effect also reads a signal that the timer itself updates, you get a self-sustaining loop. Periodic work belongs in a constructor with `DestroyRef`, not in a reactive effect.
- `markForCheck()` marks the component itself dirty plus the path to the root. What gets checked: the components on that path (their templates run `update`) and the component itself with its subtree under the usual rules. Sibling branches the marking never touched are not visited at all — including `OnPush` components next to the marked one.
- `NgZone.isStable` always returns `true`: without `zone.js` nobody tracks "no pending async operations". Logic waiting for stability will be told "all done" immediately. The equivalent for SSR and tests is `PendingTasks`/`pendingUntilEvent`, where instability is declared explicitly.
- Mutating a field of the object: the object reference did not change, so the input counts as unchanged and the `OnPush` child is not checked (until an event happens in its subtree or something marks it another way). If, however, the object holds a **signal** and the child reads it in its template, the update arrives — because the notification comes from the signal, not from the input comparison. That is in fact a usable technique: pass "an object of signals" rather than "an object you mutate".
- `NG0100` is a dev-mode mechanism: only there is the template checked twice and the results compared. Production has no second check, so the error never fires — but the inconsistency remains: the user sees a value that is one cycle behind, or no update at all. Production is not "working better", it is just quiet.

## Check yourself

1. Explain in your own words what `markForCheck()` physically does, and why it does not lead to every component in the application being checked.
2. What exactly did `zone.js` provide, and which two of its properties made moving to zoneless desirable? Why did that move only become possible together with signals?
3. An `OnPush` component does not update after you mutated the object passed to it. Name three different ways to fix it and explain which one is correct and why.
4. Why is `NG0100` a dev-mode error specifically, and what does it tell you about your code?
5. Why does `afterRenderEffect` exist rather than "just an `effect`" for DOM work after render? What happens if you measure an element's size inside a regular `effect`?

<details>
<summary>Answers</summary>

1. `markForCheck()` marks the view its injected `ChangeDetectorRef` belongs to as dirty, and marks all of its ancestors as "needing traversal" — that is, it builds a path from the root to that component. At the next synchronization Angular walks down the marked path and checks the marked component; branches the marking never reached are not visited. That is why it is a cheap operation: it does not trigger a check of the whole tree, it only adds one route.
2. `zone.js` patched the browser's async APIs and told Angular "an async operation finished, state *might* have changed", after which a full tree walk ran. The two properties that pushed the framework away from it: (a) redundancy — the zone cannot know whether anything really changed, so checks ran far more often than needed; (b) cost and opacity — an extra bundle package, patches around platform APIs, bloated stacks, and `async/await` behaving differently depending on the build target. The move became possible together with signals because the zone was an *automatic* notification source: removing it and keeping only manual `markForCheck` would have pushed that work into every callback. A signal notifies by itself and knows its readers — it replaced the zone as the automatic mechanism, but with the precision of "only what actually depends on the changed value".
3. Three ways: (a) replace the mutation with creating a new object — then the input comparison sees a new reference and the child is checked; (b) keep the state in a signal and read it in the child's template — the signal notifies regardless of inputs; (c) call `markForCheck()` on the child (for example by reaching it through `viewChild`) or give the child the `Eager` strategy. The correct answer is (b), or (a) as the minimal patch: they remove the cause rather than the symptom. Option (c) is a crutch — it treats the manifestation while leaving mutable state the framework knows nothing about, so the same bug will reappear elsewhere.
4. `NG0100` fires because in dev mode Angular checks a template and then re-checks it, comparing the results. They must match: one synchronization must produce one consistent state. If a value changed between the checks, the code is mutating state *during* the check — typically writing fields from hooks that run after the check, a getter with a side effect, or a state change from `afterNextRender`. The message says your data model is updated in the wrong place; production runs no second check, the error disappears, but the inconsistency (a value one cycle behind) does not.
5. `effect` runs as part of synchronization, **before** the result reaches the DOM. Measurements inside it therefore observe the previous layout: the size of a node that does not exist yet, or a position from before the new styles applied. `afterRenderEffect` runs after render and is split into phases (`earlyRead`, `write`, `mixedReadWrite`, `read`) so that all layout reads happen separately from all writes and the browser does not recompute layout repeatedly. Measuring inside a regular `effect` gives you either stale numbers or a forced layout at an unfortunate moment — and, at worst, a loop of "measured → wrote a signal → another check".

</details>

## Common mistake

The first mistake comes straight from React: "got the data, assigned the field, the DOM will update". In the zone model that really did work, which is why the internet is full of code shaped exactly like that; in a zoneless application, assigning a plain field from `setTimeout`, `fetch().then()` or a third-party callback achieves nothing — there was no notification, so the template is never checked. The insidious part is that the bug looks intermittent: the next click anywhere triggers a traversal and the value "catches up", so the symptom is reported as "it updates, but with a delay" or "it only updates if I click something". The right reaction is not to hunt for a place to put `markForCheck`, but to ask why this state is not a signal in the first place. A signal notifies all of its readers itself, and the question "who is supposed to trigger the check here" disappears.

The second mistake is the opposite in sign: fighting "too many checks" somewhere other than the cause. The classic culprits are methods and getters in templates (`{{ getTotal() }}`, `{{ formatDate(x) }}`) and impure pipes: they run on every check of the template, and how many checks there are is decided by CD. React experience suggests the wrong intuition here: in JSX a call inside the markup runs once per render and its cost is visible. In Angular the same code runs as many times as the component is checked — and before you open the Profiler, that is invisible. The rule is simple: templates contain signal reads, `computed` values and pure pipes; anything that computes, computes in the class. And since `OnPush` is now the default, an explicit `Eager` in a decorator deserves to be read as a red flag: nearly always it was left there by a migration rather than chosen deliberately.
