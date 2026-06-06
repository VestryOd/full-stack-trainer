<!-- verified: 2026-06-05, corrections: 0 -->
# Schema, Types и Resolvers

## Сердце GraphQL

GraphQL построен вокруг схемы.

---

# Что такое Schema

Schema описывает:

```txt
какие данные доступны
```

---

Пример:

```graphql
type User {
  id: ID!
  name: String!
  email: String
}
```

---

Это контракт между сервером и клиентом.

---

# Scalar Types

Базовые типы.

---

GraphQL содержит:

```graphql
String
Int
Float
Boolean
ID
```

---

Пример:

```graphql
type User {
  id: ID!
  age: Int
}
```

---

# Non Null

Символ:

```graphql
!
```

---

Пример:

```graphql
name: String!
```

---

Означает:

```txt
поле никогда не будет null
```

---

# Lists

Массивы.

---

```graphql
posts: [Post]
```

---

Массив Post.

---

# Комбинации

Очень любят спрашивать.

---

```graphql
posts: [Post!]!
```

---

Расшифровка:

```txt
поле обязательно
элементы массива обязательны
```

---

# Object Types

Пользовательский тип.

---

```graphql
type User {
  id: ID!
  name: String!
}
```

---

# Relationships

GraphQL отлично описывает связи.

---

```graphql
type User {
  id: ID!
  posts: [Post!]!
}
```

---

```graphql
type Post {
  id: ID!
  title: String!
}
```

---

# Query Type

Точка входа для чтения данных.

---

```graphql
type Query {
  user(id: ID!): User
}
```

---

Пример запроса:

```graphql
query {
  user(id: 1) {
    name
  }
}
```

---

# Mutation Type

Точка входа для изменения данных.

---

```graphql
type Mutation {
  createUser(name: String!): User
}
```

---

# Resolver

Самая важная часть.

---

Schema отвечает:

```txt
Что существует?
```

---

Resolver отвечает:

```txt
Как получить данные?
```

---

Пример:

```ts
const resolvers = {
  Query: {
    user: (_, args) => {
      return db.user.findById(args.id);
    },
  },
};
```

---

# Resolver Signature

Очень популярный вопрос.

---

Resolver получает:

```ts
(parent, args, context, info)
```

---

# parent

Результат предыдущего resolver.

---

# args

Аргументы GraphQL запроса.

---

Пример:

```graphql
user(id: 1)
```

---

args:

```ts
{ id: 1 }
```

---

# context

Общие данные запроса.

---

Например:

```ts
{
  user,
  prisma,
  dataloaders
}
```

---

Очень часто используется для:

```txt
авторизации
Prisma
DataLoader
```

---

# info

Информация о GraphQL запросе.

---

Используется редко.

---

# Nested Resolvers

Пример:

```graphql
query {
  user(id: 1) {
    name
    posts {
      title
    }
  }
}
```

---

Выполняются:

```txt
Query.user
↓
User.posts
```

---

Каждое поле потенциально имеет свой resolver.

---

# Почему это важно

Именно здесь появляется:

```txt
N+1 Problem
```

---

Которую будем разбирать отдельно.

---

# Context

Очень популярный вопрос.

---

В NestJS:

```ts
GraphQLModule.forRoot({
  context: ({ req }) => ({
    user: req.user,
  }),
});
```

---

Теперь любой resolver может получить:

```ts
context.user
```

---

# Интервью вопрос

Почему GraphQL называют strongly typed?

Ответ:

Потому что схема строго описывает все доступные типы, поля и аргументы. Клиент знает структуру API ещё до выполнения запроса, а сервер валидирует запросы относительно схемы.