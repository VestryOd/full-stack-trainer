# Combination Operators

## Three questions before picking an operator

There are many combination operators, but the choice always reduces to three questions:

1. **Who decides when to emit?** Any source (`combineLatest`, `merge`) or one leader (`withLatestFrom`)?
2. **Do you need every value or only the latest?** Pairs by index (`zip`) or current values (`combineLatest`)?
3. **When is the result ready?** Continuously as things change, or once after everything completes (`forkJoin`)?

```
                                       How to combine streams
┌────────────────┬───────────────────────────────────────┬────────────────────────────────────────┐
│ operator       │ when it emits                         │ scenario                               │
├────────────────┼───────────────────────────────────────┼────────────────────────────────────────┤
│ combineLatest  │ on any change of any source           │ linked form filters                    │
├────────────────┼───────────────────────────────────────┼────────────────────────────────────────┤
│ forkJoin       │ once, after every source completes    │ parallel load of independent resources │
├────────────────┼───────────────────────────────────────┼────────────────────────────────────────┤
│ zip            │ in pairs, by index                    │ strict value correspondence (rare)     │
├────────────────┼───────────────────────────────────────┼────────────────────────────────────────┤
│ withLatestFrom │ only on the leading stream            │ an action plus current state           │
├────────────────┼───────────────────────────────────────┼────────────────────────────────────────┤
│ merge          │ on any value from any source          │ several sources of one event           │
├────────────────┼───────────────────────────────────────┼────────────────────────────────────────┤
│ concat         │ in turn, after the previous completes │ stages: cache first, then network      │
├────────────────┼───────────────────────────────────────┼────────────────────────────────────────┤
│ race           │ only from the first to emit           │ a timeout race, picking the fastest    │
├────────────────┼───────────────────────────────────────┼────────────────────────────────────────┤
│ startWith      │ a value ahead of the stream           │ initial state, a skeleton              │
└────────────────┴───────────────────────────────────────┴────────────────────────────────────────┘
            the operator forms of combineLatest/merge/zip inside pipe() are deprecated:
                     inside a pipe use combineLatestWith / mergeWith / zipWith
```

> **Legacy.** An important version detail: `combineLatest(a$, b$)`, `merge(a$, b$)` and `zip(a$, b$)` as **static functions** are the norm. The same names as **operators inside `pipe()`** are deprecated in RxJS 7 and will be removed in v8: the replacements are `combineLatestWith`, `mergeWith`, `zipWith`. The reason was confusion: `a$.pipe(combineLatest(b$))` and `combineLatest(a$, b$)` looked alike but produced different argument order in the result.

## combineLatest and its trap

`combineLatest` keeps the latest value of every source and emits a new tuple whenever any of them changes.

```
                 combineLatest and withLatestFrom on the same sources
status$         --1-----2--------3--|
query$          ------x-----y-------|

combineLatest   ------A-B---C----D--|
                      ^ A=(1,x) — the first emit happens ONLY once query$ has a value
                        B=(2,x)  C=(2,y)  D=(3,y): reacts to either source

withLatestFrom  --------A--------B--|
                        ^ A=(2,x): value 1 is LOST — query$ had no value yet;
                          emits only on the LEADING status$
          combineLatest gives 4 values (any change), withLatestFrom gives 2:
        the leading stream picks the moment, the follower only adds a snapshot
```

**The trap**: `combineLatest` emits nothing until **every** source has produced at least one value. The diagram shows it: value `1` arrived at tick 2, but the result appeared only at tick 6 — when the second stream finally spoke.

The practical symptom is a screen that stays empty "for no reason":

```ts
import { combineLatest, map } from 'rxjs';

// THE TRAP: if categories$ or sort$ do not emit at startup,
// vm$ never produces a value — the screen stays empty forever
const vm$ = combineLatest([tickets$, categories$, sort$]).pipe(
  map(([tickets, categories, sort]) => buildViewModel(tickets, categories, sort)),
);
```

Three ways to guarantee a first value:

```ts
import { combineLatest, startWith, BehaviorSubject } from 'rxjs';

// 1) startWith on the "silent" sources
combineLatest([
  tickets$,
  categories$.pipe(startWith([] as Category[])),
  sort$.pipe(startWith<SortOrder>('created-desc')),
]);

// 2) a BehaviorSubject instead of a Subject: it always has a current value
//    (see Creating Streams and Subjects)
private readonly sort = new BehaviorSubject<SortOrder>('created-desc');

// 3) for Angular forms: valueChanges does not emit the initial value,
//    so it has to be added explicitly
form.valueChanges.pipe(startWith(form.getRawValue()));
```

