# Next.js Interview Questions (Middle → Senior)

This file is a quick Q&A recap. Detailed explanations with code and nuance live in the earlier articles of this section. The focus here is precise phrasing, plus the senior-level follow-ups that often get asked as a "plus one" to a basic answer.

---

## 1. What is Next.js?

A full-stack framework built on React. Beyond the UI (user interface) it addresses rendering, routing, data fetching and caching, and it provides a backend layer: Route Handlers, Server Actions, Middleware. React is a UI library; Next is an application framework that uses React as its rendering engine.

## 2. What problems does Next.js solve that React doesn't?

SEO (search engine optimization) and first paint suffer in a plain SPA (single-page application), because the initial HTML is empty. There is also no unified data-fetching model, code splitting is manual, and there is no built-in backend layer.

Senior follow-up: modern React (Suspense, Server Components) addresses part of this on its own. But without a framework around them — routing, build pipeline, deployment — these primitives have limited value.

## 3. Why is Next.js called a fullstack framework?

Because one project and one deployment combine a UI layer (Server and Client Components) with a backend layer (Route Handlers, Server Actions, Middleware). For simple tasks you don't need a separate Express or Nest service: BFF (Backend For Frontend) aggregation, forms, webhooks.

## 4. How does React differ from Next.js?

| | React | Next.js |
|---|---|---|
| Level | UI library | Application framework |
| Solves | How to describe/update UI | Where/when code runs, routing, caching |
| Backend | None | Route Handlers, Server Actions, Middleware |

## 5. What is rendering?

The process of turning a React tree into HTML. Two parameters define a model. The first is *where* it happens: server, client, or build time for a CDN (content delivery network). The second is *when*: on every request, once at build, or periodically.

## 6. What is CSR?

Client Side Rendering — HTML is created in the browser after JS loads and runs. Pro: cheap server, instant transitions after load. Con: empty initial HTML, request waterfalls inside `useEffect`.

## 7. What is SSR?

Server Side Rendering — HTML is created on the server on every request. In the App Router this is the default for a Server Component that uses `cookies()`, `headers()`, or `fetch` with `cache: 'no-store'`. You can also force it with `export const dynamic = 'force-dynamic'`.

## 8. What is SSG?

Static Site Generation — HTML is created at build time; the server isn't involved in rendering at request time at all. In the App Router: a Server Component with no dynamic APIs and `fetch` with `cache: 'force-cache'` (the default for fetch in Next.js ≤14).

## 9. What is ISR?

Incremental Static Regeneration — SSG that goes stale and regenerates in the background. Staleness comes from a TTL (time to live, set by `revalidate`) or on demand, via `revalidateTag` or `revalidatePath`. The user whose request triggers revalidation gets the **stale** version (stale-while-revalidate), not the rebuilt one.

## 10-12. When to use SSR / SSG / ISR?

```txt
SSR  → personalized, session-bound data
        (account pages, authenticated cart)
SSG  → content that rarely changes
        (docs, landing pages, blogs edited rarely)
ISR  → content that changes, but does not need
        instant freshness (catalogs, news, CMS pages)
```

## 13. What is hydration?

The process where React reconciles already-existing server HTML with a virtual DOM (Document Object Model) and attaches event handlers, **without** recreating the markup from scratch. Before hydration, content is visible but not interactive.

## 14-15. Hydration mismatch and its causes

Occurs when the HTML rendered on the server doesn't match what React renders on the client during the first pass. Causes: `Date.now()` or `Math.random()` directly in JSX (the markup syntax React uses), reading `window` or `localStorage` during render, invalid HTML tag nesting.

Fix — defer the computation to `useEffect`, rendering `null` or a placeholder on the server and on the first client render. Sparingly, `suppressHydrationWarning`.

## 16-18. App Router, Pages Router, and their main difference

The App Router (`app/`) is built around React Server Components, nested layouts that preserve state across navigation, and built-in streaming. In the Pages Router (`pages/`) every file is a route and a Client Component, with data via `getServerSideProps` or `getStaticProps`.

**The main difference isn't the folder structure but the default component model.** In the App Router a page is a Server Component. In the Pages Router it's a Client Component with a server-rendered first pass.

## 19-21. Server Component, Client Component, how to mark one

A Server Component runs only on the server, and its code never ships to the client JS bundle. That's the default for everything in `app/`.

A Client Component is marked with `'use client'`. That directive defines a *module* boundary: everything imported from that file, and everything it imports, joins the client dependency graph.

## 22-23. What's allowed/not allowed in a Server Component

Not allowed: `useState`, `useEffect`, `useRef`, `window`/`document`, event handlers — a Server Component has no browser lifecycle. Allowed: `fetch`, direct DB (database) queries, `cookies()` and `headers()`, filesystem, env variables, "heavy" server-only dependencies such as markdown parsers.

