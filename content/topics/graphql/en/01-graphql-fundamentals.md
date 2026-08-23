# GraphQL Fundamentals

## What GraphQL actually is — more precise than "an alternative to REST"

GraphQL is a **specification**: a query language, a type system, and execution semantics. It is not a specific technology, and it is not a transport protocol. That already separates it from REST (Representational State Transfer), which is an architectural style rather than a written spec.

There are many implementations: `graphql-js` (the reference implementation), Apollo Server, Mercurius (Fastify), GraphQL Yoga. They all implement the same specification, but with different extensions — caching, federation, subscriptions transport.

```txt
From the GraphQL specification:
  - Schema Definition Language (SDL) — the language for
    describing types
  - Query Language — the language for queries (query/mutation/
    subscription)
  - Execution — the algorithm for walking resolvers and
    assembling the response

  NOT part of the specification: transport (usually HTTP
  POST, but not required), authentication mechanism, caching
```

This matters for interviews: "Does GraphQL only work over HTTP?" — no, the spec is transport-agnostic. In practice it's almost always HTTP POST to `/graphql`, but GraphQL over WebSocket (subscriptions) or even gRPC are also valid implementations.

## The problem GraphQL solves: overfetching and underfetching — with a concrete example

```txt
REST: a user profile screen shows the name, avatar, the
3 most recent posts, and a follower count.

GET /users/1        → { id, name, email, avatar, bio,
                          createdAt, updatedAt, settings, ... }
                        (overfetching: only 2 of 9 fields are used)
GET /users/1/posts?limit=3
GET /users/1/followers/count

= 3 round trips, each with its own network latency
```

```graphql
# GraphQL: one request, exactly the needed fields
query ProfileScreen {
  user(id: 1) {
    name
    avatar
    posts(limit: 3) { title, createdAt }
    followersCount
  }
}
```

```txt
The core idea in one sentence:

REST    — the SERVER determines the shape of the response
          (via endpoint structure), the client adapts
GraphQL — the CLIENT determines the shape of the response
          (via query structure), the server exposes
          CAPABILITIES through the schema
```

## The query execution pipeline — three distinct phases

```txt
1. Parse — the query text is parsed into an AST (Abstract
   Syntax Tree). A syntax error (e.g., an unclosed brace) is
   rejected HERE, before any data access.

2. Validate — the AST is checked against the SCHEMA: do the
   requested types/fields/arguments exist, do argument types
   match? A VALIDATION error (a requested field doesn't
   exist) is rejected HERE — resolvers are NOT CALLED AT ALL.

3. Execute — for each field in the query, the corresponding
   resolver is called, and results are assembled into a tree
   matching the shape of the query.
```

"GraphQL is strongly typed" does not mean "type errors are impossible at runtime". The three phases show why. A query that does not match the schema is rejected in the Validate phase. No resolver runs, so the database is never touched.

But errors *inside* a resolver are Execute-phase errors. The database may be down. A resolver may return `null` for a field declared `String!`. Both happen at runtime, exactly as in any other API.

## Schema + Resolvers — separating "what's available" from "how to get it"

```graphql
# Schema (SDL) — declares the API's CAPABILITIES
type User {
  id: ID!
  name: String!
  posts: [Post!]!
}

type Query {
  user(id: ID!): User
}
```

```ts
// Resolvers — the IMPLEMENTATION of how to fetch data
// for each field in the schema
const resolvers = {
  Query: {
    user: (_parent, { id }, context) => context.db.users.findById(id),
  },
  User: {
    posts: (parent, _args, context) => context.db.posts.findByUserId(parent.id),
  },
};
```

```txt
The schema is the CONTRACT clients see and rely on (via
introspection, codegen). Resolvers are IMPLEMENTATION DETAILS,
completely hidden from the client. You can fully rewrite the
User.posts resolver (switch databases, add caching) — the
client won't notice, as long as the response shape still
matches the schema.

This decoupling underlies later topics: [N+1 Problem and
DataLoader] (optimizing resolvers without changing the
schema), [Schema, Types, and Resolvers] (resolver execution
details).
```

## Single endpoint and HTTP semantics — where GraphQL breaks familiar REST patterns

```txt
Most GraphQL servers respond on ONE endpoint (typically
POST /graphql), regardless of what data is requested.
```

### Senior nuance #1: the HTTP status is almost always 200, even on error

