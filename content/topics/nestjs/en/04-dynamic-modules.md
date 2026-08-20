# Dynamic Modules

## Why Dynamic Modules exist

A static `@Module({ providers: [...] })` has its configuration fixed in code. You cannot import such a module twice with different settings.

A Dynamic Module removes that limit: the settings are passed at the point of import — `JwtModule.register({ secret: env.JWT_SECRET })`. JWT (JSON Web Token) is a signed token used for authentication, and the signing secret is only known at runtime.

The mechanics are simple. A static method returns a `DynamicModule` object — the same module metadata (`ModuleMetadata`) plus a `module` field, but assembled at runtime.

```typescript
// Static module — configuration is hardcoded
@Module({
  providers: [{ provide: 'DB_HOST', useValue: 'localhost' }],
})
export class DatabaseModule {}

// Dynamic module — configuration passed at import time
@Module({})
export class DatabaseModule {
  static forRoot(options: DatabaseOptions): DynamicModule {
    return {
      module: DatabaseModule,       // reference to the current class
      global: options.isGlobal,     // optional: make globally available
      providers: [
        { provide: 'DB_OPTIONS', useValue: options },
        DatabaseService,            // may depend on 'DB_OPTIONS'
      ],
      exports: [DatabaseService],   // what to export
    };
  }
}

// Usage in AppModule:
@Module({
  imports: [
    DatabaseModule.forRoot({
      host: process.env.DB_HOST,
      port: parseInt(process.env.DB_PORT),
      isGlobal: true,
    }),
  ],
})
export class AppModule {}
```

## register vs registerAsync vs forRoot vs forFeature

These are four names for one mechanism: all of them are static methods, and all of them return a `DynamicModule`. What differs is what the name promises the reader:

- `register(options)` — the options are known right at the call site.
- `registerAsync({ inject, useFactory })` — the options have to be fetched first: from `ConfigService`, from a secret store. The factory may be async.
- `forRoot(options)` — app-wide initialization, called once in the root module.
- `forFeature(...)` — registers what one specific feature needs, inside that feature's module.

The `Async` suffix works the same way for both pairs, which is why modules also expose `forRootAsync`.

```typescript
// register() — synchronous configuration (options are known inline)
JwtModule.register({ secret: 'my-secret', signOptions: { expiresIn: '1h' } })

// registerAsync() — configuration depends on other providers
JwtModule.registerAsync({
  imports: [ConfigModule],
  inject: [ConfigService],
  useFactory: (config: ConfigService): JwtModuleOptions => ({
    secret: config.getOrThrow('JWT_SECRET'),
    signOptions: { expiresIn: config.get('JWT_EXPIRES_IN', '1h') },
  }),
})

// forRoot() — app-wide initialization (once in AppModule)
// forFeature() — registers feature-specific providers in a given module

// Example forRoot + forFeature:
TypeOrmModule.forRoot({               // in AppModule: database connection
  type: 'postgres',
  url: process.env.DATABASE_URL,
  autoLoadEntities: true,
})
TypeOrmModule.forFeature([User, Post]) // in UsersModule: repository registration
```

## Building your own Dynamic Module

Your own dynamic module is a class with an empty `@Module({})` and a static method that returns a `DynamicModule`. The options go into the container as an ordinary provider, and the module's service receives them through `@Inject`.

Below is a cache module with a TTL setting (time to live — how many seconds an entry stays in the cache). It has two methods: `register` for ready options, and `registerAsync` when the options come from `ConfigService`.

```typescript
// cache.module.ts — configurable cache module
export interface CacheModuleOptions {
  ttl: number;
  maxSize?: number;
  prefix?: string;
}

export const CACHE_OPTIONS = Symbol('CACHE_OPTIONS');

@Module({})
export class CacheModule {
  // Synchronous register
  static register(options: CacheModuleOptions): DynamicModule {
    return {
      module: CacheModule,
      providers: [
        { provide: CACHE_OPTIONS, useValue: options },
        CacheService,
      ],
      exports: [CacheService],
    };
  }

  // Asynchronous registerAsync — when options must come from ConfigService
  static registerAsync(asyncOptions: {
    imports?: any[];
    inject?: any[];
    useFactory: (...args: any[]) => Promise<CacheModuleOptions> | CacheModuleOptions;
  }): DynamicModule {
    return {
      module: CacheModule,
      imports: asyncOptions.imports ?? [],
      providers: [
        {
          provide: CACHE_OPTIONS,
          inject: asyncOptions.inject ?? [],
          useFactory: asyncOptions.useFactory,
        },
        CacheService,
      ],
      exports: [CacheService],
    };
  }
}

// cache.service.ts — consumes the options
@Injectable()
export class CacheService {
  constructor(
    @Inject(CACHE_OPTIONS) private options: CacheModuleOptions,
  ) {}

  set(key: string, value: unknown) {
    const prefixedKey = `${this.options.prefix ?? ''}:${key}`;
    // ... cache with this.options.ttl
  }
}

// Usage:
CacheModule.registerAsync({
  imports: [ConfigModule],
  inject: [ConfigService],
  useFactory: (config: ConfigService) => ({
    ttl: config.get('CACHE_TTL', 3600),
    prefix: config.get('CACHE_PREFIX', 'app'),
  }),
})
```

