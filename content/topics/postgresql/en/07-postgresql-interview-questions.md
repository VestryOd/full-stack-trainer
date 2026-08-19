# PostgreSQL: Interview Questions

Questions are grouped thematically. Each group gives a full senior-level answer, then the follow-up questions that usually come next. The goal is to rehearse the whole chain: base question → follow-ups → nuances.

## Group 1: Fundamentals and Architecture

### What is PostgreSQL and how does it differ from other databases?

PostgreSQL is an open-source relational database. It is usually called an ORDBMS (object-relational database management system), because it goes past plain tables: it also has user-defined types and table inheritance. It ships under the PostgreSQL License, which is close to MIT: you may use it inside a commercial product for free.

Four features define it:

- **ACID transactions.** ACID is atomicity, consistency, isolation and durability. They rest on the WAL (Write-Ahead Log): every change is written to that journal before it reaches the data file.
- **MVCC (Multi-Version Concurrency Control).** A read never takes a lock, because the database keeps several versions of the same row.
- **A rich type system.** JSONB (a binary, pre-parsed form of JSON), arrays, `hstore` (a flat key-value dictionary), range types, and your own types through `CREATE TYPE`.
- **Extensibility.** PostGIS for geospatial data, `pg_stat_statements` for query statistics, `pgcrypto` for encryption.

```sql
-- "Object-relational" in two statements
CREATE TYPE address AS (city text, zip text);   -- a user-defined type
CREATE TABLE staff (id serial, home address);   -- used as a column type
```

Against MySQL, PostgreSQL follows the SQL standard (Structured Query Language) more closely. It also supports harder query shapes out of the box:

- **window functions** — compute over a group of rows while keeping every row. That is how you write rankings and running totals.
- **CTEs** — common table expressions. The `WITH name AS (...)` clause names a subquery so you can reuse it.
- **`LATERAL JOIN`** — a join whose right side is allowed to reference each row of the left side.
- **JSONB with GIN indexes** — GIN is a generalized inverted index. It indexes the inside of a document, so you can search by a key stored within JSONB.

| Workload | Usually PostgreSQL | Usually MySQL |
|---|---|---|
| Complex queries, joins, analytics | yes, the standard is followed closely | weaker, historically |
| Simple short reads and writes | fully capable | historically faster |
| Documents and semi-structured data | JSONB plus GIN indexes | weaker JSON support |
| Geospatial data | PostGIS | no equivalent |

MySQL was historically faster on simple OLTP (online transaction processing — many short reads and writes), but PostgreSQL has caught up.

**Typical follow-ups**

- *"What does 'object-relational' mean?"* — Table inheritance (`CREATE TABLE child INHERITS parent`), user-defined types (`CREATE TYPE`), operator overloading, and arrays as a native type. All of that goes beyond Codd's pure relational model.
- *"When would you choose PostgreSQL over MySQL?"* — For complex queries with joins, for analytics, for JSONB workloads and for geospatial data through PostGIS. Also whenever standard compliance matters. MySQL is preferred for simple transactional work with very high write throughput (MySQL Cluster), or when a MySQL ecosystem is already in place.

### How does a SQL query flow through PostgreSQL?

A query passes through six stages, and every stage has a name interviewers expect:

1. **Parser** → AST (abstract syntax tree — the query text parsed into a tree). Syntax errors are caught here.
2. **Analyzer** → query tree. Table names, column names and types are resolved.
3. **Rewriter** → rules. Views are expanded and RLS policies are applied. RLS is row-level security: per-row access rules attached to a table.
4. **Planner / Optimizer** → cost-based optimization, one plan chosen out of many.
5. **Executor** → runs the chosen plan and returns rows.
6. **Buffer Manager** → serves pages from `shared_buffers`, the page cache in memory. On a miss it goes to disk.

```sql
-- The last stage, made visible
SHOW shared_buffers;   -- 128MB on a default installation
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM users WHERE id = 1;
-- Buffers: shared hit=3 → three pages came from the cache, not from disk
```

**Typical follow-ups**

