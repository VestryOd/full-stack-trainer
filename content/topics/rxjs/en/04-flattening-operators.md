# Flattening Operators

## Higher-order Observables: a stream of streams

`map` from [Transformation and Filtering Operators] turns a value into a value. But most of the time a value should **start new asynchronous work**: the user typed something, so a request must go out. And then `map` returns not data but another Observable:

```
                   Where a stream of streams comes from
input   --a-------b-------|
        map(q => api.search(q))     ← returned an Observable, not a value
result  --O-------O-------|
          ^ O is an Observable object, not yet subscribed

        the subscriber receives two Observables instead of data:
        Observable { … }  Observable { … }

        switchMap(q => api.search(q))  ← the operator subscribes for you
result  ------A-------B---|
              ^ A is the request RESULT; the offset is the response time
```

Such a stream is called a **higher-order Observable** — a stream whose values are other streams. Working with it directly is pointless: the subscriber receives `Observable` objects rather than data.

```ts
import { map, switchMap } from 'rxjs';

// The problem: next receives an Observable
input$.pipe(map((q) => api.search(q))).subscribe((value) => {
  console.log(value); // Observable { ... } — not the search result
});

// The fix: a flattening operator subscribes to the inner stream for you
input$.pipe(switchMap((q) => api.search(q))).subscribe((results) => {
  console.log(results); // Ticket[] — what you actually wanted
});
```

Flattening answers one question: **what should happen to the previous inner work when a new value arrives?** There are exactly four possible answers, and each is its own operator.

## Four strategies on one example

Take a single scenario: the user types into a search box, every value fires an HTTP request, and requests do not answer instantly.

```
                        Four strategies on one source
            the request for each value answers after 4 ticks: a→A, b→B, c→C

source      --a--b--------c-----|

switchMap   ---------B--------C-|
                     ^ a's request was CANCELLED when b arrived: A never came

mergeMap    ------A--B--------C-|
                  ^ both ran in parallel, order follows response time

concatMap   ------A---B-------C-|
                      ^ b WAITED for a to finish: order guaranteed, but later

exhaustMap  ------A-----------C-|
                  ^ b was IGNORED: new values are dropped while a is in flight
            legend: a b c — input values, A B C — request results,
        | — complete. A cancelled or dropped request yields no result
```

Note the main point: **all four received identical input and produced different output**. This is not an optimization or a matter of style — it is different business logic expressed in one word.

### switchMap: cancel the previous one

```ts
import { debounceTime, distinctUntilChanged, switchMap } from 'rxjs';

const results$ = searchInput$.pipe(
  debounceTime(300),
  distinctUntilChanged(),
  // a new request cancels the previous one: unsubscribing from the inner
  // stream aborts the HTTP request (see Reactive Model and Observables)
  switchMap((query) => api.search(query)),
);
```

The meaning: "I do not need the result of an outdated request." That holds for any **read** where only the current result matters:

- search and autocomplete;
- reloading a list when a filter changes;
- loading data when a route parameter (`:id`) changes;
- switching tabs with different data.

A bonus is network savings: a cancelled request is aborted rather than merely ignored.

### mergeMap: everything in parallel

```ts
import { mergeMap } from 'rxjs';

// Load details for each id — order is irrelevant, no waiting on each other
const details$ = ids$.pipe(mergeMap((id) => api.getTicket(id)));

// Limiting concurrency with the second argument: at most 4 requests at once
const throttled$ = ids$.pipe(mergeMap((id) => api.getTicket(id), 4));
```

The meaning: "every operation is needed, order does not matter." Fits independent loads, telemetry, parallel item processing. The key detail is that **result order is not guaranteed**: results arrive by response time, so a slow first request lands after a fast second one.

Always keep the second argument (`concurrent`) in mind: an unbounded `mergeMap` over a stream of a thousand values opens a thousand simultaneous requests.

### concatMap: strictly in order

```ts
import { concatMap } from 'rxjs';

// Every change is saved in turn: the write order equals the action order
const saved$ = changes$.pipe(concatMap((change) => api.patch(change)));
```

The meaning: "run them all, preserving order." It is `mergeMap` with `concurrent: 1`, and it is what **writes** need whenever operation order determines the final state: sequential `PATCH` calls, applying a queue of offline actions, uploading files one after another.

The cost is latency: if the first operation hangs, the whole queue waits. And if the source emits faster than the queue drains, the queue grows without bound.

### exhaustMap: ignore the new ones

