# Schema, Types, and Resolvers

## A schema isn't just "data description" — it's a contract with concrete guarantees

```graphql
type User {
  id: ID!
  name: String!
  email: String
}
```

SDL (Schema Definition Language) is a formal language describing EVERY possible query against the API and guarantees about the shape of the response. "Guarantees" is the key word here: `String!` isn't just "usually not null" — it's a COMMITMENT from the server, and violating it produces an execution error (see null bubbling below) — i.e., the schema affects runtime behavior, not just static typing.

## Scalar types and custom scalars

```graphql
scalar String
scalar Int
scalar Float
scalar Boolean
scalar ID    # serialized as String, but semantically an identifier
```

```txt
ID vs String — a common question: ID is semantically
different (used for client-side caching, Relay Global Object
Identification), but AT THE WIRE LEVEL it's indistinguishable
from String. "1" and 1 are both valid as ID.
```

### Custom scalars — a typical senior pattern

```ts
// DateTime as a custom scalar — serialization/deserialization
// happens in ONE place rather than in every resolver
const DateTimeScalar = new GraphQLScalarType({
  name: 'DateTime',
  serialize: (value: Date) => value.toISOString(),       // server → client
  parseValue: (value: string) => new Date(value),         // client → server (variables)
  parseLiteral: (ast) => new Date((ast as StringValueNode).value), // client → server (inline)
});
```

```graphql
scalar DateTime

type Post {
  createdAt: DateTime!
}
```

Without a custom scalar, `createdAt: String!` TECHNICALLY works, but loses semantic typing — the client can't tell from the schema that the string is an ISO date, and codegen will generate `string` instead of `Date`/`DateTime`.

## Non-Null and Lists — combinations and THEIR REAL IMPACT on error behavior

```graphql
posts: [Post]      # the array can be null, elements can be null
posts: [Post]!     # the array is not null, elements can be null
posts: [Post!]     # the array can be null, elements are not null
posts: [Post!]!    # neither the array nor its elements are null
```

### Senior nuance: "Null Bubbling" — what happens when a non-null field errors

```graphql
type Query {
  user(id: ID!): User    # nullable
}

type User {
  id: ID!
  name: String!          # non-null!
  email: String
}
```

```txt
If the User.name resolver throws an error (or returns null
for a String! field):

  GraphQL CANNOT return { "name": null } — that would violate
  the schema contract (String! guarantees "never null").

  So the error "bubbles up" through the response tree to the
  NEAREST NULLABLE ancestor — in this case, the entire user
  object becomes null:

  {
    "data": { "user": null },
    "errors": [{ "message": "...", "path": ["user", "name"] }]
  }

  If Query.user were also User! (non-null), the bubble would
  go EVEN HIGHER, and the ENTIRE "data" field would become null.
```

```txt
Practical takeaway: OVERUSING "!" in a schema isn't just
"strictness for its own sake." Every "!" creates a CASCADING
NULL-OUT POINT. One unstable resolver for a deeply nested
non-null field can null out the ENTIRE response. Common
practice is to make non-null ONLY fields that are TRULY
guaranteed to be present (`id`), and leave nullable anything
that depends on external services or might be temporarily
unavailable.
```

## Object Types, Interfaces, Unions — when one Object Type isn't enough

```graphql
# Interface — a common set of fields shared by different types
interface Notification {
  id: ID!
  createdAt: DateTime!
}

type LikeNotification implements Notification {
  id: ID!
  createdAt: DateTime!
  likedBy: User!
}

type CommentNotification implements Notification {
  id: ID!
  createdAt: DateTime!
  comment: Comment!
}

type Query {
  notifications: [Notification!]!
}
```

```graphql
# A query using inline fragments — the client requests COMMON
# fields shared by all types + SPECIFIC fields per concrete type
query {
  notifications {
    id
    createdAt
    ... on LikeNotification { likedBy { name } }
    ... on CommentNotification { comment { text } }
  }
}
```

```ts
// The server MUST be able to determine which CONCRETE type
// was returned — implemented via __resolveType
const resolvers = {
  Notification: {
    __resolveType(obj) {
      if ('likedBy' in obj) return 'LikeNotification';
      if ('comment' in obj) return 'CommentNotification';
      return null;
    },
  },
};
```

```txt
A Union differs from an Interface: a Union (`union
SearchResult = User | Post`) doesn't require any common
fields between types at all — union members can be
COMPLETELY UNRELATED types. An Interface requires every
implementation to include the interface's fields. Both need
__resolveType (or __resolveType at the union level).
```

## Input Types — why GraphQL doesn't use Object Types for arguments

```graphql
# ❌ Not allowed — Object Types cannot be used as an
# argument type
type Mutation {
  createUser(user: User!): User!  # SCHEMA ERROR
}

# ✅ Input Type — a separate type hierarchy for input data
input CreateUserInput {
  name: String!
  email: String!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
}
```

```txt
Reason for the separation: an Object Type can contain fields
with RESOLVERS (computed fields, relations to other types,
interfaces) — concepts that make no sense for input data,
which the client simply SERIALIZES as JSON. Input Types are
"flat" data structures with no resolvers, interfaces, or
unions (Input Unions via @oneOf only arrived in recent
versions of the spec).
```

