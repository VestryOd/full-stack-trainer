# Caching

## Why caching matters — offloading, not just "speed"

A cache cuts the latency of a single request. More importantly, it cuts the **overall load on the database**, so the same database can serve several times as many users.

The raw numbers behind that:

- a Redis or memcached request takes ~0.1-1ms;
- a relational database query that touches disk takes single-to-tens of milliseconds;
- a complex JOIN or aggregation can take hundreds of milliseconds.

| | Without a cache | With a cache (cache hit) |
|---|---|---|
| Request path | Client → API → Database | Client → API → Redis → Response |
| At 10,000 req/s | all 10,000 hit the database | 9,000 served from Redis, 1,000 (miss) hit the database |

The main interview question isn't "what is a cache". It is **where exactly in the architecture it sits, what's stored in it, how it's invalidated, and what happens on a cache miss at scale**. These details separate a senior answer from "let's add Redis".

## Cache-Aside (Lazy Loading) — the default pattern

The application explicitly manages the cache: read from the cache, and on a miss go to the database and store the result.

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

- **Pros**: only data that's actually requested gets cached (lazy). If Redis goes down, the system keeps working — just slower, going straight to the database.
- **Cons**: the first request after a miss or an invalidation is always slow (cache miss penalty). And there's a brief window of inconsistency between the database and the cache.

## Write-Through and Write-Behind — write-side alternatives

| Pattern | How it works | Pros | Cons |
|---|---|---|---|
| **Cache-Aside** | Reads go through the cache, writes go directly to the database (with invalidation) | Simple, cache never "dirty" | Cache miss penalty |
| **Write-Through** | A write goes synchronously to both the cache and the database | Cache is always consistent with the database | Every write is slower (two operations) |
| **Write-Behind (Write-Back)** | A write goes to the cache, flushed to the database asynchronously (batched) | Very fast writes | Risk of data loss if the cache dies before flushing; added complexity |

Write-behind explicitly trades durability for write latency. In an interview, say it plainly. "Write-behind is fine for metrics and counters, where losing the last few seconds of data is acceptable. It is not fine for payments."

## Eviction Policies — what to evict when the cache is full

| Policy | What it evicts | Best when |
|---|---|---|
| **Least recently used (LRU)** | Whatever hasn't been requested for the longest | "Hot" data with temporal locality |
| **Least frequently used (LFU)** | Whatever is requested least often | Popularity is stable over time |
| **Time to live (TTL)** | Anything whose lifetime has expired, regardless of usage frequency | — |

Redis supports several policies out of the box: `allkeys-lru`, `allkeys-lfu`, `volatile-ttl` and others. The choice should match the access pattern. For feed or trending data, LFU is often better than LRU. A popular post might temporarily "not be requested" for a few minutes, yet still be hot on average.

## Cache Invalidation — "one of the two truly hard things in CS"

The famous joke ("There are only two hard things in Computer Science: cache invalidation and naming things") isn't just a joke. The problem is that you now have **two sources of truth**: the database and the cache. Every write creates a window where they can diverge.

Three invalidation strategies, from the simplest to the most decoupled:

1. **TTL** — the simplest one. Data can be stale for as long as the TTL lasts. Fine when business logic tolerates staleness.
2. **Explicit invalidation** (`DEL` after `UPDATE`) — the cache entry is removed or updated synchronously with the data change. More precise, but every write path has to remember to invalidate the cache, and that is easy to miss as the codebase grows.
3. **Event-based invalidation** — a data change publishes an event, via a queue or CDC (change data capture), and an async handler invalidates the cache. This decouples writes from invalidation, but adds delay: the cache becomes eventually consistent.

Senior nuance — a **race condition with cache-aside writes**:

```txt
T1: reads old value V1 from the database (cache miss)
T2: updates the database to V2, invalidates the cache
T1: writes V1 (stale!) into the cache —
    after T2 already finished

Result: the cache holds V1, the database holds V2 —
        inconsistent until the TTL expires
```

This is a rare but real edge case in high-traffic systems. There are three fixes:

- a short TTL as a safety net, so that even if invalidation fails the data won't be stuck forever;
- versioned cache keys (`user:123:v{version}`);
- a distributed write lock.

## Cache Stampede (Thundering Herd) — a classic question

A high-traffic key — say the homepage — expires via TTL. **Thousands of concurrent requests** then see a cache miss and **all** hit the database at the same moment. That is a sudden spike, capable of bringing the database down at exactly the moment of TTL expiration.

```ts
// ❌ No protection: when the TTL expires, all concurrent
// requests hit the database at the same time
async function getHomepage(): Promise<Homepage> {
  const cached = await redis.get('homepage');
  if (cached) return JSON.parse(cached);
  const data = await db.buildHomepage(); // 10,000 concurrent calls!
  await redis.set('homepage', JSON.stringify(data), 'EX', 60);
  return data;
}

// ✅ With a distributed lock: only one request hits the database,
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
  // 1-hour fallback copy
  await redis.set('homepage:stale', JSON.stringify(data), 'EX', 3600);
  await redis.del('homepage:lock');
  return data;
}
```

Other solutions:

```txt
Random TTL jitter:  TTL = 60 + random(0, 10) seconds
   → keys expire at different times, spreading the load

Probabilistic early expiration (XFetch):
   the closer to TTL expiration, the higher the chance
   that one request refreshes the value early
   while the others keep using the old one

Background refresh:
   a separate worker refreshes hot keys ahead of the TTL,
   so user requests never see a miss for them
```

## Multi-Level Caching — a cache hierarchy, not one layer

A cache is rarely a single layer. In a real system a request falls through several of them, from the browser down to the database — including the CDN (content delivery network) edge. Each level filters out part of the traffic for the next one:

```txt
Browser Cache (HTTP cache-control, Service Worker)
  ↓ miss
CDN Edge Cache (static assets, sometimes full HTML pages)
  ↓ miss
Application-level Cache (in-process, e.g. an LRU cache
  in each instance's own memory)
  ↓ miss
Distributed Cache (Redis/Memcached — shared by all instances)
  ↓ miss
Database
```

Senior nuance: an **in-process cache on each instance** is the fastest level, because there is no network round trip. But it is duplicated across instances, and hard to invalidate. Clearing the local caches everywhere at once needs a broadcast — for example via Redis Pub/Sub. That's why they are typically used for data that either almost never changes (config, feature flags) or tolerates a few seconds of staleness.

## What to cache, and what not to

Good candidates:

- user profiles and product catalogs — read-heavy, change rarely;
- results of expensive aggregations or JOINs;
- sessions, if they are not stateless via JWT (JSON Web Token);
- rate-limit counters and feature flags.

Bad candidates, or ones that need extra care:

- account balances and payment state — here staleness is a business risk. Query the source of truth directly, or use a CP (consistency over availability) cache with explicit invalidation in the same transaction;
- data that's nearly unique per request — the hit ratio is low, so the cache doesn't help and only adds overhead.

A metric worth tracking is **cache hit ratio**. If it's below roughly 70-80% for a given type of key, the cache may not be worth the added complexity for that data.

## Common interview mistakes

- **"Let's add Redis" with no pattern (cache-aside vs write-through) and no invalidation strategy** — the most common shallow answer. The interviewer expects specifics.

- **Not mentioning cache stampede** when discussing a high-traffic popular key with a TTL. This is one of the most expected follow-up questions.

- **Confusing TTL and eviction policy.** TTL is the explicit lifetime of a specific key. Eviction policy (LRU/LFU) is what happens when the cache is **full**, independent of TTL.

- **Ignoring the cache-aside race condition** — assuming "read from the database, then write to the cache" is atomic and safe under concurrent writes.

- **Caching data that requires strict consistency** (balances, limited inventory) without discussing that staleness here could mean direct financial loss.

- **Forgetting about in-process caches when scaling horizontally.** If the cache lives in each instance's memory, invalidating it on one instance doesn't affect the others.

- **Not giving a numeric sense of cache hit ratio.** "The cache will help" is not an answer. Name the read:write ratio and the hit ratio at which the cache actually cuts database load by an order of magnitude.
