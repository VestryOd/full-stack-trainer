# Dynamic Modules

## Зачем нужны Dynamic Modules

Статический `@Module({ providers: [...] })` — конфигурация фиксирована на уровне кода. Dynamic Module позволяет передать конфигурацию в момент импорта модуля: `JwtModule.register({ secret: env.JWT_SECRET })`. Под капотом: статический метод возвращает объект `DynamicModule` — это тот же `ModuleMetadata`, но генерированный в runtime.

```typescript
// Статический модуль — конфигурация захардкожена
@Module({
  providers: [{ provide: 'DB_HOST', useValue: 'localhost' }],
})
export class DatabaseModule {}

// Динамический модуль — конфигурация передаётся при импорте
@Module({})
export class DatabaseModule {
  static forRoot(options: DatabaseOptions): DynamicModule {
    return {
      module: DatabaseModule,       // ссылка на текущий класс
      global: options.isGlobal,     // опционально: сделать глобальным
      providers: [
        { provide: 'DB_OPTIONS', useValue: options },
        DatabaseService,            // может зависеть от 'DB_OPTIONS'
      ],
      exports: [DatabaseService],   // что экспортировать
    };
  }
}

// Использование в AppModule:
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
// register() — синхронная конфигурация (опции известны на месте)
JwtModule.register({ secret: 'my-secret', signOptions: { expiresIn: '1h' } })

// registerAsync() — конфигурация зависит от других провайдеров
JwtModule.registerAsync({
  imports: [ConfigModule],
  inject: [ConfigService],
  useFactory: (config: ConfigService): JwtModuleOptions => ({
    secret: config.getOrThrow('JWT_SECRET'),   // получить из env через ConfigService
    signOptions: { expiresIn: config.get('JWT_EXPIRES_IN', '1h') },
  }),
})

// forRoot() — инициализация для всего приложения (один раз в AppModule)
// forFeature() — регистрация feature-специфичных провайдеров в конкретном модуле

// Пример forRoot + forFeature:
TypeOrmModule.forRoot({               // в AppModule: подключение к БД
  type: 'postgres',
  url: process.env.DATABASE_URL,
  autoLoadEntities: true,
})
TypeOrmModule.forFeature([User, Post]) // в UsersModule: регистрация репозиториев
```

## Создание своего Dynamic Module

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
  // Синхронный register
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

  // Асинхронный registerAsync — когда options нужно получить из ConfigService
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

// cache.service.ts — использует опции
@Injectable()
export class CacheService {
  constructor(
    @Inject(CACHE_OPTIONS) private options: CacheModuleOptions,
  ) {}

  set(key: string, value: unknown) {
    const prefixedKey = `${this.options.prefix ?? ''}:${key}`;
    // ... кешировать с this.options.ttl
  }
}

// Использование:
CacheModule.registerAsync({
  imports: [ConfigModule],
  inject: [ConfigService],
  useFactory: (config: ConfigService) => ({
    ttl: config.get('CACHE_TTL', 3600),
    prefix: config.get('CACHE_PREFIX', 'app'),
  }),
})
```

## useClass и useExisting в Dynamic Modules

```typescript
// Иногда нужна конфигурация через класс (ConfigurableModuleBuilder)
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
      ? { provide: 'THROTTLER_OPTIONS', useFactory: options.useFactory, inject: options.inject }
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

```typescript
// NestJS 9+ предоставляет builder для упрощения создания Dynamic Modules
import { ConfigurableModuleBuilder } from '@nestjs/common';

export interface HttpModuleOptions {
  baseUrl: string;
  timeout?: number;
}

// Автоматически создаёт register, registerAsync, forRoot, forRootAsync
export const { ConfigurableModuleClass, MODULE_OPTIONS_TOKEN } =
  new ConfigurableModuleBuilder<HttpModuleOptions>()
    .setClassMethodName('forRoot')       // имя метода (по умолчанию 'register')
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
// Теперь HttpModule.forRoot() и HttpModule.forRootAsync() доступны автоматически

// HttpService получает опции через MODULE_OPTIONS_TOKEN:
@Injectable()
export class HttpService {
  constructor(
    @Inject(MODULE_OPTIONS_TOKEN) private options: HttpModuleOptions,
  ) {}
}
```

## Типичные ошибки на интервью

- **"Dynamic Module нельзя сделать глобальным"** — можно. Возврат `{ module, global: true, ... }` из `forRoot()` или добавление `@Global()` на класс делает все его exports доступными во всём приложении без явного импорта. ConfigModule.forRoot({ isGlobal: true }) — именно этот паттерн.

- **"register() и registerAsync() — одно и то же"** — нет. `register()` принимает готовые опции синхронно. `registerAsync()` принимает `useFactory` с `inject`, позволяя получить опции через DI (из ConfigService, SecretManager, etc.) асинхронно. Используй `registerAsync` когда конфиг зависит от других сервисов.

- **"DynamicModule должен возвращать только providers"** — нет. DynamicModule = полноценный ModuleMetadata + `module` поле: может содержать `imports`, `providers`, `exports`, `controllers`, `global`. Это полноценный модуль, созданный в runtime.

- **"forRoot и forFeature — просто конвенция"** — да, но важная. `forRoot` — инициализация один раз в корневом модуле (DB connection, JWT config). `forFeature` — регистрация feature-специфичных ресурсов (repository для конкретной сущности) в feature-модуле. Нарушение конвенции запутывает других разработчиков.

- **"Dynamic Module нельзя использовать с useClass/useExisting"** — можно. Provider в DynamicModule.providers может быть любым типом провайдера: useClass, useValue, useFactory, useExisting — всё работает так же как в статическом модуле.
