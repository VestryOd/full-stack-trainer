# Queries, Mutations и Subscriptions

## Три типа операций GraphQL

GraphQL поддерживает:

```txt
Query
Mutation
Subscription
```

---

# Query

Используется для чтения данных.

---

Аналог REST:

```http
GET
```

---

Пример:

```graphql
query {
  users {
    id
    name
  }
}
```

---

Ответ:

```json
{
  "data": {
    "users": [
      {
        "id": "1",
        "name": "Max"
      }
    ]
  }
}
```

---

# Query с аргументами

```graphql
query {
  user(id: 1) {
    name
  }
}
```

---

Schema:

```graphql
type Query {
  user(id: ID!): User
}
```

---

Resolver:

```ts
Query: {
  user: (_, args) => {
    return prisma.user.findUnique({
      where: {
        id: Number(args.id),
      },
    });
  },
}
```

---

# Aliases

Очень полезная фича.

---

Можно вызвать один resolver несколько раз.

---

```graphql
query {
  admin: user(id: 1) {
    name
  }

  manager: user(id: 2) {
    name
  }
}
```

---

Ответ:

```json
{
  "admin": {
    "name": "Max"
  },
  "manager": {
    "name": "John"
  }
}
```

---

# Fragments

Позволяют переиспользовать набор полей.

---

Без Fragment:

```graphql
user {
  id
  name
  email
}
```

---

```graphql
author {
  id
  name
  email
}
```

---

Повторение.

---

# С Fragment

```graphql
fragment UserFields on User {
  id
  name
  email
}
```

---

Использование:

```graphql
user {
  ...UserFields
}
```

---

# Variables

Очень любят спрашивать.

---

Плохо:

```graphql
query {
  user(id: 1)
}
```

---

Лучше:

```graphql
query GetUser($id: ID!) {
  user(id: $id) {
    name
  }
}
```

---

Variables:

```json
{
  "id": 1
}
```

---

# Mutation

Используется для изменения данных.

---

Аналог:

```http
POST
PUT
PATCH
DELETE
```

---

Пример:

```graphql
mutation {
  createUser(
    name: "Max"
  ) {
    id
    name
  }
}
```

---

Schema:

```graphql
type Mutation {
  createUser(
    name: String!
  ): User!
}
```

---

Resolver:

```ts
Mutation: {
  createUser: (_, args) => {
    return prisma.user.create({
      data: {
        name: args.name,
      },
    });
  },
}
```

---

# Input Types

Очень важная тема.

---

Плохо:

```graphql
createUser(
  name: String
  email: String
  age: Int
)
```

---

Хорошо:

```graphql
input CreateUserInput {
  name: String!
  email: String!
  age: Int
}
```

---

Mutation:

```graphql
createUser(
  input: CreateUserInput!
): User!
```

---

# Почему Input Types лучше

- легче расширять
- меньше аргументов
- удобнее валидировать

---

# Subscription

Очень популярный вопрос.

---

Subscription позволяет получать данные в realtime.

---

Пример:

```graphql
subscription {
  messageAdded {
    id
    text
  }
}
```

---

Когда появляется новое сообщение:

```txt
сервер сам отправляет событие
```

---

# Чем отличается от Query

Query:

```txt
request → response
```

---

Subscription:

```txt
request → постоянное соединение
```

---

# Обычно используется

```txt
WebSocket
```

---

# Примеры использования

```txt
чат
уведомления
биржа
игры
онлайн-трекинг
```

---

# NestJS Example

```ts
@Subscription(() => Message)
messageAdded() {
  return pubSub.asyncIterator([
    'MESSAGE_ADDED',
  ]);
}
```

---

# Когда Subscription не нужна

Большинство CRUD систем прекрасно работают без нее.

---

# Интервью вопрос

Когда использовать Query, Mutation и Subscription?

Ответ:

Query используется для чтения данных, Mutation — для изменения данных, Subscription — для получения realtime обновлений через постоянное соединение, обычно WebSocket.