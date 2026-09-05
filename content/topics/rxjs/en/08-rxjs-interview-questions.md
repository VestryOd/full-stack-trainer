# RxJS — Interview Questions (Middle / Senior)

## How to use this cheat sheet

Every answer below is a condensed version of what the articles in this section cover in depth. In an interview almost none of these questions is the final one. Each one is a **setup for a follow-up**: "why?", "what happens if...?", "show me where this broke for you".

That is why every group ends with a **"Common follow-ups"** section. It shows where the conversation usually goes. If a follow-up leaves you stuck, that is a signal to reread the matching article.

Version note: the answers target **RxJS 7** (the current major version). Where it matters, the deprecated alternatives are called out.

## Group 1: The model and subscriptions

**How does an Observable differ from a Promise?**

Four axes: laziness, number of values, cancellability and synchronicity.

| axis | Promise | Observable |
|---|---|---|
| laziness | starts the work when created | starts it only on subscribe |
| number of values | resolves once | zero, one, many or endless |
| cancellability | cannot be cancelled | `unsubscribe()` aborts the work |
| synchronicity | callback always in a microtask | may deliver a value synchronously |

**Laziness** is the axis interviewers ask about most: no subscriber, no request. **Cancellability** is the second one: a promise result can only be ignored, while `unsubscribe()` also runs the teardown. On the synchronicity axis, `of(1)` delivers its value before the next line of code runs. Details in [Reactive Model and Observables](./01-reactive-model-and-observables.md).

---

**What exactly happens on `unsubscribe()`, and how is it different from `complete`?**

`unsubscribe()` stops value delivery and runs the **teardown logic**. That is the function returned from the Observable constructor: it removes a listener, clears a timer or aborts an HTTP request.

The `complete` callback is **not** invoked. Unsubscribing means "I no longer need this"; completing means "there is no more data". The teardown is the one thing guaranteed to run in both cases. That is why resource cleanup belongs there and not in `complete`.

---

**What happens to a stream after an error?**

It is **terminated**: no `next` and no `complete` will follow, the teardown has run and the subscription is gone.

The most dangerous consequence appears on long-lived sources. Say a chain over a click stream once threw on an HTTP request. The button still looks alive, but the handler is dead forever, and the logs hold one line about it.

That is precisely why errors are handled **inside** the flattening operator. A flattening operator subscribes to an inner stream instead of a value: `switchMap`, `mergeMap`, `concatMap`, `exhaustMap`. See group 6 and [Error Handling and Retries](./06-error-handling-and-retries.md).

---

**How do you turn an Observable into a Promise, and why not `toPromise()`?**

`firstValueFrom(obs$)` returns the first value; `lastValueFrom(obs$)` returns the last one and waits for `complete`.

`toPromise()` is deprecated in RxJS 7 and removed later. The reason is ambiguous semantics: it was unclear what to return for a stream that completed without values. The new functions behave explicitly — they reject with `EmptyError`.

The reverse conversion is `from(promise)`. Note that such a stream is **not lazy**: the promise has already started. Laziness comes back with `defer(() => from(fetch(...)))`.

---

## Common follow-ups (group 1)

- "You subscribed twice to `from(promise)` — how many requests go out?" → one: the promise already ran, both subscribers get the same result.
- "Is an Observable always asynchronous?" → no: `of`, `from(array)` and a synchronous `Subject.next` deliver values immediately.
- "An error is thrown inside `subscribe`'s `next` callback — will `catchError` catch it?" → no. That is an error outside the stream, and it goes to RxJS's global handler.
- "What happens if you call `next` after `complete`?" → the value is ignored: the contract forbids emissions after a terminal event.

## Group 2: Creating streams and Subjects

**What is the difference between `of` and `from`?**

`of(...)` emits its arguments as they are: `of([1,2,3])` emits **one** value, the array itself. By contrast `from(...)` expands anything iterable: `from([1,2,3])` emits **three** values. It also accepts promises, iterables and async iterables, which makes it the universal bridge from existing structures. Details in [Creating Streams and Subjects](./02-creating-streams-and-subjects.md).

---

**What is `defer` for, and which problem does it solve?**

`defer(factory)` postpones source creation until subscribe time, which restores laziness to code that lost it. Two canonical cases:

- **Wrapping a promise.** `defer(() => from(fetch(url)))` makes a new request per subscription, while `from(fetch(url))` does not.
- **A value that depends on state at subscribe time.** `of(Date.now())` computes the time once, when the stream is created. With `defer(() => of(Date.now()))` the clock is read on every subscription.

---

