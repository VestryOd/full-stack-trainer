# Redis Caching Patterns

## Cache-Aside (Lazy Loading) — the most common pattern

With Cache-Aside the application manages the cache itself. On a read it checks Redis first. If the key is missing — a cache miss — it reads PostgreSQL, writes the result into Redis with a TTL, and returns it. TTL (time to live) is how many seconds the key survives before Redis deletes it.

Hence the second name, lazy loading: only what somebody actually asked for ends up in the cache. On a write the cache is not updated but deleted. The next read then refills it with fresh data.

```typescript
import { createClient } from 'redis';
import { PrismaClient } from '@prisma/client';

const redis = createClient({ url: process.env.REDIS_URL });
const prisma = new PrismaClient();

async function getUserById(userId: string) {
  const cacheKey = `user:${userId}`;

  // 1. Check Redis
  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached); // Cache HIT

  // 2. Cache MISS — read from DB
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true, name: true, email: true, role: true },
  });

  if (!user) {
    // Cache NULL for a short time (protection against Cache Penetration)
    await redis.set(cacheKey, 'null', { EX: 30 });
    return null;
  }

  // 3. Write to Redis with TTL
  await redis.set(cacheKey, JSON.stringify(user), { EX: 3600 }); // 1 hour

  return user;
}

// Invalidation on update
async function updateUser(userId: string, data: Partial<User>) {
  const user = await prisma.user.update({ where: { id: userId }, data });
  await redis.del(`user:${userId}`); // delete cache, next GET will refresh it
  return user;
}
```

```txt
Cache-Aside advantages:
  ✓ Simple to implement
  ✓ Only what's actually requested gets cached (lazy)
  ✓ Redis failure → requests fall through to the database
    (graceful degradation)
  ✓ Database schema and cache schema are independent

Cache-Aside disadvantages:
  ✗ First request after TTL expires: always a Cache MISS (slow)
  ✗ Race condition: two processes can read the database and
    write the cache at the same time
  ✗ Stale data possible between the database update and the
    cache invalidation
```

## Write-Through — synchronous write to cache and database

Write-Through updates the cache on the same code path as the write to the database. The cache is therefore never stale. The price is that you cache rows nobody may ever read, and a Redis outage can now fail a write request.

```typescript
// Write-Through: DB AND cache are written in one operation
// Guarantee: cache is always up to date

async function updateUserWriteThrough(userId: string, data: Partial<User>) {
  // Full atomicity: Redis and DB are separate systems, 100% consistency is impossible
  // But for most cases, sequential write is enough:

  const user = await prisma.user.update({ where: { id: userId }, data });

  // Immediately update cache with new data
  await redis.set(`user:${userId}`, JSON.stringify(user), { EX: 3600 });

  return user;
}

// Downside: if Redis is unavailable → request fails (wrap in try/catch)
async function updateUserWriteThroughSafe(userId: string, data: Partial<User>) {
  const user = await prisma.user.update({ where: { id: userId }, data });

  try {
    await redis.set(`user:${userId}`, JSON.stringify(user), { EX: 3600 });
  } catch (err) {
    console.warn('Cache write failed, DB updated successfully', err);
    // Don't fail the request — DB is updated, cache will just go stale
  }

  return user;
}
```

## Write-Behind (Write-Back) — async database write

Write-Behind acknowledges the write as soon as Redis has it, and a background process pushes it to the database later. Writes become very fast, but anything Redis has not flushed yet is lost if Redis dies.

```txt
Uncommon pattern:
  Write → Redis (fast) → background process → database
  (with delay)

When it's justified:
  Counters (page views, likes) — per-second precision is
  not critical
  Analytics events — can flush once a minute
  Session updates — user activity tracking

Risks:
  Redis crash before flush → data lost
  Complex to implement: needs a reliable flush process
  (BullMQ job, cron)

Example: accumulating page views
  INCR page:123:views (in Redis, instant)
  Every 30 sec: flush accumulated counts to PostgreSQL
```

## Cache Stampede (Thundering Herd) — the problem and solutions

A stampede happens when one popular key expires and every in-flight request misses at the same moment. All of them go to the database at once. The three fixes below let only one request rebuild the value, or stop the keys from expiring together.

```typescript
// Problem: TTL expires → 1000 concurrent requests → all hit DB → overload

// Solution 1: Mutex Lock (only one request updates the cache)
async function getUserWithLock(userId: string) {
  const cacheKey = `user:${userId}`;
  const lockKey = `lock:${cacheKey}`;

  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached);

  // Try to acquire the lock (SET NX EX)
  const acquired = await redis.set(lockKey, '1', { NX: true, EX: 5 });

  if (acquired) {
    // We're first — read from DB and update cache
    try {
      const user = await prisma.user.findUniqueOrThrow({ where: { id: userId } });
      await redis.set(cacheKey, JSON.stringify(user), { EX: 3600 });
      return user;
    } finally {
      await redis.del(lockKey);
    }
  } else {
    // Another process is updating — wait and retry
    await new Promise(resolve => setTimeout(resolve, 50));
    const retried = await redis.get(cacheKey);
    return retried ? JSON.parse(retried) : null;
  }
}

// Solution 2: Random TTL jitter (prevents simultaneous expiry)
const BASE_TTL = 3600;
const jitter = Math.floor(Math.random() * 300); // ±300 sec
await redis.set(cacheKey, JSON.stringify(data), { EX: BASE_TTL + jitter });

// Solution 3: Stale-While-Revalidate
// Store data with a "soft" and "hard" TTL
// On soft expiry → return stale + background refresh
// On hard expiry → full refresh
```

