# GraphQL vs REST

## The right level of comparison — architectural, not "which is better"

Both approaches use HTTP, JSON, and stateless requests. The difference isn't about "technology" — it's about WHO controls the shape of the response and WHAT architectural invariants are baked into the protocol.

```txt
REST    — RESOURCE-oriented approach:
          URL = resource, HTTP method = operation on the resource,
          HTTP status = result of the operation
          The server determines the response shape for each endpoint

GraphQL — OPERATION-oriented approach:
          One URL, the operation is described IN THE REQUEST BODY
          (query/mutation/subscription), the client determines
          the response shape via the selection set
```

## Overfetching and Underfetching — where REST "breaks" for complex clients

```txt
These problems are covered in [GraphQL Fundamentals] with a
numeric example. A nuance that's rarely mentioned:

REST isn't required to always return everything: many public REST
APIs support sparse fieldsets (e.g., Google API:
?fields=name,email, JSON:API spec: ?fields[users]=name,email).
This partially solves overfetching — but it's a CONVENTION, not
a mechanism built into the REST specification. GraphQL makes this
standard behavior out of the box.

The more serious problem is underfetching for COMPLEX UX: a
"Dashboard" screen with profile + notifications + recent orders
= 3 round trips in REST (or 1 custom /dashboard endpoint that
breaks resource-orientation), vs 1 GraphQL request with 3
top-level fields.
```

## Versioning — REST's chronic pain point

```http
# REST — usually solved via URL versioning or a header
GET /v1/users/1
GET /v2/users/1
```

```txt
/v2 = duplicating all the logic, maintaining two versions in
parallel, eventually "/v3"...
Attempts to solve it via headers (Accept: application/vnd.api.v2+json)
or parameters (?version=2) don't fix the fundamental problem:
REMOVING or CHANGING a field in an existing endpoint is a
BREAKING CHANGE for clients.
```

```graphql
# GraphQL — additive evolution without versions
type User {
  id: ID!
  name: String!
  fullName: String @deprecated(reason: "Use 'name' instead")
  email: String
  # Adding new fields — old clients simply don't request them
  phoneNumber: String
}
```

```txt
The GraphQL approach: ADDING fields is not a breaking change (old
clients don't request them, the schema is backward compatible).
REMOVING a field is a breaking change, so the field is first
marked @deprecated (tooling will warn frontend developers via
codegen), its usage is monitored (Apollo Studio shows who's still
using the deprecated field), and it's only removed after 0% usage.

This doesn't mean GraphQL never makes breaking changes — CHANGING
a field's TYPE (String → Int), CHANGING nullable → non-null — are
breaking changes in GraphQL too. But the tooling (schema registry,
breaking-change detection in CI) is more mature.
```

## Typing and contracts — OpenAPI vs GraphQL Schema

```txt
REST + OpenAPI:
  - OpenAPI spec is a SEPARATE file/doc that CAN drift from the
    actual implementation (without automated conformance testing)
  - Types are generated from the OpenAPI spec → if the spec isn't
    updated, the generated types don't reflect the real API
  - No built-in mechanism for compatibility checking

GraphQL:
  - The schema IS the spec — the server physically cannot return a
    field that doesn't exist in the schema (Validate phase runs
    before resolvers, see [GraphQL Fundamentals])
  - Introspection gives the LIVE schema directly from the server
  - Codegen (graphql-codegen) generates types from the RUNTIME
    schema, not from potentially stale docs
  - CI can check for breaking changes (schema diffing) automatically
```

## Caching — where REST genuinely wins (and how GraphQL compensates)

```txt
REST:
  GET /users/1 — cached by a CDN by URL out of the box:
    - Cache-Control: max-age=3600
    - ETag + If-None-Match (304 Not Modified)
    - Last-Modified + If-Modified-Since
    - URL = the unit of caching (precise, predictable)

GraphQL:
  POST /graphql — not cached by a CDN by default
  (details in [GraphQL Fundamentals] and [Performance and Security])

GraphQL compensations:
  1. Persisted Queries → GET requests with a hash in the URL →
     CDN cache
  2. @cacheControl directive (Apollo):
     type Post @cacheControl(maxAge: 60) { ... }
     in the resolver: info.cacheControl.setCacheHint()
     → the server adds Cache-Control: max-age=60 to the HTTP response
  3. Client-side normalized cache (Apollo Client) — cached by
     type id, not by URL, allowing one query to automatically
     update another query's cache if both touched the same
     User { id: "1" }
```

## Error semantics — HTTP status codes vs errors[]

