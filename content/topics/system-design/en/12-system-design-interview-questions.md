# System Design Interview Questions

## How to use this overview

This is a catalog, not 12 new topics. It collects the most common problem statements in Senior Fullstack interviews. Each one is annotated with its **core fork** and points back to a topic covered earlier. Three problems already have full articles of their own: URL Shortener, Chat System and Notification System. Here they get only a short pointer.

The goal isn't to memorize 12 diagrams. It is to notice that **different problem statements often hide the same fork**. For example, "fan-out on write vs on read" shows up in Chat System, Instagram Feed and News Feed alike.

The other 9 problems are covered compactly, always in the same four parts, taken from the Universal System Design Interview Framework article:

| Part | What it answers |
|---|---|
| Problem | what exactly is being built, once the scope is narrowed |
| Core fork | the one decision that shapes everything else |
| Architecture | which blocks are wired in, and why |
| Follow-up | the probe the interviewer adds, with a reasoned answer |

## 1. Design URL Shortener (bit.ly, tinyurl)

Fully covered in the URL Shortener article. The core fork is generating unique short codes in a distributed system. There are three options: Base62 of an auto-increment ID plus a Ticket Server for distributed generation, a hash-based code with collisions, or random plus retry. The second point is a read-heavy architecture, where the cache is a central component and not an optional optimization.

## 2. Design Chat System (Telegram, Slack, WhatsApp)

Fully covered in the Chat System article, with the transport layer in WebSockets and Realtime Systems. The core fork is fan-out on write vs fan-out on read for group chats. The second point is the persist → ACK → deliver ordering for message durability. ACK is the acknowledgement the server sends back to the sender.

## 3. Design Notification System

Fully covered in the Notification System article, with the event-driven foundation in Message Queues. The core fork is the Decision Layer — preferences, channel priority, rate limiting — as a separate layer between the event and delivery. The second point is idempotency under at-least-once delivery.

## 4. Design File Upload Service (photos/videos/documents)

### Problem and core fork

A naive approach routes the file through your backend (`Client → Backend → S3`). S3 is Amazon's object storage; any similar service behaves the same way here. The problem: the backend becomes a bottleneck for large binary traffic. Memory and network bandwidth on the API server go into proxying bytes it doesn't need for business logic.

```txt
✅ Client → Backend: request a pre-signed URL (metadata, permissions)
   Backend → Client: a signed URL with a TTL (see File Storage and CDN)
   Client → S3: uploads the file directly, bypassing the backend
   S3 → Backend (via event/webhook): "file uploaded" → further processing
```

The backend's role is limited to issuing permission and post-processing. The actual byte transfer happens over a direct Client↔S3 channel. The signed URL carries a TTL — a time to live, after which the URL stops working. This is a direct application of pre-signed URLs from the File Storage and CDN article. CDN means content delivery network: a global set of caches sitting close to users.

### Follow-up: how do you generate a thumbnail/preview?

```txt
S3 (event: ObjectCreated) → Queue → Image Processing Worker
  → resize/convert → upload the thumbnail back to S3 (a different prefix/bucket)
  → update the metadata DB (thumbnailUrl)
```

This is the same reasoning as for analytics in URL Shortener. Image processing is a potentially slow operation, and it shouldn't block the "file uploaded" response to the user.

Senior nuance: the worker needs **idempotency**. Most event systems deliver at-least-once, so the same S3 event can arrive twice. Regenerating the same thumbnail must not create duplicates or fail.

### Follow-up: how do you secure the upload?

```txt
- The pre-signed URL is time-limited (TTL ~15 min) and scoped to
  one operation (PutObject on a specific key, not the whole bucket)
- File size limits — via Content-Length in the signature OR via
  an S3 bucket policy
- File type validation — happens at the post-processing step
  (after upload), since the backend can't inspect content before
  upload; the "raw" upload lands in a temporary prefix and is
  moved to permanent storage only after validation
```

## 5. Design Instagram Feed

### Problem and core fork — the same one as Chat System, applied to a different load pattern

```txt
Approach 1: Fan-out on read
  On feed open → gather posts from everyone the user follows,
  sort by time → computed "on the fly"

  + O(1) on post creation
  - expensive reads: joining/merging posts from hundreds of
    authors on every feed open

Approach 2: Fan-out on write
  On post creation → immediately write it into each follower's
  "precomputed feed"

  + reading the feed is just a SELECT on one table (fast)
  - a post from a user with 10M followers = 10M writes —
    the "celebrity problem"
```