**How do `Subject`, `BehaviorSubject`, `ReplaySubject` and `AsyncSubject` differ?**

The difference is what a **late subscriber** receives.

| Subject type | what a late subscriber gets |
|---|---|
| `Subject` | nothing from the past, only new values |
| `BehaviorSubject(initial)` | the current value immediately |
| `ReplaySubject(bufferSize, windowTime)` | the last N values from the buffer |
| `AsyncSubject` | only the last value, and only on `complete` |

`BehaviorSubject` requires an initial value and adds synchronous access through `getValue()`, which makes it the default tool for state. `ReplaySubject` without a bounded buffer is a memory leak. The API rule for all four: expose `asObservable()` so consumers cannot call `next`.

---

## Common follow-ups (group 2)

- "Why is exposing a `Subject` bad?" → any consumer can call `next()`/`complete()` on your state; encapsulation is gone and the source of changes becomes untraceable.
- "When is a Subject unnecessary?" → when it merely repackages a ready stream. The line `http.get().subscribe(v => subject.next(v))` gives an unclosed subscription, termination on request error, and lost data for late subscribers.
- "`interval(5000)` — when does the first value arrive?" → after 5 seconds; for "now and then every 5" use `timer(0, 5000)`.
- "How do you build a stream from a WebSocket?" → `new Observable` with a mandatory teardown that closes the socket. Remember that every subscriber gets its own socket unless you add `share`.

## Group 3: Operators and time

**How does `scan` differ from `reduce`?**

`scan` emits the intermediate result after **every** value; `reduce` emits only the total, and only on `complete`.

The practical consequence shows on an infinite stream such as `interval` or a stream of events. There `reduce` never emits anything at all. Meanwhile `scan` is the primary tool for accumulating state: counters, growing lists, a reducer over a stream of actions. See [Transformation and Filtering Operators](./03-transformation-and-filtering-operators.md).

---

**`debounceTime`, `throttleTime`, `auditTime` — which and when?**

All three reduce the rate, but each one yields a different value from a burst.

```
      debounceTime, throttleTime, auditTime on one burst
source           -a-b-c---------d-e------|
debounceTime(4)  ---------c-----------e--|
                          ^ the pause ended: last of the burst
throttleTime(4)  -a---c---------d--------|
                  ^ first value at once, then silence
auditTime(4)     -----c-------------e----|
                      ^ window ended: last value inside it
    a dash is one unit of time; the window here is 4 units
```

- `debounceTime` waits for a pause and emits the **last** value. That is search-as-you-type.
- `throttleTime` emits the **first** value immediately, then stays silent for the window. That is scroll, button protection, analytics.
- `auditTime` waits for the window to end after the first value. It then emits the **last** value from that window: "no more often, but always current".

The criterion: does the reaction need to be immediate, and which value from the series matters?

---

**Why does `distinctUntilChanged()` "not work" for objects?**

It compares by reference (`===`), and every API response is a new object even when the content is identical. Three fixes:

- Pass a comparator: `distinctUntilChanged((a, b) => a.id === b.id)`.
- Use `distinctUntilKeyChanged('id')`.
- Narrow the stream to a primitive with `map` first, and compare that.

The third one is usually preferable: comparing primitives is cheap, and there is no comparator to maintain.

---

**What is wrong with putting logic inside `tap`?**

`tap` is for side effects that do not affect the data: logging, metrics, integration with imperative APIs. Once state assignments move into it (`tap(v => this.items = v)`), the chain's outcome lives in its effects rather than in its value. Three things break at once:

- The chain cannot be reused.
- Effects run twice on a second subscription.
- The result depends on where `tap` sits among the operators.

The test: remove every `tap`. If the chain stops working, `tap` was misused. The positional form (`tap(next, error, complete)`) is deprecated in RxJS 7. An observer object is expected instead, and it also exposes `subscribe`, `unsubscribe` and `finalize`.

---

## Common follow-ups (group 3)

- "The user types nonstop for a minute — what does `debounceTime(300)` deliver?" → nothing: the required pause never happened.
- "`take(1)` or `first()`?" → on an empty stream `take(1)` completes quietly while `first()` throws `EmptyError`. The choice depends on whether "no value" counts as an error.
- "Does `take(n)` complete the stream?" → yes. After the n-th value `complete` arrives and the subscription is torn down, which is why `take(1)` removes the need to unsubscribe.
- "How do you write a custom operator?" → as a function returning `pipe(...)` of existing operators; no class and no internals required.
- "`pluck('a','b')` — why avoid it?" → deprecated in RxJS 7; the replacement `map(x => x?.a?.b)` types more precisely.

