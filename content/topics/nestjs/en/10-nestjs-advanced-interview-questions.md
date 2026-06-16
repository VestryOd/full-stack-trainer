# NestJS Advanced Interview Questions

## Group 1: DI Container and Providers

**Q: What happens inside NestFactory.create() when the app starts?**

Nest executes several sequential phases: (1) recursive scanning of all `@Module()` declarations, (2) building the dependency graph — topological sort to determine the initialization order, (3) instantiating all Singleton scope providers starting from the graph's leaves, (4) calling `onModuleInit()` hooks, (5) starting the HTTP adapter (Express/Fastify). If there is a circular dependency without `forwardRef()` — the error occurs during graph construction.

**Q: Why is `InjectionToken<T>` better than string tokens?**

```typescript
// String token — no type safety
{ provide: 'DATABASE_URL', useValue: 'postgres://...' }
// Injection: @Inject('DATABASE_URL') url: string — compiler does not check the type

// InjectionToken<T> — full type safety
const DATABASE_URL = new InjectionToken<string>('DATABASE_URL');
{ provide: DATABASE_URL, useValue: 'postgres://...' }
// Injection: @Inject(DATABASE_URL) url: string — compiler verifies url: string

// Additional benefits:
// - No name conflicts between modules (string 'DB' may clash)
// - IDE autocomplete
// - The token itself is documentation via the generic <T>
```

**Q: When does useFactory need to be async?**

```typescript
// When a provider requires async initialization:
{
  provide: PrismaService,
  useFactory: async (config: ConfigService) => {
    const prisma = new PrismaClient({
      datasources: { db: { url: config.get('DATABASE_URL') } },
    });
    await prisma.$connect(); // async operation
    return prisma;
  },
  inject: [ConfigService],
}
// Nest waits for the Promise to resolve before the module becomes available
// This blocks app startup — normal for critical dependencies (DB)
```

**Q: What is forwardRef() and when is it needed?**

```typescript
// Circular dependency: A depends on B, B depends on A
// Without forwardRef — error during graph construction (one of them is undefined)
@Injectable()
export class UserService {
  constructor(
    @Inject(forwardRef(() => AuthService))
    private authService: AuthService,
  ) {}
}

@Injectable()
export class AuthService {
  constructor(
    @Inject(forwardRef(() => UserService))
    private userService: UserService,
  ) {}
}
// Best solution: refactor to eliminate the circular dependency
// forwardRef is a workaround, a sign of an architectural problem
```

---

## Group 2: Decorators, Metadata, and Reflection

**Q: How does @Roles('admin') work under the hood?**

```typescript
// @Roles uses the Reflect Metadata API:
export const Roles = (...roles: string[]) => SetMetadata('roles', roles);
// SetMetadata does: Reflect.defineMetadata('roles', roles, target/method)

// Guard reads the metadata via Reflector:
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    // getAllAndOverride: check method first, then class
    const roles = this.reflector.getAllAndOverride<string[]>('roles', [
      context.getHandler(), // @Roles on method (priority)
      context.getClass(),   // @Roles on class (fallback)
    ]);

    if (!roles) return true; // no @Roles — open endpoint

    const user = context.switchToHttp().getRequest().user;
    return roles.some(role => user?.roles?.includes(role));
  }
}
```

**Q: What is the difference between getAllAndOverride and getAllAndMerge?**

```typescript
// getAllAndOverride: method takes priority over class (returns one array or undefined)
@Controller('admin')
@Roles('admin')          // class: ['admin']
class AdminController {
  @Get()
  @Roles('superadmin')   // method: ['superadmin']
  action() {}
}
// getAllAndOverride → ['superadmin'] (method wins)

// getAllAndMerge: merges method + class (one combined array)
// getAllAndMerge → ['superadmin', 'admin'] (merged)

// Use getAllAndOverride when method should OVERRIDE class (@Public)
// Use getAllAndMerge when method should ADD TO class (permissions)
```

**Q: How does applyDecorators work and how does it differ from stacked decorators?**

