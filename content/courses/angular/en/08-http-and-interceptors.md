# HTTP and interceptors

## Theory

### Wiring it up and typed requests

`HttpClient` is not available by default — it has to be provided:

```ts
provideHttpClient(
  withInterceptors([authInterceptor, loggingInterceptor, errorInterceptor]),
)
```

One important change is still described incorrectly all over the internet: **`withFetch()` is no longer needed**. `FetchBackend` is the default transport, and the flag itself is deprecated ("`withFetch` is not required anymore"). If you need the old transport, there is `withXhr()`.

The other features of `provideHttpClient`:

- `withInterceptorsFromDi()` — class-based interceptors from legacy code.
- `withXsrfConfiguration()` and `withNoXsrfProtection()`.
- `withRequestsMadeViaParent()`.
- `withJsonpSupport()` — deprecated as of 22.1, because it is an XSS (cross-site scripting) vector.

Requests are typed by the method's type parameter, not by `as`:

```ts
private readonly http = inject(HttpClient);

// The type describes the parsed response body
readonly tickets$ = this.http.get<readonly Ticket[]>('/api/tickets', {
  params: { status: 'open', page: 1 },   // an object instead of manual string building
  headers: { 'X-Client': 'support-desk' },
  timeout: 10_000,                       // a fetch option, available right here
});
```

Besides `timeout`, a request accepts other modern fetch options: `keepalive`, `cache`, `priority`, `mode`, `redirect`, `credentials`. There is also `transferCache`. It carries an SSR (server-side rendering, drawing pages on the server) response into the browser without repeating the request (chapter 15). And remember: `HttpClient` returns a **cold** Observable. Without a subscription (or without `httpResource`) no request is sent.

### httpResource: fetching data as signals

The v22-stable way to load a screen's data:

```ts
readonly ticketsResource = httpResource<readonly Ticket[]>(
  // a function, not a string: it reads signals and refetches when they change
  () => `/api/tickets?status=${this.status() ?? ''}`,
  { defaultValue: [] },
);

// the template gets state signals
// ticketsResource.value()     — the data
// ticketsResource.isLoading() — a request is in flight
// ticketsResource.error()     — the error
// ticketsResource.status()    — 'idle' | 'loading' | 'reloading' | 'resolved' | 'error'
// ticketsResource.reload()    — force a refresh
```

The core idea: the request is described **reactively**. The URL function (or an `HttpResourceRequest` object) reads signals. When a signal changes, `httpResource` cancels the previous request and issues a new one. The `loading` and `error` flags no longer need duplicating in every component, because they are part of the resource.

Options: `defaultValue`, `parse` (validating/transforming the body, handy with zod), `map`, `equal`, `injector`. For non-JSON there are `httpResource.text()`, `.blob()` and `.arrayBuffer()`. The resource also exposes `headers()`, `statusCode()`, `progress()` and `hasValue()`.

The more general `resource({ params, loader })` is also stable since v22, and it is not tied to HTTP. The `loader` receives `params`, `previous` and an `abortSignal`, so it fits any asynchronous source. Examples: a WebSocket request, IndexedDB, a third-party SDK (software development kit). Both APIs are meant for **reads**, and mutations (POST/PUT/DELETE) stay ordinary `HttpClient` calls.

Five loading approaches, and the first is the default for screen data:

| loading approach | what you get | when to use it |
|---|---|---|
| `httpResource(() => url)` | `value`/`isLoading`/`error` as signals | screen data — the default |
| `resource({ params, loader })` | the same, any async loader | a non-HTTP source, custom fetch |
| `http.get<T>()` + `subscribe` | manual control and teardown | commands: `POST`/`PUT`/`DELETE` |
| `http.get<T>()` + `toSignal` | a signal from an Observable | an RxJS pipeline is needed (ch. 09) |
| `ResolveFn` on a route | data before render | pre-navigation checks (chapter 07) |

### Interceptors

