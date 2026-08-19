# Transaction Isolation Levels

## Why isolation levels exist — and why "full isolation" is expensive

An isolation level is the setting that decides **what one transaction sees while other transactions are changing the same data**. PostgreSQL has four of them, and they differ only in which anomalies they let through.

The theoretically correct answer would be "each transaction sees only what it would see if all transactions ran strictly one after another". Reaching that requires a lock on every operation, which destroys concurrency. So an isolation level is a trade-off between the strictness of the guarantee and performance.

The SQL standard defines the four levels by listing the **anomalies** that each level prevents. SQL stands for Structured Query Language, the standard language for querying relational data.

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

PostgreSQL does **not** allow a dirty read at any isolation level, including `READ UNCOMMITTED`. MVCC is the reason. Multi-Version Concurrency Control keeps several versions of every row, and a reader only ever sees versions marked as committed. Details in [MVCC, Locks, and Vacuum](./05-mvcc-locks-vacuum.md).

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

Why this is a problem: transaction A may already have used the first value, 100, to make a business decision. Now the second `SELECT` contradicts the first one inside a single logical operation.

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

The difference from a non-repeatable read: there an **existing** row changes its value, here **new** rows appear or disappear.

In PostgreSQL, `REPEATABLE READ` prevents phantom reads too, thanks to the MVCC snapshot. The standard's `REPEATABLE READ` is weaker: it only promises protection from non-repeatable reads.

### Serialization Anomaly — the result doesn't match any sequential order

```sql
-- Both transactions run AT THE SAME TIME; the steps interleave.
-- Business rule: the total across all accounts must never fall below 900.

-- Transaction A:
BEGIN;
SELECT SUM(balance) FROM accounts;  -- → 1000
-- 1000 - 100 = 900, so taking 100 out is allowed
UPDATE accounts SET balance = balance - 100 WHERE id = 1;

-- Transaction B (at the same moment):
BEGIN;
SELECT SUM(balance) FROM accounts;  -- → 1000 (the same sum!)
-- B does the same arithmetic on the same number
UPDATE accounts SET balance = balance - 100 WHERE id = 2;

-- Transaction A:
COMMIT;

-- Transaction B:
COMMIT;
-- The total is now 800, and the rule is broken.
```

Run these one after the other and the second transaction reads 900, so it stops. Run them together and each one reads the total before the other's write lands, so the outcome matches no sequential order at all. That is a serialization anomaly, and only `SERIALIZABLE` catches it. Its everyday form has its own section below, under the name write-skew.

## The four PostgreSQL isolation levels — what actually happens

| Level | Dirty Read | Non-Repeatable Read | Phantom Read | Serialization Anomaly |
|---|---|---|---|---|
| `READ UNCOMMITTED` | impossible* | possible | possible | possible |
| `READ COMMITTED` | impossible | possible | possible | possible |
| `REPEATABLE READ` | impossible | impossible | impossible* | possible |
| `SERIALIZABLE` | impossible | impossible | impossible | impossible |

Both starred cells are PostgreSQL extras rather than standard behaviour. PostgreSQL implements `READ UNCOMMITTED` as `READ COMMITTED`, and its `REPEATABLE READ` also prevents phantom reads — an MVCC bonus.

### READ COMMITTED — the default level, most widely used

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED; -- or just BEGIN (this is the default)
```

A snapshot is taken at the start of **each statement**, so this is a statement-level snapshot. That means:

- `SELECT` #1 sees every commit that landed before `SELECT` #1.
- `SELECT` #2, later in the same transaction, sees every commit before `SELECT` #2 — including the ones that happened between #1 and #2.

This is exactly where a non-repeatable read comes from.

Typical use case: more than 90% of CRUD applications (create, read, update, delete). It is enough for any operation that does not need one consistent data view across the whole transaction.

### REPEATABLE READ — snapshot at BEGIN time

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

The snapshot is created **once**, at the first statement of the transaction. In PostgreSQL that is either at `BEGIN` or at the first `SELECT`, depending on the context. Every later `SELECT` in the transaction sees that one snapshot, no matter what other transactions commit meanwhile.

A PostgreSQL specific: the mechanism is MVCC, not range locks as in Oracle. That is why `REPEATABLE READ` also prevents phantom reads — rows another transaction inserted after your snapshot are simply not visible.

Writes can still fail here. Suppose your transaction updates or deletes a row that another transaction changed and committed after your snapshot. PostgreSQL then rolls your transaction back:

```txt
ERROR:  could not serialize access due to concurrent update
```

That message belongs to `REPEATABLE READ`, not to `SERIALIZABLE`. Its SQLSTATE is 40001, so the retry logic is the same. SQLSTATE is the five-character error code that every PostgreSQL error carries.

When to use it: financial analytics, reports and aggregations — anywhere a consistent view as of the query start matters.

### SERIALIZABLE — full isolation via SSI

```sql
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

PostgreSQL implements `SERIALIZABLE` through SSI, which stands for Serializable Snapshot Isolation. It avoids traditional read locks, because those destroy concurrency. Instead it tracks the read/write dependencies between transactions.

Sometimes the combined result of two concurrent transactions matches no sequential order of those same transactions. PostgreSQL detects that and fails one of them:

```txt
ERROR:  could not serialize access due to read/write dependencies
        among transactions
HINT:   The transaction might succeed if retried.
```

This is the SSI check reporting itself, and only `SERIALIZABLE` can produce it. A `SERIALIZABLE` transaction can also get the plain "concurrent update" error shown above. The first-updater-wins rule of `REPEATABLE READ` still applies here.

Both messages carry SQLSTATE 40001. The application **must** catch that code and retry the transaction.

When to use it: banking operations with balances and limits, billing, and any case where a write-skew anomaly could break a business invariant.

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

Write-skew is a class of anomalies where each transaction on its own keeps the invariant, but the two together break it. `REPEATABLE READ` prevents non-repeatable reads and phantom reads, but **not** write-skew — each transaction did see a correct snapshot.

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

- [ACID and Transactions](./02-acid-transactions.md) — I (isolation) as one of the four ACID principles: atomicity, consistency, isolation, durability.
- [MVCC, Locks, and Vacuum](./05-mvcc-locks-vacuum.md) — the MVCC mechanism that lets PostgreSQL build snapshots without read locks.
- [Query Planner and EXPLAIN](./06-query-planner-explain.md) — the isolation level affects the planner's choices in edge cases.

## Common interview mistakes

- **"`READ UNCOMMITTED` allows reading uncommitted data in PostgreSQL"** — it does not. PostgreSQL implements `READ UNCOMMITTED` as `READ COMMITTED`, and dirty reads are physically impossible because of MVCC.

- **"`REPEATABLE READ` and `SERIALIZABLE` are just different names for the same thing"** — they are not. The write-skew anomaly is a whole class of anomalies that `REPEATABLE READ` allows and `SERIALIZABLE` prevents.

- **"`SERIALIZABLE` blocks all other transactions"** — it blocks nothing. PostgreSQL implements it through SSI, which tracks dependencies rather than taking explicit read locks. Concurrency survives, and the price is serialization errors you have to retry.

- **"The default isolation level is `SERIALIZABLE` — it's the safest"** — the default is `READ COMMITTED`. `SERIALIZABLE` has to be requested explicitly, and it needs retry logic in the application.

- **"Phantom reads are impossible in `REPEATABLE READ` per the SQL standard"** — the standard does allow them at that level. PostgreSQL gives a stronger guarantee through its MVCC snapshot, but that is an implementation detail, not a standard requirement.