## Group 4: Flattening streams

**`switchMap`, `mergeMap`, `concatMap`, `exhaustMap` — what is the difference and how do you choose?**

All four subscribe to an inner stream, but each one treats the previous work differently.

| operator | the previous work | typical use |
|---|---|---|
| `switchMap` | **cancelled** | search, autocomplete, filter change, loading by `:id` |
| `mergeMap` | runs **in parallel**, order not guaranteed | independent loads, telemetry |
| `concatMap` | **queued**, order preserved | sequential writes |
| `exhaustMap` | new values **ignored** while it runs | double-click protection |

`mergeMap` also takes a concurrency limit as its second argument. Choose between the four with three questions, in order:

1. Do I need the result of the previous operation?
2. Does the order of results matter?
3. Should new values be accepted at all while the current operation runs?

Full treatment with marble diagrams in [Flattening Operators](./04-flattening-operators.md).

---

**Why is `switchMap` dangerous for write operations?**

Because cancelling on the client does not cancel processing on the server. A `PATCH` aborted by `switchMap` may have arrived and applied fully, partially, or not at all. The result is non-deterministic state that only reproduces when the user acts quickly. For writes use `concatMap` (run all in order) or `exhaustMap` (drop repeated presses).

---

**What is wrong with a subscription inside a subscription?**

Four concrete consequences:

- Nobody closes the inner subscriptions, and they pile up.
- Previous requests are not cancelled, so a response for a stale parameter may land on screen.
- The error cannot be handled in one place.
- The outer `unsubscribe` does not stop the inner ones.

The flat replacement is a flattening operator. Sometimes you need the outer value along with the inner result. Then build an object inside the chain: `switchMap(id => load(id).pipe(map(data => ({ id, data }))))`.

---

**Why does `mergeMap` take a second argument?**

It is the concurrency limit. Without it, a stream of a thousand values opens a thousand simultaneous requests. Then the server refuses, or the browser hits its connection cap. With `mergeMap(fn, 4)` at most four inner streams stay active. And `mergeMap(fn, 1)` is equivalent to `concatMap`.

---

## Common follow-ups (group 4)

- "The user toggled a filter twice, and the screen shows the previous filter's data. Where is the bug?" → `mergeMap` instead of `switchMap`: the slow first response arrived last.
- "How is 'cancelled' different from 'ignored'?" → `switchMap` aborts work already started, and a cancelled request is visible in Network. Meanwhile `exhaustMap` never starts the work at all, so there is no request.
- "Is `concatMap` just a safe `mergeMap`?" → no, it serializes the work. A slow operation delays the whole queue, and a fast source makes the queue grow.
- "How do you load three independent resources after a route change?" → `switchMap` on the outside (to cancel stale work) plus `forkJoin` inside (parallel, one result).

## Group 5: Combining streams

**Why does `combineLatest` sometimes emit nothing at all?**

Because it emits nothing until **every** source has emitted at least once.

In practice that shows up as an empty screen. Two filters have already produced values, while a third stream stays silent — a `Subject` with no initial value, or a form's `valueChanges`. The view model for the screen is never built.

Fixes: `startWith` on the silent sources, a `BehaviorSubject` instead of a `Subject`, or an explicit initial value. See [Combination Operators](./05-combination-operators.md).

---

**`combineLatest` or `withLatestFrom` — how do you choose?**

The question is: **what should cause a recomputation?**

- If any of the values should — `combineLatest`. Linked filters are the case: changing any one of them reloads the list.
- If only one should, with the rest providing context — `withLatestFrom`. A click on "save" plus the form's current state: saving must happen on the click, not on every keystroke.

`withLatestFrom` also has a trap: a leading value that arrives before the follower's first value is lost silently.

---

**How does `forkJoin` differ from `combineLatest`, and why does it "stay silent"?**

`forkJoin` is the `Promise.all` analogue: it emits **once**, the last value of every source, and only after each has completed.

```
      combineLatest emits on every change, forkJoin once
a$             --1---4--|
b$             ----2----|
combineLatest  ----x-y--|
                   ^ both have emitted: (1, 2)
                     ^ a$ changed: (4, 2)
forkJoin       ---------z|
                        ^ both completed: (4, 2), one emission
   forkJoin stays silent while any source has not completed
```

`combineLatest` emits on every change, so a chain of requests can deliver intermediate results instead of one final one. When `forkJoin` stays silent, it almost always means one of the sources never completes: `interval`, a `Subject`, `fromEvent`.

Two more properties. An error in any source terminates the whole result, so a partial result requires `catchError` inside each source. And a source that completes without values makes the whole thing complete without emitting.

