# RxJS in Angular

## Theory

### The Observable model in five minutes

Learning RxJS properly is a large topic of its own; what follows is the minimum without which Angular code does not read.

An **Observable** describes a stream of values over time. The key difference from a Promise: a promise is one value and work that has already started, an Observable is any number of values and a **deferred start**. Until something subscribes, nothing happens (that is exactly the "coldness" of `HttpClient` from chapter 08). Subscribing returns an object you can tear down, and tearing down aborts the work — which is how HTTP cancellation works.

A stream can complete (`complete`) or fail (`error`); after either, no more values arrive. A `Subject` is a stream you can push values into by hand (`next()`); a `BehaviorSubject` is the same but holds a current value that new subscribers receive immediately. That is precisely why `BehaviorSubject` served as a stand-in for signals for a decade.

Operators are pure functions composed into a pipeline through `pipe()`: `map`, `filter`, `debounceTime`, `switchMap`, `catchError`, `retry`, `startWith`, `distinctUntilChanged`. Their strength is time: delays, windows, ordering, cancellation, combining several sources. That is what remains RxJS's territory in modern Angular. For a deeper dive into the model and the operators (marble diagrams, hot versus cold, backpressure) keep [rxjs.dev](https://rxjs.dev) at hand — from here on this chapter is only about the seam with Angular.

Versions: Angular 22 works with RxJS 7 (`peerDependencies: rxjs ^6.5.3 || ^7.4.0`). `toPromise()` is deprecated in 7 — use `firstValueFrom`/`lastValueFrom` instead.

### What stayed with RxJS

```
                   Where RxJS stayed and where signals replaced it
┌─────────────────────────┬──────────────────────────┬───────────────────────────────┐
│ the task                │ the RxJS way             │ today                         │
├─────────────────────────┼──────────────────────────┼───────────────────────────────┤
│ component state         │ BehaviorSubject + async  │ signal                        │
├─────────────────────────┼──────────────────────────┼───────────────────────────────┤
│ a derived value         │ combineLatest + map      │ computed                      │
├─────────────────────────┼──────────────────────────┼───────────────────────────────┤
│ loading screen data     │ switchMap + subscribe    │ httpResource                  │
├─────────────────────────┼──────────────────────────┼───────────────────────────────┤
│ router events           │ router.events            │ RxJS: there is no other API   │
├─────────────────────────┼──────────────────────────┼───────────────────────────────┤
│ search with debounce    │ debounceTime + switchMap │ RxJS: timing is its domain    │
├─────────────────────────┼──────────────────────────┼───────────────────────────────┤
│ polling, intervals      │ interval + switchMap     │ RxJS or a timer plus a signal │
├─────────────────────────┼──────────────────────────┼───────────────────────────────┤
│ form valueChanges       │ valueChanges             │ RxJS inside Reactive Forms    │
├─────────────────────────┼──────────────────────────┼───────────────────────────────┤
│ teardown in a component │ takeUntil(destroy$)      │ takeUntilDestroyed()          │
└─────────────────────────┴──────────────────────────┴───────────────────────────────┘
                   the rule: state and derived values are signals;
      anything where TIME matters (delays, windows, order, cancellation) is RxJS
```

Signals took from RxJS the jobs it was overkill for: holding a value and computing derived values. What remains is where it is irreplaceable: **coordination in time**. Plus a handful of framework APIs that hand you Observables and offer no other interface: `router.events`, `valueChanges`/`statusChanges` in Reactive Forms, `HttpClient` (though screen data now usually goes through `httpResource`), and outputs of older components built on `EventEmitter`.

### The bridge between the two models

```
           toSignal(obs$)                       toObservable(sig)
┌─────────────────────────────────┐    ┌──────────────────────────────────┐
│ Observable → Signal             │    │ Signal → Observable              │
│                                 │    │                                  │
│ subscribes immediately and      │    │ values arrive through an effect: │
│ unsubscribes when the injection │    │ not synchronously, but on the    │
│ context is destroyed            │    │ next synchronization             │
│                                 │    │                                  │
│ an initial value is required:   │    │ intermediate values may never    │
│ initialValue or requireSync     │    │ reach the stream                 │
│                                 │    │                                  │
│ a stream error is rethrown when │    │ needs an injection context       │
│ the signal is read              │    │ or an explicit injector          │
└─────────────────────────────────┘    └──────────────────────────────────┘
   the common direction: an RxJS       rarely needed: only to feed a signal
     pipeline ends in a signal            into an existing RxJS pipeline
```

Everything comes from `@angular/core/rxjs-interop`:

```ts
// Observable → Signal. A signal always has a value, a stream does not,
// hence either initialValue or requireSync for synchronous sources
readonly params = toSignal(this.route.params, { requireSync: true });
readonly user = toSignal(this.userService.user$, { initialValue: null });

// Signal → Observable
readonly query$ = toObservable(this.query);

// Teardown tied to the lifetime of a component or service
this.router.events.pipe(takeUntilDestroyed()).subscribe(/* … */);
```

`toSignal` options: `initialValue`, `requireSync` (throw if the stream does not emit synchronously), `equal`, `injector` (when called outside an injection context), `manualCleanup` (the subscription lives until the stream completes rather than until the context is destroyed — a rare and risky choice).

`rxjs-interop` also ships:

- **`rxResource({ params, stream })`** (`@publicApi 22.0`) — the `resource` from chapter 08 with a loader that returns an Observable. Note the field name: **`stream`**, not `loader`.
- **`outputFromObservable`/`outputToObservable`** — a bridge between `output()` and streams.
- **`pendingUntilEvent`** (developer preview) — marks the application unstable until an emit; needed for SSR and tests (chapter 03).

### Recipes where RxJS wins

```
┌────────────┬──────────────────────────────────┬─────────────────────────┐
│ operator   │ what it does to the previous one │ typical use             │
├────────────┼──────────────────────────────────┼─────────────────────────┤
│ switchMap  │ cancels the previous request     │ search, filter change   │
├────────────┼──────────────────────────────────┼─────────────────────────┤
│ concatMap  │ waits for it, preserving order   │ a queue of saves        │
├────────────┼──────────────────────────────────┼─────────────────────────┤
│ mergeMap   │ runs them in parallel            │ independent loads       │
├────────────┼──────────────────────────────────┼─────────────────────────┤
│ exhaustMap │ ignores new ones while busy      │ double-click protection │
└────────────┴──────────────────────────────────┴─────────────────────────┘
```

Choosing an operator means choosing a policy towards the previous operation, and here RxJS has no equivalent among the signal APIs. Live search (`debounceTime` + `distinctUntilChanged` + `switchMap`), sequential saves (`concatMap`), polling (`interval` + `switchMap`), double-submit protection (`exhaustMap`) — all described declaratively, whereas signals would need timers, flags and manual cancellation.

### The fate of the async pipe

`AsyncPipe` is not deprecated and it works: it subscribes, unsubscribes on destroy and calls `markForCheck()` on every emit (chapter 03 — which is why older `| async` code survived the move to zoneless). But in new code it is nearly unnecessary: `toSignal` does the same and yields a signal you can read repeatedly, combine in a `computed` and pass into inputs. It also removes a painful quirk of `| async`: two `| async` in one template are two subscriptions, and therefore two requests when the stream is cold.

## React parallels

- **`toSignal` ≈ `useSyncExternalStore` in purpose.** Both connect an external source to the framework's reactivity. The difference is in the requirements: `toSignal` must always have a value, hence `initialValue` or `requireSync` — a signal has no "no value yet" state, unlike a stream.
- **Teardown.** In React the cleanup is returned from `useEffect`, and forgetting it is hard: it sits in the same code. In Angular a subscription lives outside the render body, which is why three generations of solutions appeared: manual `unsubscribe`, `takeUntil(destroy$)`, and now `takeUntilDestroyed()`. Signals remove the whole class of bugs — there is nothing to unsubscribe from.
- **Cancelling requests.** In React cancellation is written by hand with an `AbortController`. `switchMap` does the same as a by-product of its semantics — "switch to a new source" *means* "abort the old one".
- **Debounce.** In React you usually reach for a `useDebouncedValue` hook or a `setTimeout` in an effect; in RxJS it is one operator inside the pipeline, and the same operator guarantees only the last value reaches the server while intermediate requests are aborted.
- **Where the habit breaks:** a React developer treats an Observable as a promise and writes `firstValueFrom` (or a subscription) where a live stream is needed — getting one value instead of a stream of events. The opposite mistake is dragging RxJS where a signal suffices: a `BehaviorSubject` for component state now reads like code from 2021.

## What you will see in legacy code

