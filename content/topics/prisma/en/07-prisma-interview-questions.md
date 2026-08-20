# Prisma — Interview Questions (Senior)

## Group 1: Architecture & Approach

**What is the fundamental difference between Prisma and TypeORM?**

They build the mapping between your code and your tables at different moments. TypeORM does it while the app runs; Prisma does it ahead of time, by generating code. Both are ORMs — object-relational mappers, the layer that turns classes and method calls into SQL (Structured Query Language), the language the database speaks.

```typescript
// TypeORM — Entities with decorators, metadata read at runtime
@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid') id: string;
  @Column({ unique: true }) email: string;
}
const users = await userRepo.find({ where: { isActive: true } });
// Type of users: User[] — the whole entity, even if you need two fields

// Prisma — the client is generated from schema.prisma
const user = await prisma.user.findUnique({
  where: { id: 1 },
  select: { email: true, naem: true }, // TS error: 'naem' does not exist
});
// Type of user: { email: string } | null — known at compile time
```

- **TypeORM** is a runtime ORM: Entities with decorators, metadata built at runtime via `reflect-metadata`. Some errors are only caught at runtime.
- **Prisma** is schema-first with code generation: `schema.prisma` → `prisma generate` → a typed client. All types are compile-time, so a typo in a field name is a TS error, not a runtime crash.
- **Prisma's advantage** is precise inference: the result type is `{ id: number; email: string }`, not `User`. Your IDE (integrated development environment — the editor you write code in) autocompletes it.
- **TypeORM's advantage** is QueryBuilder, for queries that are assembled dynamically.

---

**What happens when you change schema.prisma?**

By itself, nothing at all. The file is only a description, and two commands turn it into a real change.

```bash
# 1. Create the migration and apply it
npx prisma migrate dev --name add_user_email
# → compares the schema with the current DB state, via a Shadow Database
# → writes prisma/migrations/20240101120000_add_user_email/migration.sql
# → applies that SQL to the dev database
# → runs prisma generate for you

# 2. Regenerate the client only, without a migration
npx prisma generate
# Needed after any schema.prisma change made without migrate dev
```

- `prisma migrate dev` compares the schema against the current state of the DB (database). It generates a SQL migration file and applies it to the dev database.
- `prisma generate` regenerates the TypeScript client. Inside `migrate dev` this happens automatically.

Skip `generate` and the TypeScript types stay stale, so the IDE reports errors on fields that already exist. Skip `migrate dev` and the database is out of sync with the schema.

---

**What is a Shadow Database and why is it needed?**

A Shadow Database is a temporary database that Prisma creates during `migrate dev`. It exists so Prisma can compute the exact SQL delta between your migration history and your current schema.

```txt
Shadow Database — a temporary DB, created during migrate dev:

1. Prisma applies every existing migration to the Shadow DB
2. Applies the current schema.prisma state to the Shadow DB
3. Diffs the two states → generates the new migration.sql
4. Drops the Shadow DB

Without it Prisma cannot know the real current state of the DB,
which may hold manual changes that no migration describes.
```

For managed databases such as Supabase or PlanetScale you have to point Prisma at a separate one:

```prisma
datasource db {
  provider          = "postgresql"
  url               = env("DATABASE_URL")
  shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // a separate dev database
}
```

---

**What is PrismaClient and how should it be initialized in NestJS?**

PrismaClient is the generated TypeScript class you run every query through. It manages the connection pool and passes queries to the Prisma Query Engine, a native binary written in Rust.

```typescript
// prisma.service.ts — the standard singleton in NestJS
@Injectable()
export class PrismaService extends PrismaClient
  implements OnModuleInit, OnModuleDestroy {
  async onModuleInit() {
    await this.$connect();
  }

  async onModuleDestroy() {
    await this.$disconnect();
  }
}

// prisma.module.ts — @Global(), so any module can inject the same instance
@Global()
@Module({ providers: [PrismaService], exports: [PrismaService] })
export class PrismaModule {}
```

- In NestJS there is exactly one instance: a `PrismaService extends PrismaClient` singleton, registered as a `@Global()` module.
- `OnModuleInit` → `$connect()`, `OnModuleDestroy` → `$disconnect()`.
- Creating `new PrismaClient()` per request leaks connections and degrades performance, because each instance opens its own connection pool.

---

## Group 2: Schema & Models

**When should you use UUID instead of autoincrement and vice versa?**

Use `autoincrement` for internal ids you join on, and `uuid` for ids that appear in a public API. UUID stands for universally unique identifier: a random 128-bit value instead of a counter.

```prisma
model Order {
  id       Int    @id @default(autoincrement())  // internal: 4 bytes, sequential
  publicId String @unique @default(uuid())       // shown in /orders/:publicId
}
```

