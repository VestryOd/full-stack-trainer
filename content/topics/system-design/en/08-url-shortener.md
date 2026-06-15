# URL Shortener Design

## Requirements Clarification

This is one of the most "standard" interview questions — which is exactly why the interviewer expects a structured approach rather than jumping straight to a diagram (see [System Design Fundamentals]).

**Functional Requirements:**

```txt
- given a long URL, create a short code (POST /shorten)
- given a short code, redirect to the original URL (GET /:code)
- (clarify) custom aliases ("app.com/my-link")?
- (clarify) link expiration?
- (clarify) click analytics — needed, and in what form?
```

**Non-Functional Requirements:**

```txt
- Read:Write ratio — typically 100:1 or higher (a link is created once,
  visited many times) → read-heavy, needs a cache
- Redirect latency — should be minimal (it's on the hot UX path)
- Code uniqueness — mandatory, collisions aren't acceptable
- Availability — high (a redirect shouldn't fail even if
  analytics is temporarily down)
```

### Quick scale estimate

```txt
100M new links/month → ~40 writes/sec (average)
Read:Write = 100:1   → ~4,000 reads/sec (average), higher at peak

Storage: 100M links/month * 500 bytes (URL + metadata) * 5 years
  ≈ 100M * 12 * 5 * 500B ≈ 3 TB over 5 years — not a problem for a single DB
  (volume does NOT require sharding by itself — just an index on shortCode)
```

Conclusion: this system **doesn't** require sharding for data volume — the core challenges lie elsewhere: generating unique codes at scale and caching the read path.

## Generating short codes — the central question of this topic

### Option 1: Hash (MD5/SHA256) + truncation

```ts
function generateCode(longUrl: string): string {
  const hash = crypto.createHash('md5').update(longUrl).digest('hex');
  return hash.slice(0, 7); // first 7 hex characters
}
```

- Pros: deterministic (the same URL → the same code — usable for deduplication).
- Cons: **collisions are inevitable** with a truncated hash — you need a DB check + a strategy ("if taken, take the next N characters or add a salt"). This turns a simple operation into a potentially multi-step one with retries.

### Option 2: Base62-encoding an auto-increment ID

```ts
const BASE62 = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';

function toBase62(num: number): string {
  if (num === 0) return BASE62[0];
  let result = '';
  while (num > 0) {
    result = BASE62[num % 62] + result;
    num = Math.floor(num / 62);
  }
  return result;
}
// toBase62(125) → "cb"
// 7 Base62 characters cover 62^7 ≈ 3.5 * 10^12 combinations
```

- Pros: guaranteed uniqueness (the ID is unique by definition — `PRIMARY KEY AUTO_INCREMENT`), the code gets shorter early on and grows gracefully, no collisions.
- Cons — and this is **the main senior nuance**: an auto-increment ID from a single DB is a **single point of contention** for writes. At scale, many API instances can't safely generate the next ID "on their own" without hitting the DB on every request.

### Solution for distributed generation: pre-allocated ID ranges (Ticket Server)

```txt
A separate service (or a DB table with an atomic UPDATE) hands out
an entire RANGE of IDs at once to EACH API instance:

  Instance A: requests a range → gets [1..1000]
  Instance B: requests a range → gets [1001..2000]

Each instance generates short codes from its own range
LOCALLY, without hitting the DB on every request —
the "ticket server" is only consulted once per 1,000 requests.
```

```sql
-- atomically allocate the next range
UPDATE id_ranges SET current_max = current_max + 1000
WHERE id = 1
RETURNING current_max - 1000 AS range_start, current_max AS range_end;
```

This is a classic solution (used, e.g., in Flickr's Ticket Server, Instagram's ID generation) — it turns "the DB is a bottleneck on every write" into "the DB is a bottleneck once per 1,000 writes," reducing load by orders of magnitude.

### Option 3: Random + collision check

```ts
async function generateUniqueCode(): Promise<string> {
  for (let attempt = 0; attempt < 5; attempt++) {
    const code = randomBase62String(7);
    const exists = await db.shortUrl.findUnique({ where: { code } });
    if (!exists) return code;
  }
  throw new Error('Failed to generate unique code after 5 attempts');
}
```