The second thing to keep in mind: `combineLatest` emits on **every** change, so three filters updated programmatically one after another produce three emits and three requests. The cure is `debounceTime(0)` (collapse a synchronous burst) or `distinctUntilChanged` with a comparator.

The typical correct scenario is linked filters:

```ts
const results$ = combineLatest({
  status: statusFilter$,
  query: searchQuery$.pipe(debounceTime(300)),
  page: page$,
}).pipe(
  // the object form of combineLatest (RxJS 6.5+) reads better than array destructuring
  switchMap(({ status, query, page }) => api.list({ status, query, page })),
);
```

## withLatestFrom: leader and follower

`withLatestFrom` is asymmetric: it emits **only** on a value from the main stream, taking a snapshot of the latest value from the others.

```ts
import { withLatestFrom, map, concatMap } from 'rxjs';

// "Save on click, taking the form's current state"
saveClicks$.pipe(
  withLatestFrom(formValue$, currentUser$),
  map(([, form, user]) => ({ ...form, updatedBy: user.id })),
  concatMap((payload) => api.save(payload)),
);
```

Using `combineLatest` here would be a straight-up bug: it would save on every form change rather than on the button press. And conversely, `withLatestFrom` is wrong for filters, because changing a "follower" filter would not trigger a reload.

The selection criterion is one question: **"what should cause a recomputation?"** If any of the values — `combineLatest`. If only one, with the rest merely adding context — `withLatestFrom`.

The second trap of `withLatestFrom` is visible in the diagram: a leading value that arrives before the follower has produced its first value is **lost silently**. A click made before the user profile loaded does nothing — no error, no log. If that is unacceptable, give the follower a `startWith` or restructure with `switchMap`, which will wait for a value.

## forkJoin and zip: one-shot combinations

```
            forkJoin and zip: how they differ from combineLatest
a$        --1-----2-----|
b$        ----x---------y----|

forkJoin  -------------------(2,y)|
                             ^ ONE value — the last of each, and only after
                               EVERY source has completed

zip       ----A---------B----|
              ^ A=(1,x): pairs by INDEX — first with first,
                B=(2,y): second with second; extra values are buffered
           forkJoin over an infinite source never emits anything;
      zip buffers when sources run at different speeds — a memory risk
```

### forkJoin is Promise.all

```ts
import { forkJoin } from 'rxjs';

// Three independent requests in parallel; the result arrives when all are in
const page$ = forkJoin({
  ticket: api.getTicket(id),
  comments: api.getComments(id),
  history: api.getHistory(id),
});
// { ticket, comments, history } — one emit, then complete
```

Three properties of `forkJoin` you must know, all of them consequences of "waits for `complete`":

- **An infinite source breaks everything.** `forkJoin([http$, interval(1000)])` never emits: the second stream never completes. That is the most common cause of "forkJoin stays silent".
- **An error in any source terminates the result.** Like `Promise.all`, `forkJoin` fails as a whole: to get a partial result, errors are swallowed inside each source with `catchError` (see [Error Handling and Retries]).
- **A source that completes without values produces an empty result.** If one stream completes having emitted nothing, `forkJoin` completes without emitting anything at all — silently.

```ts
// A partial result: one failed load does not break the page
forkJoin({
  ticket: api.getTicket(id),
  comments: api.getComments(id).pipe(catchError(() => of([] as Comment[]))),
  history: api.getHistory(id).pipe(catchError(() => of([] as Event[]))),
});
```

### zip pairs by index, not by time

`zip` matches the first value with the first, the second with the second, and so on. If one source is faster, its values are **buffered** while waiting for a partner — which means they grow in memory.

In practice `zip` is rarely needed: almost every time it seems necessary, what you actually want is `forkJoin` (one-shot requests) or `combineLatest` (current values). The legitimate case is a strict pairwise correspondence between two equally long streams — a stream of commands and a stream of acknowledgements, say.

## merge, concat, race, startWith

```ts
import { merge, concat, race, startWith, timer } from 'rxjs';

// merge: several sources of one event — "refresh" from three places
const refresh$ = merge(toolbarRefresh$, keyboardShortcut$, timer(0, 60_000));

// concat: stages in order — cache first, then the network
const data$ = concat(cache.read(key), api.load(key));

// race: whoever emits first wins, the rest are unsubscribed
const fastest$ = race(primaryApi.load(), mirrorApi.load());

// startWith: an initial state before the first real value
const state$ = updates$.pipe(startWith<State>({ status: 'loading' }));
```

