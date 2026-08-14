# Creating Streams and Subjects

## Where streams come from

```
                                                 How to create a stream
┌─────────────────────────┬────────────────────────────────────────────────┬──────────────────────────────────────────┐
│ function                │ what it emits                                  │ when to use it                           │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ of(a, b, c)             │ the values as-is, synchronously, then complete │ constants, tests, a default value        │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ from(source)            │ an array, promise, iterable or async iterable  │ a bridge from existing structures        │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ fromEvent(target, name) │ a value per event, never completes             │ DOM events, an EventEmitter              │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ timer(delay, period?)   │ one value after delay, then every period       │ a delayed start, polling                 │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ interval(period)        │ a counter every period, never completes        │ timers, ticks                            │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ defer(() => stream)     │ rebuilds the source on every subscribe         │ laziness on top of eager code            │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ EMPTY / NEVER           │ completes at once / never emits                │ a neutral element, a stub                │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ throwError(() => err)   │ errors immediately                             │ the error branch in catchError/switchMap │
├─────────────────────────┼────────────────────────────────────────────────┼──────────────────────────────────────────┤
│ new Observable(fn)      │ anything, plus teardown                        │ wrapping a foreign API                   │
└─────────────────────────┴────────────────────────────────────────────────┴──────────────────────────────────────────┘
                             throwError takes a FACTORY: throwError(() => new Error(...)) —
                                     passing a ready value is deprecated in RxJS 7
```

### of and from: different things that look alike

```ts
import { of, from } from 'rxjs';

of([1, 2, 3]).subscribe(console.log);    // [1, 2, 3] — ONE array value
from([1, 2, 3]).subscribe(console.log);  // 1, then 2, then 3 — three values
```

`of` emits its arguments as-is, `from` unrolls anything iterable. That is the first beginner trap: `of(array)` where a stream of elements was intended.

`from` accepts promises, iterables and async iterables, which makes it a universal bridge:

```ts
from(fetch('/api/users'));          // Promise → Observable (one value + complete)
from(new Set([1, 2, 3]));           // any Iterable
from(asyncGenerator());             // AsyncIterable — values as they arrive
```

### defer: laziness on top of eager code

The problem with `from(promise)` is that the promise has already started work (see [Reactive Model and Observables]): such a stream is not lazy, and a second subscription replays the same result instead of issuing a new request. `defer` fixes that by postponing source creation until subscribe time:

```ts
import { defer, from } from 'rxjs';

// NOT lazy: fetch runs once, at creation
const eager$ = from(fetch('/api/time'));

// Lazy: fetch runs on EVERY subscription
const lazy$ = defer(() => from(fetch('/api/time')));

lazy$.subscribe(console.log);  // request #1
lazy$.subscribe(console.log);  // request #2, a fresh value
```

The second use for `defer` is when the value depends on state at subscribe time:

```ts
// Evaluates Date.now() once, when the stream is created
const wrong$ = of(Date.now());

// Evaluates Date.now() on every subscription
const right$ = defer(() => of(Date.now()));
```

### timer and interval

```ts
import { timer, interval } from 'rxjs';

timer(1000);              // one value (0) after a second, then complete
timer(1000, 5000);        // the first after a second, then every 5 seconds
interval(5000);           // the first after 5 seconds (nothing immediately!), then every 5
```

The practical difference: `interval(5000)` makes you wait out the first interval, so polling usually uses `timer(0, 5000)` — "now and then every 5 seconds". Neither completes on its own: stopping happens through `take`, `takeUntil` or unsubscribing (see [Transformation and Filtering Operators]).

### EMPTY, NEVER, throwError

Three "degenerate" streams you constantly need in branches:

```ts
import { EMPTY, NEVER, throwError, of } from 'rxjs';

EMPTY;                                  // emits nothing, completes immediately
NEVER;                                  // never emits and never completes
throwError(() => new Error('boom'));    // errors immediately

// the typical use: the "nothing to load" branch
const users$ = query.length < 2 ? EMPTY : api.search(query);
```

Note the shape of `throwError`: in RxJS 7 it takes a **factory**, and passing a ready value is deprecated. The point is not cosmetic: a factory creates the error at the moment it should occur, so the stack trace is meaningful.

`EMPTY` versus `of()`: both complete without values, but `EMPTY` is a shared constant while `of()` builds a new stream. `NEVER` is rare in production code — mostly in tests and as "a stub that does nothing".

