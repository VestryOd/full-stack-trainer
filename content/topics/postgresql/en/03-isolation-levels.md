# Transaction Isolation Levels

## Why Isolation Levels Exist

Imagine:

There are two transactions:

Transaction A

```sql
BEGIN;
```

Transaction B

```sql
BEGIN;
```

Both work with the same data.

A question arises:

What should each transaction see?

- uncommitted data?
- old data?
- new data?
- changes from other transactions?

Isolation levels exist to answer this.

---

# Problems They Solve

## Dirty Read

A transaction reads data from another transaction
that has not yet committed.

---

Example

Transaction A:

```sql
BEGIN;

UPDATE accounts
SET balance = 0
WHERE id = 1;
```

COMMIT has not yet been executed.

---

Transaction B:

```sql
SELECT balance
FROM accounts;
```

Gets:

```txt
0
```

---

After that:

```sql
ROLLBACK;
```

---

The result:

Transaction B read data
that never actually existed.

This is a Dirty Read.

---

# Non-Repeatable Read

The same SELECT within a transaction
returns different results.

---

Transaction A:

```sql
BEGIN;

SELECT balance
FROM accounts
WHERE id = 1;
```

Result:

```txt
100
```

---

Transaction B:

```sql
UPDATE accounts
SET balance = 200
WHERE id = 1;

COMMIT;
```

---

Transaction A executes the same query again:

```sql
SELECT balance
FROM accounts
WHERE id = 1;
```

Gets:

```txt
200
```

---

Data changed within a single transaction.

This is a Non-Repeatable Read.

---

# Phantom Read

The problem is not a changed row,
but new rows appearing.

---

Transaction A:

```sql
BEGIN;

SELECT *
FROM orders
WHERE status = 'NEW';
```

Gets:

```txt
5 rows
```

---

Transaction B:

```sql
INSERT INTO orders ...
COMMIT;
```

---

Transaction A repeats the query.

Now:

```txt
6 rows
```

---

A "phantom" appeared.

This is a Phantom Read.

---

# SQL Standard Isolation Levels

The standard defines:

```txt
Read Uncommitted
Read Committed
Repeatable Read
Serializable
```

---

# PostgreSQL and Read Uncommitted

Important:

PostgreSQL does NOT support Dirty Reads.

Therefore:

```txt
Read Uncommitted
=
Read Committed
```

---

# Read Committed

The default level.

The most popular.

---

Each SELECT sees only
committed data.

---

But each new SELECT can see
new commits from other transactions.

---

Allows:

```txt
Non-Repeatable Read
Phantom Read
```

---

Prevents:

```txt
Dirty Read
```

---

Example

SELECT #1

```txt
balance = 100
```

another transaction:

```txt
COMMIT
balance = 200
```

SELECT #2

```txt
balance = 200
```

---

# Repeatable Read

In PostgreSQL, implemented via MVCC snapshot.

---

When a transaction starts:

```sql
BEGIN;
```

a data snapshot is created.

---

All SELECT statements within the transaction
see exactly this snapshot.

---

Even if other transactions execute:

```sql
COMMIT;
```

the data for the current transaction
will not change.

---

Prevents:

```txt
Dirty Read
Non-Repeatable Read
Phantom Read*
```

(*) In PostgreSQL, thanks to MVCC, phantom reads are also effectively prevented.

---

Example

Transaction A:

```sql
BEGIN;
```

sees:

```txt
balance = 100
```

---

Transaction B:

```sql
UPDATE ...
COMMIT;
```

---

Transaction A:

```sql
SELECT ...
```

still sees:

```txt
balance = 100
```

---

# Serializable

The strictest level.

---

PostgreSQL behaves as if
all transactions executed
sequentially one after another.

---

If a conflict occurs:

PostgreSQL terminates one transaction with an error:

```txt
could not serialize access
```

---

The application must retry the transaction.

---

# How to Choose a Level

## Read Committed

90% of applications.

Suitable for:

```txt
CRUD
CMS
typical business applications
```

---

## Repeatable Read

When a consistent view of the data is important.

For example:

```txt
financial analytics
reports
aggregations
```

---

## Serializable

When absolute correctness is required.

For example:

```txt
banking operations
exchanges
billing
```

---

# Interview Question

Why can PostgreSQL provide Repeatable Read without total locks?

Answer:

Thanks to MVCC.
Each transaction works with its own data snapshot,
rather than locking all rows for reading.
