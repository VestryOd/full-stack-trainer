# Request Scope и Performance

## Scope Propagation — самый важный эффект

Когда провайдер становится `Scope.REQUEST`, Nest должен создать новый dependency tree для каждого запроса. Это затрагивает НЕ только этот провайдер — все провайдеры которые зависят от него тоже становятся REQUEST-scoped (scope bubble up).

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
Правило Scope Propagation:
  Singleton может зависеть от Singleton ✓
  Singleton НЕ МОЖЕТ зависеть от REQUEST (становится REQUEST) ⚠️
  REQUEST может зависеть от Singleton ✓
  REQUEST может зависеть от REQUEST ✓
  TRANSIENT — новый instance при каждой инъекции (независимо от scope)
```

## Производительность — измеримые издержки

```typescript
// При 1000 RPS и цепочке из 5 REQUEST-scoped провайдеров:
// 1000 запросов × 5 объектов = 5000 новых объектов/сек
// Каждый объект: TypeScript instantiation + DI injection + GC давление

// Benchmark (примерные числа):
// Singleton: 0.01ms overhead per request (lookup из container)
// Request scope: 0.1-0.5ms overhead per request (instantiation + GC)
// На 1000 RPS: 100-500ms потеряно только на scope overhead

// Профилирование:
import { ProfilerService } from '@nestjs/core';
// В NestJS нет встроенного профилировщика, но можно использовать:
// - clinic.js (flamegraph)
// - @nestjs/terminus для health metrics
// - pino/winston для request timing
```

## AsyncLocalStorage — альтернатива без overhead

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

## REQUEST token — инжекция самого запроса

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

## Multi-tenancy — когда REQUEST scope оправдан

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

## Performance чеклист для production

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

- **"REQUEST scope — хорошая идея для всех сервисов"** — нет. Это антипаттерн. Каждый REQUEST-scoped провайдер создаётся заново на каждый запрос вместе со всей цепочкой зависимостей. На высоком RPS это добавляет значительный GC overhead. Default: Singleton.

- **"AsyncLocalStorage сложнее REQUEST scope"** — нет. ALS: один Singleton сервис, данные привязаны к async контексту автоматически. Плюс: нет scope propagation, нет GC overhead, сервис остаётся Singleton. Минус: менее очевидная концепция для разработчиков незнакомых с Node.js internals.

- **"Singleton провайдер не может получить данные текущего запроса"** — может, через ALS. `AsyncLocalStorage.getStore()` возвращает данные привязанные к текущей async цепочке выполнения. Middleware устанавливает store один раз, все последующие async вызовы внутри этого запроса видят те же данные.

- **"TRANSIENT scope полезен для логирования"** — частично. LoggerService с контекстом (имя сервиса) удобно делать TRANSIENT. Но каждый потребитель получает отдельный instance — для 10 сервисов это 10 LoggerService объектов на запрос. Альтернатива: один LoggerService.setContext(ctxName) или использовать pino/winston с contextual bindings.

- **"Scope.REQUEST и Scope.TRANSIENT решают одну задачу"** — нет. REQUEST: один instance на HTTP запрос, общий для всей цепочки. TRANSIENT: один instance на ИНЪЕКЦИЮ (A и B получат разные instances одного TRANSIENT провайдера в одном запросе). Разные проблемы — разные решения.
