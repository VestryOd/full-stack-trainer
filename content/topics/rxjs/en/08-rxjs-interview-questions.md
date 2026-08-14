# RxJS — Interview Questions (Middle / Senior)

## How to use this cheat sheet

Every answer below is a condensed version of what the articles in this section cover in depth. In an interview almost none of these questions is the final one — each is a **setup for a follow-up**: "why?", "what happens if...?", "show me where this broke for you". That is why every group is followed by a **"Common follow-ups"** section showing where the conversation usually goes. If a follow-up stumps you, that is a signal to revisit the corresponding article.

Version note: the answers target **RxJS 7** (the current major). Where it matters, the deprecated alternatives are called out.

## Group 1: The model and subscriptions

**How does an Observable differ from a Promise?**

Four axes. **Laziness**: a promise starts work at creation, an Observable only on subscribe (no subscriber, no request). **Number of values**: a promise resolves once, an Observable may emit zero, one, many or infinitely many values. **Cancellability**: a promise cannot be cancelled (only its result ignored), while `unsubscribe()` aborts the work and runs the teardown. **Synchronicity**: a promise callback always lands in a microtask, an Observable may deliver a value synchronously (`of(1)` delivers before the next line runs). Details in [Reactive Model and Observables].

---

**What exactly happens on `unsubscribe()`, and how is it different from `complete`?**

`unsubscribe()` stops value delivery and runs the **teardown logic** — the function returned from the Observable constructor (remove a listener, clear a timer, abort an HTTP request). The `complete` callback is **not** invoked: unsubscribing means "I no longer need this", completing means "there is no more data". The teardown is the one thing guaranteed to run in both cases, which is why resource cleanup belongs there rather than in `complete`.

---

**What happens to a stream after an error?**

It is **terminated**: no `next` and no `complete` will follow, the teardown has run and the subscription is gone. The most dangerous practical consequence appears on long-lived sources: if a chain over a click stream once threw on an HTTP request, the button still looks alive but the handler is dead forever, with a single line in the logs. That is precisely why errors are handled **inside** the flattening operator (see group 6 and [Error Handling and Retries]).

---

**How do you turn an Observable into a Promise, and why not `toPromise()`?**

`firstValueFrom(obs$)` for the first value, `lastValueFrom(obs$)` for the last (it waits for `complete`). `toPromise()` is deprecated in RxJS 7 and removed later because of ambiguous semantics: it was unclear what to return for a stream that completed without values. The new functions behave explicitly — they reject with `EmptyError`. The reverse conversion is `from(promise)`, but note that such a stream is **not lazy**: the promise has already started; laziness comes back with `defer(() => from(fetch(...)))`.

---

## Common follow-ups (group 1)

- "You subscribed twice to `from(promise)` — how many requests go out?" → one: the promise already ran, both subscribers get the same result.
- "Is an Observable always asynchronous?" → no: `of`, `from(array)` and a synchronous `Subject.next` deliver values immediately.
- "An error is thrown inside `subscribe`'s `next` callback — will `catchError` catch it?" → no, that is an error outside the stream; it goes to RxJS's global handler.
- "What happens if you call `next` after `complete`?" → the value is ignored: the contract forbids emissions after a terminal event.

## Group 2: Creating streams and Subjects

**What is the difference between `of` and `from`?**

`of(...)` emits its arguments as they are: `of([1,2,3])` emits **one** array value. `from(...)` unrolls anything iterable: `from([1,2,3])` emits **three** values. `from` also handles promises, iterables and async iterables, which makes it the universal bridge from existing structures. Details in [Creating Streams and Subjects].

---

**What is `defer` for, and which problem does it solve?**

`defer(factory)` postpones source creation until subscribe time, restoring laziness to code that lost it. Two canonical cases: wrapping a promise (`defer(() => from(fetch(url)))` makes a new request per subscription, while `from(fetch(url))` does not), and a value that depends on state at subscribe time (`defer(() => of(Date.now()))` versus `of(Date.now())`, where the time is computed once when the stream is created).