- **What UUID buys you:**
  - no predictable sequence, so nobody can guess someone else's id from their own — safer for public APIs;
  - generation on the client, before the insert;
  - painless merging of data from several databases.
- **What UUID costs:** 16 bytes instead of 4, and worse locality in B-tree indexes. New rows do not always land at the end of the index. That forces page splits: the database breaks a full index page in two.
- **What autoincrement buys you:** a compact key, a predictable order, and better index performance on bulk inserts.
- **The rule:** internal ids used in `JOIN`s → `autoincrement`; public API resources such as `/users/:id` → `uuid`.
- **In between:** ULID (universally unique lexicographically sortable identifier) and CUID (collision-resistant unique identifier). Both stay unique, and both also sort by creation time.

---

**Why use Decimal instead of Float for monetary values?**

Because `Float` cannot store most decimal fractions exactly, and money is decimal fractions.

```prisma
model Payment {
  wrongAmount Float                       // ✗ 0.1 + 0.2 = 0.30000000000000004
  amount      Decimal @db.Decimal(10, 2)  // ✓ exact: 10 digits, 2 after the dot
  amountCents Int                         // ✓ alternative: store whole cents
}
```

- `Float` is double precision in the `IEEE 754` format — the binary floating-point standard almost every language uses. It introduces rounding errors.
- Those errors accumulate across a financial calculation and surface as penny or cent discrepancies.
- `Decimal @db.Decimal(10, 2)` has exact fixed precision, with no representation errors.
- The alternative is money as whole cents or kopecks in an `Int` field. Then Float never enters the picture.
- In code, use `Decimal.js` for arithmetic on Prisma `Decimal` values.

---

**When should you add an index and when should you not?**

Index the columns you really filter or sort by, and leave alone the ones the query planner will ignore anyway.

```prisma
model Post {
  id        Int      @id @default(autoincrement())
  authorId  Int
  status    String   @default("draft")
  createdAt DateTime @default(now())

  @@index([authorId])                       // an FK — always index it
  @@index([status, createdAt(sort: Desc)])  // composite, with sort order
}
```

- **Add an index for:**
  - FK fields — always, because Prisma does not create foreign key (FK) indexes for you;
  - fields in frequent `WHERE` conditions: email, status, userId;
  - fields in `ORDER BY`, when the query also carries other `WHERE` conditions.
- **Do not add an index for:**
  - low-cardinality boolean fields such as `isActive = true/false` — the planner often ignores such an index and does a seq scan, reading the whole table instead;
  - fields that no real query filters on, because every index slows `INSERT` and `UPDATE` down;
  - a column already covered by the leading part of an existing composite index.

---

## Group 3: Relations & Queries

**Explain the difference between implicit and explicit Many-to-Many.**

In an implicit many-to-many (M2M) relation Prisma creates and hides the join table for you. In an explicit one you declare that table yourself, as an ordinary model.

```prisma
// Implicit M2M — no join model; Prisma creates "_PostToTag" itself
model Post {
  id   Int   @id @default(autoincrement())
  tags Tag[]
}
model Tag {
  id    Int    @id @default(autoincrement())
  posts Post[]
}

// Explicit M2M — the join table is a model, so it can carry fields
model UserRole {
  userId     Int
  roleId     Int
  assignedAt DateTime @default(now())
  assignedBy String?

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
  role Role @relation(fields: [roleId], references: [id], onDelete: Cascade)

  @@id([userId, roleId])
  @@index([roleId])
}
```

- **Implicit** is simpler, but the hidden table is out of reach. You cannot add fields to it, and you cannot query it through the Prisma API.
- **Explicit** is the recommendation for production. You get more control, you can add fields such as `assignedAt` or `assignedBy` without complicated migrations, and `prisma.userRole.findMany()` reads the join table directly.
- Use implicit only for very simple M2M relations that carry no extra data.

---

**What is the difference between include and select, and can they be combined?**

`include` gives you the whole model plus the relations you name; `select` gives you only the fields you name. At one level you pick one of the two, but a `select` may hold a nested `select`.

```typescript
// include: every User field + every related Post record
const a = await prisma.user.findUnique({
  where: { id: 1 },
  include: { posts: true },
});

// select: only the listed fields — relations only if you list them too
const b = await prisma.user.findMany({
  select: { id: true, posts: { select: { title: true } } },
});

// ✗ include and select at the same level → TypeScript error
// { include: { posts: true }, select: { id: true } }
```

For performance, `select` is the better default:

- it does not load fields you never asked for, passwords and tokens included;
- less data travels over the wire;
- the TypeScript type is exact, instead of the full entity.

---

