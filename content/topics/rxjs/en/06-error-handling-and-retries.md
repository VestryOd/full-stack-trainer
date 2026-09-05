# Error Handling and Retries

## An error terminates the stream

The subscription contract from [Reactive Model and Observables](./01-reactive-model-and-observables.md) is strict: `next` many times, then **exactly one** of `complete` or `error`. That means an error is not "one bad value among good ones" but the end of the stream:

```ts
import { fromEvent, map } from 'rxjs';

// the very first parsing error kills the click stream forever
fromEvent(button, 'click')
  .pipe(map((event) => JSON.parse((event.target as HTMLElement).dataset['payload']!)))
  .subscribe({
    next: (payload) => save(payload),
    error: (err) => console.error(err), // called once, and that is it
  });
```

The practical consequence worth memorizing verbatim: **the button still looks alive while the handler is dead**. There is no other sign beyond one console entry. The DOM (Document Object Model) listener was removed because the stream terminated, so later clicks go nowhere.

This class of failure is what makes error handling in RxJS not "good practice" but a condition for working software.

Two kinds of errors are worth distinguishing:

```ts
source$.pipe(
  map((x) => risky(x)),      // an error here travels the stream → catchError sees it
).subscribe({
  next: (value) => risky(value), // an error here is outside the stream → catchError cannot
});
```

An error thrown inside `subscribe`'s `next` callback is not a stream error: it goes to RxJS's global unhandled-error handler. That is an argument for moving logic out of `subscribe` into operators — there it is at least handleable.

## catchError and three recovery strategies

`catchError` intercepts an error and **must return a new Observable** — the one the stream continues with. Hence three strategies:

```ts
import { catchError, of, EMPTY, throwError } from 'rxjs';

// 1) Substitute a value: the screen renders and the user sees "no data"
api.list().pipe(catchError(() => of([] as Ticket[])));

// 2) Switch to a fallback stream: the network is down, read the cache
api.list().pipe(catchError(() => cache.read('tickets')));

// 3) Map the error and rethrow: the caller expects a domain error,
//    not an HttpErrorResponse
api.list().pipe(
  catchError((err: HttpErrorResponse) =>
    throwError(() => new TicketsUnavailableError(err.status)),
  ),
);
```

A fourth, separate shape is `EMPTY`: the stream completes with no values and no error. That is "silently do nothing", and it should be used deliberately — it hides the problem from the caller.

```ts
// Analytics: if sending a metric failed, the application does not care
metrics.send(event).pipe(catchError(() => EMPTY));
```

`catchError` has a second argument — the source Observable — which gives a compact form of infinite retry:

```ts
// caught is the same source; returning it resubscribes
socket$.pipe(catchError((err, caught) => caught));
```

It works, but it is dangerous. With no delay and no limit this is an endless resubscription loop. Against a server that is already down, your own client keeps sending requests with no pause and makes the outage worse. For retries there is `retry` with configuration — see below.

## Where to put catchError: inside or outside

```
   Where catchError sits decides whether the stream survives
         clicks: the 1st and 3rd requests succeed, the 2nd fails

clicks$  --c--c-------c--|

         switchMap(req) with catchError outside:
result   ----A--X
                ^ the stream is terminated: the third
                  click is never handled; the button
                  looks alive but the handler is dead

         switchMap(req.pipe(catchError)) — inside:
result   ----A--E-------A|
                ^ E is a fallback value instead of the
                  error; the outer click stream lives,
                  and the third click is handled
    an error terminates the stream it occurred in: inside a
 flattening operator only the inner one, outside the whole pipe
```

This is the article's main practical takeaway. The code differs by one pair of parentheses; the behaviour differs fundamentally:

```ts
// outside: one failed request kills the click stream
clicks$.pipe(
  switchMap((id) => api.load(id)),
  catchError(() => of(fallback)),   // fires once, then the stream is dead
);

// inside: only that particular request fails, the click stream lives
clicks$.pipe(
  switchMap((id) => api.load(id).pipe(catchError(() => of(fallback)))),
);
```

The reason is that an error terminates **the stream it occurred in**. Inside `switchMap` the error occurs in the inner stream (`api.load(id)`). A `catchError` there turns it into a value before it can reach the outer one.

Outside, the error has already passed through `switchMap` and become an error of the outer stream. And the outer stream here *is* the source of user events.

A flattening operator here means `switchMap` or `mergeMap` — an operator that subscribes to the inner stream itself. The rule for choosing a place:

- the source is **long-lived** (events, `interval`, a `Subject`, route params) → `catchError` **inside** the flattening operator;
- the source is **one-shot** (a single HTTP request, a `forkJoin` at screen start) → `catchError` outside is fine: there is nothing to terminate;
- you need both a local fallback and a global reaction → two `catchError`s: inside for the default value, outside for "everything is truly broken".