---

**How do `Subject`, `BehaviorSubject`, `ReplaySubject` and `AsyncSubject` differ?**

The difference is what a **late subscriber** receives. `Subject` — nothing from the past, only new values. `BehaviorSubject(initial)` — the current value immediately (and it requires an initial one), plus synchronous access through `getValue()` — which makes it the workhorse for state. `ReplaySubject(bufferSize, windowTime)` — a buffer of the last N values; without a bound that buffer is a memory leak. `AsyncSubject` — only the last value, and only on `complete`. The API rule: expose `asObservable()` so consumers cannot call `next`.

---

## Common follow-ups (group 2)

- "Why is exposing a `Subject` bad?" → any consumer can call `next()`/`complete()` on your state; encapsulation is gone and the source of changes becomes untraceable.
- "When is a Subject unnecessary?" → when it merely repackages a ready stream: `http.get().subscribe(v => subject.next(v))` gives an unclosed subscription, termination on request error, and lost data for late subscribers.
- "`interval(5000)` — when does the first value arrive?" → after 5 seconds; for "now and then every 5" use `timer(0, 5000)`.
- "How do you build a stream from a WebSocket?" → `new Observable` with a mandatory teardown that closes the socket — and remember every subscriber gets its own socket unless you add `share`.

## Group 3: Operators and time

**How does `scan` differ from `reduce`?**

`scan` emits the intermediate result after **every** value, `reduce` only the total and only on `complete`. The practical consequence: on an infinite stream (`interval`, events) `reduce` never emits anything, while `scan` is the primary tool for accumulating state (counters, growing lists, a reducer over a stream of actions). See [Transformation and Filtering Operators].

---

**`debounceTime`, `throttleTime`, `auditTime` — which and when?**

All three reduce the rate but yield a different value from a burst. `debounceTime` waits for a pause and emits the **last** value — that is search-as-you-type. `throttleTime` emits the **first** value immediately and then stays silent for the window — that is scroll, button protection, analytics. `auditTime` waits out the window after the first value and emits the **last** one from it — "no more often, but always current". The criterion: does the reaction need to be immediate, and which value from the series matters?

---

**Why does `distinctUntilChanged()` "not work" for objects?**

It compares by reference (`===`), and every API response is a new object even when the content is identical. Three fixes: pass a comparator (`distinctUntilChanged((a, b) => a.id === b.id)`), use `distinctUntilKeyChanged('id')`, or narrow the stream to a primitive with `map` first and compare that. The third is usually preferable: comparing primitives is cheap and needs no comparator to maintain.

---

**What is wrong with putting logic inside `tap`?**

`tap` is for side effects that do not affect the data: logging, metrics, integration with imperative APIs. Once state assignments move into it (`tap(v => this.items = v)`), the chain's outcome lives in effects rather than in its value: the chain cannot be reused, effects double on a second subscription, and ordering depends on operator order. The test: remove every `tap` — if the chain stops working, `tap` was misused. The positional form (`tap(next, error, complete)`) is deprecated in RxJS 7 — an observer object is expected, and it also exposes `subscribe`, `unsubscribe` and `finalize`.

---

## Common follow-ups (group 3)

- "The user types nonstop for a minute — what does `debounceTime(300)` deliver?" → nothing: the required pause never happened.
- "`take(1)` or `first()`?" → on an empty stream `take(1)` completes quietly while `first()` throws `EmptyError`; the choice depends on whether "no value" is an error.
- "Does `take(n)` complete the stream?" → yes, after the n-th value `complete` arrives and the subscription is torn down — which is why `take(1)` removes the need to unsubscribe.
- "How do you write a custom operator?" → as a function returning `pipe(...)` of existing operators; no class and no internals required.
- "`pluck('a','b')` — why avoid it?" → deprecated in RxJS 7; the replacement `map(x => x?.a?.b)` types more precisely.