```typescript
// Stacked decorators are applied bottom-to-top (right-to-left in TypeScript):
@A
@B
@C
method() {}
// Order: C → B → A

// applyDecorators applies top-to-bottom (left-to-right):
const Combined = applyDecorators(A, B, C);
// Order: A → B → C

// Example: API endpoint with auth + swagger
export const ApiEndpoint = (summary: string) =>
  applyDecorators(
    UseGuards(JwtAuthGuard),          // 1st applied to method
    ApiOperation({ summary }),         // 2nd
    ApiBearerAuth(),                   // 3rd
    ApiUnauthorizedResponse({ description: 'Unauthorized' }),
  );

@Get()
@ApiEndpoint('Get all users')
findAll() {}
```

---

## Group 3: Request Pipeline and its Mechanisms

**Q: Exact pipeline execution order — can you draw it including ExceptionFilter?**

```txt
Incoming Request
      ↓
  Middleware           — Express level, before Nest
      ↓
  ExceptionFilter      — wrapper around everything below
      ↓
  Guard                — authorization (canActivate)
      ↓
  Interceptor (pre)    — code before next.handle()
      ↓
  Pipe                 — validation/transformation of parameters
      ↓
  Controller/Handler   — business logic
      ↓
  Interceptor (post)   — operators in .pipe() after next.handle()
      ↓
  ExceptionFilter      — catches errors from Controller
      ↓
  Response
```

**Q: Why does next.handle() return an Observable instead of a Promise?**

`next.handle()` creates a "cold" Observable — the controller is invoked only on subscribe. This allows an Interceptor to return `of(cachedValue)` instead of `next.handle()`, meaning the controller is never called at all. RxJS operators (`map`, `tap`, `catchError`, `timeout`) provide a compact way to transform the response stream. Returning `firstValueFrom(next.handle())` also works, but you lose the ability to apply operators.

**Q: What is the difference between APP_GUARD and useGlobalGuards()?**

```typescript
// useGlobalGuards() in main.ts — OUTSIDE the DI container
app.useGlobalGuards(new JwtAuthGuard()); // cannot inject Reflector!

// APP_GUARD in a module — VIA DI, receives all injections
@Module({
  providers: [
    {
      provide: APP_GUARD,
      useClass: JwtAuthGuard, // Reflector is injected automatically
    },
  ],
})
// Rule: if a Guard/Pipe/Filter needs injection — use APP_*
```

---

## Group 4: Scopes, Dynamic Modules, and Performance

**Q: What is scope bubble-up and why is it a problem?**

```typescript
// If a provider is REQUEST-scoped — all its consumers also become REQUEST-scoped
@Injectable({ scope: Scope.REQUEST })
class RequestContextService {} // REQUEST

@Injectable()
class UserService {
  constructor(private ctx: RequestContextService) {}
  // ⚠️ Also REQUEST now (transitively)
}

@Injectable()
class OrderService {
  constructor(private users: UserService) {}
  // ⚠️ Also REQUEST (transitively)
}

// At 1000 RPS: 3 providers × 1000 = 3000 new objects/sec
// Solution: AsyncLocalStorage — Singleton service, data in the async context
// No scope propagation, no GC overhead
```

**Q: How to implement a Dynamic Module with registerAsync?**

```typescript
@Module({})
export class CacheModule {
  static register(options: CacheOptions): DynamicModule {
    return {
      module: CacheModule,
      providers: [
        { provide: CACHE_OPTIONS, useValue: options },
        CacheService,
      ],
      exports: [CacheService],
    };
  }

  static registerAsync(options: {
    imports?: any[];
    useFactory: (...args: any[]) => CacheOptions | Promise<CacheOptions>;
    inject?: any[];
  }): DynamicModule {
    return {
      module: CacheModule,
      imports: options.imports ?? [],
      providers: [
        {
          provide: CACHE_OPTIONS,
          useFactory: options.useFactory,
          inject: options.inject ?? [],
        },
        CacheService,
      ],
      exports: [CacheService],
    };
  }
}

// Usage: config from ConfigService
CacheModule.registerAsync({
  imports: [ConfigModule],
  useFactory: (config: ConfigService) => ({
    ttl: config.get<number>('CACHE_TTL'),
    host: config.get('REDIS_HOST'),
  }),
  inject: [ConfigService],
})
```

---

## Group 5: CQRS and Microservices

**Q: When is CQRS justified and when is it over-engineering?**

