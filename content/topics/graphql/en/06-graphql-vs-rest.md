# GraphQL vs REST

## The Most Popular Question

When to use GraphQL and when to use REST?

---

# REST

Resource-oriented approach.

---

Example:

```http
GET /users
GET /users/1
POST /users
DELETE /users/1
```

---

Each endpoint is responsible for a specific resource.

---

# GraphQL

One endpoint.

---

Typically:

```txt
/graphql
```

---

The client defines the data it needs.

---

# The Main Difference

REST:

```txt
the server defines the response
```

---

GraphQL:

```txt
the client defines the response
```

---

# Overfetching

REST:

```http
GET /user/1
```

---

Received:

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

Only needed:

```txt
name
```

---

Result: overfetching.

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

Returns exactly one field.

---

# Underfetching

REST:

```txt
User
Posts
Comments
```

---

Three requests.

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

One request.

---

# Typing

REST:

```txt
not standardized
```

---

GraphQL:

```txt
strict schema
```

---

# Self Documentation

GraphQL:

```txt
Introspection
```

---

The client can discover the API automatically.

---

REST:

```txt
Swagger/OpenAPI
```

must be maintained separately.

---

# Caching

REST wins here.

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
more complex
```

---

Because there is only one endpoint.

---

# Complexity

REST is simpler.

---

GraphQL is more complex.

---

New concepts appear:

```txt
Resolvers
DataLoader
Federation
Query Complexity
```

---

# Mobile Applications

A great use case for GraphQL.

---

Why?

---

Mobile devices are sensitive to:

```txt
number of requests
volume of data
```

---

GraphQL helps reduce both.

---

# Microservices

GraphQL is often used as:

```txt
BFF
Backend For Frontend
```

---

Architecture:

```txt
Frontend
   ↓
GraphQL Gateway
   ↓
Microservices
```

---

# When to Choose REST

- simple CRUD API
- public API
- high cacheability
- small team

---

# When to Choose GraphQL

- complex UIs
- many screens
- mobile apps
- BFF layer
- lots of related data

---

# A Common Question

Does GraphQL replace REST?

---

Answer:

No.

---

They solve different problems.

---

Today it is very common to use:

```txt
REST + GraphQL
```

in the same project.

---

# Interview Answer

REST is simpler, caches better, and is a great fit for CRUD APIs. GraphQL gives the client flexibility, solves overfetching and underfetching, and is especially useful for complex frontend applications and BFF architectures. In practice, both technologies are often used together.
