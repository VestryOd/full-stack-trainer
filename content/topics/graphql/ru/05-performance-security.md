<!-- verified: 2026-06-05, corrections: 0 -->
# GraphQL Performance and Security

## Главная проблема GraphQL

GraphQL очень гибкий.

---

Но эта гибкость может стать проблемой.

---

REST:

```txt
сервер полностью контролирует ответ
```

---

GraphQL:

```txt
клиент определяет структуру ответа
```

---

Поэтому клиент может случайно
или специально создать очень тяжелый запрос.

---

# Query Explosion

Представим:

```graphql
query {
  users {
    posts {
      comments {
        author {
          posts {
            comments {
              ...
            }
          }
        }
      }
    }
  }
}
```

---

Такой запрос может породить:

```txt
тысячи resolver вызовов
миллионы записей
огромную нагрузку
```

---

# Query Depth

Глубина запроса.

---

Пример:

```graphql
user {
  posts {
    comments {
      author {
        posts {
          title
        }
      }
    }
  }
}
```

---

Глубина:

```txt
5
```

---

# Depth Limiting

Популярная защита.

---

Например:

```txt
max depth = 5
```

---

Если клиент запросил:

```txt
depth = 10
```

---

Сервер отклоняет запрос.

---

# Query Complexity

Еще более продвинутый механизм.

---

Каждому полю назначается стоимость.

---

Например:

```txt
user      = 1
posts     = 10
comments  = 20
```

---

Запрос:

```graphql
users {
  posts {
    comments {
      id
    }
  }
}
```

---

Может иметь стоимость:

```txt
31
```

---

Если лимит:

```txt
20
```

---

Запрос блокируется.

---

# Rate Limiting

GraphQL не отменяет классические механизмы защиты.

---

Например:

```txt
100 запросов / минута
```

---

Обычно используют:

```txt
Redis
API Gateway
NestJS Throttler
```

---

# N+1

Мы уже разбирали.

---

Очень часто главная проблема производительности.

---

Решение:

```txt
DataLoader
```

---

# Pagination

Обязательна для больших коллекций.

---

Плохо:

```graphql
users {
  ...
}
```

---

Хорошо:

```graphql
users(
  limit: 20
)
```

---

Еще лучше:

```txt
Cursor Pagination
```

---

# Cursor Pagination

Очень популярный вопрос.

---

Вместо:

```txt
offset = 100000
```

---

Используем:

```txt
cursor = userId
```

---

Обычно работает быстрее.

---

# Caching

Сложнее чем в REST.

---

Почему?

---

REST:

```http
GET /users/1
```

---

Можно кешировать URL.

---

GraphQL:

```txt
все запросы идут на /graphql
```

---

Кешировать сложнее.

---

# Persisted Queries

Очень популярная техника.

---

Клиент заранее регистрирует запрос.

---

Вместо:

```graphql
полный запрос
```

---

Отправляется:

```txt
query hash
```

---

Плюсы:

```txt
меньше трафика
лучше кеширование
безопаснее
```

---

# Introspection Security

Очень любят спрашивать.

---

GraphQL может описывать сам себя.

---

Например:

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

На production часто отключают.

---

Почему?

---

Чтобы злоумышленник не получил
полное описание API.

---

# Authorization

Очень важный вопрос.

---

Плохо:

```txt
защищать только endpoint
```

---

Потому что endpoint всегда один.

---

Защита должна быть:

```txt
на уровне resolver
```

---

Например:

```ts
@UseGuards(AuthGuard)
```

---

или

```ts
if (!context.user) {
  throw new Error();
}
```

---

# Federation

Очень популярный senior вопрос.

---

Что делать если:

```txt
десятки GraphQL сервисов
```

---

Решение:

```txt
Apollo Federation
```

---

Схема:

```txt
User Service
Post Service
Comment Service
       ↓
Apollo Gateway
```

---

Клиент видит:

```txt
один GraphQL API
```

---

Хотя внутри много сервисов.

---

# Частый вопрос

Почему GraphQL может быть опаснее REST?

---

Ответ:

Потому что клиент может формировать очень сложные запросы, вызывающие высокую нагрузку. Поэтому GraphQL требует дополнительных механизмов защиты: depth limiting, query complexity analysis, pagination и rate limiting.

---

# Interview Answer

Основные проблемы производительности GraphQL связаны с N+1 запросами, глубокими вложенными запросами и отсутствием встроенного кеширования. Для решения используются DataLoader, pagination, query complexity analysis, depth limiting, persisted queries и Federation.