## retry: repeating with a delay

`retry` resubscribes to the source on error. The configuration is what matters, because `retry(3)` without a delay repeats instantly:

```
             retry with exponential backoff
source     --X
             ^ the first attempt failed

           retry({ count: 3, delay: (_, n) =>
                    timer(500 * 2 ** (n - 1)) })

attempt 1  --X
attempt 2  -----X
                ^ after 500 ms
attempt 3  ----------X
                     ^ after 1000 ms
attempt 4  --------------------V--|
                               ^ after 2000 ms — success
without a delay, retry repeats instantly and floods the server;
resetOnSuccess: true clears the counter after a successful value
```

```ts
import { retry, timer, throwError } from 'rxjs';

api.load().pipe(
  retry({
    count: 3,
    // delay can be a number (a fixed pause) or a function:
    // (error, retryCount) => Observable — an exponential backoff here
    delay: (error: HttpErrorResponse, retryCount) => {
      // retry only what is worth retrying
      if (error.status < 500 && error.status !== 0) {
        return throwError(() => error); // retrying a 4xx is pointless
      }
      return timer(500 * 2 ** (retryCount - 1)); // 500, 1000, 2000 ms
    },
    resetOnSuccess: true, // the counter resets after every successful value
  }),
);
```

Three things separate a working `retry` from a dangerous one:

1. **A count limit.** `retry()` without `count` repeats forever.
2. **A delay, preferably growing.** Instant repeats against a service that is already down make the outage worse, and they get your client blocked by rate limiting.
3. **A filter by error type.** Retrying a `401` or `422` is pointless: the result will not change. Retrying `5xx`, timeouts and `status === 0` (no network) makes sense.

About `resetOnSuccess`: it matters for long-lived streams such as a WebSocket. Without it, three disconnects over a week of uptime exhaust the limit; with it the counter resets after every successful value.

> **Legacy.** Retries with a delay used to be written as `retryWhen(errors => errors.pipe(delay(1000)))`. In RxJS 7 `retryWhen` is deprecated, and the message names the replacement: `retry({ delay })`. The reason: `retryWhen` made you treat "a stream of errors" as a separate concept, while `retry` says the same thing directly. Writing the backoff by hand with `scan` is obsolete too.

## timeout: an error instead of silence

A request that never answers is not an error as far as the stream is concerned: it is simply quiet. The spinner spins forever. `timeout` turns silence into an error:

```ts
import { timeout, TimeoutError, catchError, of, throwError } from 'rxjs';

api.load().pipe(
  // first — how long to wait for the first value; each — the maximum gap between values
  timeout({ first: 5000 }),
  catchError((err) =>
    err instanceof TimeoutError
      ? of({ status: 'timeout' as const })
      : throwError(() => err),
  ),
);

// For streams with continuing values (a socket, polling) — use each
socket$.pipe(timeout({ each: 30_000 })); // silent for over 30 seconds → error
```

There is also `timeout({ with: () => fallback$ })` — switch to a fallback stream instead of erroring. Useful when a timeout means "show the cache" rather than "show an error".

## The error-handling toolbox

Every tool from this article in one table, before the last of them gets its own section.

| operator | what it does | typical use |
|---|---|---|
| `catchError(() => of(x))` | substitutes a value for the error | an empty list, a default value |
| `catchError(() => other$)` | switches to a fallback stream | cache instead of network, an API mirror |
| `catchError(e => throwError(…))` | maps the error and rethrows | `HttpErrorResponse` to a domain error |
| `catchError((e, caught) => caught)` | resubscribes to the source | infinite retry (careful!) |
| `retry({ count, delay })` | resubscribes after an error | flaky network, `5xx` |
| `timeout({ each, first })` | throws `TimeoutError` on silence | a hung request, a slow socket |
| `finalize(fn)` | runs on any ending | hide a spinner, release a resource |
| `EMPTY` in `catchError` | completes without values | "silently nothing", no error branch |

## finalize: guaranteed cleanup

`finalize` is the only operator that runs on **any** ending: `complete`, `error` and `unsubscribe`. That makes it the right place to release resources, and the only place where cleanup is guaranteed to run:

```ts
import { finalize } from 'rxjs';

loading.set(true);
api.load().pipe(
  finalize(() => loading.set(false)),  // runs in all three cases
).subscribe({ next: render, error: showError });
```

Compare that with doing the same in `subscribe`. You would duplicate `loading.set(false)` across `next`, `error` and `complete`, and still miss the unsubscribe case — the user leaving the screen. That is why "hide the spinner" almost always lives in `finalize`.

An important ordering note: put `finalize` **after** `catchError` when the cleanup must also run for handled errors. And `finalize` never swallows the error. It only performs a side effect.

## A practical example: a resilient request

Putting it together — a request that survives a flaky network, never hangs forever, reports a meaningful error and always closes the spinner:

