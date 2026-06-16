# Transaction Isolation Levels

## Why isolation levels exist — and why "full isolation" is expensive

When multiple transactions run concurrently, a question arises: **what data does each transaction see?** The theoretically correct answer is "only what would be seen if all transactions ran strictly sequentially." But achieving this requires locking every operation, which destroys concurrency.

Isolation levels are a trade-off between the strictness of guarantees and performance. The SQL standard defines 4 levels via a list of **anomalies** that each level prevents.

## Three classic concurrency anomalies — with mechanics, not just definitions

### Dirty Read — reading uncommitted data

```sql
-- Transaction A
BEGIN;
UPDATE accounts SET balance = 0 WHERE id = 1;
-- (no COMMIT yet)

-- Transaction B (problematic scenario under Dirty Read)
SELECT balance FROM accounts WHERE id = 1; -- returns 0
-- If A does ROLLBACK — B read data that never existed
```

```txt
PostgreSQL: does NOT support Dirty Read at any isolation level
(including READ UNCOMMITTED). Implemented via MVCC (see
[MVCC, Locks, and Vacuum]) — readers only see row versions
marked as committed.
```

### Non-Repeatable Read — a repeated SELECT returns a different result

```sql
-- Transaction A (READ COMMITTED)
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- → 100

-- Transaction B
UPDATE accounts SET balance = 200 WHERE id = 1;
COMMIT;

-- Transaction A again
SELECT balance FROM accounts WHERE id = 1;  -- → 200 (!!)
-- Same SELECT, different result within one transaction
COMMIT;
```

```txt
Why this is a problem: Transaction A may have used the first value
(100) to make a business decision — and now the second SELECT
contradicts the first within one logical operation.
```

### Phantom Read — a repeated SELECT returns a different row count

```sql
-- Transaction A (REPEATABLE READ in the SQL standard)
BEGIN;
SELECT COUNT(*) FROM orders WHERE status = 'NEW';  -- → 5

-- Transaction B
INSERT INTO orders (status) VALUES ('NEW');
COMMIT;

-- Transaction A
SELECT COUNT(*) FROM orders WHERE status = 'NEW';  -- → 6 (phantom!)
COMMIT;
```

```txt
Difference from Non-Repeatable Read: there, an EXISTING row changes;
here, NEW rows APPEAR (or disappear). In PostgreSQL, REPEATABLE READ
protects against Phantom Read too thanks to the MVCC snapshot (unlike
standard Repeatable Read, which only protects against Non-Repeatable
Read).
```

### Serialization Anomaly — the result doesn't match any sequential order

```sql
-- Transaction A                  -- Transaction B
BEGIN;                            BEGIN;
SELECT SUM(balance)               SELECT SUM(balance)
FROM accounts;  -- → 1000        FROM accounts;  -- → 1000

INSERT INTO audit                 INSERT INTO audit
VALUES ('sum=1000');              VALUES ('sum=1000');

COMMIT;                           COMMIT;
-- Result: both read the same value and wrote the same thing.
-- With sequential execution, one would have read the already-changed sum.
-- This is a Serialization Anomaly — only caught by SERIALIZABLE.
```

## The four PostgreSQL isolation levels — what actually happens

```txt
┌─────────────────────┬──────────────┬───────────────────┬───────────────┬───────────────────────┐
│ Level               │ Dirty Read   │ Non-Repeatable    │ Phantom Read  │ Serialization Anomaly │
│                     │              │ Read              │               │                       │
├─────────────────────┼──────────────┼───────────────────┼───────────────┼───────────────────────┤
│ READ UNCOMMITTED    │ impossible*  │ possible          │ possible      │ possible              │
│ READ COMMITTED      │ impossible   │ possible          │ possible      │ possible              │
│ REPEATABLE READ     │ impossible   │ impossible        │ impossible*   │ possible              │
│ SERIALIZABLE        │ impossible   │ impossible        │ impossible    │ impossible            │
└─────────────────────┴──────────────┴───────────────────┴───────────────┴───────────────────────┘

(*) PostgreSQL implements READ UNCOMMITTED as READ COMMITTED.
(*) PostgreSQL REPEATABLE READ also prevents Phantom Read (MVCC bonus).
```

### READ COMMITTED — the default level, most widely used

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED; -- or just BEGIN (this is the default)
```

```txt
A snapshot is taken at the start of EACH STATEMENT (statement-level
snapshot). This means:
  - SELECT #1 sees all commits before SELECT #1
  - SELECT #2 (later in the same transaction) sees all commits before
    SELECT #2 (including those that happened between SELECT #1 and #2)

