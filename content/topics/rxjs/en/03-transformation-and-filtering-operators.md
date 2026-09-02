# Transformation and Filtering Operators

## An operator is a pure function over a stream

An operator in RxJS is a function that takes an Observable and returns a **new** one. The original stream is never modified:

```ts
import { map, of } from 'rxjs';

const source$ = of(1, 2, 3);
const doubled$ = source$.pipe(map((x) => x * 2));

// source$ is unchanged: it still emits 1, 2, 3
source$.subscribe(console.log);   // 1 2 3
doubled$.subscribe(console.log);  // 2 4 6
```

`pipe()` is function composition rather than "calling methods one after another": each operator wraps the previous stream. Two practical consequences follow.

First, **operator order changes the result**, because each one works on the previous one's output:

```ts
// Filter 100 values first, then transform 3 of them expensively
source$.pipe(filter(isRelevant), map(expensiveTransform));

// Transform 100 values expensively first, then throw 97 away
source$.pipe(map(expensiveTransform), filter(isRelevant));
```

Second, **a custom operator is just a function** returning a composition of existing ones. Nothing has to be written from scratch:

```ts
import { pipe, filter, map, distinctUntilChanged } from 'rxjs';

// an operator is pipe() without a source
export function searchQuery(minLength = 2) {
  return pipe(
    map((value: string) => value.trim()),
    filter((value) => value.length >= minLength),
    distinctUntilChanged(),
  );
}

// usage is indistinguishable from a built-in operator
input$.pipe(searchQuery(3)).subscribe(load);
```

> **Legacy.** Before RxJS 5.5 operators were **prototype methods**: `source.map(fn).filter(pred)`. That "patch operator" syntax required imports like `import 'rxjs/add/operator/map'`. It broke tree-shaking, so the whole of RxJS ended up in the bundle. It also caused conflicts when two library versions met in one project. It has since been removed; `.pipe()` with individual imports is the only norm, not "the new style".

## How to read marble diagrams

Marble notation is the language RxJS documentation and every timing explanation is written in. Five minutes spent learning to read it saves hours:

```
                  How to read a marble diagram
source  --a---b-----c--|
          ^ value a arrived early
              ^ value b — later
                    ^ value c — later still
                       ^ complete: the stream is done

        a dash = the passage of time (an abstract unit, not ms)

source  --a---b-----c--|
        map(x => x.toUpperCase())
result  --A---B-----C--|
        map keeps the timing: one value in, one value out

source  --a---b-----c--|
        filter(x => x !== "b")
result  --a---------c--|
        filter never shifts values in time, it only drops them
```

Read it like this: the horizontal axis is time flowing left to right, symbols are values, `|` is `complete`, `X` is `error`. Dashes do not stand for a specific number of milliseconds: they show *relative* intervals.

The main question you ask a diagram is: **did the values shift in time, and did their number change?** Operators split into groups along those two axes:

- `map` changes neither;
- `filter` changes the count;
- `debounceTime` changes both count and timing.

## Transformation

### map: one to one

```ts
import { map } from 'rxjs';

users$.pipe(map((user) => user.name));            // User → string
responses$.pipe(map((r) => r.data.items ?? []));  // safe extraction
```

> **Legacy.** For "grab a field" there used to be `pluck('data', 'items')`. In RxJS 7 it is deprecated with the replacement spelled out in the message: `map(x => x?.data?.items)`. The reason is that optional chaining does the job better and types more precisely than string keys.

### scan: an accumulator for an infinite stream

`scan` is `reduce` that emits the intermediate result at every step:

```ts
import { scan, reduce, of } from 'rxjs';

// scan: a value after EVERY step
of(1, 2, 3).pipe(scan((acc, x) => acc + x, 0)).subscribe(console.log);
// 1, 3, 6

// reduce: only the total, and only on complete
of(1, 2, 3).pipe(reduce((acc, x) => acc + x, 0)).subscribe(console.log);
// 6
```

Hence the rule: on infinite streams `reduce` is useless, because it waits for a `complete` that never comes. For accumulating state, `scan` is the primary tool:

```ts
// a click counter
clicks$.pipe(scan((count) => count + 1, 0));

// accumulating a list of messages
messages$.pipe(scan((all, message) => [...all, message], [] as Message[]));

// a state reducer over a stream of actions
actions$.pipe(scan(reducer, initialState));
```

That last example is what Redux-style stores are built on: a stream of actions plus `scan` with a reducer gives you a stream of states.

## Filtering and bounding