```ts
import { exhaustMap } from 'rxjs';

// Repeated presses during a save are dropped
const submitted$ = submitClicks$.pipe(exhaustMap((form) => api.create(form)));
```

The meaning: "the current operation outranks new ones." The classic case is double-click protection: while a `POST` is in flight, repeated presses do not create a second entity. It is also used for a "refresh now" button in polling, so the button cannot spawn parallel refreshes.

The flip side: values are dropped silently. If the user pressed "save" with a changed form while the previous save was running, their last action **will not happen** — and the UI must say so.

## The choice table

```
                                     The choice table and the cost of getting it wrong
┌────────────┬──────────────────────────────┬──────────────────────────────────────────┬──────────────────────────────────┐
│ operator   │ what it does to the previous │ scenario                                 │ if you pick wrong                │
├────────────┼──────────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────┤
│ switchMap  │ cancels it                   │ search, autocomplete, filter change, :id │ lost writes on POST              │
├────────────┼──────────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────┤
│ mergeMap   │ runs in parallel             │ independent loads, analytics             │ a race: interleaved responses    │
├────────────┼──────────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────┤
│ concatMap  │ queues it                    │ sequential writes where order matters    │ the queue grows, lag accumulates │
├────────────┼──────────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────┤
│ exhaustMap │ ignores new ones             │ double clicks, repeated submits          │ the user's actions are dropped   │
└────────────┴──────────────────────────────┴──────────────────────────────────────────┴──────────────────────────────────┘
                         default for READS is switchMap; for WRITES it is concatMap or exhaustMap:
                               a cancelled POST may already have been executed on the server
```

A practical selection algorithm — three questions:

1. **Do I need the previous operation's result?** No — `switchMap`. Yes — read on.
2. **Does order matter?** Yes — `concatMap`. No — `mergeMap` (remembering `concurrent`).
3. **Should new values even be accepted while the current operation runs?** No — `exhaustMap`.

## The cost of getting it wrong

### switchMap on writes: lost data

```ts
// DANGEROUS: the user quickly edits two fields
formChanges$.pipe(switchMap((data) => api.patch(data))).subscribe();
```

The first `PATCH` is cancelled by the second. Cancelling on the client **does not cancel processing the server already began**: the request may have arrived and applied, or it may have been cut off halfway. The result is non-deterministic state: sometimes everything saved, sometimes only the last change, sometimes part of it. That is unacceptable for writes; the right choice is `concatMap` (save all, in order) or `exhaustMap` (drop the extra clicks).

### mergeMap where order matters: a race

```ts
// The user toggled the filter twice: "open", then "closed"
filter$.pipe(mergeMap((f) => api.list(f))).subscribe((list) => this.render(list));
```

The `"open"` request turned out slower — its response arrives **after** the `"closed"` one, and the screen ends up showing the list for a filter that is no longer selected. That is the classic UI race `switchMap` rules out by construction: the outdated request is cancelled and its response never renders.

### concatMap on search: a growing queue

```ts
// Every keystroke joins the queue
searchInput$.pipe(concatMap((q) => api.search(q))).subscribe();
```

Ten characters mean ten requests executed one after another. The user watches results "chase" their typing with growing lag, and the last one — the only one they wanted — arrives last. This wants `switchMap`.

### exhaustMap on search: silence

With `exhaustMap` the first request runs and all further input during it is dropped — search shows results for the first few characters and then appears to freeze.

## Nesting and how to avoid it

The most common structural mistake is a subscription inside a subscription:

```ts
// BAD: subscribe inside subscribe
route.params.subscribe((params) => {
  api.getTicket(params.id).subscribe((ticket) => {
    api.getComments(ticket.id).subscribe((comments) => {
      this.render(ticket, comments);
    });
  });
});
```

What is wrong: nobody closes the inner subscriptions (they pile up as `:id` changes quickly); previous requests are not cancelled, so a response for an old ticket may land on screen; an error at any level breaks the whole construct with no single place to handle it; and unsubscribing is impossible — the outer teardown does not stop the inner ones.

The flat version reads well and behaves predictably:

```ts
import { switchMap, map, distinctUntilChanged } from 'rxjs';

const view$ = route.params.pipe(
  map((params) => params['id'] as string),
  distinctUntilChanged(),
  // changing the id cancels the previous one's pending requests
  switchMap((id) =>
    api.getTicket(id).pipe(
      switchMap((ticket) =>
        api.getComments(ticket.id).pipe(map((comments) => ({ ticket, comments }))),
      ),
    ),
  ),
);
```