## Resolver — the `(parent, args, context, info)` signature with a concrete example

```graphql
query {
  user(id: "1") {
    name
    posts(limit: 2) { title }
  }
}
```

```ts
const resolvers = {
  Query: {
    // parent = undefined (this is a root resolver)
    // args   = { id: "1" }
    user: (_parent, args, context, info) => context.db.users.findById(args.id),
  },
  User: {
    // parent = the User object RETURNED by the Query.user resolver
    // args   = { limit: 2 }
    posts: (parent, args, context, info) =>
      context.db.posts.findByUserId(parent.id, { limit: args.limit }),
  },
};
```

```txt
parent is the RESULT of the PARENT resolver, not "the parent
query." The chain: Query.user returns a user object → that
object becomes parent for ALL fields inside user (including
posts) → User.posts reads parent.id from that object.

If a field has NO explicit resolver defined (e.g., the "name"
field on User) — the DEFAULT RESOLVER is used: it simply reads
parent.name. So most "simple" fields don't need to be defined
in the resolvers object at all — it's enough for the object
returned by the parent resolver to already contain the
property.
```

### `context` — created ONCE per request, not per resolver

```ts
// NestJS / Apollo Server
const server = new ApolloServer({
  schema,
  context: async ({ req }) => ({
    user: await getUserFromToken(req.headers.authorization),
    db: dbConnection,
    // The DataLoader is created HERE — a NEW instance for
    // EVERY request, so its cache doesn't "leak" between
    // different users/requests (see [N+1 Problem and
    // DataLoader])
    postLoader: createPostLoader(dbConnection),
  }),
});
```

```txt
Senior nuance: context is an OBJECT CREATED ONCE for the
entire request (with all its nested resolvers), and PASSED BY
REFERENCE to EVERY resolver. It's the ideal place for:
  - authentication data (avoid re-decoding the JWT in every
    resolver)
  - DataLoader instances (a shared batching cache per request)
  - request-scoped DB connections/transactions

Anti-pattern: creating a DataLoader as a GLOBAL singleton —
then one user's cache can "leak" into another user's response
(a data leak across requests).
```

### `info` — rarely used, but solves a specific overfetching problem AT THE DATABASE LEVEL

```ts
// info.fieldNodes / graphql-parse-resolve-info lets you find
// out WHICH SUBFIELDS the client requested — and request ONLY
// those columns from the database
const resolvers = {
  Query: {
    user: (_parent, args, context, info) => {
      const requestedFields = getRequestedFields(info); // ['id', 'name']
      // SELECT id, name FROM users WHERE id = ?
      // instead of SELECT * — saves on wide tables
      return context.db.users.findById(args.id, { select: requestedFields });
    },
  },
};
```

```txt
This solves a problem symmetric to "overfetching from client
to server" (which GraphQL solves by default) —
"overfetching from resolver to database." Without analyzing
info, a resolver typically does SELECT * regardless of what
the client requested. graphql-tools/graphql-parse-resolve-info
are typical libraries for this pattern, more common in
high-load APIs with wide tables.
```

## Execution order of nested resolvers — not strictly "top to bottom, sequentially"

```graphql
query {
  user(id: 1) {
    name        # User.name — default resolver, reads parent.name
    posts {     # User.posts — a separate resolver
      title
      author {  # Post.author — a separate resolver for EACH post
        name
      }
    }
  }
}
```

```txt
1. Query.user runs FIRST (its result is needed as parent for
   all fields inside user)
2. User.name and User.posts — resolvers for SIBLING fields at
   the same level — can run IN PARALLEL (if both are async)
3. Post.author is called SEPARATELY for EACH element of the
   posts array — in parallel for each

Step 3 is the SOURCE of the N+1 problem: if posts returned 10
posts, Post.author is called 10 TIMES, each with its own
database query (unless DataLoader is used). Covered in detail
in [N+1 Problem and DataLoader].
```

## Connection to other topics

```txt
[GraphQL Fundamentals]            — the Parse/Validate/Execute
                                      pipeline in which resolvers run
[N+1 Problem and DataLoader]       — why resolvers for array fields
                                      are called N times and how
                                      batching solves it
[Queries, Mutations, and
 Subscriptions]                     — Mutation resolvers and how
                                      they differ (execution order,
                                      side effects)
```

## Common interview mistakes

- **"`!` in the schema is just like TypeScript's non-null, a purely static check"** — not knowing about null bubbling: an error in a non-null field cascades to null out the nearest nullable ancestor, possibly all of `data`.

- **Confusing Interface and Union** — not knowing that a Union doesn't require common fields between members while an Interface does, and that both need `__resolveType`.

- **"Why do we need Input Types if we have Object Types?"** — not explaining that Object Types can contain resolvers/interfaces/unions — concepts that don't make sense for input data.

- **"`parent` is the parent GraphQL query"** — not understanding that `parent` is the RESULT of the parent resolver (a regular JS object), and the default resolver just reads a property off it.

- **Creating a DataLoader/cache as a singleton outside `context`** — missing the risk of one user's data leaking into another's response via a shared cache across requests.
