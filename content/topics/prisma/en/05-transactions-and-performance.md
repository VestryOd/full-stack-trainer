# Prisma Transactions and Performance

## Transactions — two modes

Prisma provides two transaction modes. Both translate to `BEGIN / COMMIT / ROLLBACK` in PostgreSQL.

```typescript
// Mode 1: Sequential (batch) — array of operations; results are not available between them
const [user, profile] = await prisma.$transaction([
  prisma.user.create({ data: { email: 'alice@example.com' } }),
  prisma.profile.create({ data: { bio: 'Engineer', userId: 1 } }), // no access to user.id!
]);
// Use when: operations are independent and all data is known upfront

// Mode 2: Interactive — callback, result of one operation available in the next
await prisma.$transaction(async (tx) => {
  const user = await tx.user.create({
    data: { email: 'alice@example.com' },
  });

  // user.id is now known → can be used in the next operation
  await tx.profile.create({
    data: { bio: 'Engineer', userId: user.id },
  });

  const balance = await tx.account.findUnique({
    where: { userId: user.id },
  });

  if (!balance || balance.amount < 100) {
    throw new Error('Insufficient funds'); // automatically → ROLLBACK
  }

  await tx.account.update({
    where: { userId: user.id },
    data: { amount: { decrement: 100 } },
  });
}, {
  isolationLevel: 'Serializable', // optional: set isolation level
  timeout: 5000,                   // ms, default 5000 — ROLLBACK after timeout
  maxWait: 2000,                   // ms to wait for a connection from the pool
});
```

## Isolation Levels and when they matter

```typescript
// PostgreSQL isolation levels via Prisma
type IsolationLevel = 
  | 'ReadUncommitted'  // dirty reads (not recommended)
  | 'ReadCommitted'    // PostgreSQL default — sees only committed data
  | 'RepeatableRead'   // single snapshot for the entire transaction, no non-repeatable reads
  | 'Serializable';    // strictest: transactions appear to run sequentially

// Example: financial operation with Serializable
await prisma.$transaction(async (tx) => {
  const account = await tx.account.findUnique({ where: { id: accountId } });
  
  // Without Serializable: another transaction can change balance between findUnique and update
  // With Serializable: PostgreSQL detects the conflict → one transaction gets an error
  // The application must retry on SerializationFailure (error code 40001)
  
  if (account.balance < amount) throw new Error('Insufficient funds');
  await tx.account.update({ where: { id: accountId }, data: { balance: { decrement: amount } } });
}, { isolationLevel: 'Serializable' });
```

## Locks — SELECT FOR UPDATE via $queryRaw

```typescript
// Prisma has no built-in API for FOR UPDATE
// Use $queryRaw inside a transaction

await prisma.$transaction(async (tx) => {
  // SELECT FOR UPDATE — locks the row until the transaction ends
  const [account] = await tx.$queryRaw<Account[]>`
    SELECT * FROM accounts WHERE id = ${accountId} FOR UPDATE
  `;
  
  if (account.balance < amount) {
    throw new Error('Insufficient funds');
  }
  
  await tx.account.update({
    where: { id: accountId },
    data: { balance: { decrement: amount } },
  });
});
// FOR UPDATE: other transactions that try to UPDATE / SELECT FOR UPDATE the same row
// will wait until the current transaction completes
```

## The N+1 problem — diagnosis and solutions

```typescript
// PROBLEM: N+1
const users = await prisma.user.findMany(); // 1 query
for (const user of users) {
  // N separate queries — one per user!
  const posts = await prisma.post.count({ where: { authorId: user.id } });
}

// SOLUTION 1: include (JOIN)
const usersWithPosts = await prisma.user.findMany({
  include: { posts: { select: { id: true } } },
});
const result = usersWithPosts.map(u => ({ ...u, postCount: u.posts.length }));

// SOLUTION 2: groupBy + aggregate (one SQL query)
const postCounts = await prisma.post.groupBy({
  by: ['authorId'],
  _count: { id: true },
  where: { authorId: { in: users.map(u => u.id) } },
});

// SOLUTION 3: $queryRaw with COUNT (maximum control)
const result = await prisma.$queryRaw<{ id: number; post_count: number }[]>`
  SELECT u.id, COUNT(p.id)::int as post_count
  FROM users u
  LEFT JOIN posts p ON p.author_id = u.id
  GROUP BY u.id