- *"What is `shared_buffers`?"* — The shared in-memory cache of data pages. The default is 128MB, and it is usually configured to about 25% of the machine's memory. A page is read from disk once and then cached, so later reads come from memory.
- *"What is the WAL?"* — Write-Ahead Log, the journal of operations. Before data reaches the data file, the record goes into the WAL and is flushed with `fsync`. That gives the A and the D of ACID: after a crash, replaying the WAL restores the state.

## Group 2: ACID and Transactions

### Explain each ACID principle with its implementation in PostgreSQL

- **A — atomicity.** Implemented through the WAL (Write-Ahead Log — the journal written before the data file). Either every operation of the transaction lands in the heap on `COMMIT`, or the WAL is used to undo them all. The undo path covers both `ROLLBACK` and crash recovery. The primitives are `BEGIN`, `COMMIT` and `ROLLBACK`.
- **C — consistency.** PostgreSQL enforces constraints at `COMMIT` time: `NOT NULL`, `CHECK`, `FOREIGN KEY`, `UNIQUE`. Business consistency, such as "this balance may never go negative", holds only if you wrote it down as `CHECK (balance >= 0)`.
- **I — isolation.** Implemented through MVCC snapshots. MVCC is Multi-Version Concurrency Control. Three levels are usable: `READ COMMITTED`, `REPEATABLE READ` and `SERIALIZABLE`. The first takes a snapshot per statement, the second one snapshot per transaction. `SERIALIZABLE` adds SSI (Serializable Snapshot Isolation), which tracks dependencies between transactions.
- **D — durability.** The WAL is flushed with `fsync` before the `COMMIT` is confirmed to the client. Setting `synchronous_commit = on` guarantees durability. Setting it to `off` is faster, but a crash can then lose roughly 200 ms of data.

```sql
-- SAVEPOINT: a partial rollback point inside one transaction
BEGIN;
INSERT INTO orders (user_id, total) VALUES (1, 500);

SAVEPOINT after_order;
INSERT INTO payments (order_id, amount)
VALUES (currval('orders_id_seq'), 500);
-- Suppose the payment is declined

ROLLBACK TO after_order;  -- undoes the payment, keeps the order
INSERT INTO payments (order_id, method, amount)
VALUES (currval('orders_id_seq'), 'alternative', 500);
COMMIT;
```

**Typical follow-ups**

- *"What is a `SAVEPOINT`?"* — A partial rollback point inside a transaction, as in the example above. `ROLLBACK TO SAVEPOINT` undoes only the operations after that savepoint, not the whole transaction. Use it to try an operation, undo just that operation on error, then continue the same transaction another way.
- *"What happens if you never call `COMMIT` or `ROLLBACK`?"* — When the connection drops, PostgreSQL rolls the unfinished transaction back by itself. The real problem is a connection pool. A connection returned to the pool without `COMMIT` or `ROLLBACK` hands the next client a transaction in the "aborted" state. Every query is then rejected until someone issues an explicit `ROLLBACK`.

### How does Deadlock work and how do you prevent it?

A deadlock is a circular lock wait. Transaction A holds row 1 and waits for row 2, while transaction B holds row 2 and waits for row 1. Neither can move, so neither finishes on its own.

```sql
-- Classic deadlock (the two transactions run concurrently)
-- Transaction A:
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
-- (pause; B runs its first UPDATE)
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- Transaction B:
BEGIN;
UPDATE accounts SET balance = balance - 50  WHERE id = 2;
-- (pause; A runs its first UPDATE)
UPDATE accounts SET balance = balance + 50  WHERE id = 1;
COMMIT;
-- → ERROR: deadlock detected — one transaction is rolled back
```

PostgreSQL finds the cycle in its lock-wait graph after `deadlock_timeout`, which is 1 second by default. It then rolls back one "victim" transaction with `ERROR: deadlock detected`, error code `40P01`. That code is the SQLSTATE, the standard five-character identifier of an error.

Prevention is a discipline, not a setting: always lock rows in the **same order** in every transaction. Above, both transactions should touch `id = 1` first and `id = 2` second. The application also has to catch `40P01` and retry the transaction.

**Typical follow-ups**

- *"How is a deadlock different from lock contention?"* — Lock contention is heavy competition for one lock. The second transaction simply waits until the first releases it, so it resolves itself on `COMMIT` or `ROLLBACK`. A deadlock is a **circular** wait, and it cannot resolve itself at all. The database has to roll one transaction back.