### Your own Observable

When you need to wrap an API that has no ready factory, write the constructor directly. The essential part is returning a teardown:

```ts
import { Observable } from 'rxjs';

function fromWebSocket<T>(url: string): Observable<T> {
  return new Observable<T>((subscriber) => {
    const socket = new WebSocket(url);

    socket.onmessage = (event) => subscriber.next(JSON.parse(event.data) as T);
    socket.onerror = () => subscriber.error(new Error(`WebSocket failed: ${url}`));
    socket.onclose = (event) => {
      // a clean close is complete, an abnormal one is error
      if (event.wasClean) subscriber.complete();
      else subscriber.error(new Error(`WebSocket closed: ${event.code}`));
    };

    // teardown: runs on unsubscribe, on complete and on error
    return () => {
      if (socket.readyState === WebSocket.OPEN) socket.close();
    };
  });
}
```

Three rules for custom Observables: honour the contract (`next` many times, then one `error` or `complete`), always return a teardown, and remember the subscriber function runs anew per subscription — so every subscriber gets **its own** WebSocket. If that is not what you want, the stream must be shared — see [Multicasting and Subscription Management].

## Subject: the bridge from imperative code

A `Subject` is both an **Observable and an Observer**: it has `subscribe` as well as `next`/`error`/`complete`. Hence its role: a point where imperative code pushes values in and reactive code reads them out.

```ts
import { Subject } from 'rxjs';

const notifications$ = new Subject<string>();

// the imperative side: any code may call next
notifications$.next('Ticket saved');

// the reactive side: subscribers receive the values
notifications$.subscribe((message) => showToast(message));
```

The key difference from a plain Observable: a Subject is **hot** and multicast. It does not create work per subscription but hands the same values to every subscriber — like an `EventEmitter`, but with operators and a completion contract.

### Four kinds, and what a late subscriber sees

```
                            What a late subscriber sees
                    the source emits 1, 2, 3; subscriber B arrives between 2 and 3

Subject             --1--2--3--
  A from the start  --1--2--3--
  B late            -------3--
                           ^ values 1 and 2 are lost forever

BehaviorSubject(0)  0-1--2--3--
  A from the start  0-1--2--3--
  B late            ------2-3--
                          ^ received the CURRENT value (2) at once, then the stream

ReplaySubject(2)    --1--2--3--
  B late            ------12-3--
                          ^ caught up on a buffer of the last two values

AsyncSubject        --1--2--3--|
  any subscriber    -----------3|
                               ^ only the last value, and only on complete
```

- **`Subject`** — no memory. Subscribe later and the earlier values are gone. Fits events ("the user pressed save") where history is irrelevant.
- **`BehaviorSubject(initial)`** — holds the current value and hands it to a new subscriber immediately. Requires an initial value. This is the workhorse for **state**: state always has a "right now" value, and every new reader must receive it.
- **`ReplaySubject(bufferSize?, windowTime?)`** — a buffer of the last N values (or everything within the last `windowTime` ms). Useful for "recent history"; dangerous with a large buffer, since it holds values in memory.
- **`AsyncSubject`** — emits only the last value, and only on `complete`. Rare in practice; closest in spirit to a promise.

### BehaviorSubject as state: the working pattern

```ts
import { BehaviorSubject, Observable } from 'rxjs';

interface Filters {
  readonly status: string | null;
  readonly query: string;
}

export class TicketFiltersStore {
  // private writes: the Subject never leaves the class
  private readonly state = new BehaviorSubject<Filters>({ status: null, query: '' });

  // public reads: the type is Observable, not Subject — no next() from outside
  readonly filters$: Observable<Filters> = this.state.asObservable();

  // the current value is available synchronously — a plain Subject cannot do this
  get snapshot(): Filters {
    return this.state.getValue();
  }

  setStatus(status: string | null): void {
    this.state.next({ ...this.snapshot, status });
  }

  reset(): void {
    this.state.next({ status: null, query: '' });
  }
}
```

Three details make this pattern correct:

1. **`asObservable()`** narrows the type: the consumer sees `Observable<Filters>` and physically cannot call `next`. Without it any component can write to the state, bypassing the store's methods.
2. **`getValue()`** gives synchronous access to the current value — exactly what a `Subject` lacks and what makes `BehaviorSubject` suitable for state.
3. **Immutable updates** (`{ ...this.snapshot, status }`): subscribers compare references, and mutating the object in place goes unnoticed by operators such as `distinctUntilChanged`.