Filtering drops values, and bounding decides when the stream is allowed to end. Eight operators cover almost every case, and the third column holds the nuance people ask about at interviews.

| operator | what it does | the nuance people ask about |
|---|---|---|
| `filter(pred)` | lets matching values through | the stream goes on, no complete |
| `take(n)` | the first `n` values, then complete | it completes and tears down for you |
| `takeWhile(pred)` | while the predicate holds | `inclusive: true` also emits the stopper |
| `takeUntil(notifier$)` | until `notifier$` emits | the main teardown technique |
| `first(pred?)` | the first match, then complete | throws `EmptyError` when nothing came |
| `last(pred?)` | the last match on complete | waits for complete, so not for infinite streams |
| `skip(n)` / `skipWhile` | drops the start of the stream | values are lost, not buffered |
| `distinctUntilChanged()` | drops consecutive duplicates | compares by reference; pass a comparator |

The first two rows hide one more difference. On an empty stream `take(1)` simply completes, while `first()` throws `EmptyError` — which is sometimes exactly what you want.

Two places where mistakes happen regularly.

**`take(n)` completes the stream.** It is not "skip past n values" but "take n and close the subscription". The property is used deliberately: `take(1)` is the standard way to get one value without thinking about teardown.

**`distinctUntilChanged` compares by reference.** For objects that means two structurally identical objects count as different:

```ts
import { distinctUntilChanged, distinctUntilKeyChanged, map } from 'rxjs';

// does not work for objects: every API response is a new object
state$.pipe(distinctUntilChanged());

// Option 1: a comparator
state$.pipe(distinctUntilChanged((a, b) => a.status === b.status && a.query === b.query));

// Option 2: compare a specific key
state$.pipe(distinctUntilKeyChanged('status'));

// Option 3: narrow to a primitive first
state$.pipe(map((s) => s.status), distinctUntilChanged());
```

The third option is usually preferable: comparing primitives is cheap and needs no comparator to maintain as the model evolves.

## Time operators: debounce, throttle, audit

```
       debounceTime, throttleTime and auditTime on one burst
source           -a-b-c---------d-e-------|

debounceTime(4)  ---------c---------e-----|
                          ^ waits for a pause, emits the last value

throttleTime(4)  -a-------------d---------|
                  ^ emits the first, then goes silent for the window

auditTime(4)     -----c-------------e-----|
                      ^ waits until the window ends,
                        emits the last value from it
 search as you type — debounceTime; buttons, scroll — throttleTime;
        "no more often, but always the freshest" — auditTime
```

Three operators solve the same problem: "reduce the rate". Their semantics differ, so the choice comes down to one question — which value from the burst do you need?

**`debounceTime(ms)`** waits for a pause of the given length and emits the last value. Ideal for typing: while the user types there are no requests; the moment they stop, one request goes out with the final text.

```ts
searchInput$.pipe(
  debounceTime(300),
  distinctUntilChanged(),           // do not search the same thing twice
  switchMap((q) => api.search(q)),  // cancel the previous request
);
```

The flip side: under continuous typing the value may never be emitted at all. For "fire no more than once a second but react immediately", `debounceTime` is the wrong tool.

**`throttleTime(ms)`** emits the first value immediately and then ignores everything for the window. This is about instant reaction with a rate cap: scroll handling, protecting a button from a burst of clicks, sending analytics.

```ts
scroll$.pipe(throttleTime(100), map(getScrollPosition));
saveClicks$.pipe(throttleTime(1000)); // first click fires, repeats within 1s do not
```

By default `throttleTime` uses `leading: true, trailing: false` — "the first yes, the last no". Configuration changes that: `throttleTime(1000, undefined, { leading: false, trailing: true })` gives behaviour close to `auditTime`.

**`auditTime(ms)`** is throttle's mirror image. On receiving a value it waits until the window ends, then emits the **last** value that arrived during it. The use case: "update the indicator no more than every 100 ms, but always show the current state".

Next to it sits **`sampleTime(ms)`** — "emit the latest value every ms on a timer", so the rate is fixed regardless of source activity. Useful for metrics and real-time charts.

The practical criterion is short:

- you need the **last** value after quiet — `debounceTime`;
- you need an **immediate** reaction with a cap — `throttleTime`;
- you need the **freshest** value on a fixed rhythm — `auditTime` or `sampleTime`.

## tap: side effects and their abuse

`tap` does not change the stream — it lets you observe passing values. There are three legitimate uses: logging, debugging, and side effects unrelated to the data (analytics, syncing to external storage).

