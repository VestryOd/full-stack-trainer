# N+1 Problem and DataLoader

## The most common GraphQL senior question — and why it's specific to GraphQL

N+1 isn't a "GraphQL bug" — it's a direct consequence of the resolver architecture described in [Schema, Types, and Resolvers]: every field can have its OWN resolver, and the resolver for an array field is called SEPARATELY for EACH element of the parent array.

```graphql
type User {
  id: ID!
  name: String!
  posts: [Post!]!
}

type Query {
  users: [User!]!
}
```

```ts
const resolvers = {
  Query: {
    users: (_p, _a, ctx) => ctx.db.user.findMany(),
  },
  User: {
    posts: (user, _a, ctx) => ctx.db.post.findMany({ where: { userId: user.id } }),
  },
};
```

```graphql
query {
  users {
    id
    name
    posts { title }
  }
}
```

```txt
Step 1: Query.users → 1 SQL query, returns 100 users
Step 2: User.posts is called SEPARATELY for EACH of the 100
        users → 100 SQL queries

Total: 1 + 100 = 101 queries instead of 2.

With 1000 users — 1001 queries. The database starts to suffer,
and the degradation is LINEAR in the size of the response —
meaning the problem is invisible on dev data (10 users → 11
queries looks tolerable) and only shows up at production scale.
```

### Why "just use include/JOIN" doesn't always solve it

```ts
// Naive solution — works for ONE level of nesting
prisma.user.findMany({ include: { posts: true } });
```

```txt
This solves N+1 FOR THIS SPECIFIC query — but a GraphQL server
doesn't know in advance which query will arrive. The include
would have to be hardcoded into the Query.users RESOLVER — but
that resolver doesn't know whether the client will request posts
at all (and if it does — whether it'll also request author for
each post, and comments for each post...).

Hardcoding include for ALL possible nestings upfront defeats
GraphQL's main advantage ("the client decides what to fetch,"
see [GraphQL Fundamentals]) and causes DB-level overfetching for
queries that don't need posts.

JOIN solves the problem ONLY when the query shape is known in
advance (a REST endpoint with a fixed response shape) — in
GraphQL the query shape isn't known in advance.
```

## DataLoader: Batching + Caching, built by Facebook for exactly this problem

```ts
import DataLoader from 'dataloader';

const createUserLoader = (db: Db) =>
  new DataLoader<string, User | null>(async (ids) => {
    const users = await db.user.findMany({ where: { id: { in: ids as string[] } } });
    const byId = new Map(users.map((u) => [u.id, u]));
    // CRITICAL: return results in the SAME ORDER as ids, and
    // null/Error for missing keys — the returned array's
    // length MUST match the length of ids
    return ids.map((id) => byId.get(id) ?? null);
  });
```

```ts
// Resolver — calls .load(), not findMany() directly
const resolvers = {
  Post: {
    author: (post, _args, ctx) => ctx.userLoader.load(post.authorId),
  },
};
```

### Why result order matching `ids` is mandatory

```txt
DataLoader maps the i-th element of the RESULT to the i-th
element of the INPUT keys POSITIONALLY, not by value. If the
batch function returns users in the order the DATABASE returned
them (and a DB does NOT guarantee the order of
WHERE id IN (...) without an explicit ORDER BY), DataLoader will
assign the result intended for .load("1") to .load("3").

Solution — always build a Map<key, value> from the DB result and
map over the INPUT ids:

  return ids.map(id => byId.get(id) ?? null)

If there's no data for a key — return null (for nullable fields)
or an Error instance (DataLoader will throw it specifically for
the .load() calls that requested that key — the other keys in the
batch are unaffected).
```

### How batching works at the event-loop level

```txt
.load(key) does NOT execute a query immediately — it:
  1. Adds the key to the current "tick's" queue
  2. Returns a Promise that resolves later
  3. On the next event loop tick (process.nextTick /
     setImmediate, depending on the implementation), DataLoader
     collects ALL accumulated keys and calls the batch function
     ONCE with all of them at once

So 100 synchronous .load() calls from 100 parallel calls to
User.posts (see "execution order of nested resolvers" in
[Schema, Types, and Resolvers]) become ONE call to the batch
function with an array of 100 keys.
```

## Caching — the second superpower, and where it breaks

```txt
Within a SINGLE DataLoader instance — calling .load("1") again
returns the cached Promise without a new call to the batch
function, even if several resolvers ran in between.

Senior nuance: this cache is NOT a cache in the usual sense (TTL,
invalidation). It's request-scoped memoization. If, within a
SINGLE GraphQL request, there's a Mutation that CHANGES a user,
and AFTER it a resolver calls userLoader.load(the same id) again
— DataLoader returns the STALE cached value, not reflecting the
change.

Solution: after a mutation, explicitly call
ctx.userLoader.clear(id) or
ctx.userLoader.prime(id, updatedData)
for the specific key the mutation changed.
```

