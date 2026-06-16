# Interceptors Deep Dive

## What an Interceptor is and why it uses RxJS

An Interceptor implements the `NestInterceptor` interface with an `intercept(context, next)` method. `next.handle()` returns an `Observable<any>` — the stream of the controller's response. RxJS operators (`map`, `tap`, `catchError`, `switchMap`) allow transforming that stream before, after, or instead of the controller executing.

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
  Middleware → Guard → Interceptor.before → Pipe → Controller → Interceptor.after → Response

Interceptor.before: code BEFORE next.handle()
Interceptor.after:  operators in .pipe() AFTER next.handle()
```

## Response Transformation — standardizing responses

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
// Client receives: { success: true, data: { id: 1, name: 'Alice' }, timestamp: '...', path: '/users/1' }
```

## Cache Interceptor — bypassing the controller

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

## Error Transformation Interceptor

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

## Timeout Interceptor

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

## Interceptor vs Middleware vs Guard vs Pipe

```txt
                  Middleware    Guard       Pipe        Interceptor
Handler access:      No          Yes         Yes          Yes
Metadata access:     No          Yes         No           Yes
Can block:           Yes (next)  Yes (false) Yes (throw)  Yes (of())
Response access:     No          No          No           Yes (.pipe())
Response transform:  No          No          No           Yes (map())
RxJS Observable:     No          No          No           Yes
Position:            Before all  Guards→     Pipes→       Around Controller

Middleware:    Express-compatible, no knowledge of the Nest context
Guard:         Authorization — allow or deny
Pipe:          Transform/validate incoming data
Interceptor:   Transform response, logging, caching
```

## Common interview mistakes

- **"An Interceptor runs code before and after synchronously"** — before the controller: synchronously (before `next.handle()`). After: asynchronously via RxJS operators in `.pipe()`. `tap` executes when the Observable completes, not when the Interceptor returns its result.

- **"next.handle() calls the controller immediately"** — no. `next.handle()` creates a "cold" Observable. The controller is invoked only when someone subscribes. If you return `of(cached)` instead of `next.handle()`, the controller is never called at all.

- **"An Interceptor can read the request body"** — yes, via `context.switchToHttp().getRequest().body`. But transforming incoming data is the job of a Pipe, not an Interceptor. Interceptors are designed to transform the RESPONSE.

- **"An Interceptor and Middleware do the same thing"** — no. Middleware operates at the Express/Fastify level before Nest routing; it doesn't know which handler will be called and has no access to Nest metadata. An Interceptor works inside the Nest pipeline, knows the handler and controller, and can read metadata via ExecutionContext.

- **"useGlobalInterceptors() and APP_INTERCEPTOR do the same thing"** — there is a difference. `useGlobalInterceptors()` in `main.ts` is outside the DI container and cannot use injected dependencies (it needs `new MyInterceptor()`). `{ provide: APP_INTERCEPTOR, useClass: MyInterceptor }` in a module goes through DI and can inject services.
