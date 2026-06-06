# Redis Fundamentals

## What is Redis

Redis stands for:

```txt
Remote Dictionary Server
```

---

Redis is:

```txt
In-Memory Data Store
```

---

Very important.

---

Redis:

```txt
is not just a cache
```

---

It can be used as:

```txt
Cache

Database

Message Broker

Queue

Pub/Sub System
```

---

# Why Redis is So Fast

The most popular question.

---

Reason #1

All data lives in memory.

---

PostgreSQL:

```txt
RAM
+
Disk
```

---

Redis:

```txt
RAM
```

---

No disk access
for most operations.

---

# Reason #2

Single-threaded model.

---

Very frequently asked.

---

Redis uses:

```txt
Single Threaded Event Loop
```

---

Similar idea to Node.js.

---

# Why a Single Thread Doesn't Slow Things Down

Because operations are:

```txt
very short
```

---

For example:

```txt
GET key
SET key
INCR counter
```

---

Execute in microseconds.

---

No locks.

---

No race conditions inside Redis.

---

# Reason #3

Optimized data structures.

---

For example:

```txt
Hash Table

Skip List

Linked List
```

---

Tailored for specific operations.

---

# Redis vs PostgreSQL

A very popular question.

---

Redis:

```txt
very fast
```

---

But:

```txt
data lives in memory
```

---

PostgreSQL:

```txt
slower
```

---

But:

```txt
full ACID database
```

---

# When Redis is Used

Most common use cases:

```txt
Caching

Sessions

Rate Limiting

Leaderboards

Counters

Queues
```

---

# When Redis is NOT Used

Very frequently asked.

---

Poor fit for:

```txt
financial transactions

primary data storage

complex relationships
```

---

Typically:

```txt
PostgreSQL
+
Redis
```

---

Work together.

---

# Redis as Cache

The most popular scenario.

---

Flow:

```txt
Request
 ↓
Redis
 ↓
Miss
 ↓
PostgreSQL
 ↓
Redis
 ↓
Response
```

---

# Cache Hit

Data found in Redis.

---

No trip to the database.

---

# Cache Miss

Data not found.

---

Read from the database.

---

# TTL

Time To Live.

---

Very important topic.

---

Example:

```bash
SET user:1 value EX 60
```

---

After:

```txt
60 seconds
```

---

The key is deleted.

---

# Eviction

Very popular question.

---

What to do when memory runs out?

---

Redis supports policies:

```txt
LRU

LFU

TTL
```

---

# LRU

Least Recently Used.

---

Delete:

```txt
least recently used keys
```

---

# Common Question

Why is Redis so fast?

Answer:

Because it stores data in memory, uses a single-threaded Event Loop, and optimized data structures.

---

# Common Question

Can Redis replace PostgreSQL?

Answer:

For most business systems — no. Redis is typically used as an additional caching layer on top of the primary database.

---

# Interview Answer

Redis is a high-performance in-memory data store most commonly used for caching, session storage, counters, and queue implementation. Its high speed comes from storing data in memory and using a single-threaded execution model.
