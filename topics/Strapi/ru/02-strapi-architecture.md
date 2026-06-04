# Strapi Architecture

## Самое важное понимание

Strapi — это не просто CMS.

---

Под капотом это полноценное Node.js приложение.

---

Упрощенная схема:

```txt
Request
 ↓
Koa Middleware
 ↓
Route
 ↓
Policy
 ↓
Controller
 ↓
Service
 ↓
Document Service / Query Engine
 ↓
Database
```

---

Очень похоже на NestJS.

---

# Под капотом Koa

Очень популярный вопрос.

---

Strapi использует:

```txt
Koa
```

а не Express.

---

# Что такое Koa

Минималистичный Node.js framework,
созданный командой Express.

---

Главная идея:

```txt
Middleware Pipeline
```

---

Каждый запрос проходит цепочку middleware.

---

# Context

Основа Koa.

---

Все данные запроса хранятся в:

```js
ctx
```

---

Например:

```js
ctx.request
ctx.response
ctx.state
```

---

Похоже на:

```txt
NestJS Request
Express req/res
```

---

# Request Lifecycle

Полный путь запроса.

---

Шаг 1

Приходит HTTP запрос.

---

Шаг 2

Срабатывают глобальные middleware.

---

Например:

```txt
CORS
Auth
Logger
Body Parser
```

---

Шаг 3

Route определяет обработчик.

---

Например:

```txt
GET /api/articles
```

---

Шаг 4

Выполняются Policies.

---

Проверяют:

```txt
доступ
роль
авторизацию
```

---

Шаг 5

Вызывается Controller.

---

Контроллер отвечает за:

```txt
Request
Response
```

---

Пример:

```js
async find(ctx) {
  return await strapi
    .service(...)
    .find();
}
```

---

# Service Layer

Очень важная тема.

---

Контроллер не должен содержать бизнес-логику.

---

Она переносится в:

```txt
Service
```

---

Service отвечает за:

```txt
бизнес-правила
валидацию
агрегацию данных
```

---

# Query Engine

Следующий слой.

---

Раньше:

```txt
Entity Service
```

---

Начиная со Strapi v5:

```txt
Document Service
```

---

Ни тот, ни другой НЕ зависят от типа БД.

---

Это важно.

---

Они НЕ означают:

```txt
MongoDB
или
PostgreSQL
```

---

Это абстракция доступа к данным.

---

# Database Layer

Поддерживаются:

```txt
PostgreSQL
MySQL
SQLite
```

---

Strapi хранит собственные таблицы:

```txt
users
roles
permissions
content tables
upload tables
```

---

# Очень важное понимание

Strapi всегда требует собственную БД.

---

Схема:

```txt
Next.js
     ↓
Strapi
     ↓
PostgreSQL
```

---

# Это отдельный сервис?

Практически да.

---

В микросервисной архитектуре Strapi часто выглядит так:

```txt
Frontend
 ↓
Strapi CMS
 ↓
PostgreSQL
```

---

Отдельный deploy.

Отдельная база.

Отдельная админка.

---

# Почему Strapi похож на Backend Framework

Потому что есть:

```txt
Routes
Controllers
Services
Middlewares
Policies
RBAC
Hooks
Plugins
```

---

То есть он предоставляет
намного больше возможностей,
чем просто хранение контента.

---

# Интервью ответ

Архитектура Strapi построена поверх Koa и напоминает классическое backend приложение. Запрос проходит через middleware, route, policy, controller и service, после чего обращается к Document Service и базе данных. Strapi использует собственную БД и фактически может рассматриваться как отдельный backend сервис с административной панелью и автоматически генерируемыми API.