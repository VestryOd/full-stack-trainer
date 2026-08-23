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

A String holds any bytes: plain text, a number, or a serialized JSON object. Redis also treats it as a counter, so `INCR` on a String is atomic without a transaction.

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

A Hash is one key holding a flat map of field-value pairs. Reach for it when you update single fields of an object often, because you can write one field without reading the whole object back.

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

A List is an ordered sequence you can push to and pop from at either end. That makes it the cheapest way to build a job queue or a "last N events" buffer.

```typescript
// List = doubly linked list: O(1) push/pop from both ends, O(N) by index

// Queue (FIFO): LPUSH + RPOP
await redis.lPush(
  'jobs:email',
  JSON.stringify({ to: 'user@example.com', template: 'welcome' }),
);
const job = await redis.rPop('jobs:email');

// Stack (LIFO): LPUSH + LPOP
await redis.lPush('history:user:123', 'page-A');
await redis.lPush('history:user:123', 'page-B');
const last = await redis.lPop('history:user:123'); // 'page-B'

// BLPOP — blocking pop (consumer waits for a message)
const result = await redis.blPop('jobs:email', 5); // 5-second timeout
// → { key: 'jobs:email', element: '...' } or null on timeout

// Capped length (sliding window log)
const event = { type: 'page-view', path: '/pricing', at: Date.now() };
await redis.lPush('recent:events', JSON.stringify(event));
await redis.lTrim('recent:events', 0, 99); // keep only the last 100

// LRANGE — get a range
const recent = await redis.lRange('recent:events', 0, -1); // all
const top10 = await redis.lRange('recent:events', 0, 9);   // first 10

// List length
const len = await redis.lLen('jobs:email');
```

## Set — unique values and set operations

A Set stores unique strings with no order, and membership checks are O(1). Redis can also intersect, union or subtract two Sets on the server, so you never pull both lists into the application.

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
const hourKey = new Date().toISOString().slice(0, 13); // '2024-01-01T14'
const clientIp = '203.0.113.7'; // req.ip in Express/Nest

await redis.sAdd(`visitors:${hourKey}`, clientIp);
const uniqueVisitors = await redis.sCard(`visitors:${hourKey}`);
```

## Sorted Set — ranked data

A Sorted Set is a Set where every member also carries a numeric score, and Redis keeps the members ordered by that score. It answers "top 10" and "everything between score X and Y" without sorting anything at read time.

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
const userId = 'user:alice';
const now = Date.now();
const windowMs = 60_000; // 1 minute

await redis.zAdd(`ratelimit:${userId}`, [{ score: now, value: `${now}` }]);
await redis.zRemRangeByScore(`ratelimit:${userId}`, '-inf', now - windowMs);
const count = await redis.zCard(`ratelimit:${userId}`);
if (count > 100) throw new Error('Rate limit exceeded');
await redis.expire(`ratelimit:${userId}`, 60);
```

## HyperLogLog and Bitmap

These two trade accuracy or expressiveness for memory. HyperLogLog counts unique values in a fixed 12 kilobytes no matter how many there are. A Bitmap packs one yes/no flag into every single bit.

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

- **"Hash is always better for storing a user object"** — it depends on the access pattern. Hash is optimal for frequent updates to individual fields. If the entire object is always read and written at once, a JSON String with `SET`/`GET` is simpler and faster. `HGETALL` touches every field, while `GET` is a single read.

- **"List is fine for a queue with multiple consumers"** — a plain List has no delivery guarantees:
  - If several consumers call `RPOP`, only one of them gets the message.
  - There is no acknowledgment, so if that consumer crashes the message is gone.
  - For reliable queues use BullMQ on top of Redis, or Amazon SQS (Simple Queue Service).

- **"Sorted Set is slower than Set"** — for `ZADD`/`ZRANK` it is O(log N) against O(1) for Set. But Sorted Set enables range queries by score, which Set doesn't support at all. The choice depends on the operations needed, not just "speed."

- **"SMEMBERS is safe to use on large Sets"** — SMEMBERS blocks Redis for the duration (single-threaded). For Sets with millions of elements — use `SSCAN` (cursor-based iteration, non-blocking). Same rule applies to `KEYS *` vs `SCAN`, and `HGETALL` for large Hashes vs `HSCAN`.

- **"HyperLogLog is more precise than a regular counter"** — HyperLogLog is approximate (~0.81% error). If exact counts are required — use a Set (but memory is O(N)) or a counter column in the database. HyperLogLog is for analytics where approximation is acceptable: unique daily visitors, unique IPs.