---

## Common follow-ups (group 5)

- "Three filters change programmatically one after another — how many requests with `combineLatest` + `switchMap`?" → three; `debounceTime(0)` collapses a synchronous burst.
- "Should I use `zip` instead of `forkJoin`?" → almost never. It pairs values by index and buffers whichever source runs ahead, so sources of different speed make memory grow.
- "`concat(interval(1000), api.load())` — when does the request fire?" → never: `concat` subscribes to the second source only after the first completes.
- "How do you build a timeout by combining streams?" → `race` with `timer`, though the dedicated `timeout({ first })` is the better answer.

## Group 6: Errors and retries

**Where do you put `catchError` — before or after a flattening operator, and why does it change the behaviour?**

An error terminates **the stream it occurred in**.

With `catchError` **outside** — `switchMap(...)` and then `catchError(...)` — the request error becomes an error of the outer stream. The click stream or `route.params` then dies forever, and the handler never runs again.

With `catchError` **inside** — `switchMap(id => load(id).pipe(catchError(...)))` — the error turns into a value before it reaches the outer stream. Only that one request fails. The rule: long-lived source → `catchError` inside; one-shot request → outside is acceptable.

---

**How do you configure `retry` properly, and what should not be retried?**

Three mandatory elements:

- **A limit.** `retry()` without `count` repeats forever.
- **A delay, preferably growing.** For example `delay: (err, n) => timer(500 * 2 ** (n - 1))`. Instant repeats overload a service that is already failing, and they earn a rate-limit ban.
- **A filter by error type.** Retry `5xx`, timeouts and `status === 0`. Retrying `401` or `422` is pointless, because the result will not change.

For long-lived streams `resetOnSuccess: true` is useful: it clears the counter after each successful value. In RxJS 7 `retryWhen` is deprecated, and the replacement is `retry({ delay })`.

---

**How is `finalize` different from handling things in `subscribe`?**

`finalize` runs on **any** ending: `complete`, `error` and `unsubscribe`. Handling it in `subscribe` means duplicating code across `next`, `error` and `complete`. And it still misses the unsubscribe case: leaving the screen mid-load, for example. That is why "hide the spinner" and "release the resource" live in `finalize`.

Next to it sits `timeout({ first, each })`. It turns the silence of a hung request into a `TimeoutError`, which then flows through ordinary error handling. See [Error Handling and Retries](./06-error-handling-and-retries.md).

---

## Common follow-ups (group 6)

- "`catchError` returned `EMPTY` — what does the subscriber see?" → the stream completes with no values and no error. That is handy for "silently do nothing", but it hides the problem from the caller.
- "What does `catchError` return if you return nothing?" → a type error: the operator must return an Observable for the stream to continue with.
- "Why does `timeout` go before `retry`?" → otherwise the timeout applies to all attempts combined rather than to each one.
- "How do you get a partial result from `forkJoin`?" → a `catchError` inside each source, turning a failure into a default value.

## Group 7: Multicasting and subscriptions

**Why did the same Observable make three HTTP requests?**

Because it is **cold**: the subscriber function runs once per subscription. Three `| async` pipes in a template are three independent subscriptions, hence three requests.

Diagnosis: count the requests in the Network tab, or add `tap({ subscribe: () => console.count('sub') })`. The fix is `shareReplay({ bufferSize: 1, refCount: true })`, or a single subscription with an `as` variable in the template. See [Multicasting and Subscription Management](./07-multicasting-and-subscription-management.md).

---

**How can `shareReplay` leak?**

By default `shareReplay(1)` uses `refCount: false`. The source is **not unsubscribed** when the subscriber count drops to zero, and the inner `ReplaySubject` keeps running indefinitely.

```
          shareReplay(1): refCount false versus true
source           -0-1-2-3-4-5-6-7-8-
subscriber       -0-1-2-U
                        ^ screen closes, subscribers drop to 0
refCount: false  -0-1-2-3-4-5-6-7-8-
                          ^ the timer keeps ticking: a leak
refCount: true   -0-1-2-|
                        ^ source unsubscribed, timer stops
 U marks unsubscribe; the source here is an endless interval
```

Over an `interval`, a WebSocket or an event subscription that is a leak: the timer keeps ticking after the screen closes. The fix is `shareReplay({ bufferSize: 1, refCount: true })`.

For a completed HTTP request, however, `refCount: false` is not a leak but the desired behaviour: the value is cached for the application's lifetime. Also remember `resetOnError`. Without it the next subscriber may receive the cached error instead of a fresh attempt.

---

