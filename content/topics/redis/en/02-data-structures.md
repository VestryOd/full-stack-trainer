# Redis Data Structures

## Overview of structures and their complexity

Redis is not just a key-value store: each structure is optimized for specific access patterns. Choosing the right structure directly affects performance and memory usage.

```txt
String     → O(1) SET/GET, binary data up to 512MB
Hash       → O(1) HGET/HSET, O(N) HGETALL, object fields
List       → O(1) LPUSH/RPOP, O(N) LRANGE, doubly-ended queue
Set        → O(1) SADD/SISMEMBER, O(N) SMEMBERS, unique values
Sorted Set → O(log N) ZADD/ZRANGE, range queries by score
Stream     → O(1) XADD, O(N) XRANGE, append-only log
Bitmap     → O(1) SETBIT/GETBIT, bit flags
HyperLogLog → O(1) PFADD/PFCOUNT, ~0.81% error, 12KB memory
```

## String — the universal structure

```typescript
import { createClient } from 'redis';
const redis = createClient({ url: process.env.REDIS_URL });

// Simple value (string, number, JSON)
await redis.set('config:feature-flags', JSON.stringify({ darkMode: true, beta: false }));
await redis.set('user:123:token', 'eyJhbGciOiJIUzI1...', { EX: 86400 });

// Atomic numeric operations
await redis.set('stats:page-views', '0');
const views = await redis.incr('stats:page-views');   // atomic +1
await redis.incrBy('stats:page-views', 10);            // atomic +10
await redis.decr('stats:page-views');                  // atomic -1

// SETNX — set if not exists (basis for simple locks)
const acquired = await redis.setNX('lock:job:123', '1');
if (acquired) {
  await redis.expire('lock:job:123', 30);
  // ... do work
}
// Better: SET key value NX EX 30 (atomic)
await redis.set('lock:job:123', '1', { NX: true, EX: 30 });

// GETSET / GETDEL
const old = await redis.getDel('session:abc'); // get and delete
```

## Hash — object with fields

```typescript
// Hash vs JSON String: Hash allows updating individual fields without deserialization
// JSON String: read all → deserialize → modify → serialize → write
// Hash: HSET user:123 email "new@email.com" → only one field updated

// Write an object
await redis.hSet('user:123', {
  name: 'Alice',
  email: 'alice@example.com',
  role: 'admin',
  loginCount: '0',
});

// Read one field
const email = await redis.hGet('user:123', 'email');

// Read all fields
const user = await redis.hGetAll('user:123');
// → { name: 'Alice', email: 'alice@example.com', role: 'admin', loginCount: '0' }

// Atomic field increment
await redis.hIncrBy('user:123', 'loginCount', 1);

// Check field existence
const hasField = await redis.hExists('user:123', 'email');

// Delete a field
await redis.hDel('user:123', 'temporaryToken');

// When Hash beats JSON String:
// ✓ Frequent updates of individual fields
// ✓ Only some fields need to be read
// ✗ Nesting required (Hash is flat — no nested objects)
// ✗ Full object is always read as a whole (then JSON String is simpler)
```

## List — doubly-ended queue / stack

```typescript
// List = doubly linked list: O(1) push/pop from both ends, O(N) by index

// Queue (FIFO): LPUSH + RPOP
await redis.lPush('jobs:email', JSON.stringify({ to: 'user@example.com', template: 'welcome' }));
const job = await redis.rPop('jobs:email');

// Stack (LIFO): LPUSH + LPOP
await redis.lPush('history:user:123', 'page-A');
await redis.lPush('history:user:123', 'page-B');
const last = await redis.lPop('history:user:123'); // 'page-B'

// BLPOP — blocking pop (consumer waits for a message)
const result = await redis.blPop('jobs:email', 5); // 5-second timeout
// → { key: 'jobs:email', element: '...' } or null on timeout

// Capped length (sliding window log)
await redis.lPush('recent:events', JSON.stringify(event));
await redis.lTrim('recent:events', 0, 99); // keep only the last 100

// LRANGE — get a range
const recent = await redis.lRange('recent:events', 0, -1); // all
const top10 = await redis.lRange('recent:events', 0, 9);   // first 10

// List length
const len = await redis.lLen('jobs:email');
```

## Set — unique values and set operations

