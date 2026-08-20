# ACID and Transactions

## A transaction is a unit of work with guaranteed properties, not just a "group of queries"

A transaction is a sequence of database operations that moves the database from one **consistent state** to another. ACID is the name of the four guarantees it gives: atomicity, consistency, isolation, durability.

The key word above is "consistent". A transaction is not just an "atomic group", but a group that never leaves data half-changed or invalid. This article takes the four letters one at a time.

```sql
-- Money transfer: the classic example where a partial update is catastrophic
BEGIN;

UPDATE accounts SET balance = balance - 100 WHERE id = 1;
-- If the server crashes here — without a transaction the money would "disappear"

UPDATE accounts SET balance = balance + 100 WHERE id = 2;

COMMIT;   -- only HERE do the changes become visible to other transactions
-- or:
ROLLBACK; -- rolls back ALL changes since BEGIN, as if they never happened
```

**Autocommit.** In PostgreSQL every SQL (Structured Query Language) statement outside an explicit `BEGIN`/`COMMIT` runs in its own implicit transaction. The server wraps it in `BEGIN` and `COMMIT` for you. This is the default behaviour.

The practical consequence: an `INSERT` or `UPDATE` without `BEGIN` is already an atomic transaction, just a single-statement one. Several `UPDATE`s without `BEGIN` each land in their own transaction, so there is no shared rollback.

## A — Atomicity: "all or nothing" at the implementation level

Atomicity is implemented through the WAL — the write-ahead log, which is PostgreSQL's transaction journal. Three steps:

1. Before any data change reaches the disk, PostgreSQL writes a record into the WAL.
2. On `COMMIT` that WAL record is marked as committed, so the data may now be applied to the heap.
3. On `ROLLBACK`, or after a crash before `COMMIT`, PostgreSQL reads the WAL at startup and undoes the unfinished transactions.

The WAL is what gives you both D (durability) and A (atomicity).

```sql
-- SAVEPOINT — partial rollback within a transaction
BEGIN;

INSERT INTO orders (user_id, total) VALUES (1, 500);

SAVEPOINT after_order;

INSERT INTO payments (order_id, amount) VALUES (currval('orders_id_seq'), 500);
-- Suppose the payment is temporarily declined

ROLLBACK TO after_order;  -- rolls back only to the SAVEPOINT; the order is kept

-- Try a different payment method
INSERT INTO payments (order_id, method, amount)
VALUES (currval('orders_id_seq'), 'alternative', 500);

COMMIT;
```

## C — Consistency: constraints guarantees, not "business logic correctness"

A common misconception says that "consistency" in ACID guarantees data is always logically correct. That is not what it guarantees.

PostgreSQL only promises that constraints are not violated after `COMMIT`: `NOT NULL`, `CHECK`, `FOREIGN KEY`, `UNIQUE`. Business logic such as "you cannot transfer more than you have" belongs to the application, or to a `CHECK` constraint.

The difference in practice:

- With `CHECK (balance >= 0)` the database blocks the transfer as soon as the rule is broken.
- Without that `CHECK` the database happily lets `balance` go negative. That is logically wrong, and ACID does not help: there is no constraint to check.

```sql
-- Constraints that enforce C (Consistency)
CREATE TABLE accounts (
    id      BIGSERIAL PRIMARY KEY,
    balance NUMERIC(15, 2) NOT NULL DEFAULT 0
              CHECK (balance >= 0),          -- C: DB won't allow
    owner   TEXT NOT NULL                   --    going negative
);

-- A transaction that violates CHECK → automatic ROLLBACK
BEGIN;
UPDATE accounts SET balance = balance - 10000 WHERE id = 1;
-- rolled back if balance < 10000
COMMIT;
```

## I — Isolation: "concurrent transactions don't interfere" — more complex than it sounds

Full isolation, the `SERIALIZABLE` level, means transactions behave as if they ran one at a time. In practice that is expensive, because locks cut down concurrency.

So PostgreSQL offers several levels with different trade-offs between isolation and concurrency. All of them are built on MVCC (Multi-Version Concurrency Control): the server keeps several versions of a row instead of locking it against readers.