## Group 3: Isolation Levels

### Describe the difference between `READ COMMITTED`, `REPEATABLE READ`, and `SERIALIZABLE`

All three are built on MVCC snapshots. MVCC is Multi-Version Concurrency Control: the database keeps several versions of a row, and a snapshot decides which version a transaction sees.

- **`READ COMMITTED`** (the default) takes a fresh snapshot for every **statement**. It sees everything committed before each `SELECT` starts. So a non-repeatable read is possible: repeat the same `SELECT` and it can return a different value, because another transaction committed in between.
- **`REPEATABLE READ`** takes its snapshot **once**, at the start of the transaction. Every `SELECT` then sees the same data. Thanks to MVCC, PostgreSQL also prevents phantom reads here, which the SQL standard does not require. Write skew is still possible.
- **`SERIALIZABLE`** adds SSI — Serializable Snapshot Isolation. PostgreSQL tracks read and write dependencies between concurrent transactions. If their combined result matches no sequential order, one of them is rolled back. The error code is `40001`, with the message `could not serialize access due to read/write dependencies among transactions`. An update conflict at `REPEATABLE READ` reports the shorter `could not serialize access due to concurrent update` instead. Either way the application must retry.

```sql
-- Write skew: two doctors both go off-call, so nobody stays
-- Transaction A (doctor 1):
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM doctors WHERE on_call = true;  -- → 2
UPDATE doctors SET on_call = false WHERE id = 1;
COMMIT;

-- Transaction B (doctor 2, running at the same time):
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM doctors WHERE on_call = true;  -- → 2, same snapshot
UPDATE doctors SET on_call = false WHERE id = 2;
COMMIT;
-- Result: nobody is on call. SERIALIZABLE would roll one of them back.
```

**Typical follow-ups**

- *"What is write skew?"* — The anomaly in the example above. Each transaction on its own keeps the invariant "somebody stays on call", because each still sees two doctors. Together they break it. `REPEATABLE READ` does not protect you here, while `SERIALIZABLE` detects the conflict through SSI.
- *"Does PostgreSQL support `READ UNCOMMITTED`?"* — Technically yes: the statement `SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED` is accepted. It behaves as `READ COMMITTED`, because MVCC makes a dirty read physically impossible.

## Group 4: Indexes and Internals

### Explain B-Tree indexes, the Left Prefix Rule, and when the Planner skips an index

**B-Tree** is a balanced tree of height O(log N). Its leaf nodes are sorted and linked into a doubly-linked list, which is what makes range queries efficient. It supports `=`, `<`, `<=`, `>`, `>=`, `BETWEEN` and `ORDER BY`.

```sql
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
```

**The Left Prefix Rule** describes what that composite index can do. The keys are sorted first by `user_id`, then by `status` within one `user_id`. Without fixing `user_id`, the values of `status` are scattered across the whole index, so they cannot be found efficiently. The index therefore works for `(user_id)` and for `(user_id, status)`, but not for `status` alone.

**The Planner skips an index** in five situations:

- selectivity is low, as in `WHERE country = 'USA'` where 90% of the users match, and then a Seq Scan is simply cheaper;
- the table is small, and there the index only adds overhead;
- a function wraps the column, as in `WHERE LOWER(email) = ...`;
- an implicit type cast sits between the column and the value;
- `random_page_cost` is set too high for the actual disk, which is the usual case on flash storage.

**Typical follow-ups**

- *"What is a partial index?"* — An index with a `WHERE` clause of its own, for example `CREATE INDEX ... ON orders(created_at) WHERE status = 'pending'`. It indexes only a subset of the rows, so it is smaller and faster. A query carrying the same `WHERE` condition uses it automatically.
- *"What is an Index-Only Scan?"* — Everything the `SELECT` needs is taken straight from the index: the key plus any `INCLUDE` columns. Two conditions have to hold. Every selected field is in the index, and the Visibility Map marks the heap pages as "all-visible".
- *"How does BRIN differ from B-Tree?"* — BRIN is a Block Range INdex. It stores only the minimum and maximum value per range of blocks, so it measures in tens of kilobytes where a B-Tree measures in gigabytes. It works only when physical row order correlates strongly with the column value: time-series data, or append-only logs. On randomly ordered data BRIN is useless.

