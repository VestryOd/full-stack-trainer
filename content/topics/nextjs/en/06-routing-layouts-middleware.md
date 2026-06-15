# Routing, Layouts, and Middleware

## File-system routing: basics and typing nuances

In the App Router, a route is defined by a *folder*, not a file — a `page.tsx` file inside a folder makes it accessible as a route. This distinction matters: you can create `app/blog/components/` with regular components, and it **won't** become a route because it has no `page.tsx`.

```txt
app/
 ├─ page.tsx              → /
 ├─ about/
 │   └─ page.tsx          → /about
 ├─ blog/
 │   ├─ page.tsx          → /blog
 │   └─ [id]/
 │       └─ page.tsx      → /blog/:id
```

### Dynamic Segments

```tsx
// app/blog/[id]/page.tsx
interface PageProps {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
}

export default async function BlogPost({ params, searchParams }: PageProps) {
  const post = await getPost(params.id);
  return <Article post={post} />;
}
```

`params.id` is always a `string` (or `string[]` for catch-all segments) — even if it's conceptually a number, Next doesn't coerce it. A common mistake is forgetting `Number(params.id)`/`parseInt` before passing it to a DB query that expects a numeric ID.

### Catch-all and Optional Catch-all

```txt
app/docs/[...slug]/page.tsx     → /docs/a, /docs/a/b, /docs/a/b/c
                                    does NOT match /docs (needs at least 1 segment)

app/docs/[[...slug]]/page.tsx   → /docs, /docs/a, /docs/a/b
                                    matches /docs too (slug will be undefined)
```

```tsx
// app/docs/[...slug]/page.tsx
export default function DocsPage({ params }: { params: { slug: string[] } }) {
  // /docs/react/hooks/useEffect → params.slug = ['react', 'hooks', 'useEffect']
  const path = params.slug.join('/');
  return <DocContent path={path} />;
}
```

A typical use case is CMS/docs sites, where an arbitrarily deep page tree is defined by an external data source rather than the file structure.

### Route Groups — organization without affecting the URL

```txt
app/
 ├─ (marketing)/
 │   ├─ layout.tsx        → a separate layout just for marketing pages
 │   ├─ page.tsx          → /
 │   └─ about/page.tsx    → /about
 ├─ (app)/
 │   ├─ layout.tsx        → a separate layout for the authenticated section
 │   └─ dashboard/page.tsx → /dashboard
```

Folders in parentheses, `(marketing)`, `(app)` — **don't appear in the URL**. This lets you have multiple independent "root-like" layouts (e.g. one with a public header, another with an authenticated sidebar) without nesting them inside each other.

### Parallel Routes and Intercepting Routes (advanced)

```txt
app/
 ├─ @modal/                  → a "slot" — a parallel segment
 │   └─ (.)photo/[id]/page.tsx  → intercepting route
 ├─ photo/[id]/page.tsx
 └─ layout.tsx
```

`@modal` is a named parallel slot, rendered independently of the main content via `layout.tsx`, which receives it as a separate prop:

```tsx
// app/layout.tsx
export default function Layout({
  children,
  modal,
}: {
  children: React.ReactNode;
  modal: React.ReactNode;
}) {
  return (
    <>
      {children}
      {modal}
    </>
  );
}
```

`(.)photo` is an *intercepting route*: when navigating client-side to `/photo/123` (e.g. by clicking from a feed), a modal opens with the photo *on top of* the current page, but when accessed directly via URL (refresh, shared link) or a server-side transition, the full `/photo/[id]` page renders. This is the classic "Instagram-style" photo modal pattern — senior-level interviews sometimes ask about it via the phrasing "how would you make a click open a modal, but a direct link to the same photo open a full page".

## Layout, Template, Loading, Error, Not Found — file conventions

```txt
app/dashboard/
 ├─ layout.tsx     → persistent UI shell, NOT remounted on navigation within the segment
 ├─ template.tsx   → like layout, but REMOUNTED on every navigation
 ├─ loading.tsx    → automatic <Suspense fallback>
 ├─ error.tsx      → automatic Error Boundary (Client Component)
 ├─ not-found.tsx  → rendered when notFound() is called or a catch-all path doesn't match
 └─ page.tsx       → route content
```

### Layout vs Template — when you actually need a Template

`layout.tsx` preserves state and the DOM across navigations between child routes — this is the App Router's main advantage (the sidebar doesn't flicker, scroll position isn't reset). But sometimes that behavior is **undesirable**:

```tsx
// app/blog/[slug]/template.tsx
'use client';

import { useEffect } from 'react';

export default function Template({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // Should fire on EVERY transition between articles,
    // even though the URL changes within the same segment
    analytics.trackPageView();
  }, []);

  return <>{children}</>;
}
```

If this were a `layout.tsx`, the `useEffect` would only fire on the segment's first mount, not on every transition between `/blog/post-1` and `/blog/post-2` (since the layout never unmounts). `template.tsx` solves exactly this class of problems: per-navigation effects, enter/exit CSS animations, resetting local form state between wizard steps.

### Nested Layouts — what exactly doesn't remount

