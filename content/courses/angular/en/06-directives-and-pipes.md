# Directives and pipes

## Theory

### A directive is a component without a template

Technically a component *is* a directive that acquired a template. Everything else — the selector, `host`, `input()`/`output()`, DI, lifecycle hooks — is shared. Hence a simple rule of thumb: **need your own markup, write a component; need behaviour on an element that already exists, write a directive**.

```ts
@Directive({
  // an attribute selector: the directive attaches to someone else's element
  // and adds nothing to the markup
  selector: '[appOverdue]',
  host: {
    '[class.is-overdue]': 'isOverdue()',
    '[attr.title]': 'isOverdue() ? "Past SLA" : null',
  },
})
export class OverdueDirective {
  readonly ticket = input.required<Ticket>({ alias: 'appOverdue' });
  protected readonly isOverdue = computed(() => /* … */);
}
```

A selector can narrow applicability: `'button[appPrimary]'` only matches a `button`, `'[appOverdue]:not([disabled])'` skips disabled elements. That is a cheap way to bake a constraint into the directive itself.

### Structural directives and the asterisk

```
           What the asterisk turns into
┌───────────────────────────────────────────────┐
│ in the template                               │
│ <li *appRepeat="3">a row</li>                 │
└───────────────────────────────────────────────┘
                        │  compiler
                        ▼
┌───────────────────────────────────────────────┐
│ desugars into an ng-template                  │
│ <ng-template appRepeat [appRepeat]="3">       │
│   <li>a row</li>                              │
│ </ng-template>                                │
└───────────────────────────────────────────────┘
                        │  DI
                        ▼
┌───────────────────────────────────────────────┐
│ the directive receives two dependencies       │
│ TemplateRef  — what to render                 │
│ ViewContainerRef — where to render it         │
└───────────────────────────────────────────────┘
                        │  runtime
                        ▼
┌───────────────────────────────────────────────┐
│ the directive decides how many times and when │
│ vcr.createEmbeddedView(tpl, context)          │
│ vcr.clear()                                   │
└───────────────────────────────────────────────┘
@if/@for use the same embedded views but with no directive in
between: the blocks compile directly and are cheaper for it
```

The asterisk is syntactic sugar: the compiler wraps the element in an `<ng-template>` and puts the directive on that. The directive receives a `TemplateRef` (what to render) and a `ViewContainerRef` (where), and then **decides for itself** whether to create a view, how many, and with what context. That is exactly how `*ngIf` and `*ngFor` worked: `*ngIf` called `createEmbeddedView()`/`clear()`, `*ngFor` created one view per item and reused them by `trackBy`.

The context is passed as an object; the `$implicit` key becomes the default value for `let`:

```ts
this.vcr.createEmbeddedView(this.tpl, { $implicit: item, index: i });
// in the template: *appRepeat="items; let item; let i = index"
```

For typing the context there are `ngTemplateContextGuard` (describes the context type) and `ngTemplateGuard_<input>` (narrows a type by a condition) — without them `strictTemplates` cannot infer the types used inside the template.

Do you still write custom structural directives? The official position: use built-in control flow for conditions and lists, and write a structural directive "when you need reusable rendering behavior that control flow doesn't cover". Real examples: rendering by permission (`*appHasRole="'admin'"`), lazy wrappers, delayed display, repetition with special semantics.

### hostDirectives: composing behaviour

Component inheritance is possible in Angular but becomes unmanageable fast. Composition solves the same problem better:

```ts
@Component({
  selector: 'app-ticket-card',
  hostDirectives: [
    HighlightOnHover,            // the behaviour stays entirely private
    {
      directive: OverdueDirective,
      inputs: ['appOverdue: ticket'],   // an input forwarded under a new name
      outputs: ['overdueChange'],
    },
  ],
})
export class TicketCard {}
```

What matters here:

- Directives are applied **statically at compile time** — they cannot be added at runtime.
- By default a host directive's inputs and outputs are **private**: invisible from outside until you list them explicitly in `inputs`/`outputs` (aliases allowed).
- The host directive's own selector is ignored — it applies because it is listed.
- Host directive constructors, hooks and bindings run **before** the component itself, and a directive may apply `hostDirectives` to other directives, forming chains.
- A component and its host directives can inject one another — that is the intended way for them to share state.

The framework ships a ready-made example of this approach: `@angular/aria` (stable since v22), a set of directives covering ARIA attributes, keyboard navigation and focus management so that every project stops rewriting them.

### Pipes: pure and impure

```
                        The cost of computing inside a template
┌──────────────────────────────┬─────────────────────────────────────────────┬────────┐
│ in the template              │ when it runs                                │ cached │
├──────────────────────────────┼─────────────────────────────────────────────┼────────┤
│ a pure pipe, primitive input │ when the value changes                      │ yes    │
├──────────────────────────────┼─────────────────────────────────────────────┼────────┤
│ a pure pipe, object input    │ when the REFERENCE changes, not on mutation │ yes    │
├──────────────────────────────┼─────────────────────────────────────────────┼────────┤
│ an impure pipe (pure: false) │ on every check of the template              │ no     │
├──────────────────────────────┼─────────────────────────────────────────────┼────────┤
│ async, keyValue, slice, json │ on every check (they are impure)            │ no     │
├──────────────────────────────┼─────────────────────────────────────────────┼────────┤
│ a class method {{ f(x) }}    │ on every check of the template              │ no     │
├──────────────────────────────┼─────────────────────────────────────────────┼────────┤
│ a computed in the class      │ when its dependencies change                │ yes    │
└──────────────────────────────┴─────────────────────────────────────────────┴────────┘
              the built-in date, currency, decimal and uppercase are pure;
                  async additionally calls markForCheck on every emit
```

A pipe is a class with a `transform` method and a name it is known by in templates. By default a pipe is **pure**: the result is cached and recomputed only when a primitive value or an object **reference** changes. Two consequences to accept immediately:

1. Mutating an array passed into a pure pipe will not recompute it — the same story as with `OnPush` and signals (chapters 02–03).
2. `pure: false` removes caching entirely: the pipe runs on every check of the template. The documentation is blunt about avoiding it unless absolutely necessary.

Among the built-ins, `async`, `keyValue`, `slice` and `json` are declared `pure: false`; `date`, `currency`, `decimal`, `percent` and `uppercase` are pure. `AsyncPipe` additionally calls `markForCheck()` on every emit — which is why older `| async` code survived the move to zoneless (chapter 03).

Pipes take part in DI: `inject()` works inside `transform` (that is how `DatePipe` gets the locale). The reverse is discouraged by the documentation: do not inject a pipe class into a service to call its `transform` — if the logic is needed outside templates, it should be a plain function that the pipe merely wraps.

### Choosing the tool

```
┌────────────────────────────────────────┬────────────────────────┬──────────────────────────────┐
│ what you need                          │ the tool               │ the deciding sign            │
├────────────────────────────────────────┼────────────────────────┼──────────────────────────────┤
│ own markup and own state               │ a component            │ it has a template            │
├────────────────────────────────────────┼────────────────────────┼──────────────────────────────┤
│ behaviour on someone else's element    │ an attribute directive │ no markup is added           │
├────────────────────────────────────────┼────────────────────────┼──────────────────────────────┤
│ decide whether and how often to render │ a structural directive │ you need a TemplateRef       │
├────────────────────────────────────────┼────────────────────────┼──────────────────────────────┤
│ reshape a value for display            │ a pipe                 │ a pure function of its input │
├────────────────────────────────────────┼────────────────────────┼──────────────────────────────┤
│ a derived value of a component         │ computed               │ it depends on signals        │
├────────────────────────────────────────┼────────────────────────┼──────────────────────────────┤
│ a bundle of behaviours on a component  │ hostDirectives         │ composition, not inheritance │
└────────────────────────────────────────┴────────────────────────┴──────────────────────────────┘
```

