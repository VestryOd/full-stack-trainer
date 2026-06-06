<!-- verified: 2026-06-05, corrections: 0 -->
# ExecutionContext и Reflection

## Самая недооцененная тема NestJS

Очень многие используют:

```ts
@UseGuards()
@Roles()
@Auth()
```

---

Но не понимают:

```txt
как это работает под капотом
```

---

Для понимания нужно знать:

```txt
ExecutionContext
Reflect Metadata
```

---

# Что такое ExecutionContext

ExecutionContext описывает:

```txt
контекст текущего запроса
```

---

Упрощенно:

```txt
кто вызвал
что вызвал
какие аргументы
какой handler
какой controller
```

---

# Где используется

Практически везде.

---

Например:

```txt
Guards
Interceptors
Filters
Custom Decorators
```

---

# Пример

```ts
canActivate(
  context: ExecutionContext
)
```

---

Каждый Guard получает:

```ts
ExecutionContext
```

---

# Что можно получить

Handler:

```ts
context.getHandler()
```

---

Controller:

```ts
context.getClass()
```

---

# HTTP Context

Самый частый кейс.

---

```ts
const req =
  context
    .switchToHttp()
    .getRequest();
```

---

Теперь доступен:

```ts
req.user
req.headers
req.params
```

---

# Почему switchToHttp()

Очень популярный вопрос.

---

Nest поддерживает:

```txt
HTTP
GraphQL
WebSockets
Microservices
```

---

Поэтому контекст абстрактный.

---

Нужно явно переключиться.

---

# Другие варианты

```ts
switchToWs()
```

---

```ts
switchToRpc()
```

---

# getHandler()

Очень любят спрашивать.

---

Возвращает:

```txt
текущий метод
```

---

Например:

```ts
@Get()
findUsers()
```

---

Вернется:

```txt
findUsers
```

---

# getClass()

Возвращает:

```txt
контроллер
```

---

Например:

```ts
UsersController
```

---

# Что такое Reflection

Следующая важная тема.

---

Reflection позволяет:

```txt
читать metadata
во время выполнения
```

---

# Metadata

Дополнительные данные,
которые мы вешаем на класс
или метод.

---

Пример:

```ts
@Roles('admin')
```

---

Где-то нужно сохранить:

```txt
admin
```

---

Для этого используется metadata.

---

# Под капотом

Пример.

---

```ts
Reflect.defineMetadata(
  'roles',
  ['admin'],
  target
);
```

---

Позже:

```ts
Reflect.getMetadata(
  'roles',
  target
);
```

---

# Почему это важно

Почти весь Nest построен вокруг metadata.

---

Например:

```txt
@Controller
@Get
@Post
@Roles
@UseGuards
@Inject
```

---

Все используют metadata.

---

# Reflector

Специальный сервис Nest.

---

Используется для чтения metadata.

---

```ts
constructor(
 private reflector: Reflector
) {}
```

---

Пример:

```ts
const roles =
 this.reflector.get(
   'roles',
   context.getHandler()
 );
```

---

# Частый вопрос

Как работает @Roles()?

Ответ:

Декоратор сохраняет роли в metadata через Reflect Metadata. Затем Guard читает эту metadata через Reflector и принимает решение о доступе.

---

# Interview Answer

ExecutionContext предоставляет информацию о текущем запросе и используется в Guards, Interceptors и Filters. Reflect Metadata позволяет сохранять дополнительные данные на классах и методах. Большинство декораторов NestJS работают через механизм metadata и читаются во время выполнения через сервис Reflector.