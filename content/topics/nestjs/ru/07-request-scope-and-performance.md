# Область видимости REQUEST и производительность

## Распространение области видимости — самый важный эффект

Когда провайдер получает область видимости `Scope.REQUEST`, Nest обязан собирать для каждого запроса новое дерево зависимостей. Затрагивает это не только сам провайдер: все, кто от него зависит, тоже становятся REQUEST-провайдерами. Этот эффект называют всплытием области видимости (scope bubble up).

```typescript
// Пример scope propagation:
@Injectable({ scope: Scope.REQUEST })
export class RequestContextService {
  // Singleton - нет
  // Этот провайдер REQUEST-scoped
}

@Injectable() // был Singleton
export class UserService {
  constructor(private context: RequestContextService) {}
  // ⚠️ Теперь тоже REQUEST-scoped из-за зависимости!
}

@Injectable() // был Singleton
export class OrderService {
  constructor(private users: UserService) {}
  // ⚠️ Тоже REQUEST-scoped (транзитивно)!
}

// Результат: цепочка RequestContext → UserService → OrderService
// Создаётся заново на КАЖДЫЙ запрос
```

```txt
Правило распространения области видимости:
  Singleton может зависеть от Singleton ✓
  Singleton НЕ МОЖЕТ зависеть от REQUEST (сам станет REQUEST) ⚠️
  REQUEST может зависеть от Singleton ✓
  REQUEST может зависеть от REQUEST ✓
  TRANSIENT — новый экземпляр на каждую инъекцию,
    независимо от области видимости остальных
```

## Производительность — измеримые издержки

Цена области REQUEST измерима, и это цена создания объектов. Возьмите 1000 RPS (requests per second — запросов в секунду) и цепочку из пяти REQUEST-провайдеров. Получится 5000 новых объектов в секунду, и все они достанутся сборщику мусора (GC, garbage collector).

Порядок величин и инструменты замера — ниже. Встроенного профилировщика в NestJS нет, поэтому берут внешние.

```typescript
// При 1000 RPS и цепочке из 5 REQUEST-scoped провайдеров:
// 1000 запросов × 5 объектов = 5000 новых объектов/сек
// Каждый объект: TypeScript instantiation + DI injection + GC давление

// Benchmark (примерные числа):
// Singleton: 0.01ms overhead per request (lookup из container)
// Request scope: 0.1-0.5ms overhead per request (instantiation + GC)
// На 1000 RPS: 100-500ms потеряно только на scope overhead

// Профилирование:
// - clinic.js (flamegraph)
// - @nestjs/terminus для health metrics
// - pino/winston для request timing
```

## AsyncLocalStorage — альтернатива без накладных расходов

`AsyncLocalStorage` — встроенный в Node.js механизм, который привязывает данные к цепочке асинхронных вызовов. Дальше по тексту — сокращённо ALS (AsyncLocalStorage).

Схема такая: сервис остаётся Singleton, а данные запроса лежат в хранилище ALS. Middleware один раз открывает контекст для запроса, и любой асинхронный вызов внутри этого запроса видит те же данные. Новые провайдеры при этом не создаются, значит и всплытия области видимости не происходит.

```typescript
// Node.js встроенный механизм для request-scoped данных БЕЗ создания новых провайдеров
import { AsyncLocalStorage } from 'async_hooks';

// request-context.service.ts — SINGLETON, данные хранятся в ALS
@Injectable()
export class RequestContextService {
  private readonly storage = new AsyncLocalStorage<Map<string, unknown>>();

  run(store: Map<string, unknown>, callback: () => void) {
    this.storage.run(store, callback);
  }

  get<T>(key: string): T | undefined {
    return this.storage.getStore()?.get(key) as T;
  }

  set(key: string, value: unknown) {
    this.storage.getStore()?.set(key, value);
  }
}

// Middleware инициализирует контекст для каждого запроса:
@Injectable()
export class ContextMiddleware implements NestMiddleware {
  constructor(private context: RequestContextService) {}

  use(req: Request, res: Response, next: NextFunction) {
    const store = new Map<string, unknown>();
    store.set('requestId', req.headers['x-request-id'] ?? crypto.randomUUID());
    store.set('userId', req['user']?.id);

    // Запустить остальной pipeline внутри контекста ALS
    this.context.run(store, () => next());
  }
}

// Использование в любом Singleton сервисе:
@Injectable()
export class AuditService {
  constructor(private context: RequestContextService) {}

  log(action: string) {
    const requestId = this.context.get<string>('requestId');
    const userId = this.context.get<string>('userId');
    console.log(`[${requestId}] User ${userId}: ${action}`);
  }
}
// AuditService остаётся Singleton — нет scope propagation, нет GC overhead
```

## Токен REQUEST — инъекция самого запроса

Токен `REQUEST` из `@nestjs/core` отдаёт объект запроса прямо в конструктор. Инжектировать его можно только в провайдер с областью REQUEST.

Причина простая: у Singleton нет «своего» запроса. Он создаётся один раз, поэтому навсегда запомнил бы тот запрос, который случился первым.

