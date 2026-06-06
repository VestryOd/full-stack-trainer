# Redis Interview Questions (Middle → Senior)

---

# 1. What is Redis?

Redis is a high-performance in-memory data store.

Can be used as:

```txt
Cache
Database
Queue
Message Broker
Pub/Sub
```

---

# 2. Why is Redis so fast?

Main reasons:

```txt
data in memory

single-threaded architecture

no SQL Parser

no Query Planner

simple data structures
```

---

# 3. What does In-Memory Database mean?

Data is stored in RAM rather than read from disk on every request.

---

# 4. Is Redis a database or a cache?

Both are possible.

In practice, it is most often used as:

```txt
Cache Layer
```

on top of PostgreSQL.

---

# 5. Why does Redis use a single thread?

To avoid:

```txt
locks
mutexes
race conditions
```

---

Operations are very short and execute quickly.

---

# 6. Does that mean Redis doesn't use multiple CPUs?

No.

Modern versions use additional threads for:

```txt
network IO

background tasks

persistence
```

---

But commands are executed by one main thread.

---

# 7. What data structures does Redis support?

```txt
String
Hash
List
Set
Sorted Set
Stream
Bitmap
HyperLogLog
```

---

# 8. What is a String?

The basic Redis structure.

---

Example:

```bash
SET user:1 John
GET user:1
```

---

# 9. What is a Hash?

A set of fields inside a single key.

---

Example:

```bash
HSET user:1 name John
```

---

Often used for users.

---

# 10. What is a List?

An ordered collection of elements.

---

Good for:

```txt
Queues
Jobs
```

---

# 11. What is a Set?

A collection of unique values.

---

Good for:

```txt
Tags
Permissions
Followers
```

---

# 12. What is a Sorted Set?

A Set with an additional score.

---

Used for:

```txt
Leaderboards
Ratings
Rankings
```

---

# 13. How to implement a view counter?

Via:

```bash
INCR page_views
```

---

# 14. What is TTL?

Time To Live.

---

The lifetime of a key.

---

Example:

```bash
SET user:1 value EX 60
```

---

# 15. What happens when TTL expires?

The key is automatically deleted.

---

# 16. What is a Cache Hit?

Data found in Redis.

---

No database access needed.

---

# 17. What is a Cache Miss?

Data not found in Redis.

---

Need to go to the database.

---

# 18. What is the Cache Aside Pattern?

The most popular caching pattern.

---

Flow:

```txt
Redis
 ↓ miss
Database
 ↓
Redis
```

---

# 19. What is Write Through?

Updating Redis and the database simultaneously.

---

# 20. What is Write Behind?

First write to Redis.

---

Later asynchronous write to the database.

---

# 21. What is Cache Invalidation?

Deleting or updating stale data in the cache.

---

# 22. What is Cache Stampede?

Many requests simultaneously going to the database after TTL expires.

---

# 23. How to handle Cache Stampede?

```txt
Mutex Lock

Random TTL

Warm Cache
```

---

# 24. What is Cache Penetration?

Constant requests for data that doesn't exist.

---

# 25. How to handle Cache Penetration?

Cache:

```txt
NULL
```

---

for a short time.

---

# 26. What is Cache Avalanche?

Mass expiration of TTL for a large number of keys.

---

# 27. What is Eviction Policy?

A strategy for deleting data when memory is insufficient.

---

# 28. What Eviction Policies do you know?

```txt
LRU
LFU
TTL
No Eviction
```

---

# 29. What is LRU?

Least Recently Used.

---

Keys that haven't been used recently are deleted.

---

# 30. What is LFU?

Least Frequently Used.

---

Rarely used keys are deleted.

---

# 31. What is Pub/Sub?

A messaging mechanism through channels.

---

# 32. What is a Publisher?

A message sender.

---

# 33. What is a Subscriber?

A message receiver.

---

# 34. Main disadvantage of Pub/Sub?

Messages are not stored.

---

# 35. What happens if a Subscriber disconnects?

The message is lost.

---

# 36. What is Redis Streams?

A reliable Redis messaging system.

---

Messages are stored.

---

# 37. How do Streams differ from Pub/Sub?

Pub/Sub:

```txt
no history
```

---

Streams:

```txt
with history
```

---

# 38. What is a Consumer Group?

A group of consumers for distributing load.

---

# 39. What is ACK in Streams?

Confirmation of successful message processing.

---

# 40. What happens if a Consumer crashes?

The message remains pending.

---

Can be processed again.

---

# 41. What is a Distributed Lock?

A synchronization mechanism between multiple application instances.

---

# 42. How does Redis implement a Lock?

Via:

```bash
SET key value NX EX
```

---

# 43. What does NX mean?

Create the key only if it doesn't exist.

---

# 44. Why is EX needed?

So the lock is automatically released.

---

# 45. Why can't you just do DEL lock?

Because the lock may have already passed to another process.

---

# 46. What is Redlock?

A distributed locking algorithm using multiple Redis instances.

---

# 47. What is Persistence?

Saving data to disk.

---

# 48. What Persistence mechanisms exist?

```txt
RDB
AOF
```

---

# 49. What is RDB?

A snapshot of Redis memory.

---

Creates a file:

```txt
dump.rdb
```

---

# 50. Disadvantage of RDB?

You can lose the latest changes between snapshots.

---

# 51. What is AOF?

Append Only File.

---

A log of all write operations.

---

# 52. Advantage of AOF?

Lower risk of data loss.

---

# 53. What is fsync?

The AOF disk write policy.

---

# 54. What is Redis Replication?

Replication of data from Master to Replica.

---

# 55. What is Redis Sentinel?

A monitoring and automatic failover system.

---

# 56. What is Redis Cluster?

A horizontally scalable Redis cluster.

---

# 57. What is Sharding?

Distributing data across multiple nodes.

---

# 58. Can Redis be used as the primary database?

Yes.

---

But rarely recommended for business systems.

---

# 59. When is Redis better than PostgreSQL?

For:

```txt
Cache

Sessions

Rate Limiting

Counters

Leaderboards
```

---

# 60. When is PostgreSQL better than Redis?

For:

```txt
Transactions

Relations

JOIN

Complex Queries

Long-term Storage
```

---

# 61. What is Rate Limiting?

Limiting the number of requests.

---

Often implemented via:

```txt
Redis + INCR
```

---

# 62. How to implement "100 requests per minute"?

Via:

```txt
INCR
+
TTL
```

---

# 63. How to implement session storage?

```txt
session:{id}
```

---

with TTL.

---

# 64. How to implement a leaderboard?

Via:

```txt
Sorted Set
```

---

# 65. How to implement a job queue?

Via:

```txt
List

or

Streams
```

---

# 66. Why is Redis often used together with PostgreSQL?

Because they solve different problems:

Redis:

```txt
speed
```

---

PostgreSQL:

```txt
reliability
```

---

# 67. Most Popular Senior Question

Why is Redis faster than PostgreSQL?

Answer:

```txt
Data is in memory.

No SQL Parser.

No Query Planner.

No JOIN.

No MVCC.

No complex transactions.

Most operations have O(1) complexity.
```

---

# 68. Strongest Senior Answer

When would you NOT use Redis?

Answer:

I would not use Redis as primary storage for financial operations, complex business entities, and systems where data consistency is critical. In such cases, PostgreSQL is a much better fit. I would use Redis as an additional layer for caching, queues, rate limiting, and read acceleration.