### Follow-up: what does real Instagram choose?

**A hybrid** — and this is only a strong answer if you explain **how** the split actually works:

```txt
Regular users (tens-hundreds of followers):
  → fan-out on write — write cost is negligible,
    feed reads are fast

"Celebrity" accounts (millions of followers):
  → fan-out on read OR deferred fan-out — the celebrity's
    post gets merged into the reader's feed at open time,
    rather than pushed to every follower immediately
```

This directly parallels the group-chat fan-out hybrid from the Chat System article. The deciding factor isn't the content type. It is the **write:read ratio for that specific author or chat**. A strong candidate states this general principle, not "Instagram does a hybrid because that's what Instagram does".

## 6. Design YouTube (video hosting)

### Problem and core fork

```txt
Upload → S3 (raw video, can be several GB)
  → Encoding Queue → Workers (transcode into several
    resolutions: 360p/480p/720p/1080p and formats)
  → CDN (finished videos are served from here, not from origin S3)
```

Transcoding is a textbook example of Heavy Computation from the Universal System Design Interview Framework article. The operation takes minutes, so it must not block the "video uploaded" response. It must also be retry-able when a worker fails.

Suppose a worker crashes 80% through transcoding 1080p. Restarting from scratch is an acceptable price for simplicity, compared with the cost of storing partial progress.

### Follow-up: why can't you serve video directly from origin?

```txt
- Bandwidth: a single popular video served directly from one
  origin server to millions of users instantly saturates that
  server's network link
- Latency: users are geographically distributed; without a CDN,
  every request hits one data center, adding hundreds of ms
- Adaptive bitrate streaming (HLS/DASH): video is served in
  chunks of varying quality depending on the user's network —
  this requires many small files, for which a CDN isn't a
  "speed-up" — it's the only practical way to serve them
```

HLS and DASH are the two standard formats for adaptive streaming — HTTP Live Streaming, and Dynamic Adaptive Streaming over HTTP.

This is the CDN pattern from the File Storage and CDN article, applied to the content type with the largest traffic volume by far: video.

## 7. Design Dropbox / Google Drive (file sync)

### Problem and core fork

Separating **metadata** — folder structure, versions, permissions, all in a relational DB (database) — from **file content**, which lives in object storage of the S3 kind:

```txt
Client
 ↓
API (auth, permissions, metadata)
 ↓                    ↓
Metadata DB        Object Storage (S3)
(files, folders,   (file content,
 versions, owners)  addressed by content hash)
```

What distinguishes "just file storage" from Dropbox is **synchronization across devices**. That is almost always the follow-up.

### Follow-up: how do you sync changes across devices?

```txt
Naive: each device periodically polls "what changed?"
  → sync latency = polling interval, extra API load

Better: Change Events + a long-lived connection
  - a file changes on device A → the API creates a
    "FileChanged" event with a version number
  - devices B, C are subscribed to these events (WebSocket/long
    polling, see WebSockets and Realtime Systems) → get notified and download
    the changed portion of the file
```

### Follow-up: how do you avoid re-transferring the whole file for a small change?

```txt
Split the file into fixed-size chunks, addressed by content
hash (content-addressed storage):

  - one paragraph changed in a large document → only 1-2 chunks
    changed → only those are transferred
  - if multiple users upload the same file (same set of chunks)
    → deduplication at the storage layer
```

This is the "versioning" principle applied to data split into content-addressed blocks — the same approach Git uses for storing objects by hash.

## 8. Design Ride Sharing (Uber, Bolt)

### Problem and core fork

The main technical difficulty isn't "store rides in a DB". It is **continuously updated geolocation for thousands of drivers**, plus a fast "who's nearby" search:

```txt
Driver app → periodically (every 3-5 sec) sends
  coordinates → Location Service

The Location Service stores positions in a structure optimized
for geo queries, NOT in a plain relational table with a
full scan over lat/lng
```

### Follow-up: how do you efficiently find nearby drivers?

```txt
Geohash: encodes (lat, lng) into a string — nearby
  coordinates share a string prefix
  → "find nearby drivers" = a prefix search

  geohash("50.450, 30.523") → "ucewef..."
  → all drivers with prefix "ucewe" — in the same area

Alternative: a spatial index (PostGIS GiST index, or
  Redis GEOADD/GEORADIUS — Redis stores geo data as a
  sorted set keyed by geohash under the hood)
```

