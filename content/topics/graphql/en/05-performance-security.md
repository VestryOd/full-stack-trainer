# GraphQL Performance and Security

## The Main Problem with GraphQL

GraphQL is very flexible.

---

But that flexibility can become a problem.

---

REST:

```txt
the server fully controls the response
```

---

GraphQL:

```txt
the client defines the response shape
```

---

So a client can accidentally or intentionally create a very expensive query.

---

# Query Explosion

Imagine:

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

Such a query can generate:

```txt
thousands of resolver calls
millions of records
enormous load
```

---

# Query Depth

The depth of a query.

---

Example:

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

Depth:

```txt
5
```

---

# Depth Limiting

A popular protection mechanism.

---

For example:

```txt
max depth = 5
```

---

If the client requests:

```txt
depth = 10
```

---

The server rejects the request.

---

# Query Complexity

An even more advanced mechanism.

---

Each field is assigned a cost.

---

For example:

```txt
user      = 1
posts     = 10
comments  = 20
```

---

Query:

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

May have a cost of:

```txt
31
```

---

If the limit is:

```txt
20
```

---

The query is blocked.

---

# Rate Limiting

GraphQL does not replace classic protection mechanisms.

---

For example:

```txt
100 requests / minute
```

---

Typically implemented with:

```txt
Redis
API Gateway
NestJS Throttler
```

---

# N+1

Already covered separately.

---

Very often the main performance issue.

---

Solution:

```txt
DataLoader
```

---

# Pagination

Required for large collections.

---

Bad:

```graphql
users {
  ...
}
```

---

Good:

```graphql
users(
  limit: 20
)
```

---

Even better:

```txt
Cursor Pagination
```

---

# Cursor Pagination

A very popular interview topic.

---

Instead of:

```txt
offset = 100000
```

---

Use:

```txt
cursor = userId
```

---

Usually faster.

---

# Caching

More complex than in REST.

---

Why?

---

REST:

```http
GET /users/1
```

---

The URL can be cached.

---

GraphQL:

```txt
all requests go to /graphql
```

---

Harder to cache.

---

# Persisted Queries

A very popular technique.

---

The client registers a query in advance.

---

Instead of:

```graphql
full query
```

---

Sends:

```txt
query hash
```

---

Benefits:

```txt
less traffic
better caching
more secure
```

---

# Introspection Security

A very popular interview topic.

---

GraphQL can describe itself.

---

For example:

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

Often disabled in production.

---

Why?

---

To prevent an attacker from obtaining a full description of the API.

---

# Authorization

A very important topic.

---

Bad:

```txt
protecting only the endpoint
```

---

Because the endpoint is always just one.

---

Protection must be:

```txt
at the resolver level
```

---

For example:

```ts
@UseGuards(AuthGuard)
```

---

or

```ts
if (!context.user) {
  throw new Error();
}
```

---

# Federation

A very popular senior interview topic.

---

What to do when you have:

```txt
dozens of GraphQL services
```

---

Solution:

```txt
Apollo Federation
```

---

Architecture:

```txt
User Service
Post Service
Comment Service
       ↓
Apollo Gateway
```

---

The client sees:

```txt
one GraphQL API
```

---

Even though there are many services internally.

---

# A Common Question

Why can GraphQL be more dangerous than REST?

---

Answer:

Because clients can form very complex queries that cause high load. That is why GraphQL requires additional protection mechanisms: depth limiting, query complexity analysis, pagination, and rate limiting.

---

# Interview Answer

The main GraphQL performance challenges are N+1 queries, deeply nested queries, and the lack of built-in caching. Solutions include DataLoader, pagination, query complexity analysis, depth limiting, persisted queries, and Federation.
