# Redis — Interview Questions (Senior)

## Group 1: Architecture & Performance

**Why is Redis fast?**

Three reasons: (1) data in RAM — reading from memory ~100 ns vs ~10 ms from disk; (2) single-threaded Event Loop — no mutex/lock on data, no context-switch overhead; (3) optimized data structures — Hash Table for String/Hash, Skip List for Sorted Set, Linked List for List — O(1)–O(log N) operations without a complex query planner.

---

**Isn't single-threading a bottleneck?**

No. Redis commands execute in microseconds (SET/GET ~1–10 µs), so a single thread handles hundreds of thousands of operations per second. The bottleneck is not CPU for commands but network I/O and disk. Since Redis 6.0, network I/O is offloaded to separate threads (threaded I/O); persistence (RDB/AOF) also runs in the background via fork. The main thread stays single-threaded — this guarantees atomicity of every command without locks.

---

**When does Redis lose to PostgreSQL, and when does it complement it?**

Redis loses to PostgreSQL for: multi-table transactions (MVCC, ACID), JOIN and complex queries, long-term storage with full-text search, and when RAM is limited. Redis complements PostgreSQL for: hot-data cache (Cache-Aside), counters (INCR — atomic without a transaction), rate limiting, sessions, task queues, pub/sub. Typical architecture: PostgreSQL as the source of truth, Redis as the read-acceleration layer.

---

**What is an Eviction Policy and which one should you choose?**

Eviction Policy — the strategy for removing keys when `maxmemory` is exhausted. Options:
- `noeviction` — return an error on write (for persistent store)
- `allkeys-lru` — evict least-recently-used keys from all keys (recommended for cache)
- `volatile-lru` — LRU only among keys with a TTL
- `allkeys-lfu` — evict least-frequently-used (better for hot/cold distribution)
- `volatile-ttl` — evict keys closest to expiration

For cache-only Redis: `allkeys-lru` or `allkeys-lfu`. For mixed (cache + persistent): `volatile-lru` — persistent keys without TTL are not evicted.

---

## Group 2: Data Structures

**What data structures does Redis provide and what is their complexity?**

```txt
String     — O(1) GET/SET/INCR/SETNX
Hash       — O(1) HGET/HSET, O(N) HGETALL (N = field count)
List       — O(1) LPUSH/RPOP/LLEN, O(N) LRANGE
Set        — O(1) SADD/SISMEMBER, O(N) SMEMBERS, O(N) SINTER/SUNION
Sorted Set — O(log N) ZADD/ZRANK, O(log N + M) ZRANGEBYSCORE (M = results)
HyperLogLog— O(1) PFADD/PFCOUNT, ~1.5% error, max 12 KB
Bitmap     — O(1) SETBIT/GETBIT, O(N) BITCOUNT
Stream     — O(1) XADD, O(log N) XRANGE/XREAD
```

---

**When should you use Hash instead of separate String keys?**

Hash — when storing multiple attributes of one entity: `HSET user:123 name "Alice" age "30" email "alice@..."`. Advantages: one key instead of three (`user:123:name`, `user:123:age`), memory savings (Redis optimizes small Hashes via ziplist/listpack), atomic multi-field reads via `HMGET`. Limitation: `HGETALL` is O(N) — do not use it for hashes with thousands of fields.

---

**How do you implement a real-time leaderboard?**

Sorted Set: `ZADD leaderboard <score> <userId>`. Update: `ZINCRBY leaderboard 10 user:123` — atomically increment the score. Top 10: `ZREVRANGE leaderboard 0 9 WITHSCORES`. User rank: `ZREVRANK leaderboard user:123` — O(log N). For a sliding-window leaderboard by time: use timestamp as score, `ZRANGEBYSCORE` for a time range + `ZREMRANGEBYSCORE` to remove old entries.

---

**Why use HyperLogLog if Set already exists?**

HyperLogLog counts unique values with ~1.5% error, using at most 12 KB regardless of element count. A Set with a million elements uses ~50 MB+. For an exact count of unique daily users: Set. For analytics (DAU, unique views) where 1.5% error is acceptable: `PFADD dau:2024-01-15 userId` → `PFCOUNT dau:2024-01-15`. Merging multiple days: `PFMERGE dau:week dau:2024-01-15 dau:2024-01-16`.

---

## Group 3: Caching Patterns

**Explain Cache-Aside and its drawbacks.**

Cache-Aside (lazy loading): on read — check Redis first; on miss — query PostgreSQL → write to Redis → return. On update — update the DB → `DEL` the key from Redis (not SET — race condition: a concurrent reader could write stale data between UPDATE and SET). Drawbacks: (1) first request after TTL expiry — always a Cache Miss; (2) if Redis fails during `DEL` — stale data persists until TTL expires. Write-Through: write to Redis and DB simultaneously on every update — no stale data, but caches data that may never be read.