GiST is a PostgreSQL index type for data that is not a simple sortable value. The name stands for generalized search tree.

A strong answer explains **why** a regular B-tree index on (lat, lng) doesn't work for "within 2 km". Range queries on two independent dimensions at once don't reduce to a single range scan. A geohash or a spatial index turns 2D proximity into 1D proximity: a shared prefix, or a sorted structure.

### Follow-up: how does driver-rider matching work?

```txt
1. The rider requests a ride → the Matching Service finds
   N nearby available drivers (via the geo-index above)
2. The request is sent to drivers (one at a time or in batches)
   over a realtime channel (WebSocket/push)
3. The first to accept is assigned; the rest get a "cancel"
4. Race condition: what if 2 drivers accept at the same time?
   → an atomic operation (a DB transaction with a conditional
     UPDATE, or a distributed lock on ride_id) — analogous to
     the double-booking problem in Booking System below
```

## 9. Design Booking System (Airbnb, cinema seats, flights)

### Problem and core fork

The main problem is **double booking**: two users simultaneously book the last available seat/date.

```txt
❌ Naive:
  1. SELECT — check if it's available
  2. if available → INSERT booking

  Between steps 1 and 2, another request can pass the same
  check → both INSERTs succeed → overbooking
```

### Solution and follow-up: is a Redis lock always needed?

```txt
✅ The default solution — atomicity at the DB level:

  BEGIN;
  SELECT * FROM seats WHERE id = ? FOR UPDATE;  -- row-level lock
  -- if seat.status = 'available' → UPDATE seats SET status = 'booked'
  COMMIT;

  A second concurrent request for the same seat blocks on
  SELECT FOR UPDATE until the first transaction finishes —
  the guarantee comes from the DB itself, no extra infrastructure.
```

`SELECT FOR UPDATE` is sufficient for booking with relatively low write throughput on one resource. A single cinema seat is rarely targeted by thousands of requests per second.

A Redis distributed lock becomes necessary in two cases.

- **The booking operation spans several services or steps**: "hold the seat → wait for payment → confirm". You can't keep a DB transaction open for the whole wait for payment.
- **The resource is extremely hot** — a popular concert sale, for instance. Then even a row-level DB lock becomes a bottleneck.

In both cases the Redis lock has a short TTL (time to live) and only "holds" the seat while checkout proceeds. Final confirmation still goes through an atomic DB operation.

```txt
A "hold" with a TTL — a common pattern:
  Redis: SET seat:123:hold user_456 EX 600 NX
  → if the user doesn't pay within 10 minutes, the hold
    expires automatically and the seat is released with no
    explicit "cancel" needed
```

## 10. Design News Feed (similar to Instagram Feed)

The core fork is identical to Instagram Feed above. It is fan-out on write vs read, with a hybrid chosen by the write:read ratio of a given content source. What News Feed adds is **ranking**. The feed isn't purely chronological — it is sorted by relevance: engagement signals, recency, and relationships between users.

### Follow-up: what becomes the bottleneck once you add ranking?

```txt
Chronological feed: sorted by a single field (created_at) —
  trivial for a DB/precomputed feed

Ranked feed: score = f(recency, author_affinity, engagement, ...)
  → the score isn't static (a post's engagement changes over
    time) → a "precomputed feed" from fan-out on write goes
    stale faster

Practical solution: a two-stage approach —
  1. Candidate generation — fetch ~500 candidates
     (via fan-out/precomputed feed, as before)
  2. Ranking — recompute the score and sort ONLY those 500
     candidates at request time (cheaper than ranking the
     entire corpus of posts)
```

This is again the general principle from the Universal System Design Interview Framework article. An expensive operation — ranking across many signals — runs over a small, already-filtered set, not over all the data.

## 11. Design Rate Limiter

### Problem and solution

```txt
Redis INCR + TTL — the simplest working approach (Fixed Window Counter):

  key = `ratelimit:{userId}:{currentMinute}`
  INCR key
  EXPIRE key 60 (only on the first INCR)
  if value > limit → 429 Too Many Requests
```

### Follow-up: what's the problem with Fixed Window, and what's better?

