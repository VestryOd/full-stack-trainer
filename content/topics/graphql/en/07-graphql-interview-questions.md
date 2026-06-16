# GraphQL: Interview Questions

Questions are grouped thematically. Each group has a full senior-level answer + typical follow-up questions with brief answers. Goal: replicate the "base question → clarifications → nuances" chain that actually happens in interviews.

---

## Group 1: GraphQL Fundamentals — spec, schema, execution

### What is GraphQL and how does it differ from REST at the spec level?

GraphQL is a SPECIFICATION (a query language + a type system + execution semantics), not a specific technology or transport protocol. Implementations: graphql-js (the reference), Apollo Server, Mercurius, GraphQL Yoga — all implement one spec with different extensions. Unlike REST (which isn't a spec at all — it's an architectural style), GraphQL strictly defines what a valid query looks like, how the server must execute it, and what the response must contain.

The key difference is in who controls the response shape: in REST the SERVER decides what each endpoint returns; in GraphQL the CLIENT decides via a selection set which fields are needed. This solves overfetching (only the needed fields come back) and underfetching (one request = multiple related entities).

```txt
Typical follow-ups:

Q: "Does GraphQL only work over HTTP?"
A: No, the spec is transport-agnostic. In practice it's almost
   always HTTP POST /graphql, but GraphQL over WebSocket
   (subscriptions) and GraphQL over gRPC are also valid
   implementations.

Q: "What is SDL?"
A: Schema Definition Language — the formal language for describing
   a GraphQL schema (type User { id: ID! name: String! }). It's
   part of the spec, not just a documentation format — the server
   is required to conform to the SDL at runtime.

Q: "Why is GraphQL called strongly typed if runtime errors are
   still possible?"
A: "Strongly typed" means that a MISMATCH BETWEEN THE QUERY AND
   THE SCHEMA is rejected at the Validate phase — before resolvers
   run, before touching the DB. But errors INSIDE a resolver (DB
   is down, resolver returned null for String!) are runtime errors
   of the Execute phase — they always happen.
```

### Describe the three phases of GraphQL query execution.

1. **Parse** — the query text is parsed into an AST (Abstract Syntax Tree). A syntax error (unclosed brace) is rejected HERE, before any data access.

2. **Validate** — the AST is checked against the SCHEMA: do the requested types/fields/arguments exist, do argument types match? A validation error (a requested field doesn't exist in the schema) → resolvers are NOT called AT ALL. This lets you reject invalid queries without hitting the database.

3. **Execute** — for each field in the query, the corresponding resolver is called, and results are assembled into a tree matching the query's shape.

```txt
Typical follow-ups:

Q: "At which phase does Depth Limiting / Query Complexity run?"
A: At the Validate phase — they're implemented as additional
   validation rules (validationRules in Apollo Server). The query
   is rejected before any resolvers run.

Q: "At which phase does GraphQL detect that a String! field
   returned null?"
A: At the Execute phase — this is a runtime error inside the
   resolver, not a schema violation at the query level. The schema
   is a SERVER commitment, not something validated at the Validate
   phase.
```

---

## Group 2: Operations — Query, Mutation, Subscription

### What's the difference between Query and Mutation from a spec perspective (not just semantics)?

Semantically: Query = read, Mutation = write. But the spec adds a CRITICALLY IMPORTANT behavioral difference:

- **Query**: top-level fields MAY (and by default SHOULD, if async) execute IN PARALLEL. The order of fields in the response matches the query, but the order resolvers are CALLED is not guaranteed.
- **Mutation**: top-level fields execute STRICTLY SEQUENTIALLY, in the order they appear in the request. This is a spec requirement, specifically to prevent race conditions when multiple data changes are made in one request.

```txt
Typical follow-ups:

Q: "How do NESTED fields inside a Mutation result behave?"
A: Like Query — they can execute in parallel. The sequential rule
   applies only to TOP-LEVEL Mutation fields, not to the whole tree.

Q: "What is the Payload Pattern and when should you use it?"
A: Instead of type Mutation { createUser: User! } (where errors
   go into errors[] with null bubbling), use type Mutation {
   createUser: CreateUserPayload! }, where CreateUserPayload has
   user: User and errors: [UserError!]. errors[] is for UNEXPECTED
   errors (server crash), the Payload Pattern is for EXPECTED
   business errors (email taken). TypeScript then forces you to
   check errors before accessing user.

Q: "When are subscriptions over-engineering?"
A: When polling (a notification counter) or SSE (a one-way stream)
   would do. Subscriptions are justified when latency is critical
   (chat, trading quotes) or events are bidirectional/very frequent.
```

### How do Variables differ from inline arguments, and why does it matter?

On the surface — a style preference. But there's an architectural reason:

- **Inline arguments** (`user(id: "42") { name }`) — every unique dataset creates a NEW query string.
- **Variables** (`query GetUser($id: ID!) { user(id: $id) }` + `{"id": "42"}`) — the query text is STABLE, only the variables change.

Text stability is critical for: 1) **Persisted Queries/APQ** — the client sends a SHA-256 hash of the text instead of the full text; if the text changes with each request, the hash changes and caching is useless; 2) **Query allowlisting** — a whitelist of allowed queries only works with stable texts; 3) **Security** — values in variables go through `parseValue` of custom scalars for validation.

