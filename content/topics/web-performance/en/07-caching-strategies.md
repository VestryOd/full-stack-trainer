# Caching Strategies

## Why caching is the most impactful optimization

Caching is the only optimization that can reduce load time **to zero**: a cached resource requires not a single byte of network traffic.

```txt
Without cache (every request):
  DNS → TCP → TLS → Request → Server → Response
  = 200–800ms even for small resources

With cache (memory cache):
  = 0ms (< 1ms from RAM)

With cache (disk cache):
  = 2–10ms (disk read)

With cache (CDN edge, nearest server):
  = 10–50ms (network RTT to the nearest node)

Browser cache priority (fastest to slowest):
  1. Memory cache (tab still open)
  2. Service Worker cache
  3. HTTP disk cache
  4. Push cache (HTTP/2, short-lived)
  → Network (if nothing found)
```

## HTTP Cache-Control — the foundation

`Cache-Control` is the primary header. Its directives determine: who can cache, for how long, and whether validation is required.

### Cache-Control directives

```txt
max-age=N         — cache for N seconds (from response time)
s-maxage=N        — same, but only for shared caches (CDN, proxies)
                    overrides max-age for CDN

no-cache          — CAN be cached, but MUST validate before
                    each use (does NOT mean "don't cache"!)

no-store          — MUST NOT cache at all (sensitive data)

public            — can be stored in a shared cache (CDN)
private           — only in the user's browser (not CDN)

immutable         — resource will NEVER change; don't validate
                    even on an explicit refresh (F5)

must-revalidate   — after max-age expires, MUST revalidate
                    (don't serve stale even on server error)

stale-while-revalidate=N  — serve stale for up to N seconds,
                            revalidating in the background

stale-if-error=N  — serve stale if server is unavailable (up to N seconds)
```

### Caching strategies by resource type

```ts
// Strategy 1: Static assets with a content hash in the filename
// (JS, CSS, images from the bundler)
// Filename: main.a3f2c9d.js — changes only when content changes
// Therefore: cache forever

// Express/Node.js
app.use('/static', express.static('dist', {
  maxAge: '1 year',
  immutable: true,
  // Cache-Control: public, max-age=31536000, immutable
}));

// Next.js does this automatically for /_next/static/
// (the hash in the path guarantees cache busting on deploy)
```

```ts
// Strategy 2: HTML documents
// DON'T hash the filename (URLs must be stable).
// Use no-cache — browser validates on every request,
// but if ETag matched — serves from cache (304, no download)

res.setHeader(
  'Cache-Control',
  'no-cache' // or: max-age=0, must-revalidate
);

// With a CDN — separate browser and CDN cache behavior:
res.setHeader(
  'Cache-Control',
  'public, max-age=0, s-maxage=60, stale-while-revalidate=600'
  // Browser: don't cache (max-age=0)
  // CDN: cache for 60 seconds, then stale for another 600
);
```

```ts
// Strategy 3: API responses
// Depends on the nature of the data:

// Personal data (cart, profile):
res.setHeader('Cache-Control', 'private, no-cache');

// Public data, changes rarely (article list):
res.setHeader(
  'Cache-Control',
  'public, max-age=60, stale-while-revalidate=3600'
);

// Real-time data (prices, availability):
res.setHeader('Cache-Control', 'no-store');
```

```ts
// Next.js App Router — server-side fetch caching
async function getProducts() {
  const res = await fetch('https://api.example.com/products', {
    next: {
      revalidate: 60,  // ISR: regenerate after 60 seconds
      // or:
      tags: ['products'], // cache tag for manual invalidation
    },
  });
  return res.json();
}

// Manual invalidation by tag (e.g. on a CMS webhook)
import { revalidateTag } from 'next/cache';
revalidateTag('products'); // regenerates all pages with this tag
```

## ETag and conditional requests

```txt
ETag — a "fingerprint" of the resource version (content hash).
The browser stores the ETag and sends it on the next request.
The server compares: match → 304 Not Modified (no body),
no match → 200 with new content.

First request:
  Client → GET /api/articles
  Server → 200 OK
           ETag: "abc123"
           Cache-Control: no-cache
           [body: 50KB]

Subsequent request:
  Client → GET /api/articles
           If-None-Match: "abc123"
  Server → 304 Not Modified (if data hasn't changed)
           [body: 0 bytes] ← bandwidth saved

  Or:    → 200 OK
           ETag: "def456"
           [new body: 50KB]
```

