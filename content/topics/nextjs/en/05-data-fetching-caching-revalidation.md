# Data Fetching, Caching, and Revalidation

## Four caching layers in Next.js — must-know for senior interviews

One of the most common senior-level questions is "how many caching layers does Next.js have, and what's the difference". Most candidates only know about the `fetch` cache, but the App Router actually has **four**, and they work independently:

```txt
1. Request Memoization  — deduplicates identical fetch() calls within a SINGLE render
                           (lives only for the duration of that render, then discarded)

2. Data Cache           — a persistent cache of fetch() results across requests
                           and (with persistent storage) across deployments

3. Full Route Cache     — a cache of the rendered HTML + RSC payload for static routes,
                           built at build time or on first request

4. Router Cache         — a client-side, in-memory, per-session cache used for
                           navigation between already-visited routes
```

Confusion in interviews almost always comes from a candidate answering only about the Data Cache when the question is actually about the Full Route Cache (or vice versa) — these are different layers with different invalidation mechanisms.

## 1. Request Memoization

If several components independently call `fetch()` with the same URL and options during a single tree render, React/Next performs **one** real HTTP request, and the other calls get the same result from memory:

```tsx
// app/layout.tsx
async function getUser() {
  const res = await fetch('https://api.example.com/me');
  return res.json();
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const user = await getUser(); // request #1
  return <html><body><Header user={user} />{children}</body></html>;
}

// app/dashboard/page.tsx
async function getUser() {
  const res = await fetch('https://api.example.com/me');
  return res.json();
}

export default async function DashboardPage() {
  const user = await getUser(); // same URL — NOT a new request, served from memory
  return <Profile user={user} />;
}
```

This only works for `fetch` (and `React.cache`-wrapped functions for other data sources, e.g. direct DB queries) and **only within a single server-side render** — memory isn't shared across different users' requests. It solves the "N components — N identical requests" problem, but it's not a replacement for a persistent cache.

## 2. Data Cache — caching fetch results across requests

This is usually what people mean by "Next.js caches fetch". Unlike Request Memoization, the Data Cache **survives separate user requests** (and in some setups, deployments, if persistent storage is configured).

### A major change in Next.js 15

```txt
Next.js 13/14: fetch() defaults to → cache: 'force-cache' (cached)
Next.js 15:    fetch() defaults to → cache: 'no-store'    (not cached)
```

This is one of the most discussed breaking changes in Next.js history — many projects that upgraded to v15 unexpectedly got SSR-like behavior where they previously had SSG, because they never explicitly set `cache`. In an interview, it's not enough to know the fact — explain the motivation: the Next team concluded that "silent" caching by default was a root cause of many production bugs around stale data, and made the behavior explicit.

```ts
// SSG-like behavior: result is cached indefinitely (until explicitly invalidated)
fetch('https://api.example.com/products', { cache: 'force-cache' });

// SSR-like behavior: a fresh request on every render
fetch('https://api.example.com/products', { cache: 'no-store' });

// ISR-like behavior: cached for 60 seconds, then background regeneration
fetch('https://api.example.com/products', { next: { revalidate: 60 } });
```

### Caching non-fetch data sources

`fetch` isn't the only way to load data, and the Data Cache only works with it out of the box. For arbitrary async functions (e.g. queries via Prisma), use `unstable_cache`:

```ts
import { unstable_cache } from 'next/cache';

export const getProducts = unstable_cache(
  async () => db.product.findMany(),
  ['products'],                 // key parts
  { revalidate: 60, tags: ['products'] },
);
```

## 3. Full Route Cache

This caches the **result of rendering an entire route** — the HTML and RSC payload generated at build time (for static routes) or on the first request (for routes generated on demand). This is what physically lives on a CDN/edge and is served without running server code.

A route enters the Full Route Cache if it's **fully static** — i.e. it doesn't use:

```txt
cookies()
headers()
searchParams (in a Server Component)
fetch with cache: 'no-store'
export const dynamic = 'force-dynamic'
```

Using any of these marks the route as **dynamic**, and the Full Route Cache doesn't apply — every request is rendered fresh (though the Data Cache inside it can still be in effect).

```tsx
// This segment will NOT enter the Full Route Cache,
// even if every fetch inside it is cached via the Data Cache
export default async function Page() {
  const session = cookies().get('session'); // → dynamic rendering
  const products = await fetch(url, { cache: 'force-cache' }); // Data Cache still applies
  ...
}
```

## 4. Router Cache (Client-Side Router Cache)

A client-side, in-memory cache of RSC payloads for routes the user has already visited in the current session. It's why back/forward navigation between visited pages is instant, with no server round trip. This cache lives in browser memory and is cleared on a full page reload.