```json
// Response to a request where a resolver threw an error
// (e.g., the database is down) — HTTP 200 OK!
{
  "data": { "user": null },
  "errors": [
    { "message": "Database connection failed", "path": ["user"] }
  ]
}
```

```txt
This is EXPECTED per the spec: execution errors are PART OF
the GraphQL response, not an HTTP-level concern. HTTP 4xx/5xx
statuses are reserved for TRANSPORT-level errors (invalid
JSON, server unreachable, request too large).

Practical consequence: HTTP-based monitoring ("alert on 5xx")
does NOT CATCH GraphQL business-logic errors — you need to
inspect the "errors" field in the response body, which
requires GraphQL-aware tooling (Apollo Studio, dedicated
dashboards), not standard status-code-based APM.
```

### Senior nuance #2: a single endpoint complicates infrastructure-level HTTP caching

```txt
REST: GET /users/1 — cached "for free" by CDNs/browsers based
on URL (HTTP caching works at the URL + method level).

GraphQL: POST /graphql with body {"query": "..."} — POST
requests aren't cached by standard HTTP caches, and even if
they were, the cache key would need to include the ENTIRE body
(query + variables), not just the URL.

Solutions (details in [Performance and Security]):
  - Persisted Queries — the client sends a HASH of the query
    instead of the full text; the server can cache by hash,
    and theoretically serve via GET with the hash in the URL
  - Caching at the RESOLVER/FIELD level (Apollo Cache Control
    directives), rather than the HTTP level
```

## Introspection — power and risk at the same time

```graphql
{
  __schema {
    types { name, fields { name, type { name } } }
  }
}
```

```txt
Introspection is GraphQL's built-in ability to describe ITS
OWN schema via a query. It's the foundation for:
  - GraphiQL/Apollo Studio Playground (autocomplete)
  - Codegen (generating TS types from the schema)
  - Schema diffing in CI (detecting breaking changes)

Senior nuance — a security trade-off: introspection in
production EXPOSES THE ENTIRE API structure, including fields
that might be "internal only" (e.g., type AdminMutation) but
still technically reachable. Many teams DISABLE introspection
in production (`introspection: false` in Apollo Server),
leaving it enabled only in staging — but this creates a
trade-off: external tools (Apollo Studio Explorer, codegen for
partners) also stop working against the production schema.
```

## Strengths and weaknesses — without "GraphQL is always better"

```txt
Strengths:
  - the client controls the response shape → fewer round
    trips for complex UIs with nested data
  - one strongly-typed schema as a contract between frontend
    and backend, with auto-generated types
  - built-in API evolution without versioning (see [GraphQL
    vs REST] — adding fields doesn't break old clients)

Weaknesses (require dedicated engineering effort):
  - HTTP caching is harder (see above)
  - arbitrary client queries → risk of expensive/deeply nested
    queries (see [N+1 Problem and DataLoader] and [Performance
    and Security] — query complexity limits, depth limiting)
  - monitoring/alerting doesn't map to HTTP status codes
  - file uploads, batch operations aren't "out of the box,"
    they require spec extensions (the multipart request spec, etc.)
```

## Connection to other topics

```txt
[Schema, Types, and Resolvers]   — schema type details and the
                                     resolver lifecycle
[N+1 Problem and DataLoader]      — why "the client decides the
                                     response shape" creates a
                                     specific performance problem
[Performance and Security]        — query complexity, depth
                                     limiting, persisted queries
[GraphQL vs REST]                 — a detailed comparison of
                                     approaches to versioning,
                                     caching, and contracts
```

## Common interview mistakes

- **"GraphQL is a database, or a replacement protocol for REST"** — confusing a query-language specification with a specific transport or storage. GraphQL is a layer between the client and any data source: databases, REST APIs, gRPC services.

- **"GraphQL's strong typing means no runtime errors"** — not distinguishing two kinds of error. Validate-phase errors mean the query doesn't match the schema, and no resolver runs. Execute-phase errors are ordinary runtime errors: a resolver threw, or the database is down.

- **"GraphQL always returns HTTP 200, so it doesn't distinguish success from failure"** — not knowing about the `errors` array in the response body. Monitoring must inspect that array instead of the HTTP status.

- **"Introspection is just a convenience feature with no risk"** — not mentioning that exposing the full schema in production can be a security problem. Disabling introspection is itself a trade-off, not a free improvement.

- **Not mentioning that a single endpoint complicates HTTP caching** — a typical "hidden" downside of GraphQL. It only becomes obvious when you try to put a CDN (content delivery network) cache in front of a GraphQL API.
