# MVCC, Locks, and VACUUM

## MVCC — PostgreSQL's fundamental mechanism explaining why "readers don't block writers"

The naive solution to concurrent access is locks: a Reader takes a shared lock, Writer waits; a Writer takes an exclusive lock, all Readers wait. This works, but becomes a bottleneck under load.

PostgreSQL solves this via **MVCC (Multi-Version Concurrency Control)**: instead of locking a row on read — store multiple versions of one row simultaneously. Each transaction sees a consistent "snapshot" of data at its start time, without blocking others.

## How UPDATE actually works — not "overwrite," but "create a new version"

```sql
UPDATE accounts SET balance = 200 WHERE id = 1;
```

```txt
What ACTUALLY HAPPENS PHYSICALLY:
  1. The old row (balance=100) is NOT DELETED. Its xmax field
     gets the Transaction ID (XID) of the current transaction.
  2. A NEW row (balance=200) is inserted into the heap with
     xmin = XID of the current transaction.
  3. On COMMIT: the new version becomes "visible" to transactions
     that started after the COMMIT.
  4. The old version (xmax != 0) becomes "dead" — a dead tuple.

The heap file after UPDATE (simplified):
  ┌──────────────────────────────┐
  │ xmin=100, xmax=200, bal=100  │  ← dead tuple (xmax is set)
  ├──────────────────────────────┤
  │ xmin=200, xmax=0,   bal=200  │  ← live tuple (xmax=0 → alive)
  └──────────────────────────────┘
```

```txt
Key fields in every heap tuple:
  xmin  — XID of the transaction that created this row
          (INSERT or the UPDATE that created this version)
  xmax  — XID of the transaction that "deleted" this row
          (DELETE or UPDATE-old); 0 = row is alive
  infomask — bit flags (committed, aborted, etc.)
  ctid  — pointer to the latest version of this row
          (UPDATE chain: old ctid → new version)
```

## Transaction snapshot — how PostgreSQL decides "what's visible?"

```txt
At the start of a transaction (at the first statement for READ
COMMITTED, at BEGIN for REPEATABLE READ) PostgreSQL creates a
snapshot containing:

  xmin   — minimum active XID at snapshot time
  xmax   — next XID to be assigned
  xip    — list of active (in-progress) transactions

A row is VISIBLE to a transaction if:
  1. xmin < snapshot.xmin  (created before the snapshot)
     OR xmin is in "committed before snapshot"
     (via pg_clog/pg_xact — commit log)
  2. xmax = 0 OR xmax belongs to an aborted transaction
     OR xmax >= snapshot.xmax (created after the snapshot)

This explains the isolation level behavior:
  READ COMMITTED:   snapshot is refreshed for each statement
  REPEATABLE READ:  snapshot is created once per transaction
```

## HOT Update — optimization for frequent UPDATEs on the same row

```txt
Normal UPDATE: new row version → ALL indexes need updating (new ctid).
Expensive when there are many indexes.

HOT (Heap-Only Tuple) Update: if:
  1. The new version fits on the SAME heap page as the old one
  2. The updated column is NOT indexed

...then PostgreSQL creates a chain within the page:
  old row ctid → new row ctid (on the same page)

Indexes are NOT updated — they still point to the old row, and from
there PostgreSQL follows the HOT chain to the current version.
Savings: no page splits in indexes, less WAL, faster.

Practical consequence: fillfactor < 100 for tables with frequent
UPDATEs reserves free space on the page for new versions:
  ALTER TABLE accounts SET (fillfactor = 70);
  -- 30% of each page is reserved for HOT Updates
```

## Dead Tuples and Table Bloat — why tables "inflate"

```txt
Every UPDATE and DELETE leaves dead tuples:
  - UPDATE: the old row version with a set xmax
  - DELETE: the only row version with a set xmax

Dead tuples occupy disk space and "pollute" pages:
  SELECT * → PostgreSQL reads page → sees dead tuple → checks
  visibility → tuple not visible → skips it.
  Extra I/O for every Seq Scan.

Table bloat: after heavy UPDATE/DELETE a table can occupy 5-10x
more space than it holds in "live" data. This also means indexes
have "holes" (dead index entries).
```

## VACUUM — the dead-tuple cleanup mechanism

```sql
-- Manual run (usually unnecessary with autovacuum configured)
VACUUM users;

-- With stats output
VACUUM VERBOSE ANALYZE users;
```

```txt
What VACUUM does:
  1. Scans the table, finds dead tuples
  2. Marks their space as "free" (in the FSM — Free Space Map)
     for reuse by new rows
  3. Removes dead index entries (for every index on the table)
  4. Updates the Visibility Map (pages where all tuples are
     "all-visible" → enables Index-Only Scan)
  5. Updates pg_class.relpages / reltuples (statistics for Planner)

What VACUUM does NOT do:
  - Does NOT return freed space to the OS (pages remain in the
    file, just marked available for reuse)
  - Does NOT defragment data within pages

VACUUM doesn't take ACCESS EXCLUSIVE LOCK → can run concurrently
with regular SELECT/INSERT/UPDATE/DELETE (only takes
ShareUpdateExclusiveLock).
```

