# Multicasting and Subscription Management

## Cold vs hot: why there were two requests

The laziness from [Reactive Model and Observables](./01-reactive-model-and-observables.md) means the subscriber function runs **per subscription**. For HTTP that is literal: two subscriptions, two requests.

```
             Cold and hot: how many times the work runs
              the same users$ = http.get(...), two subscriptions

              without share (cold):
subscriber A  --R-----D--|
subscriber B  -----R-----D--|
                   ^ a second request: the work started from scratch

              with share() (hot after the first subscription):
subscriber A  --R-----D--|
subscriber B  --------D--|
                      ^ no request: it joined the shared result
             legend: R — a request went to the network,
      D — data reached the subscriber. Every subscription to a
           cold stream starts the work from the beginning
```

A **cold Observable** creates its own source for every subscriber: `http.get()`, `new Observable(...)`, `defer(...)`, `interval(...)`.

A **hot Observable** has a source that exists independently of subscribers and hands them the same values. Examples are a `Subject`, `fromEvent` (the event happens whether you listen or not) and the result of `share()`.

The most common practical trap looks like this:

```ts
// The service exposes a cold stream
readonly tickets$ = this.http.get<Ticket[]>('/api/tickets');

// The template subscribes twice — and two requests go out
// {{ (tickets$ | async)?.length }} — subscription 1
// @for (t of tickets$ | async) — subscription 2
```

The diagnosis is unambiguous: open the Network tab and count the requests. More requests than logical operations means a cold stream was subscribed to several times. A second technique is temporarily adding `tap({ subscribe: () => console.count('subscribe') })` at the start of the chain.

## share and shareReplay

`share()` inserts a `Subject` between the source and the subscribers. The first subscription starts the source, and the rest join the same result. When no subscribers remain, the source is unsubscribed, so the next subscription starts the work again.

`shareReplay(bufferSize)` does the same but with a buffer: a late subscriber immediately receives the last N values. That is exactly what "load a reference list once and hand it to everyone" needs.

Four call shapes cover the whole choice between them.

| call | what it does | the risk |
|---|---|---|
| `share()` | one source for all active subscribers | a late subscriber misses the past |
| `shareReplay(1)` | the same plus replaying the last value | `refCount` defaults to `false`, which leaks |
| `shareReplay({ bufferSize: 1, refCount: true })` | the source unsubscribes once no subscribers remain | a new subscriber restarts the work from scratch |
| `share({ resetOnRefCountZero: false, resetOnError: true })` | full control: reset on zero subscribers, on error, on complete | you must understand all four flags |

The RxJS docs warn about the second row explicitly. With `refCount: false` the source is **not** unsubscribed when the count drops to zero, and it may "run for ever".

### The leak in shareReplay

Here is the detail spelled out. `refCount: false` is **the default** for the `shareReplay(1)` form. With it the source is **not unsubscribed** when the subscriber count drops to zero, and the inner `ReplaySubject` may "run for ever".

```ts
import { interval, shareReplay } from 'rxjs';

// a leak: the interval keeps ticking after every subscriber has left,
// and it keeps the buffer in memory
const ticks$ = interval(1000).pipe(shareReplay(1));

const sub = ticks$.subscribe();
sub.unsubscribe();   // the interval is alive, values keep flowing into the ReplaySubject

// no leak: the source unsubscribes once no subscribers remain
const safeTicks$ = interval(1000).pipe(
  shareReplay({ bufferSize: 1, refCount: true }),
);
```

The rule is simple:

- **`refCount: true`** — for anything with an ongoing side effect: `interval`, a WebSocket, an event subscription, polling. Otherwise the stream outlives its last subscriber.
- **`refCount: false`** (the default) — sensible for one-shot expensive computations. It also fits HTTP requests you want cached for the whole application lifetime: a reference list, config, the user profile. Here "the source is not unsubscribed" is not a leak but the desired behaviour, because the source has already completed.

The second nuance is error behaviour. `share()` has the flags `resetOnError` (default `true`), `resetOnComplete` and `resetOnRefCountZero`. If a `shareReplay` stream fails, all current subscribers receive the error.