What matters about each:

- **`merge`** joins by time: values arrive in the order they appear, from all sources. It takes a concurrency limit as a second argument, like `mergeMap`.
- **`concat`** subscribes to the next source only after the previous one completes. Hence the trap: `concat(interval(1000), api.load())` never reaches the request — the first stream is infinite.
- **`race`** picks the winner by **first emit**, not by completion, and unsubscribes from the losers. The classic use is a timeout: `race(api.load(), timer(5000).pipe(switchMap(() => throwError(() => new Error('timeout')))))`. Although for timeouts there is a dedicated `timeout` operator (see [Error Handling and Retries]).
- **`startWith`** simply prepends values. Useful for `combineLatest`, for showing a skeleton, and for making a stream "have a value" from tick one.

## Common selection mistakes

**`combineLatest` instead of `withLatestFrom` for an action.** A "save" button wired as `combineLatest([clicks$, form$])` saves on every form change — that is, on every keystroke. The tell: the action fires without the user acting.

**`withLatestFrom` instead of `combineLatest` for filters.** The list reloads only when the status changes while editing the search box "does nothing". The tell: some filters work, others do not.

**`forkJoin` over a stream that never completes.** Nothing happens and no error appears. The check: add `take(1)` to each source, or look for a `complete` in the chain.

**`combineLatest` where `forkJoin` belongs.** Three HTTP requests in `combineLatest` yield not one result but three intermediate tuples (as responses arrive), because every response is a source change. If you want one result "when everything is ready" — `forkJoin`.

**`merge` instead of `concat` for stages.** "Cache first, then network" with `merge` delivers both values in arbitrary order, and fresh data may be overwritten by the cache.

## Relation to other topics

```txt
[Creating Streams and Subjects]   — BehaviorSubject as a way to guarantee
                                     a first value for combineLatest
[Transformation and Filtering
 Operators]                        — startWith, debounceTime and
                                     distinctUntilChanged alongside combineLatest
[Flattening Operators]             — switchMap after combineLatest:
                                     the standard "filters → request" pairing
[Error Handling and Retries]       — why one failed source breaks forkJoin
                                     and how to get a partial result
[Multicasting and Subscription
 Management]                        — how many subscriptions combineLatest
                                     creates on a shared source
```

## Common interview traps

- **Not knowing about `combineLatest`'s silence** — it emits nothing until every source has produced a value. The expected answer includes the symptom ("the screen is empty although the data loaded") and three fixes: `startWith`, a `BehaviorSubject`, or rethinking the construct. Follow-up: "what if one source never emits at all?" — the result never appears, and there is no error.

- **Confusing `combineLatest` with `withLatestFrom`** — the most common pair after `switchMap`/`mergeMap`. What is expected is a criterion rather than a definition: "what should cause a recomputation". An extra probing question: "what happens on a click if the follower has not emitted yet?" — the value is lost silently.

- **"`forkJoin` is `combineLatest` for requests"** — no: `forkJoin` emits once after every source completes, `combineLatest` on every change. For three HTTP requests, `combineLatest` produces three intermediate results instead of one final one.

- **Not connecting "forkJoin is silent" with a missing `complete`** — the most common practical problem. The cause is always the same: one of the sources never completes (`interval`, a `Subject`, `fromEvent`).

- **Expecting a partial result from `forkJoin`** — like `Promise.all` it fails entirely when any source errors. The right answer is a `catchError` inside each source, turning the failed part into a default value.

- **`zip` instead of `forkJoin`** — it works in the simple case, but the semantics differ: `zip` pairs by index and buffers whichever source runs ahead. On streams of different speeds that is a memory leak; on one-shot requests the difference only shows up with repeated values.

- **`concat` with an infinite first source** — the second one never subscribes. A good answer immediately names the check: does the first stream complete at all?

- **Operator forms inside `pipe()`** — `a$.pipe(combineLatest(b$))`, `a$.pipe(merge(b$))` and `a$.pipe(zip(b$))` are deprecated in RxJS 7. The expected forms are `combineLatestWith`/`mergeWith`/`zipWith` inside a `pipe()`, or the static `combineLatest(a$, b$)` outside it.
