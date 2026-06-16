# ACID and Transactions

## A transaction is a unit of work with guaranteed properties, not just a "group of queries"

A transaction is a sequence of database operations that moves the DB from one **consistent state** to another. The key word is "consistent": not just an "atomic group," but a group that doesn't leave data in a partially-changed or invalid state.

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

```txt
Autocommit: in PostgreSQL, every SQL statement outside an explicit
BEGIN/COMMIT runs in its own implicit transaction — BEGIN + COMMIT
are wrapped automatically. This is the default behavior.

Practical consequence: INSERT/UPDATE without BEGIN is already a
transaction (atomic), just a single-statement one. Multiple UPDATEs
without BEGIN are each in their own transaction — no shared rollback.
```

## A — Atomicity: "all or nothing" at the implementation level

```txt
Atomicity is implemented via the Write-Ahead Log (WAL):
  1. Before any data change hits the disk, PostgreSQL writes a
     record to the WAL (transaction log)
  2. On COMMIT: the WAL record is marked as committed → data can
     be applied to the heap
  3. On ROLLBACK (or crash before COMMIT): PostgreSQL reads the WAL
     at startup and "undoes" unfinished transactions

WAL is what gives both D (Durability) and A (Atomicity).
```

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

```txt
A common misconception: "Consistency" in ACID guarantees that data
is always "logically correct." That's not right.

PostgreSQL only guarantees that CONSTRAINTS (NOT NULL, CHECK,
FOREIGN KEY, UNIQUE) won't be violated after COMMIT. Business logic
("you can't transfer more than you have") is the APPLICATION's
responsibility — or a CHECK constraint.

The difference in practice:
  CHECK (balance >= 0)  → the DBMS blocks the transfer on violation
  Without CHECK         → the DBMS allows balance to go negative
                          (logically wrong, but ACID doesn't help —
                          there's no constraint to check)
```

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
UPDATE accounts SET balance = balance - 10000 WHERE id = 1; -- rolled back if balance < 10000
COMMIT;
```

## I — Isolation: "concurrent transactions don't interfere" — more complex than it sounds

```txt
Full isolation (Serializable) = transactions run as if they execute
sequentially, one at a time. In practice this is expensive — locks
reduce concurrency.

PostgreSQL supports several isolation levels with different
concurrency/isolation trade-offs (details in [Isolation Levels]):

  READ COMMITTED   — default; sees data committed BEFORE each
                     STATEMENT starts within the transaction
  REPEATABLE READ  — sees a snapshot as of the BEGINNING of the
                     transaction
  SERIALIZABLE     — full isolation via SSI
                     (Serializable Snapshot Isolation)

Each level protects differently against: dirty read, non-repeatable
read, phantom read, serialization anomaly.
```

## D — Durability: COMMIT = data on disk (but it's not that simple)

```txt
After COMMIT, the application gets confirmation — and the data is
guaranteed to survive a power failure, process crash, or OS restart.

Implementation:
  WAL fsync — before confirming COMMIT, PostgreSQL calls fsync()
  (or fdatasync()) on the WAL file — a BLOCKING call that waits for
  the physical disk write.

Settings that affect D:
  synchronous_commit = on    — standard (D guaranteed)
  synchronous_commit = off   — confirmation BEFORE fsync (risk of
                              losing ~200ms of data on crash, but faster)
  fsync = off                — VERY dangerous: completely removes the
                              D guarantee (only for bulk loads where
                              data can be replayed)
```

## Deadlock — how it occurs and how PostgreSQL detects it

```txt
A deadlock is a circular lock-wait between two or more transactions:

  Transaction A: holds lock on row 1, waiting for row 2
  Transaction B: holds lock on row 2, waiting for row 1
  → Neither can proceed → deadlock
```

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

```txt
PostgreSQL detects deadlocks via a lock wait graph: after
deadlock_timeout (default 1 second), PostgreSQL inspects the graph
for cycles. When a cycle is found — it picks a victim (usually the
transaction with the least work done) and rolls it back with ERROR.

The application MUST catch SQLSTATE 40P01 (deadlock detected) and
retry the transaction.

Preventing deadlocks:
  - always update rows in the SAME ORDER (both transactions do id=1
    first, then id=2 — deadlock is impossible)
  - keep transactions short (minimize the window for contention)
  - use SELECT ... FOR UPDATE with NOWAIT or SKIP LOCKED for
    explicit lock control
```

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

```txt
Critical for production:

1. Transactions must be SHORT:
   - While a transaction is open, it holds locks
   - A long transaction blocks VACUUM (see [MVCC, Locks, and Vacuum])
   - A long transaction holds WAL, increasing its size

2. Network calls INSIDE a transaction — an anti-pattern:
   await prisma.$transaction(async (tx) => {
     const user = await tx.user.findFirst();
     await fetch('https://external-api.com/notify'); // BAD
     // If fetch hangs for 30 seconds — the transaction holds
     // locks for 30 seconds
   });

3. Correct: finish the transaction first, then make external calls.
```

## Connection to other topics

```txt
[Isolation Levels]          — how I (Isolation) is concretely
                               implemented via READ COMMITTED /
                               REPEATABLE READ / SERIALIZABLE
[MVCC, Locks, and Vacuum]   — the mechanism PostgreSQL uses to
                               implement transactions without read
                               locks
[Indexes and Internals]     — how WAL interacts with heap files
                               and indexes when data changes
```

## Common interview mistakes

- **"C (Consistency) in ACID means data is always logically correct"** — not understanding that Consistency in ACID context only means database-level constraints (NOT NULL, CHECK, FK) are maintained. Application business-rule correctness is the app's responsibility.

- **"ROLLBACK deletes data from the table"** — not understanding the mechanism: PostgreSQL uses WAL to "undo" changes not yet applied to the heap (or applies undo via MVCC row versions).

- **"A deadlock is when two queries wait longer than usual"** — not distinguishing deadlock (circular wait — fundamentally unresolvable) from lock contention (high competition for one lock — resolves when the lock is released).

- **"It's always safe to make external HTTP calls inside Prisma.$transaction"** — not understanding that while a transaction is open, locks are held, and an external API hang blocks database rows for the entire wait.

- **"synchronous_commit = off is always unsafe — keep it on"** — not knowing the use case: for non-critical data (event logs), `synchronous_commit = off` gives a significant performance boost at the acceptable risk of losing a few hundred milliseconds of data.
