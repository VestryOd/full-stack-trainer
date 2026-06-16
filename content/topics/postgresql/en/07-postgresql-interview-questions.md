# PostgreSQL: Interview Questions

Questions are grouped thematically. Each group includes a full senior-level answer + typical follow-up questions. Goal: reproduce the "base question → follow-ups → nuances" chain.

---

## Group 1: Fundamentals and Architecture

### What is PostgreSQL and how does it differ from other databases?

PostgreSQL is an open-source object-relational database management system (ORDBMS), released under the PostgreSQL License (similar to MIT). Key features: ACID transactions via WAL, MVCC with no read locks, a rich type system (JSONB, Arrays, hstore, range types, user-defined types), and extensibility (extensions: PostGIS, pg_stat_statements, pgcrypto).

Difference from MySQL: PostgreSQL adheres more strictly to the SQL standard, natively supports complex queries (window functions, CTEs, LATERAL JOIN), and JSONB with GIN indexes; MySQL was historically faster for simple OLTP, but PostgreSQL has caught up.

```txt
Typical follow-ups:

Q: "What does 'object-relational' mean?"
A: Support for table inheritance (CREATE TABLE child INHERITS parent),
   user-defined types (CREATE TYPE), operator overloading, arrays as
   a native type — it goes beyond Codd's pure relational model.

Q: "When to choose PostgreSQL over MySQL?"
A: For complex queries with JOINs, analytics, JSONB workloads,
   geospatial data (PostGIS), and when SQL standard compliance matters.
   MySQL preferred for: simple OLTP with high write throughput
   (MySQL Cluster), existing MySQL ecosystem.
```

### How does a SQL query flow through PostgreSQL?

```txt
1. Parser → AST (syntax check, syntax errors caught here)
2. Analyzer → Query Tree (resolve table/column names, types)
3. Rewriter → rules (VIEW expansion, RLS policies)
4. Planner/Optimizer → cost-based optimization, plan selection
5. Executor → execute the plan, return rows
6. Buffer Manager → shared_buffers (page cache in RAM), miss → disk
```

```txt
Typical follow-ups:

Q: "What is shared_buffers?"
A: Shared RAM cache for data pages (default 128MB, typically configured
   to 25% of RAM). A page is read from disk once and cached; subsequent
   reads come from RAM.

Q: "What is WAL?"
A: Write-Ahead Log — an operations journal. Before data is written to
   disk, the record goes into WAL (fsync). Provides A (Atomicity) and D
   (Durability): on crash — WAL replay restores the state.
```

---

## Group 2: ACID and Transactions

### Explain each ACID principle with its implementation in PostgreSQL

**A — Atomicity**: implemented via WAL. Either all transaction operations are applied to the heap (COMMIT), or WAL uses undo to roll them back (ROLLBACK / crash recovery). Primitives: `BEGIN / COMMIT / ROLLBACK`.

