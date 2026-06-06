<!-- verified: 2026-06-05, corrections: 0 -->
# Providers, Scopes и DI Container

## Самая важная идея NestJS

Практически весь Nest построен вокруг:

```txt
Dependency Injection
```

---

# Что такое Dependency

Пример.

---

```ts
class UserService {

  constructor(
    private db: DatabaseService
  ) {}
}
```

---

Здесь:

```txt
DatabaseService
```

является зависимостью.

---

# Без DI

Создаем вручную.

---

```ts
const db =
 new DatabaseService();

const service =
 new UserService(db);
```

---

Недостатки:

```txt
сильная связанность
сложно тестировать
сложно заменять реализации
```

---

# С DI

```ts
constructor(
 private db: DatabaseService
) {}
```

---

Nest сам создаст объект.

---

# Что такое DI Container

Самая популярная тема.

---

Упрощенно:

```txt
Map<Token, Instance>
```

---

Например:

```txt
UserService
 ↓
instance

DatabaseService
 ↓
instance
```

---

При старте приложения Nest строит:

```txt
Dependency Graph
```

---

# Dependency Graph

Пример.

---

```txt
UserController
      ↓
UserService
      ↓
DatabaseService
```

---

Nest анализирует:

```txt
constructor()
```

---

И понимает:

```txt
кого нужно создать первым
```

---

# Что происходит при старте

Шаг 1

Сканируются:

```txt
Modules
Providers
Controllers
```

---

Шаг 2

Создается Dependency Graph.

---

Шаг 3

Создаются экземпляры.

---

Шаг 4

Сохраняются в Container.

---

# Provider

Очень популярный вопрос.

---

Provider — любой объект,
который может участвовать в DI.

---

Например:

```ts
@Injectable()
export class UserService {}
```

---

Это Provider.

---

# Provider Token

Самая недооцененная тема.

---

Под капотом Nest ищет не класс.

---

Он ищет:

```txt
Token
```

---

Обычно токеном является класс.

---

Например:

```ts
UserService
```

---

Фактически:

```txt
Token → Instance
```

---

# Упрощенная схема

```txt
UserService
 ↓
new UserService()
```

---

Хранится в контейнере.

---

# Инъекция

```ts
constructor(
 private userService:
 UserService
)
```

---

Nest ищет:

```txt
Token = UserService
```

---

Находит instance.

---

Передает в конструктор.

---

# Custom Token

Очень любят спрашивать.

---

Можно использовать строку.

---

```ts
{
 provide: 'API_URL',
 useValue: 'https://...'
}
```

---

Инъекция:

```ts
@Inject('API_URL')
private url: string
```

---

# useClass

Самый простой вариант.

---

```ts
{
 provide: UserRepository,
 useClass: PrismaRepository
}
```

---

Что означает:

```txt
при запросе UserRepository
создать PrismaRepository
```

---

# useValue

Готовое значение.

---

```ts
{
 provide: 'CONFIG',
 useValue: {
  port: 3000
 }
}
```

---

Часто используют для:

```txt
config
constants
mocks
```

---

# useFactory

Очень популярный вопрос.

---

Позволяет создать объект динамически.

---

```ts
{
 provide: DatabaseClient,

 useFactory: () => {

  return new PrismaClient();
 }
}
```

---

# useFactory с зависимостями

```ts
{
 provide: ApiClient,

 inject: [ConfigService],

 useFactory: (config) => {

  return new ApiClient(
   config.get('url')
  );
 }
}
```

---

Очень часто используется.

---

# useExisting

Менее популярный.

---

```ts
{
 provide: UserRepo,
 useExisting:
 PrismaRepo
}
```

---

Оба токена будут указывать
на один объект.

---

# Scopes

Очень популярный Senior вопрос.

---

# Singleton

По умолчанию.

---

Создается:

```txt
один экземпляр
на всё приложение
```

---

```ts
@Injectable()
export class UserService {}
```

---

Singleton.

---

# Request Scope

```ts
@Injectable({
 scope: Scope.REQUEST
})
```

---

Новый экземпляр:

```txt
на каждый запрос
```

---

# Пример

```txt
Request 1
 ↓
UserService #1

Request 2
 ↓
UserService #2
```

---

# Transient Scope

Самый редкий.

---

```ts
Scope.TRANSIENT
```

---

Новый экземпляр:

```txt
каждая инъекция
```

---

# Когда нужен Request Scope

Например:

```txt
Tenant Context
Current User Context
Correlation ID
```

---

# Почему Request Scope опасен

Очень популярный вопрос.

---

Потому что:

```txt
создаются тысячи объектов
```

---

Сильнее нагрузка на GC.

---

Поэтому:

```txt
Singleton
```

предпочтительнее.

---

# Частый вопрос

Почему DI делает код лучше?

---

Ответ:

Позволяет инвертировать зависимости, уменьшает связанность компонентов, упрощает тестирование и замену реализаций.

---

# Interview Answer

NestJS использует Dependency Injection Container, который хранит объекты по токенам и автоматически разрешает зависимости через конструкторы. Providers являются основными элементами контейнера и могут создаваться через useClass, useValue, useFactory и useExisting. По умолчанию все провайдеры являются Singleton, но также поддерживаются Request и Transient Scope.