```txt
Fixed Window: a user can make `limit` requests at the end of
  minute N and another `limit` requests at the start of minute
  N+1 → 2x the limit in a short span at the window boundary

Sliding Window Log / Sliding Window Counter:
  - stores exact request timestamps (or counters per
    sub-interval) and counts requests over the last 60 seconds
    FROM THE CURRENT MOMENT, not from a fixed window start
  - more accurate, but more expensive in memory/computation

Token Bucket:
  - a "bucket" of tokens refills at a fixed rate, each request
    spends a token
  - allows short bursts up to the bucket size, which is often
    closer to real API requirements (a client may legitimately
    send a batch of requests right after a pause)
```

### Follow-up: how do you make the rate limiter distributed (multiple API servers)?

```txt
Redis INCR — being atomic itself already solves this problem:
all API instances increment the same key in shared Redis, so
no race condition arises between servers without extra locks.

Senior nuance: Redis becomes a single point of failure for rate
limiting — if Redis is unavailable, the default behavior is
usually "fail open" (let requests through unlimited) rather
than "fail closed" (reject everything), since a rate limiter
outage shouldn't take down the whole API.
```

## 12. Design Search System (Google-like, product search)

### Problem and core fork

```txt
PostgreSQL → CDC/Events → Elasticsearch (or OpenSearch)
  - PostgreSQL remains the source of truth for transactional data
  - Elasticsearch — a read-side index optimized for full-text
    search (this is CQRS from Database Scaling: the write
    model and read model are separated)
```

CQRS in that block stands for command query responsibility segregation. CDC is change data capture: streaming the database's own log of changes to other systems.

### Follow-up: why not `WHERE name LIKE '%query%'` in PostgreSQL?

```txt
- LIKE '%...%' (with a leading wildcard) CANNOT use a B-tree
  index — a full table scan on every search query
- PostgreSQL's full-text capabilities (tsvector/GIN index) exist,
  but don't cover: relevance with typo tolerance (fuzzy matching),
  synonyms, weighted multi-field ranking, faceted search
  (aggregations over attributes) — this is Elasticsearch/Lucene's
  specialty
- At large document volumes and high search query rates, a
  dedicated search index scales horizontally (sharding by
  default in Elasticsearch) independently of the transactional DB
```

GIN is the PostgreSQL index type for full-text search — a generalized inverted index.

A senior nuance worth mentioning: syncing PostgreSQL → Elasticsearch is **eventually consistent**, whether it goes through an event queue or through CDC. So a record may briefly not be searchable right after creation.

For some use cases that is unacceptable: "I just created a listing and want to find it myself immediately." Two ways out. Add an explicit fallback to a direct PostgreSQL query for the user's own records. Or index synchronously for the critical operations.

## Common patterns across all 12 problems

If you generalize, almost every problem reduces to a combination of the same building blocks covered in earlier topics:

```txt
Load Balancer → API (stateless) → Redis (cache/lock/rate-limit)
                                 → PostgreSQL (source of truth)
                                 → Queue → Workers (async/heavy)
                                 → S3/CDN (files, static assets)
                                 → WebSocket (realtime)
                                 → Elasticsearch (search, optional)
```

But **the set of blocks isn't the answer**. The answer is the sequence of decisions from the Universal System Design Interview Framework article: requirements → scale → data and access patterns. Then: which of these blocks does **this** specific problem need, and why, with explicit trade-offs.

## Common interview mistakes

- **Treating every problem as brand new.** Most "new" problem statements — Instagram Feed, News Feed, chat groups — reduce to the same fan-out on write vs read fork. A candidate who spots that connection shows deeper understanding than one who solves each problem from scratch.

- **Listing blocks with no connection to the specific problem.** "Load Balancer, Redis, PostgreSQL, Queue, S3, CDN" fits almost any system equally well. That is exactly why, on its own, it proves nothing.

- **Using a Redis lock for every concurrency problem.** For most booking scenarios `SELECT FOR UPDATE` is enough and simpler. A distributed lock is needed in specific cases: the operation spans several services, or the resource is extremely hot.

- **"Fail closed" by default for auxiliary systems.** A rate limiter, a recommendation engine or a search index being unavailable shouldn't halt core functionality. You can ship an order without recommendations; you can't ship it without payment.

- **Ignoring eventual consistency between the write model and the read model**, whether it is PostgreSQL → Elasticsearch or a precomputed feed. The defect is not mentioning that this data can be briefly out of sync, and not discussing whether that matters here.

- **Not stating the general principle behind a solution.** For example, explaining geohash as "Uber's magic string" instead of the general technique: turning 2D proximity into 1D proximity through a shared prefix. The general form applies far more broadly.