```ts
import {
  catchError, finalize, retry, throwError, timeout, TimeoutError, timer,
} from 'rxjs';

export class TicketsUnavailableError extends Error {
  constructor(readonly reason: 'timeout' | 'server' | 'network') {
    super(`Tickets unavailable: ${reason}`);
  }
}

function loadTickets(api: TicketApi, ui: LoadingUi) {
  ui.setLoading(true);

  return api.list().pipe(
    // 1. do not wait forever: silence becomes a TimeoutError
    timeout({ first: 8000 }),

    // 2. retry only what is worth retrying, with a growing pause
    retry({
      count: 2,
      delay: (error, attempt) => {
        const retryable =
          error instanceof TimeoutError ||
          (error as HttpErrorResponse).status >= 500 ||
          (error as HttpErrorResponse).status === 0;

        return retryable ? timer(500 * 2 ** (attempt - 1)) : throwError(() => error);
      },
    }),

    // 3. surface a domain error rather than a transport one
    catchError((error) => {
      if (error instanceof TimeoutError) {
        return throwError(() => new TicketsUnavailableError('timeout'));
      }
      const status = (error as HttpErrorResponse).status;
      return throwError(
        () => new TicketsUnavailableError(status === 0 ? 'network' : 'server'),
      );
    }),

    // 4. the spinner closes on success, on error and on leaving the screen
    finalize(() => ui.setLoading(false)),
  );
}
```

The operator order is not accidental:

- `timeout` before `retry`, otherwise the timeout would apply to all attempts combined;
- `retry` before `catchError`, otherwise the mapped error would not be recognized as retryable;
- `finalize` last.

> **Angular context.** In Angular this logic usually lives in an HTTP interceptor rather than a service. Retries and error mapping then apply to every request at once. The "show a banner" branch stays separate from the "show a field error" branch. A code walkthrough is in the Angular course, in the chapter on HTTP and interceptors.

## Relation to other topics

- [Reactive Model and Observables](./01-reactive-model-and-observables.md) — the `next`/`error`/`complete` contract that makes stream termination inevitable.
- [Creating Streams and Subjects](./02-creating-streams-and-subjects.md) — `throwError` as a factory, and why a `Subject` that received an error is dead forever.
- [Transformation and Filtering Operators](./03-transformation-and-filtering-operators.md) — why an error cannot simply be filtered out.
- [Flattening Operators](./04-flattening-operators.md) — why `catchError`'s position relative to `switchMap` changes the behaviour.
- [Combination Operators](./05-combination-operators.md) — why one error breaks a whole `forkJoin`, and how to get a partial result.
- [Multicasting and Subscription Management](./07-multicasting-and-subscription-management.md) — how an error inside `shareReplay` affects every subscriber.

## Common interview traps

- **"An error is just another notification in the stream"** — no. After `error` the stream is dead: `next` and `complete` will not follow, and the teardown has already run. The expected illustration is a stream of user events that "stopped working" after one failed operation.

- **`catchError` at the end of a chain over a long-lived source** — the most consequential mistake. After the first error a click stream or `route.params` is terminated and the interface stops responding with no visible sign. What is expected is placing `catchError` **inside** the flattening operator, plus the reason: an error terminates the stream it occurred in.

- **A `catchError` that returns nothing** — the operator must return an Observable. Returning `undefined`, or logging without a `return`, is a type error. Semantically it is an attempt to swallow the error, and swallowing is what `EMPTY` is for.

- **`retry` with no delay and no limit** — `retry()` repeats forever and instantly. A service that is already down gets a flood of requests, and the client gets blocked by rate limiting. The expected answer is `retry({ count, delay })` with a growing delay and a filter: retrying `4xx` is pointless.

- **Not distinguishing retryable from non-retryable errors** — retrying `422 Unprocessable Entity` or `401` will not change the outcome. A good answer names the criterion: retry `5xx`, timeouts and `status === 0`.

- **Answering with `retryWhen`** — deprecated in RxJS 7 with the direct replacement `retry({ delay })`. Knowing this shows the candidate has worked with a current version rather than importing recipes from 2018 articles.

- **Hiding the spinner in `subscribe` instead of `finalize`** — then `loading = false` is duplicated across three callbacks. It also misses the unsubscribe case, when the user leaves the screen mid-load. And `finalize` is the only place that runs on `complete`, `error` and `unsubscribe` alike.

- **Not knowing about `timeout`** — "the request hung and the spinner is eternal" is not solved by a timer in the component. The tool is `timeout({ first })`. It converts silence into a `TimeoutError`, which then goes through ordinary error handling.

- **Confusing a stream error with an error in the subscriber** — an exception thrown inside `subscribe`'s `next` callback does not pass through `catchError`. It goes to the global handler instead. That is the argument for keeping logic in operators rather than in `subscribe`.
