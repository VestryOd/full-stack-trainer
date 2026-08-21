# Rendering Models: CSR, SSR, SSG, ISR

The four models in the title are CSR (client-side rendering), SSR (server-side rendering), SSG (static site generation) and ISR (incremental static regeneration).

## What a "rendering model" actually is

Rendering is the process of turning a React tree into HTML. The rendering model answers two questions:

```txt
Where is the HTML created?  — on the server, on a CDN at build
                              time, or in the browser
When is the HTML created?   — on every request, once at build time,
                              or periodically via revalidation
```

In the App Router (Next.js 13+) the model is no longer chosen "for the whole app". It's chosen *granularly*, per route segment: through `fetch` options and exported config (`export const dynamic`, `export const revalidate`). That's a key difference from the Pages Router, where the model was chosen per page by an exported function — `getServerSideProps`, `getStaticProps`, or neither.

## CSR — Client Side Rendering

The classic single-page application (SPA) model: the server sends minimal HTML, and JS in the browser builds the rest.

```txt
Browser
 ↓
download HTML (nearly empty) + JS bundle
 ↓
execute React, mount
 ↓
fetch data (useEffect / react-query / SWR)
 ↓
re-render with data
```

```tsx
'use client';

import { useEffect, useState } from 'react';

export function UserDashboard() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    fetch('/api/me').then((res) => res.json()).then(setUser);
  }, []);

  if (!user) return <Spinner />;
  return <Profile user={user} />;
}
```

**Pros**: minimal server load — the server just hands out static assets. And the experience *after* the initial load is great: transitions between states are instant, with no server round trip.

**Cons**: the HTML is empty until JS runs. That hurts search engine optimization (SEO) and paint metrics — FCP (first contentful paint) and LCP (largest contentful paint). Fetching data inside `useEffect` also creates *request waterfalls*: a component mounts first, then fetches, then renders children that may fetch again.

In the App Router, CSR happens through Client Components (`'use client'`). It is a deliberate choice for interactive pieces of the interface — forms, dropdowns, charts — not the default model for entire pages.

## SSR — Server Side Rendering

HTML is generated on the server **on every request**.

```txt
Request → server renders React to HTML
        → HTML sent to browser → hydration
```

**In the Pages Router**, via `getServerSideProps`:

```ts
export async function getServerSideProps(context) {
  const data = await fetchUserData(context.params.id);
  return { props: { data } };
}
```

**In the App Router**, SSR is the *default* for a Server Component that reads dynamic data. Dynamic means `cookies()`, `headers()`, or a `fetch` with `cache: 'no-store'`:

```tsx
// app/profile/page.tsx
import { cookies } from 'next/headers';

export default async function ProfilePage() {
  const cookieStore = await cookies(); // Next.js 15: cookies() is async
  const sessionId = cookieStore.get('session')?.value;
  const user = await fetch(`https://api.example.com/me`, {
    headers: { Authorization: `Bearer ${sessionId}` },
    cache: 'no-store', // → forces SSR for this fetch
  }).then((r) => r.json());

  return <Profile user={user} />;
}
```

You can also force SSR for the whole segment:

```ts
export const dynamic = 'force-dynamic';
```

**Pros**: always-fresh data, great SEO (full HTML on every request), personalization (you can read cookies/headers before rendering).

**Cons**: server load scales with traffic. TTFB (time to first byte) is higher, because you wait for render plus fetch before the first byte goes out. And caching on a CDN (content delivery network) is harder — though Next can still cache SSR responses via `Cache-Control` and its Data Cache.

## SSG — Static Site Generation

HTML is generated **at build time**, once, before any user request.

```txt
Build time → HTML for every page → deployed to a CDN
           → users get static files
```

**In the Pages Router**: `getStaticProps` (+ `getStaticPaths` for dynamic routes).

**In the App Router**: a Server Component with no dynamic APIs and a `fetch` whose `cache` is `'force-cache'` (the default!). For dynamic routes, use `generateStaticParams`:

```tsx
// app/blog/[slug]/page.tsx
export async function generateStaticParams() {
  const posts = await getAllPostSlugs();
  return posts.map((post) => ({ slug: post.slug }));
}

export default async function BlogPost({ params }: { params: { slug: string } }) {
  const post = await fetch(`https://cms.example.com/posts/${params.slug}`)
    .then((r) => r.json()); // cache: 'force-cache' by default → SSG

  return <Article post={post} />;
}
```

**Pros**: maximum speed (static files served straight from a CDN, no Node.js involved per request), perfect cacheability, zero read load on the origin server.

**Cons**: data is "frozen" at build time — content updates require a rebuild (or ISR). For sites with thousands/millions of pages, `generateStaticParams` can make builds impractically long — that's where ISR with on-demand generation of missing pages comes in.

**When to use**: blogs, docs, marketing landing pages — anything where content changes rarely (hours/days).

## ISR — Incremental Static Regeneration

ISR is SSG that can "go stale" and regenerate without a full redeploy.

```txt
Request 1 (within TTL)
  → the cached page is served instantly
Request after TTL expires
  → the STALE page is served, regeneration runs in the background
Subsequent request
  → the new page is served
```

The key nuance: the user whose request "triggers" revalidation does **not** wait for the rebuild. They get the stale version, and the fresh one is cached for everyone after them. The pattern is called stale-while-revalidate.

**In the Pages Router**:

```ts
export async function getStaticProps() {
  const data = await fetchProducts();
  return {
    props: { data },
    revalidate: 60, // seconds
  };
}
```

**In the App Router** — the same thing via a `fetch` option:

```tsx
export default async function ProductsPage() {
  const products = await fetch('https://api.example.com/products', {
    next: { revalidate: 60 }, // ISR: page goes stale after 60s
  }).then((r) => r.json());

  return <ProductList products={products} />;
}
```

Or for the whole segment:

```ts
export const revalidate = 60;
```

Besides time-based revalidation there's **on-demand revalidation** — targeted invalidation by tag or path, e.g. after publishing an article in a CMS:

```ts
// app/api/revalidate/route.ts
import { revalidateTag } from 'next/cache';