- With 7 Base62 characters (~3.5 * 10^12 combinations), the collision probability at millions of records is tiny (see "birthday paradox") but **not zero** — so a check + retry is always needed, and it's important to explicitly note this is a probabilistic approach, unlike auto-increment-based Base62 which is guaranteed.

## Read Path: redirect — the hottest path in the system

```txt
GET /abc123
  ↓
Redis: GET shortcode:abc123 → cache hit → 302 Redirect (fast)
  ↓ (miss)
PostgreSQL: SELECT longUrl WHERE shortCode = 'abc123'
  ↓
Redis: SET shortcode:abc123 (with a TTL)
  ↓
302 Redirect
```

### 301 vs 302 — a non-obvious but real senior question

```txt
301 Moved Permanently:
  The browser CACHES the redirect locally — repeat visits
  to /abc123 may never reach the server again.
  + less server load
  - clicks can't be counted (the browser doesn't re-request)
  - the target URL for an existing short code can't be changed

302 Found (Temporary Redirect):
  The browser does NOT cache — every visit reaches the server.
  + accurate click analytics
  + the target URL can be changed later
  - more server load (offset by the Redis cache)
```

For a URL shortener with analytics, the correct choice is **302**, and you should justify it explicitly (candidates often default to 301 "because permanent sounds right" without considering analytics).

## Analytics — asynchronous, off the hot path

```txt
GET /abc123
  ↓ (synchronous, minimal latency)
302 Redirect sent to the user
  ↓ (asynchronous, fire-and-forget)
Queue: { shortCode: 'abc123', timestamp, userAgent, referrer, ip }
  ↓
Worker → batched insert into the Analytics DB (ClickHouse/an analytical store)
```

Why not `UPDATE clicks SET count = count + 1` synchronously on every redirect: it's an extra DB write **on the redirect's critical path** — under peak load, this exact write could become the bottleneck, slowing down what should be as fast as possible. A queue (see [Message Queues]) decouples "respond to the user" from "count the click."

## Custom Aliases and Expiration

```txt
Custom alias ("app.com/my-campaign"):
  - check uniqueness before creation (UNIQUE constraint on shortCode)
  - not covered by Base62/Ticket Server generation —
    a separate write path with explicit collision checking

Expiration:
  - an expiresAt field on the ShortUrls table
  - checked on redirect: if expiresAt < now() → 404/410 Gone
  - a periodic job to remove expired records
    (or a Redis cache TTL + lazy check against the DB)
```

## Final architecture

```txt
                    ┌─────────────┐
Client ──────────→ │ Load Balancer│
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  API Servers │ (stateless)
                    └──────┬──────┘
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
           Redis      PostgreSQL        Queue (clicks)
        (hot codes)  (source of truth)       │
                                              ▼
                                       Analytics Worker
                                              │
                                              ▼
                                       Analytics DB
```

Read replicas for PostgreSQL get added if redirect traffic after the Redis cache is still significant — but in most realistic scenarios, the Redis hit ratio for popular links (a Zipf distribution: a small share of links gets most of the traffic) makes this a lower priority.

## Common interview mistakes

- **Using `hash % N` or simple MD5 truncation without discussing collisions** — without a check + retry strategy, this isn't a "solution," it's a hidden bug source at scale.

- **Auto-increment ID without discussing distributed generation** — simple on a single server, but "how does this work with 50 API instances" is an expected follow-up, and a Ticket Server/pre-allocated ranges is the expected answer.

- **Defaulting to a 301 redirect** — without realizing it makes analytics impossible and the user may never reach the server again.

- **A synchronous click-counter increment** — a DB write on every redirect on the hot path, with no queue.

- **Not estimating data volume** — trying to justify sharding for a system where 5 years of data fits in a couple TB and works fine in a single indexed DB.

- **Treating the cache as an "optional improvement"** — for a 100:1+ read:write ratio, the cache isn't an optimization, it's a central architectural component.
