# GraphQL Performance and Security

## The root of all problems — flexibility the server pays for

```txt
REST    — the server fully controls the shape and cost of
          EVERY endpoint (fixed JOINs, fixed depth)
GraphQL — the client builds the query DYNAMICALLY, and the
          server MUST execute ANY syntactically valid
          combination of schema fields
```

This asymmetry is why GraphQL APIs need an EXTRA layer of protection that a typical REST API doesn't: depth limiting, query complexity analysis, resolver timeouts. Without them, a single request that's perfectly valid from the schema's point of view can become a DoS vector.

## Query Depth and Depth Limiting — a simple but blunt defense

```graphql
query {
  user {
    posts {
      comments {
        author {
          posts {
            comments { text }   # depth 6
          }
        }
      }
    }
  }
}
```

```ts
// graphql-depth-limit — rejects the query at the Validate
// stage (before any resolvers run, see [GraphQL Fundamentals])
import depthLimit from 'graphql-depth-limit';

const server = new ApolloServer({
  schema,
  validationRules: [depthLimit(5)],
});
```

```txt
Problem with depth limiting: it only counts NESTING, not COST.
A query with depth 3 but 3 aliases of the same expensive field
(see Query Aliasing below) passes the depth limit, but actually
calls the resolver 3 times. Depth limiting is a "cheap first
line of defense," not a complete solution.
```

## Query Complexity — assigning a "cost" to every field

```ts
// graphql-query-complexity — every field gets a weight, the sum
// of weights of requested fields must not exceed the limit
const complexityRule = createComplexityLimitRule(1000, {
  estimators: [
    fieldExtensionsEstimator(),
    simpleEstimator({ defaultComplexity: 1 }),
  ],
});
```

```graphql
type Query {
  users(first: Int!): [User!]! @complexity(value: 1, multipliers: ["first"])
}

type User {
  posts(first: Int!): [Post!]! @complexity(value: 2, multipliers: ["first"])
}
```

```txt
Senior nuance: complexity is MULTIPLIED via multipliers — the
posts(first: 10) field inside users(first: 100) yields a
complexity of ROUGHLY 100 * (1 + 10 * 2) = 2100, not just "1 + 2".
It's exactly this multiplication of limit/first arguments across
nested levels that makes an "innocent"-looking query (depth 3,
but first: 100 at every level) exponentially expensive. This is
the formalization of "Query Explosion."
```

### Query Aliasing — bypassing naive limits via field duplication

```graphql
query {
  a: expensiveField
  b: expensiveField
  c: expensiveField
  # ... 1000 aliases of the same field
}
```

```txt
Aliases are a legitimate GraphQL feature (requesting the same
field with different arguments under different names). But 1000
aliases of ONE expensive field in ONE request → 1000 resolver
calls in a single HTTP request — depth limiting won't stop this
(depth = 1). Defense: either limiting the number of fields in a
request (graphql-validation-complexity also counts this), or
rate limiting based on query COMPLEXITY rather than the number of
HTTP requests.
```

## Rate Limiting — GraphQL doesn't make the classics obsolete, but the unit should be COMPLEXITY

```txt
Naively: "100 requests per minute per IP" doesn't work, because
1 request can cost as little as 1 or as much as 10,000 (see Query
Complexity above). Production practice combines:

  1. Rate limiting by HTTP request count (Redis, API Gateway,
     NestJS Throttler) — basic defense against simple flooding
  2. Rate limiting by the SUM of query complexity over a period —
     to defend against "a small number of expensive requests"
  3. Resolver-level timeouts — a resolver that hangs longer than
     N seconds (e.g., waiting on an external API) fails with an
     error without blocking the whole event loop (see [Worker
     Threads and Cluster] from the Node.js section on event loop
     blocking)
```

## Pagination — why limit/offset isn't enough at scale

```graphql
# ⚠️ Offset pagination — simple, but degrades at large offsets
# (the DB still scans and discards offset rows)
users(skip: 100000, take: 20): [User!]!
```

```graphql
# ✅ Cursor-based (Relay Connection spec) — the cursor encodes a
# position (often an encoded id/timestamp of the last record),
# the DB does WHERE id > cursor LIMIT 20 — an index is used
# directly, without scanning skipped rows
type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
}

type UserEdge {
  node: User!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  endCursor: String
}

type Query {
  users(first: Int!, after: String): UserConnection!
}
```

```txt
Additional benefit of cursor pagination: it's STABLE under
inserts/deletes between pages (offset 100-120 after a record is
inserted at position 50 "shifts" the whole page and causes
duplicates/gaps — a cursor doesn't have this problem since it's
tied to a specific record, not a position).

first/take in the schema is a MANDATORY argument in production:
without it, an unpaginated users field is the most common source
of a "suddenly expensive" query — depth limiting won't stop it
(depth 1), and it's hard to constrain with complexity rules
without multipliers.
```

## Caching — why GraphQL isn't cached "for free," and Persisted Queries as a solution

```txt
This problem is covered at the HTTP level in [GraphQL
Fundamentals] (POST /graphql isn't cached by a CDN/browser based
on URL). Persisted Queries solve it like this:
```

