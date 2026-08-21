# REQUEST Scope and Performance

## Scope propagation — the most important effect

When a provider gets `Scope.REQUEST`, Nest has to build a new dependency tree for every request. This affects more than that one provider: everything that depends on it becomes REQUEST-scoped too. The effect is known as scope bubble-up.

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
Scope propagation rules:
  Singleton can depend on Singleton ✓
  Singleton CANNOT depend on REQUEST (it becomes REQUEST) ⚠️
  REQUEST can depend on Singleton ✓
  REQUEST can depend on REQUEST ✓
  TRANSIENT — a new instance per injection,
    whatever the scope of the others
```

## Performance — measurable overhead

The cost of REQUEST scope is measurable, and it is the cost of creating objects. Take 1000 RPS (requests per second) and a chain of five REQUEST-scoped providers. That is 5000 new objects per second, and every one of them ends up with the garbage collector (GC).

The orders of magnitude and the measuring tools are below. NestJS has no built-in profiler, so people use external ones.

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

## AsyncLocalStorage — an alternative without the overhead

`AsyncLocalStorage` is a built-in Node.js mechanism that binds data to a chain of async calls. From here on it is shortened to ALS (AsyncLocalStorage).

The scheme is this: the service stays a Singleton, and the request data lives in the ALS store. Middleware opens the context once per request, and every async call inside that request sees the same data. No new providers are created, so nothing bubbles up.

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

## The REQUEST token — injecting the request object itself

The `REQUEST` token from `@nestjs/core` hands the request object straight into the constructor. You can only inject it into a provider with REQUEST scope.

The reason is simple: a Singleton has no request of its own. It is created once, so it would hold on to whichever request happened to arrive first.

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

Multi-tenancy is one application serving several isolated customers, and each customer is called a tenant. The typical case is SaaS (software as a service), a product customers use as a subscription service.

If every tenant has its own database, REQUEST scope looks natural: the database address is only known once a request arrives with the tenant id.

There is still a cost — a new `PrismaClient` per request. That is why the example's comment points at the alternative: keep a connection pool per tenant and reuse it.

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

The list is short, and the first item weighs more than the rest. Start with Singleton, and change the scope only when there is no way around it.

The rest is about measuring. Until you have numbers, talk about overhead is a guess, so the example below includes an Interceptor that logs slow requests.

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

- **"REQUEST scope is a good idea for all services"** — no, it is an anti-pattern. Every REQUEST provider is re-created on every request together with its whole dependency chain. At high RPS that is a noticeable load on the garbage collector. The default is Singleton.

- **"AsyncLocalStorage is more complex than REQUEST scope"** — no. ALS is one Singleton service, and the data binds itself to the async context. The upsides: no scope bubble-up, no extra work for the garbage collector, the service stays a Singleton. The single downside: to anyone who has not dug into Node.js internals, the mechanism looks unclear.

- **"A Singleton provider cannot access current request data"** — it can, through ALS. `AsyncLocalStorage.getStore()` returns the data bound to the current chain of async calls. Middleware puts it in the store once, and every call inside that request sees the same thing.

- **"TRANSIENT scope is useful for logging"** — partly. A logger that carries a service name is convenient as TRANSIENT. But an instance is created per injection: ten services mean ten logger objects. The alternatives are one logger with `setContext(ctxName)`, or pino or winston with context bindings.

- **"Scope.REQUEST and Scope.TRANSIENT solve the same problem"** — no. REQUEST is one instance per HTTP request, shared by the whole dependency chain. TRANSIENT is one instance **per injection**: inside a single request, services A and B get different instances of the same TRANSIENT provider. Different problems, different solutions.
