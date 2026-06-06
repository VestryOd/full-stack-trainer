# GraphQL Fundamentals

## What is GraphQL

GraphQL is a query language for APIs and a runtime for executing those queries.

Developed by Facebook in 2015.

---

# Why GraphQL Was Created

Before GraphQL, most APIs were built with REST.

For example:

```txt
GET /users/1
GET /users/1/posts
GET /users/1/comments
```

---

To retrieve complex data, clients often had to make many requests.

---

# The Overfetching Problem

REST:

```http
GET /users/1
```

Returns:

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

But the client only needs:

```json
{
  "name": "Max"
}
```

---

Result:

```txt
Overfetching
```

Got more data than needed.

---

# The Underfetching Problem

Needed:

```txt
User
Posts
Comments
```

---

Have to make:

```txt
3 REST requests
```

---

Result:

```txt
Underfetching
```

---

# The GraphQL Solution

The client describes exactly what data it needs.

---

Example:

```graphql
query {
  user(id: 1) {
    name
  }
}
```

---

Response:

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

Only the requested fields are returned.

---

# The Core Idea of GraphQL

REST:

```txt
The server defines the response shape
```

---

GraphQL:

```txt
The client defines the response shape
```

---

# GraphQL Consists of Two Parts

Schema

+

Resolvers

---

# Schema

Describes:

```txt
what data exists
```

---

# Resolver

Describes:

```txt
how to fetch the data
```

---

# Architecture

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

# One Endpoint

A very popular interview question.

---

REST:

```txt
/users
/posts
/comments
```

---

GraphQL typically uses:

```txt
/graphql
```

---

All requests go through a single endpoint.

---

# Introspection

GraphQL can describe itself.

---

The client can ask:

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

And receive a description of the API.

---

# Why This Is Convenient

The following work automatically:

- Playground
- GraphiQL
- Apollo Studio
- Code Generation

---

# Strongly Typed API

GraphQL has strict typing.

---

Example:

```graphql
type User {
  id: ID!
  name: String!
}
```

---

If types don't match:

```txt
runtime error
```

---

# The Main Advantage of GraphQL

The client receives exactly the data it requested.

---

# The Main Drawback

More complex caching.

More complex security.

More complex optimization.

---

# Interview Answer

GraphQL is a query language for APIs and a runtime for executing them. Unlike REST, GraphQL lets the client define the response shape itself, which solves the problems of overfetching and underfetching. A GraphQL API is typically built around a type schema and a set of resolvers.