```typescript
// Set: unique strings, O(1) add/check/remove

// Tags for a post
await redis.sAdd('post:123:tags', 'redis', 'caching', 'backend');
await redis.sAdd('post:123:tags', 'redis'); // duplicate — ignored

// Membership check (instant)
const isTagged = await redis.sIsMember('post:123:tags', 'redis'); // true

// All tags
const tags = await redis.sMembers('post:123:tags');

// Followers/Following
await redis.sAdd('user:123:following', 'user:456', 'user:789');
await redis.sAdd('user:456:following', 'user:123', 'user:789');

// Mutual follows (intersection)
const mutual = await redis.sInter('user:123:following', 'user:456:following');
// → ['user:789']

// Set operations
const union = await redis.sUnion('user:123:following', 'user:456:following');
const diff = await redis.sDiff('user:123:following', 'user:456:following');

// Random element (for lotteries, random recommendations)
const random = await redis.sRandMember('post:123:tags');

// Rate limiting with Set (unique IPs in the last hour)
await redis.sAdd(`visitors:${hourKey}`, clientIp);
const uniqueVisitors = await redis.sCard(`visitors:${hourKey}`);
```

## Sorted Set — ranked data

```typescript
// Sorted Set: unique elements with a score (float), O(log N) insert/update
// Internally: Skip List + Hash Table → fast range queries by score

// Leaderboard
await redis.zAdd('leaderboard:game', [
  { score: 5000, value: 'user:alice' },
  { score: 7500, value: 'user:bob' },
  { score: 3200, value: 'user:carol' },
]);

// Top 3 (descending by score)
const top3 = await redis.zRangeWithScores('leaderboard:game', 0, 2, { REV: true });
// → [{ value: 'user:bob', score: 7500 }, ...]

// User rank (0-based, ascending)
const rank = await redis.zRank('leaderboard:game', 'user:alice');
const rankRev = await redis.zRevRank('leaderboard:game', 'user:alice'); // descending

// Update score (atomic)
await redis.zIncrBy('leaderboard:game', 1000, 'user:alice');

// User's score
const score = await redis.zScore('leaderboard:game', 'user:alice');

// Range by score (e.g., all users with > 5000 points)
const highScorers = await redis.zRangeByScore('leaderboard:game', 5001, '+inf');

// Sliding Window Rate Limiting with Sorted Set:
const now = Date.now();
const windowMs = 60_000; // 1 minute

await redis.zAdd(`ratelimit:${userId}`, [{ score: now, value: `${now}` }]);
await redis.zRemRangeByScore(`ratelimit:${userId}`, '-inf', now - windowMs);
const count = await redis.zCard(`ratelimit:${userId}`);
if (count > 100) throw new Error('Rate limit exceeded');
await redis.expire(`ratelimit:${userId}`, 60);
```

## HyperLogLog and Bitmap

```typescript
// HyperLogLog: approximate count of unique elements
// ~12KB memory regardless of element count, ~0.81% error rate

// Unique visitors
await redis.pfAdd('visitors:2024-01-01', 'user:123', 'user:456', 'user:789');
await redis.pfAdd('visitors:2024-01-01', 'user:123'); // duplicate — not counted
const uniqueCount = await redis.pfCount('visitors:2024-01-01'); // ~3

// Merge multiple HLLs (unique visitors for the week)
await redis.pfMerge('visitors:week', 'visitors:2024-01-01', 'visitors:2024-01-02');

// Bitmap: bit flags, O(1) SETBIT/GETBIT
// Example: track active days for a user (365 bits = 45 bytes)
const dayOfYear = 15;
await redis.setBit(`user:123:activity:2024`, dayOfYear, 1);
const wasActive = await redis.getBit(`user:123:activity:2024`, dayOfYear);

// BITCOUNT: number of active days
const activeDays = await redis.bitCount(`user:123:activity:2024`);
```

## Common interview mistakes

- **"Hash is always better for storing a user object"** — it depends on the access pattern. Hash is optimal for frequent updates to individual fields. If the entire object is always read/written at once — a JSON String with `SET`/`GET` is simpler and faster (`HGETALL` involves multiple ops vs a single `GET`).

- **"List is fine for a queue with multiple consumers"** — List without extra logic is not suitable: if multiple consumers call `RPOP`, only one gets the message, but there's no acknowledgment — if the consumer crashes, the message is lost. For reliable queues: BullMQ (on top of Redis) or SQS.

- **"Sorted Set is slower than Set"** — for ZADD/ZRANK: O(log N) vs O(1) for Set. But Sorted Set enables range queries by score, which Set doesn't support at all. The choice depends on the operations needed, not just "speed."

- **"SMEMBERS is safe to use on large Sets"** — SMEMBERS blocks Redis for the duration (single-threaded). For Sets with millions of elements — use `SSCAN` (cursor-based iteration, non-blocking). Same rule applies to `KEYS *` vs `SCAN`, and `HGETALL` for large Hashes vs `HSCAN`.

- **"HyperLogLog is more precise than a regular counter"** — HyperLogLog is approximate (~0.81% error). If exact counts are required — use a Set (but memory is O(N)) or a regular DB increment. HyperLogLog is for analytics where approximation is acceptable: unique daily visitors, unique IPs.
