# Caching Strategies

## Why caching is the most impactful optimization

Caching is the only optimization that can reduce load time **to zero**: a cached resource requires not a single byte of network traffic.

Every uncached request pays the full setup cost first: a domain-name lookup, a new connection, an encryption handshake. Only then comes the round trip to the server. That is 200–800ms even for a tiny file. A cached request skips all of it:

| Where the response comes from | Cost |
|---|---|
| Memory cache | effectively 0ms — under 1ms from memory |
| Disk cache | 2–10ms for the disk read |
| The CDN (content delivery network) node nearest the user | 10–50ms, one network round trip |

The browser looks in those places in a fixed order, fastest first:

1. Memory cache, while the tab is still open.
2. Service Worker cache.
3. HTTP disk cache.
4. Push cache, which comes from HTTP/2 and is short-lived.
5. The network, if nothing was found anywhere else.

## HTTP Cache-Control — the foundation

`Cache-Control` is the primary header. Its directives decide who may cache the response, for how long, and whether it has to be validated first.

### Cache-Control directives

| Directive | What it means |
|---|---|
| `max-age=N` | Cache for N seconds, counted from the time of the response. |
| `s-maxage=N` | The same, but only for shared caches such as a CDN or a proxy. It overrides `max-age` there. |
| `no-cache` | The response **may** be cached, but it **must** be validated before every use. It does not mean "do not cache". |
| `no-store` | Do not cache at all. This is the directive for sensitive data. |
| `public` | May be stored in a shared cache. |
| `private` | Only in the user's own browser, never in a shared cache. |
| `immutable` | The resource will never change, so do not validate it even on an explicit page refresh. |
| `must-revalidate` | Once `max-age` has expired, validate before serving. Do not serve stale even when the server errors. |
| `stale-while-revalidate=N` | Serve stale for up to N more seconds while revalidating in the background. |
| `stale-if-error=N` | Serve stale for up to N seconds if the server is unavailable. |

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

An ETag is a fingerprint of one version of a resource, usually a hash of its content. The browser stores it and sends it back on the next request. If the fingerprint on the server still matches, the server answers `304 Not Modified` with no body at all. If it does not match, the answer is `200` with the new content.

```txt
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

With a plain `no-cache`, the browser sends the request, waits for the server, gets the answer and only then shows it. That delay happens **every single time**.

With `stale-while-revalidate` the order changes. The cached copy is shown immediately, stale as it is. At the same time the browser fetches a fresh copy and updates the cache. The user waits 0ms, and the next request already gets fresh data.

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

Without a CDN, a user in Tokyo talks to a server in Virginia. That is about 150ms for the round trip alone, before the connection and encryption handshakes described above are added on top.

With a CDN such as Cloudflare, CloudFront or Fastly, the same user talks to an edge node in Tokyo, 5–10ms away. The edge node checks its own cache:

- **Hit** — it answers immediately, within those 5–10ms.
- **Miss** — it fetches from the origin server once, paying the 300ms, and caches the response. Every later request is a hit again.

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

The problem is a chain reaction. A cache entry expires, and 10,000 users ask for the resource at the same moment. That is 10,000 requests hitting the origin at once, and the origin falls over.

Three ways out:

1. **`stale-while-revalidate`** — only one background request goes to the origin, and everyone else is served stale.
2. **Probabilistic Early Expiration (PER)** — start revalidating early and at random, before the entry actually expires. The XFetch algorithm does exactly this.
3. **A lock or mutex** — the first request takes the lock, and the others either wait or get stale data.

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

The deploy problem looks like this. You ship a new version of the HTML and the JS. The HTML is served with `no-cache`, so the browser fetches it again. The JS still carries `max-age=1 year`, and the browser has no idea it changed. The result is new HTML talking to an old JS bundle over a new API contract, and runtime errors.

The fix is content-addressable filenames. The name carries a hash of the file's content, so `main.abc123.js` becomes `main.def456.js` when the content changes. Changed content means a changed name, which means a cache miss. Unchanged content keeps its name and stays a cache hit.

Webpack, Vite and Next.js all do this for you. Your part is making sure the HTML itself is not cached aggressively — `no-cache`, or a short `max-age`.

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

In the Chrome DevTools **Network** tab, the `Status` column tells you where each response came from:

- `200` — a fresh response from the server.
- `304` — Not Modified, so the conditional request confirmed the cache is still valid.
- `(disk cache)` — served from the HTTP disk cache.
- `(memory cache)` — served from the memory cache.

One thing trips everyone up: when you are testing caching, **uncheck** `Disable cache` in DevTools. While it is checked, every request goes out with `Cache-Control: no-cache`.

Right-click a request and choose Copy → Copy as fetch to reproduce it with its real headers.

In the **Application** tab, Storage → Cache Storage shows what the Service Worker has cached. The Service Workers section shows its status and lets you unregister the worker or bypass it for the network. `Update on reload` there forces an update on every page reload, which is what you want during development.

For header diagnostics with no browser behaviour in the way, use `curl`:

```bash
curl -I https://example.com/api/articles
curl -I -H 'If-None-Match: "abc123"' https://example.com/api/articles
```

## Connection to other topics

- [Performance Metrics](./02-performance-metrics.md) — a CDN cache directly reduces TTFB (time to first byte). A Service Worker cache gives an instant FCP (First Contentful Paint) on repeat visits.
- [Core Web Vitals](./01-core-web-vitals.md) — LCP (Largest Contentful Paint) on a repeat visit depends on the image and JS cache. The `Cache-Control` strategy for HTML affects it too.
- [Resource Loading](./03-resource-loading.md) — `prefetch` writes into the HTTP cache, and a Service Worker cache intercepts prefetched resources.
- [JavaScript Performance](./04-javascript-performance.md) — the vendor chunk is cached separately from the app chunk, and a content hash gives effective cache busting with no manual invalidation.

## Common interview traps

- **"no-cache means don't cache"** — a critical misconception. The directive actually says: you may cache this, but you must validate it before every use. If the ETag matches, the browser serves the copy it already has, with a 304. The directive that really means "do not cache at all" is `no-store`.

- **"max-age=31536000 for everything — maximum performance"** — not for HTML documents. After a deploy, users would see the old version for a full year. The rule: large `max-age` only for resources with a content hash in their filename.

- **"Service Worker cache is the same as HTTP cache"** — they're different mechanisms. HTTP cache (disk cache) is controlled by the browser via headers. Service Worker Cache API is controlled by your code. The Service Worker cache lives longer and is more programmable, but you have to manage stale versions yourself.

- **"CDN caching works automatically"** — not without the right `Cache-Control`. If the server responds with `Cache-Control: private` or `no-store`, the CDN caches nothing. `public, s-maxage=3600` is the right directive for CDN caching.

- **"stale-while-revalidate is the same as max-age"** — they are different models. With `max-age` the cache is fresh until a point in time, and after that the browser waits for the server. With `stale-while-revalidate` the browser serves the stale copy past that point and revalidates in the background. The user never waits: stale data arrives instantly.

- **"There are no caching problems if I use React Query"** — React Query caches data in memory (not in HTTP cache, not in Service Worker). Page refresh — all data is gone. HTTP Cache-Control headers and Service Workers are different layers of caching that work together, not as replacements for each other.

- **"Cache invalidation is simple — just bump the version"** — it is famously one of the two hard problems in computer science. Three things make it hard. Knowing *when* to invalidate, neither too early nor too late. Knowing *what else* to invalidate: an article changed, so the article list, the article page and the API response all go stale. And avoiding a cache stampede when a popular resource is invalidated.