```txt
REST:    200 OK, 201 Created, 400 Bad Request,
         401 Unauthorized, 404 Not Found, 500 Internal Error
         → Monitoring via HTTP status codes — a standard
           tool for any APM/alerting system

GraphQL: almost always HTTP 200, even on errors
         (details in [GraphQL Fundamentals])
         → Monitoring requires parsing the response body,
           needs GraphQL-aware tooling (Apollo Studio)

That said, GraphQL errors are STRUCTURED: each error includes a
path (the path to the failing field in the response), which lets
you pinpoint EXACTLY which field broke, rather than just knowing
"something is 500-ing."
```

## File uploads — where REST is simpler

```txt
REST: multipart/form-data — native HTTP-level support, handlers
available in any framework.

GraphQL: files aren't part of the GraphQL specification (which
describes ONLY JSON). For file uploads you need either:
  - graphql-upload (implements the graphql-multipart-request-spec
    — an extension on top of GraphQL) — with limitations (only
    works with multipart-compatible clients)
  - Hybrid approach: a separate REST/presigned-S3 URL for the file
    upload, a GraphQL mutation only for saving metadata — this is
    the cleanest architectural pattern for production
```

## BFF — the most common way to use both together

```txt
Frontend
    ↓
GraphQL BFF (Backend For Frontend)
    ↓
  ┌─────────────────────────────────┐
  │ Users REST Service              │
  │ Orders REST Service             │
  │ Notifications gRPC Service      │
  │ External Partner REST API       │
  └─────────────────────────────────┘
```

```txt
The GraphQL layer aggregates data from MULTIPLE downstream services
(which can remain REST or gRPC) into ONE graph, optimally shaping
the response for the specific client's needs (web, mobile, TV app
— each with its own data requirements).

The downstream services stay REST because:
  - they serve OTHER clients (other BFFs, partners, webhooks)
  - REST is simpler for public APIs and standardization
  - HTTP caching at the inter-service level is simpler with REST

GraphQL Federation (see [Performance and Security]) is the same
idea but without a single monolithic BFF: each service owns its
part of the GraphQL graph.
```

## When to choose REST, when GraphQL — an honest assessment

```txt
REST is preferable:
  ✓ Public APIs (GitHub v3 REST, Stripe, Twilio) — CDN caching,
    wide client support (curl, HTTPie, Postman out of the box),
    no dependency on a GraphQL client
  ✓ Simple CRUD with no complex entity relationships
  ✓ APIs with frequent file uploads
  ✓ When HTTP caching is critical and there are no resources for
    Persisted Queries / Apollo Cache Control
  ✓ Webhooks, event-driven integrations (REST endpoint as an event
    "receiver")
  ✓ Small team with less GraphQL experience

GraphQL is preferable:
  ✓ Complex UIs with nested, related data
  ✓ Multiple clients with DIFFERENT data requirements (web vs
    mobile vs embedded — each requests exactly what it needs)
  ✓ A BFF layer over multiple downstream services
  ✓ Teams that value type-safe codegen and a shared schema
    contract between frontend and backend
  ✓ Actively evolving API with frequently changing client
    requirements (additive evolution without versioning)

The most realistic production answer: REST + GraphQL in one
project — REST for the public API and webhook integrations,
GraphQL as a BFF for your own frontend.
```

## Connection to other topics

```txt
[GraphQL Fundamentals]            — overfetching/underfetching,
                                      GraphQL's HTTP semantics
[Performance and Security]         — caching via Persisted Queries,
                                      Federation as an alternative
                                      to a monolithic BFF
[Queries, Mutations, and
 Subscriptions]                     — comparing Mutation with REST
                                      verbs POST/PUT/PATCH/DELETE
                                      and idempotency
```

## Common interview mistakes

- **"GraphQL will replace REST"** — not understanding that they solve different problems: GraphQL has no native CDN caching, makes file uploads harder, and most public APIs will stay REST precisely because of ease of consumption and HTTP caching.

- **"REST is less type-safe because it has no schema"** — not mentioning OpenAPI/Swagger as the standard for REST API typing, and not explaining the difference in guarantees (OpenAPI can drift, GraphQL schema IS the runtime contract).

- **"GraphQL has no versioning — so things are always breaking"** — not knowing about @deprecated + additive evolution as the primary strategy, not mentioning breaking-change detection via schema diffing in CI.

- **"GraphQL caching is Apollo Client"** — confusing the client-side normalized cache with HTTP caching; not knowing about @cacheControl and Persisted Queries as a way to get CDN caching for GraphQL.

- **"You have to choose: REST or GraphQL"** — not proposing the hybrid BFF pattern (GraphQL as an aggregation layer over REST microservices) as the most common production solution.
