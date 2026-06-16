# Queries, Mutations, and Subscriptions

## Three operation types — but the difference is deeper than "Query = GET, Mutation = POST"

```txt
Query        — reading data
Mutation      — modifying data
Subscription  — a real-time stream of events
```

The surface-level analogy to HTTP methods is helpful as a starting point, but it hides the MOST important difference between Query and Mutation — the execution order of top-level fields, which is defined by the specification and has direct consequences for data consistency.

## Query: top-level fields execute IN PARALLEL

```graphql
query Dashboard {
  profile { name }
  notifications { count }
  recentOrders { id, total }
}
```

```txt
Per the GraphQL specification, top-level resolvers for Query
MAY (and typically SHOULD, if async) run IN PARALLEL — a
GraphQL server isn't required to wait for profile to finish
before starting notifications. The order of fields in the
RESPONSE always matches the order in the query (object keys
preserve order), but the EXECUTION order of resolvers doesn't.
```

```ts
// If all three resolvers hit the database, they run in
// parallel — total response time ≈
// max(t_profile, t_notifications, t_recentOrders),
// NOT the sum
const resolvers = {
  Query: {
    profile: async (_p, _a, ctx) => ctx.db.users.findById(ctx.user.id),
    notifications: async (_p, _a, ctx) => ctx.db.notifications.countUnread(ctx.user.id),
    recentOrders: async (_p, _a, ctx) => ctx.db.orders.findRecent(ctx.user.id),
  },
};
```

## Mutation: top-level fields execute STRICTLY SEQUENTIALLY — the spec's most underappreciated fact

```graphql
mutation BatchUpdate {
  deductBalance(amount: 100)
  addLoyaltyPoints(amount: 10)
}
```

```txt
The GraphQL specification EXPLICITLY requires: top-level
Mutation fields execute SEQUENTIALLY, in the order they
appear in the request — deductBalance MUST COMPLETE FULLY
BEFORE addLoyaltyPoints starts. This exists SPECIFICALLY to
prevent race conditions when multiple data mutations happen
in one request.

Senior implication: if a developer assumes multiple mutations
in one request will run "somehow in parallel for speed," that
assumption is WRONG, and it shouldn't drive architecture
decisions (e.g., "let's not split this into separate requests
for consistency reasons" — the spec ALREADY guarantees
sequential execution).

That said: NESTED resolvers within the RESULT of a single
mutation (e.g., fields of a related object in the response)
follow the SAME rules as Query (parallel where possible).
```

## Designing mutation responses — the "Payload Pattern" vs exceptions

```graphql
# ❌ Naive approach — the mutation either returns an object or
# fails with a GraphQL error (loses structure — the client
# can't easily distinguish "validation error" from "server error")
type Mutation {
  createUser(input: CreateUserInput!): User!
}
```

```graphql
# ✅ Payload Pattern — the mutation is ALWAYS successful at the
# transport level; business errors are part of the SCHEMA,
# not errors[]
type CreateUserPayload {
  user: User
  errors: [UserError!]
}

type UserError {
  field: String!
  message: String!
  code: UserErrorCode!
}

enum UserErrorCode {
  EMAIL_TAKEN
  INVALID_EMAIL
  WEAK_PASSWORD
}

type Mutation {
  createUser(input: CreateUserInput!): CreateUserPayload!
}
```

```txt
A trade-off worth stating explicitly in an interview:

GraphQL errors[] (the top-level errors array) is meant for
UNEXPECTED errors (database down, a bug) — it causes null
bubbling (see [Schema, Types, and Resolvers]).

Typed error unions / the Payload Pattern are for EXPECTED
business errors (email taken, insufficient funds) — the
client MUST handle them as part of the normal data flow
(TypeScript forces checking errors before using user), rather
than via try/catch.

This is exactly why most production GraphQL APIs (Shopify,
GitHub) use the Payload Pattern for business logic and reserve
errors[] for system failures.
```

## Variables — not just "style," but a requirement for Persisted Queries and security

```graphql
# ❌ Inline arguments — every unique piece of data creates a
# NEW query string
query {
  user(id: "42") { name }
}

# ✅ Variables — the query text is STABLE regardless of the data
query GetUser($id: ID!) {
  user(id: $id) { name }
}
```

```txt
Why this matters, and isn't "best practice for its own sake":

1. Persisted Queries / APQ (Automatic Persisted Queries) — the
   client sends a HASH of the query text instead of the text
   itself. If every request has a unique inline argument, the
   HASH CHANGES every time, and hash-based caching becomes
   useless (see [Performance and Security]).

2. Query allowlisting in production — a whitelist of allowed
   QUERIES (by text hash) — only works if the query text
   doesn't depend on user data.

3. Security — values serialized in variables go through
   custom scalars' parseValue (see [Schema, Types, and
   Resolvers]), giving a single point for
   validation/sanitization, unlike an arbitrary query string.
```