```typescript
import { REQUEST } from '@nestjs/core';
import { Request } from 'express';

// Инжектировать объект запроса напрямую (только в REQUEST-scoped провайдерах)
@Injectable({ scope: Scope.REQUEST })
export class TenantService {
  constructor(
    @Inject(REQUEST) private readonly request: Request,
  ) {}

  getTenantId(): string {
    // Читать из sub-domain: tenant.example.com
    const host = this.request.hostname;
    return host.split('.')[0];

    // Или из header:
    // return this.request.headers['x-tenant-id'] as string;
  }
}

// TenantService ДОЛЖЕН быть REQUEST-scoped — иначе request всегда первый
// Это один из немногих обоснованных случаев для REQUEST scope
```

## Мультитенантность — когда область REQUEST оправдана

Мультитенантность — это когда одно приложение обслуживает несколько изолированных клиентов, и каждый такой клиент называется tenant. Типичный случай — SaaS (software as a service), то есть продукт, который клиенты используют как сервис по подписке.

Если у каждого клиента своя база данных, область REQUEST выглядит естественно: адрес базы становится известен только после того, как пришёл запрос с идентификатором клиента.

Цена всё равно есть — новый `PrismaClient` на каждый запрос. Поэтому в комментарии к примеру указана альтернатива: держать пул соединений на каждого клиента и переиспользовать его.

```typescript
// Сценарий: SaaS с несколькими tenant-ами, каждый со своей БД connection
@Injectable({ scope: Scope.REQUEST })
export class TenantDatabaseService {
  private prisma: PrismaClient;

  constructor(
    @Inject(REQUEST) private request: Request,
    private tenantConfig: TenantConfigService,
  ) {}

  async onModuleInit() {
    const tenantId = this.request.headers['x-tenant-id'] as string;
    const dbUrl = await this.tenantConfig.getDatabaseUrl(tenantId);

    this.prisma = new PrismaClient({ datasources: { db: { url: dbUrl } } });
    await this.prisma.$connect();
  }

  getClient() {
    return this.prisma;
  }
}

// Альтернатива без REQUEST scope: connection pool per tenant
// const pool = tenantPools.get(tenantId) ?? await createPool(tenantId)
// Избегает создания нового PrismaClient на каждый запрос
```

## Чеклист производительности для продакшена

Список короткий, и первый пункт весит больше остальных: начинайте с Singleton и меняйте область видимости только тогда, когда без этого не обойтись.

Остальное — про измерения. Пока нет замера, разговор про накладные расходы остаётся догадкой, поэтому в примере ниже есть Interceptor, который логирует медленные запросы.

```typescript
// 1. Всегда начинать с Singleton — изменять только при необходимости
// 2. Профилировать memory: node --inspect + Chrome DevTools heap snapshot
// 3. Использовать ALS вместо REQUEST scope где возможно

// 4. Измерять реальный overhead:
@Injectable()
export class PerformanceInterceptor implements NestInterceptor {
  intercept(ctx: ExecutionContext, next: CallHandler) {
    const start = process.hrtime.bigint();
    return next.handle().pipe(
      tap(() => {
        const duration = Number(process.hrtime.bigint() - start) / 1e6;
        if (duration > 500) {
          console.warn(`Slow request: ${duration.toFixed(2)}ms`);
        }
      }),
    );
  }
}

// 5. Connection pool: PrismaService — Singleton с одним pool
// НЕ создавать PrismaClient в REQUEST-scoped сервисах без необходимости

// 6. Lazy loading модулей для быстрого старта:
const lazyModule = await import('./heavy.module');
```

## Типичные ошибки на интервью

- **"REQUEST scope — хорошая идея для всех сервисов"** — нет, это антипаттерн. Каждый REQUEST-провайдер создаётся заново на каждый запрос вместе со всей цепочкой зависимостей. На высоком RPS это заметная нагрузка на сборщик мусора. По умолчанию — Singleton.

- **"AsyncLocalStorage сложнее REQUEST scope"** — нет. ALS — это один Singleton-сервис, а данные привязываются к асинхронному контексту сами. Плюсы: нет всплытия области видимости, нет лишней работы для сборщика мусора, сервис остаётся Singleton. Минус один: тем, кто не копался во внутренностях Node.js, механизм кажется неочевидным.

- **"Singleton провайдер не может получить данные текущего запроса"** — может, через ALS. `AsyncLocalStorage.getStore()` возвращает данные, привязанные к текущей цепочке асинхронных вызовов. Middleware кладёт их в хранилище один раз, и все вызовы внутри этого запроса видят то же самое.

- **"TRANSIENT scope полезен для логирования"** — частично. Логгер, который носит с собой имя сервиса, удобно сделать TRANSIENT. Но экземпляр создаётся на каждую инъекцию: десять сервисов — десять объектов логгера. Альтернатива: один логгер с `setContext(ctxName)` либо pino или winston с привязкой контекста.

- **"Scope.REQUEST и Scope.TRANSIENT решают одну задачу"** — нет. REQUEST — один экземпляр на HTTP-запрос, общий для всей цепочки зависимостей. TRANSIENT — один экземпляр **на каждую инъекцию**: внутри одного запроса сервисы A и B получат разные экземпляры одного и того же TRANSIENT-провайдера. Задачи разные, решения тоже.