```ts
// ETag implementation in Express
import crypto from 'crypto';

app.get('/api/articles', async (req, res) => {
  const articles = await db.article.findMany();
  const body = JSON.stringify(articles);
  const etag = crypto.createHash('md5').update(body).digest('hex');

  // Client sent If-None-Match — check it
  if (req.headers['if-none-match'] === `"${etag}"`) {
    return res.status(304).end();
  }

  res.setHeader('ETag', `"${etag}"`);
  res.setHeader('Cache-Control', 'no-cache');
  res.json(articles);
});
```

```ts
// Last-Modified — alternative to ETag (for static files)
// Browser sends: If-Modified-Since: <date>
// Server: 304 if unchanged, 200 if changed

// Express handles this automatically for static files:
app.use(express.static('public')); // Last-Modified from fs.stat()
```

## stale-while-revalidate — freshness without waiting

`stale-while-revalidate` answers the question "how to get fresh data without waiting for it":

```txt
Regular no-cache:
  Request → wait for server → receive → display
  = delay EVERY TIME

stale-while-revalidate:
  Request → immediately serve from cache (stale data)
           → simultaneously fetch from server
           → update cache
  = 0ms delay, fresh data on the next request
```

```ts
// HTTP header: stale-while-revalidate
res.setHeader(
  'Cache-Control',
  // max-age: cache is "fresh" for 60s (serve without server request)
  // stale-while-revalidate: for another 3600s — serve stale,
  //   but SIMULTANEOUSLY revalidate in the background
  'public, max-age=60, stale-while-revalidate=3600'
);
```

```ts
// SWR (stale-while-revalidate) — React library
import useSWR from 'swr';

function ArticleList() {
  const { data, error, isLoading } = useSWR(
    '/api/articles',
    fetcher,
    {
      // Always shows cached data instantly,
      // revalidates in the background
      revalidateOnFocus: true,     // revalidate when tab gets focus
      revalidateOnReconnect: true,  // revalidate after reconnect
      refreshInterval: 30_000,      // auto-refresh every 30 seconds
      dedupingInterval: 2_000,      // deduplicate: one request per 2s
    }
  );

  // data — always available (from cache), even while revalidating
  if (error) return <Error />;
  return <ArticleGrid articles={data} isUpdating={isLoading} />;
}
```

```ts
// TanStack Query — more powerful SWR alternative
import { useQuery, useQueryClient } from '@tanstack/react-query';

function ArticleList() {
  const { data, isStale } = useQuery({
    queryKey: ['articles'],
    queryFn: () => fetch('/api/articles').then(r => r.json()),
    staleTime: 60_000,  // data is "fresh" for 60 seconds
    gcTime: 5 * 60_000, // keep in memory 5 minutes after unmount
  });

  return <ArticleGrid articles={data} />;
}

// Manual invalidation (e.g. after a mutation)
const queryClient = useQueryClient();
await queryClient.invalidateQueries({ queryKey: ['articles'] });
```

## CDN Caching

### How CDN solves the caching problem

```txt
Without CDN:
  User (Tokyo) → Server (Virginia) = 150ms RTT × 2 = 300ms

With CDN (Cloudflare, CloudFront, Fastly):
  User (Tokyo) → CDN Edge (Tokyo) = 5–10ms RTT
  CDN Edge checks its cache:
    Hit  → responds immediately (5–10ms)
    Miss → fetches from Origin server (300ms), caches response
           subsequent requests → hit again (5–10ms)
```

```ts
// s-maxage — for CDN (overrides max-age for shared caches)
res.setHeader(
  'Cache-Control',
  // Browser caches for 5 minutes
  // CDN caches for 1 hour
  'public, max-age=300, s-maxage=3600'
);

// CDN-specific headers (Cloudflare):
res.setHeader('Cloudflare-CDN-Cache-Control', 's-maxage=86400');

// Surrogate-Control (Fastly, Varnish):
res.setHeader('Surrogate-Control', 'max-age=86400');
```

### Cache invalidation on CDN

```ts
// CloudFront (AWS) — invalidation via API
import { CloudFrontClient, CreateInvalidationCommand } from '@aws-sdk/client-cloudfront';

const client = new CloudFrontClient({ region: 'us-east-1' });

async function invalidateCDNPaths(paths: string[]) {
  await client.send(new CreateInvalidationCommand({
    DistributionId: process.env.CLOUDFRONT_DISTRIBUTION_ID!,
    InvalidationBatch: {
      CallerReference: Date.now().toString(),
      Paths: {
        Quantity: paths.length,
        Items: paths, // ['/', '/articles/*', '/static/hero.jpg']
      },
    },
  }));
}

// Call on deploy:
await invalidateCDNPaths(['/*']); // invalidate everything
// or selectively:
await invalidateCDNPaths(['/articles/*', '/']);
```