## 24. Why are Server Components faster?

Four concrete mechanisms. First, their code never ships to the client bundle — 0 bytes of JS. Second, there is no hydration, so the client spends no CPU (processor) time reconciling the DOM. Third, data access is direct, without an extra "browser → API" round trip. Fourth, heavy dependencies like parsers and formatters don't weigh down the client.

## 25. How does SSR differ from Server Components?

SSR is about *when/where HTML is generated* (and can apply to a Client Component with a server-rendered first pass + later hydration). Server Components are about *whether the component's code runs in the browser at all*. An SSR component in the Pages Router still hydrates and ships JS to the client; a Server Component never does.

## 26-27. Data fetching in the App Router, and how it differs from browser fetch

`async/await` directly in a Server Component, co-located with the markup. App Router `fetch` differs from browser `fetch`: it is integrated with Next's caching system. It supports `cache`, `next.revalidate` and `next.tags`, and it participates in Request Memoization, which deduplicates identical requests within one render.

## 28-30. cache: 'force-cache', 'no-store', revalidate

With `force-cache` the result is cached indefinitely, until explicit invalidation — SSG-like. With `no-store` every render makes a fresh request — SSR-like.

**Senior nuance**: in Next.js 13/14 `force-cache` is the default. In Next.js 15 the default changed to `no-store`, one of the most discussed breaking changes. And `revalidate: N` sets a TTL in seconds, giving ISR-like behavior. Write it as `next: { revalidate: 60 }` or `export const revalidate = 60`.

## 31-32. revalidatePath vs revalidateTag

`revalidatePath('/blog')` targets the cached render of a specific route (Full Route Cache). By contrast, `revalidateTag('posts')` clears the Data Cache for *all* `fetch` calls carrying that tag, regardless of route. That's useful when one resource appears on several pages.

## 33. generateStaticParams

The `getStaticPaths` equivalent from the Pages Router — returns an array of params for statically generating dynamic routes at build time. For paths not returned here, behavior is controlled by `export const dynamicParams` (defaults to `true` → generate on demand on first request, like `fallback: 'blocking'`).

## 34-36. cookies(), headers(), Dynamic Rendering

`cookies()` and `headers()` give access to request-specific data on the server, and they **mark the route as dynamic**. The route drops out of the Full Route Cache and renders on every request.

Dynamic Rendering is the umbrella term. Other triggers: `searchParams` in a Server Component, `fetch` with `cache: 'no-store'` or `revalidate: 0`, and `export const dynamic = 'force-dynamic'`.

## 37. Request Memoization

If several components within a *single* render call `fetch` with the same URL and options, one real HTTP request runs. The others get the result from memory. This only applies within one server-side render — it is not a persistent cache across different users' requests, which is the Data Cache's job.

## 38-40. Layout, Nested Layout, why a Layout beats a plain wrapper

`layout.tsx` is a persistent UI shell for a route segment and its descendants. It **doesn't remount** on navigation between child routes, so state survives — open menus, sidebar scroll position. Layouts nest: `Root Layout → Dashboard Layout → Page`.

A manual wrapper component in the Pages Router can't do this. Next requests only the RSC payload (React Server Components payload) for the changed segment, while shared layouts stay mounted.

## 41-43. loading.tsx, error.tsx, not-found.tsx

`loading.tsx` automatically wraps `page.tsx` in `<Suspense fallback={...}>`. The `error.tsx` file must be a Client Component; it is an Error Boundary for the segment and **its descendants**. It does not cover a `layout.tsx` at its own level — that one is caught by the parent's `error.tsx`. And `not-found.tsx` renders when `notFound()` is called or a catch-all route doesn't match.

## 44-46. Middleware: what, where, what for

Code that runs **before** routing, on the Edge Runtime (V8 isolates, no Node APIs). The `middleware.ts` file lives at the project root. Uses: auth redirects, rewrites, geo/locale routing, A/B bucket assignment, modifying headers/cookies. Not a fit for heavy business logic or per-request DB operations — that's for Route Handlers/Server Actions with the Node runtime.

## 47. Redirect vs Rewrite

Redirect (`NextResponse.redirect`) — the browser gets a 307/308, the URL in the address bar **changes**, visible to the user and search engines. Rewrite (`NextResponse.rewrite`) — the request is served by a different path "under the hood", the URL **doesn't change**. For SEO these are different signals: redirect = "content moved", rewrite = "same resource, different implementation".

## 48-53. Metadata API, OpenGraph, robots.txt, sitemap.xml

The Metadata API is a declarative `metadata` or `generateMetadata` export from `layout.tsx` and `page.tsx`. Metadata is **inherited and merged** across the layout tree, and `title.template` shapes child titles.

