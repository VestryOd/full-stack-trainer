# Redis Fundamentals

## What is Redis and why is it fast

Redis (Remote Dictionary Server) is an in-memory data store: all data lives in RAM, operations execute in microseconds. It's not just a cache — it supports rich data structures, Pub/Sub, Streams, Lua scripting, and transactions.

```txt
Why Redis is orders of magnitude faster than PostgreSQL:

1. In-Memory:
   PostgreSQL: data on disk → buffer pool in RAM → disk I/O on miss
   Redis: everything in RAM, no disk I/O for reads/writes
   Latency: Redis ~100μs, PostgreSQL ~1-10ms (10-100ms on cache miss)

2. Single-Threaded Event Loop:
   One thread for all commands → no race conditions, no mutex overhead
   Similar to Node.js event loop: I/O doesn't block, commands execute atomically
   Commands like GET/SET/INCR = O(1), execute in <<1ms
   Multi-threading in Redis 6+: only for I/O (network, persistence), not for commands

3. Optimized data structures:
   Hash Table for String/Hash
   Skip List for Sorted Set (O(log N) range queries)
   Linked List for List
   Radix Tree for Streams
```

## Redis as a complement to PostgreSQL

```txt
Standard architecture: PostgreSQL (source of truth) + Redis (fast layer)

Cache-Aside (most popular pattern):
  1. Request → check Redis
  2. Cache HIT → return from Redis (no DB call)
  3. Cache MISS → read from PostgreSQL → write to Redis with TTL → return

Typical use cases in fullstack:
  Cache:            API responses, expensive SQL query results
  Sessions:         JWT blacklist, server-side sessions
  Rate Limiting:    request counters (INCR + EXPIRE)
  Leaderboard:      Sorted Set by score
  Pub/Sub:          real-time notifications (but SQS/Kafka for reliability)
  Queue:            List + BLPOP (or BullMQ on top of Redis)
  Distributed Lock: SET NX EX (Redlock algorithm)
```

## Core operations and TTL

```typescript
import { createClient } from 'redis';

const redis = createClient({ url: process.env.REDIS_URL });
await redis.connect();

// SET with TTL
await redis.set('user:123', JSON.stringify(user), { EX: 3600 }); // 1 hour
// or
await redis.setEx('user:123', 3600, JSON.stringify(user));

// GET
const cached = await redis.get('user:123');
const user = cached ? JSON.parse(cached) : null;

// Atomic increment (request counter for rate limiting)
const count = await redis.incr('rate:user:123');
if (count === 1) {
  await redis.expire('rate:user:123', 60); // reset after 60 sec
}

// TTL check
const ttl = await redis.ttl('user:123'); // seconds remaining, -1 = no TTL, -2 = doesn't exist

// DEL
await redis.del('user:123');

// EXISTS
const exists = await redis.exists('user:123'); // 1 or 0
```

## Eviction Policies — what to do when memory runs out

```txt
maxmemory-policy in redis.conf (or via CONFIG SET):

noeviction (default):
  New writes are rejected with OOM error
  Use when: Redis as primary DB (can't lose data)

allkeys-lru:
  Evict least recently used keys (from all keys)
  Use when: general cache, not all keys have TTL

volatile-lru:
  LRU only among keys with TTL
  Use when: cache with TTL + separate persistent keys (sessions) without TTL

allkeys-lfu:
  Least Frequently Used (Redis 4+) — counts frequency, not just recency
  Use when: hot/cold data with uneven access patterns

volatile-ttl:
  Keys with the soonest expiration are evicted first
  Use when: important to free the "oldest" data first

Recommendation for cache: allkeys-lru or allkeys-lfu
Recommendation for sessions: volatile-lru (sessions have TTL, lock keys don't)
```

## Redis Cluster vs Sentinel vs Standalone

```txt
Standalone (single server):
  Dev, low-traffic production
  No HA: if it goes down → downtime

Sentinel (HA without sharding):
  Master + Replica(s) + 3+ Sentinel processes
  Sentinel monitors Master, performs automatic failover on failure
  One shard → full dataset on one node
  Use when: need HA, dataset fits in one server's RAM

Cluster (horizontal sharding):
  16384 hash slots distributed across N master nodes
  Each master: replica for HA
  key → CRC16(key) % 16384 → slot → node
  Use when: dataset > one server's RAM, or need throughput >100k ops/sec

  Cluster limitation: multi-key ops only if all keys are in the same slot
  Hash tags: {user}:123 and {user}:456 → same slot (curly braces)
```

## Common interview mistakes

- **"Redis is just a cache"** — Redis supports: Sorted Sets (leaderboards, priority queues), Streams (append-only log, like lightweight Kafka), Pub/Sub, Lua scripting, distributed locks, geospatial indexes (GEOADD/GEORADIUS), HyperLogLog (approximate cardinality). It's a full-featured in-memory data structure store.

- **"Redis is single-threaded so it must be slow under load"** — the opposite. Single-threaded Event Loop: no context switching, no mutex overhead, commands are atomic. Redis handles >1M ops/sec on a single core. The bottleneck is usually network, not CPU.

- **"Data in Redis is always lost on restart"** — Redis supports persistence: RDB (periodic snapshots) and AOF (append-only log of every command). In production: AOF + RDB for reliability. But for intentional ephemeral caches, skipping persistence is faster.

- **"TTL guarantees deletion exactly after N seconds"** — lazy expiration: the key is marked as expired, but physically deleted on the next GET or by a background sweep (every 100ms, a fraction of expired keys is deleted). Under load, there may be a slight delay before actual deletion.

- **"SET + EXPIRE is an atomic operation"** — no! `SET key value` + `EXPIRE key 60` are two separate calls. The process can crash between them → key without TTL (memory leak). Correct: `SET key value EX 60` (atomic in one command) or `SETEX`.
