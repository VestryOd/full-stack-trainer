# Providers, Scopes and the DI Container

## How the DI Container works in NestJS

The DI container (DI stands for dependency injection) is a registry of providers. You never write `new UserService(...)`: a class declares its dependencies in the constructor, and the container finds and passes them in.

At startup Nest does three things:

1. Scans every module and collects the list of providers.
2. Builds the dependency graph: which provider depends on which others.
3. Creates instances in topological order — a dependency first, then whoever asked for it.

Inside, the container is a map shaped like `Map<Token, { instance, scope, dependencies }>`. A token is the key a provider is looked up by, and most often that key is the class itself.

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

A provider record answers two questions: which token to look it up by (`provide`) and how to produce the value. The "how" is one of four fields:

- `useClass` — instantiate the given class. This lets you swap the implementation without touching the consumers.
- `useValue` — take a ready value: a string from the environment, a config object, a mock in a test.
- `useFactory` — call a function and take what it returns. The function may be async and may receive its own dependencies through `inject`.
- `useExisting` — make a second token an alias of the first. There is still only one instance.

The short form `providers: [UserService]` is the same `useClass`, just with the token and the class being the same thing.

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

## Provider scopes — Singleton, Request, Transient

A scope answers one question: how many instances of the provider live in the app, and when they are created. There are three options:

- **Singleton** (`Scope.DEFAULT`, the default) — one instance for the whole application.
- **Request** (`Scope.REQUEST`) — a new instance per incoming request.
- **Transient** (`Scope.TRANSIENT`) — a new instance per injection, so every consumer gets its own.

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
  Used for: 95% of all providers

Scope.REQUEST:
  Created: on every HTTP request
  Destroyed: when the request completes
  Used for: per-client (tenant) data, request data
  Careful: scope bubbles up — consumers become REQUEST too

Scope.TRANSIENT:
  Created: on every injection, a separate instance
    for each consumer
  Used for: loggers that carry a context
  Rarely needed: Singleton is usually enough
```

## Scope bubble-up — an important side effect

A scope is contagious and spreads upwards through the dependency graph. As soon as a Singleton asks for a REQUEST provider in its constructor, it silently becomes a REQUEST provider itself. Nest does not complain and logs nothing.

From there it travels along the chain: whoever depends on the newly REQUEST-scoped provider becomes REQUEST-scoped as well. One provider can move half of your app onto per-request re-creation.

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

## InjectionToken — a type-safe token

A string token works, but it has two problems. The compiler will not notice a typo in `'JWT_SECRET'`, and you have to write the value's type by hand at every injection point.

A typed token fixes both: the name is written once in a constant, and the type of the value lives in the token itself.

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

## Circular dependencies — how to untangle them

A circular dependency is when class `A` asks for `B` in its constructor while `B` asks for `A` back. The container cannot create either one first. So during graph construction one of the constructor arguments ends up as `undefined`.

`forwardRef(() => Class)` delays resolving the class reference until both classes are loaded. You need the wrapper in two places: at the injection point and at the module import.

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

- **"@Injectable() creates an instance"** — no. The decorator only adds metadata (`scope`, token) that lets Nest recognise the class as a provider and take over its lifecycle. The instance is created by the DI container: at startup, or per request if the scope is REQUEST.

- **"All providers in the application are available everywhere"** — no. A provider is visible only inside the module that lists it in `providers`. To use it from another module, add it to that module's `exports` and import the module. The exception is a module marked `@Global()`: its exports are visible everywhere without an explicit import.

- **"useFactory runs on every request"** — not when the scope is Singleton. Then the factory is called **once** at startup and the result is stored in the container. For a REQUEST provider it is different: the factory really does run on every request.

- **"Request scope is a good alternative to AsyncLocalStorage"** — both solve the same task: giving a service the data of the current request. A REQUEST provider is re-created together with its whole dependency chain, which is extra work for the garbage collector (GC). AsyncLocalStorage keeps one Singleton and stores the data in the async call context. For an API under high load, pick AsyncLocalStorage.

- **"A token has to be a string"** — no. A token can be a class (the most common case), a string, a `Symbol`, or an `InjectionToken<T>`. For custom tokens `InjectionToken<T>` is the recommended one: it is typed and, unlike a string, will not let a typo slip past the compiler.
