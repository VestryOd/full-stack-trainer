# NestJS Advanced Interview Questions

## Group 1: the DI container and providers

**Q: What happens inside NestFactory.create() when the app starts?**

Nest goes through five phases in order. It assembles the dependency graph first and only then starts the server, which is why configuration errors show up before the first request. DI below means dependency injection.

```txt
NestFactory.create() phases:
  1. Recursive scan of every @Module() declaration
  2. Dependency graph is built → topological order
  3. Singleton providers created, starting from the leaves
  4. onModuleInit() hooks are called
  5. HTTP adapter starts (Express or Fastify)
```

A circular dependency without `forwardRef()` breaks phase two. The error arrives while the graph is being built, before the server ever listens on a port.

**Q: Why is a `Symbol` token better than a string token?**

Because a symbol cannot be misspelled and cannot collide. A string token is retyped at every injection point, so a typo in `'DATABASE_URL'` fails at runtime, not at compile time. Two `'DB'` strings from different modules resolve to the same token and overwrite each other; two symbols never do, even with the same description.

What a symbol does **not** give you is the type of the value. No Nest token carries it. `InjectionToken<T>` is a type alias for what may serve as a token, not a container for the value type. The constructor annotation is what types the injection.

```typescript
// String token — retyped everywhere, collides across modules
{ provide: 'DATABASE_URL', useValue: 'postgres://...' }
// Injection: @Inject('DATABASE_URL') url: string — a typo here compiles

// Symbol token — one constant, unique by construction
export const DATABASE_URL = Symbol('DATABASE_URL');
{ provide: DATABASE_URL, useValue: 'postgres://...' }
// Injection: @Inject(DATABASE_URL) url: string — the name cannot be mistyped

// Additional benefits:
// - No name conflicts between modules (string 'DB' may clash)
// - IDE autocomplete
// - The token itself is documentation via the generic <T>
```

**Q: When does useFactory need to be async?**

When the value cannot be produced by one constructor call: you have to open a connection, read a secret, wait for the network. The factory returns a promise, and Nest waits for it before handing the module to anyone else.

Application startup blocks while that happens. For critical dependencies such as the database that is the right behaviour: better not to start at all than to start without a database.

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
// This blocks app startup — normal for critical dependencies
```

**Q: What is forwardRef() and when is it needed?**

`forwardRef(() => Class)` delays resolving the class reference until both classes are loaded. You need it for a circular dependency: `A` asks for `B` in its constructor while `B` asks for `A`.

Without the delayed reference one of the arguments arrives as `undefined`. But `forwardRef` treats the symptom, not the cause: a cycle almost always means the shared logic belongs in a third service.

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

## Group 2: decorators, metadata and reflection

**Q: How does @Roles('admin') work under the hood?**

The decorator checks nothing — it only writes metadata. Under the hood `SetMetadata('roles', roles)` calls `Reflect.defineMetadata` and attaches the array of roles to the method or to the controller class.

The checking is done by a Guard. It reads the same metadata through `Reflector` and compares it with the user's roles. No metadata means no restriction, so the endpoint is open.

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

Both read the same metadata from two levels, the method and the class. They differ in how they combine the result. The `getAllAndOverride` call takes the method value if there is one, otherwise the class value. The `getAllAndMerge` call joins both arrays into one.

The rule for choosing is simple. Use `getAllAndOverride` when the method overrides the class, as `@Public()` does inside a protected controller. Use `getAllAndMerge` when permissions add up.

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

`applyDecorators(A, B, C)` applies the decorators in the written order: A first, then B, then C last. TypeScript does the opposite with a stack of `@A @B @C`, applying it bottom-up.

That is where the practical value comes from. A set built with `applyDecorators` behaves predictably and is reused as a single decorator.

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

## Group 3: the request pipeline and its mechanisms

**Q: Exact pipeline execution order — can you draw it including ExceptionFilter?**

The order is fixed, and ExceptionFilter appears in it twice. It wraps everything below itself, which is how it catches exceptions from a Guard, from a Pipe and from the controller alike.

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

`next.handle()` creates a "cold" Observable: the controller runs only on subscribe. That is what lets an Interceptor return `of(cachedValue)` instead of `next.handle()`, in which case the controller never runs at all.

The second reason is operators. `map`, `tap`, `catchError` and `timeout` give you a compact way to process the response stream. You can write `firstValueFrom(next.handle())`, but the operators are gone after that.

```typescript
// One line decides whether the controller runs at all:
return cached ? of(cached) : next.handle();
```

**Q: What is the difference between APP_GUARD and useGlobalGuards()?**

The difference is access to the container. The `useGlobalGuards()` call in `main.ts` receives a finished object built with `new`. Nothing can be injected into it, neither `Reflector` nor `ConfigService`.

The `APP_GUARD` token registers the Guard as an ordinary module provider. The container builds the instance, and the dependencies arrive on their own.

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

## Group 4: scopes, dynamic modules and performance

**Q: What is scope bubble-up and why is it a problem?**

Scope bubble-up is when a REQUEST-scoped provider turns everything that depends on it into REQUEST-scoped providers too. The effect then travels along the chain transitively, and Nest gives you no warning.

The problem is the amount of work. At 1000 RPS (requests per second) a chain of three providers means 3000 new objects per second. All of them land on the garbage collector.

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
// No scope propagation, no load on the garbage collector
```