OpenGraph controls link previews on social and messaging platforms. The files `app/robots.ts` and `app/sitemap.ts` are typed file conventions (`MetadataRoute.Robots`, `MetadataRoute.Sitemap`). For very large catalogs, `generateSitemaps` produces several files.

## 54-55. next/image, next/font

`next/image` generates a `srcset` and converts images to modern formats: WebP (Google's format, noticeably smaller files) and AVIF (newer, smaller still). It lazily loads anything outside the viewport. Explicit `width` and `height` — or `fill` with a positioned parent — reserve space, which reduces CLS (Cumulative Layout Shift). The `priority` prop raises fetch priority for the LCP element (Largest Contentful Paint).

`next/font` downloads the font **at build time**, self-hosts it as a static asset, and tunes fallback metrics. That removes the runtime request to Google Fonts and reduces CLS when the font swaps in.

## 56. Core Web Vitals

LCP (Largest Contentful Paint) is improved by SSR/SSG, `next/image priority` and `next/font`. CLS (Cumulative Layout Shift) is improved by explicit image and font dimensions. INP (Interaction to Next Paint) is improved by shipping less client JS via Server Components.

## 57-58. Streaming and Suspense

Streaming sends HTML in chunks (chunked transfer encoding) as data becomes ready, instead of rendering the whole page before sending anything. A `<Suspense fallback={...}>` wraps a slow part of the tree. The user sees the shell and the fallback immediately, while content "fills in" as it becomes ready. Streaming is transparent to SEO: crawlers receive the final HTML after it completes.

## 59-60. Server Actions: what and when

Functions marked with `'use server'`, called from forms/UI code as mutations (`<form action={myAction}>`), without a separate API endpoint. Good for CRUD mutations (create, read, update, delete), forms, optimistic UI (`useOptimistic`). **Not** a fit for a public API — they have no stable, versionable contract and aren't meant for external consumers.

## 61. When are Route Handlers (API Routes) the better choice?

When you need an explicit REST (representational state transfer) contract for external consumers. Typical callers: webhooks from payment providers or a CMS (content management system), a mobile app, third-party integrations, OAuth callbacks.

## 62-63. The Edge Runtime and its constraints

Runs on V8 isolates close to the user — low latency, minimal/no cold start. Constraints: no `fs`/`net`/`child_process`/native modules, only Web-standard APIs (`fetch`, `crypto`, Streams). Standard Prisma + the `pg` driver doesn't work on Edge without an adapter — a common cause of "works locally, breaks in prod on Edge".

## 64. What is a BFF?

Backend For Frontend — Next aggregates and transforms data from multiple microservices into a single, screen-tailored API. The frontend doesn't know the internal service topology. Boundary: a BFF is for UI-facing aggregation/transformation, not for business logic with side effects spanning multiple domains (that's the domain services' job).

## 65-66. How would you architect an e-commerce / CMS project?

E-commerce is a combination of models, one per screen. Home and categories → SSG/ISR. Product page → ISR plus on-demand revalidation via webhook. Cart → CSR. Checkout → Server Actions plus a Route Handler for the payment webhook. Account → SSR.

A CMS project — Next plus Strapi or Contentful, with ISR and `revalidateTag`, invalidated by a webhook when content is published.

## 67. How would you describe the architecture of modern Next.js?

Built around the App Router and React Server Components: rendering, data fetching, and caching are chosen granularly per route segment, not for the whole app. Most logic runs on the server by default; Client Components are a deliberate opt-in only where interactivity is needed (forms, event handlers, browser APIs).

## 68. The most popular senior question: which rendering model would you choose?

There's no single correct model. A production app combines SSG, ISR, SSR, and Server/Client Components *per screen*, based on SEO requirements, performance, data freshness, and compute cost. A strong answer is a "page type → strategy" table, not one word.

## Common interview mistakes

- **Confusing SSR and Server Components** (see question 25) — the most common mistake in this whole section.

- **Answering "fetch is cached by default" without specifying the Next version** — true in 13/14 (`force-cache`), false in 15 (`no-store`). Not knowing this breaking change is a red flag for a role requiring current knowledge.

- **Confusing revalidatePath and revalidateTag** — the former targets a route (Full Route Cache), the latter targets data across the whole app (Data Cache), regardless of route.

- **Assuming middleware can do everything a Route Handler can** — the Edge Runtime doesn't provide Node APIs or most ORM libraries (object-relational mappers).

- **Giving a one-word answer to "how would you cache/architect this app"** — a strong answer shows a composition of decisions, one per screen. A single strategy for the whole app isn't one.

- **Not knowing Server Component errors are invisible in the browser** — critical for discussing observability and error tracking in production.