```ts
// Cloudflare — invalidation via API
async function purgeCloudflareCache(urls: string[]) {
  await fetch(
    `https://api.cloudflare.com/client/v4/zones/${process.env.CF_ZONE_ID}/purge_cache`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${process.env.CF_API_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ files: urls }),
    }
  );
}
```

### Cache Stampede (thundering herd) — and how to handle it

```txt
Problem: cache expires → 10,000 users simultaneously
request the resource → 10,000 requests to origin → origin crashes

Solutions:

1. stale-while-revalidate — only one background request,
   everyone else gets stale

2. Probabilistic Early Expiration (PER):
   Start revalidating early, randomly, before the cache expires
   (XFetch algorithm)

3. Lock/mutex: the first request "acquires a lock,"
   others wait or get stale
```

```ts
// Simple Redis mutex to prevent stampede
import { Redis } from 'ioredis';

const redis = new Redis(process.env.REDIS_URL!);

async function getCachedWithLock<T>(
  key: string,
  ttl: number,
  fetchFn: () => Promise<T>
): Promise<T> {
  // Try to get from cache
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached);

  // Acquire lock (SET NX = only if not exists)
  const lockKey = `lock:${key}`;
  const locked = await redis.set(lockKey, '1', 'EX', 10, 'NX');

  if (!locked) {
    // Another process is already fetching — wait and retry
    await new Promise(r => setTimeout(r, 100));
    return getCachedWithLock(key, ttl, fetchFn);
  }

  try {
    const data = await fetchFn();
    await redis.setex(key, ttl, JSON.stringify(data));
    return data;
  } finally {
    await redis.del(lockKey);
  }
}
```

## Service Workers — full control over the cache

A Service Worker is a JS file running in a separate thread that intercepts all network requests from the page.

### Service Worker caching strategies

```ts
// sw.ts — caching strategies

// 1. Cache First (Offline First)
// Check cache first, then network. Ideal for static assets.
async function cacheFirst(request: Request): Promise<Response> {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  const cache = await caches.open('static-v1');
  cache.put(request, response.clone()); // clone — body can only be read once
  return response;
}

// 2. Network First
// Try network first, fall back to cache on error.
// For APIs with frequent updates.
async function networkFirst(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);
    const cache = await caches.open('api-v1');
    cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw new Error('Network error and no cache available');
  }
}

// 3. Stale While Revalidate
// Instant cache response + background update.
async function staleWhileRevalidate(request: Request): Promise<Response> {
  const cache = await caches.open('dynamic-v1');
  const cached = await cache.match(request);

  // Background update (no await — don't block the response)
  const fetchAndUpdate = fetch(request).then(response => {
    cache.put(request, response.clone());
    return response;
  });

  return cached ?? fetchAndUpdate; // cache if available, else wait for network
}

// 4. Cache Only — only for resources pre-cached during SW install
async function cacheOnly(request: Request): Promise<Response> {
  const cached = await caches.match(request);
  if (!cached) throw new Error(`Not in cache: ${request.url}`);
  return cached;
}

// 5. Network Only — no caching (analytics, POST requests)
async function networkOnly(request: Request): Promise<Response> {
  return fetch(request);
}
```

```ts
// Full Service Worker with strategy routing
self.addEventListener('fetch', (event: FetchEvent) => {
  const { request } = event;
  const url = new URL(request.url);

  // Hashed static assets → Cache First (cache forever)
  if (url.pathname.startsWith('/_next/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // API → Network First (fresh data, cache fallback)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // HTML pages → Network First (always current HTML)
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  // Everything else → Stale While Revalidate
  event.respondWith(staleWhileRevalidate(request));
});
```

### Workbox — abstraction over the Cache API

```ts
// workbox-config.js — used with next-pwa or @ducanh2912/next-pwa
import { registerRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';

// Next.js static assets — forever
registerRoute(
  ({ url }) => url.pathname.startsWith('/_next/static/'),
  new CacheFirst({
    cacheName: 'next-static',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxAgeSeconds: 365 * 24 * 60 * 60 }),
    ],
  })
);