## Group 4: Flattening streams

**`switchMap`, `mergeMap`, `concatMap`, `exhaustMap` — what is the difference and how do you choose?**

All four subscribe to an inner stream but treat the previous work differently. `switchMap` **cancels** it (search, autocomplete, filter change, loading by `:id`). `mergeMap` runs it **in parallel** with no ordering guarantee (independent loads, telemetry); it takes a concurrency limit as a second argument. `concatMap` **queues** it, preserving order (sequential writes). `exhaustMap` **ignores** new values while the current operation runs (double-click protection). The selection algorithm: do I need the previous result → does order matter → should new values be accepted at all during the current one. Full treatment with marble diagrams in [Flattening Operators].

---

**Why is `switchMap` dangerous for write operations?**

Because cancelling on the client does not cancel server-side processing: a `PATCH` aborted by `switchMap` may have arrived and applied fully, partially, or not at all. The result is non-deterministic state that only reproduces when the user acts quickly. For writes use `concatMap` (run all in order) or `exhaustMap` (drop repeated presses).

---

**What is wrong with a subscription inside a subscription?**

Four concrete consequences: nobody closes the inner subscriptions and they pile up; previous requests are not cancelled, so a response for a stale parameter may land on screen; the error cannot be handled in one place; and the outer unsubscribe does not stop the inner ones. The flat replacement is a flattening operator; when you need both the outer value and the inner result, build an object inside (`switchMap(id => load(id).pipe(map(data => ({ id, data }))))`).

---

**Why does `mergeMap` take a second argument?**

It is the concurrency limit. Without it, a stream of a thousand values opens a thousand simultaneous requests — the server refuses or the browser hits its connection cap. `mergeMap(fn, 4)` keeps at most four inner streams active; `mergeMap(fn, 1)` is equivalent to `concatMap`.

---

## Common follow-ups (group 4)

- "The user toggled a filter twice and the screen shows the previous filter's data — where is the bug?" → `mergeMap` instead of `switchMap`: the slow first response arrived last.
- "How is 'cancelled' different from 'ignored'?" → `switchMap` aborts work already started (a cancelled request is visible in Network), `exhaustMap` never starts it (no request at all).
- "Is `concatMap` just a safe `mergeMap`?" → no: it serializes work, so a slow operation delays the entire queue and a fast source makes the queue grow.
- "How do you load three independent resources after a route change?" → `switchMap` on the outside (to cancel stale work) plus `forkJoin` inside (parallel, one result).

## Group 5: Combining streams

**Why does `combineLatest` sometimes emit nothing at all?**