## Cache Penetration — protection against non-existent keys

Penetration is the opposite problem: the requested row does not exist anywhere, so nothing is ever cached and every request reaches the database. The cure is to cache the absence itself, or to reject the key before you query at all.

```typescript
// Attack/problem: requests for user:99999999 that doesn't exist
// Every request: Redis MISS → DB query → null → not cached → DB again

// Solution 1: Cache NULL value
async function getUserSafe(userId: string) {
  const cacheKey = `user:${userId}`;
  const cached = await redis.get(cacheKey);

  if (cached !== null) {
    // 'null' string means "does not exist"
    return cached === 'null' ? null : JSON.parse(cached);
  }

  const user = await prisma.user.findUnique({ where: { id: userId } });

  if (!user) {
    // Cache the absence with a short TTL (30 sec)
    await redis.set(cacheKey, 'null', { EX: 30 });
    return null;
  }

  await redis.set(cacheKey, JSON.stringify(user), { EX: 3600 });
  return user;
}

// Solution 2: Bloom Filter (for advanced cases)
// Pre-load all existing userIds into a Bloom Filter
// Before Redis/DB check: if (!bloomFilter.has(userId)) return null;
// RedisBloom (Redis Stack module): BF.ADD, BF.EXISTS
// ~0.01% false positive rate with proper configuration
```

## Cache Avalanche — mass TTL expiration

A stampede is one hot key; an avalanche is thousands of unrelated keys expiring in the same second. It usually follows a deploy, because every key was written at the same moment with the same TTL. Spread the expiry times and the load stays flat.

```typescript
// Cache Avalanche: many different keys expire at the same time
// Example: new service deployed → all TTLs started from zero → all expire together

// Solution: Random TTL for different data types
const TTL_BASE = {
  user: 3600,      // 1 hour
  product: 1800,   // 30 minutes
  category: 7200,  // 2 hours
};

function getRandomTTL(base: number, spread = 0.1): number {
  const delta = Math.floor(base * spread * (Math.random() * 2 - 1));
  return base + delta; // base ± 10%
}

// On deploy: warm the cache gradually (cache warming)
// Don't flush all keys at once — use rolling invalidation
```

## Session storage pattern

Sessions, token blacklists and rate-limit counters share one shape: short-lived keys whose loss is survivable. That is exactly what a TTL is for, so Redis cleans up after you and no cron job is needed.

```typescript
// Typical use of Redis for sessions / JWT blacklist

// JWT Blacklist (logout → token invalidated)
async function invalidateToken(jti: string, expiresAt: number) {
  const ttl = Math.max(0, expiresAt - Math.floor(Date.now() / 1000));
  await redis.set(`blacklist:${jti}`, '1', { EX: ttl });
}

async function isTokenBlacklisted(jti: string): Promise<boolean> {
  const result = await redis.exists(`blacklist:${jti}`);
  return result === 1;
}

// Rate Limiting (INCR + EXPIRE — sliding counter)
async function checkRateLimit(
  identifier: string,
  maxRequests: number,
  windowSec: number,
): Promise<boolean> {
  const key = `ratelimit:${identifier}:${Math.floor(Date.now() / 1000 / windowSec)}`;
  const count = await redis.incr(key);
  if (count === 1) await redis.expire(key, windowSec * 2);
  return count <= maxRequests;
}
```

## Common interview mistakes

- **"Cache-Aside is the only correct pattern"** — it depends on requirements. Write-Through: when cache staleness is unacceptable. Write-Behind: when ultra-fast writes with eventual consistency are needed. Read-Through, built into some object-relational mapping (ORM) libraries: the cache itself queries the database on a miss, and the application never sees the cache.

- **"Cache Invalidation = just delete the key"** — not in a distributed system. With several application instances, deleting the key opens a race:

```txt
1. Instance A updates the database, then deletes the cache key
2. Instance B reads the same row — but from a read replica that
   has not caught up yet, so it gets the OLD value (replica lag)
3. Instance B writes that old value into the cache
4. Everyone reads stale data until the TTL expires
```

  Fixes: a short TTL on top of explicit invalidation, or event-driven invalidation.

- **"Cache everything you can"** — cache adds complexity (invalidation, stale data, cache penetration). Cache what's worth it: expensive queries (heavy JOINs), external APIs with rate limits, static data. Don't cache: simple lookups by primary key (the PostgreSQL B-Tree index is fast enough), or data that changes very frequently.

- **"TTL solves all staleness problems"** — no. With TTL=1h, data can be up to 1 hour stale after an update. For critical data (balance, inventory) — invalidate cache on every update, not TTL-only. TTL is a safety net, not the primary mechanism.

- **"Cache Stampede is a rare edge case"** — at high traffic it's a real problem. With a popular key, TTL=60s and 10k requests per second, every minute up to 10k requests hit the database at once. Mutex lock or probabilistic early expiration (refresh cache N seconds before TTL expires) are essential.