When you need **both** the outer value **and** the inner result, two techniques avoid extra nesting:

```ts
// 1) the projector's second argument: (outer, inner) => result
route$.pipe(switchMap((id) => api.getTicket(id), (id, ticket) => ({ id, ticket })));

// 2) usually more readable — build the object inside
route$.pipe(switchMap((id) => api.getTicket(id).pipe(map((ticket) => ({ id, ticket })))));
```

And when the inner requests are independent, they should not be nested at all: parallel loading is expressed with `forkJoin`/`combineLatest`, see [Combination Operators].

```ts
import { forkJoin, switchMap } from 'rxjs';

const page$ = route.params.pipe(
  switchMap((params) =>
    forkJoin({
      ticket: api.getTicket(params['id']),
      comments: api.getComments(params['id']),
      history: api.getHistory(params['id']),
    }),
  ),
);
```

> **Angular context.** These are exactly the two most common RxJS spots in an Angular application: loading data by a route parameter (`route.params` + `switchMap`) and live search (`debounceTime` + `switchMap`). A detailed walkthrough with signals and `takeUntilDestroyed` lives in the Angular course, in the chapter on RxJS in Angular.

## Error handling inside flattening

One detail ties this article to the next one: **where you put `catchError` changes the behaviour**.

```ts
// catchError OUTSIDE: one failed request kills the whole input stream —
// search stops working forever
input$.pipe(
  switchMap((q) => api.search(q)),
  catchError(() => of([])),
);

// catchError INSIDE: only the current request fails, the input stream lives
input$.pipe(
  switchMap((q) => api.search(q).pipe(catchError(() => of([])))),
);
```

The reason is that an error terminates the stream it occurred in: outside that is the outer stream (`input$`), inside it is only the inner one. The full treatment is in [Error Handling and Retries].

## Relation to other topics

```txt
[Reactive Model and Observables]  — why unsubscribing aborts an HTTP request:
                                     all of switchMap's semantics rests on it
[Transformation and Filtering
 Operators]                        — debounceTime and distinctUntilChanged,
                                     without which switchMap on input is partial
[Combination Operators]            — parallel independent requests:
                                     forkJoin instead of nested subscriptions
[Error Handling and Retries]       — why catchError inside and outside a
                                     flattening operator behave differently
[Multicasting and Subscription
 Management]                        — how not to create N requests instead of one
```

## Common interview traps

- **"switchMap is `map` for async"** — a description that misses the essential part: cancelling the previous inner work. What is expected is the framing question "what should happen to the previous request": cancel it (`switchMap`), run in parallel (`mergeMap`), queue it (`concatMap`), ignore the new one (`exhaustMap`).

- **`switchMap` for write operations** — the most expensive mistake by consequence. Cancelling on the client does not roll back what the server already started processing: the result is non-deterministic state. For `POST`/`PATCH` the expected answer is `concatMap` (all in order) or `exhaustMap` (drop extra presses).

- **Not knowing about `mergeMap`'s `concurrent`** — an unbounded `mergeMap` on a large stream opens as many parallel requests as there are values. Follow-up: "what happens with a thousand ids?" — a thousand simultaneous requests, a server refusal, or the browser's connection limit.

- **"`concatMap` is just a safe `mergeMap`"** — it is not: it serializes the work, so a slow first operation delays the entire queue, and a fast source makes the queue grow without bound. It is a deliberate trade-off for ordering, not "the more reliable option".

- **Subscribing inside a subscription** — a marker that the candidate has not internalized flattening. A good answer names four concrete consequences: unclosed inner subscriptions, no cancellation of outdated requests, no single place to handle errors, and an outer teardown that does not work.

- **`catchError` at the end of a chain over user events** — after the first error the stream is dead and the interface "stops responding". What is expected is the understanding that `catchError` goes **inside** `switchMap` to confine termination to the inner stream.

- **Not distinguishing "cancelled" from "ignored"** — `switchMap` aborts work already begun (the request is cancelled), `exhaustMap` never starts new work (the value is dropped). The difference is visible in the Network tab: the first case shows a cancelled request, the second shows no request at all.

- **Treating a response race as "a backend bug"** — if fast filter switching leaves the wrong data on screen, the cause is `mergeMap` where `switchMap` belongs. Connecting the symptom ("sometimes the previous filter's list is displayed") to the operator choice is what makes an answer senior-level.
