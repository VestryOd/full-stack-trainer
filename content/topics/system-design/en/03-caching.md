# Caching

## Why caching matters — offloading, not just "speed"

The basic motivation: a Redis/memcached request takes ~0.1-1ms, a relational DB query with disk access takes single-to-tens of milliseconds, and a complex JOIN/aggregation can take hundreds of milliseconds. A cache reduces not just the latency of a single request, but the **overall load on the database**, which lets the same DB serve a multiple of the users.

```txt
Without a cache:                    With a cache (cache hit):
Client → API → Database             Client → API → Redis → Response
10,000 req/s all hit the DB          9,000 req/s served from Redis,
                                      1,000 req/s (miss) hit the DB
```

The main interview question isn't "what is a cache" — it's **where exactly in the architecture it sits, what's stored in it, how it's invalidated, and what happens on a cache miss at scale**. These details separate a senior answer from "let's add Redis."

## Cache-Aside (Lazy Loading) — the default pattern

The application explicitly manages the cache: read from cache, on a miss go to the DB and store the result.

```ts
async function getUser(userId: string): Promise<User> {
  const cached = await redis.get(`user:${userId}`);
  if (cached) {
    return JSON.parse(cached); // cache hit
  }

  const user = await db.user.findUnique({ where: { id: userId } });
  if (user) {
    // TTL is mandatory — otherwise stale data could live forever
    await redis.set(`user:${userId}`, JSON.stringify(user), 'EX', 300);
  }
  return user;
}
```

- **Pros**: only data that's actually requested gets cached (lazy); if Redis goes down, the system keeps working (just slower, going straight to the DB).
- **Cons**: the first request after a miss/invalidation is always "slow" (cache miss penalty); there's a brief window of inconsistency between the DB and the cache.

## Write-Through and Write-Behind — write-side alternatives

| Pattern | How it works | Pros | Cons |
|---|---|---|---|
| **Cache-Aside** | Reads go through the cache, writes go directly to the DB (with invalidation) | Simple, cache never "dirty" | Cache miss penalty |
| **Write-Through** | A write goes synchronously to both the cache and the DB | Cache is always consistent with the DB | Every write is slower (two operations) |
| **Write-Behind (Write-Back)** | A write goes to the cache, flushed to the DB asynchronously (batched) | Very fast writes | Risk of data loss if the cache dies before flushing; added complexity |

Write-behind explicitly trades durability for write latency. In an interview, say it plainly: "write-behind is fine for metrics/counters where losing the last few seconds of data is acceptable, but not for payments."

## Eviction Policies — what to evict when the cache is full

```txt
LRU (Least Recently Used)  — evict whatever hasn't been requested for the longest
                              (good for "hot" data with temporal locality)
LFU (Least Frequently Used) — evict whatever is requested least often
                              (better when popularity is stable over time)
TTL-based                    — evict once the lifetime expires,
                              regardless of usage frequency
```

Redis supports several policies out of the box (`allkeys-lru`, `allkeys-lfu`, `volatile-ttl`, etc.) — the choice should match the access pattern: for feed/trending data, LFU is often better than LRU, because a popular post might temporarily "not be requested" for a few minutes but is still hot on average.

## Cache Invalidation — "one of the two truly hard things in CS"

The famous joke ("There are only two hard things in Computer Science: cache invalidation and naming things") isn't just a joke. The problem is that you now have **two sources of truth** (the DB and the cache), and every write creates a window where they can diverge.

```txt
Invalidation strategies:

1. TTL (Time To Live) — simplest, but data can be stale for up to
   TTL minutes. Fine when business logic tolerates staleness.

2. Explicit invalidation (DEL after UPDATE) — the cache is
   removed/updated synchronously with the data change. More precise,
   but requires that ALL write paths remember to invalidate the cache —
   easy to miss as the codebase grows.

3. Event-based invalidation — a data change publishes an event
   (via a queue/CDC), and the cache is invalidated by an async handler.
   Decouples writes from invalidation, but adds delay
   (eventual consistency for the cache).
```

Senior nuance — a **race condition with cache-aside writes**:

```txt
T1: reads old value V1 from the DB (cache miss)
T2: updates the DB to V2, invalidates the cache
T1: writes V1 (stale!) into the cache — after T2 already finished

Result: the cache holds V1, the DB holds V2 — inconsistent until TTL expires
```