This is the source of Non-Repeatable Read.

Typical use case: 90%+ of CRUD applications. Sufficient for most
operations where a consistent data view across the whole transaction
isn't needed.
```

### REPEATABLE READ — snapshot at BEGIN time

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

```txt
A snapshot is created ONCE — at the time of the first statement in
the transaction. All subsequent SELECTs in the transaction see this
snapshot, regardless of new commits from other transactions.

PostgreSQL specificity: thanks to MVCC (not range locks like Oracle),
REPEATABLE READ also prevents Phantom Read — rows inserted by another
transaction after the snapshot was taken are not visible.

When to use: financial analytics, reports, aggregations where a
consistent view at query start time matters.
```

### SERIALIZABLE — full isolation via SSI

```sql
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

```txt
PostgreSQL implements SERIALIZABLE via SSI (Serializable Snapshot
Isolation) — not through traditional read locks (which destroy
concurrency), but by tracking dependencies between transactions
(read/write dependencies).

If PostgreSQL detects that the result of concurrent execution of two
transactions isn't equivalent to any sequential order of their
execution — one transaction fails with:
ERROR: could not serialize access due to concurrent update

The application MUST catch SQLSTATE 40001 and retry the transaction.

When to use: banking operations with balances/limits, billing,
situations where write-skew anomaly could violate business invariants.
```

## Write-Skew Anomaly — the anomaly REPEATABLE READ doesn't catch

```sql
-- Example: two doctors can't both go "off-call" simultaneously —
-- at least one must stay at the clinic

-- Transaction A (Doctor 1 goes off-call)
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM doctors WHERE on_call = true;  -- → 2
-- "Someone else will stay"
UPDATE doctors SET on_call = false WHERE id = 1;
COMMIT;

-- Transaction B (Doctor 2 goes off-call, concurrently with A)
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM doctors WHERE on_call = true;  -- → 2 (same snapshot!)
-- "Someone else will stay"
UPDATE doctors SET on_call = false WHERE id = 2;
COMMIT;

-- Result: both left, nobody at the clinic. This is write-skew.
-- SERIALIZABLE would detect the conflict and roll back one transaction.
```

```txt
Write-Skew is a class of anomalies where each transaction individually
doesn't violate the invariant, but their combined execution does.
REPEATABLE READ prevents non-repeatable read and phantom read, but
NOT write-skew (each transaction saw a correct snapshot).
```

## Setting the isolation level in the application

```ts
// Prisma — isolation level at the transaction level
await prisma.$transaction(
  async (tx) => {
    const total = await tx.account.aggregate({ _sum: { balance: true } });
    // The entire report is built on a consistent snapshot
    await tx.report.create({ data: { total: total._sum.balance } });
  },
  { isolationLevel: Prisma.TransactionIsolationLevel.RepeatableRead }
);

// Serializable — for critical financial operations
await prisma.$transaction(
  async (tx) => { /* ... */ },
  { isolationLevel: Prisma.TransactionIsolationLevel.Serializable }
);
```

```sql
-- Raw SQL
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
-- or
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
-- (before the first statement in the transaction)
```

## Connection to other topics

```txt
[ACID and Transactions]         — I (Isolation) as one of the four
                                   ACID principles
[MVCC, Locks, and Vacuum]       — the MVCC mechanism that lets
                                   PostgreSQL implement snapshots
                                   without read locks
[Query Planner and EXPLAIN]     — isolation level affects the
                                   planner's choices in edge cases
```

## Common interview mistakes

- **"READ UNCOMMITTED allows reading uncommitted data in PostgreSQL"** — PostgreSQL implements READ UNCOMMITTED as READ COMMITTED; dirty reads are physically impossible because of MVCC.

- **"REPEATABLE READ and SERIALIZABLE are just different names for the same thing"** — not explaining Write-Skew Anomaly as a class of anomalies that REPEATABLE READ allows but SERIALIZABLE prevents.

- **"SERIALIZABLE blocks all other transactions"** — PostgreSQL implements SERIALIZABLE via SSI (dependency tracking), not via explicit read locks; concurrency is preserved at the cost of possible serialization errors.

- **"The default isolation level is SERIALIZABLE — it's the safest"** — the default is READ COMMITTED; SERIALIZABLE requires explicit specification and retry logic in the application.

- **"Phantom Read is impossible in REPEATABLE READ per the SQL standard"** — the standard allows Phantom Read at REPEATABLE READ; PostgreSQL provides a stronger guarantee (MVCC snapshot), but this is an implementation detail, not a standard requirement.
