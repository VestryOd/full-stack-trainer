# Policies, Middlewares and RBAC

## The Most Important Understanding

In Strapi, security is built on several layers.

---

Simplified:

```txt
Request
 ↓
Middleware
 ↓
Authentication
 ↓
Policy
 ↓
Controller
 ↓
Service
```

---

# Authentication vs Authorization

A very popular interview question.

---

Authentication:

```txt
Who are you?
```

---

For example:

```txt
JWT
Login
Access Token
```

---

Authorization:

```txt
What are you allowed to do?
```

---

For example:

```txt
Admin
Editor
Reader
```

---

# Users & Permissions Plugin

One of the most important Strapi plugins.

---

Provides:

```txt
Users
Roles
Permissions
JWT Auth
Registration
Login
```

---

It is essentially a ready-made authorization system.

---

# Public Role

By default there is:

```txt
Public
```

---

This is:

```txt
an unauthenticated user
```

---

For example:

```txt
an anonymous site visitor
```

---

# Authenticated Role

The second default role.

---

```txt
Authenticated
```

---

The user has performed:

```txt
login
```

---

And received a JWT.

---

# RBAC

Role Based Access Control.

---

A very popular term.

---

The idea:

```txt
Role
 ↓
Permissions
```

---

Example:

```txt
Admin
Editor
Viewer
```

---

# Example

Editor:

```txt
read articles
create articles
update articles
```

---

Viewer:

```txt
read articles
```

---

# How It Works in Strapi

For each endpoint you can specify:

```txt
allowed
or
denied
```

---

For example:

```http
GET /api/articles
```

---

Allow:

```txt
Public
```

---

But:

```http
POST /api/articles
```

---

Only for:

```txt
Authenticated
```

---

# JWT

By default Strapi uses:

```txt
JWT
```

---

After login:

```http
POST /api/auth/local
```

---

We receive:

```json
{
  "jwt": "...",
  "user": {...}
}
```

---

The client then sends:

```http
Authorization: Bearer token
```

---

# Middleware

The first level of request processing.

---

Very similar to Koa middleware.

---

Example:

```js
module.exports = (config, { strapi }) => {

  return async (ctx, next) => {

    console.log(ctx.request.url);

    await next();
  };
};
```

---

# Middleware Can

```txt
log
add data
modify the request
modify the response
stop the request
```

---

# Middleware Order

Very important.

---

They work as a chain.

---

```txt
Middleware A
 ↓
Middleware B
 ↓
Controller
```

---

After the response:

```txt
Controller
 ↑
Middleware B
 ↑
Middleware A
```

---

Just like Koa.

---

# Policy

A very popular interview topic.

---

A Policy is similar to a Guard in NestJS.

---

Main responsibility:

```txt
allow
or
deny
execution of a Route
```

---

# Example

Admin only.

---

```js
module.exports = async (
  policyContext,
  config,
  { strapi }
) => {

  return (
    policyContext.state.user.role
      .name === 'Admin'
  );
};
```

---

# Where It Is Applied

Route:

```js
{
  method: 'GET',
  path: '/reports',
  handler: 'report.find',
  config: {
    policies: [
      'global::is-admin'
    ]
  }
}
```

---

# Policy vs Middleware

A very popular interview question.

---

Middleware:

```txt
general request processing
```

---

Policy:

```txt
access check
```

---

# Frequent Question

How is a Policy similar to a NestJS Guard?

---

Almost a direct analogy.

---

Nest:

```txt
Guard
```

---

Strapi:

```txt
Policy
```

---

Both solve:

```txt
Authorization
```

---

# Full Flow

```txt
Request
 ↓
Middleware
 ↓
JWT Validation
 ↓
Policy
 ↓
Controller
 ↓
Service
```

---

# Interview Answer

Strapi uses RBAC through the Users & Permissions Plugin. Authentication is typically implemented via JWT, and Authorization is handled through roles and permissions. Middleware is used for general request processing, and Policies are the equivalent of Guards in NestJS and are responsible for controlling access to endpoints.
