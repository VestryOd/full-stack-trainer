# Interceptors Deep Dive

## Что такое Interceptor и почему он использует RxJS

Interceptor реализует интерфейс `NestInterceptor` с методом `intercept(context, next)`. `next.handle()` возвращает `Observable<any>` — поток ответа контроллера. RxJS операторы (`map`, `tap`, `catchError`, `switchMap`) позволяют трансформировать этот поток до, после или вместо выполнения контроллера.

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

    // Код до контроллера — выполняется синхронно перед next.handle()
    console.log(`→ ${method} ${url}`);

    return next.handle().pipe(
      // Код после контроллера — выполняется когда Observable завершается
      tap(() => console.log(`← ${method} ${url} ${Date.now() - startTime}ms`)),
    );
  }
}
```

```txt
Request pipeline:
  Middleware → Guard → Interceptor.before → Pipe → Controller → Interceptor.after → Response

Interceptor.before: код ПЕРЕД next.handle()
Interceptor.after:  операторы в .pipe() ПОСЛЕ next.handle()
```

## Response Transformation — стандартизация ответов

```typescript
// Оборачивать все ответы в { success, data, timestamp }
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

// Применить глобально в main.ts:
app.useGlobalInterceptors(new TransformInterceptor());

// Результат: контроллер возвращает { id: 1, name: 'Alice' }
// Клиент получает: { success: true, data: { id: 1, name: 'Alice' }, timestamp: '...', path: '/users/1' }
```

## Cache Interceptor — обойти контроллер

```typescript
// Вернуть of(cachedData) — контроллер НЕ вызывается
@Injectable()
export class CacheInterceptor implements NestInterceptor {
  constructor(private readonly cacheService: CacheService) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const req = context.switchToHttp().getRequest();
    const cacheKey = `cache:${req.method}:${req.url}`;

    return from(this.cacheService.get(cacheKey)).pipe(
      switchMap(cached => {
        if (cached) {
          return of(cached); // вернуть из кеша — next.handle() НЕ вызывается
        }

        return next.handle().pipe(
          tap(response => {
            this.cacheService.set(cacheKey, response, 60); // кешировать на 60 сек
          }),
        );
      }),
    );
  }
}
```

## Error Transformation Interceptor

```typescript
// Трансформировать внутренние ошибки в стандартный формат
@Injectable()
export class ErrorInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    return next.handle().pipe(
      catchError(err => {
        // Трансформировать Prisma ошибки в HTTP ошибки
        if (err.code === 'P2002') { // unique constraint
          throw new ConflictException('Resource already exists');
        }
        if (err.code === 'P2025') { // record not found
          throw new NotFoundException('Resource not found');
        }
        throw err; // пробросить остальные ошибки без изменений
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
      timeout(5000), // 5 секунд
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
Доступ к handler:    Нет         Да          Да           Да
Доступ к metadata:   Нет         Да          Нет          Да
Может блокировать:   Да (next)   Да (false)  Да (throw)   Да (of())
Доступ к response:   Нет         Нет         Нет          Да (.pipe())
Трансформ. response: Нет         Нет         Нет          Да (map())
RxJS Observable:     Нет         Нет         Нет          Да
Позиция:             Раньше всех Guards→     Pipes→       Вокруг Controller
                                Guards       Controller

Middleware:    Express-совместимый, без знания Nest контекста
Guard:         Авторизация — пропустить или запретить
Pipe:          Трансформировать/валидировать входные данные
Interceptor:   Трансформировать ответ, логировать, кешировать
```

## Типичные ошибки на интервью

- **"Interceptor выполняет код до и после синхронно"** — до контроллера: синхронно (перед `next.handle()`). После: асинхронно через RxJS операторы в `.pipe()`. `tap` выполняется когда Observable завершается, не когда Interceptor возвращает результат.

- **"next.handle() вызывает контроллер немедленно"** — нет. `next.handle()` создаёт "холодный" Observable. Контроллер вызывается только когда кто-то подписывается (subscribe). Если вернуть `of(cached)` вместо `next.handle()` — контроллер вообще не вызывается.

- **"Interceptor может читать тело запроса"** — да, через `context.switchToHttp().getRequest().body`. Но трансформировать входные данные — задача Pipe, не Interceptor. Interceptor предназначен для трансформации ОТВЕТА.

- **"Interceptor и Middleware делают одно и то же"** — нет. Middleware работает на уровне Express/Fastify до Nest routing, не знает какой handler будет вызван, не имеет доступа к Nest metadata. Interceptor работает внутри Nest pipeline, знает handler, controller, может читать metadata через ExecutionContext.

- **"Глобальный Interceptor через useGlobalInterceptors() и APP_INTERCEPTOR делают одно и то же"** — есть разница. `useGlobalInterceptors()` в `main.ts` — вне DI контейнера, не может использовать инжектированные зависимости (new MyInterceptor()). `{ provide: APP_INTERCEPTOR, useClass: MyInterceptor }` в модуле — через DI, может инжектировать сервисы.
