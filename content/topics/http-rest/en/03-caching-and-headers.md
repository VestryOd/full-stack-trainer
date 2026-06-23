<!-- verified: 2026-06-23, corrections: 0 -->
# Caching and Headers

## Why HTTP Caching Exists and How It Works

HTTP caching means storing a response and reusing it without hitting the server again. The benefit is twofold: the client gets a faster response, the server handles less load.

Cache exists at several layers:

```txt
Client (browser)
    │
    │  ← Private cache: stores responses for this user only
    │    (session data, profile, cart)
    │
CDN / Reverse Proxy (Cloudflare, nginx, Varnish)
    │
    │  ← Shared cache: stores responses for all users
    │    (static assets, public API responses)
    │
Origin Server (backend)
```

All caching behavior is controlled by headers. The primary one is `Cache-Control`.

---

## Cache-Control — Full Directive Breakdown

`Cache-Control` can appear in both **responses** (server tells caches "here are the rules for this resource") and **requests** (client tells caches "here's how I want to use the cache").

### Response Directives (server → client/CDN)

```http
Cache-Control: max-age=3600
```
Cache the resource for 3600 seconds (1 hour) from the time it was received. After that it becomes "stale."

```http
Cache-Control: s-maxage=86400
```
Same as `max-age`, but only for **shared caches** (CDN, proxies). Overrides `max-age` for CDN. The browser uses `max-age`.

```http
Cache-Control: no-cache
```
The cache **may** store the response, but must **revalidate** with the server before using it (conditional request). If the server says "not modified" → 304, the cached copy is used. Does NOT mean "don't cache."

```http
Cache-Control: no-store
```
Don't store anything. No cache at all — not in the browser, not in CDN. For sensitive data (banking transactions, medical records).

```http
Cache-Control: private
```
Cache only in the private cache (browser). CDNs and proxies must not cache. For personalized responses.

```http
Cache-Control: public
```
May be cached in shared caches (CDN). Usually combined with `max-age`. For static assets and public content.

```http
Cache-Control: must-revalidate
```
If a resource is stale (`max-age` expired), the stale version cannot be used — the cache must revalidate with the server. Without this, some caches may serve stale content.

```http
Cache-Control: immutable
```
The resource will never change — no need to check freshness even after `max-age` expires. Used for versioned assets (`main.abc123.js`).

```http
Cache-Control: stale-while-revalidate=60
```
Serve the stale cache for up to 60 seconds while a background revalidation happens. Improves perceived performance: the user doesn't wait; the update is async.

```http
Cache-Control: stale-if-error=3600
```
If the server is unavailable (5xx, timeout), serve the stale cache for up to 3600 seconds. Protects against transient failures.

### Directive Combinations

```http
# Public static asset — cache everywhere for a year:
Cache-Control: public, max-age=31536000, immutable

# Private user data — browser only, 5 minutes:
Cache-Control: private, max-age=300

# Dynamic data — CDN caches for 1 min, browser revalidates:
Cache-Control: public, s-maxage=60, no-cache

# Don't cache at all (personal/sensitive data):
Cache-Control: no-store

# Aggressive freshness with degradation protection:
Cache-Control: public, max-age=3600, stale-while-revalidate=60, stale-if-error=86400
```

### Request Directives (client → server)

The client can also control caching via `Cache-Control` on requests:

```http
Cache-Control: no-cache     # Bypass cache, get a fresh response
Cache-Control: no-store     # Don't store the response
Cache-Control: max-age=0    # Only accept a cache fresher than 0 seconds (= always revalidate)
Cache-Control: max-stale=60 # Accept cache even if stale by up to 60 seconds
```

---

## Conditional Requests

When a cache is stale, the client doesn't have to download the full resource again — it can ask the server "has the resource changed?" This is a conditional request. Two mechanisms:

### ETag (Entity Tag)

The server returns a unique version identifier for the resource. On the next request, the client sends it back.

```txt
Request 1: client has no cache
─────────────────────────────────────────────────────
GET /api/users/42 HTTP/1.1

HTTP/1.1 200 OK
ETag: "v3-abc123"
Cache-Control: max-age=300

{ "id": 42, "name": "Alice" }

Request 2: cache is stale (after 5 minutes), client revalidates
─────────────────────────────────────────────────────
GET /api/users/42 HTTP/1.1
If-None-Match: "v3-abc123"

HTTP/1.1 304 Not Modified
ETag: "v3-abc123"
(no body — bandwidth saved)

Request 3: resource has changed
─────────────────────────────────────────────────────
GET /api/users/42 HTTP/1.1
If-None-Match: "v3-abc123"

HTTP/1.1 200 OK
ETag: "v4-def456"
Cache-Control: max-age=300

{ "id": 42, "name": "Alice Updated" }
```