export async function POST(request: Request) {
  const { tag } = await request.json();
  revalidateTag(tag); // instantly marks cached data with this tag as stale
  return Response.json({ revalidated: true });
}
```

```tsx
// tag the fetch so it can be targeted later
fetch('https://cms.example.com/posts', { next: { tags: ['posts'] } });
```

**When to use**: product catalogs, news sites, CMS content — data changes, but doesn't need to be fresh to the millisecond.

## Hydration and Hydration Mismatch

After SSR/SSG, the browser receives ready-made HTML — content is visible immediately, but **not interactive**: event handlers aren't wired up yet. Hydration is the process where React walks the existing tree of DOM (Document Object Model — the browser's tree of page nodes) nodes. It "attaches" its own virtual DOM and event handlers to that markup, *without* recreating it from scratch.

```txt
Server renders HTML
 ↓
Browser receives and shows HTML (visible but not interactive)
 ↓
JS bundle downloads and executes
 ↓
React reconciles the SSR markup against what it would render itself
 ↓
Hydration: event listeners attached → UI becomes interactive
```

A **Hydration Mismatch** happens when the HTML rendered on the server doesn't match what React renders on the client during the first render. React logs a warning and (in production) may overwrite the server markup with the client render — causing a visible content "flicker".

Typical causes:

```tsx
// 1. Using values that depend on the environment
function Clock() {
  return <span>{new Date().toLocaleTimeString()}</span>;
  // server: 10:00:00, client at hydration time: 10:00:02 → mismatch
}

// 2. Accessing browser-only APIs during render
function Banner() {
  // window is undefined on the server → server HTML differs from client HTML
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  return <div>{isMobile ? 'Mobile' : 'Desktop'}</div>;
}

// 3. Invalid HTML that the browser "fixes" itself
function Wrapper() {
  // <p> can't contain a <div> — the browser will break the tag while parsing,
  // so the resulting DOM tree won't match what React expects
  return <p><div>content</div></p>;
}
```

**Correct fixes**:

```tsx
// For values known only on the client — render after mount
function Clock() {
  const [time, setTime] = useState<string | null>(null);

  useEffect(() => {
    setTime(new Date().toLocaleTimeString());
  }, []);

  // null on the server and on the first client render — they match
  return <span>{time ?? '--:--:--'}</span>;
}

// Or explicitly tell React the mismatch is expected (use very sparingly)
<span suppressHydrationWarning>{new Date().toLocaleTimeString()}</span>
```

`suppressHydrationWarning` suppresses the warning only for that node's text/attribute content — it's not a blanket switch for hydration checks, and overusing it masks real bugs.

## Comparing the models

| Model | When HTML is created | TTFB | Data freshness | Cacheability |
|---|---|---|---|---|
| CSR | In the browser, after JS | Low (static) | Always fresh (client fetch) | Excellent (static) |
| SSR | On every request | High | Always fresh | Harder (per-request) |
| SSG | At build time | Low (CDN) | Fixed at build time | Perfect |
| ISR | Build + periodic regeneration | Low (CDN) | Configurable TTL (time to live) delay | Good |

## Choosing a model — practical scenarios

```txt
Blog / docs                    → SSG
Product catalog                → ISR (TTL revalidation, plus
                                 on-demand on product update)
Personal user dashboard        → SSR or CSR (session-bound data)
Landing / marketing page       → SSG
E-commerce product page        → ISR + on-demand revalidation
                                 after price/stock updates
Real-time data (markets, chat) → CSR + WebSocket/polling, or
                                 Server Components + streaming
```

Important: in the App Router you compose models instead of picking one for the whole app. A Layout can be static (SSG) while a Server Component nested inside it renders dynamic data via SSR. Wrap that component in `<Suspense>` and it streams as a separate chunk. Partial Prerendering is an experimental feature that pushes this idea even further.

## Common interview mistakes

- **"SSG means the server renders the HTML"** — no. SSG means the HTML is created *at build time*. At request time the server renders nothing at all, it just serves a pre-built file.

- **"ISR is just SSR with a cache"** — more precisely: ISR is SSG with a background regeneration mechanism. The user whose request triggers TTL-based revalidation gets the *old* version, not the new one.

- **Confusing `revalidate: 0` and `cache: 'no-store'`** — both "disable" the static cache, but they mean different things. The option `revalidate: 0` is still part of the ISR and Data Cache model: effectively "don't cache at all". A `no-store` fetch is explicit per-request SSR that bypasses the Data Cache entirely. In practice the outcomes are similar, but a strong answer shows you know the difference between the Full Route Cache and the Data Cache.

- **Treating hydration mismatch as "just a console warning, safe to ignore"** — in production it can visibly "repaint" content and lose state. A typical example: an input the user has already started typing into gets reset.

- **Can't explain why `Date.now()` or `Math.random()` directly in JSX is an anti-pattern** — the value is computed twice. It is computed once on the server (during SSR or SSG) and again on the client, during the first render before hydration. Those two values will almost certainly diverge.

- **Assuming the model is chosen once for the whole app** — in the App Router it is chosen per segment. Models also combine inside one page: a static layout, dynamic content, and streaming via Suspense.