```
      One request through the interceptor chain
┌────────────────────────────────────────────────────┐
│ httpResource(() => url) or http.get<Ticket[]>(url) │
│ the request travels down in withInterceptors order │
└────────────────────────────────────────────────────┘
                           │  req
                           ▼
┌────────────────────────────────────────────────────┐
│ authInterceptor                                    │
│ down: req.clone({ headers: … Bearer token })       │
│ up: 401 → refresh or sign out                      │
└────────────────────────────────────────────────────┘
                           │  req
                           ▼
┌────────────────────────────────────────────────────┐
│ loggingInterceptor                                 │
│ down: start time, method, url                      │
│ up: status code and duration                       │
└────────────────────────────────────────────────────┘
                           │  req
                           ▼
┌────────────────────────────────────────────────────┐
│ errorInterceptor                                   │
│ down: nothing                                      │
│ up: 5xx → retry, then map to a domain error        │
└────────────────────────────────────────────────────┘
                           │  req
                           ▼
┌────────────────────────────────────────────────────┐
│ FetchBackend — the actual fetch()                  │
│ the response travels back up in reverse order      │
└────────────────────────────────────────────────────┘
a request is immutable: change it only through req.clone();
   metadata for interceptors travels in req.context
```

A functional interceptor is a plain function:

```ts
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // interceptors run in an injection context — inject() works
  const token = inject(AuthStore).token();
  if (token === null) return next(req);

  // a request is immutable: modify it only through clone()
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};
```

The order in `withInterceptors([...])` is the order in which the **request** is processed, and the response travels back in reverse. Hence a practical rule in two halves. An interceptor that needs to see the final request — logging, signing — goes later in the array. An interceptor that decides the fate of a response — error handling, retries — is placed so that the error reaches it before anyone else.

Metadata for interceptors travels through `HttpContext` — not through headers and not through flags in a service:

```ts
export const SKIP_AUTH = new HttpContextToken(() => false);

// at the call site
this.http.get('/api/public/status', { context: new HttpContext().set(SKIP_AUTH, true) });

// inside the interceptor
if (req.context.get(SKIP_AUTH)) return next(req);
```

### Errors: what to handle where

Not every error belongs in the same place:

| situation | where to handle it | what the user sees |
|---|---|---|
| 401 Unauthorized | an interceptor | redirect to sign-in |
| 403 Forbidden | an interceptor | a "no access" page |
| 404 for a specific entity | the screen or a resolver | "ticket not found" |
| 422 / validation errors | the form that sent it | messages next to fields |
| 5xx | an interceptor: retry, then a banner | "try again later" |
| network down, timeout | an interceptor | an offline state |

The rule: if the reaction is the same app-wide, it belongs in an interceptor. If it depends on the screen, handle it where the request was made.

