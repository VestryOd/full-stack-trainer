# Data Fetching, Caching, and Revalidation

## The four caching layers in Next.js

The App Router has **four** caching layers, and each one works independently of the others:

```txt
1. Request Memoization  — deduplicates identical fetch() calls
                          within a SINGLE render
                          (only for that render, then discarded)

2. Data Cache           — a persistent cache of fetch() results
                          across requests, and across deployments
                          when persistent storage is set up

3. Full Route Cache     — a cache of the rendered HTML + RSC payload
                          for static routes, built at build time
                          or on the first request

4. Router Cache         — a client-side in-memory cache, per session
                          for navigation between visited routes
```

Most candidates know only about the `fetch` cache. That is why interviewers like the question "how many caching layers are there, and what is the difference". Confusion almost always comes from answering about the Data Cache when the question is about the Full Route Cache, or the other way round. These are different layers with different invalidation mechanisms.

## 1. Request Memoization

Several components can call `fetch()` with the same URL and options during a single tree render. React and Next then perform **one** real HTTP request, and the other calls get the same result from memory:

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

This only works for `fetch`, and **only within a single server-side render**. For other data sources — direct database queries, for example — wrap the function in `React.cache`. Memory is never shared across different users' requests. It solves the "N components — N identical requests" problem, but it is not a replacement for a persistent cache.

## 2. Data Cache — caching fetch results across requests

This is usually what people mean by "Next.js caches fetch". Unlike Request Memoization, the Data Cache **survives separate user requests** (and in some setups, deployments, if persistent storage is configured).

### A major change in Next.js 15

```txt
Next.js 13/14: fetch() cached by default  → cache: 'force-cache'
Next.js 15+:   caching is opt-in          → default: 'auto no cache'
```

This is one of the most discussed breaking changes in Next.js history. In Next.js 15 caching became **opt-in**: you turn it on with `cache: 'force-cache'` or with `next: { revalidate }`.

The default is not `no-store`, and the difference matters. Under the default (`auto no cache`) a static route still fetches once during `next build` and serves the prerendered result. The `no-store` value is an explicit opt-out: it fetches on every request and makes the route dynamic.

Many projects that upgraded to v15 suddenly rendered on every request — server-side rendering (SSR) where they previously had static generation (SSG). The reason: they never set `cache` explicitly.

Knowing the fact is not enough in an interview; explain the motivation too. The Next team concluded that "silent" caching by default caused many production bugs with stale data, so it made the behavior explicit.

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

This caches the **result of rendering an entire route**: the HTML and the RSC (React Server Component) payload. They are generated at build time for static routes, or on the first request for routes generated on demand. This is what physically lives on a CDN (content delivery network) or edge node, and it is served without running any server code.

A route enters the Full Route Cache if it's **fully static** — i.e. it doesn't use:

```txt
cookies()
headers()
searchParams (in a Server Component)
fetch with cache: 'no-store'
export const dynamic = 'force-dynamic'
```

Using any of these marks the route as **dynamic**, so the Full Route Cache doesn't apply. Every request is rendered fresh. The Data Cache inside that render can still be in effect.

```tsx
// This segment will NOT enter the Full Route Cache,
// even if every fetch inside it is cached via the Data Cache
import { cookies } from 'next/headers';

export default async function Page() {
  const cookieStore = await cookies(); // Next.js 15: cookies() is async
  const session = cookieStore.get('session'); // any cookie read → dynamic

  const products = await fetch('https://api.example.com/products', {
    cache: 'force-cache', // the Data Cache still applies in a dynamic route
  }).then((r) => r.json());

  return <ProductList products={products} session={session} />;
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
- `revalidateTag('posts')` — clears the Data Cache for *all* `fetch` calls tagged `posts`, regardless of which route they ran on. This is useful when the same resource appears on several pages — the post list on the home page and on the blog page.

A typical scenario — a webhook from the CMS (content management system) when an article is published:

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

export default async function BlogPost({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; // Next.js 15: params is async
  const post = await getPost(slug);
  return <Article post={post} />;
}
```

Nuance: for paths not returned by `generateStaticParams`, behavior depends on `export const dynamicParams`, which defaults to `true`. Next then generates the page on demand on the first request and caches the result. That is the equivalent of `fallback: 'blocking'` from the Pages Router. With `dynamicParams = false`, a request to an unknown path returns a 404.

## What makes a route "dynamic" — the full list of triggers

```txt
cookies(), headers()               — request-specific data
searchParams in a Server Component — query params vary per request
fetch(..., { cache: 'no-store' })
fetch(..., { next: { revalidate: 0 } })
export const dynamic = 'force-dynamic'
export const fetchCache = 'force-no-store'
```

Any of these "bubbles up" through the layout tree. If even one segment on a route is dynamic, the whole route renders dynamically. Static parts of the layout can still use their own Data Cache.

## Practical example: an e-commerce product page

```tsx
// app/products/[id]/page.tsx

// The catalog is large — don't generate every page at build time,
// but pre-generate popular ones
export async function generateStaticParams() {
  const popular = await getPopularProductIds();
  return popular.map((id) => ({ id }));
}

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; // Next.js 15: params is async

  // Product info changes rarely — ISR with a tag for on-demand invalidation
  const product = await fetch(`https://api.example.com/products/${id}`, {
    next: { revalidate: 3600, tags: [`product-${id}`] },
  }).then((r) => r.json());

  // Price/stock is near-real-time — a separate dynamic fetch
  const stock = await fetch(`https://api.example.com/stock/${id}`, {
    cache: 'no-store',
  }).then((r) => r.json());

  return <ProductView product={product} stock={stock} />;
}
```

This deliberately combines three models on a single page. Popular products are pre-generated statically (SSG). Product info sits in a long ISR (incremental static regeneration) cache. Stock levels come from a dynamic fetch.

This is the "granular" approach that distinguishes the App Router from the Pages Router, where one page means one rendering strategy.

## Common interview mistakes

- **"fetch in Next.js is cached by default"** — true for Next.js 13/14. From Next.js 15 caching is opt-in: the default is `auto no cache`, and you enable caching with `cache: 'force-cache'`. A good answer shows you know *which version* you are talking about, and that the default is not the same as `no-store`.

- **Confusing the Data Cache with the Full Route Cache** — these are separate layers. A typical complaint: "I set `revalidate: 60` on my fetch, but the page still renders dynamically because of `cookies()`". That's expected: `cookies()` makes the route dynamic at the Full Route Cache level, no matter what the Data Cache does.

- **"revalidateTag and revalidatePath are the same thing, just different arguments"** — no. The function `revalidatePath` targets a specific route and its Full Route Cache. Meanwhile `revalidateTag` targets data across the whole app, regardless of which routes use it.

- **Not knowing about Request Memoization** — this leads to two habits. Either you "lift" fetches to the top level by hand and thread data through props, which kills colocation. Or you assume that N calls to the same `fetch` in the tree mean N HTTP requests.

- **"unstable_cache is an unstable experimental feature that can't be used in production"** — the `unstable_` prefix historically signals that the API may change in future versions. It does not mean the function is "broken" or unsuitable for production. In Next.js 15 it is the standard way to cache data sources other than `fetch`.

- **Can't list what makes a route dynamic** — this is one of the most practical skills. You look at the code and predict whether a page lands in the Full Route Cache or renders on every request.