ETags come in two flavors:
```http
ETag: "abc123"    # Strong ETag — byte-for-byte identical content
ETag: W/"abc123"  # Weak ETag — semantically equivalent content
                  # (whitespace differences, JSON field order, etc.)
```

### Last-Modified

A time-based alternative to ETag:

```http
# Server response:
Last-Modified: Mon, 23 Jun 2025 10:00:00 GMT

# Client's next request:
If-Modified-Since: Mon, 23 Jun 2025 10:00:00 GMT

# Response if unchanged:
HTTP/1.1 304 Not Modified
```

**ETag is better than Last-Modified** in most cases:
- More precise: a file may be re-saved with the same content but a different timestamp
- No timezone or second-level precision issues
- Can store an arbitrary fingerprint (hash, version number)

### If-Match for PUT/PATCH (Optimistic Locking)

```http
# Client reads a resource, receives ETag:
GET /api/documents/5
→ ETag: "v2"

# Client updates, requiring the version hasn't changed:
PUT /api/documents/5
If-Match: "v2"
{ "content": "..." }

# If someone else already changed it:
HTTP/1.1 412 Precondition Failed

# If the version matches:
HTTP/1.1 200 OK
ETag: "v3"
```

---

## Cache Layers: Browser vs CDN vs Proxy

```txt
┌──────────────────────────────────────────────────────────────┐
│                         Browser                              │
│  Stores: GET responses for the current user                 │
│  Capacity: a few hundred MB (user-configurable)             │
│  Key: URL + Vary                                            │
│  Controlled by: Cache-Control: private or public            │
└──────────────────────────────────────────────────────────────┘
           ↕ requests pass through (on cache miss)
┌──────────────────────────────────────────────────────────────┐
│                 CDN (Cloudflare, CloudFront, Fastly)         │
│  Stores: public responses for all users                     │
│  Capacity: practically unlimited                            │
│  Key: URL + Vary + often custom cache keys                  │
│  Controlled by: Cache-Control: public, s-maxage=N           │
│  Bonus: edge nodes close to the user (worldwide)           │
└──────────────────────────────────────────────────────────────┘
           ↕ on cache miss, goes to origin
┌──────────────────────────────────────────────────────────────┐
│            Reverse Proxy / Load Balancer (nginx, Varnish)   │
│  Stores: shared cache inside infrastructure                 │
│  Offloads origin from repeated requests                     │
└──────────────────────────────────────────────────────────────┘
           ↕ on cache miss
┌──────────────────────────────────────────────────────────────┐
│                      Origin Server                           │
└──────────────────────────────────────────────────────────────┘
```

**Key distinction:**
- `Cache-Control: private` → browser cache only, CDN skips it
- `Cache-Control: public` → both browser and CDN cache it
- `Cache-Control: s-maxage=3600` → CDN caches for 1 hour, browser uses `max-age`

---

## The Vary Header

`Vary` tells the cache: "the same URL can return different content depending on these request headers." The cache must store separate copies for each combination.

```http
# Server supports JSON and XML:
Vary: Accept

# JSON request — stored separately:
GET /api/users
Accept: application/json
→ saves "JSON copy"

# XML request — stored separately:
GET /api/users
Accept: application/xml
→ saves "XML copy"
```

Other uses:
```http
Vary: Accept-Encoding    # gzip vs br vs identity — almost always needed
Vary: Accept-Language    # localized responses
Vary: Authorization      # different content per user
                         # (if Authorization is in Vary, CDN won't cache —
                         #  every user has a unique token)
```

**Caution with `Vary: Authorization`**: combining it with `Cache-Control: public` causes the CDN to store a separate copy for every unique auth token — effectively breaking the cache.

---

## Cache Invalidation

"There are only two hard things in Computer Science: cache invalidation and naming things." — Phil Karlton

When a resource changes on the server, the cache doesn't know. Strategies:

### 1. URL Versioning (Cache Busting)

The most reliable approach — change the URL when content changes:

```txt
Version 1:  /static/main.js?v=1   or   /static/main.abc123.js
After change: /static/main.js?v=2  or   /static/main.def456.js
```

The browser sees a new URL → makes a fresh request. The old URL with `max-age=31536000` is served from cache without any requests to the server.

This is the standard approach for assets (JS, CSS, images).

### 2. Programmatic CDN Purge

CDNs provide APIs to purge specific entries:

```typescript
// Cloudflare: purge by cache tag
await fetch("https://api.cloudflare.com/client/v4/zones/{id}/purge_cache", {
  method: "POST",
  headers: { "Authorization": `Bearer ${CF_TOKEN}` },
  body: JSON.stringify({ tags: ["user-42"] }),
});

// AWS CloudFront: create an invalidation
await cloudfrontClient.send(new CreateInvalidationCommand({
  DistributionId: DISTRIBUTION_ID,
  InvalidationBatch: {
    Paths: { Quantity: 1, Items: ["/api/users/42"] },
    CallerReference: Date.now().toString(),
  },
}));
```

