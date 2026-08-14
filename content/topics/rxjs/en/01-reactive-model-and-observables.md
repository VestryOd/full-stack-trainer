# Reactive Model and Observables

## A stream of values over time as the primary abstraction

Ordinary data structures describe values available *now*: an array is all its elements at once, a promise is one value that will arrive later. RxJS introduces a different abstraction: a **stream** — a sequence of values spread over time that you can manipulate as a whole.

The practical payoff is that events which used to need different mechanisms get one interface:

```ts
import { fromEvent, interval } from 'rxjs';

const clicks$ = fromEvent<PointerEvent>(document, 'click'); // many values, forever
const ticks$ = interval(1000);                              // values on a timer
const response$ = ajax.getJSON<User[]>('/api/users');       // one value, then complete
```

All three are `Observable`s, and the same operators apply to any of them: filter, delay, combine with another stream, cancel. That unification — not "a replacement for promises" — is the main reason RxJS exists. As soon as a task is phrased as "when A happens, but no more than once per second, and only if B has already produced a value, and the previous request must be cancelled", imperative code turns into a pile of flags and timers while a stream describes it declaratively.

A naming convention: stream variables carry a `$` suffix (`clicks$`, `user$`). Not a language requirement, but it saves reading time — you can see at a glance that the value must be subscribed to rather than used directly.

## Observable versus Promise: four axes

```
                                Observable versus Promise: four axes
┌──────────────────┬──────────────────────────────────────────┬───────────────────────────────────┐
│ axis             │ Promise                                  │ Observable                        │
├──────────────────┼──────────────────────────────────────────┼───────────────────────────────────┤
│ when work starts │ immediately on creation (eager)          │ on subscribe (lazy)               │
├──────────────────┼──────────────────────────────────────────┼───────────────────────────────────┤
│ how many values  │ exactly one                              │ zero, one, many, infinite         │
├──────────────────┼──────────────────────────────────────────┼───────────────────────────────────┤
│ cancellation     │ none: then is simply not called          │ unsubscribe aborts the work       │
├──────────────────┼──────────────────────────────────────────┼───────────────────────────────────┤
│ synchronicity    │ the callback always lands in a microtask │ may deliver a value synchronously │
└──────────────────┴──────────────────────────────────────────┴───────────────────────────────────┘
           the consequence of laziness: with no subscriber there is no request, no timer,
               no event listener — a stream describes work rather than performing it
```

### 1. Laziness

A promise starts work the moment it is created — the constructor runs immediately:

```ts
const promise = fetch('/api/users'); // the request has ALREADY gone out
// even without .then(), the server received it
```

An Observable is a *description* of work. The subscriber function runs on every subscription:

```ts
import { Observable } from 'rxjs';

const users$ = new Observable<User[]>((subscriber) => {
  console.log('request sent');          // does not run until the first subscribe
  fetch('/api/users')
    .then((r) => r.json())
    .then((users) => {
      subscriber.next(users);
      subscriber.complete();
    })
    .catch((err) => subscriber.error(err));
});

// nothing has happened here: not a single request
users$.subscribe();                     // "request sent" — the first request
users$.subscribe();                     // "request sent" — a SECOND request
```

Two subscriptions mean two independent pieces of work. That is not a bug but a direct consequence of laziness, and simultaneously the source of the classic "why do I get two HTTP requests instead of one" — the mechanics and the fix are covered in [Multicasting and Subscription Management].

### 2. Number of values

A promise resolves once by contract: `resolve(a); resolve(b)` — the second call is ignored. An Observable may call `next` any number of times, including never completing:

```ts
import { of, interval, EMPTY } from 'rxjs';

of(1, 2, 3);      // three values, then complete
interval(1000);   // an infinite stream: 0, 1, 2, ... with no complete
EMPTY;            // zero values, completes immediately
```

The practical consequence: code working with a stream must answer "what if there are many values" — a question that never arises with a promise.

### 3. Cancellability

A promise cannot be cancelled: you may ignore the result, but the work continues (the request reaches the server, the timer fires). Cancellation in promise-land exists only through an external mechanism — `AbortController` — which you must thread through by hand.

For an Observable, cancellation is built into the model: `unsubscribe()` does more than detach callbacks, it runs the **teardown logic** — the code that releases resources:

```ts
import { Observable } from 'rxjs';

const timer$ = new Observable<number>((subscriber) => {
  let count = 0;
  const id = setInterval(() => subscriber.next(count++), 1000);

  // teardown: runs on unsubscribe, on complete and on error
  return () => {
    clearInterval(id);
    console.log('timer cleared');
  };
});

const sub = timer$.subscribe(console.log);
setTimeout(() => sub.unsubscribe(), 3500); // "timer cleared", interval stopped
```

The same principle applies to the network: Angular's `HttpClient` aborts the request on unsubscribe (through an `AbortController` under the hood), and the `switchMap` operator uses that to cancel outdated requests automatically — the central story of [Flattening Operators].

### 4. Synchronicity

A promise is always asynchronous: even `Promise.resolve(1).then(fn)` calls `fn` in a microtask, i.e. after the current synchronous code. An Observable has no such requirement:

```ts
import { of } from 'rxjs';

console.log('before');
of(1, 2).subscribe((v) => console.log('value', v)); // synchronously!
console.log('after');

// output: before → value 1 → value 2 → after
```

That property is useful (no artificial delay for data you already have) and dangerous at the same time: code that is "sometimes synchronous, sometimes not" leads to subtle ordering differences. The rule: do not rely on a particular stream being synchronous unless its construction guarantees it.