The practical rule: **a pipe is for presentation, a `computed` is for data**. Date formatting, pluralization, units — a pipe: it does not depend on component state and can be reused anywhere. A filtered list, an aggregate, an "overdue" flag — a `computed`: it is tied to state and must be memoized by signals. A pipe that filters an array (`| filterBy`) is the classic anti-pattern: pure, it will not see mutations; impure, it runs on every check.

## React parallels

- **Directives have no React equivalent.** In React, behaviour on someone else's element is expressed either as a hook (`useHover`, `useClickOutside`) returning props you must spread yourself, or as a wrapper component that adds a node to the DOM. A directive adds no nodes and attaches through an attribute — closer to "a mixin for an element" than to anything in React.
- **`hostDirectives` versus HOCs and hook composition.** An HOC wraps the component in a new layer of the tree; hook composition requires a manual call in the body. `hostDirectives` attaches behaviour to the host element declaratively, with no extra nodes and no changes to the component body — and with inputs private by default, so the component's API is never widened by accident.
- **A pipe versus a function in JSX.** In JSX you simply call `formatDate(x)`, and that is fine because the component body runs a bounded number of times. In Angular a function in a template runs on every check and is never cached; a pure pipe caches by its input. That is not a matter of style but of cost.
- **A structural directive versus conditional rendering.** `{cond && <X/>}` is an ordinary JS expression: React evaluates both sides as values and picks by the result. A structural directive receives a **template**, not a result: the body is not evaluated until the directive creates a view. Hence the ability to render it zero times, five times, or later — without rebuilding the expression itself.
- **Where the habit breaks:** trying to port "a helper in JSX" into a pipe that filters a list. In React `{items.filter(f).map(...)}` is predictable; in Angular `| filterBy` forces a choice between "will not see mutations" (pure) and "runs always" (impure). The right answer is not to filter in the template at all: filtering belongs in a `computed` (chapter 02).

## What you will see in legacy code

- **`*ngIf` / `*ngFor` / `[ngSwitch]`** with `CommonModule` in `imports`. These are exactly the structural directives whose mechanics the diagram above describes; the new control flow does the same without an intermediary directive.
- **`*ngIf="user$ | async as user; else loading"`** with `<ng-template #loading>` — the classic "impure pipe plus structural directive" combo, replaceable by `@if` over a signal.
- **`@HostBinding('class.active')` and `@HostListener('mouseenter')`** inside directives instead of the `host` object (chapter 01). In directives this shows up even more often than in components.
- **Behaviour through inheritance:** `export class TicketCard extends BaseHighlightComponent` — precisely what `hostDirectives` was introduced for. The tell: a base class carrying a `@Directive()` decorator with no selector that components extend.
- **Filter pipes:** `*ngFor="let t of tickets | filterByStatus: status | orderBy: 'date'"` with `pure: false`. Such code is both slow and a source of new arrays on every check, which breaks `trackBy`.
- **`constructor(private el: ElementRef, private renderer: Renderer2)`** with manual `renderer.addClass(...)` instead of host bindings — how directives were written before bindings became declarative.

## What we add to the project

The ticket card gets a directive that highlights overdue tickets (a class and an attribute on the host element, with no markup changes) and an SLA pipe that turns hours into a human-readable "2h left" / "overdue by 3h". Plus `hostDirectives` — attaching the behaviour to the card without inheritance.

## Exercise

**Input:** the project from chapter 05 (two stores, components without state).
**Output:** a directive, a pipe, and behaviour composition through `hostDirectives`.

Requirements:

1. An `slaRemaining` pipe: takes a ticket (or `createdAt` + `slaHours`) plus the current time and returns strings like `2h left`, `30m left`, `overdue by 3h`, `no SLA`. The pipe must be pure — work out how that is possible when the result depends on "now" (hint: "now" can be an input).
2. An `appOverdue` directive: adds a class and an aria attribute to the element when the SLA is breached. No `ElementRef`/`Renderer2` — only the `host` object and signals. Take the input via `input.required()` with an alias so that `[appOverdue]="ticket"` works.
3. Attach the directive to the card in two ways: as an attribute in the list template, and via `hostDirectives` inside the card itself. Compare them: where each is appropriate, and what happens to inputs in the second case.
4. A structural directive `*appHasRole="'admin'"`: renders its content only if the current user has the role (take the role from `APP_CONFIG` or a stub service for now — authorization arrives in chapter 07). Implement it with `TemplateRef` + `ViewContainerRef`, adding a template guard or context as needed.
5. Measuring the cost: write a temporary impure pipe that logs on every call and observe how often it runs while you type in the search box. Then switch to a pure pipe and compare.
6. Constraint: no filtering or sorting inside pipes.

Edge cases to think about:

- A pure pipe receives a ticket object. What happens when the ticket is updated through `update(id, patch)` in the store, and why?
- A directive sits on an element inside an `@if`. When does its constructor run, and when is it destroyed?
- A `hostDirectives` input is not listed in `inputs`. How do you pass a value into it, and why is that the default?
- `*appHasRole` inside a `@for`: how many directive instances are created, and what happens when the list changes?
- Why is `{{ ticket.createdAt | date: 'short' }}` cheaper than `{{ formatDate(ticket.createdAt) }}` even though both lines look the same?

## Solution walkthrough

`src/app/tickets/sla-remaining-pipe.ts`:

```ts
import { Pipe, PipeTransform } from '@angular/core';
import { Ticket } from './ticket';

@Pipe({
  name: 'slaRemaining',
  // pure by default — we keep it. Purity is possible because "now" is
  // passed as an argument: the pipe stays a function of its inputs
})
export class SlaRemainingPipe implements PipeTransform {
  transform(ticket: Ticket, now: number): string {
    if (ticket.slaHours === undefined) return 'no SLA';

    const deadline = new Date(ticket.createdAt).getTime() + ticket.slaHours * 3_600_000;
    const diffMinutes = Math.round((deadline - now) / 60_000);

    if (diffMinutes < 0) return `overdue by ${formatSpan(-diffMinutes)}`;
    return `${formatSpan(diffMinutes)} left`;
  }
}

// The logic lives in a plain function: if the same formatting is ever needed
// in a service or a test, call this rather than injecting the pipe class
function formatSpan(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  return `${Math.round(minutes / 60)}h`;
}
```

`src/app/tickets/overdue-directive.ts`:

```ts
import { Directive, computed, input } from '@angular/core';
import { Ticket } from './ticket';

@Directive({
  // an attribute selector: the directive adds no node to the DOM
  selector: '[appOverdue]',
  host: {
    '[class.is-overdue]': 'isOverdue()',
    '[class.is-at-risk]': 'isAtRisk()',
    // an attribute, not a property: title does have a DOM property, but null
    // here must REMOVE the attribute, and only [attr.] can do that (chapter 01)
    '[attr.data-sla-state]': 'state()',
  },
})
export class OverdueDirective {
  // the alias lets you write [appOverdue]="ticket" — the input name matches
  // the selector, exactly as *ngIf/*ngFor did
  readonly ticket = input.required<Ticket>({ alias: 'appOverdue' });
  readonly now = input(Date.now());

  private readonly minutesLeft = computed(() => {
    const { createdAt, slaHours } = this.ticket();
    if (slaHours === undefined) return null;
    const deadline = new Date(createdAt).getTime() + slaHours * 3_600_000;
    return Math.round((deadline - this.now()) / 60_000);
  });

  protected readonly isOverdue = computed(() => (this.minutesLeft() ?? 1) < 0);
  protected readonly isAtRisk = computed(() => {
    const left = this.minutesLeft();
    return left !== null && left >= 0 && left < 60;
  });
  protected readonly state = computed(() =>
    this.minutesLeft() === null ? null : this.isOverdue() ? 'overdue' : 'ok',
  );
}
```

The first way to attach it — an attribute in the list template:

```html
@for (ticket of board.filtered(); track ticket.id) {
  <li [appOverdue]="ticket" [now]="now()">
    <app-ticket-card [ticket]="ticket" />
  </li>
}
```

The second — composition inside the card itself:

```ts
@Component({
  selector: 'app-ticket-card',
  imports: [DatePipe, SlaRemainingPipe],
  // The behaviour attaches to the card's host element. The directive instance
  // is created before the component, so its bindings apply first
  hostDirectives: [
    {
      directive: OverdueDirective,
      // without this line the input would stay private: writing [appOverdue]
      // from outside would be impossible. Here we forward it as ticket, so
      // [ticket]="…" on the card feeds both the component and the directive
      inputs: ['appOverdue: ticket'],
    },
  ],
  templateUrl: './ticket-card.html',
  styleUrl: './ticket-card.css',
})
export class TicketCard {
  readonly ticket = input.required<Ticket>();
  protected readonly now = input(Date.now());
}
```

`src/app/tickets/ticket-card.html` — the pipe in action:

```html
@let t = ticket();

<h3>{{ t.title }}</h3>
<p class="ticket-card__sla">{{ t | slaRemaining: now() }}</p>
<p class="ticket-card__created">{{ t.createdAt | date: 'mediumDate' }}</p>
```

`src/app/core/has-role-directive.ts` — the structural directive:

```ts
import { Directive, TemplateRef, ViewContainerRef, effect, inject, input } from '@angular/core';
import { CurrentUser } from './current-user';

@Directive({ selector: '[appHasRole]' })
export class HasRoleDirective {
  // TemplateRef — the content the compiler wrapped in an <ng-template>
  private readonly tpl = inject(TemplateRef<unknown>);
  // ViewContainerRef — the place in the DOM that content can be inserted into
  private readonly vcr = inject(ViewContainerRef);
  private readonly user = inject(CurrentUser);

  readonly role = input.required<string>({ alias: 'appHasRole' });

  constructor() {
    // An effect is right here: the result is not a value but an imperative
    // action on the view container (chapter 02)
    effect(() => {
      const allowed = this.user.roles().includes(this.role());
      this.vcr.clear();
      if (allowed) this.vcr.createEmbeddedView(this.tpl);
    });
  }

  // A hint to the compiler about the context type: without it strictTemplates
  // cannot check the expressions inside the template
  static ngTemplateContextGuard(_dir: HasRoleDirective, _ctx: unknown): _ctx is object {
    return true;
  }
}
```

Usage:

```html
<button type="button" *appHasRole="'admin'" (click)="tickets.reset()">
  Reset demo data
</button>
```

Answers to the edge cases:

- `update(id, patch)` creates a **new** ticket object (`{ ...ticket, ...patch }`), so the reference changes and the pure pipe recomputes. Had the store mutated the object in place, the pipe would return its cached value — one of the reasons immutability in the store is not ideology but a precondition for the other mechanisms.
- The directive's constructor runs when the view is created — that is, when the `@if` first becomes true. Switching the condition to `false` destroys the embedded view along with the directive (`ngOnDestroy` and `DestroyRef.onDestroy` fire), and switching back creates a **new** instance. Directive state does not survive between those cycles.
- You cannot pass one: unlisted inputs of a host directive are private and invisible from outside. That is deliberate, so attaching behaviour never widens a component's public API by accident: the component's author decides which inputs to expose and under what name (`'appOverdue: ticket'`).
- One directive instance per list item — each with its own `TemplateRef` and its own embedded view. When the list changes, `@for` reuses views by `track`: directives survive for the items that remain, are destroyed for removed ones and created for new ones.
- `date` is a pure pipe: the result is cached by its input value and recomputed only when that value changes. A class method has no cache at all and runs on every check of the template — and how many checks there are is decided by change detection, not by you (chapter 03). The two lines look alike, but the first means "compute once per new value" and the second means "compute always".

## Check yourself