### 3. Short TTL + stale-while-revalidate

Instead of explicit invalidation — a short TTL:

```http
Cache-Control: public, max-age=60, stale-while-revalidate=30
```

The resource is fresh for 60 seconds. For the next 30 seconds, the CDN serves the stale version and simultaneously revalidates in the background. Maximum staleness: 90 seconds. Appropriate for content where a short delay is acceptable.

---

## Practical Example: Express + Caching Strategies

```typescript
import express from "express";
import crypto from "crypto";

const app = express();

// Static assets — cache forever (URL changes when content changes)
app.use("/static", express.static("public", {
  maxAge: "1y",
  immutable: true,
}));

// Public data — CDN caches for 1 min, browser revalidates
app.get("/api/articles", async (req, res) => {
  const articles = await db.articles.findAll({ where: { published: true } });
  const etag = crypto
    .createHash("md5")
    .update(JSON.stringify(articles))
    .digest("hex");

  res.set({
    "Cache-Control": "public, s-maxage=60, no-cache",
    "ETag": `"${etag}"`,
  });

  if (req.headers["if-none-match"] === `"${etag}"`) {
    return res.sendStatus(304);
  }

  res.json(articles);
});

// Private user data — browser only, 5 minutes
app.get("/api/users/me", requireAuth, async (req, res) => {
  const user = await db.users.findById(req.user.id);

  res.set("Cache-Control", "private, max-age=300");
  res.json(user);
});

// Sensitive data — no caching
app.get("/api/payments/:id", requireAuth, async (req, res) => {
  const payment = await db.payments.findById(req.params.id);

  res.set("Cache-Control", "no-store");
  res.json(payment);
});

// Conditional PUT with optimistic locking
app.put("/api/documents/:id", requireAuth, async (req, res) => {
  const ifMatch = req.headers["if-match"];
  const doc = await db.documents.findById(req.params.id);

  if (!doc) return res.sendStatus(404);

  if (ifMatch && ifMatch !== `"${doc.version}"`) {
    return res.sendStatus(412); // Precondition Failed
  }

  const updated = await db.documents.update(req.params.id, req.body);

  res.set("ETag", `"${updated.version}"`);
  res.json(updated);
});
```

---

## Pragma: no-cache — Legacy

`Pragma` is an obsolete HTTP/1.0 header:

```http
Pragma: no-cache
```

Equivalent to `Cache-Control: no-cache`, but only for HTTP/1.0 caches. Modern servers should return `Cache-Control`, but for compatibility with very old proxies, some APIs still include both. In practice, `Pragma` can be ignored.

---

## Full Caching Flow

```txt
Client makes GET /api/articles

           ┌─────────────────────┐
           │  In cache?          │
           └─────────────────────┘
                    │
          ┌─────────┴─────────┐
          │ No                │ Yes
          ▼                   ▼
   Request to server    ┌──────────────┐
          │             │  Fresh?      │
          │             └──────────────┘
          │                   │
          │           ┌───────┴───────┐
          │           │ Yes           │ No
          │           ▼               ▼
          │     Return cache   Conditional Request
          │                   If-None-Match / If-Modified-Since
          │                           │
          │                   ┌───────┴───────┐
          │                   │ 304           │ 200
          │                   │ Not Modified  │ OK
          │                   ▼               ▼
          │             Update TTL,      Store new
          │             return cache     response in cache
          │
          ▼
    Store in cache
    (if Cache-Control permits)
```

---

## Common Interview Traps

- **"`no-cache` means don't cache"** — the most common mistake. `no-cache` means: you may store the response, but always revalidate before using it. `no-store` means don't cache at all. These are different things with different performance characteristics.

- **"ETag is a hash of the file"** — not necessarily. An ETag can be a hash, a version from the database, a timestamp, or any string that uniquely represents the version of the resource. The server defines the format.

- **"`Cache-Control: public` makes cached data visible to all users"** — yes, which is exactly why personalized responses need `private`. Use `public` only for data that is identical for every user.

- **"304 means an error"** — no. 304 Not Modified is a successful response meaning "your cache is current, use it." It saves bandwidth and reduces server load.

- **"`Vary: *` — is that a problem?"** — yes. `Vary: *` tells the cache "every request is unique" — effectively disabling it. Never use it unless you understand the consequences.

- **"CDN cache can be invalidated instantly"** — almost impossible without a purge API call. This is why critical updates (hotfixes, security patches) require either the CDN purge API, URL versioning (cache busting), or a very short TTL with `stale-while-revalidate`.

- **"stale-while-revalidate breaks consistency"** — it's a deliberate tradeoff. If users can receive data that's 90 seconds old — that's fine for most content. For banking transactions or inventory counts — it's not.
