# Routes, Controllers and Services

## Very Important Understanding

Strapi doesn't just store data.

---

Under the hood it is a full-featured backend framework.

---

It has:

```txt
Routes
Controllers
Services
Policies
Middlewares
```

---

Practically like NestJS.

---

# Automatic Generation

We create:

```txt
Article
```

---

Strapi automatically generates:

```txt
Route
Controller
Service
```

---

That's why CRUD works immediately.

---

# Routes

A Route defines:

```txt
which URL
which Controller
```

---

Example:

```http
GET /api/articles
```

---

Is mapped to:

```txt
Article Controller
```

---

# Route Definition

Simplified:

```js
{
  method: 'GET',
  path: '/articles',
  handler: 'article.find'
}
```

---

# Controller

Very similar to a NestJS Controller.

---

Main responsibility:

```txt
Request
↓
Response
```

---

Receive request data.

---

Call a service.

---

Return a response.

---

# Example

```js
async find(ctx) {
  return await strapi
    .service('api::article.article')
    .find();
}
```

---

# What a Controller Must NOT Do

A very popular interview question.

---

Must not contain:

```txt
complex business logic
```

---

Because:

```txt
the Controller becomes fat
```

---

# Service Layer

All business logic lives here.

---

For example:

```txt
validation
aggregation
calling external APIs
working with multiple entities
```

---

# Example

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

# Why a Service Is Needed

It can be reused.

---

For example:

```txt
Controller A
Controller B
Lifecycle Hook
Cron Job
```

---

All can use a single Service.

---

# Document Service

Starting from Strapi 5.

---

High-level data access API.

---

Example:

```js
strapi.documents(
  'api::article.article'
)
.findMany();
```

---

# Query Engine

A lower-level layer.

---

Used when finer control is needed.

---

Usually used less often.

---

# Full Flow

Request:

```http
GET /api/articles
```

---

Passes through:

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

Then back:

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

A very popular interview question.

---

Suppose we need an endpoint:

```http
GET /api/articles/popular
```

---

We create a route.

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

# Very Similar to NestJS

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

# Where to Write Business Logic

A very popular interview question.

---

Correct answer:

```txt
Service Layer
```

---

Not the Controller.

---

# Frequent Question

Why customize a Controller
if CRUD is already generated?

---

Answer:

When you need:

```txt
a non-standard endpoint
data aggregation
integration with an external API
complex business logic
```

---

# Interview Answer

Strapi automatically generates Routes, Controllers and Services for each Content Type. A Route defines the endpoint, a Controller handles the request and forms the response, and a Service contains the business logic. For data access in Strapi v5, the Document Service is used, which works on top of the Query Engine and the database.
