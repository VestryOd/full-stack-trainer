# Prisma — Interview Questions (Senior)

## Group 1: Architecture & Approach

**What is the fundamental difference between Prisma and TypeORM?**

TypeORM is a runtime ORM: Entities with decorators, metadata built at runtime via `reflect-metadata`. Some errors are only caught at runtime. Prisma is schema-first with code generation: `schema.prisma` → `prisma generate` → a typed client. All types are compile-time: a typo in a field name is a TS error, not a runtime crash. Prisma's advantage: precise inference (`{ id: number; email: string }` instead of `User`), excellent IDE autocomplete. TypeORM's advantage: QueryBuilder for dynamically complex queries.

---

**What happens when you change schema.prisma?**

Changing `schema.prisma` by itself does nothing. Two steps are needed: (1) `prisma migrate dev` — compares the schema against the current DB state (via Shadow Database), generates a SQL migration file, and applies it to the dev DB; (2) `prisma generate` — regenerates the TypeScript client (happens automatically in `migrate dev`). If you skip `generate` — TypeScript types are stale and the IDE reports errors. If you skip `migrate dev` — the DB is out of sync with the schema.

---

**What is a Shadow Database and why is it needed?**

A Shadow Database is a temporary DB created by Prisma during `migrate dev`. Workflow: (1) apply ALL existing migrations to the Shadow DB; (2) apply the current schema.prisma state directly to the Shadow DB; (3) diff the two states → generate a precise SQL delta. Without a Shadow DB: it's impossible to determine the exact delta between the real DB state (which may have manual changes) and schema.prisma. For managed DBs (Supabase, PlanetScale): a separate `SHADOW_DATABASE_URL` must be configured.

---

**What is PrismaClient and how should it be initialized in NestJS?**

PrismaClient is a generated TypeScript class that manages the connection pool and query execution via the Prisma Query Engine (Rust). In NestJS: a single `PrismaService extends PrismaClient` singleton registered as a `@Global()` module. `OnModuleInit` → `$connect()`, `OnModuleDestroy` → `$disconnect()`. Creating `new PrismaClient()` per request causes connection leaks and performance degradation (each instance creates a separate connection pool).

---

## Group 2: Schema & Models

**When should you use UUID instead of autoincrement and vice versa?**