```ts
import { tap } from 'rxjs';

// Debugging: see what actually flows through a given part of the chain
source$.pipe(
  tap((value) => console.debug('before filter', value)),
  filter(isRelevant),
  tap((value) => console.debug('after filter', value)),
);

// Watching the lifecycle: an observer object instead of positional callbacks
request$.pipe(
  tap({
    subscribe: () => metrics.start('load-tickets'),
    next: (response) => metrics.mark('first-byte', response.length),
    error: (err) => logger.error('load failed', err),
    complete: () => metrics.end('load-tickets'),
    finalize: () => spinner.hide(),        // on complete, on error and on unsubscribe
  }),
);
```

> **Legacy.** The `tap(nextFn, errorFn, completeFn)` form with separate callbacks is deprecated in RxJS 7 — an observer object is expected. Beyond consistency with `subscribe({...})`, the object form exposes `subscribe`, `unsubscribe` and `finalize`, which the positional form cannot reach.

Abuse looks like this:

```ts
// bad: tap mutates state — the stream stops being a description of data
tickets$.pipe(
  tap((tickets) => (this.tickets = tickets)),          // writing to a field
  tap((tickets) => (this.count = tickets.length)),     // a derived value
  tap(() => (this.loading = false)),                   // driving the UI
).subscribe();
```

Four things are wrong here:

1. The chain's outcome lives in its side effects rather than in its value, so it cannot be reused and is hard to test.
2. The order of the effects depends on the order of the operators.
3. A second subscription runs every effect twice.
4. A bare `subscribe()` signals that the real result is "hidden" inside `tap`.

The right shape is to return data from the stream and handle it in one place:

```ts
// Derived values come from operators, not from effects
readonly tickets$ = source$;
readonly count$ = source$.pipe(map((tickets) => tickets.length));

// The single side effect lives where the stream is consumed
tickets$.subscribe((tickets) => this.render(tickets));
```

A guiding rule: if removing every `tap` from a chain breaks it, `tap` was used for the wrong purpose.

## Relation to other topics

- [Reactive Model and Observables](./01-reactive-model-and-observables.md) — why an operator returns a new stream, and what the subscription contract is.
- [Creating Streams and Subjects](./02-creating-streams-and-subjects.md) — the sources these operators apply to.
- [Flattening Operators](./04-flattening-operators.md) — what to do when `map` returns a stream instead of a value.
- [Combination Operators](./05-combination-operators.md) — joining several streams.
- [Error Handling and Retries](./06-error-handling-and-retries.md) — why an error cannot be "filtered out".
- [Multicasting and Subscription Management](./07-multicasting-and-subscription-management.md) — `takeUntil` as the main teardown technique.

## Common interview traps

- **"Operators modify the stream"** — they do not: every operator returns a new Observable and the source stays intact. It follows that `source$.pipe(map(...))` without using the result does nothing, and the same `source$` can feed several independent chains.

- **Not distinguishing `scan` from `reduce`** — `scan` emits the intermediate result on every value, `reduce` only the total on `complete`. A probing question: "what does `reduce` emit on `interval(1000)`?" The right answer: nothing, the stream never completes and the subscriber never receives a value.

- **Confusing `debounceTime` with `throttleTime`** — the most common pair at interviews. What is expected is not a definition but a criterion. Need the last value after quiet, as in search? That is `debounce`. Need an immediate reaction with a rate cap, as on scroll and clicks? That is `throttle`. The follow-up question is "what if the user types nonstop for a minute?" With `debounceTime` no request goes out at all.

- **`distinctUntilChanged()` on objects** — it compares by reference, so it is useless for API responses: every object is new. The expected answer is a comparator, `distinctUntilKeyChanged`, or a `map` down to a primitive first.

- **Not knowing that `take(n)` completes the stream** — it is not "take and continue". After the n-th value `complete` arrives, the subscription is torn down and the teardown runs. That is exactly why `take(1)` is a legitimate way to avoid manual unsubscription.

- **`first()` instead of `take(1)` without knowing the difference** — on an empty stream `first()` throws `EmptyError` while `take(1)` completes quietly. The choice depends on whether "no value" is an error in your scenario.

- **A `tap` that contains the logic** — a marker that the candidate treats the stream as "a loop with callbacks". A good answer names concrete consequences: the chain cannot be reused, effects double on a second subscription, and testing requires spies instead of asserting values.

- **Answering with `pluck('a', 'b')`** — deprecated in RxJS 7, with the replacement `map(x => x?.a?.b)` stated in the deprecation message itself. Likewise `tap(next, error, complete)` with positional arguments — an observer object is expected.