1. Explain in your own words what a structural directive receives instead of a ready-made expression result, and what that enables.
2. Why does a pure pipe miss a mutation of an array, and why is `pure: false` a poor fix for that?
3. How is `hostDirectives` better than component inheritance, and why are a host directive's inputs private by default?
4. What tells you whether a given transformation should be a pipe or a `computed`?
5. A directive applies a class. Why through the `host` object rather than `ElementRef` + `Renderer2`, and what do you lose with the latter?

<details>
<summary>Answers</summary>

1. A structural directive receives a `TemplateRef` — a "recipe" for markup that has not become DOM yet — plus a `ViewContainerRef`, the place it can be inserted into. The template body is not evaluated until the directive calls `createEmbeddedView()`. That grants three abilities an ordinary expression lacks: not rendering at all (and not paying for node creation), rendering several times with different contexts (`$implicit`, an index), and rendering later — on an event, a permission check, a load. The directive also controls destruction: `clear()` destroys the view together with every nested component and its state.
2. A pure pipe recomputes only when a primitive value or an object **reference** changes. Mutating an array leaves the reference intact, so the input "did not change" and the cached value comes back. `pure: false` does address the symptom — the pipe will now always run — but at the price of losing caching entirely: it executes on every check of the template, for every place it is written, and the number of checks is decided by change detection. The correct fix is not to mutate: update data immutably and the pure pipe will see a new reference.
3. Inheritance couples components rigidly: one chain, name collisions, no way to attach two behaviours at once, and a base class that accumulates logic for all descendants over time. `hostDirectives` is composition: several independent behaviours can be attached, each with its own state and lifecycle, without touching the component body and without adding DOM nodes. Inputs are private by default because attaching behaviour must not silently widen the component's public API: the author explicitly decides which inputs to expose and under what name — otherwise an internal implementation detail would become part of the contract.
4. The criterion is what the transformation depends on. If it is a pure function of a value (date format, units, pluralization), it is unrelated to component state, reusable in any template, and fits a pipe with its input-keyed cache. If the result depends on state (filters, selection, aggregates over a list), it is a `computed`: memoized by its signal dependencies, recomputed exactly when they change, and testable without a template. The tell-tale sign of a mistake is a pipe that needs three or four state arguments — that is a `computed` in disguise.
5. The `host` object is a declarative binding: Angular applies and removes the class as the expression changes, participates in change detection and behaves correctly when bindings collide. `ElementRef` + `Renderer2` is an imperative write: you must decide when to update, remove the class yourself when the condition flips, and manage the lifecycle by hand — and direct access to the native element additionally breaks portability (SSR and non-DOM platforms) and opens the door to XSS when working with content. The practical outcome: more code, less predictable behaviour on toggles, and tests that need a real DOM.

</details>

## Common mistake

The first one is a pipe instead of a `computed` for filtering and sorting. The temptation is understandable: in React `{items.filter(f)}` goes straight into the markup, and you want "the same thing, the Angular way". The result is `| filterBy: status | orderBy: 'date'`, which either misses changes (a pure pipe caches by reference) or becomes `pure: false` and starts running on every check of the template. Worse, such a pipe returns a **new array** on every call, so `@for` receives a new collection and has to re-match items by `track` — precisely the extra work `track` exists to prevent (chapter 01). The rule: a pipe formats one value; anything that filters, sorts or aggregates lives in a `computed`.

The second is a directive that reaches into the DOM by hand. A developer arriving from React reasons by analogy with `ref`, grabs an `ElementRef` and starts writing `nativeElement.classList.add(...)`, `nativeElement.style.color = ...`, and in the worst cases `innerHTML`. This works right up to the first change of the condition: the class has to be removed manually, and toggling branches leaves DOM state out of sync with data state. Direct access to `nativeElement` also breaks rendering outside the browser (SSR — chapter 15) and, with `innerHTML`, bypasses the built-in sanitizer. Practically everything a directive needs can be expressed declaratively: `[class.x]`, `[style.y]`, `[attr.z]` and `(event)` in the `host` object — and the rare exceptions (measurements, focus, integrating a third-party widget) belong in `afterRenderEffect` (chapter 03).
