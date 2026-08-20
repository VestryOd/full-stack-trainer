# Interceptors: подробный разбор

## Что такое Interceptor и почему он работает через RxJS

Interceptor — это класс, который оборачивает вызов обработчика запроса. Он реализует интерфейс `NestInterceptor` с единственным методом `intercept(context, next)`.

Ключевая деталь: `next.handle()` — это ещё не вызов контроллера, а обещание его вызвать. Технически это Observable — поток значений из библиотеки RxJS. Поток «холодный»: контроллер запустится только тогда, когда на поток кто-то подпишется, и подписывается сам Nest.

Отсюда три возможности. Сделать что-то до `next.handle()`. Навесить обработку на результат через `.pipe(...)`. Или вообще не вызывать `next.handle()` и вернуть свой поток.

Обработку навешивают операторами RxJS, и дальше в статье будет пример на каждый:

- `map` меняет значение в потоке.
- `tap` смотрит на значение и ничего не меняет.
- `catchError` перехватывает ошибку.
- `switchMap` подменяет один поток другим.

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
Порядок обработки запроса:
  Middleware → Guard → Interceptor.before → Pipe
    → Controller → Interceptor.after → Response

Interceptor.before: код до next.handle()
Interceptor.after:  операторы в .pipe() после next.handle()
```

## Трансформация ответа — единый формат для всех эндпоинтов

Оператор `map` меняет значение, которое контроллер вернул, по пути к клиенту. Самое частое применение — обернуть любой ответ в общий конверт вида `{ success, data, timestamp, path }`.

Выгода в том, что контроллеры остаются чистыми: каждый возвращает свои данные и ничего не знает про формат ответа API.

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
// Клиент получает:
// { success: true, data: { id: 1, name: 'Alice' },
//   timestamp: '...', path: '/users/1' }
```

## Кеширующий Interceptor — как обойти контроллер

Здесь работает «холодность» потока. Если вместо `next.handle()` вернуть `of(cached)`, подписки на поток контроллера не будет, и контроллер не выполнится вообще.

Здесь `from(...)` превращает промис от кеша в поток. Дальше `switchMap` выбирает, какой поток отдать: значение из кеша или поток контроллера с сохранением результата через `tap`.

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

## Interceptor, переводящий чужие ошибки в HTTP-ответы

`catchError` перехватывает ошибку, которая пришла из контроллера, и решает её судьбу: пробросить как есть или заменить на другую.

Типичная задача — превратить коды драйвера базы данных в осмысленные HTTP-исключения. Читателю ответа не нужно знать, что `P2002` у Prisma означает нарушение уникальности.

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

## Interceptor с таймаутом

Оператор `timeout(5000)` даёт потоку пять секунд и, если ответа нет, выбрасывает `TimeoutError`. Дальше `catchError` ловит эту ошибку и подменяет её на HTTP-исключение 408.

Без такого перехвата клиент увидит внутреннюю ошибку RxJS вместо понятного кода ответа.

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

## Interceptor против Middleware, Guard и Pipe

Все четыре механизма встраиваются в обработку запроса, но умеют разное. Interceptor — единственный, кто видит и меняет ответ.

| Что умеет | Middleware | Guard | Pipe | Interceptor |
|---|---|---|---|---|
| Доступ к обработчику | Нет | Да | Да | Да |
| Доступ к метаданным | Нет | Да | Нет | Да |
| Может остановить запрос | Да (`next`) | Да (`false`) | Да (`throw`) | Да (`of()`) |
| Доступ к ответу | Нет | Нет | Нет | Да (`.pipe()`) |
| Меняет ответ | Нет | Нет | Нет | Да (`map()`) |
| Работает с Observable | Нет | Нет | Нет | Да |
| Место в конвейере | Раньше всех | После middleware | После guards, до контроллера | Вокруг контроллера |

Зона ответственности у каждого своя:

- **Middleware** — уровень Express/Fastify, про контекст Nest ничего не знает.
- **Guard** — авторизация: пропустить запрос или запретить.
- **Pipe** — проверить и преобразовать входные данные.
- **Interceptor** — изменить ответ, залогировать, закешировать.

## Типичные ошибки на интервью

- **"Interceptor выполняет код до и после синхронно"** — только первую половину. До контроллера код идёт синхронно, прямо перед `next.handle()`. После — асинхронно, операторами внутри `.pipe()`. `tap` срабатывает, когда поток завершился, а не когда `intercept` вернул результат.

- **"next.handle() вызывает контроллер немедленно"** — нет. `next.handle()` создаёт «холодный» Observable, и контроллер вызывается только при подписке. Верните `of(cached)` вместо `next.handle()` — и контроллер не выполнится ни разу.

- **"Interceptor может читать тело запроса"** — может, через `context.switchToHttp().getRequest().body`. Но менять входные данные — работа Pipe. Interceptor придуман для **ответа**.

- **"Interceptor и Middleware делают одно и то же"** — нет. Middleware работает на уровне Express/Fastify, до маршрутизации Nest: он не знает, какой обработчик будет вызван, и не видит метаданные декораторов. Interceptor работает внутри конвейера Nest и через `ExecutionContext` знает и обработчик, и контроллер, и метаданные.

- **"useGlobalInterceptors() и APP_INTERCEPTOR — одно и то же"** — разница есть, и она в зависимостях. Вызов в `main.ts` создаёт объект руками, через `new MyInterceptor()`, вне контейнера внедрения зависимостей (DI). Инжектировать в него ничего нельзя. Запись `{ provide: APP_INTERCEPTOR, useClass: MyInterceptor }` в модуле идёт через контейнер, и зависимости приходят обычным способом.