## Revalidation: path vs. tag, and the difference between them

```ts
// app/api/revalidate/route.ts
import { revalidatePath, revalidateTag } from 'next/cache';

export async function POST(request: Request) {
  const { type, value } = await request.json();

  if (type === 'path') {
    revalidatePath('/blog'); // invalidates the Full Route Cache for a specific path
  } else {
    revalidateTag('posts'); // invalidates ALL fetch calls tagged 'posts',
                             // on any route where it was used
  }

  return Response.json({ revalidated: true, now: Date.now() });
}
```

- `revalidatePath('/blog')` — targets the cached render of a specific route (and optionally its child segments).
- `revalidateTag('posts')` — clears the Data Cache for *all* `fetch` calls tagged `posts`, regardless of which route they ran on. This is useful when the same resource is used on multiple pages (e.g. a list of posts on the home page and on the blog page).

A typical scenario — a CMS webhook on article publish:

```ts
// A content editor publishes an article in Strapi/Contentful
// → a webhook calls /api/revalidate with the tag 'posts'
// → every page whose fetch was tagged tags: ['posts'] becomes stale
// → the next request to them triggers background regeneration (ISR semantics)
```

## generateStaticParams — the getStaticPaths equivalent

```tsx
// app/blog/[slug]/page.tsx
export async function generateStaticParams() {
  const posts = await getAllPosts();
  return posts.map((post) => ({ slug: post.slug }));
}

export default async function BlogPost({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug);
  return <Article post={post} />;
}
```

Nuance: for paths not returned by `generateStaticParams`, behavior depends on `export const dynamicParams` (defaults to `true`) — Next generates the page on demand on first request and caches the result (the equivalent of `fallback: 'blocking'` from the Pages Router). With `dynamicParams = false`, requesting a non-existent path returns a 404.

## What makes a route "dynamic" — the full list of triggers

```txt
cookies(), headers()              — access to request-specific data
searchParams in a Server Component — query params differ between requests
fetch(..., { cache: 'no-store' })
fetch(..., { next: { revalidate: 0 } })
export const dynamic = 'force-dynamic'
export const fetchCache = 'force-no-store'
```

Any of these "bubbles up" through the layout tree — if even one segment on a route is dynamic, the whole route renders dynamically (though static parts of the layout can still use their own Data Cache).

## Practical example: an e-commerce product page

```tsx
// app/products/[id]/page.tsx

// The catalog is large — don't generate every page at build time,
// but pre-generate popular ones
export async function generateStaticParams() {
  const popular = await getPopularProductIds();
  return popular.map((id) => ({ id }));
}

export default async function ProductPage({ params }: { params: { id: string } }) {
  // Product info changes rarely — ISR with a tag for on-demand invalidation
  const product = await fetch(`https://api.example.com/products/${params.id}`, {
    next: { revalidate: 3600, tags: [`product-${params.id}`] },
  }).then((r) => r.json());

  // Price/stock is near-real-time — a separate dynamic fetch
  const stock = await fetch(`https://api.example.com/stock/${params.id}`, {
    cache: 'no-store',
  }).then((r) => r.json());

  return <ProductView product={product} stock={stock} />;
}
```

This deliberately combines three models on a single page: statically pre-generated popular products (SSG), a long ISR cache for rarely-changing product info, and a dynamic fetch for stock levels. This is the "granular" approach that distinguishes the App Router from the Pages Router's "one page — one rendering strategy" model.

## Common interview mistakes

- **"fetch in Next.js is cached by default"** — true for Next.js 13/14, false for Next.js 15 (the default became `no-store`). A good answer shows you know *which version* you're talking about and why it changed.

- **Confusing the Data Cache with the Full Route Cache** — e.g. saying "I set `revalidate: 60` on my fetch, but the page still renders dynamically because of `cookies()`". That's expected: the Data Cache works independently of the Full Route Cache, but `cookies()` makes the route dynamic at the Full Route Cache level regardless.

- **"revalidateTag and revalidatePath are the same thing, just different arguments"** — no: `revalidatePath` targets a specific route (and its Full Route Cache), while `revalidateTag` targets data across the whole app, regardless of which routes use it.

- **Not knowing about Request Memoization** — and as a result either manually "lifting" fetches to the top level and threading data through props (killing colocation), or assuming N calls to the same `fetch` in the tree means N HTTP requests.

- **"unstable_cache is an unstable experimental feature that can't be used in production"** — the `unstable_` prefix historically signals the API may change in future versions, not that it's "broken" or unsuitable for production. It's the standard way to cache non-fetch data sources.

- **Can't list what makes a route dynamic** — this is one of the most practical skills: being able to look at code and predict whether a page lands in the Full Route Cache or renders on every request.