**Q: How do you implement a Dynamic Module with registerAsync?**

Both methods return the same `DynamicModule` object, and they differ only in how the options are obtained. The plain `register` puts ready options in through `useValue`. The async version puts them in through `useFactory` together with an `inject` list, so the options can come from `ConfigService`.

Everything else in the object is identical: the same `module`, the same providers, the same `exports`.

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

## Group 5: CQRS and microservices

**Q: When is CQRS justified and when is it over-engineering?**

CQRS (Command Query Responsibility Segregation) pays off where reads and writes have genuinely drifted apart: their own model, their own load, their own side effects. On a plain set of operations over records it adds files and adds no value.

The table uses three abbreviations. DDD (domain-driven design) means designing from the business domain. CRUD (create, read, update, delete) are the four basic operations on a record. MVP (minimum viable product) is the smallest shippable version of a product.

| CQRS needed | CQRS not needed |
|---|---|
| Complex domain designed with DDD | Simple CRUD |
| Different read and write loads | Admin panel, content management system |
| Side effects driven by events | MVP or prototype |
| Full history of changes required | Team smaller than five people |
| Microservice architecture | |

Signs of an overloaded service that is ready to be split:

- More than ten methods, with reads and writes mixed together.
- Methods that do both business logic and side effects.
- The service is hard to test: too many dependencies in one class.

**Q: How can CommandHandler.execute() return data if CQRS says a Command returns nothing?**

The strict ban comes from Bertrand Meyer's CQS principle (Command Query Separation), and it is academic. `@nestjs/cqrs` does not restrict the return type.

In practice, returning the id of the created entity from a command handler is normal and convenient. What matters is different: do not return read data from a command, that is what a query is for. A created `{ id }` is the result of a mutation, not the result of a read.

```typescript
// This is fine: what comes back is the result of a mutation, not a query
async execute(cmd: CreateUserCommand): Promise<{ id: string }> {
  const user = await this.prisma.user.create({ data: { ...cmd } });
  return { id: user.id };
}
```

**Q: What is the difference between TCP, RabbitMQ and Kafka as transports in NestJS?**

TCP (transmission control protocol) is a direct connection: no queues, no retries. RabbitMQ and Kafka put a broker between the services, and that broker does not lose the message. So the real difference between the three is the delivery guarantee.

The two brokers store messages differently. RabbitMQ keeps a message in the queue until the consumer acknowledges it. Kafka keeps it for a set period (the retention policy), whether anyone has read it or not.

| Transport | What it is | What it fits |
|---|---|---|
| TCP | Direct connection, no queues, no retries | Development, demos, synchronous calls |
| RabbitMQ | Queues with acknowledgement, retries, routing, dead letters | Task queues, reliable delivery |
| Kafka | Partitioned log, consumer groups, stored history | Event streaming, analytics, high throughput |
| gRPC | Binary protocol (Protocol Buffers), strict contract in a `.proto` file | Internal calls between services, low latency |

---

## Group 6: architectural decisions and practices

**Q: How do you implement multi-tenancy in NestJS without REQUEST scope?**

Keep a connection pool per customer (tenant) in an ordinary Singleton service and take the ready client from there by id. The id itself goes into `AsyncLocalStorage` instead of being dragged through every method signature.

The bad option is a REQUEST provider with a fresh `PrismaClient`: a new connection per request, and constant load on the garbage collector.

```typescript
// Bad: REQUEST scope creates a new PrismaClient on every request
@Injectable({ scope: Scope.REQUEST })
class TenantDatabaseService {
  // New PrismaClient per request — constant work for the garbage collector
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

// Middleware sets tenantId in AsyncLocalStorage
// Singleton services read tenantId from there and get the right pool
```

**Q: What do you choose for global error handling — ExceptionFilter or Interceptor?**

ExceptionFilter. It catches exceptions from any level of the pipeline, receives `ArgumentsHost`, and therefore works for HTTP, for WebSocket and for microservice messages. It is the standard Nest mechanism, so anyone reading your code recognises it.

An Interceptor with `catchError` is a complement, not a replacement. Its job is narrow: turning specific internal errors, such as Prisma codes, into HTTP exceptions.

```typescript
// ExceptionFilter — the right choice for error handling:
// - Catches exceptions thrown at any level of the pipeline
// - Has access to ArgumentsHost for HTTP/WS/RPC context
// - Standard Nest mechanism, understood by other developers

// Interceptor with catchError — a complement:
// - Transform specific errors (Prisma → HTTP)
// - Does NOT replace ExceptionFilter

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

**Q: How do you test NestJS services that use dependency injection?**

With `Test.createTestingModule` from `@nestjs/testing`: you declare the same provider list, but replace the real dependencies with mocks through `useValue`. Then `module.get(UserService)` hands you an instance assembled by the container.

Integration tests run against a real database in Docker and a real `PrismaService`. Isolation between tests is kept with a transaction: open it in `beforeEach`, roll it back afterwards.

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

// Integration test — real database (PostgreSQL in Docker)
// @nestjs/testing + real PrismaService
// beforeEach: transaction → rollback for test isolation
```