## Group 5: MVCC, VACUUM, Locks

### Explain MVCC — the mechanism and why PostgreSQL stores multiple row versions

MVCC stands for Multi-Version Concurrency Control. Instead of locking a row on read, PostgreSQL keeps several versions of that row at the same time.

```sql
UPDATE accounts SET balance = 200 WHERE id = 1;
-- The old row is NOT overwritten:
--   its xmax  ← the XID (transaction id) of this transaction
--   a new row is inserted into the heap, with xmin = the same XID
```

Every reading transaction has its own snapshot, made of `xmin`, `xmax` and `xip` (the list of transactions still running). The snapshot decides which version of each row that transaction may see.

The result is the sentence worth remembering: readers don't block writers, and writers don't block readers. That is concurrency without any read locks.

**Typical follow-ups**

- *"What is a dead tuple and where does it come from?"* — The old version of a row after an `UPDATE` or a `DELETE`. Its `xmax` is filled in. No transaction needs it any more, but it is still physically in the heap. It takes up space and slows down a Seq Scan, because visibility must be checked for every version.
- *"What does `VACUUM` do, and how is `VACUUM FULL` different?"* — Plain `VACUUM` marks dead-tuple space as free in the FSM (Free Space Map). It also removes dead index entries and updates the Visibility Map. What it does not do is return space to the operating system. `VACUUM FULL` rebuilds the table from scratch and does return the space. The price is an `ACCESS EXCLUSIVE` lock, which blocks everything on that table. In production, use `pg_repack` instead.
- *"Why does `VACUUM` matter for XID wraparound?"* — PostgreSQL counts transactions in a 32-bit XID (transaction id). `VACUUM` freezes old rows, which means resetting `xmin` on rows already visible to every transaction. Without that freezing the counter wraps around after 2^32 transactions. PostgreSQL then stops accepting queries, to avoid losing data.
- *"When do you need `SELECT ... FOR UPDATE`?"* — For the "check-then-act" pattern: read a value, check a business condition, then update. Without `FOR UPDATE` there is a race. Two transactions read the same value, both decide the condition holds, both update, and the invariant is broken. A plain read with no later `UPDATE` does not need it.

## Group 6: Query Planner and Performance

### How does EXPLAIN ANALYZE work and what should you look for?

`EXPLAIN` prints the execution plan with estimated cost and estimated row counts, without running the query. `EXPLAIN ANALYZE` really runs it and adds the measured values: actual time, actual rows, and loops.

```sql
-- Always add BUFFERS for the full picture of disk and cache reads
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

Five things are worth looking for in the output:

- **Seq Scan on a large table with a `WHERE`** → that column needs an index.
- **estimated rows ≠ actual rows** (`rows=100` against `actual=100000`) → statistics are stale, so run `ANALYZE`.
- **Nested Loop with a high `loops`** → the same lookup repeated thousands of times, which is the SQL form of the N+1 problem. The inner side needs an index.
- **`Sort Method: external merge Disk`** → `work_mem` is too small, so the sort spilled to disk. Raise it inside the session with `SET work_mem = '256MB'`.
- **high `shared read`** → the data does not fit into `shared_buffers`, so the query is reading from disk.

**Typical follow-ups**

- *"Why does the Planner sometimes choose Seq Scan when an index exists?"* — Because it compares costs. At low selectivity many rows match, and then random reads through the index cost more than one sequential pass. Two more reasons are common. `random_page_cost` may be too high for an SSD (solid-state drive), where it should come down to 1.1-2.0. And a function around the column in `WHERE` prevents index use entirely.
- *"What is `pg_stat_statements`?"* — An extension that accumulates statistics over **all** executed queries: `total_exec_time`, `calls`, `mean_exec_time`. It lets you find the expensive queries in production without running `EXPLAIN ANALYZE` on each one. It needs `shared_preload_libraries = 'pg_stat_statements'`.
- *"How do you find slow queries in production without downtime?"* — `pg_stat_statements` is the answer they expect. Three more tools are worth naming. Use `pg_stat_activity` for the queries running right now. Use `log_min_duration_statement` to log every query slower than N milliseconds. Use `auto_explain` to log the plan of a slow query automatically.