> **Angular context.** This very pattern — a private `BehaviorSubject` plus a public `Observable` — was the standard way to hold state in services before signals arrived. Today Angular fills that role with a `signal` plus `asReadonly()`, and the two worlds interoperate through `toSignal`/`toObservable`. Details are in the Angular course, in the chapters on signals, state in services and RxJS in Angular.

## When a Subject is not needed

The most common anti-pattern is a Subject where a plain Observable would do.

```ts
// BAD: a Subject repackaging a ready-made stream
export class UserService {
  private readonly users = new Subject<User[]>();
  readonly users$ = this.users.asObservable();

  loadUsers(): void {
    this.http.get<User[]>('/api/users').subscribe((users) => this.users.next(users));
  }
}
```

What is wrong here: a subscription nobody closes; an HTTP error terminates `users` forever (see [Error Handling and Retries]); a late subscriber never sees data that was already loaded; and above all, a stream has been "converted" into imperative code for no benefit.

```ts
// GOOD: the stream stays a stream
export class UserService {
  readonly users$ = this.http.get<User[]>('/api/users');
  // subscription happens where the data is needed;
  // multiple subscriptions are handled with share (see Multicasting)
}
```

Signs that a Subject really **is** needed:

- the source of values is imperative code you do not control (a handler, a library callback, a component method);
- you need multicast: one value, many independent subscribers;
- you need to hold current state and hand it to new readers (`BehaviorSubject`);
- you need a manual trigger: `refresh$ = new Subject<void>()` with `refresh$.pipe(switchMap(() => load()))`.

And the rule worth memorizing: **never expose a Subject**. The public type is always an `Observable` via `asObservable()`. Otherwise encapsulation is gone, and debugging "who exactly called next" turns into a project-wide search.

## Relation to other topics

```txt
[Reactive Model and Observables]  — laziness, the subscription contract and
                                     teardown, which everything here rests on
[Transformation and Filtering
 Operators]                        — how to bound an infinite interval and
                                     what to do with values next
[Combination Operators]            — how to join several created streams
[Error Handling and Retries]       — why an error in a Subject kills it for good
[Multicasting and Subscription
 Management]                        — the Subject behind share/shareReplay
                                     and the difference between hot and cold
```

## Common interview traps

- **Confusing `of(array)` with `from(array)`** — `of([1,2,3])` emits one item (the array itself), `from([1,2,3])` emits three values. A simple knowledge check, but it also exposes a missing grasp of the fact that a stream may carry values of any type, arrays included.

- **"`from(promise)` makes the stream lazy"** — it does not: the promise already started work at creation. Laziness comes back with `defer(() => from(fetch(...)))`. The usual follow-up people stumble on: "what if you subscribe twice to `from(promise)`?" — both subscribers get the same result and no second request is made.

- **`interval(5000)` for "poll every 5 seconds starting now"** — `interval` stays silent through the first interval. You want `timer(0, 5000)`. A small detail that in practice becomes "the data shows up late when the screen opens".

- **Exposing a `Subject` from a public API** — any consumer can then call `next()` or `complete()` on your state. The expected answer: a private Subject plus a public `asObservable()`; in the Angular context, a private `signal` plus a public `asReadonly()`.

- **Not knowing why state wants `BehaviorSubject` over `Subject`** — the key is that state always has a "right now" value: a new subscriber must receive it, and code needs synchronous access via `getValue()`. With a plain `Subject`, a component subscribing after the last `next` sees an empty screen until the next update.

- **`ReplaySubject` with an unbounded buffer** — `new ReplaySubject()` keeps **every** value forever. On an event stream that is a memory leak growing linearly with uptime. A good answer mentions `bufferSize` and `windowTime`.

- **`throwError(new Error(...))` instead of a factory** — the RxJS 6 shape. In version 7 passing a value is deprecated: the expected form is `throwError(() => new Error(...))`, with the explanation that the error is created when it actually occurs, so the stack trace is meaningful.

- **A Subject "repackaging" an HTTP request** — the most common architectural anti-pattern: `subscribe` inside a service plus `next` into a Subject. A good answer names three concrete consequences: an unclosed subscription, the Subject terminating on a request error, and lost data for a late subscriber.
