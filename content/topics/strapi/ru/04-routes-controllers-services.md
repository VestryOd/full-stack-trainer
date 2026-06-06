<!-- verified: 2026-06-05, corrections: 0 -->
# Routes, Controllers и Services

## Очень важное понимание

Strapi не просто хранит данные.

---

Под капотом это полноценный backend framework.

---

Есть:

```txt
Routes
Controllers
Services
Policies
Middlewares
```

---

Практически как NestJS.

---

# Автоматическая генерация

Создаем:

```txt
Article
```

---

Strapi автоматически генерирует:

```txt
Route
Controller
Service
```

---

Поэтому CRUD работает сразу.

---

# Routes

Route определяет:

```txt
какой URL
какой Controller
```

---

Пример:

```http
GET /api/articles
```

---

Привязывается к:

```txt
Article Controller
```

---

# Route Definition

Упрощенно:

```js
{
  method: 'GET',
  path: '/articles',
  handler: 'article.find'
}
```

---

# Controller

Очень похож на NestJS Controller.

---

Главная задача:

```txt
Request
↓
Response
```

---

Получить данные запроса.

---

Вызвать сервис.

---

Вернуть ответ.

---

# Пример

```js
async find(ctx) {
  return await strapi
    .service('api::article.article')
    .find();
}
```

---

# Что НЕ должен делать Controller

Очень популярный вопрос.

---

Не должен содержать:

```txt
сложную бизнес-логику
```

---

Потому что:

```txt
Controller становится толстым
```

---

# Service Layer

Вся бизнес-логика.

---

Например:

```txt
валидация
агрегация
вызов других API
работа с несколькими сущностями
```

---

# Пример

```js
async getPopularArticles() {

  return await strapi
    .documents('api::article.article')
    .findMany({
      sort: {
        views: 'desc'
      }
    });
}
```

---

# Почему нужен Service

Можно переиспользовать.

---

Например:

```txt
Controller A
Controller B
Lifecycle Hook
Cron Job
```

---

Все могут использовать один Service.

---

# Document Service

Начиная со Strapi 5.

---

Высокоуровневый API доступа к данным.

---

Пример:

```js
strapi.documents(
  'api::article.article'
)
.findMany();
```

---

# Query Engine

Более низкий уровень.

---

Используется если нужен
более тонкий контроль.

---

Обычно используют реже.

---

# Полный Flow

Запрос:

```http
GET /api/articles
```

---

Проходит:

```txt
Middleware
↓
Route
↓
Policy
↓
Controller
↓
Service
↓
Document Service
↓
Query Engine
↓
Database
```

---

Затем обратно:

```txt
Database
↓
Query Engine
↓
Service
↓
Controller
↓
Response
```

---

# Custom Route

Очень популярный вопрос.

---

Предположим нужен endpoint:

```http
GET /api/articles/popular
```

---

Создаем route.

---

```js
{
  method: 'GET',
  path: '/articles/popular',
  handler: 'article.popular'
}
```

---

# Custom Controller

```js
async popular(ctx) {

  return await strapi
    .service('api::article.article')
    .getPopularArticles();
}
```

---

# Custom Service

```js
async getPopularArticles() {

  return await strapi
    .documents('api::article.article')
    .findMany({
      sort: {
        views: 'desc'
      }
    });
}
```

---

# Очень похож на NestJS

Nest:

```txt
Controller
 ↓
Service
 ↓
Repository
```

---

Strapi:

```txt
Controller
 ↓
Service
 ↓
Document Service
 ↓
Query Engine
```

---

# Где писать бизнес-логику

Очень любят спрашивать.

---

Правильный ответ:

```txt
Service Layer
```

---

Не Controller.

---

# Частый вопрос

Зачем кастомизировать Controller,
если CRUD уже генерируется?

---

Ответ:

Когда нужен:

```txt
нестандартный endpoint
агрегация данных
интеграция с внешним API
сложная бизнес-логика
```

---

# Interview Answer

Strapi автоматически генерирует Routes, Controllers и Services для каждого Content Type. Route определяет endpoint, Controller отвечает за обработку запроса и формирование ответа, а Service содержит бизнес-логику. Для доступа к данным в Strapi v5 используется Document Service, который работает поверх Query Engine и базы данных.