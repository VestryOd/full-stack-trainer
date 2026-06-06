# Prisma Transactions and Performance

## The Golden Rule

Prisma does not replace knowledge of PostgreSQL.

---

A very common mistake:

```txt
I know Prisma
↓
Therefore I understand the database
```

---

In reality:

```txt
Prisma
↓
generates SQL
↓
PostgreSQL executes SQL
```

---

Therefore:

- indexes
- MVCC
- transactions
- planner

are still important.

---

# Prisma Transactions

The simplest option.

---

```ts
await prisma.$transaction([
  prisma.user.create(...),
  prisma.profile.create(...),
]);
```

---

Under the hood:

```sql
BEGIN;

INSERT ...
INSERT ...

COMMIT;
```

---

If one query fails:

```sql
ROLLBACK;
```

---

# Interactive Transactions

A more flexible option.

---

```ts
await prisma.$transaction(async (tx) => {

  const user = await tx.user.create(...);

  await tx.profile.create(...);

});
```

---

What happens

Prisma:

```txt
BEGIN
↓
passes tx
↓
all operations use one transaction
↓
COMMIT
```

---

On error:

```txt
ROLLBACK
```

---

# When to Use Interactive Transactions

When the result of a previous query
is needed by the next one.

---

Example:

```txt
created User
↓
got id
↓
created Profile
```

---

# Isolation Levels

Prisma allows specifying the isolation level.

---

For example:

```ts
await prisma.$transaction(
  async (tx) => {},
  {
    isolationLevel: 'Serializable',
  }
);
```

---

Under the hood,
PostgreSQL's isolation is used.

---

# A Very Common Question

Does Prisma protect against race conditions?

---

Answer:

No.

---

Race conditions are solved by:

```txt
PostgreSQL
locks
constraints
transactions
```

---

Not by the ORM.

---

# N+1 Problem

A very common interview topic.

---

Imagine:

```ts
const users = await prisma.user.findMany();
```

---

Then:

```ts
for (const user of users) {
  await prisma.post.findMany(...);
}
```

---

The result:

```txt
1 query for users
+
N queries for posts
```

---

This is:

```txt
N+1 Problem
```

---

# How to Fix It

Use include.

---

```ts
await prisma.user.findMany({
  include: {
    posts: true,
  },
});
```

---

Now Prisma can retrieve data
much more efficiently.

---

# Overusing include

A very important topic.

---

Bad:

```ts
include: {
  posts: {
    include: {
      comments: {
        include: {
          author: true,
        }
      }
    }
  }
}
```

---

You can end up with a massive data graph.

---

And the query will become slow.

---

# select

It is better to return only the needed fields.

---

Bad:

```ts
include: {
  posts: true
}
```

---

Better:

```ts
select: {
  id: true,
  email: true,
}
```

---

# Pagination

Very popular.

---

Bad:

```ts
findMany()
```

on a million rows.

---

Better:

```ts
take: 20
```

---

# Offset Pagination

```ts
skip: 1000
take: 20
```

---

Downside:

The further the page,
the slower the query.

---

# Cursor Pagination

Better for large tables.

---

```ts
cursor: {
  id: 100
}
```

---

Uses an index.

---

# Connection Pool

A very important topic.

---

Prisma does not create a new connection
for every query.

---

A connection pool is used.

---

Otherwise:

```txt
1000 requests
↓
1000 connections
```

---

PostgreSQL will quickly stop responding.

---

# Bulk Operations

Very useful.

---

Bad:

```ts
for (...) {
 create(...)
}
```

---

Better:

```ts
createMany()
```

---

Same for:

```ts
updateMany()
deleteMany()
```

---

# Raw SQL

Sometimes ORM is not enough.

---

Prisma allows:

```ts
await prisma.$queryRaw`
  SELECT *
  FROM users
`;
```

---

Or:

```ts
await prisma.$executeRaw`
  UPDATE users ...
`;
```

---

# When Raw SQL Is Needed

Complex analytical queries.

---

Window Functions.

---

CTE.

---

Database-specific optimizations.

---

# Performance Checklist

Before optimizing:

1. Check EXPLAIN ANALYZE
2. Check indexes
3. Check include
4. Check select
5. Check pagination
6. Check N+1

---

# Interview Answer

Prisma transactions are a wrapper over database transactions. For performance it is important to avoid N+1 queries, use select instead of excessive includes, apply pagination, and remember that real performance issues are usually solved at the SQL and PostgreSQL level, not at the ORM level.
