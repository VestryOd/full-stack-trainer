# Strapi Architecture

## The Most Important Understanding

Strapi is not just a CMS.

---

Under the hood it is a full-featured Node.js application.

---

Simplified diagram:

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

Very similar to NestJS.

---

# Koa Under the Hood

A very popular interview question.

---

Strapi uses:

```txt
Koa
```

not Express.

---

# What is Koa

A minimalist Node.js framework
created by the Express team.

---

The main idea:

```txt
Middleware Pipeline
```

---

Every request passes through a chain of middleware.

---

# Context

The foundation of Koa.

---

All request data is stored in:

```js
ctx
```

---

For example:

```js
ctx.request
ctx.response
ctx.state
```

---

Similar to:

```txt
NestJS Request
Express req/res
```

---

# Request Lifecycle

The full path of a request.

---

Step 1

An HTTP request arrives.

---

Step 2

Global middleware fires.

---

For example:

```txt
CORS
Auth
Logger
Body Parser
```

---

Step 3

A Route determines the handler.

---

For example:

```txt
GET /api/articles
```

---

Step 4

Policies execute.

---

They check:

```txt
access
role
authorization
```

---

Step 5

The Controller is called.

---

The controller is responsible for:

```txt
Request
Response
```

---

Example:

```js
async find(ctx) {
  return await strapi
    .service(...)
    .find();
}
```

---

# Service Layer

A very important topic.

---

A controller must not contain business logic.

---

It is moved into:

```txt
Service
```

---

A Service is responsible for:

```txt
business rules
validation
data aggregation
```

---

# Query Engine

The next layer.

---

Previously:

```txt
Entity Service
```

---

Starting from Strapi v5:

```txt
Document Service
```

---

Neither of them depends on the database type.

---

This is important.

---

They do NOT imply:

```txt
MongoDB
or
PostgreSQL
```

---

They are an abstraction for data access.

---

# Database Layer

Supported databases:

```txt
PostgreSQL
MySQL
SQLite
```

---

Strapi stores its own tables:

```txt
users
roles
permissions
content tables
upload tables
```

---

# Very Important Understanding

Strapi always requires its own database.

---

Diagram:

```txt
Next.js
     ↓
Strapi
     ↓
PostgreSQL
```

---

# Is It a Separate Service?

Practically yes.

---

In a microservice architecture Strapi often looks like this:

```txt
Frontend
 ↓
Strapi CMS
 ↓
PostgreSQL
```

---

Separate deploy.

Separate database.

Separate admin panel.

---

# Why Strapi Resembles a Backend Framework

Because it has:

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

That is, it provides
much more capability
than just content storage.

---

# Interview Answer

Strapi's architecture is built on top of Koa and resembles a classic backend application. A request passes through middleware, route, policy, controller and service, then accesses the Document Service and the database. Strapi uses its own database and can effectively be considered a separate backend service with an admin panel and automatically generated APIs.
