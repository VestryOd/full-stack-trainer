# Providers, Scopes и DI Container

## Как работает DI Container в NestJS

NestJS DI Container — реестр провайдеров. При старте приложения Nest сканирует все модули, строит граф зависимостей (какой провайдер от каких других зависит), и создаёт экземпляры в правильном топологическом порядке. Под капотом: `Map<Token, { instance, scope, dependencies }>`.

```typescript
// При старте Nest делает это автоматически:
// 1. Сканирует @Module({ providers: [UserService, PrismaService] })
// 2. Видит: UserService конструктор требует PrismaService
// 3. Строит граф: PrismaService → UserService → UsersController
// 4. Создаёт в порядке: PrismaService → UserService → UsersController
// 5. Сохраняет все instances в Container

@Injectable()
export class PrismaService { ... }

@Injectable()
export class UserService {
  constructor(private prisma: PrismaService) {}
  // Nest читает TypeScript metadata: constructor param type = PrismaService
  // Ищет в Container по токену PrismaService → передаёт instance
}

@Controller('users')
export class UsersController {
  constructor(private users: UserService) {}
}
```

## Типы провайдеров — useClass, useValue, useFactory, useExisting

```typescript
// Module providers — расширенный синтаксис
@Module({
  providers: [
    // 1. Short syntax (useClass подразумевается)
    UserService,
    // эквивалентно: { provide: UserService, useClass: UserService }

    // 2. useClass — подменить реализацию через интерфейс
    { provide: UserRepository, useClass: PrismaUserRepository },
    // Инъекция: constructor(private repo: UserRepository) — получит PrismaUserRepository

    // 3. useValue — статическое значение (конфиг, моки)
    { provide: 'JWT_SECRET', useValue: process.env.JWT_SECRET },
    { provide: 'APP_CONFIG', useValue: { port: 3000, debug: false } },

    // 4. useFactory — создать динамически (асинхронно)
    {
      provide: 'REDIS_CLIENT',
      inject: [ConfigService],
      useFactory: async (config: ConfigService) => {
        const client = createClient({ url: config.get('REDIS_URL') });
        await client.connect();
        return client;
      },
    },

    // 5. useExisting — алиас: два токена → один instance
    { provide: 'IUserService', useExisting: UserService },
    // Оба токена указывают на один и тот же экземпляр UserService
  ],
})
export class UsersModule {}

// Инъекция кастомного токена (@Inject обязателен для не-классовых токенов):
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

// Singleton (default) — один экземпляр на всё приложение
@Injectable()
export class UserService { ... }
// эквивалентно: @Injectable({ scope: Scope.DEFAULT })

// Request Scope — новый экземпляр на каждый HTTP запрос
@Injectable({ scope: Scope.REQUEST })
export class RequestContextService {
  private readonly requestId = Math.random().toString(36);

  getRequestId() { return this.requestId; }
}
// Каждый запрос получает свой экземпляр с уникальным requestId

// Transient Scope — новый экземпляр при каждой инъекции
@Injectable({ scope: Scope.TRANSIENT })
export class LoggerService {
  private context: string;

  setContext(ctx: string) { this.context = ctx; }
  log(msg: string) { console.log(`[${this.context}] ${msg}`); }
}
// UsersService и PostsService получат РАЗНЫЕ LoggerService instances
```

```txt
Scope.DEFAULT (Singleton):
  Создаётся: 1 раз при старте
  Уничтожается: при завершении приложения
  Использование: 95% всех провайдеров

Scope.REQUEST:
  Создаётся: при каждом HTTP запросе
  Уничтожается: когда запрос завершён
  Использование: tenant context, request-specific data
  Предупреждение: "scope bubble up" — все зависимости тоже становятся REQUEST

Scope.TRANSIENT:
  Создаётся: при каждой инъекции (каждый потребитель получает свой instance)
  Использование: контекстуализированные логгеры
  Редко нужен: в большинстве случаев Singleton достаточен
```

## Scope Bubble Up — важный эффект

```typescript
// ПРОБЛЕМА: если REQUEST-scoped провайдер инжектируется в Singleton,
// Singleton тоже становится REQUEST-scoped (NestJS делает это автоматически)

@Injectable({ scope: Scope.REQUEST })
export class RequestContext {
  constructor(@Inject(REQUEST) private request: Request) {}
  getUserId() { return this.request['user']?.id; }
}

// UserService был Singleton, но теперь автоматически стал REQUEST
// потому что зависит от REQUEST-scoped RequestContext
@Injectable()
export class UserService {
  constructor(private context: RequestContext) {}
  // ⚠️ UserService неявно стал REQUEST-scoped!
}

// Альтернатива без bubble up: передавать userId явно через параметр метода
@Injectable()
export class UserService {
  async getUser(userId: string) { ... } // userId передаётся явно, не через контекст
}
```

## InjectionToken — типобезопасный токен

```typescript
// Строковые токены ('JWT_SECRET') — риск typo
// Решение: InjectionToken<T> для типобезопасности

import { InjectionToken } from '@nestjs/common';

export const JWT_SECRET = new InjectionToken<string>('JWT_SECRET');
export const REDIS_CLIENT = new InjectionToken<RedisClientType>('REDIS_CLIENT');

// В Module:
{ provide: JWT_SECRET, useValue: process.env.JWT_SECRET }

// Инъекция — TypeScript знает тип:
constructor(@Inject(JWT_SECRET) private jwtSecret: string) {}
// vs строковый токен: тип приходится указывать вручную
```

## Circular Dependencies — как решить

```typescript
// Проблема: A зависит от B, B зависит от A → circular dependency

// Решение 1: forwardRef() — отложенная ссылка
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

// В Module тоже нужен forwardRef:
@Module({
  imports: [forwardRef(() => UsersModule)],
})
export class AuthModule {}

// Решение 2 (лучше): вынести общую логику в третий сервис
// AuthSharedService без циклической зависимости
```

## Типичные ошибки на интервью

- **"@Injectable() создаёт экземпляр"** — нет. `@Injectable()` добавляет metadata (`scope`, `token`) что позволяет Nest обнаружить класс как провайдер и управлять его жизненным циклом. Экземпляр создаётся DI Container при старте (или при запросе для REQUEST scope).

- **"Все провайдеры в приложении доступны везде"** — нет. Провайдер доступен только в том модуле, где объявлен в `providers`. Для использования в другом модуле: добавить в `exports` исходного модуля и импортировать модуль. Исключение: `@Global()` модуль — его экспорты доступны везде без явного импорта.

- **"useFactory выполняется каждый запрос"** — нет для Singleton scope. Factory вызывается ОДИН РАЗ при старте и возвращает instance, который сохраняется в Container. Для REQUEST scope: factory вызывается каждый запрос.

- **"Request Scope — хорошая альтернатива AsyncLocalStorage"** — оба решают задачу request-specific данных. REQUEST scope: создаёт новый провайдер (и всю цепочку зависимостей) на каждый запрос — overhead на GC. AsyncLocalStorage: единственный Singleton, данные хранятся в async контексте — эффективнее. Для высоконагруженных API: AsyncLocalStorage предпочтительнее.

- **"TOKEN должен быть строкой"** — нет. Token может быть: классом (самый частый), строкой, Symbol, или `InjectionToken<T>`. InjectionToken рекомендован для кастомных токенов — типобезопасен, исключает typo, в отличие от строки.