## useClass and useExisting in a Dynamic Module

Options do not have to come from a factory. The `useClass` field asks Nest to create a class that supplies them. The `useExisting` field reuses a provider that already exists and has the same interface.

That is how the official modules are built. One method accepts any of the three ways, and inside it builds the same options provider from all of them.

```typescript
// Sometimes configuration through a class is needed (ConfigurableModuleBuilder)
export interface ThrottlerModuleOptions {
  ttl: number;
  limit: number;
}

@Module({})
export class ThrottlerModule {
  static forRootAsync(options: {
    imports?: any[];
    useClass?: Type<ThrottlerModuleOptions>;
    useExisting?: Type<ThrottlerModuleOptions>;
    useFactory?: (...args: any[]) => ThrottlerModuleOptions;
    inject?: any[];
  }): DynamicModule {
    const provider: Provider = options.useFactory
      ? {
          provide: 'THROTTLER_OPTIONS',
          useFactory: options.useFactory,
          inject: options.inject,
        }
      : options.useClass
        ? { provide: 'THROTTLER_OPTIONS', useClass: options.useClass }
        : { provide: 'THROTTLER_OPTIONS', useExisting: options.useExisting };

    return {
      module: ThrottlerModule,
      imports: options.imports ?? [],
      providers: [provider, ThrottlerGuard],
      exports: [ThrottlerGuard],
    };
  }
}
```

## ConfigurableModuleBuilder — NestJS v9+

`ConfigurableModuleBuilder` saves you from writing these methods by hand. You describe the options type, and the builder hands back a base class with ready-made `register`/`registerAsync` plus the token the options are stored under.

The method name is configurable: `setClassMethodName('forRoot')` gives you `forRoot` and `forRootAsync` instead of `register`. The builder arrived in NestJS 9.

```typescript
// NestJS 9+ provides a builder that simplifies creating Dynamic Modules
import { ConfigurableModuleBuilder } from '@nestjs/common';

export interface HttpModuleOptions {
  baseUrl: string;
  timeout?: number;
}

// Automatically generates register, registerAsync, forRoot, forRootAsync
export const { ConfigurableModuleClass, MODULE_OPTIONS_TOKEN } =
  new ConfigurableModuleBuilder<HttpModuleOptions>()
    .setClassMethodName('forRoot')       // method name (default is 'register')
    .setExtras({ isGlobal: false }, (definition, extras) => ({
      ...definition,
      global: extras.isGlobal,
    }))
    .build();

@Module({
  providers: [HttpService],
  exports: [HttpService],
})
export class HttpModule extends ConfigurableModuleClass {}
// HttpModule.forRoot() and HttpModule.forRootAsync() are now available automatically

// HttpService receives options via MODULE_OPTIONS_TOKEN:
@Injectable()
export class HttpService {
  constructor(
    @Inject(MODULE_OPTIONS_TOKEN) private options: HttpModuleOptions,
  ) {}
}
```

## Common interview mistakes

- **"A Dynamic Module can't be made global"** — it can, in two ways. Return an object with `global: true` from `forRoot()`, or put `@Global()` on the class. After that the module's exports are visible across the whole app without an explicit import. `ConfigModule.forRoot({ isGlobal: true })` is exactly this trick.

- **"register() and registerAsync() are the same thing"** — no. The plain `register()` takes ready options synchronously. The async version takes a `useFactory` together with `inject`, so the options can be resolved through the container: from `ConfigService`, from a secret manager. Reach for `registerAsync` when the config depends on other services.

- **"DynamicModule must only return providers"** — no. It is full module metadata plus a `module` field, so it may contain `imports`, `providers`, `exports`, `controllers`, and `global`. An ordinary module, just assembled at runtime.

- **"forRoot and forFeature are just conventions"** — conventions, but important ones. The name `forRoot` promises one-time initialization in the root module: the database connection, the token signing config. The name `forFeature` promises the resources of a single feature, such as a repository for one entity. A name that promises something the method does not do confuses the whole team.

- **"A Dynamic Module can't use useClass/useExisting"** — it can. A provider inside `DynamicModule.providers` may be of any type: `useClass`, `useValue`, `useFactory`, `useExisting`. Everything works exactly as in a static module.