What the *next* subscriber gets — a fresh attempt or the cached error — depends on configuration. A caching reference list usually wants "reset on error", so the next subscription retries.

```ts
// A reference-list cache: keep the value forever, but do not cache the error
readonly categories$ = this.http.get<Category[]>('/api/categories').pipe(
  shareReplay({ bufferSize: 1, refCount: false }),
);
```

> **Legacy.** Multicasting was once assembled by hand: `multicast(() => new Subject()), refCount()` or `publishReplay(1), refCount()`. In RxJS 7 the whole `multicast`/`publish`/`publishReplay`/`publishBehavior`/`refCount` family is deprecated, removed in v8. Replacements: `share()`/`shareReplay()`, plus `connectable(source, { connector })` for manual connection via `connect()`. Code with `publish().refCount()` is RxJS 5-6.

## The rule: subscribe close to the edge

The most practical subscription-management rule reads: **the fewer `subscribe` calls in the code, the less there is to close**. Services return streams; the subscriber is whoever actually consumes the data — a component, an effect, an entry point.

```ts
// bad: the service subscribed itself — now it owns the subscription,
// must close it, and exposes "state" instead of a stream
class TicketService {
  tickets: Ticket[] = [];
  load(): void {
    this.http.get<Ticket[]>('/api/tickets').subscribe((t) => (this.tickets = t));
  }
}

// good: the service returns a stream, the subscription lives with the consumer
class TicketService {
  readonly tickets$ = this.http.get<Ticket[]>('/api/tickets');
}
```

The second level of the same rule concerns display-only values. Hand that subscription to the framework: the `async` pipe in a template, or `toSignal` in Angular. Then there is nothing to close at all.

Six techniques close a subscription, and they are not equally good.

| technique | when it fits | note |
|---|---|---|
| a completing operator | `take(1)`, `first()`, `takeWhile` | the stream closes itself, which is the best option |
| `takeUntil(destroy$)` | a long-lived stream in a component | must be last in the pipe |
| `takeUntilDestroyed()` | Angular: tied to the context lifetime | see the Angular course, RxJS chapter |
| `sub.unsubscribe()` | imperative code, tests | easy to forget on an early return |
| `sub.add(other)` | a subscription tree from one point | a historical trick, rare today |
| `async` pipe / `toSignal` | the value is only needed by a template | teardown is entirely the framework's job |

The rule behind the table: subscribe as close to the edge of the application as possible. Services should return streams rather than subscribe internally.

### takeUntil and why it must come last

```ts
import { Subject, takeUntil, switchMap } from 'rxjs';

private readonly destroy$ = new Subject<void>();

ngOnInit(): void {
  source$.pipe(
    switchMap((x) => load(x)),
    takeUntil(this.destroy$),   // last in the pipe
  ).subscribe(render);
}

ngOnDestroy(): void {
  this.destroy$.next();
  this.destroy$.complete();
}
```

The order is not a style choice. A `takeUntil` placed **not last** leaves the operators after it alive. If a `switchMap` follows `takeUntil`, its inner subscriptions keep running, because `takeUntil` only completed the part of the chain before it.

This is one of the rare situations where operator order affects leaks rather than results.

> **Legacy.** Manual management through `new Subscription()` with `add()` and an `unsubscribe()` in `ngOnDestroy` is the previous generation of solutions. It works but demands discipline at every new subscription. Today components use `takeUntil(destroy$)`, and in Angular `takeUntilDestroyed()`, which finds the destruction context on its own.

## Diagnostics: the stream never completes, the subscription lives on

RxJS leaks do not surface as errors — the application simply grows heavier. The signs and how to check:

**Sign 1: work continues after the screen closes.** Requests in the Network tab after navigating away, timer ticks in the console, a counter that keeps growing in the logs.

**Sign 2: a handler runs several times for one action.** Every screen visit adds another live subscription, so by the third visit a click is handled three times.

**How to check — log the lifecycle:**