```txt
Typical follow-ups:

Q: "How does APQ (Automatic Persisted Queries) actually work?"
A: 1) Client sends only the hash → server: "I don't know this hash"
   → 2) Client sends hash + full text → server saves the text
   under the hash → 3) All future requests are just the hash.
   Bonus: via GET with the hash in the URL → CDN cache by URL.
```

---

## Group 3: Schema and types

### What is Null Bubbling and why is overusing "!" dangerous?

If a resolver returns null (or throws) for a field marked NON-NULL (`String!`), GraphQL cannot violate the schema contract and return `{ "name": null }`. So the error "bubbles up" through the response tree to the NEAREST NULLABLE ancestor, which becomes null.

```graphql
type Query { user: User }    # nullable
type User { name: String! }  # non-null!
```

On a `User.name` error → `data.user` becomes `null` (the entire object), because `User` is the nearest nullable ancestor. If `Query.user` were also `User!` — `data` itself would become null.

Practical takeaway: the more `!` in the schema, the higher the risk of the entire response "collapsing" due to one unstable resolver deep in the tree. Typical practice: `id` is always non-null; fields that depend on external services are nullable.

```txt
Typical follow-ups:

Q: "How does null bubbling interact with field-level authorization?"
A: If a field email: String! is unavailable to the current user,
   and the resolver returns null instead of throwing, this triggers
   null bubbling of the entire User object. So fields with
   conditional access MUST be nullable in the schema — this is an
   architectural requirement.
```

### What's the difference between Interface and Union, and when do you use each?

- **Interface** — a common set of fields REQUIRED by all implementing types. The client can request shared fields without `... on TypeName`; specific fields go through inline fragments.
- **Union** — a union of COMPLETELY UNRELATED types. No shared fields — only `... on TypeName` for each possible type.

Both require `__resolveType` — a function that determines, from the object, which concrete type it belongs to:

```ts
Notification: {
  __resolveType(obj) {
    if ('likedBy' in obj) return 'LikeNotification';
    if ('comment' in obj) return 'CommentNotification';
  }
}
```

In practice: Interface — when types are conceptually related (`Notification`, `Animal`); Union — when a field can be one of fundamentally different alternatives (`SearchResult = User | Post | Comment`).

```txt
Typical follow-ups:

Q: "Why can't you use an Object Type as an argument type?"
A: An Object Type can contain fields with resolvers, interfaces,
   and unions — concepts that make no sense for input data. For
   arguments you need an Input Type — a "flat" structure with no
   resolvers. (Input Unions via @oneOf only arrived in recent
   spec versions.)
```

---

## Group 4: N+1 Problem and DataLoader

### What is the N+1 Problem in GraphQL and why does it happen specifically here?

Every GraphQL field can have its own resolver. The resolver for an array field is called SEPARATELY for EACH element of the parent array:

```txt
Query.users → 1 SQL (returns 100 users)
User.posts  → called 100 times → 100 SQL queries
Total: 101 queries instead of 2
```

In REST, every endpoint has a fixed shape → you can hardcode the JOIN upfront. In GraphQL, the request shape is dynamic → a JOIN in the Query.users resolver only works if the client ALWAYS requests posts. The GraphQL-specific issue is that this is linear degradation, invisible on small dev data (10 → 11 queries) and destructive in production (1000 → 1001).

### How does DataLoader solve N+1?

DataLoader works via **batching** + **request-scoped caching**:

- `.load(key)` doesn't execute a query immediately — it adds the key to a queue and returns a Promise.
- On the next event loop tick, DataLoader calls the batch function ONCE with ALL accumulated keys → one SQL `WHERE id IN (1,2,...,100)` instead of 100 separate queries.
- Within one request, a repeated `.load("1")` returns the cached Promise without hitting the DB again.

```ts
const createUserLoader = (db: Db) =>
  new DataLoader<string, User | null>(async (ids) => {
    const users = await db.user.findMany({ where: { id: { in: [...ids] } } });
    const byId = new Map(users.map(u => [u.id, u]));
    return ids.map(id => byId.get(id) ?? null); // order is MANDATORY!
  });
```

