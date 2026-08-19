# MVCC, Locks, and VACUUM

## MVCC — PostgreSQL's fundamental mechanism explaining why "readers don't block writers"

The naive solution to concurrent access is locks. A reader takes a shared lock and a writer waits. A writer takes an exclusive lock and every reader waits. This works, but it becomes a bottleneck under load.

PostgreSQL solves this with **MVCC (Multi-Version Concurrency Control)**. Instead of locking a row on read, the database keeps several versions of the same row at once. Each transaction sees a consistent "snapshot" of the data as of its own start time, and blocks nobody.

Two words below carry the whole article. A **tuple** is one physical version of a row on disk. The **heap** is the main table file where those versions live — the table data outside the indexes.

## How `UPDATE` actually works — not "overwrite," but "create a new version"

```sql
UPDATE accounts SET balance = 200 WHERE id = 1;
```

Physically that one statement does four things:

1. The old row (`balance=100`) is **not** deleted. Its `xmax` field receives the transaction id (XID) of the current transaction.
2. A new row (`balance=200`) is inserted into the heap, with `xmin` set to the XID of the current transaction.
3. On `COMMIT` the new version becomes visible to transactions that start after that commit.
4. The old version now has a non-zero `xmax`, so it is dead. That is a **dead tuple**.

```txt
The heap file after UPDATE (simplified):
  ┌──────────────────────────────┐
  │ xmin=100, xmax=200, bal=100  │  ← dead tuple (xmax is set)
  ├──────────────────────────────┤
  │ xmin=200, xmax=0,   bal=200  │  ← live tuple (xmax=0 → alive)
  └──────────────────────────────┘
```

Every heap tuple carries these fields:

- `xmin` — the XID of the transaction that created this row. That is either an `INSERT`, or the `UPDATE` that produced this version.
- `xmax` — the XID of the transaction that "deleted" this row: a `DELETE`, or the old side of an `UPDATE`. A value of 0 means the row is still alive.
- `infomask` — bit flags (committed, aborted and so on).
- `ctid` — a pointer to the newest version of this row. An `UPDATE` builds a chain: `ctid` of the old version → the new version.

## Transaction snapshot — how PostgreSQL decides "what's visible?"

A transaction takes a **snapshot** when it starts: at the first statement under `READ COMMITTED`, at `BEGIN` under `REPEATABLE READ`. The snapshot is what the transaction is allowed to see.

Careful: a snapshot has its own `xmin` and `xmax` fields, and they do **not** mean what the same names mean on a row. On a row, `xmin` is "who created me". On a snapshot, `xmin` is a boundary: "everything older than this has already finished". The fields below are written as `snapshot.xmin` to keep the two apart.

- `snapshot.xmin` — the lowest XID among the transactions still running when the snapshot was taken.
- `snapshot.xmax` — the next XID the database has not handed out yet.
- `xip` — the list of transactions that were active, that is unfinished, at that moment.

A row is visible to a transaction when both conditions hold:

1. Its `xmin` is below `snapshot.xmin`, so the row was created earlier. It also passes if `xmin` belongs to a transaction that committed before the snapshot. PostgreSQL looks that up in the commit log (`pg_clog` / `pg_xact`).
2. Its `xmax` is 0. Or that `xmax` belongs to a transaction that aborted. Or `xmax` is at or above `snapshot.xmax`, which means the deletion happened after the snapshot.

```txt
Snapshot: snapshot.xmin = 100, snapshot.xmax = 150

Row xmin=90,  xmax=0   → visible: created long before, never deleted
Row xmin=160, xmax=0   → not visible: 160 >= snapshot.xmax, so it
                         was created after the snapshot
```

The isolation levels are built directly on this:

- `READ COMMITTED` — a fresh snapshot for every statement.
- `REPEATABLE READ` — one snapshot for the whole transaction.

## HOT Update — optimization for frequent UPDATEs on the same row

A normal `UPDATE` writes a new row version. Every index on the table then has to be updated too, because the new version sits at a new `ctid`. On a table with many indexes that is expensive.

**HOT (Heap-Only Tuple) Update** skips that work. PostgreSQL can use it when two conditions hold:

1. The new version fits on the **same** heap page as the old one.
2. The updated column is **not** indexed.