Because it emits nothing until **every** source has emitted at least once. In practice that shows up as an empty screen: two filters already produced values while a third stream (a `Subject` with no initial value, or a form's `valueChanges`) stays silent — and the whole view model is never built. Fixes: `startWith` on the silent sources, a `BehaviorSubject` instead of a `Subject`, or an explicit initial value. See [Combination Operators].

---

**`combineLatest` or `withLatestFrom` — how do you choose?**

The question is: **what should cause a recomputation?** If any of the values — `combineLatest` (linked filters: changing any of them reloads the list). If only one, with the rest providing context — `withLatestFrom` (a click on "save" plus the form's current state: saving must happen on the click, not on every keystroke). `withLatestFrom` also has a trap: a leading value arriving before the follower's first value is lost silently.

---

**How does `forkJoin` differ from `combineLatest`, and why does it "stay silent"?**

`forkJoin` is the `Promise.all` analogue: it emits **once**, the last value of every source, and only after each has completed. `combineLatest` emits on every change, so three HTTP requests produce three intermediate results instead of one final one. `forkJoin` staying silent almost always means one of the sources never completes (`interval`, a `Subject`, `fromEvent`). Two more properties: an error in any source terminates the whole result (a partial result requires `catchError` inside each source), and a source that completes without values makes the whole thing complete without emitting.

---

## Common follow-ups (group 5)

- "Three filters change programmatically one after another — how many requests with `combineLatest` + `switchMap`?" → three; `debounceTime(0)` collapses a synchronous burst.
- "Should I use `zip` instead of `forkJoin`?" → almost never: `zip` pairs by index and buffers whichever source runs ahead, which grows memory at different speeds.
- "`concat(interval(1000), api.load())` — when does the request fire?" → never: `concat` subscribes to the second source only after the first completes.
- "How do you build a timeout by combining streams?" → `race` with `timer`, though the dedicated `timeout({ first })` is the better answer.

## Group 6: Errors and retries

**Where do you put `catchError` — before or after a flattening operator, and why does it change the behaviour?**

An error terminates **the stream it occurred in**. With `catchError` outside (`switchMap(...)` then `catchError(...)`) the request error becomes an error of the outer stream — and the click stream or `route.params` dies forever: the handler never runs again. With `catchError` inside (`switchMap(id => load(id).pipe(catchError(...)))`) it turns the error into a value before it reaches the outer stream, so only that one request fails. The rule: long-lived source → `catchError` inside; one-shot request → outside is acceptable.

---

**How do you configure `retry` properly, and what should not be retried?**

Three mandatory elements: a **limit** (`retry()` without `count` repeats forever), a **delay**, preferably growing (`delay: (err, n) => timer(500 * 2 ** (n - 1))` — instant repeats finish off a downed service and earn a rate-limit ban), and a **filter by error type**: retry `5xx`, timeouts and `status === 0`, but retrying `401`/`422` is pointless because the result will not change. For long-lived streams `resetOnSuccess: true` is useful, clearing the counter after each successful value. `retryWhen` is deprecated in RxJS 7 — the replacement is `retry({ delay })`.

---

**How is `finalize` different from handling things in `subscribe`?**

`finalize` runs on **any** ending: `complete`, `error` and `unsubscribe`. Handling it in `subscribe` means duplicating code across `next`/`error`/`complete` and still missing the unsubscribe case — leaving the screen mid-load, for example. That is why "hide the spinner" and "release the resource" live in `finalize`. Next to it sits `timeout({ first, each })`: it turns a hung request's silence into a `TimeoutError` that then flows through ordinary error handling. See [Error Handling and Retries].

---

## Common follow-ups (group 6)

- "`catchError` returned `EMPTY` — what does the subscriber see?" → the stream completes with no values and no error; handy for "silently nothing", but it hides the problem from the caller.
- "What does `catchError` return if you return nothing?" → a type error: the operator must return an Observable for the stream to continue with.
- "Why does `timeout` go before `retry`?" → otherwise the timeout applies to all attempts combined rather than to each one.
- "How do you get a partial result from `forkJoin`?" → a `catchError` inside each source, turning a failure into a default value.

## Group 7: Multicasting and subscriptions

**Why did the same Observable make three HTTP requests?**

Because it is **cold**: the subscriber function runs per subscription, and three `| async` in a template are three independent subscriptions, hence three requests. Diagnosis: count requests in the Network tab, or add `tap({ subscribe: () => console.count('sub') })`. The fix: `shareReplay({ bufferSize: 1, refCount: true })`, or a single subscription with an `as` variable in the template. See [Multicasting and Subscription Management].

---

**How can `shareReplay` leak?**

By default `shareReplay(1)` uses `refCount: false`: the source is **not unsubscribed** when the subscriber count drops to zero, and the inner `ReplaySubject` keeps running indefinitely. Over an `interval`, a WebSocket or an event subscription that is a leak: the timer keeps ticking after the screen closes. The fix is `shareReplay({ bufferSize: 1, refCount: true })`. For a completed HTTP request, however, `refCount: false` is not a leak but the desired behaviour: the value is cached for the application's lifetime. Also remember `resetOnError`: otherwise the next subscriber may receive the cached error instead of a fresh attempt.

---

**Why must `takeUntil` be last in the `pipe()`?**

Because it only completes the part of the chain **before** it. If a `switchMap` follows `takeUntil`, its inner subscriptions keep living after the destroy signal — the leak remains even though "there is an unsubscribe". This is one of the rare cases where operator order affects resource release rather than the result.

---

**How do you detect a subscription leak?**

Signs: work continues after the screen closes (requests in Network, ticks in the console), and a handler fires several times for one action (every screen visit adds a live subscription). The check: log the lifecycle with `tap({ subscribe, unsubscribe, complete })` plus `finalize` — if `SUB` vastly outnumbers `UNSUB`, the leak is found. The second method is a heap snapshot before and after opening a screen repeatedly: a growing count of `Subscriber` objects or components points at retained subscriptions. Three questions to localize it: does the source complete on its own; is there a `shareReplay` without `refCount` over an infinite source; is `takeUntil` last?

---

## Common follow-ups (group 7)

- "How do you tell cold from hot?" → by the source: does it exist independently of the subscriber (`fromEvent`, a `Subject` — yes; `http.get`, `defer`, `interval` — no).
- "`share()` or `shareReplay()`?" → `share` when a late subscriber should not see the past; `shareReplay` when it should receive the latest values.
- "Where should `subscribe` actually be called?" → as close to the application's edge as possible: services return streams, the consumer subscribes, and in templates the subscription is handed to the framework (`async` pipe, `toSignal`).
- "What do you do with `publish().refCount()` in old code?" → that family (`multicast`/`publish`/`publishReplay`/`refCount`) is deprecated in RxJS 7 and removed in v8; the replacement is `share`/`shareReplay`, or `connectable()` for manual connection.

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
          catchError(() => of([])),  // INSIDE: a failed request does not kill the input stream
        ),
  ),
  shareReplay({ bufferSize: 1, refCount: true }), // when there are several subscribers
);
```

What the interviewer is actually checking: the choice of `switchMap` (not `mergeMap`) with the race-and-cancellation rationale; `debounceTime` plus `distinctUntilChanged` as a pair; `catchError` placed **inside** `switchMap`; no subscription inside the service; and an understanding of why `shareReplay` is there and why with `refCount: true`. A strong candidate adds that loading state is better expressed as its own stream or through `tap`/`finalize` than as a third field on the component.

## Common interview traps

- **Describing an Observable as "a Promise with several values"** — that is one axis out of four, and it usually precedes a missing grasp of laziness, from which both repeated requests and working cancellation follow.

- **Knowing the operators but having no selection criterion** — "switchMap cancels the previous one" with no answer to "when is that right and when is it dangerous" reads as a memorized definition. What is expected is the chain "scenario → operator → cost of getting it wrong".

- **Not connecting symptom to cause** — senior level shows in hearing "sometimes the previous filter's data is displayed" and naming `mergeMap` instead of `switchMap`, or hearing "the timer keeps ticking after the screen closed" and naming `shareReplay` without `refCount`.

- **Recipes from 2018 articles** — `toPromise()`, `retryWhen`, `publish().refCount()`, `pluck`, `tap(next, error, complete)`, the operator forms of `combineLatest`/`merge`/`zip` inside `pipe()`. All of these are deprecated in RxJS 7; knowing the current replacements shows you work with the current version.

- **Ignoring subscription management** — "I use the `async` pipe, it handles everything" is incomplete: the interviewer will ask about the cases where the subscription is manual and expects `takeUntil`/`takeUntilDestroyed` with an understanding of why `takeUntil` goes last.

- **"RxJS everywhere"** — senior interviews value the opposite: the ability to say where a stream is redundant (one value, no cancellation, no combining) and where `async`/`await` or signals read better.