---

**What is Cache Stampede and how do you prevent it?**

Cache Stampede (Thundering Herd): 1000 parallel requests arrive exactly when a key's TTL expires → all go to the DB → overload. Solutions: (1) Mutex Lock — the first process sets a lock (`SET mutex:key 1 NX EX 5`), others wait and read from cache later; implemented via Lua script for atomic check+get. (2) Random TTL jitter — instead of a fixed TTL=3600, use `3600 + random(0, 300)` — keys expire at different times, spreading the load. (3) Background refresh — asynchronously update the cache before TTL expires (probabilistic early recomputation).

---

**What is Cache Penetration and what is a Bloom Filter?**

Cache Penetration: requests for data that doesn't exist in Redis or PostgreSQL (e.g., `GET /users/999999` — nonexistent user). Every time: Cache Miss → DB query → `NULL` → nothing cached → the next identical request hits the DB again. Solutions: (1) cache `null` — `SET user:999999 "null" EX 60` — on read check `if cached === "null" return null`; (2) Bloom Filter — a probabilistic data structure that answers "definitely absent" or "probably present," checked before hitting the DB. Bloom Filter: false positives are possible, false negatives are not.

---

**How do you implement rate limiting with Redis?**

Sliding window counter via INCR + EXPIRE:
```typescript
const key = `ratelimit:${userId}:${Math.floor(Date.now() / 60000)}`;
const count = await redis.incr(key);
if (count === 1) await redis.expire(key, 60);
if (count > 100) throw new Error('Rate limit exceeded');
```
Problem: the window resets every minute, allowing a burst of 200 requests at the minute boundary. Precise sliding window: Sorted Set with timestamp as score — `ZADD ratelimit:userId <timestamp> <uuid>`, remove old: `ZREMRANGEBYSCORE key 0 <timestamp-60s>`, count: `ZCARD`. More accurate, but uses more memory.

---

## Group 4: Pub/Sub & Streams

**What is the difference between Pub/Sub and Streams?**

Pub/Sub: ephemeral, fire-and-forget, no storage. If a subscriber is offline — the message is lost. Ideal for: broadcasting WebSocket events between instances, cache invalidation, live dashboards. Streams: append-only persistent log with unique IDs. Messages are stored until explicitly deleted. Consumer Groups — each message is delivered to exactly one consumer (load balancing). ACK (XACK) — confirms processing; without ACK a message stays pending and can be reprocessed. Streams is Redis's Kafka analogue for low/medium throughput (~100k/sec).

---

**Why can't you use one connection for both subscribe and regular commands?**

After `SUBSCRIBE`/`PSUBSCRIBE`, the connection enters subscribe mode: only `SUBSCRIBE`, `UNSUBSCRIBE`, `PSUBSCRIBE`, `PUNSUBSCRIBE`, `PING`, and `QUIT` are allowed. Attempting `SET`/`GET` returns an error. Therefore, always use two clients: one for subscribing (subscriber connection), one for commands (publisher/command connection). In ioredis, the subscriber client is created via `redis.duplicate()`.

---

**How do you scale WebSocket across multiple NestJS instances?**

Problem: a client is connected to instance A, an event fires on instance B → the client won't receive it. Solution via Redis Pub/Sub: when an event fires on instance B → `redis.publish('user:123:events', JSON.stringify(event))`. Each instance subscribes to the user's channel → on message receipt, looks up the WebSocket connection for that user ON THAT INSTANCE → sends it. Socket.IO provides `@socket.io/redis-adapter` — an official implementation of this exact pattern.

---

**When to use Consumer Groups vs multiple SUBSCRIBE calls?**

Multiple `SUBSCRIBE` on the same channel: fan-out — each subscriber receives ALL messages (notifying multiple independent services). Consumer Group: competing consumers — each message goes to exactly ONE consumer in the group (load balancing). If you have 3 order-processing workers and each order should be processed exactly once — Consumer Group. If an event must reach both a notification service and an analytics service — separate Consumer Groups on the same Stream (each group independently receives all messages).

---

## Group 5: Distributed Locks

**How do you implement a distributed lock and why does a unique token matter?**

`SET lock:resource <uuid> NX PX 30000` — atomic: create only if not exists + 30-second TTL. The UUID (unique token) ensures you only release YOUR lock. Scenario without a token: Process A acquires lock (TTL=5s), stalls for 6s → TTL expires → Process B acquires lock → Process A resumes → `DEL lock` → accidentally releases Process B's lock. With a token: `GET lock` → if value matches our UUID → `DEL lock`. But GET + DEL are two separate steps with a non-atomic gap — a Lua script is required.