UUID (`@default(uuid())`): no predictable sequence (safer for public APIs — IDs can't be guessed), can be generated client-side before insert, convenient when merging data from multiple DBs. Downside: 16 bytes vs 4 bytes, worse B-tree index locality (new rows are not always at the end → page splits). Autoincrement: compact, predictable order, better index performance for bulk inserts. Rule: internal IDs for JOINs → `autoincrement`. Public API resources (`/users/:id`) → `uuid`. Alternative: ULID or CUID — time-sortable UUIDs.

---

**Why use Decimal instead of Float for monetary values?**

`Float` is IEEE 754 double precision, which introduces rounding errors: `0.1 + 0.2 = 0.30000000000000004`. Accumulated errors in financial calculations lead to penny/cent discrepancies. `Decimal @db.Decimal(10, 2)` — exact fixed precision, no representation errors. Alternative: store money as integers (cents/kopecks) as `Int` — then Float is never a concern. In code, use `Decimal.js` for arithmetic with Prisma Decimal values.

---

**When should you add an index and when should you not?**

Add an index for: Foreign Key fields (always — Prisma does not automatically create FK indexes), fields in frequent `WHERE` conditions (email, status, userId), fields in `ORDER BY` when other `WHERE` conditions are present. Do not add indexes for: low-cardinality boolean fields (isActive=true/false — the query planner often ignores them and does a seq scan), fields with no real `WHERE` queries (indexes slow down INSERT/UPDATE), and redundant indexes already covered by an existing composite index.

---

## Group 3: Relations & Queries

**Explain the difference between implicit and explicit Many-to-Many.**

Implicit M2M: `Post[] tags Tag[]` without an explicit join table → Prisma creates a hidden `_PostToTag` table. Simple, but you cannot add fields to the join table or query it directly via the Prisma API. Explicit M2M: an explicit `UserRole` model with `@@id([userId, roleId])` and extra fields (assignedAt, assignedBy). Production recommendation: explicit — more control, fields can be added without migration complexity, and `prisma.userRole.findMany()` gives direct access to the join table. Use implicit only for very simple M2M with no extra data.

---

**What is the difference between include and select, and can they be combined?**

`include: { posts: true }` — load ALL fields of User + all related Post records. `select: { id: true, email: true }` — load ONLY the specified fields, without relations. They cannot be used together at the same level (`{ include, select }` → TypeScript error). Combining: `select: { id: true, posts: { select: { title: true } } }` — select with a nested select for the relation. For performance: `select` is better — does not load unnecessary fields (passwords, tokens), less data over the wire, precise TypeScript type instead of the full Entity.

---

**What is N+1 and how do you diagnose and fix it in Prisma?**

N+1: one query for the list (`findMany` → N records) + N separate queries for related data in a loop. Diagnosis: `log: ['query']` in PrismaClient — see all SQL queries for a single HTTP request. Solutions: (1) `include` — JOIN everything in one query; (2) `groupBy` + `_count` — aggregation in one query; (3) `$queryRaw` with an explicit `LEFT JOIN ... GROUP BY`; (4) two queries with `WHERE id IN (...)` — sometimes more efficient than a heavy JOIN. A deeply nested `include` can produce a Cartesian product — worse than N+1.

---

## Group 4: Transactions & Performance

**When should you use Sequential $transaction vs Interactive?**

Sequential (`$transaction([op1, op2])`): when operations are independent and all data is known upfront. Faster — no overhead from holding an open transaction. Limitation: the result of op1 is not available for op2. Interactive (`$transaction(async tx => { ... })`): when the result of a previous step is needed for the next one (create User → get id → create Profile). Allows: conditional logic inside the transaction, throwing an Error → automatic ROLLBACK. Parameters: `timeout` (maximum transaction time), `maxWait` (time to wait for a connection from the pool), `isolationLevel`.

---

**How do you implement SELECT FOR UPDATE in Prisma?**

Prisma has no built-in API for `FOR UPDATE`. Solution: `$queryRaw` inside `$transaction`:
```typescript
await prisma.$transaction(async (tx) => {
  const [row] = await tx.$queryRaw`SELECT * FROM accounts WHERE id = ${id} FOR UPDATE`;
  // row is locked — other transactions wait
  await tx.account.update({ where: { id }, data: { balance: { decrement: amount } } });
});
```
When `FOR UPDATE` is needed: concurrent transactions read the same row → both see `balance=100` → both deduct → result is $0 instead of an error. `FOR UPDATE` locks the row: a second `SELECT FOR UPDATE` waits until the first transaction completes.

---

**How should you configure the connection pool for production?**

Parameters in DATABASE_URL: `?connection_limit=20&pool_timeout=10`. `connection_limit` — max connections (default: min(10, max_connections/2)). `pool_timeout` — seconds to wait for a connection from the pool (default: 10). For serverless (Lambda, Vercel): `connection_limit=1` — each function instance has one connection; otherwise, thousands of cold starts create thousands of connections. For serverless: add PgBouncer or Prisma Accelerate in front of PostgreSQL. Sign of misconfiguration: "too many connections" errors or high `pool_timeout` error rate.

---

## Group 5: Migrations in Production

**How do you safely add a NOT NULL column to a table with millions of rows?**

Can't do it in one step: `ADD COLUMN name TEXT NOT NULL DEFAULT 'value'` → PostgreSQL locks the table to rewrite every row → downtime. Safe approach (three separate deploys): (1) Migration: `ADD COLUMN name TEXT` — nullable, instant, no lock; (2) Deploy new code: populates `name` for new records + background job fills old ones; (3) Migration: `ALTER COLUMN name SET NOT NULL` — once all rows are populated. Each deploy must be backward-compatible with the previous schema.

---

**What should you do if a migration fails in production?**

Do not: delete the migration file, edit `migration.sql` manually after apply, run `migrate reset`. Correct approach: (1) understand exactly what failed (Prisma stores status in the `_prisma_migrations` table); (2) if the migration was partially applied — write a new migration that reverts the changes; (3) fix the issue in the new migration; (4) `migrate deploy` will apply the corrected migration. Monitoring: in CI/CD, always check the exit code of `migrate deploy` and add a health check after migration.

---

## Group 6: Raw SQL & Complex Queries

**When should you use $queryRaw instead of the Prisma API?**

`$queryRaw` is needed for: (1) window functions (`ROW_NUMBER()`, `RANK()`, `LAG()`/`LEAD()`); (2) recursive CTEs (`WITH RECURSIVE`); (3) `LATERAL JOIN`; (4) PostgreSQL-specific operators (`@>`, `&&` for jsonb/arrays); (5) aggregations unavailable in the Prisma API (`PERCENTILE_CONT`, `ARRAY_AGG`, `STRING_AGG`); (6) `SELECT FOR UPDATE`; (7) batch UPDATE with different values (`UPDATE ... SET ... FROM (VALUES ...)`). Always use the `Prisma.sql` template literal — never string concatenation → SQL injection.

---

**Why doesn't Prisma replace knowledge of PostgreSQL?**

Prisma is an abstraction that generates SQL. Performance is determined by: the presence of indexes (Prisma does not automatically create FK indexes), transaction isolation level (MVCC, deadlock), SQL quality (`EXPLAIN ANALYZE` will reveal a seq scan instead of an index scan), and PostgreSQL configuration (work_mem, shared_buffers, autovacuum). Typical scenario: a Prisma query is slow → `log: ['query']` → see the SQL → `EXPLAIN ANALYZE` → missing index or inefficient JOIN → add `@@index` or rewrite with `$queryRaw`. An ORM removes boilerplate but does not remove the need to understand how the database works.