**Why must `takeUntil` be last in the `pipe()`?**

Because it only completes the part of the chain **before** it. If a `switchMap` follows `takeUntil`, its inner subscriptions keep living after the destroy signal — the leak remains even though "there is an unsubscribe". This is one of the rare cases where operator order affects resource release rather than the result.

---

**How do you detect a subscription leak?**

Two signs, and either one is enough:

- Work continues after the screen closes: requests in Network, ticks in the console.
- A handler fires several times for one action, because every screen visit adds a live subscription.

The check: log the lifecycle with `tap({ subscribe, unsubscribe, complete })` plus `finalize`. If there are many more `SUB` lines than `UNSUB` lines, the leak is found. The second method is a heap snapshot taken before and after opening a screen repeatedly. A growing count of `Subscriber` objects or components points at retained subscriptions.

Three questions to localize it:

1. Does the source complete on its own?
2. Is there a `shareReplay` without `refCount` over an infinite source?
3. Is `takeUntil` last?

---

## Common follow-ups (group 7)

- "How do you tell cold from hot?" → by the source. Does it exist independently of the subscriber? `fromEvent` and a `Subject` do; `http.get`, `defer` and `interval` do not.
- "`share()` or `shareReplay()`?" → `share` when a late subscriber should not see the past; `shareReplay` when it should receive the latest values.
- "Where should `subscribe` actually be called?" → as close to the application's edge as possible. Services return streams, the consumer subscribes, and in templates the subscription is handed to the framework (`async` pipe, `toSignal`).
- "`publish().refCount()` in old code — what do you do with it?" → that family is deprecated in RxJS 7 and removed in v8. It covers `multicast`, `publish`, `publishReplay` and `refCount`. The replacement is `share` or `shareReplay`, and `connectable()` for manual connection.

## The classic "wrap-up" senior question

**Design a live search: user input, an API request, rendered results. What do you account for?**

The expected answer walks through every topic in this section:

```ts
const results$ = searchInput$.pipe(
  map((q) => q.trim()),
  debounceTime(300),                 // not a request per keystroke
  distinctUntilChanged(),            // do not search the same thing twice
  filter((q) => q.length === 0 || q.length >= 2), // do not search on one letter
  switchMap((q) =>
    q.length === 0
      ? of([] as Ticket[])           // empty input, empty result, no request
      : api.search(q).pipe(
          timeout({ first: 8000 }),  // a hung request becomes an error
          retry({ count: 2, delay: (_, n) => timer(300 * n) }),
          catchError(() => of([])),  // inside: keeps the input stream alive
        ),
  ),
  shareReplay({ bufferSize: 1, refCount: true }), // when there are several subscribers
);
```

What the interviewer is actually checking:

- The choice of `switchMap` rather than `mergeMap`, with the race-and-cancellation rationale.
- `debounceTime` plus `distinctUntilChanged` as a pair.
- `catchError` placed **inside** `switchMap`.
- No subscription inside the service.
- An understanding of why `shareReplay` is there, and why with `refCount: true`.

A strong candidate adds one more thing. Loading state is better expressed as its own stream, or through `tap` and `finalize`, than as a third field on the component.

## Common interview traps

- **Describing an Observable as "a Promise with several values"** — that is one axis out of four. It usually comes together with a poor understanding of laziness, and laziness is where both repeated requests and working cancellation come from.

- **Knowing the operators but having no selection criterion** — "switchMap cancels the previous one" is a memorized definition on its own. The follow-up is "when is that right, and when is it dangerous?". What is expected is the chain "scenario → operator → cost of getting it wrong".

- **Not connecting symptom to cause** — senior level shows in the jump from symptom to operator. "Sometimes the previous filter's data is displayed" means `mergeMap` where `switchMap` was needed. "The timer keeps ticking after the screen closed" means `shareReplay` without `refCount`.

- **Recipes from 2018 articles** — `toPromise()`, `retryWhen`, `publish().refCount()`, `pluck`, `tap(next, error, complete)`, the operator forms of `combineLatest`/`merge`/`zip` inside `pipe()`. All of these are deprecated in RxJS 7; knowing the current replacements shows you work with the current version.

- **Ignoring subscription management** — "I use the `async` pipe, it handles everything" is an incomplete answer. The interviewer will ask about the cases where the subscription is manual. There the expected answer is `takeUntil` or `takeUntilDestroyed`, with an understanding of why `takeUntil` goes last.

- **"RxJS everywhere"** — senior interviews value the opposite. Saying where a stream is redundant is a strength: one value, no cancellation, nothing to combine. It also helps to say where `async`/`await` or signals read better.
