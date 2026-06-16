# Dynamic Modules

## Why Dynamic Modules exist

A static `@Module({ providers: [...] })` has its configuration fixed in code. A Dynamic Module lets you pass configuration at the point of import: `JwtModule.register({ secret: env.JWT_SECRET })`. Under the hood: a static method returns a `DynamicModule` object — the same as `ModuleMetadata`, but generated at runtime.

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
TypeOrmModule.forRoot({               // in AppModule: DB connection
  type: 'postgres',
  url: process.env.DATABASE_URL,
  autoLoadEntities: true,
})
TypeOrmModule.forFeature([User, Post]) // in UsersModule: repository registration
```

## Building your own Dynamic Module

```typescript
// cache.module.ts — configurable cache module
export interface CacheModuleOptions {
  ttl: number;
  maxSize?: number;
  prefix?: string;
}

export const CACHE_OPTIONS = new InjectionToken<CacheModuleOptions>('CACHE_OPTIONS');

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

## ConfigurableModuleBuilder — NestJS v9+

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

- **"A Dynamic Module can't be made global"** — it can. Returning `{ module, global: true, ... }` from `forRoot()`, or adding `@Global()` to the class, makes all its exports available throughout the application without explicit imports. `ConfigModule.forRoot({ isGlobal: true })` is exactly this pattern.

- **"register() and registerAsync() are the same thing"** — no. `register()` accepts ready-made options synchronously. `registerAsync()` accepts a `useFactory` with `inject`, allowing options to be resolved via DI (from ConfigService, SecretManager, etc.) asynchronously. Use `registerAsync` when the config depends on other services.

- **"DynamicModule must only return providers"** — no. A DynamicModule is a full ModuleMetadata plus a `module` field: it can contain `imports`, `providers`, `exports`, `controllers`, and `global`. It's a complete module generated at runtime.

- **"forRoot and forFeature are just conventions"** — yes, but important ones. `forRoot` — one-time initialization in the root module (DB connection, JWT config). `forFeature` — registers feature-specific resources (a repository for a given entity) inside a feature module. Breaking the convention confuses other developers.

- **"A Dynamic Module can't use useClass/useExisting"** — it can. Any provider in `DynamicModule.providers` can be of any type: useClass, useValue, useFactory, useExisting — everything works exactly as in a static module.