---

**Why is a Lua script required to release the lock?**

Between `GET lock` (token check) and `DEL lock` (deletion) there is a non-atomic window. If the TTL expires in that gap: Process B acquires the lock after GET, then Process A executes DEL and deletes Process B's lock. A Lua script executes atomically (Redis is single-threaded, so nothing can interleave between commands inside Lua):
```lua
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
```
Returns 1 (successfully deleted) or 0 (token mismatch — lock belongs to someone else).

---

**When should you use Redlock instead of a plain Redis lock?**

Redlock is needed under strict reliability requirements: a single Redis instance is a Single Point of Failure. If Redis crashes immediately after granting a lock, the new Master (post-Sentinel failover) has no knowledge of that lock → two processes simultaneously believe they hold the lock. Redlock: `N` independent Redis instances (3 or 5); a lock is granted only if `>N/2` instances responded successfully within `TTL * 0.1` time. Even if one instance goes down — quorum is preserved. For most applications: Single Redis + Sentinel is sufficient. Redlock — for critical infrastructure (financial operations, distributed transactions).

---

**Redis Lock vs PostgreSQL SELECT FOR UPDATE — when to use which?**

PostgreSQL `FOR UPDATE`: locks a row for the duration of a transaction, automatically released on commit/rollback, no Redis needed. Use when: the operation is atomic within a single PostgreSQL transaction. Redis Lock: use when: (1) the operation spans multiple services/databases; (2) a lock is needed before the transaction begins; (3) you need to lock an external API call (not just the DB); (4) Cron job — only one instance should run the job. Example: Redis Lock → call Payment API → write to DB. `FOR UPDATE` doesn't help for the Payment API call.

---

## Group 6: Persistence & High Availability

**What is the difference between RDB and AOF, and what should you use in production?**

RDB (Redis Database): binary snapshot of all in-memory data via `BGSAVE` (fork + Copy-on-Write). Pros: compact file, fast restart. Cons: data loss between snapshots (minutes). AOF (Append Only File): log of every write command, `appendfsync everysec` — at most 1 second of data loss. Pros: minimal data loss, human-readable format. Cons: larger file, slower recovery on a large log. Production recommendation: RDB + AOF together — on restart Redis uses AOF (more accurate); RDB for fast disaster recovery. Cache-only Redis: disable both.

---

**What is AOF Rewrite and why is it needed?**

AOF accumulates the full command history: 1000 `INCR counter` entries → 1000 lines in AOF. But the final state is a single key with one value. `BGREWRITEAOF` (or automatic via `auto-aof-rewrite-percentage 100`) rewrites the AOF into the minimal equivalent command set: 1000 `INCR` → one `SET counter 1000`. Runs in the background via fork, does not block Redis. Without Rewrite: the AOF grows indefinitely, and recovery time on restart keeps increasing.

---

**What is the difference between Sentinel and Cluster?**

Sentinel: monitoring and automatic failover without sharding. 3+ Sentinel processes monitor the Master. On failure: a vote → one Sentinel initiates failover → a Replica becomes the Master → clients update the address. The entire dataset stays on one Master. Use when: HA is needed and the dataset fits in one server's RAM. Redis Cluster: sharding (16384 hash slots) + HA. Data distributed across N Master nodes, each with Replicas. Automatic failover within the cluster. Limitation: multi-key operations only work for keys in the same hash slot. Use when: the dataset does not fit in one server's RAM.

---

**When is it correct to disable persistence on Redis?**

For cache-only Redis: `appendonly no` + `save ""` (disable RDB). Justification: on cache data loss — just a Cache Miss, PostgreSQL is the source of truth. Persistence adds overhead: RDB fork can impact latency with large datasets, AOF causes disk I/O. Cache-only config: `maxmemory 2gb` + `maxmemory-policy allkeys-lru` + persistence off. Do NOT disable if Redis is used as: a job queue (BullMQ), distributed locks for critical resources, primary session store where logouts on restart are unacceptable.

---

**What is replica lag and how does it affect your application?**

Redis replication is asynchronous: Master writes a command → sends it to Replica → Replica applies it. Lag is usually <1ms, but under high load or on a slow network — hundreds of ms. Consequence: reading from a Replica immediately after writing to the Master may return stale data. Solution for critical reads: read from the Master. For non-critical reads (cache, analytics): Replica is acceptable. In the application: two clients — `masterClient` for writes and critical reads, `replicaClient` for scaling non-critical reads. During a Sentinel failover: the client must reconnect to the new Master through the Sentinel endpoint (never hardcode the Master address).