Then PostgreSQL links the two versions inside the page: `ctid` of the old row → `ctid` of the new row. The indexes are never touched. They still point at the old row, and from there PostgreSQL walks the HOT chain to the current version. The savings are real: no page splits in indexes, less traffic in the write-ahead log (WAL), and a faster `UPDATE`.

```sql
ALTER TABLE accounts SET (fillfactor = 70);
-- 30% of every page is kept free for HOT Updates
```

A `fillfactor` below 100 reserves free space on each page, and that free space is exactly what a HOT Update needs for the new version. So on tables with frequent `UPDATE`s, lowering `fillfactor` is what makes the optimization possible at all.

## Dead Tuples and Table Bloat — why tables "inflate"

Every `UPDATE` and every `DELETE` leaves dead tuples behind:

- `UPDATE` leaves the old row version, with `xmax` set.
- `DELETE` leaves the only row version, with `xmax` set.

Dead tuples take up disk space and clutter pages. A `SELECT` reads the page, sees a dead tuple, checks its visibility, finds it invisible and skips it. That is extra input/output work on disk for every Seq Scan.

**Table bloat** is the result: after heavy `UPDATE` and `DELETE` traffic a table can occupy 5-10x more space than its live data needs. Indexes get the same holes, called dead index entries.

## VACUUM — the dead-tuple cleanup mechanism

```sql
-- Manual run (usually unnecessary with autovacuum configured)
VACUUM users;

-- With stats output
VACUUM VERBOSE ANALYZE users;
```

`VACUUM` does five things:

1. Scans the table and finds the dead tuples.
2. Marks their space as free in the FSM (Free Space Map), so new rows can reuse it.
3. Removes dead index entries, for every index on the table.
4. Updates the Visibility Map — the record of pages where every tuple is visible to everyone. That map is what makes an Index-Only Scan possible.
5. Updates `pg_class.relpages` and `pg_class.reltuples`, the statistics the planner reads.

What `VACUUM` does **not** do:

- It does not give the freed space back to the operating system. The pages stay inside the file, only marked as available for reuse.
- It does not defragment the data inside a page.

`VACUUM` never takes an `ACCESS EXCLUSIVE` lock; it takes only `ShareUpdateExclusiveLock`. That is why it can run at the same time as ordinary `SELECT`, `INSERT`, `UPDATE` and `DELETE`.

## VACUUM FULL — the radical fix for bloat

```sql
VACUUM FULL users;
-- Alternative: CLUSTER users USING idx_users_pk (with sorting)
```

`VACUUM FULL` goes much further, in three steps:

1. It rebuilds the table from scratch, as if by `CREATE TABLE ... AS SELECT` over the live tuples only.
2. It rebuilds every index.
3. It returns the freed space to the operating system, so the file really does shrink.

The price is the lock. `VACUUM FULL` takes an `ACCESS EXCLUSIVE` lock on the table, so **all** queries against that table are blocked for the whole run. On a table of one hundred gigabytes that means hours.

In production, use `pg_repack` instead. It is an extension that does the same job without a long lock, through a temporary table plus triggers.

## Autovacuum — how to tune it and why you can't disable it

Two settings decide when autovacuum wakes up for a table.

```txt
autovacuum_vacuum_threshold    = 50    -- minimum dead tuples
autovacuum_vacuum_scale_factor = 0.2   -- plus 20% of the rows

Autovacuum triggers when:
  dead_tuples > threshold + scale_factor * reltuples
```

For a table of 1,000,000 rows that threshold is 50 + 0.2 × 1,000,000 = 200,050 dead tuples. Under a high `UPDATE` rate the table therefore bloats a lot before the first autovacuum ever runs.

```sql
-- Tuning autovacuum for hot tables (lots of UPDATE/DELETE)
ALTER TABLE orders SET (
  autovacuum_vacuum_scale_factor = 0.01,  -- trigger earlier: 1% not 20%
  autovacuum_vacuum_threshold    = 100,   -- lower minimum threshold
  autovacuum_analyze_scale_factor = 0.005 -- update stats more often
);
```

There are three reasons you cannot simply set `autovacuum = off`:

1. Table bloat degrades Seq Scan performance.
2. Index bloat degrades Index Scan performance.
3. XID wraparound, which is the critical one. PostgreSQL counts transactions in a 32-bit XID, so after 2^32 ≈ 4 billion transactions the counter wraps around. `VACUUM` prevents that by "freezing" old XIDs: it resets `xmin` on rows that are already visible to everyone. Without `VACUUM`, PostgreSQL stops accepting queries at the danger threshold and reports this:

```txt
database is not accepting commands to avoid wraparound data loss
```

## Locks — when MVCC isn't enough

MVCC removes read locks, not write locks. As soon as the correctness of an update depends on a value you have just read, you need an explicit lock.

```sql
-- Optimistic approach (MVCC): two transactions read, then UPDATE
-- Problem: race condition on "check-then-act"
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- reads 100
-- Another transaction also read 100 and is doing UPDATE...
UPDATE accounts SET balance = balance - 50 WHERE id = 1;
COMMIT;

-- Pessimistic approach: explicit row lock
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;
-- Now other transactions trying to SELECT ... FOR UPDATE on this
-- row WAIT until COMMIT/ROLLBACK
UPDATE accounts SET balance = balance - 50 WHERE id = 1;
COMMIT;
```

```sql
-- FOR UPDATE NOWAIT — immediate error instead of waiting
SELECT * FROM orders WHERE id = 1 FOR UPDATE NOWAIT;
-- ERROR: could not obtain lock on row in relation "orders"

-- FOR UPDATE SKIP LOCKED — skip locked rows
-- (pattern for job queues: each worker picks "its own" task)
SELECT * FROM tasks WHERE status = 'pending'
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

Table lock levels, from the weakest to the strongest:

| Lock level | Taken by |
|---|---|
| `AccessShareLock` | `SELECT` (taken automatically) |
| `RowShareLock` | `SELECT ... FOR UPDATE` |
| `RowExclusiveLock` | `INSERT`, `UPDATE`, `DELETE` |
| `ShareUpdateExclusiveLock` | `VACUUM`, `CREATE INDEX CONCURRENTLY` |
| `ShareLock` | `CREATE INDEX` (non-concurrent) |
| `ExclusiveLock` | `REFRESH MATERIALIZED VIEW CONCURRENTLY` |
| `AccessExclusiveLock` | `ALTER TABLE`, `VACUUM FULL`, `DROP TABLE` — blocks everything, `SELECT` included |

DDL statements (Data Definition Language — statements that change the schema) need care in production. `ALTER TABLE` takes `AccessExclusiveLock`, which blocks every query to that table.

## Connection to other topics

- [ACID and Transactions](./02-acid-transactions.md) — ACID is atomicity, consistency, isolation and durability. That article shows how the write-ahead log provides the durability and the atomicity, and why a deadlock is one special case of concurrency.
- [Isolation Levels](./03-isolation-levels.md) — MVCC snapshots as the foundation of `READ COMMITTED` and `REPEATABLE READ`.
- [Indexes and Internals](./04-indexes-internals.md) — dead tuples inside indexes, HOT Update as an optimization, Index-Only Scan and the Visibility Map.
- [Query Planner and EXPLAIN](./06-query-planner-explain.md) — what stale statistics from a missed `ANALYZE` do to a plan.

## Common interview mistakes

- **"`UPDATE` modifies the row in place"** — in PostgreSQL an `UPDATE` creates a new row version and marks the old one dead through `xmax`. The old version stays in the heap until `VACUUM` clears it.

- **"MVCC completely eliminates locks"** — MVCC eliminates read locks, which is what "readers don't block writers" means. Write locks at row level stay: of two concurrent `UPDATE`s on the same row, the second one waits for the first.

- **"VACUUM shrinks the table file size"** — plain `VACUUM` only marks the space of dead tuples as available for reuse. The physical file shrinks only under `VACUUM FULL`, which takes an `ACCESS EXCLUSIVE` lock, or under `pg_repack`.

- **"You can disable autovacuum if you run `VACUUM` manually"** — that is the XID wraparound risk. Without regular freezing of old XIDs, PostgreSQL is forced to stop accepting queries to protect your data.

- **"`SELECT ... FOR UPDATE` is needed for all transactions that read data"** — you need `FOR UPDATE` only for the "check-then-act" pattern. That is: read a value, check a condition, then update. There a race condition can break a business rule. A plain read is safe with MVCC alone.