## Fragments — field reuse AND a unit of co-location in frontend architecture

```graphql
fragment UserCard on User {
  id
  name
  avatar
}

query ProfilePage {
  currentUser { ...UserCard }
  suggestedFriends { ...UserCard }
}
```

```txt
At the SCHEMA level, fragments are just field reuse. But in
modern frontend architecture (Apollo Client, Relay), fragments
are a UNIT OF CO-LOCATION: EACH React component defines ITS
OWN fragment with the fields IT needs, and a parent component
"assembles" its children's fragments into one query. This lets
a component change its data requirements without changing its
parents — a direct parallel to "the client determines the
response shape" from [GraphQL Fundamentals], but at the level
of COMPONENT DECOMPOSITION rather than the whole query.

Fragment masking (Relay, modern Apollo Client) goes further:
a component CANNOT access fields not declared in its OWN
fragment, even if they're present in the overall result — this
prevents hidden dependencies between components.
```

## Subscriptions: transport and architectural constraints rarely discussed

```graphql
type Subscription {
  messageAdded(chatId: ID!): Message!
}
```

```ts
// NestJS / graphql-ws
@Subscription(() => Message, {
  filter: (payload, variables) => payload.messageAdded.chatId === variables.chatId,
})
messageAdded(@Args('chatId') chatId: string) {
  return pubSub.asyncIterableIterator('MESSAGE_ADDED');
}
```

### Senior nuance #1: in-memory PubSub does NOT WORK with horizontal scaling

```txt
graphql-subscriptions provides PubSub "out of the box" — but
the DEFAULT IMPLEMENTATION (the PubSub class) holds
subscribers IN A SINGLE PROCESS'S MEMORY.

If you have 4 server replicas (see [Worker Threads and
Cluster] from the Node.js section):
  - Client A connects to Replica 1 and subscribes to
    messageAdded
  - A mutation from Client B is handled by Replica 3
  - Replica 3 publishes the event to ITS OWN local PubSub —
    Replica 1 (and Client A's subscription) RECEIVES NOTHING

Solution: a Redis-backed PubSub (graphql-redis-subscriptions)
or Kafka — events are published through an EXTERNAL bus that
EVERY replica listens to.
```

### Senior nuance #2: WebSocket connection authentication happens ONCE, not per message

```ts
// graphql-ws — connectionParams are sent ONCE when the
// WebSocket connection is established, not per subscription
const serverConfig = {
  context: async (ctx) => {
    const token = ctx.connectionParams?.authorization;
    const user = await verifyToken(token);
    return { user };
  },
};
```

```txt
Unlike HTTP requests (where the Authorization header is sent
on EVERY request), a WebSocket connection is established ONCE,
and the subscription's context is built from data captured AT
THAT MOMENT.

Practical consequence: if a user's JWT expires WHILE a
long-lived subscription is active, the standard mechanism
doesn't "recheck" the token on every event. You need explicit
logic to drop the connection when the token expires (a timer
based on the exp claim, or periodic re-authentication).
```

### When subscriptions are over-engineering

```txt
Subscriptions add complexity: WebSocket infrastructure,
distributed PubSub, managing long-lived connection state,
separate authentication.

Alternatives for "near real-time":
  - Polling (refetch every N seconds) — simple, cacheable,
    fine for data where a few seconds of delay is acceptable
    (a notification counter)
  - Long Polling / Server-Sent Events — for a one-way stream
    without the full complexity of WebSocket

Subscriptions are worth it when: latency is CRITICAL (chat,
trading quotes), and events are BIDIRECTIONAL or very frequent
(polling would generate too many redundant requests).
```

## Connection to other topics

```txt
[Schema, Types, and Resolvers]   — null bubbling, which affects
                                     mutation response design
[Performance and Security]        — Persisted Queries, query
                                     allowlisting — depend on
                                     variables instead of inline
                                     arguments
[GraphQL vs REST]                  — comparing Mutation with
                                     POST/PUT/PATCH/DELETE and
                                     the idempotency question
```

## Common interview mistakes

- **"Query and Mutation differ only semantically (read vs write)"** — not knowing that the spec REQUIRES sequential execution of Mutation top-level fields, unlike Query's parallel execution.

- **"Errors in GraphQL are always `errors[]`"** — not knowing about the Payload Pattern with typed error unions for expected business errors, and not explaining the trade-off between null bubbling and explicit client-side error handling.

- **"Variables are just syntactic sugar for arguments"** — not connecting variables to Persisted Queries/query allowlisting, where stable query text is critical.

- **"Subscriptions work out of the box with any number of replicas"** — not knowing about the in-memory PubSub limitation and the need for Redis/Kafka-backed PubSub for horizontal scaling.

- **Not mentioning the authentication problem for long-lived WebSocket connections** — not understanding that a subscription's context is built once at connection time, not per event.
