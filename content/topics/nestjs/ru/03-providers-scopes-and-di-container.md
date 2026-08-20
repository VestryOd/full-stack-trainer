# Провайдеры, области видимости и DI-контейнер

## Как работает DI-контейнер в NestJS

DI-контейнер (dependency injection — внедрение зависимостей) — это реестр провайдеров. Вы нигде не пишете `new UserService(...)`: класс объявляет свои зависимости в конструкторе, а контейнер их находит и подставляет сам.

На старте приложения Nest делает три шага:

1. Сканирует все модули и собирает список провайдеров.
2. Строит граф зависимостей: какой провайдер от каких других зависит.
3. Создаёт экземпляры в топологическом порядке — сначала зависимость, потом тот, кто её просит.

Внутри контейнер — это словарь вида `Map<Token, { instance, scope, dependencies }>`. Токен — ключ, по которому провайдера ищут; чаще всего это сам класс.

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

Запись провайдера отвечает на два вопроса: под каким токеном его искать (`provide`) и как получить значение. За «как» отвечает одно из четырёх полей:

- `useClass` — создать экземпляр указанного класса. Так можно подменить реализацию, не меняя код потребителей.
- `useValue` — взять готовое значение: строку из окружения, объект конфигурации, мок в тесте.
- `useFactory` — вызвать функцию и взять то, что она вернула. Функция может быть асинхронной и сама получать зависимости через `inject`.
- `useExisting` — сделать второй токен псевдонимом первого. Экземпляр остаётся один.

Короткая запись `providers: [UserService]` — это тот же `useClass`, просто с одинаковым токеном и классом.

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

## Области видимости — Singleton, Request, Transient

Область видимости (scope) отвечает на один вопрос: сколько экземпляров провайдера живёт в приложении и когда они создаются. Вариантов три:

- **Singleton** (`Scope.DEFAULT`, по умолчанию) — один экземпляр на всё приложение.
- **Request** (`Scope.REQUEST`) — новый экземпляр на каждый входящий запрос.
- **Transient** (`Scope.TRANSIENT`) — новый экземпляр на каждую инъекцию, то есть у каждого потребителя свой.

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
  Создаётся: один раз при старте
  Уничтожается: при остановке приложения
  Где применяется: 95% всех провайдеров

Scope.REQUEST:
  Создаётся: на каждый HTTP-запрос
  Уничтожается: когда запрос завершён
  Где применяется: данные клиента (tenant), данные запроса
  Осторожно: всплытие scope — потребители тоже станут REQUEST

Scope.TRANSIENT:
  Создаётся: на каждую инъекцию, свой экземпляр
    каждому потребителю
  Где применяется: логгеры с контекстом
  Нужен редко: обычно достаточно Singleton
```

## Всплытие области видимости — важный побочный эффект

Область видимости заразна и распространяется вверх по графу зависимостей. Стоит Singleton-провайдеру попросить в конструкторе REQUEST-провайдера, и он сам молча становится REQUEST-провайдером. Nest не ругается и ничего не пишет в лог.

Дальше это идёт по цепочке: тот, кто зависит от ставшего REQUEST провайдера, тоже становится REQUEST. Так один провайдер может перевести половину приложения на пересоздание при каждом запросе.

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

Токен-строка работает, но у неё две беды. Опечатку в `'JWT_SECRET'` компилятор не заметит, а тип значения приходится указывать руками на каждой инъекции.

Типизированный токен решает и то и другое: имя пишется один раз в константе, а тип значения хранится в самом токене.

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

## Циклические зависимости — как их развязать

Циклическая зависимость — это когда класс `A` просит в конструкторе `B`, а `B` просит обратно `A`. Контейнер не может создать ни одного из них первым. Поэтому на этапе построения графа один из аргументов конструктора оказывается `undefined`.

`forwardRef(() => Class)` откладывает вычисление ссылки на класс до момента, когда оба класса уже загружены. Обёртка нужна в двух местах: у инъекции и у импорта модуля.

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

- **"@Injectable() создаёт экземпляр"** — нет. Декоратор только добавляет метаданные (`scope`, токен), по которым Nest узнаёт класс как провайдер и берёт на себя его жизненный цикл. Экземпляр создаёт DI-контейнер: на старте приложения или на запросе, если область видимости REQUEST.

- **"Все провайдеры в приложении доступны везде"** — нет. Провайдер виден только внутри того модуля, где он объявлен в `providers`. Чтобы им пользовался другой модуль, добавьте его в `exports` исходного модуля и импортируйте сам модуль. Исключение — модуль с `@Global()`: его экспорты видны везде без явного импорта.

- **"useFactory выполняется на каждый запрос"** — нет, если область видимости Singleton. Тогда фабрику вызывают **один раз** на старте, а результат кладут в контейнер. Для REQUEST-провайдера всё иначе: фабрика действительно вызывается на каждый запрос.

- **"Request Scope — хорошая альтернатива AsyncLocalStorage"** — обе вещи решают одну задачу: дать сервису данные текущего запроса. REQUEST-провайдер создаётся заново вместе со всей цепочкой зависимостей, а это лишняя работа для сборщика мусора (GC, garbage collector). AsyncLocalStorage оставляет один Singleton и держит данные в контексте асинхронного вызова. Для API под высокой нагрузкой выбирайте AsyncLocalStorage.

- **"Токен должен быть строкой"** — нет. Токеном может быть класс (самый частый случай), строка, `Symbol` или `InjectionToken<T>`. Для своих токенов рекомендуют `InjectionToken<T>`: он типизирован и, в отличие от строки, не даст опечатке пройти мимо компилятора.
