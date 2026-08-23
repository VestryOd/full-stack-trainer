# Redis — Interview Questions (Senior)

## Group 1: Architecture & Performance

**Why is Redis fast?**

Three reasons.

1. **Data lives in RAM (random access memory).** A read from memory takes ~100 ns; a read from disk takes ~10 ms.
2. **One thread runs every command.** Nothing needs a mutex to protect the data, and the processor never pays for switching between threads.
3. **Purpose-built data structures.** Hash Table for String and Hash, Skip List for Sorted Set, Linked List for List. Every operation is O(1) or O(log N), with no query planner deciding how to run it.

---

**Isn't single-threading a bottleneck?**

No. Redis commands execute in microseconds (SET/GET ~1–10 µs), so a single thread handles hundreds of thousands of operations per second. The bottleneck is not the processor but network I/O and disk.

Since Redis 6.0 network I/O is offloaded to separate threads (threaded I/O). Persistence runs in the background via fork: RDB (Redis Database) snapshots and AOF (Append Only File) logs. The main thread stays single-threaded, and that is what makes every command atomic without locks.

---

**When does Redis lose to PostgreSQL, and when does it complement it?**

**Redis loses to PostgreSQL when you need:**

- Transactions across several tables. PostgreSQL gives them ACID guarantees: atomicity, consistency, isolation, durability. It reaches them with MVCC (multi-version concurrency control), where a reader sees a snapshot instead of waiting for writers.
- JOIN and other complex queries.
- Long-term storage with full-text search.
- More data than fits in memory.

**Redis complements PostgreSQL for:** a hot-data cache (Cache-Aside), counters (`INCR` is atomic without a transaction), rate limiting, sessions, task queues and pub/sub.

Typical architecture: PostgreSQL as the source of truth, Redis as the read-acceleration layer.

---

**What is an Eviction Policy and which one should you choose?**

Eviction Policy — the strategy for removing keys when `maxmemory` is exhausted. LRU below stands for least recently used, LFU for least frequently used, and TTL (time to live) is the time a key has left.

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
Sorted Set — O(log N) ZADD/ZRANK
             O(log N + M) ZRANGEBYSCORE (M = results)
HyperLogLog— O(1) PFADD/PFCOUNT, ~1.5% error, max 12 KB
Bitmap     — O(1) SETBIT/GETBIT, O(N) BITCOUNT
Stream     — O(1) XADD, O(log N) XRANGE/XREAD
```

---

**When should you use Hash instead of separate String keys?**

Hash — when storing multiple attributes of one entity: `HSET user:123 name "Alice" age "30" email "alice@..."`. Advantages:

- One key instead of three (`user:123:name`, `user:123:age`).
- Memory savings: Redis packs small Hashes into a ziplist/listpack.
- Atomic multi-field reads via `HMGET`.

Limitation: `HGETALL` is O(N) — do not use it for hashes with thousands of fields.

---

**How do you implement a real-time leaderboard?**

Sorted Set: `ZADD leaderboard <score> <userId>`. Update: `ZINCRBY leaderboard 10 user:123` — atomically increment the score. Top 10: `ZREVRANGE leaderboard 0 9 WITHSCORES`. User rank: `ZREVRANK leaderboard user:123` — O(log N). For a sliding-window leaderboard by time: use timestamp as score, `ZRANGEBYSCORE` for a time range + `ZREMRANGEBYSCORE` to remove old entries.

---

**Why use HyperLogLog if Set already exists?**

HyperLogLog counts unique values with ~1.5% error, using at most 12 kilobytes regardless of element count. A Set with a million elements uses ~50 megabytes or more.

For an exact count of unique daily users: Set. For analytics — daily active users (DAU), unique views — where 1.5% error is acceptable: `PFADD dau:2024-01-15 userId` → `PFCOUNT dau:2024-01-15`. Merging multiple days: `PFMERGE dau:week dau:2024-01-15 dau:2024-01-16`.

---

## Group 3: Caching Patterns

**Explain Cache-Aside and its drawbacks.**

Cache-Aside (lazy loading): on read — check Redis first; on miss — query PostgreSQL → write to Redis → return. On update — update the database, then `DEL` the key from Redis. Deleting is safer than `SET`: a concurrent reader could write stale data into the cache between the `UPDATE` and the `SET`.

Drawbacks:

- The first request after the TTL expires is always a Cache Miss.
- If Redis is unreachable during the `DEL`, stale data lives on until the TTL expires.

Write-Through is the alternative: write to Redis and the database on every update. No stale data, but you cache rows that may never be read.

---

**What is Cache Stampede and how do you prevent it?**

Cache Stampede (Thundering Herd): 1000 parallel requests arrive exactly when a key's TTL expires, they all go to the database, and it falls over. Three solutions:

1. **Mutex Lock.** The first process sets a lock (`SET mutex:key 1 NX EX 5`); the others wait and read from the cache a moment later. Use a Lua script so the check and the read are one atomic step.
2. **Random TTL jitter.** Instead of a fixed TTL=3600, use `3600 + random(0, 300)`. Keys then expire at different moments and the load spreads out.
3. **Background refresh.** Rebuild the cache asynchronously shortly before the TTL runs out (probabilistic early recomputation).

---

**What is Cache Penetration and what is a Bloom Filter?**

Cache Penetration: requests for data that doesn't exist in Redis or PostgreSQL (e.g., `GET /users/999999` — nonexistent user). Every time: Cache Miss → database query → `NULL` → nothing cached → the next identical request hits the database again. Two solutions:

1. **Cache the `null`.** Write `SET user:999999 "null" EX 60`, and on read check `if cached === "null" return null`.
2. **Bloom Filter.** A probabilistic structure that answers "definitely absent" or "probably present". Check it before you touch the database. False positives are possible; false negatives are not.

---

**How do you implement rate limiting with Redis?**

Sliding window counter via `INCR` + `EXPIRE`:

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

Pub/Sub is ephemeral: fire-and-forget, no storage. If a subscriber is offline the message is lost. Ideal for broadcasting WebSocket events between instances, cache invalidation and live dashboards.

Streams are an append-only persistent log with unique IDs, and messages stay until you delete them.

```txt
                  Pub/Sub            Streams