**C — Consistency**: PostgreSQL enforces CONSTRAINTS (NOT NULL, CHECK, FOREIGN KEY, UNIQUE) at COMMIT time. Business-logic "consistency" (can't go negative) — only if there's a `CHECK (balance >= 0)`.

**I — Isolation**: implemented via MVCC snapshots. Three levels: READ COMMITTED (snapshot per statement), REPEATABLE READ (snapshot per transaction), SERIALIZABLE (SSI — dependency tracking).

**D — Durability**: WAL fsync before confirming COMMIT. `synchronous_commit = on` guarantees D; `off` — faster but risks losing ~200ms of data on crash.

```txt
Typical follow-ups:

Q: "What is SAVEPOINT?"
A: A partial rollback point within a transaction. ROLLBACK TO SAVEPOINT
   undoes only operations after the SAVEPOINT, not the whole transaction.
   Use case: try an operation, roll it back on error, continue the
   transaction a different way.

Q: "What happens if you don't call COMMIT/ROLLBACK?"
A: On connection drop, PostgreSQL automatically ROLLBACKs the unfinished
   transaction. Problem: if a pool connection is "returned" without
   COMMIT/ROLLBACK — the next client gets a transaction in "aborted"
   state, all queries rejected until explicit ROLLBACK.
```

### How does Deadlock work and how do you prevent it?

Deadlock = cyclic lock wait: Transaction A holds row 1 and waits for row 2; Transaction B holds row 2 and waits for row 1 → neither can proceed.

PostgreSQL detects deadlock via the lock-wait graph after `deadlock_timeout` (default 1 sec) and rolls back the "victim" with `ERROR: deadlock detected` (SQLSTATE 40P01).

Prevention: always update rows in the SAME ORDER (`WHERE id = 1`, then `WHERE id = 2` — in both transactions). The application must catch 40P01 and retry the transaction.

```txt
Typical follow-ups:

Q: "How is deadlock different from lock contention?"
A: Lock contention — high competition for one lock (one waits for the
   other to release). Resolves itself on COMMIT/ROLLBACK. Deadlock —
   CYCLIC waiting, fundamentally unresolvable without external
   intervention (DBMS rolls back one transaction).
```

---

## Group 3: Isolation Levels

### Describe the difference between READ COMMITTED, REPEATABLE READ, and SERIALIZABLE

**READ COMMITTED** (default): snapshot is created per STATEMENT. Sees all commits before each SELECT → Non-Repeatable Read is possible (repeated SELECT returns a different value if another transaction COMMITted between them).

**REPEATABLE READ**: snapshot is created ONCE per transaction. All SELECTs see the same data. PostgreSQL (via MVCC) additionally prevents Phantom Reads (the standard doesn't require this). Write-Skew Anomaly is possible.

**SERIALIZABLE** (SSI): PostgreSQL tracks read/write dependencies between transactions. If their concurrent result isn't equivalent to any sequential order — rolls one back with `ERROR: could not serialize access` (SQLSTATE 40001). Application must handle retries.

```txt
Typical follow-ups:

Q: "What is Write-Skew Anomaly?"
A: Both doctors read "2 doctors on duty" and both go home — now nobody
   is there. Each transaction individually doesn't violate the invariant
   (someone is still on duty), but together they do. REPEATABLE READ
   doesn't protect against this; SERIALIZABLE detects the conflict
   via SSI.

Q: "Does PostgreSQL support READ UNCOMMITTED?"
A: Technically yes (SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED),
   but it's implemented as READ COMMITTED — dirty reads are physically
   impossible because of MVCC.
```

---

## Group 4: Indexes and Internals

### Explain B-Tree indexes, the Left Prefix Rule, and when the Planner skips an index

**B-Tree** — a balanced tree with O(log N) height. Leaf nodes are sorted and linked (doubly-linked list) → efficient for range queries. Supports: =, <, <=, >, >=, BETWEEN, ORDER BY.

**Left Prefix Rule** for composite index `(a, b, c)`: data is sorted first by `a`, then by `b` within one `a`, then by `c`. Without fixing `a`, you can't efficiently find `b` — it's scattered across the entire index. Rule: the index works for `(a)`, `(a, b)`, `(a, b, c)`, but not for `(b)` or `(c)` alone.

**When the Planner skips the index**: low selectivity (WHERE country = 'USA' with 90% USA users → Seq Scan is cheaper), small table, function in WHERE (`WHERE LOWER(email) = ...`), implicit type cast, `random_page_cost` too high for SSD.

```txt
Typical follow-ups:

Q: "What is a Partial Index?"
A: An index with a WHERE clause: CREATE INDEX ... ON orders(created_at)
   WHERE status = 'pending'. Indexes only a subset of rows → smaller,
   faster. A query with the same WHERE automatically uses it.

Q: "What is an Index-Only Scan?"
A: All needed SELECT data is taken directly from the index (key + INCLUDE
   columns) without touching the heap. Requires: all SELECT fields in
   the index AND Visibility Map = "all-visible" for heap pages.

Q: "How does BRIN differ from B-Tree?"
A: BRIN stores min/max values per block ranges (tens of KB vs GBs for
   B-Tree). Effective only with HIGH CORRELATION between physical row
   order and column value (time-series, append-only logs). For random
   data, BRIN is useless.
```

---

## Group 5: MVCC, VACUUM, Locks

### Explain MVCC — the mechanism and why PostgreSQL stores multiple row versions

MVCC (Multi-Version Concurrency Control): instead of locking a row on read — store multiple versions of one row simultaneously.

On UPDATE: the old row is NOT overwritten. Its `xmax` gets the XID of the current transaction. A NEW row with `xmin` = transaction's XID is inserted into the heap. Each reading transaction uses its own snapshot (xmin/xmax/xip) to determine the visibility of each row version.

Result: "readers don't block writers, writers don't block readers" — parallelism without read locks.

```txt
Typical follow-ups:

Q: "What is a dead tuple and how does it appear?"
A: An old row version after UPDATE or DELETE with a set xmax. No longer
   needed by any transaction, but still physically in the heap. Takes
   up space, slows down Seq Scan (visibility must be checked for each
   version).

Q: "What does VACUUM do vs VACUUM FULL?"
A: VACUUM: marks dead tuple space as free (FSM), removes dead index
   entries, updates Visibility Map. Does NOT return space to the OS.
   VACUUM FULL: rebuilds the table from scratch (ACCESS EXCLUSIVE LOCK
   → everything is blocked), returns space to the OS. For production
   use pg_repack.

Q: "Why does VACUUM matter for XID Wraparound?"
A: PostgreSQL uses a 32-bit XID (transaction counter). VACUUM "freezes"
   old rows (resets xmin for rows visible to ALL transactions). Without
   freezing, after 2^32 transactions — wraparound: PostgreSQL stops
   accepting queries to prevent data loss.

Q: "When is SELECT ... FOR UPDATE needed?"
A: For the "check-then-act" pattern: read a value → check a business
   condition → update. Without FOR UPDATE — race condition (two
   transactions read the same value, both "see" the condition satisfied,
   both update → invariant violated). For plain reads without a
   subsequent UPDATE — not needed.
```

---

## Group 6: Query Planner and Performance

### How does EXPLAIN ANALYZE work and what should you look for?

`EXPLAIN` — shows the execution plan (estimated cost, rows) without actually running the query. `EXPLAIN ANALYZE` — really executes the query and adds actual time, actual rows, loops.

What to look for:
- **Seq Scan on a large table with WHERE** → needs an index
- **estimated rows ≠ actual rows** (rows=100 vs actual=100000) → stale statistics → `ANALYZE`
- **Nested Loop with high loops** → N+1 problem in SQL, needs index on inner
- **Sort Method: external merge Disk** → work_mem too small (`SET work_mem = '256MB'` in session)
- **high shared read** → data doesn't fit in shared_buffers, heavy disk I/O

```sql
-- Always use BUFFERS for the full I/O picture
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

```txt
Typical follow-ups:

Q: "Why does the Planner sometimes choose Seq Scan when an index exists?"
A: Planner estimates cost: with low selectivity (many rows match), random
   I/O through the index costs more than sequential Seq Scan. Also:
   random_page_cost too high for SSD (should be lowered to 1.1-2.0);
   a function in WHERE prevents index use.

Q: "What is pg_stat_statements?"
A: An extension that accumulates statistics for ALL executed queries
   (total_exec_time, calls, mean_exec_time). Allows finding "expensive"
   queries in production without EXPLAIN ANALYZing each one.
   Requires shared_preload_libraries = 'pg_stat_statements'.

Q: "How do you find slow queries in production without downtime?"
A: pg_stat_statements is the most common answer. Also: pg_stat_activity
   (currently active queries), log_min_duration_statement (log queries
   slower than N ms to the PostgreSQL log), auto_explain (automatically
   log EXPLAIN for slow queries).
```