```txt
Root Layout
 └─ Dashboard Layout
     └─ Settings Page
```

When navigating `/dashboard/settings/profile` → `/dashboard/settings/billing`:

```txt
Root Layout      — not remounted
Dashboard Layout — not remounted
Settings Layout  — not remounted (if it exists)
page.tsx         — replaced with new content
```

Next requests only the RSC payload for the changed segment from the server — shared layouts stay mounted in the React tree, so state (an open menu, scroll position inside the sidebar) isn't lost.

## Middleware

### Where it runs and why that matters

Middleware is code that runs **before** a request reaches Next.js routing, on the **Edge Runtime** (V8 isolates, not a full Node.js runtime). This gives low latency (middleware can run geographically close to the user), but imposes constraints:

```txt
Unavailable in middleware:
  fs, net, child_process, any Node-specific native modules
  Full ORMs (Prisma Client doesn't work on the Edge in its standard config)

Available:
  Web-standard APIs: fetch, Request, Response, URL, crypto (Web Crypto)
  Next-specific wrappers: NextRequest, NextResponse
```

### Basic example with a matcher

```ts
// middleware.ts — must be at the project root (or src/)
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('session')?.value;

  if (!token) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('from', request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/settings/:path*'],
};
```

`matcher` isn't just an "optimization" — it's a necessity: without it, middleware runs **for every request**, including static assets (`/_next/static/...`), adding unnecessary latency across the whole app.

### Redirect vs Rewrite — the difference people confuse most

```ts
// Redirect — the browser gets a 307/308, the URL in the address bar CHANGES
return NextResponse.redirect(new URL('/login', request.url));

// Rewrite — the request is handled by a different path "under the hood",
// the URL in the user's address bar STAYS the same
return NextResponse.rewrite(new URL('/internal/maintenance-page', request.url));
```

A practical rewrite example — A/B testing without changing the URL:

```ts
export function middleware(request: NextRequest) {
  const bucket = request.cookies.get('ab-bucket')?.value ?? (Math.random() < 0.5 ? 'a' : 'b');

  const response = bucket === 'b'
    ? NextResponse.rewrite(new URL('/home-variant-b', request.url))
    : NextResponse.next();

  response.cookies.set('ab-bucket', bucket, { maxAge: 60 * 60 * 24 * 30 });
  return response;
}
```

The user sees `/` in the address bar in both cases, but Next serves the content of different pages depending on the cookie — that's a rewrite in action.

### Geo and Localization

```ts
export function middleware(request: NextRequest) {
  const country = request.geo?.country ?? 'US'; // available on Vercel; self-hosted needs its own source
  const locale = country === 'DE' ? 'de' : country === 'FR' ? 'fr' : 'en';

  if (!request.nextUrl.pathname.startsWith(`/${locale}`)) {
    return NextResponse.redirect(new URL(`/${locale}${request.nextUrl.pathname}`, request.url));
  }
  return NextResponse.next();
}
```

### When middleware isn't the right choice

```txt
Good fit:
  - routing-level auth checks (does a token exist)
  - redirects and rewrites
  - modifying headers/cookies for all requests
  - geo/locale-based routing, A/B bucket assignment

Poor fit:
  - validating a token with a DB lookup on every request (Edge Runtime + DB latency
    on EVERY request, including static assets, if the matcher is too broad)
  - complex business logic — belongs in Route Handlers/Server Actions,
    which have a full Node.js runtime available
```

A common anti-pattern is validating a JWT with a DB check (e.g. "has this token been revoked") directly in middleware. It's technically possible via `fetch` to an external service, but adds a network round trip to *every* protected request. Heavier authorization logic is usually moved into the Route Handlers/Server Actions themselves, while middleware sticks to cheap checks (e.g. verifying a JWT signature without a DB lookup).

## Common interview mistakes

- **"params.id is a number if the URL has digits"** — no, `params` are always strings (or arrays of strings for catch-all), type coercion is the developer's responsibility.

- **Confusing `[...slug]` and `[[...slug]]`** — the first doesn't match the parent path with no segments (`/docs` gives a 404), the second does, and `slug` will be `undefined`.

- **"Route Groups affect the URL"** — no, `(marketing)`/`(app)` exist only to organize files and provide different layouts; they don't appear in the URL.

- **"layout.tsx and template.tsx are just synonyms"** — `layout` preserves state and the DOM across navigations within a segment, `template` is recreated on every navigation. The difference is critical for `useEffect`-based analytics or enter/exit animations.

- **"Middleware can do everything a Route Handler can"** — no, the Edge Runtime doesn't give access to Node APIs or most ORMs. Not knowing this is a common cause of "Prisma crashes in my middleware".

- **Forgetting `matcher`** — without it, middleware runs on every request, including `/_next/static/*`, `/favicon.ico`, etc., measurably increasing latency.

- **"Redirect and Rewrite are synonyms for 'send the user somewhere'"** — Redirect changes the URL in the browser (visible to the user and search engines), Rewrite doesn't. For SEO these are fundamentally different tools (redirect signals "content has moved", rewrite signals "this is the same resource, just a different internal implementation").