Storage:          None               Until deleted
Subscriber down:  Message lost       Message waits
Delivery:         Every subscriber   One consumer per group
Acknowledgement:  None               XACK; unacked = pending
Replay history:   No                 Yes
```

With Consumer Groups each message is delivered to exactly one consumer in the group, which is how you load-balance workers. `XACK` is the acknowledgement that processing finished; without it the message stays pending and can be picked up again. Streams is Redis's Kafka analogue for low and medium throughput (~100k/sec).

---

**Why can't you use one connection for both subscribe and regular commands?**

After `SUBSCRIBE`/`PSUBSCRIBE`, the connection enters subscribe mode: only `SUBSCRIBE`, `UNSUBSCRIBE`, `PSUBSCRIBE`, `PUNSUBSCRIBE`, `PING`, and `QUIT` are allowed. Attempting `SET`/`GET` returns an error. Therefore, always use two clients: one for subscribing (subscriber connection), one for commands (publisher/command connection). In ioredis, the subscriber client is created via `redis.duplicate()`.

---

**How do you scale WebSocket across multiple NestJS instances?**

Problem: a client is connected to instance A, an event fires on instance B, so the client never receives it. Redis Pub/Sub is the bus that fixes it.

```txt
1. Instance B publishes to the user's channel:
   redis.publish('user:123:events', JSON.stringify(event))
2. Every instance is subscribed to that channel
3. On receipt, each instance looks for a socket of that user
   among its own connections
4. Only the instance that actually holds the socket sends it
```

Socket.IO ships `@socket.io/redis-adapter`, an official implementation of exactly this pattern.

---

**When to use Consumer Groups vs multiple SUBSCRIBE calls?**

Multiple `SUBSCRIBE` on the same channel is fan-out: every subscriber receives **all** messages. That is what you want for notifying several independent services.

A Consumer Group is competing consumers: each message goes to exactly **one** consumer in the group, which load-balances the work. Three order-processing workers, each order handled once — Consumer Group.

Need both? Put two separate Consumer Groups on the same Stream. Each group receives every message independently, so the notification service and the analytics service both get it.

---

## Group 5: Distributed Locks

**How do you implement a distributed lock and why does a unique token matter?**

`SET lock:resource <uuid> NX PX 30000` — atomic: create only if the key does not exist, with a 30-second TTL. The UUID (universally unique identifier) is a token that proves the lock is yours, so you never release someone else's.

Here is what goes wrong without a token:

```txt
1. Process A acquires the lock with TTL=5s
2. Process A stalls for 6s, so the TTL expires and Redis
   drops the key
