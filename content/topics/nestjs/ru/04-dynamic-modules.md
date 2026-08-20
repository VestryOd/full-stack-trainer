# Динамические модули

## Зачем нужны динамические модули

У статического `@Module({ providers: [...] })` конфигурация зафиксирована в коде. Подключить такой модуль дважды с разными настройками нельзя.

Динамический модуль снимает это ограничение: настройки передаются в момент импорта — `JwtModule.register({ secret: env.JWT_SECRET })`. JWT (JSON Web Token) — подписанный токен для аутентификации, и секрет для подписи известен только в рантайме.

Механика простая. Статический метод возвращает объект `DynamicModule` — те же метаданные модуля (`ModuleMetadata`) плюс поле `module`, но собранные во время выполнения.

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

Это четыре имени одного механизма: все они статические методы, и все возвращают `DynamicModule`. Различается то, что имя обещает читателю:

- `register(options)` — опции известны прямо в месте вызова.
- `registerAsync({ inject, useFactory })` — опции надо сначала получить: из `ConfigService`, из хранилища секретов. Фабрика может быть асинхронной.
- `forRoot(options)` — инициализация на всё приложение, вызывается один раз в корневом модуле.
- `forFeature(...)` — регистрация того, что нужно одной конкретной фиче, внутри её модуля.

Суффикс `Async` работает одинаково для обеих пар, поэтому у модулей встречается и `forRootAsync`.

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
TypeOrmModule.forRoot({               // в AppModule: подключение к базе данных
  type: 'postgres',
  url: process.env.DATABASE_URL,
  autoLoadEntities: true,
})
TypeOrmModule.forFeature([User, Post]) // в UsersModule: регистрация репозиториев
```

## Свой динамический модуль

Свой динамический модуль — это класс с пустым `@Module({})` и статическим методом, который возвращает `DynamicModule`. Опции кладут в контейнер как обычный провайдер, а сервис модуля получает их через `@Inject`.

Ниже — модуль кеша с настройкой TTL (time to live — сколько секунд запись живёт в кеше). Методов два: `register` для готовых опций и `registerAsync`, когда опции приходят из `ConfigService`.

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

## useClass и useExisting в динамическом модуле

Опции можно отдавать не только фабрикой. `useClass` просит Nest создать класс, который эти опции предоставит, а `useExisting` берёт уже существующий провайдер с тем же интерфейсом.

Так устроены официальные модули: один метод принимает любой из трёх способов, а внутри собирает из них один и тот же провайдер опций.

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

`ConfigurableModuleBuilder` избавляет от ручного написания этих методов. Вы описываете тип опций, а билдер отдаёт базовый класс с готовыми `register`/`registerAsync` и токен, по которому опции лежат в контейнере.

Имя метода настраивается: `setClassMethodName('forRoot')` даёт `forRoot` и `forRootAsync` вместо `register`. Билдер появился в NestJS 9.

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

- **"Динамический модуль нельзя сделать глобальным"** — можно, двумя способами. Вернуть из `forRoot()` объект с полем `global: true` или навесить `@Global()` на класс. После этого экспорты модуля видны во всём приложении без явного импорта. `ConfigModule.forRoot({ isGlobal: true })` — ровно этот приём.

- **"register() и registerAsync() — одно и то же"** — нет. Простой `register()` принимает готовые опции синхронно. Асинхронная версия принимает `useFactory` вместе с `inject`, поэтому опции можно получить через контейнер: из `ConfigService`, из менеджера секретов. Берите `registerAsync`, когда конфигурация зависит от других сервисов.

- **"DynamicModule должен возвращать только providers"** — нет. Это полноценные метаданные модуля плюс поле `module`, то есть внутри могут быть `imports`, `providers`, `exports`, `controllers` и `global`. Обычный модуль, просто собранный во время выполнения.

- **"forRoot и forFeature — просто конвенция"** — конвенция, но важная. Имя `forRoot` обещает однократную инициализацию в корневом модуле: подключение к базе данных, настройки подписи токенов. Имя `forFeature` обещает ресурсы одной фичи, например репозиторий для конкретной сущности. Имя, которое обещает не то, что делает метод, сбивает с толку всю команду.

- **"Динамический модуль нельзя использовать с useClass/useExisting"** — можно. Провайдер внутри `DynamicModule.providers` бывает любого типа: `useClass`, `useValue`, `useFactory`, `useExisting`. Всё работает так же, как в статическом модуле.
