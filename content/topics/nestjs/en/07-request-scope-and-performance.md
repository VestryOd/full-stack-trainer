# Request Scope and Performance

## Scope Propagation — the most important effect

When a provider becomes `Scope.REQUEST`, Nest must create a new dependency tree for every request. This affects NOT just that provider — all providers that depend on it also become REQUEST-scoped (scope bubble up).

```typescript
// Scope propagation example:
@Injectable({ scope: Scope.REQUEST })
export class RequestContextService {
  // NOT a Singleton
  // This provider is REQUEST-scoped
}

@Injectable() // was Singleton
export class UserService {
  constructor(private context: RequestContextService) {}
  // ⚠️ Now REQUEST-scoped due to dependency!
}

@Injectable() // was Singleton
export class OrderService {
  constructor(private users: UserService) {}
  // ⚠️ Also REQUEST-scoped (transitively)!
}

// Result: chain RequestContext → UserService → OrderService
// Re-created on EVERY request
```

```txt
Scope Propagation rules:
  Singleton can depend on Singleton ✓
  Singleton CANNOT depend on REQUEST (becomes REQUEST) ⚠️
  REQUEST can depend on Singleton ✓
  REQUEST can depend on REQUEST ✓
  TRANSIENT — new instance per injection (independent of scope)
```

## Performance — measurable overhead

```typescript
// At 1000 RPS with a chain of 5 REQUEST-scoped providers:
// 1000 requests × 5 objects = 5000 new objects/sec
// Each object: TypeScript instantiation + DI injection + GC pressure

// Benchmark (approximate numbers):
// Singleton: 0.01ms overhead per request (lookup from container)
// Request scope: 0.1-0.5ms overhead per request (instantiation + GC)
// At 1000 RPS: 100-500ms wasted on scope overhead alone

// Profiling:
// - clinic.js (flamegraph)
// - @nestjs/terminus for health metrics
// - pino/winston for request timing
```

## AsyncLocalStorage — an alternative without overhead

```typescript
// Node.js built-in mechanism for request-scoped data WITHOUT creating new providers
import { AsyncLocalStorage } from 'async_hooks';

// request-context.service.ts — SINGLETON, data stored in ALS
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

// Middleware initializes the context for each request:
@Injectable()
export class ContextMiddleware implements NestMiddleware {
  constructor(private context: RequestContextService) {}

  use(req: Request, res: Response, next: NextFunction) {
    const store = new Map<string, unknown>();
    store.set('requestId', req.headers['x-request-id'] ?? crypto.randomUUID());
    store.set('userId', req['user']?.id);

    // Run the rest of the pipeline inside the ALS context
    this.context.run(store, () => next());
  }
}

// Usage in any Singleton service:
@Injectable()
export class AuditService {
  constructor(private context: RequestContextService) {}

  log(action: string) {
    const requestId = this.context.get<string>('requestId');
    const userId = this.context.get<string>('userId');
    console.log(`[${requestId}] User ${userId}: ${action}`);
  }
}
// AuditService stays Singleton — no scope propagation, no GC overhead
```

## REQUEST token — injecting the request object itself

```typescript
import { REQUEST } from '@nestjs/core';
import { Request } from 'express';

// Inject the request object directly (only in REQUEST-scoped providers)
@Injectable({ scope: Scope.REQUEST })
export class TenantService {
  constructor(
    @Inject(REQUEST) private readonly request: Request,
  ) {}

  getTenantId(): string {
    // Read from sub-domain: tenant.example.com
    const host = this.request.hostname;
    return host.split('.')[0];

    // Or from header:
    // return this.request.headers['x-tenant-id'] as string;
  }
}

// TenantService MUST be REQUEST-scoped — otherwise request is always the first one
// This is one of the few justified use cases for REQUEST scope
```

## Multi-tenancy — when REQUEST scope is justified

```typescript
// Scenario: SaaS with multiple tenants, each with their own DB connection
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

// Alternative without REQUEST scope: connection pool per tenant
// const pool = tenantPools.get(tenantId) ?? await createPool(tenantId)
// Avoids creating a new PrismaClient on every request
```

## Performance checklist for production

```typescript
// 1. Always start with Singleton — change only when necessary
// 2. Profile memory: node --inspect + Chrome DevTools heap snapshot
// 3. Use ALS instead of REQUEST scope when possible

// 4. Measure actual overhead:
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

// 5. Connection pool: PrismaService — Singleton with one pool
// Do NOT create PrismaClient in REQUEST-scoped services without need

// 6. Lazy loading modules for fast startup:
const lazyModule = await import('./heavy.module');
```

## Common interview mistakes

- **"REQUEST scope is a good idea for all services"** — no. This is an anti-pattern. Every REQUEST-scoped provider is re-created on every request along with its entire dependency chain. At high RPS this adds significant GC overhead. Default: Singleton.

- **"AsyncLocalStorage is more complex than REQUEST scope"** — no. ALS: one Singleton service, data is automatically bound to the async context. Pros: no scope propagation, no GC overhead, service stays Singleton. Con: less obvious concept for developers unfamiliar with Node.js internals.

- **"A Singleton provider cannot access current request data"** — it can, via ALS. `AsyncLocalStorage.getStore()` returns data bound to the current async execution chain. Middleware sets the store once; all subsequent async calls within that request see the same data.

- **"TRANSIENT scope is useful for logging"** — partially. A LoggerService with context (service name) is convenient to make TRANSIENT. But each consumer gets a separate instance — for 10 services that's 10 LoggerService objects per request. Alternative: one `LoggerService.setContext(ctxName)` or use pino/winston with contextual bindings.

- **"Scope.REQUEST and Scope.TRANSIENT solve the same problem"** — no. REQUEST: one instance per HTTP request, shared across the entire dependency chain. TRANSIENT: one instance per INJECTION (A and B will receive different instances of the same TRANSIENT provider within one request). Different problems — different solutions.
