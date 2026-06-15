# Next.js Interview Questions (Middle → Senior)

This file is a quick Q&A recap. Detailed explanations with code and nuance live in the earlier articles in this section; the focus here is precise phrasing and the senior-level follow-ups that often get asked as a "plus one" to a basic answer.

---

## 1. What is Next.js?

A full-stack framework built on React that addresses (beyond UI) rendering, routing, data fetching, caching, and provides a backend layer (Route Handlers, Server Actions, Middleware). React is a UI library; Next is an application framework that uses React as its rendering engine.

## 2. What problems does Next.js solve that React doesn't?

SEO and first paint (empty HTML in an SPA), no unified data-fetching model, manual code splitting, no built-in backend layer. Senior follow-up: modern React (Suspense, Server Components) addresses part of this on its own — but without a framework around them (routing, build pipeline, deployment), these primitives have limited value.

## 3. Why is Next.js called a fullstack framework?

Because one project and one deployment combine a UI layer (Server/Client Components) with a backend layer (Route Handlers, Server Actions, Middleware) — no need to stand up a separate Express/Nest service for simple tasks (BFF aggregation, forms, webhooks).

## 4. How does React differ from Next.js?

| | React | Next.js |
|---|---|---|
| Level | UI library | Application framework |
| Solves | How to describe/update UI | Where/when code runs, routing, caching |
| Backend | None | Route Handlers, Server Actions, Middleware |

## 5. What is rendering?

The process of turning a React tree into HTML. The key parameters of a model: *where* (server/client/build-time CDN) and *when* (every request/once at build/periodically).

## 6. What is CSR?

Client Side Rendering — HTML is created in the browser after JS loads and runs. Pro: cheap server, instant transitions after load. Con: empty initial HTML, request waterfalls inside `useEffect`.

## 7. What is SSR?

Server Side Rendering — HTML is created on the server on every request. In the App Router, this is the default for a Server Component using `cookies()`/`headers()`/`fetch` with `cache: 'no-store'`, or explicitly via `export const dynamic = 'force-dynamic'`.

## 8. What is SSG?

Static Site Generation — HTML is created at build time; the server isn't involved in rendering at request time at all. In the App Router: a Server Component with no dynamic APIs and `fetch` with `cache: 'force-cache'` (the default for fetch in Next.js ≤14).

## 9. What is ISR?

Incremental Static Regeneration — SSG that goes stale via TTL (`revalidate`) or on demand (`revalidateTag`/`revalidatePath`) and regenerates in the background. The user whose request triggers revalidation gets the **stale** version (stale-while-revalidate), not the rebuilt one.

## 10-12. When to use SSR / SSG / ISR?

```txt
SSR  → personalized/session-bound data (account pages, authenticated cart)
SSG  → content that rarely changes (docs, landing pages, blogs with infrequent edits)
ISR  → content that changes but doesn't need instant freshness
        (catalogs, news, CMS pages)
```

## 13. What is hydration?

The process where React reconciles already-existing server HTML with a virtual DOM and attaches event handlers, **without** recreating the markup from scratch. Before hydration, content is visible but not interactive.

## 14-15. Hydration mismatch and its causes

Occurs when the HTML rendered on the server doesn't match what React renders on the client during the first pass. Causes: `Date.now()`/`Math.random()` directly in JSX, accessing `window`/`localStorage` during render, invalid HTML tag nesting. Fix — defer the computation to `useEffect` (render `null`/a placeholder on the server and on the first client render) or, sparingly, `suppressHydrationWarning`.

## 16-18. App Router, Pages Router, and their main difference

The App Router (`app/`) is built around React Server Components, nested layouts that preserve state across navigation, and built-in streaming. The Pages Router (`pages/`) — every file = a route = a Client Component, data via `getServerSideProps`/`getStaticProps`. **The main difference isn't the folder structure but the default component model**: in the App Router a page is a Server Component, in the Pages Router it's a Client Component with a server-rendered first pass.

## 19-21. Server Component, Client Component, how to mark one

A Server Component runs only on the server, and its code never ships to the client JS bundle (the default for everything in `app/`). A Client Component is marked with `'use client'`, which defines a *module* boundary: everything imported from that file (and everything it imports) joins the client dependency graph.

## 22-23. What's allowed/not allowed in a Server Component

Not allowed: `useState`, `useEffect`, `useRef`, `window`/`document`, event handlers — a Server Component has no browser lifecycle. Allowed: `fetch`, direct DB queries, `cookies()`/`headers()`, filesystem, env variables, "heavy" server-only dependencies (markdown parsers, etc.).