- **`private destroy$ = new Subject<void>()`** plus `takeUntil(this.destroy$)` on every subscription and `this.destroy$.next()` in `ngOnDestroy`. Today that is one line: `takeUntilDestroyed()`.
- **Manual subscriptions with no teardown** in `ngOnInit` — a leak source: the component is destroyed while the subscription to `router.events` or to a service stream lives on.
- **A `BehaviorSubject` store** with `state$ | async` in the template (chapter 05), and `combineLatest([a$, b$, c$]).pipe(map(...))` where three `computed` values would do today.
- **Nested subscriptions:** `a$.subscribe(a => b$.subscribe(b => ...))` — the classic mistake that `switchMap`/`concatMap` solves.
- **`.toPromise()`** (deprecated in RxJS 7) and `async`/`await` over streams instead of `firstValueFrom`/`lastValueFrom`.
- **`shareReplay(1)`** as a way to cache an HTTP response in a service — it works, but without `refCount` it keeps the subscription forever; the modern replacement is `httpResource` or a signal store.

## What we add to the project

Support Desk gains live search with a delay and cancellation of previous requests, polling for the new-tickets counter, and a reaction to router events — three places where RxJS is still the right tool. All of them end in signals, so templates never learn about streams.

## Exercise

**Input:** the project from chapter 08 (the HTTP layer, `httpResource`, interceptors).
**Output:** three RxJS scenarios embedded in a signal-based architecture.

Requirements:

1. Live search: typing → a 300 ms delay → ignoring repeats → a request to `/api/tickets?q=` with the previous one cancelled. Implement it two ways and compare: (a) `toObservable(signal)` + `debounceTime` + `switchMap` + `toSignal`; (b) `httpResource` with a reactive URL and a separate "debounce signal". Explain what the second one loses.
2. Polling: the new-tickets counter refreshes every 15 seconds, but **not** while the tab is hidden (`document.visibilityState`). The stream must stop when the service is destroyed. No hand-written `setInterval`.
3. Router events: show a loading indicator between `NavigationStart` and `NavigationEnd`/`NavigationCancel`/`NavigationError`. This is the only way — the router has no signal API for events.
4. Teardown: not a single `destroy$`. Use `takeUntilDestroyed()` everywhere, or better `toSignal`, which unsubscribes itself.
5. Saving the form: protect the button from a double click with the operator that ignores new clicks while a request is in flight. Explain why not `switchMap`.
6. Constraint: no `| async` anywhere in the templates. Everything that reaches the markup is a signal.

Edge cases to think about:

- `toSignal` without `initialValue` and without `requireSync`: what type do you get, and what does the signal return before the first value?
- What happens if the stream inside `toSignal` fails, and where does that error surface?
- Why does `toObservable` not emit every intermediate value of a signal, and when does that matter?
- Two `| async` over one cold stream in a template — how many HTTP requests, and why does `toSignal` not have that problem?
- Your polling uses `switchMap`. What changes when a request takes longer than the interval?

## Solution walkthrough

`src/app/tickets/ticket-search.ts` — live search:

```ts
import { Service, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { debounceTime, distinctUntilChanged, map, of, startWith, switchMap } from 'rxjs';
import { TicketApi } from './ticket-api';
import { Ticket } from './ticket';

@Service({ autoProvided: false })
export class TicketSearch {
  private readonly api = inject(TicketApi);

  // the input stays a signal: the template writes into it directly
  private readonly queryInput = signal('');
  readonly query = this.queryInput.asReadonly();

  // The pipeline: signal → stream → time operators → signal again.
  // This is exactly where RxJS is irreplaceable: debouncing and cancelling
  private readonly results$ = toObservable(this.queryInput).pipe(
    map((q) => q.trim()),
    debounceTime(300),                 // wait for a pause in typing
    distinctUntilChanged(),            // "abc" → "abc" needs no second request
    switchMap((q) =>
      q.length < 2
        ? of([] as readonly Ticket[])  // too short — do not hit the network
        : this.api.list({ q }),        // switchMap CANCELS the previous request
    ),
    startWith([] as readonly Ticket[]),
  );

  // The pipeline ends in a signal: the template knows nothing about RxJS,
  // and teardown happens when the service is destroyed
  readonly results = toSignal(this.results$, { requireSync: true });
  readonly hasQuery = computed(() => this.query().trim().length >= 2);

  setQuery(value: string): void {
    this.queryInput.set(value);
  }
}
```

`src/app/tickets/new-tickets-feed.ts` — polling that respects tab visibility:

```ts
import { DestroyRef, Service, inject } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { fromEvent, interval, map, startWith, switchMap } from 'rxjs';
import { TicketApi } from './ticket-api';

@Service()
export class NewTicketsFeed {
  private readonly api = inject(TicketApi);

  // A stream of tab visibility: while the tab is hidden polling is pointless —
  // the most common source of wasted traffic
  private readonly visible$ = fromEvent(document, 'visibilitychange').pipe(
    map(() => document.visibilityState === 'visible'),
    startWith(document.visibilityState === 'visible'),
  );

  private readonly count$ = this.visible$.pipe(
    // switchMap: leaving the tab cancels the inner interval,
    // coming back creates it again
    switchMap((visible) => (visible ? interval(15_000).pipe(startWith(0)) : [])),
    switchMap(() => this.api.list({ status: 'new' })),
    map((tickets) => tickets.length),
    // the subscription lives no longer than the service; without this the
    // polling would keep running after destruction (in a root service —
    // for the rest of the application's life)
    takeUntilDestroyed(inject(DestroyRef)),
  );

  readonly count = toSignal(this.count$, { initialValue: 0 });
}
```

`src/app/core/navigation-progress.ts` — router events:

```ts
import { Service, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import {
  NavigationCancel,
  NavigationEnd,
  NavigationError,
  NavigationStart,
  Router,
} from '@angular/router';
import { filter, map } from 'rxjs';

@Service()
export class NavigationProgress {
  private readonly router = inject(Router);

  // The router has NO signal API for events — this is the case where RxJS
  // is mandatory rather than a stylistic choice
  private readonly inProgress$ = this.router.events.pipe(
    filter(
      (e) =>
        e instanceof NavigationStart ||
        e instanceof NavigationEnd ||
        e instanceof NavigationCancel ||
        e instanceof NavigationError,
    ),
    map((e) => e instanceof NavigationStart),
  );

  // the output is a signal: the template reads it as an ordinary value
  readonly isNavigating = toSignal(this.inProgress$, { initialValue: false });
}
```

Protecting the form from a double submit:

```ts
export class TicketForm {
  private readonly api = inject(TicketApi);
  private readonly submit$ = new Subject<TicketDto>();

  constructor() {
    this.submit$
      .pipe(
        // exhaustMap ignores new clicks while the current request is in flight.
        // switchMap here would be sabotage: it would ABORT a POST that has
        // already been sent, and the server may have executed it
        exhaustMap((dto) => this.api.create(dto)),
        takeUntilDestroyed(),
      )
      .subscribe(() => void this.router.navigate(['/tickets']));
  }

  protected save(dto: TicketDto): void {
    this.submit$.next(dto);
  }
}
```

The second variant of live search — without RxJS, through `httpResource`:

```ts
// a "debounce signal": the value reaches the URL with a delay
private readonly debouncedQuery = signal('');

constructor() {
  effect((onCleanup) => {
    const q = this.query();                     // the dependency
    const timer = setTimeout(() => this.debouncedQuery.set(q), 300);
    onCleanup(() => clearTimeout(timer));       // cancel the previous timer
  });
}

private readonly resource = httpResource<readonly Ticket[]>(
  () => `${this.config.apiUrl}/tickets?q=${encodeURIComponent(this.debouncedQuery())}`,
  { defaultValue: [] },
);
```

It works, and `httpResource` handles request cancellation. But notice the cost: an `effect` that writes a signal appeared (chapter 02 called that a smell), the timer has to be cleared by hand, and `distinctUntilChanged` plus "do not search on one letter" must be added as separate conditions. This is exactly the situation RxJS remains in Angular for: the moment time enters the problem, a declarative pipeline is shorter and more honest than hand-rolled timers.

Answers to the edge cases:

- Without `initialValue` and `requireSync` the type is `Signal<T | undefined>`, and until the first value the signal returns `undefined`. That honestly reflects the gap between the models: a stream may have no value, a signal cannot, so `undefined` is substituted as a placeholder. For synchronous sources (`route.params`, a `BehaviorSubject`) prefer `requireSync: true` — the type loses `undefined`, and a broken contract fails immediately rather than producing "sometimes undefined in the template".
- The error is not lost: `toSignal` remembers it and rethrows it **when the signal is read**. So the exception surfaces in the template or in the `computed` that reads it — and the debugger shows the read stack, not the stream's. That is why error handling belongs inside the pipeline (`catchError`) rather than relying on the rethrow.
- `toObservable` is implemented with an `effect`: values are published not at `set` time but at the next synchronization. If the signal changed three times between two synchronizations, only the last value reaches the stream. For UI that is correct, but if you need every intermediate event (a click counter, say), a signal is the wrong source: send events into a `Subject` directly.
- Two `| async` over one cold stream produce **two requests**: each subscription starts the work anew. The classic workarounds are `shareReplay(1)` or a single `| async` with `as`. `toSignal` does not have the problem by construction: it subscribes once, and the signal can be read as often as you like because reading a signal is not a subscription.
- If the request outlasts the interval, `switchMap` aborts the unfinished one and starts a new one — the counter keeps updating, but on a slow network a cycle may never complete. If every request must finish, use `concatMap` (a queue) or `exhaustMap` (skip ticks while a request is in flight). For polling the right answer is usually `exhaustMap`: it builds no queue and does not pile load onto the server.

