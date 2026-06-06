<!-- verified: 2026-06-05, corrections: 0 -->
# GraphQL Fundamentals

## Что такое GraphQL

GraphQL — это язык запросов к API и runtime для выполнения этих запросов.

Разработан Facebook в 2015 году.

---

# Почему появился GraphQL

До GraphQL большинство API строились через REST.

Например:

```txt
GET /users/1
GET /users/1/posts
GET /users/1/comments
```

---

Для получения сложных данных клиенту часто приходилось делать много запросов.

---

# Проблема Overfetching

REST:

```http
GET /users/1
```

Возвращает:

```json
{
  "id": 1,
  "name": "Max",
  "email": "max@test.com",
  "avatar": "...",
  "createdAt": "...",
  "updatedAt": "..."
}
```

---

Но клиенту нужен только:

```json
{
  "name": "Max"
}
```

---

Получаем:

```txt
Overfetching
```

Получили больше данных, чем нужно.

---

# Проблема Underfetching

Нужны:

```txt
User
Posts
Comments
```

---

Приходится делать:

```txt
3 REST запроса
```

---

Получаем:

```txt
Underfetching
```

---

# Решение GraphQL

Клиент сам описывает,
какие данные нужны.

---

Пример:

```graphql
query {
  user(id: 1) {
    name
  }
}
```

---

Ответ:

```json
{
  "data": {
    "user": {
      "name": "Max"
    }
  }
}
```

---

Получаем только нужные поля.

---

# Главная идея GraphQL

REST:

```txt
Сервер определяет структуру ответа
```

---

GraphQL:

```txt
Клиент определяет структуру ответа
```

---

# GraphQL состоит из двух частей

Schema

+

Resolvers

---

# Schema

Описывает:

```txt
какие данные существуют
```

---

# Resolver

Описывает:

```txt
как получить данные
```

---

# Архитектура

Client
↓
GraphQL Query
↓
GraphQL Server
↓
Resolvers
↓
Database / Services

---

# Один Endpoint

Очень популярный вопрос.

---

REST:

```txt
/users
/posts
/comments
```

---

GraphQL обычно:

```txt
/graphql
```

---

Все запросы идут через один endpoint.

---

# Introspection

GraphQL умеет описывать сам себя.

---

Клиент может спросить:

```graphql
{
  __schema {
    types {
      name
    }
  }
}
```

---

И получить описание API.

---

# Почему это удобно

Автоматически работают:

- Playground
- GraphiQL
- Apollo Studio
- Code Generation

---

# Strongly Typed API

GraphQL имеет строгую типизацию.

---

Пример:

```graphql
type User {
  id: ID!
  name: String!
}
```

---

Если типы не совпадают:

```txt
ошибка выполнения
```

---

# Главный плюс GraphQL

Клиент получает ровно те данные,
которые запросил.

---

# Главный минус

Сложнее кеширование.

Сложнее защита.

Сложнее оптимизация.

---

# Interview Answer

GraphQL — это язык запросов к API и runtime для их выполнения. В отличие от REST, GraphQL позволяет клиенту самостоятельно определять структуру ответа, что решает проблемы overfetching и underfetching. GraphQL API обычно строится вокруг схемы типов и набора resolvers.