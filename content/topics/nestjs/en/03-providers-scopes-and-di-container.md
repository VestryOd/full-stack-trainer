# Providers, Scopes and DI Container

## How the DI Container works in NestJS

The NestJS DI Container is a registry of providers. At startup, Nest scans all modules, builds a dependency graph (which provider depends on which others), and creates instances in the correct topological order. Under the hood: `Map<Token, { instance, scope, dependencies }>`.

```typescript
// At startup, Nest does this automatically:
// 1. Scans @Module({ providers: [UserService, PrismaService] })
// 2. Sees: UserService constructor requires PrismaService
// 3. Builds graph: PrismaService → UserService → UsersController
// 4. Creates in order: PrismaService → UserService → UsersController
// 5. Stores all instances in the Container

@Injectable()
export class PrismaService { ... }

@Injectable()
export class UserService {
  constructor(private prisma: PrismaService) {}
  // Nest reads TypeScript metadata: constructor param type = PrismaService
  // Looks up in Container by token PrismaService → passes the instance
}

@Controller('users')
export class UsersController {
  constructor(private users: UserService) {}
}
```

## Provider types — useClass, useValue, useFactory, useExisting

```typescript
// Module providers — extended syntax
@Module({
  providers: [
    // 1. Short syntax (useClass is implied)
    UserService,
    // equivalent to: { provide: UserService, useClass: UserService }

    // 2. useClass — swap the implementation via an interface
    { provide: UserRepository, useClass: PrismaUserRepository },
    // Injection: constructor(private repo: UserRepository) — gets PrismaUserRepository

    // 3. useValue — static value (config, mocks)
    { provide: 'JWT_SECRET', useValue: process.env.JWT_SECRET },
    { provide: 'APP_CONFIG', useValue: { port: 3000, debug: false } },

    // 4. useFactory — create dynamically (async-capable)
    {
      provide: 'REDIS_CLIENT',
      inject: [ConfigService],
      useFactory: async (config: ConfigService) => {
        const client = createClient({ url: config.get('REDIS_URL') });
        await client.connect();
        return client;
      },
    },

    // 5. useExisting — alias: two tokens → one instance
    { provide: 'IUserService', useExisting: UserService },
    // Both tokens point to the same UserService instance
  ],
})
export class UsersModule {}

// Injecting a custom token (@Inject is required for non-class tokens):
@Injectable()
export class AuthService {
  constructor(
    @Inject('JWT_SECRET') private jwtSecret: string,
    @Inject('REDIS_CLIENT') private redis: RedisClientType,
  ) {}
}
```

## Provider Scopes — Singleton, Request, Transient

```typescript
import { Injectable, Scope } from '@nestjs/common';

// Singleton (default) — one instance for the entire application
@Injectable()
export class UserService { ... }
// equivalent to: @Injectable({ scope: Scope.DEFAULT })

// Request Scope — a new instance per HTTP request
@Injectable({ scope: Scope.REQUEST })
export class RequestContextService {
  private readonly requestId = Math.random().toString(36);

  getRequestId() { return this.requestId; }
}
// Each request gets its own instance with a unique requestId

// Transient Scope — a new instance per injection
@Injectable({ scope: Scope.TRANSIENT })
export class LoggerService {
  private context: string;

  setContext(ctx: string) { this.context = ctx; }
  log(msg: string) { console.log(`[${this.context}] ${msg}`); }
}
// UsersService and PostsService each get their own LoggerService instance
```

```txt
Scope.DEFAULT (Singleton):
  Created: once at startup
  Destroyed: when the application shuts down
  Usage: 95% of all providers

Scope.REQUEST:
  Created: on every HTTP request
  Destroyed: when the request completes
  Usage: tenant context, request-specific data
  Warning: "scope bubble up" — all dependents also become REQUEST-scoped

Scope.TRANSIENT:
  Created: on every injection (each consumer gets its own instance)
  Usage: contextualized loggers
  Rarely needed: Singleton is sufficient in most cases
```

## Scope Bubble Up — an important side effect

```typescript
// PROBLEM: if a REQUEST-scoped provider is injected into a Singleton,
// the Singleton also becomes REQUEST-scoped (NestJS does this automatically)

@Injectable({ scope: Scope.REQUEST })
export class RequestContext {
  constructor(@Inject(REQUEST) private request: Request) {}
  getUserId() { return this.request['user']?.id; }
}

// UserService was a Singleton but now implicitly becomes REQUEST-scoped
// because it depends on the REQUEST-scoped RequestContext
@Injectable()
export class UserService {
  constructor(private context: RequestContext) {}
  // ⚠️ UserService is now implicitly REQUEST-scoped!
}

// Alternative without bubble-up: pass userId explicitly as a method parameter
@Injectable()
export class UserService {
  async getUser(userId: string) { ... } // userId passed explicitly, not via context
}
```

## InjectionToken — type-safe token

```typescript
// String tokens ('JWT_SECRET') — risk of typos
// Solution: InjectionToken<T> for type safety

import { InjectionToken } from '@nestjs/common';

export const JWT_SECRET = new InjectionToken<string>('JWT_SECRET');
export const REDIS_CLIENT = new InjectionToken<RedisClientType>('REDIS_CLIENT');

// In Module:
{ provide: JWT_SECRET, useValue: process.env.JWT_SECRET }

// Injection — TypeScript knows the type:
constructor(@Inject(JWT_SECRET) private jwtSecret: string) {}
// vs a string token: you must annotate the type manually
```

## Circular Dependencies — how to resolve

```typescript
// Problem: A depends on B, B depends on A → circular dependency

// Solution 1: forwardRef() — deferred reference
@Injectable()
export class AuthService {
  constructor(
    @Inject(forwardRef(() => UsersService))
    private usersService: UsersService,
  ) {}
}

@Injectable()
export class UsersService {
  constructor(
    @Inject(forwardRef(() => AuthService))
    private authService: AuthService,
  ) {}
}

// The module also needs forwardRef:
@Module({
  imports: [forwardRef(() => UsersModule)],
})
export class AuthModule {}

// Solution 2 (better): extract shared logic into a third service
// AuthSharedService — no circular dependency
```

## Common interview mistakes

- **"@Injectable() creates an instance"** — no. `@Injectable()` adds metadata (`scope`, `token`) that lets Nest discover the class as a provider and manage its lifecycle. The instance is created by the DI Container at startup (or per request for REQUEST scope).

- **"All providers in the application are available everywhere"** — no. A provider is only available in the module that declares it in `providers`. To use it in another module: add it to `exports` of the source module and import that module. Exception: a `@Global()` module — its exports are available everywhere without explicit imports.

- **"useFactory runs on every request"** — not for Singleton scope. The factory is called ONCE at startup and its return value is stored in the Container. For REQUEST scope: the factory is called on every request.

- **"Request Scope is a good alternative to AsyncLocalStorage"** — both solve the request-specific data problem. REQUEST scope: creates a new provider (and the entire dependency chain) per request — overhead on the GC. AsyncLocalStorage: a single Singleton, data stored in the async context — more efficient. For high-throughput APIs: AsyncLocalStorage is preferred.

- **"A TOKEN must be a string"** — no. A token can be: a class (most common), a string, a Symbol, or an `InjectionToken<T>`. `InjectionToken` is recommended for custom tokens — it's type-safe and eliminates typos, unlike a plain string.