## VACUUM FULL — the radical fix for bloat

```sql
VACUUM FULL users;
-- Alternative: CLUSTER users USING idx_users_pk (with sorting)
```

```txt
VACUUM FULL:
  1. Rebuilds the table from scratch (like CREATE TABLE ... AS
     SELECT live tuples)
  2. Rebuilds all indexes
  3. Returns freed space to the OS (the file shrinks)

Cost: takes ACCESS EXCLUSIVE LOCK on the table → ALL queries
to the table are blocked for the entire duration. For a 100 GB
table — hours.

Production alternative: pg_repack (an extension that does the
same thing without a long lock, using a temp table + triggers).
```

## Autovacuum — how to tune it and why you can't disable it

```txt
autovacuum_vacuum_threshold    = 50      -- min dead tuples
autovacuum_vacuum_scale_factor = 0.2     -- + 20% of row count

Autovacuum triggers when:
  dead_tuples > threshold + scale_factor * reltuples

For a 1,000,000-row table: threshold = 50 + 0.2 * 1,000,000 = 200,050
dead tuples. Under high UPDATE rates this means significant bloat
before the first autovacuum.
```

```sql
-- Tuning autovacuum for hot tables (lots of UPDATE/DELETE)
ALTER TABLE orders SET (
  autovacuum_vacuum_scale_factor = 0.01,  -- trigger earlier: 1% not 20%
  autovacuum_vacuum_threshold    = 100,   -- lower minimum threshold
  autovacuum_analyze_scale_factor = 0.005 -- update stats more often
);
```

```txt
Why you can't disable autovacuum (autovacuum = off):
  1. Table bloat → degraded Seq Scan performance
  2. Index bloat → degraded Index Scan performance
  3. XID Wraparound (critical): PostgreSQL uses a 32-bit XID
     (transaction counter). After 2^32 ≈ 4 billion transactions,
     wraparound occurs. VACUUM "freezes" old XIDs (resets xmin for
     very old rows). Without VACUUM → PostgreSQL shuts down queries
     at the "danger threshold" with:
     "database is not accepting commands to avoid wraparound data loss"
```

## Locks — when MVCC isn't enough

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

```txt
Table lock levels (from weakest to strongest):
  AccessShareLock         — SELECT (taken automatically)
  RowShareLock            — SELECT ... FOR UPDATE
  RowExclusiveLock        — INSERT/UPDATE/DELETE
  ShareUpdateExclusiveLock — VACUUM, CREATE INDEX CONCURRENTLY
  ShareLock               — CREATE INDEX (non-concurrent)
  ExclusiveLock           — REFRESH MATERIALIZED VIEW CONCURRENTLY
  AccessExclusiveLock     — ALTER TABLE, VACUUM FULL, DROP TABLE
                           (blocks EVERYTHING, including SELECT)

DDL operations in production need care — ALTER TABLE takes
AccessExclusiveLock → blocks all queries to the table.
```

## Connection to other topics

```txt
[ACID and Transactions]       — how WAL provides Durability and
                                 Atomicity; deadlock as a special
                                 case of concurrency
[Isolation Levels]            — MVCC snapshots as the foundation
                                 of READ COMMITTED / REPEATABLE READ
[Indexes and Internals]       — dead tuples in indexes, HOT Update
                                 as an optimization, Index-Only Scan
                                 and the Visibility Map
[Query Planner and EXPLAIN]   — stale statistics from a missed
                                 ANALYZE → wrong plans
```

## Common interview mistakes

- **"UPDATE modifies the row in place"** — in PostgreSQL, UPDATE creates a new row version (new tuple) and marks the old one as dead via xmax. The old version stays in the heap until VACUUM.

- **"MVCC completely eliminates locks"** — MVCC eliminates read locks ("readers don't block writers"), but doesn't eliminate write locks at the row level (two concurrent UPDATEs on the same row — the second one waits for the first).

- **"VACUUM shrinks the table file size"** — VACUUM only marks the dead tuple space as available for reuse. Only VACUUM FULL (with ACCESS EXCLUSIVE LOCK) or pg_repack actually shrinks the physical file.

- **"You can disable autovacuum if you run VACUUM manually"** — XID Wraparound risk: without regularly "freezing" old XIDs, PostgreSQL is forced to shut down queries to prevent data loss.

- **"SELECT ... FOR UPDATE is needed for all transactions that read data"** — FOR UPDATE is only needed for the "check-then-act" pattern (read, check condition, update), where a race condition can violate a business invariant. For plain reads, MVCC is enough.