## Anatomy of a subscription

Subscribing means handing the stream an **observer**: an object with `next`, `error` and `complete`. The contract is strict: `next` may be called many times, then exactly one of `error` or `complete` — and after that the stream is dead.

```
     The subscription contract: next* (error | complete)?
success      --1--2--3--|
                        ^ complete: no more values ever,
                          teardown has run
error        --1--2--X
                     ^ error: the stream is TERMINATED,
                       neither next nor complete will follow
unsubscribe  --1--2--!
                     ^ unsubscribe: work aborted,
                       and this is neither error nor complete
legend:  1 2 3 — values,  | — complete,  X — error,  ! — unsubscribe
```

```ts
const sub = source$.subscribe({
  next: (value) => console.log('value', value),
  error: (err) => console.error('error', err),    // called at most once
  complete: () => console.log('completed'),        // called at most once
});

sub.unsubscribe(); // stops receiving values and runs the teardown
```

What matters here:

- **`error` terminates the stream.** This is the most common place where subscriptions to user events break: once an error travels through the chain, the click stream no longer works and the button "stopped responding". Handling strategies are in [Error Handling and Retries].
- **`complete` and `error` are mutually exclusive**, and both run the teardown automatically: there is no need to unsubscribe afterwards.
- **`unsubscribe` is not the same as `complete`.** Unsubscribing means "I am no longer interested", not "the data ran out": the `complete` callback is not invoked.
- **`Subscription` composes**: `sub.add(otherSub)` ties one subscription's lifetime to another, and `unsubscribe()` on the parent closes the whole tree. In components that is the historical way to manage subscriptions — today `takeUntil`/`takeUntilDestroyed` is preferable, see [Multicasting and Subscription Management].

## When a Promise is honestly better

RxJS is not a universal replacement for promises. A promise (with `async`/`await`) wins when the task is one-shot by nature:

```ts
// One value, no cancellation needed, no composition over time
async function loadConfig(): Promise<AppConfig> {
  const response = await fetch('/api/config');
  if (!response.ok) throw new Error(`Config load failed: ${response.status}`);
  return response.json();
}
```

Signs that an Observable would be overkill: exactly one value, no cancellation, no combination with other sources, and a linear sequence of steps that reads better through `await` than through a chain of operators. Forcing a stream onto such code makes it more complex for no gain.

The bridge between the models works both ways:

```ts
import { from, firstValueFrom, lastValueFrom } from 'rxjs';

const stream$ = from(fetch('/api/users'));    // Promise → Observable
const users = await firstValueFrom(users$);   // Observable → Promise (first value)
const total = await lastValueFrom(count$);    // Observable → Promise (last value)
```

One important detail about `from(promise)`: the promise has already started work, so this Observable is **not lazy** — it merely wraps the result. To restore laziness you need `defer(() => from(fetch(...)))`, a technique covered in [Creating Streams and Subjects].

A separate note on `toPromise()`: it is deprecated in RxJS 7 and removed in later versions. The reason is ambiguous semantics (what should it return for a stream with no values?). The replacement is `firstValueFrom`/`lastValueFrom`, with an explicit choice and defined behaviour for empty streams (they reject with `EmptyError`).

## Relation to other topics

```txt
[Creating Streams and Subjects]   — where streams come from: of/from/fromEvent,
                                     defer and laziness, Subject as the bridge
                                     from imperative code
[Transformation and Filtering
 Operators]                        — what happens to a stream next and why
                                     .pipe() is composition
[Flattening Operators]             — cancellation in action: switchMap and family
[Error Handling and Retries]       — what to do about error terminating a stream
[Multicasting and Subscription
 Management]                        — why laziness gives you N requests instead
                                     of one, and how to control it
```

## Common interview traps

- **"An Observable is a Promise that can return many values"** — that describes one axis out of four, and it usually comes with a missing grasp of laziness. Laziness matters more than multiplicity: it is what produces repeated requests on multiple subscriptions, what makes cancellation work, and what lets you describe a stream ahead of time without starting any work.

- **"An Observable is always asynchronous"** — no: `of(1)` and `from([1, 2])` deliver values synchronously, at subscribe time. The practical consequence: code assuming "the subscription will run later" may receive a value before the next line executes.

- **Conflating `unsubscribe` and `complete`** — unsubscribing means "I no longer need this", completing means "there is no more data". The `complete` callback does not fire on unsubscribe, which breaks logic like "close the modal in complete". A common probing question: "does the teardown run on unsubscribe?" — yes, it does, and that is the one thing guaranteed to happen in both cases.

- **Not knowing that `error` terminates the stream** — the most expensive mistake by consequence. A click stream whose chain once threw on an HTTP request is dead forever: the button still looks alive, but the handler never runs again. That is precisely why `catchError` goes *inside* a flattening operator rather than at the end of the chain — see [Error Handling and Retries].

- **Answering with `toPromise()`** — a marker of RxJS 6-era knowledge. It is deprecated in RxJS 7; the expected answer is `firstValueFrom`/`lastValueFrom`, ideally with the awareness that they reject with `EmptyError` when the stream completes without a value.

- **"RxJS is always better than async/await"** — senior interviews value the opposite: naming the cases where a stream is redundant (one value, no cancellation, no combining) and where `await` reads better. Answering "I use RxJS everywhere because this is Angular" shows the absence of a selection criterion.