```txt
1. The client registers the query text with the server once
   (or computes a SHA-256 hash itself — Automatic Persisted
   Queries)
2. On every SUBSEQUENT call, the client sends ONLY the hash:
   GET /graphql?extensions={"persistedQuery":{"sha256Hash":"abc123"}}&variables={"id":"1"}
3. The server: if the hash is known — executes the query using
   the stored text + the received variables; if unknown — asks
   the client to send the full text once (to register it)
```

```txt
Effects:
  - Traffic drops sharply (a hash is shorter than the query)
  - The request goes over GET → can be cached by a CDN based on
    URL (hash + variables in the query string)
  - Security side effect: since KNOWN hashes can be put on an
    allowlist (see [Queries, Mutations, and Subscriptions] on the
    connection between variables and Persisted Queries), the
    server can REJECT requests with arbitrary text — defense
    against Query Explosion at the root
```

## Introspection — details from [GraphQL Fundamentals] applied to security

```txt
The detailed trade-off (codegen/Playground vs leaking API
structure) is covered in [GraphQL Fundamentals]. Addendum for the
security context: disabling introspection is "security through
obscurity," NOT a replacement for authorization. An attacker with
access to the frontend source (bundle.js contains ALL queries
used) or to intercepted traffic ALREADY sees part of the schema —
disabling __schema only makes brute-forcing the REST of the
fields harder, it doesn't make them inaccessible if permissions
allow it.
```

## Authorization — why "protect the endpoint" doesn't work in GraphQL

```txt
In REST, every resource has its own URL → route middleware
(`router.get('/admin/users', requireAdmin, handler)`) covers all
access to the resource.

In GraphQL, ONE endpoint serves ALL data types — authorization
"at the entrance" to /graphql can only check "is the user logged
in at all," but NOT "can this user see the FIELD User.email of
ANOTHER user."
```

```ts
// ❌ Not enough — a check at the whole-request level
app.use('/graphql', requireAuth, graphqlHandler);

// ✅ Authorization at the RESOLVER level for a specific FIELD
const resolvers = {
  User: {
    email: (user, _args, ctx) => {
      if (ctx.user.id !== user.id && !ctx.user.isAdmin) {
        return null; // or throw new ForbiddenError()
      }
      return user.email;
    },
  },
};
```

```ts
// NestJS — declaratively, via Guards at the field resolver level
@ResolveField('email')
@UseGuards(FieldOwnerOrAdminGuard)
email(@Parent() user: User) {
  return user.email;
}
```

```txt
Senior nuance: field-level authorization interacts with null
bubbling (see [Schema, Types, and Resolvers]) — if email is
declared as String! (non-null), and the resolver returns null due
to access rights, this triggers null bubbling of the entire User
object. So fields whose access may be restricted by permissions
MUST be nullable in the schema — an architectural decision driven
by authorization requirements, not just by the data itself.
```

## Federation — when one monolithic GraphQL server isn't enough

```txt
User Service (graph)  ──┐
Post Service (graph)  ──┼──→  Apollo Gateway / Router  →  Client
Review Service (graph) ─┘     (one combined graph)
```

```graphql
# User Service — owns the User type
type User @key(fields: "id") {
  id: ID!
  name: String!
}

# Post Service — EXTENDS User with a field it OWNS itself
extend type User @key(fields: "id") {
  id: ID! @external
  posts: [Post!]!
}
```

```ts
// Post Service — a resolver that "assembles" an entity extension
// from another service. When the Gateway assembles the response
// and needs to resolve User.posts, it calls the Reference
// Resolver with { id } from User Service
const resolvers = {
  User: {
    posts: (user, _args, ctx) => ctx.db.post.findMany({ where: { authorId: user.id } }),
  },
};
```

```txt
Federation solves an organizational problem (different teams own
different parts of the graph independently), but adds a NEW
N+1-like layer: the Gateway makes separate network requests to
EACH service to "fill in" an entity — meaning DataLoader (see
[N+1 Problem and DataLoader]) is now needed not just at the DB
level inside a service, but the Gateway also batches _entities
requests between services.
```

## Connection to other topics

```txt
[GraphQL Fundamentals]            — why HTTP caching doesn't work
                                      "out of the box," the
                                      Introspection trade-off
[Schema, Types, and Resolvers]    — null bubbling and its
                                      interaction with field-level
                                      authorization
[N+1 Problem and DataLoader]       — DataLoader as part of the
                                      overall performance picture
[Queries, Mutations, and
 Subscriptions]                     — variables as a requirement
                                      for Persisted Queries
```

## Common interview mistakes

- **"Depth limiting solves the problem of expensive queries"** — not mentioning Query Aliasing as a way to bypass depth limiting at depth 1, and not knowing about Query Complexity with multipliers as a more precise mechanism.

- **"Offset pagination is enough, just add a limit"** — not explaining the performance degradation at large offsets and the instability under inserts/deletes, not knowing about the Relay Connection spec (cursor-based).

- **"Persisted Queries are just a traffic optimization"** — not connecting them to security (allowlisting known hashes as a defense against Query Explosion) and to caching via GET.

- **"Authorization can be done with one middleware on /graphql"** — not understanding that in GraphQL, authorization must happen at the RESOLVER level for a specific field, not for the whole request.

- **Not seeing the conflict between field-level authorization and non-null fields** — a resolver that returns null due to access rights for a `String!` field triggers null bubbling of the entire object.

- **"Federation is just microservices for GraphQL"** — not mentioning that the Gateway introduces ITS OWN N+1-like layer between services when assembling entities (`_entities`).
