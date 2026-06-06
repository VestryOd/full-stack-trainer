# MVCC, Locks, and VACUUM

## The Core Problem of Any Database

Imagine:

User A is reading data.

At the same time, User B is updating data.

The question arises:

```txt
What should User A see?
```

Old data?

New data?

Wait for UPDATE to complete?

---

# The Naive Solution

Use locks.

For example:

```txt
Reader takes a lock
Writer waits
```

or

```txt
Writer takes a lock
Reader waits
```

---

Problem:

Under load, everything starts blocking everything else.

---

# PostgreSQL's Solution

MVCC

Multi-Version Concurrency Control

---

The Main Idea of MVCC

PostgreSQL does not modify a row directly.

It creates a new version of the row.

---

Suppose there is a record:

```txt
id=1
balance=100
```

---

UPDATE

```sql
UPDATE accounts
SET balance = 200
WHERE id = 1;
```

---

What actually happens

NOT:

```txt
100 → 200
```

---

But:

```txt
Version 1
balance = 100

Version 2
balance = 200
```

---

The old version continues to exist.

---

# Why This Is Great

A Reader can read:

```txt
Version 1
```

While a Writer creates:

```txt
Version 2
```

---

The result:

```txt
Readers don't block writers
Writers don't block readers
```

---

This is one of the main reasons for PostgreSQL's high performance.

---

# Tuple Versions

Every row in PostgreSQL contains system fields.

Simplified:

```txt
xmin
xmax
```

---

# xmin

Transaction ID of the transaction that created the row.

---

For example:

```txt
Transaction #100
INSERT row
```

---

Then:

```txt
xmin = 100
```

---

# xmax

Transaction ID of the transaction that deleted the row.

---

For example:

```txt
Transaction #200
DELETE row
```

---

Then:

```txt
xmax = 200
```

---

# How SELECT Works

When a transaction executes:

```sql
SELECT *
FROM users;
```

PostgreSQL looks at:

```txt
my snapshot
xmin
xmax
```

---

And decides:

```txt
row is visible
or not visible
```

---

# Snapshot

A snapshot is created when a transaction starts.

---

The snapshot contains:

```txt
which transactions are committed
which are active
```

---

So two transactions can see different versions of the same row.

---

# MVCC Example

Transaction A

```sql
BEGIN;
SELECT balance;
```

Sees:

```txt
100
```

---

Transaction B

```sql
UPDATE balance=200;
COMMIT;
```

---

Transaction A executes again:

```sql
SELECT balance;
```

---

Repeatable Read:

```txt
100
```

---

Read Committed:

```txt
200
```

---

# The Problem with MVCC

Old row versions remain.

---

For example:

```sql
UPDATE users
SET name='John';
```

---

The old row version is not deleted immediately.

---

A:

```txt
dead tuple
```

appears.

---

# Dead Tuple

A row that no one needs anymore.

But it still occupies disk space.

---

Example

```txt
Version 1 ← dead
Version 2 ← active
```

---

Over time they accumulate.

---

# What Happens Without Cleanup

Tables start to grow.

---

For example:

```txt
100 MB of data
```

after a year:

```txt
5 GB table
```

---

Even though live data is still only:

```txt
100 MB
```

---

This is called:

```txt
table bloat
```

---

# VACUUM

VACUUM cleans up dead tuples.

---

It:

```txt
finds old row versions
frees up space
updates statistics
```

---

# Important

VACUUM does NOT reduce the file size.

It makes space available for reuse.

---

# VACUUM FULL

A different mode.

---

It:

```txt
rebuilds the table
returns space to the OS
```

---

But:

```txt
takes an ACCESS EXCLUSIVE LOCK
```

---

Therefore used rarely.

---

# AUTOVACUUM

In most cases runs automatically.

---

A special PostgreSQL process:

```txt
autovacuum worker
```

---

Monitors:

```txt
dead tuples
statistics
table bloat
```

---

# Why You Should Not Disable Autovacuum

A very popular question.

---

If disabled:

```txt
dead tuples grow
indexes bloat
tables grow
performance degrades
```

---

After some time the database will start to degrade.

---

# Locks

MVCC does not eliminate locks entirely.

---

PostgreSQL still uses locks.

---

But much less often.

---

# Row Lock

A single row is locked.

---

For example:

```sql
SELECT *
FROM users
WHERE id = 1
FOR UPDATE;
```

---

Now no one can modify this row.

---

# When FOR UPDATE Is Needed

A very common interview question.

---

For example:

```txt
inventory quantities
account balance
seat reservations
```

---

To avoid race conditions.

---

# Table Lock

The entire table is locked.

---

For example:

```sql
ALTER TABLE users
ADD COLUMN age INTEGER;
```

---

Some DDL operations take a table lock.

---

# Deadlock

Transaction A

```txt
locks row1
waits for row2
```

---

Transaction B

```txt
locks row2
waits for row1
```

---

A cycle forms.

---

PostgreSQL detects deadlocks automatically.

---

Terminates one transaction with an error:

```txt
deadlock detected
```

---

# Senior Interview Answer

What is MVCC?

MVCC (Multi-Version Concurrency Control) is PostgreSQL's concurrency mechanism in which an UPDATE creates a new version of a row instead of modifying the existing one. This means reads and writes rarely block each other. Old row versions are cleaned up by the VACUUM process.