## 24. Why are Server Components faster?

Four concrete mechanisms: (1) their code never ships to the client bundle — 0 bytes of JS; (2) no hydration — no client CPU cost reconciling the DOM; (3) direct data access without an extra "browser → API" round trip; (4) heavy dependencies (parsers, formatters) don't weigh down the client.

## 25. How does SSR differ from Server Components?

SSR is about *when/where HTML is generated* (and can apply to a Client Component with a server-rendered first pass + later hydration). Server Components are about *whether the component's code runs in the browser at all*. An SSR component in the Pages Router still hydrates and ships JS to the client; a Server Component never does.

## 26-27. Data fetching in the App Router, and how it differs from browser fetch

`async/await` directly in a Server Component, co-located with the markup. Unlike browser `fetch`, App Router fetch is integrated with Next's caching system: it supports `cache`, `next.revalidate`, `next.tags`, and participates in Request Memoization (deduplicating identical requests within one render).

## 28-30. cache: 'force-cache', 'no-store', revalidate

`force-cache` — caches the result indefinitely (until explicit invalidation), SSG-like. `no-store` — a fresh request on every render, SSR-like. **Senior nuance**: in Next.js 13/14, `force-cache` is the default; in Next.js 15 the default changed to `no-store` — one of the most discussed breaking changes. `revalidate: N` — TTL in seconds for ISR-like behavior (`next: { revalidate: 60 }` or `export const revalidate = 60`).

## 31-32. revalidatePath vs revalidateTag

`revalidatePath('/blog')` — targets the cached render of a specific route (Full Route Cache). `revalidateTag('posts')` — clears the Data Cache for *all* `fetch` calls tagged with it, regardless of route — useful when one resource is used on multiple pages.

## 33. generateStaticParams

The `getStaticPaths` equivalent from the Pages Router — returns an array of params for statically generating dynamic routes at build time. For paths not returned here, behavior is controlled by `export const dynamicParams` (defaults to `true` → generate on demand on first request, like `fallback: 'blocking'`).

## 34-36. cookies(), headers(), Dynamic Rendering

`cookies()`/`headers()` give access to request-specific data on the server and **mark the route as dynamic** — it drops out of the Full Route Cache and renders on every request. Dynamic Rendering is the umbrella term; the full list of triggers also includes `searchParams` in a Server Component, `fetch` with `cache: 'no-store'`/`revalidate: 0`, and `export const dynamic = 'force-dynamic'`.

## 37. Request Memoization

If multiple components within a *single* render call `fetch` with the same URL/options, one real HTTP request runs and the rest get the result from memory. This only applies within one server-side render — it's not a persistent cache across different users' requests (that's the Data Cache's job).

## 38-40. Layout, Nested Layout, why a Layout beats a plain wrapper

`layout.tsx` is a persistent UI shell for a route segment and its descendants — it **doesn't remount** on navigation between child routes, preserving state (open menus, sidebar scroll position). Layouts nest: `Root Layout → Dashboard Layout → Page`. Unlike a manual wrapper component in the Pages Router, Next only requests the RSC payload for the changed segment from the server, while shared layouts stay mounted.

## 41-43. loading.tsx, error.tsx, not-found.tsx

`loading.tsx` automatically wraps `page.tsx` in `<Suspense fallback={...}>`. `error.tsx` (must be a Client Component) is an Error Boundary for the segment and **its descendants**, but not for a `layout.tsx` at its own level (that's caught by the parent's `error.tsx`). `not-found.tsx` renders when `notFound()` is called or a catch-all route doesn't match.

## 44-46. Middleware: what, where, what for

Code that runs **before** routing, on the Edge Runtime (V8 isolates, no Node APIs). The `middleware.ts` file lives at the project root. Uses: auth redirects, rewrites, geo/locale routing, A/B bucket assignment, modifying headers/cookies. Not a fit for heavy business logic or per-request DB operations — that's for Route Handlers/Server Actions with the Node runtime.

## 47. Redirect vs Rewrite

Redirect (`NextResponse.redirect`) — the browser gets a 307/308, the URL in the address bar **changes**, visible to the user and search engines. Rewrite (`NextResponse.rewrite`) — the request is served by a different path "under the hood", the URL **doesn't change**. For SEO these are different signals: redirect = "content moved", rewrite = "same resource, different implementation".

## 48-53. Metadata API, OpenGraph, robots.txt, sitemap.xml