3. Process B acquires the same lock
4. Process A wakes up and runs DEL lock
5. Process B has just lost a lock it still thinks it holds
```

With a token you run `GET lock` first, and delete only if the value matches your own UUID. But `GET` and `DEL` are two separate steps with a gap in between, so a Lua script is required.

---

**Why is a Lua script required to release the lock?**

Between `GET lock` (token check) and `DEL lock` (deletion) there is a non-atomic window. If the TTL expires in that gap: Process B acquires the lock after `GET`, then Process A executes `DEL` and deletes Process B's lock. A Lua script executes atomically (Redis is single-threaded, so nothing can interleave between commands inside Lua):

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

Redlock is for cases where losing a lock is unacceptable. A single Redis instance is a single point of failure (SPOF). If it crashes right after granting a lock, the replacement Master elected by Sentinel knows nothing about that lock. Two processes then both believe they hold it.

```txt
Redlock, step by step:
1. startTime = now
2. SET NX PX on all N nodes (short timeout, so one dead
   node can't hang you)
3. Lock granted only if >N/2 nodes said OK
   AND elapsed < ttl * 0.1
4. Effective TTL = TTL - elapsed - clock drift
5. Quorum not reached → DEL on every node, then retry
```

`N` is 3 or 5 independent instances, so one of them going down still leaves a quorum. For most applications Single Redis + Sentinel is enough. Redlock is for critical infrastructure: financial operations, distributed transactions.

---

**Redis Lock vs PostgreSQL SELECT FOR UPDATE — when to use which?**

PostgreSQL `FOR UPDATE` locks a row for the duration of a transaction and releases it on commit or rollback. No Redis needed. Use it when the whole operation is atomic inside a single PostgreSQL transaction.

Use a Redis Lock when:

- The operation spans several services or databases.
- The lock is needed before the transaction begins.
- You need to lock an external API call, not just a row.
- A cron job must run on exactly one instance.

Example: take the Redis Lock, call the Payment API, then write to the database. `FOR UPDATE` cannot cover the Payment API call at all.

---

## Group 6: Persistence & High Availability

**What is the difference between RDB and AOF, and what should you use in production?**

RDB is a binary snapshot of all in-memory data, taken by `BGSAVE` (fork + Copy-on-Write). AOF is a log of every write command; with `appendfsync everysec` you lose at most one second of data.

```txt
                 RDB                    AOF
File size:       Compact                Larger (full history)
Restart speed:   Fast (load snapshot)   Slower (replay log)
Worst-case loss: Minutes                1 second (everysec)
Readable:        No (binary)            Yes (plain commands)
```

Production recommendation: run both. On restart Redis uses the AOF because it is more accurate, and the RDB stays as the fast disaster-recovery file. Cache-only Redis: disable both.

---

**What is AOF Rewrite and why is it needed?**

AOF accumulates the full command history: 1000 `INCR counter` entries become 1000 lines in the file. But the final state is a single key with one value.

`BGREWRITEAOF` (or the automatic trigger `auto-aof-rewrite-percentage 100`) rewrites the AOF into the minimal equivalent command set: 1000 `INCR` collapse into one `SET counter 1000`. It runs in the background via fork and does not block Redis. Without Rewrite the AOF grows without limit, and restart time keeps climbing with it.

---

**What is the difference between Sentinel and Cluster?**

Both give you high availability — automatic recovery when a node dies — but only Cluster also splits the data.

```txt
                 Sentinel               Cluster
Sharding:        No                     Yes (16384 slots)
Dataset:         One Master holds all   Split over N Masters
Failover:        Sentinel vote          Inside the cluster
Multi-key ops:   Always work            Same hash slot only
Use when:        Data fits in one       Data outgrew one
                 server's RAM           server's RAM
```

Sentinel: 3 or more Sentinel processes monitor the Master. On failure they vote, one Sentinel initiates the failover, a Replica is promoted to Master, and clients pick up the new address.

Cluster: data is distributed across N Master nodes, each with its own Replicas, and failover happens inside the cluster.

---

**When is it correct to disable persistence on Redis?**

For cache-only Redis: `appendonly no` + `save ""` (disable RDB). Losing the cache costs you a Cache Miss and nothing else, because PostgreSQL is the source of truth. Persistence is not free: the RDB fork can hurt latency on large datasets, and AOF causes disk I/O. Cache-only config: `maxmemory 2gb` + `maxmemory-policy allkeys-lru` + persistence off.

Keep persistence on if Redis is used as:

- A job queue such as BullMQ.
- Distributed locks for critical resources.
- The primary session store, where logging everyone out on restart is unacceptable.

---

**What is replica lag and how does it affect your application?**

Redis replication is asynchronous: the Master writes a command, sends it to the Replica, and the Replica applies it. Lag is usually under 1ms, but under high load or on a slow network it can reach hundreds of ms.

The consequence: reading from a Replica immediately after writing to the Master may return stale data. So route critical reads to the Master, and let non-critical reads (cache, analytics) go to a Replica.

In the application that means two clients: `masterClient` for writes and critical reads, `replicaClient` for scaling the rest. During a Sentinel failover the client must reconnect to the new Master through the Sentinel endpoint, so never hardcode the Master address.