## Check yourself

1. Explain in your own words why signals did not replace RxJS entirely, and name three tasks where RxJS remains the right choice.
2. Why does `toSignal` require `initialValue` or `requireSync`? What does that say about the difference between an Observable and a signal?
3. Why is `switchMap` right for search but dangerous for saving a form? Which operator does the second case need?
4. What does `takeUntilDestroyed()` do, and why is it needed less often in signal code than in RxJS code?
5. How is `toSignal(obs$)` better than `obs$ | async` in a template? Name two concrete differences.

<details>
<summary>Answers</summary>

1. Signals describe **a value at the current moment**: a signal always has a value, and neither history nor timing is expressible in it. RxJS describes **events over time**, so it can do what signals cannot: delays and windows (`debounceTime`, `throttleTime`), a policy towards the previous operation (`switchMap`/`concatMap`/`exhaustMap`), combining sources while preserving order, and cancellation. Three tasks: live search with a delay and cancellation of the previous request; polling that depends on external conditions (tab visibility, connectivity); a sequence of requests where order matters or double submission must be prevented. Plus the framework APIs that only hand out Observables: router events, form `valueChanges`.
2. Because a signal has no "no value yet" state while a stream does: time may pass between subscribing and the first emit (or no value may ever arrive). `toSignal` must return something on the first read, so either you supply an `initialValue` or you promise `requireSync: true` — that the source is synchronous (a `BehaviorSubject`, `route.params`) — and then the signal is typed without `undefined` and a broken promise becomes an explicit error. That is exactly where the two models fail to line up: an Observable is about events in time, a signal is about a value that always exists.
3. On a new value `switchMap` **aborts the previous inner stream**. For search that is precisely right: results of an outdated request are useless and cancelling saves network. For saving it is dangerous: an already-sent `POST` gets aborted, but the server may have processed it — leaving you with a created entity the client does not know about, or a half-applied change. For a second click on the button the right operator is `exhaustMap`: it ignores new events while the current request is in flight. If every request must run and order matters, use `concatMap`.
4. `takeUntilDestroyed()` is an operator that completes a stream when the injection context (a component, directive or service) is destroyed: it takes the `DestroyRef` from the context or accepts it as an argument. It replaces the `destroy$` + `takeUntil` pattern. In signal code it is needed less often because there are barely any subscriptions: a `computed`'s dependency on a signal is a graph edge rather than a subscription and dies with the unreachable node; `toSignal` unsubscribes itself; `httpResource` cancels its own requests. `takeUntilDestroyed` remains for the cases where you genuinely subscribe by hand: router events, form streams, your own `Subject`s.
5. First, `toSignal` subscribes **once** while the result can be read any number of times: two `| async` over one cold stream are two subscriptions and two HTTP requests, and the only ways around it are `shareReplay` or an `as` variable. Second, the result of `toSignal` is an ordinary signal: it can be combined in a `computed`, passed into child inputs, read in an `effect` — whereas `| async` exists only inside the template. On top of that a signal takes part in change detection surgically, while `AsyncPipe` is built as an impure pipe, so it is invoked on every pass and calls `markForCheck()` on every emit.

</details>

## Common mistake

The first is treating an Observable as a promise. React experience leaves the reflex of "get the value and move on", producing code like `const tickets = await firstValueFrom(this.api.list({}))` where a live stream is needed, or a subscription inside a subscription: `this.route.params.subscribe(p => this.api.byId(p.id).subscribe(...))`. The latter is especially treacherous: the outer stream keeps emitting, inner subscriptions accumulate, nobody cancels the earlier requests, and while switching tickets quickly the screen receives the response for a ticket that is no longer open. The cure is an operator instead of nesting: `switchMap` (for navigation and search), or `concatMap`/`exhaustMap` when cancellation is not allowed.

The second is dragging RxJS where a signal suffices. The symptoms: a `BehaviorSubject` for component state, `combineLatest` for two flags, `shareReplay(1)` as a "cache" and `| async` in five places in the template. Such code works but costs more: subscriptions must be torn down, cold streams duplicate requests, and `combineLatest` emits nothing until every source has emitted (the classic "the screen is empty because one stream stays silent" bug). A practical test: if the task is phrased as "what is the value right now", it is a signal; if it is "what happened and in what order", it is RxJS. Mixing them is fine, but the transition should be one-way: an RxJS pipeline ends in `toSignal`, not the other way round.
