<!-- verified: 2026-06-05, corrections: 0 -->
# GraphQL vs REST

## Самый популярный вопрос

Когда использовать GraphQL,
а когда REST?

---

# REST

Ресурсно-ориентированный подход.

---

Пример:

```http
GET /users
GET /users/1
POST /users
DELETE /users/1
```

---

Каждый endpoint отвечает
за конкретный ресурс.

---

# GraphQL

Один endpoint.

---

Обычно:

```txt
/graphql
```

---

Клиент сам определяет данные.

---

# Главная разница

REST:

```txt
сервер определяет ответ
```

---

GraphQL:

```txt
клиент определяет ответ
```

---

# Overfetching

REST:

```http
GET /user/1
```

---

Получили:

```json
{
  "id": 1,
  "name": "Max",
  "email": "...",
  "avatar": "...",
  "settings": ...
}
```

---

Нужен только:

```txt
name
```

---

Получаем overfetching.

---

# GraphQL

```graphql
query {
  user(id:1) {
    name
  }
}
```

---

Получаем ровно одно поле.

---

# Underfetching

REST:

```txt
User
Posts
Comments
```

---

Три запроса.

---

GraphQL:

```graphql
query {
  user {
    posts {
      comments {
        text
      }
    }
  }
}
```

---

Один запрос.

---

# Типизация

REST:

```txt
не стандартизирована
```

---

GraphQL:

```txt
строгая схема
```

---

# Self Documentation

GraphQL:

```txt
Introspection
```

---

Клиент может узнать API автоматически.

---

REST:

```txt
Swagger/OpenAPI
```

нужно поддерживать отдельно.

---

# Caching

Здесь REST выигрывает.

---

REST:

```txt
URL-based caching
CDN caching
ETag
```

---

GraphQL:

```txt
сложнее
```

---

Потому что endpoint один.

---

# Complexity

REST проще.

---

GraphQL сложнее.

---

Появляются:

```txt
Resolvers
DataLoader
Federation
Query Complexity
```

---

# Mobile Applications

Очень хороший кейс для GraphQL.

---

Почему?

---

Мобильные устройства чувствительны к:

```txt
количеству запросов
объему данных
```

---

GraphQL помогает уменьшить оба параметра.

---

# Microservices

GraphQL часто используется как:

```txt
BFF
Backend For Frontend
```

---

Схема:

```txt
Frontend
   ↓
GraphQL Gateway
   ↓
Microservices
```

---

# Когда выбирать REST

- простое CRUD API
- публичный API
- высокая кешируемость
- небольшая команда

---

# Когда выбирать GraphQL

- сложные UI
- много экранов
- mobile apps
- BFF layer
- много связанных данных

---

# Частый вопрос

GraphQL заменяет REST?

---

Ответ:

Нет.

---

Они решают разные задачи.

---

Сегодня очень часто используют:

```txt
REST + GraphQL
```

в одном проекте.

---

# Interview Answer

REST проще, лучше кешируется и отлично подходит для CRUD API. GraphQL предоставляет гибкость клиенту, решает проблемы overfetching и underfetching и особенно полезен для сложных frontend приложений и BFF архитектур. На практике обе технологии часто используются совместно.