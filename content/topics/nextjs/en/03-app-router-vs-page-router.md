# App Router vs Pages Router

## The short version

Next.js has two routers, and in practice you need both. The **App Router** is where new code goes. The **Pages Router** is what most existing codebases are still written in.

The difference that matters is the default component model. In the App Router a page is a Server Component; in the Pages Router it is a Client Component.

The **Pages Router** was the only option before Next.js 13. Its rule is simple: in the `pages/` structure every file is a page, and a page is a React component. That component is server-rendered on the initial request, then hydrated as a regular Client Component.

Next.js 13 introduced the **App Router** (the `app/` directory), built around React Server Components (RSC), nested layouts and streaming. Since Next.js 13.4 it is stable and recommended for new projects. The Pages Router is still officially supported and used in a huge number of codebases, so knowing both is a practical skill, not history.

## Why the App Router was created

The Pages Router handled server rendering (SSR), static generation (SSG) and incremental regeneration (ISR) well, but it had structural limits:

- **No nested layouts without costly re-renders**: the only layout mechanism was `_app.tsx`, shared by the whole app. Giving different sections their own layouts meant wrapping pages in wrapper components by hand. And navigating between pages re-created the layout from scratch, which reset state like scroll position or open modals.
- **No built-in streaming**: the entire page was rendered on the server and sent as one block. One slow data fetch — say, a "Recommendations" widget — blocked sending the whole HTML.
- **No Server Components**: every page was hydrated as a Client Component, even an essentially static one. All the JS needed for rendering ended up in the client bundle.
- **Data fetching via special functions** (`getServerSideProps`, `getStaticProps`) — these lived *next to* the component, but not *inside* it. There was no data co-location for nested components: the whole page received props as one big object.

## Structure and routing

**Pages Router**:

```txt
pages/
 ├─ index.tsx          → /
 ├─ about.tsx           → /about
 ├─ users/
 │   ├─ index.tsx       → /users
 │   └─ [id].tsx        → /users/:id
 ├─ _app.tsx            → shared wrapper for all pages
 └─ _document.tsx       → customizing <html>/<head>
```

Every file under `pages/` *directly* becomes a route — you can't put a helper component there without consequences (it becomes a page).

**App Router**:

```txt
app/
 ├─ layout.tsx           → Root Layout (required)
 ├─ page.tsx              → /
 ├─ about/
 │   └─ page.tsx          → /about
 ├─ users/
 │   ├─ layout.tsx        → layout for all /users/*
 │   ├─ page.tsx          → /users
 │   ├─ loading.tsx       → loading UI for /users
 │   ├─ error.tsx         → error boundary for /users
 │   └─ [id]/
 │       └─ page.tsx      → /users/:id
 └─ api/
     └─ health/
         └─ route.ts      → /api/health (Route Handler)
```

Only files with reserved names create a route: `page.tsx`, `route.ts`, `layout.tsx` and a few others. So you can freely keep `components/`, `utils.ts` and `hooks.ts` next to `page.tsx` without turning them into routes. This is called **colocation**.

## The key difference: the default component model

```txt
Pages Router:  Page = Client Component
                (fully hydrated; getServerSideProps is a separate
                 server-only layer)

App Router:    Page = Server Component by default
                ('use client' is an explicit opt-in
                 for interactivity)
```

This changes how you think architecturally. The question is no longer "how do I fetch data for the page". It becomes "which parts of the tree *need* to be interactive, and how do I keep that surface small". More on this in the Server vs Client Components article.

## Data fetching

**Pages Router** — special exported functions that Next.js runs before rendering the component:

```ts
// pages/users/index.tsx
export async function getServerSideProps() {
  const users = await db.user.findMany();
  return { props: { users } }; // must be JSON-serializable
}

export default function UsersPage({ users }: { users: User[] }) {
  return <UserList users={users} />;
}
```

**App Router** — `async/await` directly in the component, co-located with the markup:

```tsx
// app/users/page.tsx
export default async function UsersPage() {
  const users = await db.user.findMany();
  return <UserList users={users} />;
}
```

The key consequence: in the App Router, *nested* Server Components fetch their own data independently. You don't have to thread everything through props from the top-level page. Next automatically deduplicates identical `fetch` requests within a single render (request memoization).

## Layouts and state preservation across navigation

In the Pages Router, shared UI (header, sidebar) usually lived in `_app.tsx` — the single "layout" for the entire app. Separate layouts for different sections required wrapper components written by hand, often a higher-order component (HOC). And navigating between pages re-rendered the **entire** layout, including `_app`.

In the App Router, every route segment can have its own `layout.tsx`, and they **nest**:

```tsx
// app/layout.tsx — Root Layout, required, contains <html> and <body>
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Header />
        {children}
      </body>
    </html>
  );
}

// app/dashboard/layout.tsx — nested layout only for /dashboard/*
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="dashboard-shell">
      <Sidebar />
      <main>{children}</main>
    </div>
  );
}
```

```txt
Navigating /dashboard/settings → /dashboard/profile:

RootLayout       — does NOT re-render
DashboardLayout  — does NOT re-render
                   (Sidebar keeps its state, scroll isn't reset)
page.tsx         — re-renders
```

