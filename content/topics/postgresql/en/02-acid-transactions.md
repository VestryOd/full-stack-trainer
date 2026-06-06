# ACID and Transactions

## What is a Transaction

A transaction is a group of operations that executes as a single unit.

The classic example:

Transferring money between accounts.

```txt
Account A -> -100$
Account B -> +100$
```

Both operations must either complete together or not at all.

---

# Transaction Example

```sql
BEGIN;

UPDATE accounts
SET balance = balance - 100
WHERE id = 1;

UPDATE accounts
SET balance = balance + 100
WHERE id = 2;

COMMIT;
```

---

# What if an error occurs?

Then:

```sql
ROLLBACK;
```

and the database will roll back the changes.

---

# ACID

ACID — a set of guarantees provided by PostgreSQL.

---

# A — Atomicity

Either everything executes.

Or nothing.

Example:

```txt
UPDATE A
UPDATE B
```

If UPDATE B fails:

```txt
UPDATE A is also rolled back
```

---

# C — Consistency

After a transaction completes, the database must remain in a valid state.

Example:

There is a constraint:

```sql
balance >= 0
```

A transaction cannot leave data in an invalid state.

---

# I — Isolation

Concurrent transactions must not interfere with each other.

For example:

```txt
User A updates a record
User B reads a record
```

The DBMS must control this interaction.

---

# D — Durability

After COMMIT, data is guaranteed to be saved.

Even if:

- the application crashes
- the server restarts

---

# Transaction Lifecycle

```txt
BEGIN
 ↓
SQL operations
 ↓
COMMIT
```

or

```txt
BEGIN
 ↓
Error
 ↓
ROLLBACK
```

---

# Autocommit

By default, PostgreSQL runs in autocommit mode.

For example:

```sql
UPDATE users
SET name = 'Max'
WHERE id = 1;
```

Effectively executes as:

```sql
BEGIN;
UPDATE ...
COMMIT;
```

---

# When to Use Transactions

Use transactions if:

- multiple tables are being modified
- data must change simultaneously
- there is a risk of partial updates

---

# Example Without a Transaction

```sql
UPDATE orders;
UPDATE inventory;
```

If the second query fails:

```txt
order changed
inventory not changed
```

Data is corrupted.

---

# Example With a Transaction

```sql
BEGIN;

UPDATE orders;
UPDATE inventory;

COMMIT;
```

Either both changes are saved.

Or both are rolled back.

---

# Savepoint

Allows partial rollback.

```sql
BEGIN;

UPDATE users;

SAVEPOINT before_payment;

UPDATE payments;

ROLLBACK TO before_payment;

COMMIT;
```

---

# Deadlock

A deadlock occurs when:

Transaction A waits for B.

Transaction B waits for A.

Example:

```txt
A holds row1
B holds row2

A wants row2
B wants row1
```

A circular wait is formed.

---

# What PostgreSQL Does

PostgreSQL detects deadlocks automatically.

One of the transactions will be terminated with an error:

```txt
deadlock detected
```

---

# Practical Recommendations

Always:

- keep transactions short
- do not make network calls inside a transaction
- do not hold a transaction open longer than necessary
- update rows in a consistent order

---

# Prisma Transaction Example

```ts
await prisma.$transaction([
  prisma.user.create(...),
  prisma.profile.create(...),
]);
```

---

# NestJS + Prisma Example

```ts
await this.prisma.$transaction(async (tx) => {
  const user = await tx.user.create(...);

  await tx.profile.create({
    data: {
      userId: user.id,
    },
  });
});
```

---

# Interview Answer

What is a transaction?

A transaction is a group of operations executed as a single unit. PostgreSQL guarantees ACID properties: atomicity, consistency, isolation, and durability. If one operation inside the transaction fails, all changes are rolled back via ROLLBACK.