```txt
CQRS needed:                       CQRS NOT needed:
─────────────────────────────────────────────────────
Complex domain (DDD)               Simple CRUD
Different read/write loads         Admin Panel, CMS
Event-driven side effects          MVP / prototype
Audit trail required               Team < 5 engineers
Microservice architecture

Signs of an overloaded Service (time for CQRS):
  >10 methods mixing reads and writes
  Methods do both business logic and side effects
  Hard to test (too many dependencies in one service)
```

**Q: How can CommandHandler.execute() return data if CQRS says Commands are void?**

Bertrand Meyer's CQS principle is academic. In practice, returning the ID of a created entity from a CommandHandler is normal and convenient. `@nestjs/cqrs` does not restrict the return type. The key is not to return query data (use a Query for that) — but a created `{ id }` is the result of a mutation, not a query result.

**Q: What is the difference between TCP, RabbitMQ, and Kafka as transports in NestJS?**

```txt
TCP:       Direct connection, no queues, no retry.
           Good for: development, demos, synchronous calls.

RabbitMQ:  Queues with acknowledgement, dead-letter, retry, routing.
           Good for: task queues, reliable delivery.
           Messages persist until acknowledgement.

Kafka:     Partitioned log, consumer groups, retention.
           Good for: event streaming, analytics, high throughput.
           Messages persist for a defined retention period.

gRPC:      Binary protocol (protobuf), strict contract via .proto.
           Good for: internal inter-service calls, low latency.
```

---

## Group 6: Architectural Decisions and Best Practices

**Q: How to implement multi-tenancy in NestJS without REQUEST scope?**

```typescript
// Bad: REQUEST scope creates a new PrismaClient on every request
@Injectable({ scope: Scope.REQUEST })
class TenantDatabaseService {
  // New PrismaClient per request — GC nightmare
}

// Good: connection pool per tenant + AsyncLocalStorage
@Injectable()
class TenantService {
  private pools = new Map<string, PrismaClient>();

  async getClient(tenantId: string): Promise<PrismaClient> {
    if (!this.pools.has(tenantId)) {
      const client = new PrismaClient({
        datasources: { db: { url: await this.getTenantUrl(tenantId) } },
      });
      await client.$connect();
      this.pools.set(tenantId, client);
    }
    return this.pools.get(tenantId)!;
  }
}

// Middleware sets tenantId in ALS
// Singleton services read tenantId from ALS and get the right pool
```

**Q: What to choose for global error handling — ExceptionFilter or Interceptor?**

```typescript
// ExceptionFilter — the right choice for error handling:
// - Catches exceptions thrown at any level of the pipeline
// - Has access to ArgumentsHost for HTTP/WS/RPC context
// - Standard Nest mechanism, understood by other developers

// Interceptor with catchError — a complement:
// - Transform specific errors (Prisma → HTTP) in the middleware layer
// - Does NOT replace ExceptionFilter

// Rule: ExceptionFilter for formatting errors,
//       Interceptor.catchError for transforming internal errors into HTTP errors
@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const status = exception instanceof HttpException
      ? exception.getStatus()
      : HttpStatus.INTERNAL_SERVER_ERROR;

    ctx.getResponse().status(status).json({
      statusCode: status,
      timestamp: new Date().toISOString(),
      path: ctx.getRequest().url,
      message: exception instanceof Error ? exception.message : 'Internal error',
    });
  }
}
```

**Q: How to test NestJS services with DI?**

```typescript
// Unit test — mocks via Jest
describe('UserService', () => {
  let service: UserService;
  let prisma: DeepMockProxy<PrismaService>;

  beforeEach(async () => {
    const module = await Test.createTestingModule({
      providers: [
        UserService,
        {
          provide: PrismaService,
          useValue: mockDeep<PrismaService>(), // jest-mock-extended
        },
      ],
    }).compile();

    service = module.get(UserService);
    prisma = module.get(PrismaService);
  });

  it('should find user by id', async () => {
    prisma.user.findUnique.mockResolvedValue({ id: '1', email: 'test@test.com' });
    const result = await service.findById('1');
    expect(result.email).toBe('test@test.com');
  });
});

// Integration test — real DB (PostgreSQL in Docker)
// @nestjs/testing + real PrismaService
// beforeEach: transaction → rollback for test isolation
```