This follows directly from the Server Components model and React reconciliation at the tree level. On navigation Next requests only the changed segment, and shared layouts stay mounted.

## Loading UI and error handling — built-in conventions

In the Pages Router, loading and error states were implemented manually (your own `if (loading) return <Spinner />`, your own error boundaries). The App Router introduces file conventions that Next automatically wraps in `<Suspense>` and an Error Boundary:

```txt
app/users/
 ├─ page.tsx     → main content
 ├─ loading.tsx  → wraps page.tsx in
 │                 <Suspense fallback={<Loading />}>
 └─ error.tsx    → wraps page.tsx in an Error Boundary
```

```tsx
// app/users/loading.tsx
export default function Loading() {
  return <Skeleton rows={5} />;
}

// app/users/error.tsx — must be a Client Component
'use client';

export default function Error({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <div>
      <p>Something went wrong: {error.message}</p>
      <button onClick={() => retry()}>Try again</button>
    </div>
  );
}
```

The `retry` prop became stable in Next.js 16.3 — it re-fetches and re-renders the segment. Older code, and any project on Next.js 15, uses `reset` instead. That one clears the error state and re-renders the children without re-fetching.

An important nuance: `error.tsx` catches errors only in *its own segment and below*. An error in a `layout.tsx` at the same level is caught by the *parent* segment's `error.tsx`, not the current one. The reason: a layout renders "outside" its own error boundary.

## Streaming

The Pages Router renders a page in full and sends one HTML document. So a slow data fetch in any part of the page delays TTFB (time to first byte) for everything.

The App Router supports streaming out of the box via `<Suspense>`. The server sends the page shell immediately, then streams slow parts as separate chunks when they are ready. Under the hood this is HTTP chunked transfer encoding:

```tsx
// app/dashboard/page.tsx
import { Suspense } from 'react';

export default function DashboardPage() {
  return (
    <div>
      <Header /> {/* renders immediately */}
      <Suspense fallback={<RevenueSkeleton />}>
        <RevenueChart /> {/* slow fetch — streamed separately */}
      </Suspense>
      <Suspense fallback={<OrdersSkeleton />}>
        <RecentOrders /> {/* its own independent fetch */}
      </Suspense>
    </div>
  );
}
```

The user sees `Header` and skeletons instantly, while `RevenueChart`/`RecentOrders` "fill in" as their data arrives — without blocking each other (parallel, not sequential, fetches).

## Metadata and search engine optimization (SEO)

Pages Router: `_document.tsx` + manually inserting `<Head>` via `next/head` on every page.

App Router: a declarative Metadata API, static or dynamic:

```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from 'next';

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params; // Next.js 15: params is async
  const post = await getPost(slug);
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: { images: [post.coverImage] },
  };
}
```

## What's left of the Pages Router

The Pages Router is officially supported, and both routers **can coexist in the same project**. On a route conflict Next prioritizes `app/`. Teams use this for gradual migration of legacy projects.

Most existing Next 12-14 codebases are still written with `pages/`. In practice you are more likely to meet the Pages Router in a real project than to start fresh with the App Router.

## Comparison

| | Pages Router | App Router |
|---|---|---|
| Directory | `pages/` | `app/` |
| File → route | any file | only `page.tsx`/`route.ts` |
| Default component | Client Component | Server Component |
| Data fetching | `getServerSideProps`/`getStaticProps` | `async/await` in the component |
| Layouts | `_app.tsx`, manual wrappers | nested `layout.tsx`, preserve state |
| Loading/Error | manual | `loading.tsx`/`error.tsx` (conventions) |
| Streaming | no | yes, via `<Suspense>` |
| Metadata | `next/head` | Metadata API / `generateMetadata` |

## Common interview mistakes

- **"The App Router is just a new folder instead of `pages/`"** — the directory is a consequence, not the cause. The main change is the default component model (Server Components) and built-in streaming/nested layouts.

- **"getServerSideProps doesn't exist anymore in Next.js"** — it does, and works fine in the Pages Router. In the App Router it's replaced by an `async` component + `fetch` options.

- **Can't explain why changing layouts per page is "more expensive" in the Pages Router** — `_app.tsx` is the only layout level there. Without nested layouts, shared UI either re-renders or needs a custom workaround. The usual one is per-page layouts via a `getLayout` pattern, invented by the community and never part of the framework.

- **Thinking `error.tsx` catches every error in the app** — it does not catch errors in a `layout.tsx` at its own level. It also does not replace a global `global-error.tsx` at the root of `app/`.

- **"Server Components are the same thing as SSR in the Pages Router"** — SSR in the Pages Router still hydrates the component fully on the client. It is a Client Component, just with a server-rendered first pass. A Server Component in the App Router **never ships to the client JS bundle at all**. That is a fundamentally different model, not "the same SSR with a new name".

- **Not knowing both routers can run simultaneously** — this is a key fact in migration discussions. Moving from Pages to App Router is done incrementally, route by route, not as a big-bang rewrite.
