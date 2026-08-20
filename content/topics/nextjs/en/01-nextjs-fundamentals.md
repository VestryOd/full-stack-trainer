# Next.js Fundamentals

## What is Next.js

Next.js is a full-stack framework built on top of React. The key word is *framework*, not *library*. React gives you the building blocks: components, hooks, reconciliation of the virtual DOM (Document Object Model — the browser's tree of page nodes). But it deliberately leaves the big questions open. Where do routes live? When and where should data be fetched? Should this page render on the server or in the browser?

Next.js answers those questions for you and imposes (in a good way) its own project structure.

The distinction matters:

```txt
React   → UI library: components, hooks, state, virtual DOM
Next.js → Application framework: routing, rendering, data fetching,
          caching, bundling, optimizations, a backend layer
```

Next.js doesn't replace React. It uses React as its rendering engine and builds the infrastructure around it. Without a framework you assemble that yourself: React Router, a Webpack config, your own rendering server, your own data layer, your own cache.

## Why Next.js exists: problems with classic SPAs

An SPA (single-page application) ships one nearly empty HTML page and draws everything else with JS in the browser.

### Problem 1 — search engine optimization (SEO) and first paint

A classic SPA built with Create React App or Vite ships an almost empty HTML document:

```html
<!DOCTYPE html>
<html>
  <body>
    <div id="root"></div>
    <script src="/bundle.js"></script>
  </body>
</html>
```

Before ~2018-2019, search crawlers executed JS poorly, so such a page was indexed as empty. Today Googlebot can render JS (via headless Chromium), but:

- rendering happens asynchronously and can take days, which affects how quickly new pages get indexed;
- crawl budget is limited — large SPAs get indexed more slowly and less completely;
- other bots (social network OpenGraph preview scrapers, some search engines) still don't execute JS at all.

Server-side rendering (SSR) and static site generation (SSG) solve this. Both send ready-made HTML with the content already in it.

### Problem 2 — the cost of the first load

The path to an interactive page is usually measured with three metrics:

- **TTFB** (time to first byte) — when the first byte of the response arrives;
- **FCP** (first contentful paint) — when the user first sees anything on screen;
- **TTI** (time to interactive) — when the page starts reacting to clicks.

In a pure SPA, the user goes through a long, mostly *sequential* chain:

```txt
HTML (nearly empty)
  ↓
download JS bundle
  ↓
parse and execute bundle, React mounts
  ↓
API requests (often after mount, not before)
  ↓
re-render with data
```

Every step adds latency, and they mostly run one after another. On slow networks (3G, mobile connections in some regions) this turns into seconds of a blank screen. With SSR/SSG the HTML arrives with the data already in it, and hydration "wakes up" that markup. So the user sees content well before the app becomes interactive.

### Problem 3 — where and when to fetch data

In classic React — before Suspense and React Server Components (RSC) — data fetching was a set of conventions each team invented on its own. Typical ones: `useEffect` + `useState`, custom hooks, react-query and SWR (stale-while-revalidate), Redux thunks.

Next.js provides a single model instead. You fetch data directly in a Server Component with `async`/`await`. No client-side `useEffect`, no request waterfalls, and no extra client JS shipped just to run fetching logic.

```tsx
// app/products/page.tsx — Server Component, runs on the server
export default async function ProductsPage() {
  const products = await fetch('https://api.example.com/products', {
    cache: 'no-store', // or revalidate, see the data fetching article
  }).then((res) => res.json());

  return (
    <ul>
      {products.map((p: { id: string; name: string }) => (
        <li key={p.id}>{p.name}</li>
      ))}
    </ul>
  );
}
```

There's no `useEffect`, no client-side loading state, and no extra JS shipped just to call an API.

## Next.js as an "opinionated framework"

Interviewers often ask what "opinionated" means here. It means the framework makes architectural decisions for you and expects you to follow its conventions rather than invent your own:

- **Routing** — the `app/` directory structure *is* the routing (file-system based routing). There's no separate route config.
- **Rendering model** — by default, everything in `app/` is a Server Component; client-side code is an explicit opt-in via `'use client'`.
- **Data fetching** — `fetch` with an extended API (`cache`, `next.revalidate`, `next.tags`) is built into the platform, not a third-party library.
- **Bundling/Code splitting** — automatic per-route splitting, no manual `React.lazy` setup per route.

The upside of this approach is less boilerplate and fewer architectural debates within the team. The downside is that stepping outside these conventions is harder here. A custom SSR server or a custom cache layer costs more here than in an "unopinionated" stack like Vite + React Router. There you pick every piece yourself.

## Next.js as a fullstack framework

Next.js simultaneously contains:

```txt
Frontend:  React Server/Client Components, Layouts, Streaming UI
Backend:   Route Handlers (app/api/**/route.ts), Server Actions,
           Middleware
```

This lets you keep the BFF layer (Backend For Frontend) and the UI (user interface) in one repository and one deployment. You need no separate Express or Nest service just to aggregate data for one screen. A Route Handler is a full backend endpoint:

```ts
// app/api/users/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const userId = request.nextUrl.searchParams.get('id');
  const user = await db.user.findUnique({ where: { id: userId ?? '' } });

  if (!user) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }
  return NextResponse.json(user);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const created = await db.user.create({ data: body });
  return NextResponse.json(created, { status: 201 });
}
```

And Middleware — code that runs *before* a request reaches a page or Route Handler, on the Edge Runtime:

```ts
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('session')?.value;

  if (!token && request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*'],
};
```

Typical uses: auth redirects, geo-based routing, A/B testing (picking a variant before render), modifying headers/cookies. An important nuance: middleware runs on the Edge Runtime for *every* request that matches its matcher. There it has no access to Node.js-specific APIs (`fs`, `net`, native modules). And every invocation adds latency to all matching requests, so keep the middleware as lightweight as you can.

## Code splitting and built-in optimizations

In a classic SPA, the app is often shipped as one large JS bundle (or requires manual `React.lazy`/`Suspense` setup per route). Next.js does per-route code splitting by default: a user opening `/checkout` doesn't download the JS that's only needed for `/admin`.

The framework also provides wrapper components over browser primitives that solve performance problems on their own:

```tsx
import Image from 'next/image';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], display: 'swap' });

export default function Hero() {
  return (
    <div className={inter.className}>
      <Image
        src="/hero.jpg"
        alt="Hero banner"
        width={1200}
        height={600}
        priority // disables lazy-loading for above-the-fold images
      />
    </div>
  );
}
```

`next/image` does several things for you. It generates a `srcset`, converts images to modern formats (`.webp`, `.avif`), and lazily loads everything outside the viewport. It also reserves space for the image, which prevents layout shift — the cumulative layout shift (CLS) part of Core Web Vitals.

`next/font` downloads fonts at build time and serves them as static assets of your own project. That removes the runtime request to Google Fonts, and with it the flash of invisible text (FOIT) and the flash of unstyled text (FOUT).

## React vs Next.js — how to explain the difference in an interview

A common question, and a weak answer is "Next is React with routing built in". A more precise framing:

| | React | Next.js |
|---|---|---|
| Level | UI library | Application framework |
| What it solves | How to describe and update UI | Where and when code runs, routing, caching, data delivery |
| Rendering | Client-side only (by default) | client-side (CSR), server (SSR), static (SSG), incremental (ISR), streaming — chosen per segment |
| Backend | None | Route Handlers, Server Actions, Middleware |

Next.js uses React *as* its rendering engine — it doesn't replace reconciliation, hooks, or the component model, it wraps them in a request-lifecycle infrastructure.

## Common interview mistakes

- **"Next.js is just a routing library for React"** — misses the point. Next is an application framework that addresses rendering, data fetching, caching, and the backend layer, not just routing.

- **"SSR solves SEO once and for all"** — modern search engines already execute JS. The real value of SSR/SSG is performance (TTFB/FCP) and predictable indexing, not just "visibility to a crawler".

- **Confusing SSG and SSR** — describing both as "rendered on the server" without distinguishing *when*: at build time (SSG) vs. on every request (SSR). These are different models with different cost/freshness trade-offs — see the rendering models article.

- **"Middleware is just a way to redirect"** — middleware runs on the Edge Runtime for *every* matching request, with no Node.js API access. Not knowing this is a common root cause behind "why doesn't Prisma/fs work in my middleware".

- **Can't explain why Next is called "fullstack"** — the answer isn't "because it has API Routes". It's that one app and one deployment combine a UI layer (Server and Client Components) with a backend layer (Route Handlers, Server Actions, Middleware). That's what makes a BFF layer cheap to build.

- **Treating `next/image` and `next/font` as "just syntactic sugar"** — they are real build-time and runtime optimizations: `srcset` generation, format conversion, font inlining. In vanilla React you configure all of that by hand, with third-party tools.