```ts
import { tap, finalize } from 'rxjs';

source$.pipe(
  tap({
    subscribe: () => console.log('SUB', label),
    unsubscribe: () => console.log('UNSUB', label),
    complete: () => console.log('COMPLETE', label),
  }),
  finalize(() => console.log('FINALIZE', label)),
);
```

If the log shows ten `SUB` entries against two `UNSUB`, the leak is found. Note that `tap` with an observer object sees both subscribe and unsubscribe, as described in [Transformation and Filtering Operators](./03-transformation-and-filtering-operators.md). And `finalize` fires on any ending — see [Error Handling and Retries](./06-error-handling-and-retries.md).

**How to check in the browser:** take a heap snapshot before and after opening/closing a screen repeatedly. A growing number of `Subscriber`, `SafeSubscriber` or your own component objects points directly at retained subscriptions.

Three questions that localize the problem quickly:

1. **Does the stream complete on its own?** `http.get()` — yes; `interval`, `fromEvent`, a `Subject` — no. A non-completing source plus an unbounded subscription equals a leak.
2. **Is there a `shareReplay` without `refCount: true` over a non-completing source?** Then the source outlives every subscriber.
3. **Is `takeUntil` last?** If flattening operators follow it, their inner subscriptions will not close.

## Relation to other topics

- [Reactive Model and Observables](./01-reactive-model-and-observables.md) — the laziness behind "two subscriptions, two units of work", and teardown on unsubscribe.
- [Creating Streams and Subjects](./02-creating-streams-and-subjects.md) — the `Subject` that sits inside `share`/`shareReplay`.
- [Transformation and Filtering Operators](./03-transformation-and-filtering-operators.md) — `take`, `takeWhile` and `takeUntil` as ways to complete a stream, and `tap` for diagnostics.
- [Flattening Operators](./04-flattening-operators.md) — why nested subscriptions are not closed by an outer unsubscribe.
- [Combination Operators](./05-combination-operators.md) — how many subscriptions `combineLatest` creates on a shared source.
- [Error Handling and Retries](./06-error-handling-and-retries.md) — `finalize` as guaranteed cleanup, and how `share` behaves on an error.

## Common interview traps

- **"Why did the same Observable make three HTTP requests?"** — because it is cold. Every subscription restarts the work, and three `| async` in a template are three subscriptions. What is expected is not only the diagnosis but the fix. That is `shareReplay({ bufferSize: 1, refCount: true })`, or a single subscription with an `as` variable in the template.

- **Not telling cold from hot by the source** — `http.get()`, `defer`, `interval` are cold; a `Subject`, `fromEvent` and the result of `share()` are hot. The practical criterion: does the source of values exist independently of the subscriber?

- **`shareReplay(1)` as "just a cache"** — the default is `refCount: false`. Over an `interval` or a socket that is a leak: the source is not unsubscribed at zero subscribers. The expected answer distinguishes the cases. For a completed HTTP request `refCount: false` is safe and desirable; for an infinite source `refCount: true` is required.

- **Not knowing the error behaviour** — a failed `shareReplay` may hand the cached error to the next subscriber instead of retrying. This is controlled by `share`'s `resetOnError`/`resetOnComplete`/`resetOnRefCountZero` flags.

- **`takeUntil` not last in the `pipe()`** — operators after it keep working, and the inner subscriptions of flattening operators never close. It is a classic "attention to detail" question that has a technical explanation rather than being mere convention.

- **`subscribe` inside a service** — the service becomes the owner of both the subscription and the state. It exposes an array instead of a stream, and a request error terminates it forever. What is expected is the "subscribe close to the edge" rule: the service returns a stream, the consumer subscribes.

- **Answering with `publish().refCount()` or `multicast`** — that whole family is deprecated in RxJS 7 and removed in v8. The expected answer is `share`/`shareReplay`, or `connectable()` for manual connection.

- **"Leaks in RxJS are just forgetting to unsubscribe"** — incomplete. Leaks also arise from `shareReplay` without `refCount`, from nested subscriptions (an outer teardown does not close them), and from `takeUntil` not being last. A good answer includes how to **detect** them: logging `subscribe`/`unsubscribe` through `tap`, and a heap snapshot after repeatedly opening a screen.