**What is N+1 and how do you diagnose and fix it in Prisma?**

N+1 is one query for the list plus one more query per item in that list, usually issued inside a loop. To diagnose it, switch on `log: ['query']` and count the SQL statements for a single HTTP request.

```typescript
// Diagnosis: every SQL query of one HTTP request lands in the console
const prisma = new PrismaClient({ log: ['query'] });

// PROBLEM: 1 query for the users + N queries for the counts
const users = await prisma.user.findMany();
for (const user of users) {
  const count = await prisma.post.count({ where: { authorId: user.id } });
}

// FIX 1: include — everything in one query with a JOIN
const withPosts = await prisma.user.findMany({
  include: { posts: { select: { id: true } } },
});

// FIX 2: groupBy + _count — aggregation in one query
const counts = await prisma.post.groupBy({
  by: ['authorId'],
  _count: { id: true },
});

// FIX 3: $queryRaw with an explicit LEFT JOIN ... GROUP BY
const rows = await prisma.$queryRaw<{ id: number; post_count: number }[]>`
  SELECT u.id, COUNT(p.id)::int AS post_count
  FROM users u LEFT JOIN posts p ON p.author_id = u.id
  GROUP BY u.id
`;
```

- **Fix 4, easy to forget:** two queries, where the second one uses `WHERE id IN (...)`. It is sometimes cheaper than a single heavy `JOIN`.

The trap is a deeply nested `include`. A chain like `user → posts → comments → author` can produce a Cartesian product: every combination of rows from the joined tables. That is worse than the N+1 you started with.

---

## Group 4: Transactions & Performance

**When should you use Sequential $transaction vs Interactive?**

Sequential when the operations are independent and every value is known upfront. Interactive when a later step needs the result of an earlier one.

```typescript
// Sequential — an array of operations, no results in between
const [user, profile] = await prisma.$transaction([
  prisma.user.create({ data: { email: 'alice@example.com' } }),
  prisma.profile.create({ data: { bio: 'Engineer', userId: 1 } }),
]);

// Interactive — a callback: user.id is available in the next step
await prisma.$transaction(async (tx) => {
  const user = await tx.user.create({ data: { email: 'bob@example.com' } });
  await tx.profile.create({ data: { bio: 'Engineer', userId: user.id } });

  const account = await tx.account.findUnique({ where: { userId: user.id } });
  if (!account) throw new Error('No account'); // → automatic ROLLBACK
}, {
  timeout: 5000,   // ms: budget for the whole transaction
  maxWait: 2000,   // ms: how long to wait for a connection from the pool
  isolationLevel: 'Serializable',
});
```

- **Sequential** (`$transaction([op1, op2])`) is faster, because nothing holds an open transaction while your code thinks. Its limitation is the same thing: the result of `op1` is not available to `op2`.
- **Interactive** (`$transaction(async tx => { ... })`) is for chains: create a User → take its id → create the Profile. It also allows conditional logic inside the transaction, and a thrown Error becomes an automatic ROLLBACK.
- Its options: `timeout` (maximum time for the whole transaction), `maxWait` (time to wait for a connection from the pool) and `isolationLevel`.

---

**How do you implement `SELECT FOR UPDATE` in Prisma?**

Prisma has no built-in API for `FOR UPDATE`, so you write it as `$queryRaw` inside `$transaction`.

```typescript
await prisma.$transaction(async (tx) => {
  const [row] = await tx.$queryRaw`
    SELECT * FROM accounts WHERE id = ${id} FOR UPDATE
  `;
  // the row is locked now — other transactions wait for this one
  await tx.account.update({
    where: { id },
    data: { balance: { decrement: amount } },
  });
});
```

Why the lock matters. Two concurrent transactions read the same row and both see `balance=100`. Both subtract, so the account lands on $0 instead of one of them getting an error. `FOR UPDATE` locks that row, so a second `SELECT FOR UPDATE` waits until the first transaction completes.

---

**How should you configure the connection pool for production?**

With query parameters on `DATABASE_URL`: `?connection_limit=20&pool_timeout=10`.

```typescript
const prisma = new PrismaClient({
  datasources: {
    db: {
      url: `${process.env.DATABASE_URL}?connection_limit=20&pool_timeout=10`,
    },
  },
});
```

- `connection_limit` — the maximum number of connections. Default: `min(10, max_connections / 2)`.
- `pool_timeout` — seconds to wait for a connection from the pool before failing. Default: 10.
- For serverless (Lambda, Vercel): `connection_limit=1`, one connection per function instance. Otherwise thousands of cold starts open thousands of connections.
- For serverless, also put PgBouncer or Prisma Accelerate in front of PostgreSQL, so those instances share one pool.