```sql
-- The level is chosen per transaction
BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED;   -- the default
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

- `READ COMMITTED` — the default. It sees data committed **before each statement** inside the transaction starts.
- `REPEATABLE READ` — it sees one snapshot, taken at the **beginning** of the transaction.
- `SERIALIZABLE` — full isolation through SSI, which stands for Serializable Snapshot Isolation.

Each level protects against a different set of anomalies: dirty read, non-repeatable read, phantom read, serialization anomaly. Details in [Isolation Levels](./03-isolation-levels.md).

## D — Durability: COMMIT = data on disk (but it's not that simple)

After `COMMIT` the application gets its confirmation. From that moment the data is guaranteed to survive a power failure, a process crash or an operating system restart.

The mechanism is `fsync`. Before confirming the `COMMIT`, PostgreSQL calls `fsync()` — or `fdatasync()` — on the WAL file. That is a **blocking** call: it waits for the physical disk write to finish.

Three settings change this guarantee:

| Setting | What it does | Risk |
|---|---|---|
| `synchronous_commit = on` | The standard. `fsync()` finishes before the `COMMIT` is confirmed. | None. Durability is guaranteed. |
| `synchronous_commit = off` | Confirms the `COMMIT` **before** `fsync()`. Faster. | A crash can lose up to 600 ms of data: three times `wal_writer_delay`. |
| `fsync = off` | Removes the durability guarantee completely. | Very dangerous. Only for bulk loads you can replay. |

## Deadlock — how it occurs and how PostgreSQL detects it

A deadlock is a circular lock-wait between two or more transactions. Transaction A holds the lock on row 1 and waits for row 2. Transaction B holds the lock on row 2 and waits for row 1. Neither can move forward, so neither ever finishes on its own.

```sql
-- Classic deadlock scenario (executed concurrently)
-- Transaction A:
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
-- (pause; B executes its first UPDATE)
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- Transaction B:
BEGIN;
UPDATE accounts SET balance = balance - 50  WHERE id = 2;
-- (pause; A executes its first UPDATE)
UPDATE accounts SET balance = balance + 50  WHERE id = 1;
COMMIT;
-- → PostgreSQL detects the deadlock and rolls back one transaction
--   with: ERROR: deadlock detected
```

PostgreSQL finds deadlocks with a lock wait graph. After `deadlock_timeout`, which is 1 second by default, it inspects that graph for cycles. When it finds a cycle it picks a victim — usually the transaction that has done the least work — and rolls it back with an `ERROR`.

Your application **must** catch SQLSTATE 40P01, the `deadlock detected` code, and retry the transaction. SQLSTATE is the five-character error code that every PostgreSQL error carries.

Three ways to prevent deadlocks:

- Always update rows in the **same order**. If both transactions touch `id=1` first and `id=2` second, a deadlock is impossible.
- Keep transactions short, so the window for contention stays small.
- Use `SELECT ... FOR UPDATE` with `NOWAIT` or `SKIP LOCKED` when you want explicit control over locking.

## Transactions in the application: Prisma, errors, and long transactions

```ts
// Prisma: interactive transaction (recommended for complex business
// logic with conditions between queries)
await prisma.$transaction(async (tx) => {
  const sender = await tx.account.findUniqueOrThrow({ where: { id: senderId } });

  if (sender.balance < amount) {
    throw new Error('Insufficient funds'); // automatic ROLLBACK
  }

  await tx.account.update({
    where: { id: senderId },
    data: { balance: { decrement: amount } },
  });

  await tx.account.update({
    where: { id: recipientId },
    data: { balance: { increment: amount } },
  });
  // Exiting the callback without an error → automatic COMMIT
});
```

Two rules matter in production.

**1. Transactions must be short.** While a transaction is open it holds its locks. A long transaction also blocks `VACUUM` (see [MVCC, Locks, and Vacuum](./05-mvcc-locks-vacuum.md)), and it holds on to WAL segments, which grows the log on disk.

**2. Network calls inside a transaction are an anti-pattern.**

```ts
await prisma.$transaction(async (tx) => {
  const user = await tx.user.findFirst();
  await fetch('https://external-api.com/notify'); // BAD
  // If fetch hangs for 30 seconds, the transaction keeps
  // holding its locks for those 30 seconds too.
});
```

Do it the other way round: finish the transaction first, then make the external calls.

## Connection to other topics

- [Isolation Levels](./03-isolation-levels.md) — how I (isolation) is concretely implemented through `READ COMMITTED`, `REPEATABLE READ` and `SERIALIZABLE`.
- [MVCC, Locks, and Vacuum](./05-mvcc-locks-vacuum.md) — the mechanism PostgreSQL uses to implement transactions without read locks. MVCC is Multi-Version Concurrency Control.
- [Indexes and Internals](./04-indexes-internals.md) — how the WAL interacts with heap files and indexes when data changes.

## Common interview mistakes

- **"C (Consistency) in ACID means data is always logically correct"** — that is not what it means. Consistency in ACID only covers the database's own constraints: `NOT NULL`, `CHECK`, `FOREIGN KEY`, `UNIQUE`. Business-rule correctness stays the application's job.

- **"ROLLBACK deletes data from the table"** — not understanding the mechanism. PostgreSQL uses the WAL to undo changes not yet applied to the heap, or applies undo through MVCC row versions.

- **"A deadlock is when two queries wait longer than usual"** — not distinguishing a deadlock from lock contention. A deadlock is a circular wait and can never resolve itself. Lock contention is heavy competition for one lock, and it clears as soon as that lock is released.

- **"It's always safe to make external HTTP calls inside `prisma.$transaction`"** — while a transaction is open it holds locks. So an external API that hangs blocks those database rows for the entire wait.

- **"`synchronous_commit = off` is always unsafe, keep it on"** — not knowing the use case. For non-critical data such as event logs it gives a large speed-up. The risk is losing a few hundred milliseconds of data, which is acceptable there.