`;

// Diagnosis: enable query logging
const prisma = new PrismaClient({ log: ['query'] });
// Watch the number of queries in the console per HTTP request
```

## Connection Pool — configuration

```typescript
// PrismaClient uses a connection pool by default
// Pool size: min(10, max_connections / 2) by default
// For production: configure explicitly

const prisma = new PrismaClient({
  datasources: {
    db: {
      url: `${process.env.DATABASE_URL}?connection_limit=20&pool_timeout=10`,
    },
  },
});
// connection_limit=20 → max 20 connections in the pool
// pool_timeout=10 → wait 10 sec for a connection, then throw error

// In NestJS: PrismaService is a singleton — one connection pool for the whole app
// NEVER create new PrismaClient() per request!

// For serverless (AWS Lambda, Vercel):
// connection_limit=1 — each function instance has one connection
// Recommended: Prisma Accelerate or PgBouncer for connection pooling in front of Lambda
```

## select instead of include — response optimization

```typescript
// BAD: load the entire User object when only id and email are needed
const users = await prisma.user.findMany({
  include: { posts: true, profile: true }, // loads EVERYTHING including passwords, tokens
});

// GOOD: request only the needed fields
const users = await prisma.user.findMany({
  select: {
    id: true,
    email: true,
    name: true,
    posts: {
      select: { id: true, title: true, createdAt: true },
      where: { published: true },
      orderBy: { createdAt: 'desc' },
      take: 3,
    },
  },
});
// Less data over the wire, less memory, faster JSON serialization

// BAD: deeply nested include
const data = await prisma.user.findMany({
  include: {
    posts: {
      include: {
        comments: {
          include: { author: { include: { profile: true } } },
        },
      },
    },
  },
});
// Can generate a heavy JOIN with a Cartesian product
```

## Bulk operations

```typescript
// createMany — insert many records in one query
await prisma.post.createMany({
  data: posts.map(p => ({ title: p.title, authorId: userId })),
  skipDuplicates: true,
});
// Limitation: createMany does not support nested create (relations)

// updateMany — update by condition
const { count } = await prisma.post.updateMany({
  where: { authorId: userId, published: false },
  data: { published: true },
});

// deleteMany — delete by condition
await prisma.post.deleteMany({
  where: { createdAt: { lt: new Date('2020-01-01') } },
});

// For bulk insert with relations or large volumes → $executeRaw
await prisma.$executeRaw`
  INSERT INTO posts (title, author_id, created_at)
  SELECT title, ${userId}, NOW()
  FROM json_array_elements_text(${JSON.stringify(titles)}::json) as title
`;
```

## Common interview mistakes

- **"Prisma $transaction guarantees isolation from race conditions automatically"** — no. The default isolation level is `ReadCommitted`. Under concurrent transactions, Non-Repeatable Reads and Phantom Reads are possible. For critical operations: `isolationLevel: 'Serializable'` or `SELECT FOR UPDATE` via `$queryRaw`.

- **"Sequential transaction is better than Interactive"** — depends on the task. Sequential is faster (no overhead from keeping the transaction open), but you cannot use the result of one operation in the next. Interactive — use when you need logic between steps (conditions, using a generated id).

- **"include always solves N+1"** — no. Deep nested include (user → posts → comments → author) can generate heavy JOINs with a Cartesian product. Alternatives: `$queryRaw` with an explicit JOIN, `groupBy` + aggregate, or split into two separate queries with `WHERE id IN (...)`.

- **"Connection pool doesn't need configuration"** — it does for production. The default pool size may be insufficient under load or excessive for serverless. For Lambda/Vercel: `connection_limit=1` + PgBouncer/Prisma Accelerate. Without proper pooling: "connection count exceeded" errors.

- **"The timeout in $transaction is how long the SQL runs"** — no. `timeout` is the maximum time for the ENTIRE transaction (including callback execution time). `maxWait` is the time to wait for a connection from the pool. If the callback is slow (e.g., an external API call inside the transaction) → timeout → ROLLBACK. External API calls must not be inside a transaction.
