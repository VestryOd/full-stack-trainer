<!-- verified: 2026-06-05, corrections: 0 -->
# CQRS Pattern

## Очень популярная Senior тема

Что такое:

```txt
CQRS
```

---

Расшифровка:

```txt
Command Query Responsibility Segregation
```

---

Разделение:

```txt
Чтение
```

и

```txt
Запись
```

---

# Обычный сервис

Например:

```ts
class UserService {

 createUser()

 updateUser()

 deleteUser()

 getUser()

 getUsers()
}
```

---

Всё в одном месте.

---

# CQRS

Разделяем.

---

```txt
Commands
```

отвечают за:

```txt
изменение состояния
```

---

```txt
Queries
```

отвечают за:

```txt
чтение данных
```

---

# Пример

Command:

```txt
CreateUser
```

---

Query:

```txt
GetUser
```

---

Разные объекты.

---

# Почему появился CQRS

Очень популярный вопрос.

---

Причина:

```txt
чтение и запись
часто масштабируются
по-разному
```

---

# Пример

Интернет-магазин.

---

Записей:

```txt
100 заказов
```

---

Чтений:

```txt
100000 просмотров
```

---

Нагрузка разная.

---

# Основные элементы

В Nest CQRS используются:

```txt
Command

CommandHandler

Query

QueryHandler

Event

EventHandler
```

---

# Command

Команда описывает действие.

---

```ts
export class CreateUserCommand {

 constructor(
  public email: string
 ) {}
}
```

---

# Command Handler

Выполняет действие.

---

```ts
@CommandHandler(
 CreateUserCommand
)
export class
CreateUserHandler {

 async execute(
  command
 ) {}
}
```

---

# Выполнение

Через:

```ts
commandBus.execute(...)
```

---

Пример:

```ts
await this.commandBus.execute(
 new CreateUserCommand(
  email
 )
);
```

---

# Query

Описывает запрос.

---

```ts
export class GetUserQuery {

 constructor(
  public id: string
 ) {}
}
```

---

# Query Handler

```ts
@QueryHandler(
 GetUserQuery
)
```

---

Возвращает данные.

---

# Выполнение

```ts
queryBus.execute(...)
```

---

# Event

Очень популярная тема.

---

После создания пользователя:

```txt
UserCreatedEvent
```

---

# Зачем

Чтобы не связывать код напрямую.

---

Вместо:

```txt
Create User
 ↓
Send Email
 ↓
Create Audit
 ↓
Update CRM
```

---

Получаем:

```txt
Create User
 ↓
Publish Event
```

---

А подписчики реагируют сами.

---

# Event Handler

```ts
@EventsHandler(
 UserCreatedEvent
)
```

---

Обрабатывает событие.

---

# Flow

```txt
Command
 ↓
Command Handler
 ↓
Database
 ↓
Event
 ↓
Event Handlers
```

---

# Когда CQRS оправдан

Очень популярный вопрос.

---

Подходит:

```txt
сложный домен

много бизнес логики

event driven architecture

microservices
```

---

# Когда CQRS НЕ нужен

Еще популярнее.

---

Плохо:

```txt
CRUD приложение
```

---

Например:

```txt
Admin Panel

Simple CMS

Internal Tool
```

---

Только усложнит код.

---

# CQRS в Nest

Пакет:

```ts
@nestjs/cqrs
```

---

Модули:

```ts
CommandBus

QueryBus

EventBus
```

---

# Плюсы

```txt
разделение ответственности

явная бизнес логика

масштабируемость

event driven architecture
```

---

# Минусы

Очень любят спрашивать.

---

```txt
много файлов

больше boilerplate

сложнее поддерживать
```

---

# Частый вопрос

CQRS всегда нужен?

Ответ:

Нет.

---

Для большинства CRUD систем
обычный Service Layer проще.

---

# Частый вопрос

Чем Command отличается от Query?

---

Command:

```txt
изменяет состояние
```

---

Query:

```txt
только читает
```

---

# Частый вопрос

Как связаны CQRS и Event Sourcing?

---

CQRS:

```txt
может использоваться отдельно
```

---

Event Sourcing:

```txt
часто строится поверх CQRS
```

---

Но это разные паттерны.

---

# Interview Answer

CQRS разделяет операции чтения и записи на отдельные модели. Commands отвечают за изменение состояния системы, Queries — за получение данных. В NestJS CQRS реализуется через CommandBus, QueryBus и EventBus. Этот подход полезен для сложных доменных систем, но часто является избыточным для простых CRUD приложений.