```txt
Typical follow-ups:

Q: "Why do results have to be returned in the same order as ids?"
A: DataLoader maps the i-th result to the i-th key POSITIONALLY.
   If the order is wrong — one user's data arrives for another.

Q: "Why can't DataLoader be created as a singleton?"
A: Its cache isn't cleared between requests → User A's data leaks
   into User B's response (data leak), plus unbounded memory growth.
   Each GraphQL request must get a NEW instance in context.

Q: "What happens if a Mutation within one request changes a user,
   and then a resolver requests the same user via DataLoader?"
A: DataLoader returns the STALE cached value. You need to explicitly
   call userLoader.clear(id) or userLoader.prime(id, newData) after
   the mutation.

Q: "Does DataLoader fully replace JOIN?"
A: No. DataLoader gives O(nesting levels) queries, not O(1). For
   frequently-requested relations, a targeted JOIN in a specific
   resolver can be faster.
```

---

## Group 5: Performance and Security

### Why is a GraphQL API potentially more dangerous than REST from a DoS perspective?

In REST, every endpoint has a fixed cost (the server controls JOINs and depth). In GraphQL, the client builds the query dynamically, and ANY syntactically valid combination must be executed:

```graphql
query {
  users {
    posts {
      comments {
        author {
          posts {         # cyclic graph — depth grows
            comments { text }
          }
        }
      }
    }
  }
}
```

Defense — multiple layers:
- **Depth Limiting** (graphql-depth-limit) — blunt, bypassed by Query Aliasing (1000 aliases of one field at depth 1).
- **Query Complexity with multipliers** — `users(first: 100) { posts(first: 100) }` costs `100 * (1 + 100*2) = 20100` — more precise, accounts for multiplication of limit arguments.
- **Persisted Queries + allowlisting** — only known queries reach the server.
- **Rate limiting by complexity** — not by HTTP request count but by the sum of complexity over a period.

```txt
Typical follow-ups:

Q: "Is disabling introspection in production sufficient?"
A: No, it's "security through obscurity." An attacker with access
   to the frontend bundle.js can see all queries. Disabling
   introspection does NOT replace field-level authorization.

Q: "Why does authorization need to be at the resolver level, not
   middleware?"
A: In GraphQL one endpoint handles everything. Middleware on
   /graphql checks "is the user logged in," but not "can this user
   see User.email of ANOTHER user." That's only verifiable inside
   the resolver for the specific field.
```

### Why is cursor-based pagination better than offset at scale?

`OFFSET 100000 LIMIT 20` — the DB still scans and discards 100,000 rows (seq scan or index scan to the right point).

`WHERE id > cursor LIMIT 20` — uses the index directly, without scanning skipped rows. Bonus: stable under inserts/deletes (offset "shifts" pages; a cursor is tied to a specific record).

The Relay Connection spec formalizes cursor pagination: `UserConnection` with `edges: [UserEdge]` (node + cursor), `pageInfo` (hasNextPage, endCursor), and `first`/`after` arguments.

---

## Group 6: Architecture — Federation, BFF, GraphQL vs REST

### How would you scale a large GraphQL API in a microservices architecture?

The key tool is **Apollo Federation**: each microservice owns its part of the GraphQL graph (`@key(fields: "id")`, `extend type`, `__resolveReference`); the Gateway/Router assembles them into one unified schema for the client. Teams work independently without a monolithic BFF.

Additionally:
- **DataLoader** in each service (for N+1 to its own DB)
- The Gateway also batches `_entities` requests between services — analogous to DataLoader at the inter-service level
- **Query complexity + depth limiting** at the Gateway
- **Persisted Queries** for caching and allowlisting
- **Cursor-based pagination** for all collections

```txt
Typical follow-ups:

Q: "What is a BFF and when is Federation preferable?"
A: BFF (Backend For Frontend) — a single GraphQL service that
   aggregates data from multiple REST/gRPC downstream services.
   Simple at the start, but becomes a monolith. Federation is for
   when teams grow and need independence between subgraphs.
   Federation adds Gateway complexity but removes the monolithic
   BFF bottleneck.

Q: "When would you choose REST over GraphQL?"
A: Public API (CDN caching, no GraphQL client dependency), simple
   CRUD without nested relations, frequent file uploads, webhooks.
   The most realistic production answer: REST + GraphQL in one
   project — REST for the public API, GraphQL as a BFF for your
   own frontend.

Q: "Does GraphQL replace REST?"
A: No. They solve different problems. Most public APIs will stay
   REST because of ease of consumption, HTTP caching, and no
   dependency on a GraphQL client. GraphQL is optimal as an
   aggregation layer over services for complex clients.
```
