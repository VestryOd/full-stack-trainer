# Routing, Layouts, and Middleware

## File-system routing: basics and typing nuances

In the App Router, a route is defined by a *folder*, not a file. A folder becomes reachable as a route once it contains a `page.tsx`. This distinction matters: you can create `app/blog/components/` with regular components, and it **won't** become a route because it has no `page.tsx`.

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
// Next.js 15: params and searchParams are now Promises
export default async function BlogPost({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { id } = await params;
  const post = await getPost(id);
  return <Article post={post} />;
}
```

`id` (from `await params`) is always a `string`, or `string[]` for catch-all segments. Even if it is conceptually a number, Next doesn't coerce it. A common mistake is forgetting `Number(params.id)` or `parseInt` before passing the value to a DB (database) query that expects a numeric ID.

### Catch-all and Optional Catch-all

```txt
app/docs/[...slug]/page.tsx
  → /docs/a, /docs/a/b, /docs/a/b/c
  → /docs does NOT match (needs at least 1 segment)

app/docs/[[...slug]]/page.tsx
  → /docs, /docs/a, /docs/a/b
  → /docs matches too, and slug is undefined
```

```tsx
// app/docs/[...slug]/page.tsx
export default async function DocsPage({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const { slug } = await params; // Next.js 15: params is async
  // /docs/react/hooks/useEffect → slug = ['react', 'hooks', 'useEffect']
  const path = slug.join('/');
  return <DocContent path={path} />;
}
```

A typical use case is a docs site driven by a CMS (content management system). The page tree there can be arbitrarily deep, and its shape comes from an external data source rather than from the file structure.

### Route Groups — organization without affecting the URL

```txt
app/
 ├─ (marketing)/
 │   ├─ layout.tsx        → layout for marketing pages only
 │   ├─ page.tsx          → /
 │   └─ about/page.tsx    → /about
 ├─ (app)/
 │   ├─ layout.tsx        → layout for the signed-in area
 │   └─ dashboard/page.tsx → /dashboard
```

Folders in parentheses, `(marketing)`, `(app)` — **don't appear in the URL**. That lets you keep several independent "root-like" layouts side by side: one with a public header, another with a sidebar for signed-in users. Neither has to nest inside the other.

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

`(.)photo` is an *intercepting route*. Click a thumbnail in a feed and the client navigates to `/photo/123`. A modal opens with the photo *on top of* the current page. Open the same address directly, through a refresh or a shared link, and the full `/photo/[id]` page renders instead. A server-side transition behaves the same way.

This is the classic "Instagram-style" photo modal. Senior interviews sometimes ask for it in exactly this phrasing. How do you make a click open a modal, while a direct link to the same photo opens a full page?

## Layout, Template, Loading, Error, Not Found — file conventions

```txt
app/dashboard/
 ├─ layout.tsx     → shell; NOT remounted inside the segment
 ├─ template.tsx   → like layout, but REMOUNTED every navigation
 ├─ loading.tsx    → automatic <Suspense fallback>
 ├─ error.tsx      → automatic Error Boundary (Client Component)
 ├─ not-found.tsx  → shown on notFound() or unmatched catch-all
 └─ page.tsx       → route content
```

### Layout vs Template — when you actually need a Template

`layout.tsx` preserves state and the DOM (Document Object Model — the live tree of nodes the browser renders) across navigations between child routes. That is the App Router's main advantage: the sidebar doesn't flicker, and scroll position isn't reset. But sometimes that behavior is **undesirable**:

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

Put this same code in `layout.tsx` and the `useEffect` fires once, when the segment first mounts. It does not fire again when you move from `/blog/post-1` to `/blog/post-2`, because the layout never unmounts. The `template.tsx` file is for exactly this class of problem. Three examples: effects that must run on every navigation, enter/exit CSS animations, and resetting local form state between wizard steps.

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

Next asks the server for only one thing: the RSC payload (React Server Components payload — a serialized description of the changed segment). Shared layouts stay mounted in the React tree, so their state survives: an open menu, the scroll position inside the sidebar.

## Middleware

### Where it runs and why that matters

Middleware is code that runs **before** a request reaches Next.js routing, on the **Edge Runtime** (V8 isolates, not a full Node.js runtime). This gives low latency (middleware can run geographically close to the user), but imposes constraints:

```txt
Unavailable in middleware:
  fs, net, child_process, any Node-specific native modules
  Full ORMs (standard Prisma Client does not run on the Edge)

Available:
  Web-standard APIs: fetch, Request, Response, URL, Web Crypto
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

`matcher` isn't an "optimization", it's a necessity. Without it, middleware runs **for every request**, including static assets like `/_next/static/...`. That adds latency across the whole app for no benefit.

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
  const existing = request.cookies.get('ab-bucket')?.value;
  const bucket = existing ?? (Math.random() < 0.5 ? 'a' : 'b');

  const response = bucket === 'b'
    ? NextResponse.rewrite(new URL('/home-variant-b', request.url))
    : NextResponse.next();

  response.cookies.set('ab-bucket', bucket, { maxAge: 60 * 60 * 24 * 30 });
  return response;
}
```

The user sees `/` in the address bar either way. Next serves the content of a different page depending on the cookie — that's a rewrite in action.

### Geo and Localization

```ts
export function middleware(request: NextRequest) {
  // request.geo is filled in on Vercel; self-hosting needs its own source
  const country = request.geo?.country ?? 'US';
  const locale = country === 'DE' ? 'de' : country === 'FR' ? 'fr' : 'en';

  if (!request.nextUrl.pathname.startsWith(`/${locale}`)) {
    const target = new URL(`/${locale}${request.nextUrl.pathname}`, request.url);
    return NextResponse.redirect(target);
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
  - geo/locale routing, A/B bucket assignment

Poor fit:
  - validating a token with a DB lookup on every request
    (Edge Runtime plus DB latency on EVERY request, including
    static assets, if the matcher is too broad)
  - complex business logic — belongs in Route Handlers or
    Server Actions, which have a full Node.js runtime
```

A common anti-pattern is validating a JWT (JSON Web Token) in middleware with a DB check — "has this token been revoked", for example. It is technically possible through `fetch` to an external service. But it adds a network round trip to *every* protected request.

Heavier authorization logic usually moves into the Route Handlers and Server Actions themselves. Middleware then sticks to cheap checks, such as verifying a JWT signature without a DB lookup.

## Common interview mistakes

- **"params.id is a number if the URL has digits"** — no. `params` values are always strings, or arrays of strings for catch-all. Coercing the type is the developer's job.

- **Confusing `[...slug]` and `[[...slug]]`** — the first needs at least one segment, so `/docs` gives a 404. The second matches `/docs` as well, and there `slug` is `undefined`.

- **"Route Groups affect the URL"** — no, `(marketing)`/`(app)` exist only to organize files and provide different layouts; they don't appear in the URL.

- **"layout.tsx and template.tsx are just synonyms"** — `layout` preserves state and the DOM across navigations within a segment, `template` is recreated on every navigation. The difference is critical for `useEffect`-based analytics or enter/exit animations.

- **"Middleware can do everything a Route Handler can"** — no. The Edge Runtime gives no access to Node APIs or to most ORM libraries (object-relational mappers). Not knowing this is a common cause of "Prisma crashes in my middleware".

- **Forgetting `matcher`** — without it, middleware runs on every request, including `/_next/static/*`, `/favicon.ico`, etc., measurably increasing latency.

- **"Redirect and Rewrite are synonyms for 'send the user somewhere'"** — no. A redirect changes the URL in the browser, so both the user and search engines see it. A rewrite does not change it. For SEO (search engine optimization) they are different tools: a redirect says "the content has moved", a rewrite says "same resource, different implementation".