## DataLoader is created PER REQUEST — why this isn't optional

```ts
// NestJS / Apollo Server — a NEW instance in context for every request
const server = new ApolloServer({
  schema,
  context: async () => ({
    userLoader: createUserLoader(db),
  }),
});
```

```txt
If createUserLoader() is moved outside of context (as a
singleton created once at server startup):

  1. The cache isn't reset between requests from different
     users — User A could get cached data that was fetched
     while handling User B's request (a data leak in
     multi-tenant systems with different access rights)

  2. The cache grows unbounded (memory leak) — there's no point
     where it's cleared

This is the same "request-scoped vs singleton" pattern as
context in general (see [Schema, Types, and Resolvers]) —
DataLoader MUST live for exactly one GraphQL request.
```

## DataLoader doesn't replace JOIN — when to use which

```txt
DataLoader = an APPLICATION-LEVEL batching layer. It turns N
"WHERE id = X" queries into 1 "WHERE id IN (...)" query — but
that's still N+1 → 2 queries, not 1.

JOIN = a SQL operation that does 1 query for ALL levels at once —
but requires the JOIN shape to be known BEFORE the query runs
(i.e., suits REST with a fixed response shape, not arbitrary
GraphQL queries).

In practice:
  - DataLoader — a general-purpose solution for GraphQL
    resolvers, works for ANY shape of client query
  - If profiling shows that a SPECIFIC frequent query (e.g.,
    User.posts is ALMOST ALWAYS requested together with users)
    gets a noticeable win from a JOIN — you can add a targeted
    optimization to the Query.users resolver (eager-loading via
    include), and DataLoader for posts simply won't be needed in
    that case (its cache stays untouched, since .load() was never
    called)
```

## How to diagnose N+1 in a real project

```txt
1. Enable SQL query logging (Prisma: log: ['query'])
2. Run a GraphQL query with an array of N elements at the top
   level
3. If the log shows N+1 queries (or more, with multiple levels
   of nesting — N*M+1) instead of 1-2 — that's N+1

Tools: Apollo Server plugins for counting resolver calls, Prisma
query logging, APM tracing (see [Performance and Security] for
monitoring GraphQL in general).
```

## Nested N+1 — when one DataLoader isn't enough

```graphql
query {
  users {
    posts {
      comments {
        author { name }
      }
    }
  }
}
```

```txt
Each level of nesting is a SEPARATE potential N+1 point, and each
needs its OWN DataLoader (postsByUserLoader, commentsByPostLoader,
userByIdLoader for author). There's no such thing as "one
DataLoader for everything" — a DataLoader is batched for a
SPECIFIC batch function shape (one key type → one value type).

With deep nesting, the total number of SQL queries becomes "1 per
level" (not "1 per node"), which is DataLoader's goal — but NOT
"1 query for the whole graph."
```

## Connection to other topics

```txt
[GraphQL Fundamentals]            — "the client decides the
                                      response shape" — the root
                                      cause why include/JOIN can't
                                      be hardcoded upfront
[Schema, Types, and Resolvers]    — why an array field's resolver
                                      is called N times; context
                                      as request-scoped storage
                                      for DataLoader
[Performance and Security]         — monitoring query counts,
                                      query complexity
[Queries, Mutations, and
 Subscriptions]                     — invalidating the DataLoader
                                      cache after mutations within
                                      one request
```

## Common interview mistakes

- **"N+1 is an ORM/Prisma bug"** — not understanding that the cause is GraphQL's resolver architecture (each array field → a separate resolver call per element), not a specific ORM.

- **"include/JOIN solves N+1 for GraphQL the same way it does for REST"** — not explaining that in GraphQL the query shape isn't known in advance, so include can't be statically hardcoded into a resolver without losing flexibility.

- **Returning batch function results in an order that doesn't match the input ids** — not knowing that DataLoader maps results to keys POSITIONALLY, and getting the order wrong means one user's data can "arrive" for another.

- **"DataLoader's cache is a regular TTL cache"** — not understanding it's request-scoped memoization, which can return stale data after a mutation within the same request unless `.clear()`/`.prime()` is called.

- **Creating a DataLoader as a singleton at server startup** — not seeing the risk of cache leaks between users and unbounded memory growth.

- **"DataLoader fully replaces JOIN"** — not understanding that DataLoader gives O(nesting levels) queries, not O(1), and for frequently-requested relations a targeted JOIN can be faster.