The Metadata API is a declarative `metadata`/`generateMetadata` export from `layout.tsx`/`page.tsx`; metadata is **inherited and merged** across the layout tree (`title.template` for child titles). OpenGraph controls link previews on social/messaging platforms. `app/robots.ts`/`app/sitemap.ts` are typed file conventions (`MetadataRoute.Robots`/`MetadataRoute.Sitemap`); for very large catalogs, `generateSitemaps` produces multiple files.

## 54-55. next/image, next/font

`next/image` generates a `srcset`, converts to WebP/AVIF, lazily loads images outside the viewport; explicit `width`/`height` (or `fill` with a positioned parent) reserve space — reducing CLS; `priority` raises fetch priority for LCP elements. `next/font` downloads the font **at build time**, self-hosts it as a static asset, and tunes fallback metrics — eliminating a runtime request to Google Fonts and reducing CLS on font swap.

## 56. Core Web Vitals

LCP (Largest Contentful Paint — improved by SSR/SSG + `next/image priority` + `next/font`), CLS (Cumulative Layout Shift — improved by explicit image/font dimensions), INP (Interaction to Next Paint — improved by less client JS via Server Components).

## 57-58. Streaming and Suspense

Streaming sends HTML in chunks (chunked transfer encoding) as data becomes ready, instead of rendering the whole page before sending anything. `<Suspense fallback={...}>` wraps a slow part of the tree — the user sees the shell and fallback immediately, while content "fills in" as it's ready. Transparent to SEO — crawlers receive the final HTML after streaming completes.

## 59-60. Server Actions: what and when

Functions marked with `'use server'`, called from forms/UI code as mutations (`<form action={myAction}>`), without a separate API endpoint. Good for CRUD mutations, forms, optimistic UI (`useOptimistic`). **Not** a fit for a public API — they have no stable, versionable contract and aren't meant for external consumers.

## 61. When are Route Handlers (API Routes) the better choice?

When you need an explicit REST/JSON contract for external consumers: webhooks (payment providers, CMS), a mobile app, third-party integrations, OAuth callbacks.

## 62-63. The Edge Runtime and its constraints

Runs on V8 isolates close to the user — low latency, minimal/no cold start. Constraints: no `fs`/`net`/`child_process`/native modules, only Web-standard APIs (`fetch`, `crypto`, Streams). Standard Prisma + the `pg` driver doesn't work on Edge without an adapter — a common cause of "works locally, breaks in prod on Edge".

## 64. What is a BFF?

Backend For Frontend — Next aggregates and transforms data from multiple microservices into a single, screen-tailored API. The frontend doesn't know the internal service topology. Boundary: a BFF is for UI-facing aggregation/transformation, not for business logic with side effects spanning multiple domains (that's the domain services' job).

## 65-66. How would you architect an e-commerce / CMS project?

E-commerce — a combination of models per screen: home/categories → SSG/ISR, product page → ISR + on-demand revalidation via webhook, cart → CSR, checkout → Server Actions + a Route Handler for the payment webhook, account → SSR. CMS project — Next + Strapi/Contentful + ISR with `revalidateTag`, invalidated via webhook on content publish.

## 67. How would you describe the architecture of modern Next.js?

Built around the App Router and React Server Components: rendering, data fetching, and caching are chosen granularly per route segment, not for the whole app. Most logic runs on the server by default; Client Components are a deliberate opt-in only where interactivity is needed (forms, event handlers, browser APIs).

## 68. The most popular senior question: which rendering model would you choose?

There's no single correct model — a production app combines SSG, ISR, SSR, and Server/Client Components *per screen*, based on SEO requirements, performance, data freshness, and compute cost. A strong answer is a "page type → strategy" table, not one word.

## Common interview mistakes

- **Confusing SSR and Server Components** (see question 25) — the most common mistake in this whole section.

- **Answering "fetch is cached by default" without specifying the Next version** — true in 13/14 (`force-cache`), false in 15 (`no-store`). Not knowing this breaking change is a red flag for a role requiring current knowledge.

- **Confusing revalidatePath and revalidateTag** — the former targets a route (Full Route Cache), the latter targets data across the whole app (Data Cache), regardless of route.

- **Assuming middleware can do everything a Route Handler can** — the Edge Runtime doesn't provide Node APIs or most ORMs.

- **Giving a one-word answer to "how would you cache/architect this app"** — a strong senior answer always shows a composition of decisions per screen, not a single strategy.

- **Not knowing Server Component errors are invisible in the browser** — critical for discussing observability and error tracking in production.