This is a rare but real edge case in high-traffic systems. Fixes: a short TTL as a "safety net" (even if invalidation fails, data won't be stuck forever), versioned cache keys (`user:123:v{version}`), or a distributed write lock.

## Cache Stampede (Thundering Herd) — a classic question

The problem: a high-traffic key (e.g., the homepage) expires via TTL — and **thousands of concurrent requests** see a cache miss and **all** hit the DB simultaneously, creating a sudden spike capable of bringing down the DB at exactly the moment of TTL expiration.

```ts
// ❌ No protection: when TTL expires, all concurrent requests
// hit the DB at the same time
async function getHomepage(): Promise<Homepage> {
  const cached = await redis.get('homepage');
  if (cached) return JSON.parse(cached);
  const data = await db.buildHomepage(); // 10,000 concurrent calls!
  await redis.set('homepage', JSON.stringify(data), 'EX', 60);
  return data;
}

// ✅ With a distributed lock: only one request hits the DB,
// others either wait or get slightly stale data
async function getHomepageSafe(): Promise<Homepage> {
  const cached = await redis.get('homepage');
  if (cached) return JSON.parse(cached);

  const lockAcquired = await redis.set('homepage:lock', '1', 'NX', 'EX', 10);
  if (!lockAcquired) {
    // another instance is already recomputing — return slightly stale data
    // or wait and retry (with short polling)
    const stale = await redis.get('homepage:stale');
    if (stale) return JSON.parse(stale);
    await sleep(50);
    return getHomepageSafe();
  }

  const data = await db.buildHomepage();
  await redis.set('homepage', JSON.stringify(data), 'EX', 60);
  await redis.set('homepage:stale', JSON.stringify(data), 'EX', 3600); // 1-hour fallback
  await redis.del('homepage:lock');
  return data;
}
```

Other solutions:

```txt
Random TTL jitter:     TTL = 60 + random(0, 10) seconds
                        → keys expire at different times, spreading the load

Probabilistic early expiration (XFetch):
                        the closer to TTL expiration, the higher the chance
                        that one request "early-refreshes" the value
                        while others keep using the old one

Background refresh:    a separate worker refreshes hot keys BEFORE TTL expires,
                        user requests never see a miss for them
```

## Multi-Level Caching — a cache hierarchy, not one layer

```txt
Browser Cache (HTTP cache-control, Service Worker)
  ↓ miss
CDN Edge Cache (static assets, sometimes full HTML pages)
  ↓ miss
Application-level Cache (in-process, e.g. an in-memory LRU cache per instance)
  ↓ miss
Distributed Cache (Redis/Memcached — shared across all instances)
  ↓ miss
Database
```

Each level filters out part of the traffic for the next one. Senior nuance: an **in-process cache on each instance** is the fastest level (no network round trip), but it's "duplicated" across instances and hard to invalidate (you need a broadcast, e.g. via Redis Pub/Sub, to synchronously clear local caches everywhere). That's why in-process caches are typically used for data that either almost never changes (config, feature flags) or tolerates a few seconds of staleness.

## What to cache, and what not to

```txt
Good candidates:
  - user profiles, product catalogs — read-heavy, change rarely
  - results of expensive aggregations/JOINs
  - sessions (if not stateless via JWT)
  - rate-limit counters, feature flags

Bad candidates (or require extra care):
  - account balances, payment state — here staleness = business risk,
    the source of truth should be queried directly (or a CP-cache with
    explicit invalidation in the same transaction)
  - data that's nearly unique per request (low hit ratio —
    the cache doesn't help, only adds overhead)
```

A metric worth tracking is **cache hit ratio**: if it's below roughly 70-80% for a given type of key, the cache may not be worth the added complexity for that data.

## Common interview mistakes

- **"Let's add Redis" without specifying a pattern (cache-aside vs write-through) or an invalidation strategy** — this is the most common shallow answer; the interviewer expects specifics.

- **Not mentioning cache stampede** when discussing a high-traffic popular key with a TTL — this is one of the most expected follow-up questions.

- **Confusing TTL and eviction policy** — TTL is the explicit lifetime of a specific key; eviction policy (LRU/LFU) is what happens when the cache is **full**, independent of TTL.

- **Ignoring the cache-aside race condition** — assuming "read from DB → write to cache" is atomic and safe under concurrent writes.

- **Caching data that requires strict consistency** (balances, limited inventory) without discussing that staleness here could mean direct financial loss.

- **Forgetting about in-process caches when scaling horizontally** — if the cache lives in each instance's memory, invalidating it on one instance doesn't affect the others.

- **Not giving a numeric sense of cache hit ratio** — "the cache will help" without explaining at what read:write ratio and hit ratio it actually cuts DB load by an order of magnitude.
