# Distributed Locks

## Why Locks Are Needed at All

Imagine the following situation.

---

We have:

```txt
Balance = 100$
```

---

Two simultaneous requests:

```txt
Withdraw 50$

Withdraw 70$
```

---

Both read:

```txt
100$
```

---

We get:

```txt
100 - 50 = 50

100 - 70 = 30
```

---

Result:

```txt
Balance = 30
```

---

But what should have happened:

```txt
one operation succeeds

the second is rejected
```

---

# Race Condition

Very popular question.

---

Race Condition:

```txt
the result depends
on the order of execution
```

---

of operations.

---

# Local Lock

In a monolith you can do:

```ts
mutex.lock()
```

---

But in a distributed system:

```txt
API #1

API #2

API #3
```

---

a local mutex won't help.

---

# Distributed Lock

A shared mechanism is needed.

---

Schema:

```txt
Service A
 ↓
Redis Lock
```

---

While the lock is held:

```txt
Service B
```

---

cannot perform the operation.

---

# Redis Lock

The most popular implementation.

---

Uses:

```bash
SET key value NX EX 30
```

---

# Breaking Down the Command

NX:

```txt
create only if it doesn't exist
```

---

EX:

```txt
TTL
```

---

# Example

```bash
SET order:123 locked NX EX 30
```

---

If the key doesn't exist:

```txt
lock acquired
```

---

If it exists:

```txt
lock is busy
```

---

# Why TTL is Needed

Very popular question.

---

Imagine:

```txt
the service crashed
```

---

Before releasing the lock.

---

Without TTL:

```txt
deadlock forever
```

---

With TTL:

```txt
after 30 seconds
the key disappears
```

---

# Unlock

You can't simply do:

```bash
DEL lock
```

---

Why?

---

Because the lock may have already expired.

---

And been acquired by:

```txt
another process
```

---

# The Correct Way

Use a unique token.

---

For example:

```txt
UUID
```

---

Create:

```bash
SET lock uuid NX EX 30
```

---

When deleting, verify:

```txt
is this the lock owner
```

---

# Lua Script

Very frequently asked.

---

Used to:

```txt
check value

delete atomically
```

---

In one step.

---

# Redlock

The most popular Senior question.

---

The problem.

---

If Redis is a single instance:

```txt
Single Point Of Failure
```

---

Redis goes down.

---

Lock is lost.

---

# Redlock

Uses:

```txt
multiple Redis instances
```

---

For example:

```txt
Redis A

Redis B

Redis C

Redis D

Redis E
```

---

# Acquiring the Lock

Must acquire:

```txt
majority
```

---

For example:

```txt
3 out of 5
```

---

Then the lock is considered successful.

---

# Where It's Used

```txt
Payment Processing

Order Processing

Cron Jobs

Inventory Updates
```

---

# When It's NOT Needed

Very frequently asked.

---

If you have:

```txt
PostgreSQL Transaction
```

---

Often enough:

```sql
SELECT ... FOR UPDATE
```

---

Without Redis Lock.

---

# Common Question

Why can't you use a regular mutex?

Answer:

A mutex only works within a single process, while a distributed lock must synchronize multiple services or application instances.

---

# Common Question

Why is TTL needed?

Answer:

To avoid an infinite deadlock if a process crashes before releasing the lock.

---

# Common Question

What is Redlock?

Answer:

A distributed locking algorithm for Redis that uses multiple independent Redis instances to improve reliability.

---

# Interview Answer

A Distributed Lock allows synchronizing operation execution between multiple application instances. In Redis, the SET NX EX command is typically used for atomic lock acquisition. To improve reliability, the Redlock algorithm operates across multiple Redis nodes.
