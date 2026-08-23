# Redis Fundamentals

## What is Redis and why is it fast

Redis (Remote Dictionary Server) is a data store that keeps everything in memory. All data lives in RAM (random access memory) instead of on disk, so a single operation takes microseconds. It's not just a cache — it supports rich data structures, Pub/Sub, Streams, Lua scripting, and transactions.

```txt
Why Redis is orders of magnitude faster than PostgreSQL:

1. In-Memory:
   PostgreSQL: data on disk → buffer pool in RAM → disk I/O on miss
   Redis: everything in RAM, no disk I/O for reads/writes
   Latency: Redis ~100μs vs PostgreSQL ~1-10ms
   PostgreSQL on a cache miss: 10-100ms

2. Single-Threaded Event Loop:
   One thread for all commands → no race conditions, no mutexes
   Like the Node.js event loop: I/O never blocks the thread,
   and every command runs atomically from start to finish
   Commands like GET/SET/INCR = O(1), execute in <<1ms
   Multi-threading in Redis 6+: only for I/O (network,
   persistence) — commands still run on one thread

3. Optimized data structures:
   Hash Table for String/Hash
   Skip List for Sorted Set (O(log N) range queries)
   Linked List for List
   Radix Tree for Streams
```

## Redis as a complement to PostgreSQL

Redis does not replace a relational database. The usual split is that PostgreSQL owns the data and Redis holds a fast copy of the parts that are read often.

```txt
Standard architecture:
  PostgreSQL = source of truth, Redis = fast layer on top

Cache-Aside (most popular pattern):
  1. Request → check Redis
  2. Cache HIT → return from Redis (no DB call)
  3. Cache MISS → read from PostgreSQL → write to Redis
     with a TTL → return

Typical use cases in fullstack:
  Cache:       API responses, expensive SQL query results
  Sessions:    JWT blacklist, server-side sessions
  Rate limit:  request counters (INCR + EXPIRE)
  Leaderboard: Sorted Set by score
  Pub/Sub:     real-time notifications (Kafka or SQS if
               delivery must be guaranteed)
  Queue:       List + BLPOP (or BullMQ on top of Redis)
  Locks:       SET NX EX distributed lock (Redlock algorithm)
```

## Core operations and TTL

TTL (time to live) is the number of seconds after which Redis deletes the key on its own. It is the main tool that stops a cache from growing forever.

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
// -1 = the key exists but has no TTL, -2 = the key doesn't exist
const ttl = await redis.ttl('user:123'); // seconds remaining

// DEL
await redis.del('user:123');

// EXISTS
const exists = await redis.exists('user:123'); // 1 or 0
```

## Eviction Policies — what to do when memory runs out

An eviction policy tells Redis which keys to throw away once it hits its `maxmemory` limit. Pick the wrong one and Redis either starts rejecting writes or quietly drops the session you needed.

```txt
maxmemory-policy in redis.conf (or via CONFIG SET):

noeviction (default):
  New writes are rejected with an out-of-memory error
  Use when: Redis as primary DB (can't lose data)

allkeys-lru:
  Evict least recently used keys (from all keys)
  Use when: general cache, not all keys have TTL

volatile-lru:
  LRU only among keys with TTL
  Use when: cache with TTL, plus separate persistent
  keys (sessions) that have no TTL

allkeys-lfu:
  Least Frequently Used (Redis 4+) — counts frequency,
  not just recency
  Use when: hot/cold data with uneven access patterns

volatile-ttl:
  Keys with the soonest expiration are evicted first
  Use when: important to free the "oldest" data first

Recommendation for cache: allkeys-lru or allkeys-lfu
Recommendation for sessions: volatile-lru
  (sessions have a TTL, lock keys don't)
```

## Redis Cluster vs Sentinel vs Standalone

These three are deployment shapes, not features. Standalone is one server, Sentinel adds automatic failover, and Cluster adds sharding on top of that.

```txt
Standalone (single server):
  Dev, low-traffic production
  No high availability: if it goes down → downtime

Sentinel (high availability without sharding):
  Master + Replica(s) + 3+ Sentinel processes
  Sentinel monitors Master, performs automatic failover
  One shard → full dataset on one node
  Use when: you need failover and the dataset fits in
  one server's RAM

Cluster (horizontal sharding):
  16384 hash slots distributed across N master nodes
  Each master: replica for failover
  key → CRC16 checksum of the key % 16384 → slot → node
  Use when: dataset > one server's RAM, or throughput
  above 100k ops/sec is needed

  Cluster limitation: multi-key ops work only when all
  keys land in the same slot
  Hash tags: {user}:123 and {user}:456 → same slot (curly braces)
```

## Common interview mistakes

- **"Redis is just a cache"** — it is a full-featured in-memory data structure store. Beyond plain strings it also gives you:
  - Sorted Sets for leaderboards and priority queues.
  - Streams — an append-only log, like a lightweight Kafka.
  - Pub/Sub, Lua scripting and distributed locks.
  - Geospatial indexes (`GEOADD`/`GEORADIUS`) and HyperLogLog for approximate cardinality.

- **"Redis is single-threaded so it must be slow under load"** — the opposite. Single-threaded Event Loop: no context switching, no mutex overhead, commands are atomic. Redis handles >1M ops/sec on a single core. The bottleneck is usually the network, not the processor.

- **"Data in Redis is always lost on restart"** — Redis supports persistence: RDB (periodic snapshots) and AOF (append-only log of every command). In production: AOF + RDB for reliability. But for intentional ephemeral caches, skipping persistence is faster.

- **"TTL guarantees deletion exactly after N seconds"** — expiration is lazy. The key is marked as expired, but it is physically deleted on the next GET. There is also a background sweep that clears a fraction of expired keys every 100ms. Under load there may be a slight delay before the actual deletion.

- **"SET + EXPIRE is an atomic operation"** — no! `SET key value` + `EXPIRE key 60` are two separate calls. The process can crash between them → key without TTL (memory leak). Correct: `SET key value EX 60` (atomic in one command) or `SETEX`.