The signs of a misconfigured pool are concrete: "too many connections" errors, or a high rate of `pool_timeout` errors.

---

## Group 5: Migrations in Production

**How do you safely add a `NOT NULL` column to a table with millions of rows?**

In three separate deploys, never in one step. `ADD COLUMN name TEXT NOT NULL DEFAULT 'value'` makes PostgreSQL lock the table and rewrite every row. On millions of rows, that lock is your downtime.

```sql
-- migration 1: nullable column — instant, no table rewrite
ALTER TABLE users ADD COLUMN name TEXT;

-- deploy the new code, then wait for the backfill

-- migration 2: enforce the constraint once every row has a value
ALTER TABLE users ALTER COLUMN name SET NOT NULL;
```

1. Migration: `ADD COLUMN name TEXT` — nullable, instant, takes no lock.
2. Deploy the new code: it populates `name` for new records, while a background job fills in the old ones.
3. Migration: `ALTER COLUMN name SET NOT NULL` — only once all rows are populated.

Every deploy has to stay backward-compatible with the previous schema, because during a rollout the old and the new code run side by side.

---

**What should you do if a migration fails in production?**

Find out what actually failed, then fix it forward with a new migration. Do not rewrite history.

```bash
npx prisma migrate status
# → which migrations are applied, which are pending, which one failed
# Prisma keeps that state in the _prisma_migrations table
```

- **Do not:**
  - delete the migration file;
  - edit `migration.sql` by hand after it was applied;
  - run `migrate reset` — reset drops every table.
- **Do, in this order:**
  1. Understand exactly what failed. Prisma stores the status in the `_prisma_migrations` table.
  2. If the migration was applied only partially, write a new migration that reverts those changes.
  3. Fix the problem in the new migration.
  4. Run `migrate deploy` — it applies the corrected migration.

For monitoring, always check the exit code of `migrate deploy` in your CI/CD pipeline. CI/CD means continuous integration and continuous delivery: the automated build-and-deploy chain. Add a health check right after the migration step.

---

## Group 6: Raw SQL & Complex Queries

**When should you use $queryRaw instead of the Prisma API?**

When the Prisma API has no method for the SQL you need. There are seven such cases:

- window functions: `ROW_NUMBER()`, `RANK()`, `LAG()`/`LEAD()`;
- recursive CTEs — a CTE is a common table expression, the named subquery a `WITH` clause defines — written as `WITH RECURSIVE`;
- `LATERAL JOIN`;
- operators only PostgreSQL has: `@>`, `&&` for jsonb and arrays;
- aggregations the Prisma API does not expose: `PERCENTILE_CONT`, `ARRAY_AGG`, `STRING_AGG`;
- `SELECT FOR UPDATE`;
- batch `UPDATE` where every row gets a different value: `UPDATE ... SET ... FROM (VALUES ...)`.

```typescript
// The Prisma.sql template literal sends values as SQL parameters
const result = await prisma.$queryRaw<{ id: number; rank: number }[]>`
  SELECT id, RANK() OVER (ORDER BY score DESC) as rank
  FROM users
  WHERE created_at > ${new Date('2024-01-01')}
`;

// ✗ never assemble the string yourself — that is an SQL injection
// prisma.$queryRawUnsafe('SELECT * FROM users WHERE id = ' + userId)
```

Always use the `Prisma.sql` template literal, never string concatenation. Concatenation is how an SQL injection gets in.

---

**Why doesn't Prisma replace knowledge of PostgreSQL?**

Because Prisma only generates SQL, and everything that makes that SQL fast or slow still lives inside PostgreSQL.

```sql
EXPLAIN ANALYZE SELECT * FROM posts WHERE author_id = 42;
-- Seq Scan on posts   ← reads the whole table: no index on author_id
-- Index Scan using posts_author_id_idx on posts   ← after adding @@index
```

Four things decide performance, and Prisma controls none of them:

- indexes — and Prisma does not create foreign key indexes on its own;
- the transaction isolation level, with MVCC (multi-version concurrency control) and deadlocks behind it. Under MVCC PostgreSQL keeps several versions of a row, so readers do not block writers;
- the quality of the SQL itself — `EXPLAIN ANALYZE` will show a seq scan, a full table read, where you expected an index scan;
- PostgreSQL configuration: `work_mem`, `shared_buffers`, `autovacuum`.

The debugging path is always the same:

- a Prisma query is slow;
- `log: ['query']` shows the SQL it actually produced;
- `EXPLAIN ANALYZE` on that SQL shows the plan;
- the plan names the problem: a missing index, or an inefficient `JOIN`;
- the fix is `@@index` in the schema, or a rewrite with `$queryRaw`.

An ORM removes boilerplate. It does not remove the need to understand how the database works.