An error arrives as an `HttpErrorResponse`. Two cases must be distinguished. With `status === 0` the request never arrived. The cause is no network, a cancellation, or a block by CORS (cross-origin resource sharing — the browser's rules for cross-origin requests). With `status >= 400` the server responded with an error.

Inside an interceptor errors are caught with `catchError`, and retries are done with `retry({ count, delay })`.

### Cancelling requests

Cancellation works through unsubscription: `HttpClient` aborts the request on unsubscribe (with `FetchBackend`, via `AbortController`). Three practical routes:

- **`httpResource`/`resource`** — cancel the previous request themselves when dependencies change; `resource` additionally hands an `abortSignal` to the loader.
- **`switchMap`** — cancels the previous request when a new value arrives: the foundation of live search (chapter 09).
- **`takeUntilDestroyed()`** — ties the subscription to the component's lifetime (chapter 09).

## React parallels

- **`httpResource` ≈ TanStack Query, not `fetch` in `useEffect`.** Both give you `data`/`isLoading`/`error` and refetch when a key changes. The differences are two. `httpResource` does not cache across components and does not deduplicate requests, because there is no shared key-based cache. But it needs no provider and hands you signals directly. Invalidation is simpler and blunter too: `reload()` instead of `invalidateQueries`.
- **Interceptors versus a wrapper around `fetch`.** In React you usually intercept with your own `apiFetch()` or an axios instance with interceptors — and any code calling bare `fetch` bypasses the logic. In Angular the interceptor is built into `HttpClient`. The only way around it is not to use `HttpClient` at all, which makes the auth layer genuinely single.
- **Cancelling requests.** In React cancellation is manual work: an `AbortController` plus cleanup in `useEffect`. In Angular it follows from the model: unsubscribing aborts the request, `switchMap` does it automatically, and `httpResource` does it whenever dependencies change.
- **Where `loading` and `error` live.** In React projects without a library those flags are usually declared by hand in every component. With `httpResource` they become part of the request object, so `isLoading` need not be duplicated in the component. That is what separates modern Angular code from code written three years ago.
- **Where the habit breaks:** `http.get()` with no subscription. A React developer used to `fetch()` as a promise expects the call to have already sent the request. Nothing happens: the Observable is cold, and "the request never fires" is the single most common first problem in an Angular HTTP layer.

## What you will see in legacy code

- **`HttpClientModule` in `imports`** instead of `provideHttpClient()` — the module era. You will not find `withFetch()` next to it, because the transport was XHR (XMLHttpRequest, the browser API that predates `fetch`).
- **Class-based interceptors:** `@Injectable() export class AuthInterceptor implements HttpInterceptor`. Registration goes through a multi provider: `{ provide: HTTP_INTERCEPTORS, useClass: AuthInterceptor, multi: true }` (the `multi` example from chapter 04). For such interceptors to keep working alongside new ones you need `withInterceptorsFromDi()`.
- **Manual `loading`/`error` in every component:** `loading = true` before the call. Then `subscribe({ next, error, complete })` with `loading = false` in two places. And a `cdr.markForCheck()` on top (chapter 03).
- **`BehaviorSubject` plus the `async` pipe as a "cache":** the service stores the last response itself and hands it out through `state$`. Today that is `httpResource` or a signal store (chapter 05).
- **`toPromise()`** (removed in RxJS 8; replaced by `firstValueFrom`/`lastValueFrom`) and `.subscribe()` without teardown in `ngOnInit`.
- **URLs built by string concatenation:** `` `${env.apiUrl}/tickets?status=${status}&page=${page}` `` instead of `params`, which loses escaping. And `environment.ts` as the source of `apiUrl` instead of a DI (dependency injection) token (chapter 04).

## What we add to the project

Support Desk gets a real HTTP layer. That is a `TicketApi` with typed requests and three interceptors: auth, logging, and error handling with retries. The list is loaded through `httpResource` with reactive parameters, and reactions to 401 and 500 are centralized.

## Exercise

**Input:** the project from chapter 07 (routes, stores, in-memory data).
**Output:** data comes from a mock backend and errors are handled at the right level.

Requirements:

1. A mock backend: spin up anything you like — `json-server`, `msw` or a small Express app. It needs four endpoints. Those are `GET /api/tickets` (with `status`, `q`, `page`), `GET /api/tickets/:id`, `POST /api/tickets` and `PATCH /api/tickets/:id`. The base URL comes from `APP_CONFIG` (chapter 04), not from a constant inside the service.
2. `TicketApi`: typed methods `list(params)`, `byId(id)`, `create(dto)`, `patch(id, dto)`. Pass parameters through the `params` object rather than string concatenation. No `any` anywhere.
3. The ticket list is loaded with `httpResource`, and its parameters read from the filter signals. Changing the status or the search string must issue a new request and cancel the previous one. Verify the cancellation in the Network tab.
4. `loading` and `error` in the template come from the resource, not from separate component signals. Distinguish an empty result from an error explicitly.
5. Three interceptors. The `authInterceptor` adds the token and skips requests marked `SKIP_AUTH` via `HttpContext`. The `loggingInterceptor` records the method, URL, status and duration. The `errorInterceptor` retries 5xx, redirects to `/login` on 401, and maps `HttpErrorResponse` into a domain error type. Decide on the order in the array and justify it.
6. Mutations: creating a ticket is a plain `POST` through `HttpClient`, and the list refreshes on success. Decide how exactly — `reload()` on the resource or an optimistic store update — and justify the choice.

Edge cases to think about:

- Why does `this.http.get('/api/tickets')` without a subscription send nothing, and what does that look like while debugging?
- What does `httpResource` hold between a filter change and the new response: the old data, `undefined`, or `defaultValue`?
- `errorInterceptor` does `retry({ count: 2 })`. What happens to a `POST` that the server already processed?
- What does an error with `status === 0` mean, and why must it not be shown as "server error"?
- The token is refreshed inside `authInterceptor` on a 401. What happens when five requests get a 401 simultaneously?

## Solution walkthrough

`src/app/tickets/ticket-api.ts`:

```ts
import { HttpClient, HttpContext, httpResource } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { APP_CONFIG } from '../core/app-config';
import { SKIP_AUTH } from '../core/http-context';
import { Ticket, TicketStatus } from './ticket';

export interface TicketListParams {
  readonly status?: TicketStatus | null;
  readonly q?: string;
  readonly page?: number;
}

@Service()
export class TicketApi {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(APP_CONFIG).apiUrl;

  // The generic describes the parsed body — no `as Ticket[]` anywhere
  list(params: TicketListParams) {
    return this.http.get<readonly Ticket[]>(`${this.baseUrl}/tickets`, {
      // the params object: Angular escapes values and drops undefined for you
      params: {
        ...(params.status ? { status: params.status } : {}),
        ...(params.q ? { q: params.q } : {}),
        page: params.page ?? 1,
      },
      timeout: 10_000, // a fetch option on the request, no RxJS operator needed
    });
  }

  byId(id: number) {
    return this.http.get<Ticket>(`${this.baseUrl}/tickets/${id}`);
  }

  create(dto: Omit<Ticket, 'id' | 'createdAt'>) {
    return this.http.post<Ticket>(`${this.baseUrl}/tickets`, dto);
  }

  patch(id: number, dto: Partial<Omit<Ticket, 'id'>>) {
    return this.http.patch<Ticket>(`${this.baseUrl}/tickets/${id}`, dto);
  }

  // a public endpoint: marked through the context so authInterceptor skips it
  status() {
    return this.http.get<{ ok: boolean }>(`${this.baseUrl}/public/status`, {
      context: new HttpContext().set(SKIP_AUTH, true),
    });
  }
}
```

`src/app/core/http-context.ts`:

```ts
import { HttpContextToken } from '@angular/common/http';

// Per-request metadata for interceptors: not a header (that would go to the
// server) and not a global flag in a service (that is not tied to a request)
export const SKIP_AUTH = new HttpContextToken(() => false);
export const SKIP_RETRY = new HttpContextToken(() => false);
```

`src/app/core/interceptors.ts`:

```ts
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, retry, tap, throwError, timer } from 'rxjs';
import { AuthStore } from './auth-store';
import { SKIP_AUTH, SKIP_RETRY } from './http-context';
import { Notifications } from './notifications';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // interceptors run in an injection context
  const token = inject(AuthStore).token();

  // the request context instead of a "list of public URLs" inside the interceptor
  if (req.context.get(SKIP_AUTH) || token === null) return next(req);

  // req is immutable: the only way to change it is clone()
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};

export const loggingInterceptor: HttpInterceptorFn = (req, next) => {
  const startedAt = performance.now();

  return next(req).pipe(
    tap({
      // the request that reaches here is already modified: this interceptor
      // sits after authInterceptor, so it sees the final headers
      next: (event) => {
        if (event.type !== 4 /* HttpEventType.Response */) return;
        const ms = Math.round(performance.now() - startedAt);
        console.debug(`${req.method} ${req.urlWithParams} → ${event.status} (${ms}ms)`);
      },
      error: (error: HttpErrorResponse) => {
        const ms = Math.round(performance.now() - startedAt);
        console.warn(`${req.method} ${req.urlWithParams} → ${error.status} (${ms}ms)`);
      },
    }),
  );
};

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const auth = inject(AuthStore);
  const notifications = inject(Notifications);

  return next(req).pipe(
    // Retry only idempotent methods: a POST must not be retried, the server
    // may have created the entity while the response got lost on the way
    retry({
      count: req.method === 'GET' && !req.context.get(SKIP_RETRY) ? 2 : 0,
      delay: (error: HttpErrorResponse, retryCount) =>
        error.status >= 500 || error.status === 0
          ? timer(retryCount * 500) // linear backoff
          : throwError(() => error), // retrying a 4xx is pointless
    }),
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401) {
        auth.signOut();
        void router.navigate(['/login'], { queryParams: { returnTo: router.url } });
      } else if (error.status === 403) {
        void router.navigate(['/forbidden']);
      } else if (error.status === 0) {
        // status 0 — the request never arrived: network, CORS or cancellation.
        // This is not a server error, and the wording must differ
        notifications.show('No connection to the server');
      } else if (error.status >= 500) {
        notifications.show('Something went wrong. Please try again later.');
      }

      // 404 and 422 are left alone: the screen or the form handles them,
      // because the reaction depends on context rather than on the status code
      return throwError(() => error);
    }),
  );
};
```

`src/app/app.config.ts`:

```ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    // withFetch() is not needed here: FetchBackend is the default transport
    // and the flag itself is deprecated
    provideHttpClient(
      // The order is the order the request is processed in (responses go back
      // in reverse). auth first — so the others see the final headers;
      // error last — so an error reaches it before it reaches the caller
      withInterceptors([authInterceptor, loggingInterceptor, errorInterceptor]),
    ),
    ...provideAppConfig({ apiUrl: '/api' }),
  ],
};
```

`src/app/tickets/ticket-board-state.ts` — loading through `httpResource`:

```ts
@Service({ autoProvided: false })
export class TicketBoardState {
  private readonly config = inject(APP_CONFIG);

  private readonly statusFilter = signal<TicketStatus | null>(null);
  private readonly searchQuery = signal('');

  readonly status = this.statusFilter.asReadonly();
  readonly search = this.searchQuery.asReadonly();

  // A reactive request: the function reads signals, so on a filter change
  // httpResource cancels the previous request and issues a new one itself
  private readonly ticketsResource = httpResource<readonly Ticket[]>(
    () => ({
      url: `${this.config.apiUrl}/tickets`,
      params: {
        ...(this.statusFilter() ? { status: this.statusFilter()! } : {}),
        ...(this.searchQuery() ? { q: this.searchQuery() } : {}),
      },
    }),
    { defaultValue: [] },
  );

  // Only the resource's state signals go out; the component no longer
  // declares loading/error of its own
  readonly tickets = this.ticketsResource.value;
  readonly isLoading = this.ticketsResource.isLoading;
  readonly error = this.ticketsResource.error;
  readonly isEmpty = computed(
    () => !this.isLoading() && this.error() === undefined && this.tickets().length === 0,
  );

  setStatus(status: TicketStatus | null): void {
    this.statusFilter.set(status);
  }

  setSearch(query: string): void {
    this.searchQuery.set(query);
  }

  reload(): void {
    this.ticketsResource.reload();
  }
}
```

The template distinguishes three states explicitly:

```html
@if (board.isLoading()) {
  <p class="ticket-list__status">Loading…</p>
} @else if (board.error()) {
  <p class="ticket-list__status ticket-list__status--error">
    Could not load tickets.
    <button type="button" (click)="board.reload()">Retry</button>
  </p>
} @else {
  <ul class="ticket-list__items">
    @for (ticket of board.tickets(); track ticket.id) {
      <li><app-ticket-card [ticket]="ticket" /></li>
    } @empty {
      <li class="ticket-list__empty">No tickets match the filter</li>
    }
  </ul>
}
```

A mutation is a plain `HttpClient` call, and the resource refreshes on success:

```ts
export class TicketForm {
  private readonly api = inject(TicketApi);
  private readonly board = inject(TicketBoardState);
  private readonly router = inject(Router);

  protected save(dto: Omit<Ticket, 'id' | 'createdAt'>): void {
    // httpResource is meant for reads; creation is a plain POST.
    // takeUntilDestroyed is not required — subscribe completes on response —
    // but if the user leaves earlier, aborting is better (chapter 09)
    this.api.create(dto).subscribe({
      next: () => {
        // reload() instead of inserting into the list by hand: the server is
        // the source of truth, and this avoids drift (id, createdAt, validation)
        this.board.reload();
        void this.router.navigate(['/tickets']);
      },
      // a 422 is handled here: the reaction belongs to this form,
      // not to the application as a whole
      error: (error: HttpErrorResponse) => {
        if (error.status === 422) this.applyServerValidation(error.error);
      },
    });
  }
}
```

Answers to the edge cases:

- `HttpClient` returns a **cold** Observable: the request goes out when you subscribe. Without `subscribe()`, `httpResource` or `firstValueFrom` nothing happens — the Network tab stays empty and the console is silent. That is exactly why the symptom sounds like "the method is called but there is no request".
- While the new request is in flight, `value()` keeps the **previous value** (or `defaultValue` if there was none), `status()` becomes `'reloading'` and `isLoading()` becomes `true`. That is convenient: the list does not flash empty on a filter change. If you want the opposite, render a skeleton based on `isLoading()`.
- Retrying a `POST` may create a second entity: the server could have processed the request and failed to deliver the response. That is why the solution enables `retry` for `GET` only. Mutations are either not retried at all, or the server has to support an idempotency key.
- `status === 0` means there was no HTTP response at all: no network, the request was blocked by CORS, or the subscription was cancelled. Showing "server error" is doubly wrong. The server may have been fine, and the cause is on the client. The user also needs different advice — "check your connection" rather than "try again later".
- Five parallel 401s with no protection produce five refresh requests. Four of them will most likely fail, because a refresh token is single-use, and the user gets signed out. The fix is one shared refresh Observable in the service, reused for all waiting requests. Implement it with `shareReplay` plus a "refresh already in progress" flag, and retry the rest once it resolves.

## Check yourself

1. Why does calling `http.get()` not send a request by itself, and what three ways of "activating" it do you know?
2. What is `httpResource` and how does it differ from "`http.get` plus two signals for loading and error"? What happens to the data when a dependency changes?
3. Interceptor order in `withInterceptors([a, b, c])`: in what order do they process the request, and in what order the response? Where do you put the error handler and why?
4. Why does `HttpContext` exist if you could pass a header or check the URL inside the interceptor?
5. What tells you whether to handle an error in an interceptor or in the component? Give two examples of each.

<details>
<summary>Answers</summary>

1. `HttpClient` returns a cold Observable: it describes the request but does not perform it. The request is sent on subscription, and each subscription sends a **new** one. There are three ways to activate it. The first is `subscribe()`, usually for mutations. The second is `httpResource`/`resource` for screen data: they subscribe themselves and expose state as signals. The third is `firstValueFrom`/`lastValueFrom`, when a promise is genuinely needed — in an `async` guard, for example. The upside of coldness is free cancellation: unsubscribing aborts the request.
2. `httpResource` is a reactive wrapper around a request. The URL or request object is a function that reads signals. The state is available as `value()`, `isLoading()`, `error()` and `status()`, plus `reload()`. The difference from the manual pair is that loading state stops being component code. There is no `loading = true` before the call, no resetting it in two branches, and nothing to remember about `markForCheck`. When a dependency changes, the resource cancels the previous request and issues a new one. Meanwhile `value()` keeps the previous value and `status()` becomes `'reloading'`, so the UI (user interface) does not flash empty.
3. The request flows in declaration order: `a → b → c → backend`. The response (and any error) travels back in reverse: `c → b → a`. The error handler logically goes last in the array. On the response path it then gets control **first**, so it can decide the error's fate before anyone else sees it — including the caller. Deciding means retrying, turning the error into a redirect, or showing a banner. Interceptors that need the final request — logging, signing, metrics — go after those that modify it.
4. `HttpContext` is a way to pass metadata about **one specific request** to the interceptors without sending anything over the network. A header does not fit: it would travel to the server and become part of the protocol (and sometimes trigger a preflight). Checking the URL inside the interceptor is a brittle coupling. The list of public paths lives far from the call site, breaks when API routes are refactored, and does not express intent. With an `HttpContextToken` the intent is visible where the call happens: `context.set(SKIP_AUTH, true)`. The value is typed and has a default, and the interceptor simply reads `req.context.get(...)`.
5. The criterion is whether the reaction depends on the screen. If it is the same application-wide, handle it in an interceptor. That covers 401 (sign out and redirect to login) and 403 (an "access denied" page). It also covers 5xx (retry plus a generic banner) and `status === 0` (an offline state). If the reaction depends on context, handle it where the request was made. A 404 for a specific entity belongs to the screen, which shows "ticket not found" rather than a generic banner. A 422 with validation errors belongs to the form, because the messages must appear next to its fields. A 409 version conflict belongs to the screen too, which offers to reload the data. The practical test: if producing the right message requires knowing which screen made the request, it is not the interceptor's job.

</details>

## Common mistake

The first one is `http.get()` with no subscription. The code looks functional: the service method is called, the return type satisfies the compiler, there are no errors. But `HttpClient` returns a cold Observable, so nothing happens: the Network tab is empty and the console is silent.

For a React developer this mistake is nearly inevitable, because `fetch()` is a promise that starts work immediately and `await` merely waits for the result. The symptom is easy to recognize. It sounds like this: "the service is called, I put a `console.log` in the method and it prints, but there is no request".

The cure: fetch screen data through `httpResource` (it subscribes itself), send mutations through `subscribe()`, and reserve `firstValueFrom` for the places that genuinely need a promise.

The second is duplicating loading state. The component declares `loading = signal(false)` and `error = signal<string|null>(null)` while a resource sitting next to it already exposes `isLoading()` and `error()`.

The two sets then drift apart. Nobody reset `loading` in the error branch, and nobody cleared `error` before the retry. The user ends up with a spinner on top of an error message. The same goes for data: a copy of the response in the component's own signal lives its own life after `reload()`.

The rule is the one from chapter 05. State that can be read is read rather than copied — `resource.value()`, `resource.isLoading()`, `resource.error()` — and everything derived is a `computed`.
