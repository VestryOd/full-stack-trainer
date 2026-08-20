# Interceptors Deep Dive

## What an Interceptor is and why it works through RxJS

An Interceptor is a class that wraps the call to a request handler. It implements the `NestInterceptor` interface with a single method, `intercept(context, next)`.

The key detail: `next.handle()` is not the controller call yet, it is a promise to make that call. Technically it is an Observable — a stream of values from the RxJS library. The stream is "cold": the controller only starts once something subscribes to the stream, and Nest is what subscribes.

That gives you three options. Do something before `next.handle()`. Attach processing to the result through `.pipe(...)`. Or never call `next.handle()` at all and return your own stream.

The processing is attached with RxJS operators, and the rest of the article gives one example of each:

- `map` changes the value in the stream.
- `tap` looks at the value and changes nothing.
- `catchError` catches an error.
- `switchMap` swaps one stream for another.

```typescript
import { Injectable, NestInterceptor, ExecutionContext, CallHandler } from '@nestjs/common';
import { Observable } from 'rxjs';
import { map, tap, catchError } from 'rxjs/operators';

@Injectable()
export class LoggingInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const req = context.switchToHttp().getRequest();
    const { method, url } = req;
    const startTime = Date.now();

    // Code before the controller — runs synchronously before next.handle()
    console.log(`→ ${method} ${url}`);

    return next.handle().pipe(
      // Code after the controller — runs when the Observable completes
      tap(() => console.log(`← ${method} ${url} ${Date.now() - startTime}ms`)),
    );
  }
}
```

```txt
Request pipeline:
  Middleware → Guard → Interceptor.before → Pipe
    → Controller → Interceptor.after → Response

Interceptor.before: code before next.handle()
Interceptor.after:  operators in .pipe() after next.handle()
```

## Response transformation — one format for every endpoint

The `map` operator changes the value the controller returned on its way to the client. The most common use is wrapping every response in a shared envelope shaped like `{ success, data, timestamp, path }`.

The payoff is clean controllers: each one returns its own data and knows nothing about the API response format.

```typescript
// Wrap all responses in { success, data, timestamp }
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  timestamp: string;
  path: string;
}

@Injectable()
export class TransformInterceptor<T> implements NestInterceptor<T, ApiResponse<T>> {
  intercept(context: ExecutionContext, next: CallHandler<T>): Observable<ApiResponse<T>> {
    const req = context.switchToHttp().getRequest();

    return next.handle().pipe(
      map(data => ({
        success: true,
        data,
        timestamp: new Date().toISOString(),
        path: req.url,
      })),
    );
  }
}

// Apply globally in main.ts:
app.useGlobalInterceptors(new TransformInterceptor());

// Result: controller returns { id: 1, name: 'Alice' }
// Client receives:
// { success: true, data: { id: 1, name: 'Alice' },
//   timestamp: '...', path: '/users/1' }
```

## Cache Interceptor — how to bypass the controller

This is where the "cold" stream matters. Return `of(cached)` instead of `next.handle()`, and nothing ever subscribes to the controller's stream, so the controller does not run.

Here `from(...)` turns the cache promise into a stream. Then `switchMap` decides which stream to pass on. Either the cached value, or the controller's stream with a `tap` that stores the result in the cache.

```typescript
// Returning of(cachedData) — the controller is NOT called
@Injectable()
export class CacheInterceptor implements NestInterceptor {
  constructor(private readonly cacheService: CacheService) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const req = context.switchToHttp().getRequest();
    const cacheKey = `cache:${req.method}:${req.url}`;

    return from(this.cacheService.get(cacheKey)).pipe(
      switchMap(cached => {
        if (cached) {
          return of(cached); // return from cache — next.handle() is NOT called
        }

        return next.handle().pipe(
          tap(response => {
            this.cacheService.set(cacheKey, response, 60); // cache for 60 sec
          }),
        );
      }),
    );
  }
}
```

## An Interceptor that turns library errors into HTTP responses

`catchError` intercepts an error coming from the controller and decides its fate: rethrow it as is, or replace it with another one.

The typical job is turning database driver codes into meaningful HTTP exceptions. Whoever reads the response does not need to know that Prisma's `P2002` means a unique constraint violation.

```typescript
// Transform internal errors into a standard format
@Injectable()
export class ErrorInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    return next.handle().pipe(
      catchError(err => {
        // Transform Prisma errors into HTTP errors
        if (err.code === 'P2002') { // unique constraint
          throw new ConflictException('Resource already exists');
        }
        if (err.code === 'P2025') { // record not found
          throw new NotFoundException('Resource not found');
        }
        throw err; // rethrow everything else unchanged
      }),
    );
  }
}
```

## An Interceptor with a timeout

The `timeout(5000)` operator gives the stream five seconds and throws a `TimeoutError` if no response arrives. Then `catchError` picks that error up and replaces it with a 408 HTTP exception.

Without that step the client sees an internal RxJS error instead of a clear status code.

```typescript
import { TimeoutError, throwError } from 'rxjs';
import { timeout, catchError } from 'rxjs/operators';

@Injectable()
export class TimeoutInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    return next.handle().pipe(
      timeout(5000), // 5 seconds
      catchError(err => {
        if (err instanceof TimeoutError) {
          throw new RequestTimeoutException('Request took too long');
        }
        throw err;
      }),
    );
  }
}
```

## Interceptor versus Middleware, Guard and Pipe

All four mechanisms plug into request handling, but they can do different things. The Interceptor is the only one that sees and changes the response.

| Capability | Middleware | Guard | Pipe | Interceptor |
|---|---|---|---|---|
| Handler access | No | Yes | Yes | Yes |
| Metadata access | No | Yes | No | Yes |
| Can stop the request | Yes (`next`) | Yes (`false`) | Yes (`throw`) | Yes (`of()`) |
| Response access | No | No | No | Yes (`.pipe()`) |
| Changes the response | No | No | No | Yes (`map()`) |
| Works with Observables | No | No | No | Yes |
| Place in the pipeline | Before everything | After middleware | After guards, before the controller | Around the controller |

Each one owns a different job:

- **Middleware** — the Express/Fastify level, with no knowledge of the Nest context.
- **Guard** — authorization: let the request through or deny it.
- **Pipe** — validate and convert the incoming data.
- **Interceptor** — change the response, log it, cache it.

## Common interview mistakes

- **"An Interceptor runs code before and after synchronously"** — only the first half is true. Before the controller the code runs synchronously, right before `next.handle()`. After it, the work happens through operators inside `.pipe()`. `tap` fires when the stream completes, not when `intercept` returns.

- **"next.handle() calls the controller immediately"** — no. `next.handle()` creates a "cold" Observable, and the controller is invoked only on subscribe. Return `of(cached)` instead of `next.handle()` and the controller never runs.

- **"An Interceptor can read the request body"** — it can, via `context.switchToHttp().getRequest().body`. But changing incoming data is a Pipe's job. Interceptors exist for the **response**.

- **"An Interceptor and Middleware do the same thing"** — no. Middleware works at the Express/Fastify level, before Nest routing: it does not know which handler will run and cannot see decorator metadata. An Interceptor works inside the Nest pipeline and, through `ExecutionContext`, knows the handler, the controller and the metadata.

- **"useGlobalInterceptors() and APP_INTERCEPTOR do the same thing"** — there is a difference, and it is about dependencies. The call in `main.ts` builds the object by hand, with `new MyInterceptor()`, outside the dependency injection (DI) container. Nothing can be injected into it. The `{ provide: APP_INTERCEPTOR, useClass: MyInterceptor }` form in a module goes through the container, and dependencies arrive the usual way.