// Images — Cache First, but no more than 30 days
registerRoute(
  ({ request }) => request.destination === 'image',
  new CacheFirst({
    cacheName: 'images',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 100,                    // max 100 images
        maxAgeSeconds: 30 * 24 * 60 * 60,  // 30 days
      }),
    ],
  })
);

// API — Stale While Revalidate
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new StaleWhileRevalidate({
    cacheName: 'api-cache',
    plugins: [
      new ExpirationPlugin({ maxAgeSeconds: 60 * 60 }), // 1 hour
    ],
  })
);
```

## Cache-busting strategy on deploy

```txt
The deploy problem:
  You deploy a new version of HTML + JS.
  HTML updated (no-cache → browser re-fetched it).
  JS is old (max-age=1year, browser doesn't know it changed).
  Result: new HTML with a new API contract +
          old JS → runtime errors.

Solution — content-addressable filenames:
  The filename contains a hash of the content.
  Content changed → filename changed → cache miss.
  Content unchanged → filename unchanged → cache hit.

  main.abc123.js → main.def456.js (new version)

Webpack/Vite/Next.js do this automatically.
Your job: ensure HTML is not cached aggressively
(no-cache or a short max-age).
```

```ts
// Vite — content hash in filenames
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name].[hash].js',
        chunkFileNames: 'assets/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash].[ext]',
      },
    },
  },
});
```

## DevTools workflow for caching

```txt
Chrome DevTools → Network tab:

  "Status" column:
    200          — fresh response from server
    304          — Not Modified (conditional request, cache valid)
    "(disk cache)"   — from HTTP disk cache
    "(memory cache)" — from memory cache

  Important: when testing caching, ALWAYS
  uncheck "Disable cache" in DevTools!
  (it sends Cache-Control: no-cache on every request)

  Right-click → Copy → Copy as fetch:
  → copies the request with real headers for reproduction

Chrome DevTools → Application tab:
  → Storage → Cache Storage: Service Worker cache contents
  → Service Workers: SW status, unregister, bypass for network

  "Update on reload" in Service Workers:
  → forces SW update on page reload (for development)

curl for header diagnostics (no browser effects):
  curl -I https://example.com/api/articles
  curl -I -H 'If-None-Match: "abc123"' https://example.com/api/articles
```

## Connection to other topics

```txt
[Performance Metrics]     — CDN cache directly reduces TTFB;
                            Service Worker cache = instant FCP
                            on repeat visits
[Core Web Vitals]         — repeat-visit LCP depends on image
                            and JS cache; Cache-Control strategy
                            for HTML affects LCP
[Resource Loading]        — prefetch saves to HTTP cache;
                            Service Worker cache intercepts
                            prefetched resources
[JavaScript Performance]  — vendor chunk cached separately from
                            app chunk; content hash = effective
                            cache busting without manual invalidation
```

## Common interview traps

- **"no-cache means don't cache"** — a critical misconception. `no-cache` means "you may cache it, but you must validate before using it." If the ETag matches, the browser serves from cache (304). The directive that means "don't cache at all" is `no-store`.

- **"max-age=31536000 for everything — maximum performance"** — not for HTML documents. After a deploy, users would see the old version for a full year. The rule: large `max-age` only for resources with a content hash in their filename.

- **"Service Worker cache is the same as HTTP cache"** — they're different mechanisms. HTTP cache (disk cache) is controlled by the browser via headers. Service Worker Cache API is controlled by your code. SW cache lives longer, is more programmable, but requires explicit management of stale versions.

- **"CDN caching works automatically"** — not without the right `Cache-Control`. If the server responds with `Cache-Control: private` or `no-store`, the CDN caches nothing. `public, s-maxage=3600` is the right directive for CDN caching.

- **"stale-while-revalidate is the same as max-age"** — different models. `max-age` says "cache is fresh until this point, then wait for the server." `stale-while-revalidate` says "after max-age, serve stale and revalidate in the background." The user doesn't wait — they get stale data instantly.

- **"There are no caching problems if I use React Query"** — React Query caches data in memory (not in HTTP cache, not in Service Worker). Page refresh — all data is gone. HTTP Cache-Control headers and Service Workers are different layers of caching that work together, not as replacements for each other.

- **"Cache invalidation is simple — just bump the version"** — this is one of the "two hard problems in CS." The challenges: when to invalidate (not too early, not too late), how to invalidate related resources (article changed → invalidate article list, article page, API response), how to avoid cache stampede when a popular resource is invalidated.
