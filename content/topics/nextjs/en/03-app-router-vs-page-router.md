# App Router vs Pages Router

## Context

Before Next.js 13, the only option was the **Pages Router** — a `pages/` file structure where every file is a page, and a page is a React component that's server-rendered on the initial request and then hydrated as a regular Client Component. Next.js 13 introduced the **App Router** (`app/` directory), built around React Server Components (RSC), nested layouts, and streaming. Since Next.js 13.4 the App Router is considered stable and recommended for new projects, but the Pages Router is officially supported and used in a huge number of existing codebases — so knowing both isn't "history", it's a practical skill for working with legacy code.

## Why the App Router was created

The Pages Router handled SSR/SSG/ISR well, but had structural limitations:

- **No nested layouts without costly re-renders**: the only layout mechanism was `_app.tsx`, shared by the whole app. Giving different sections of a site different layouts required manually wrapping pages in wrapper components, and navigating between pages fully re-created the layout (resetting state like scroll position or open modals).
- **No built-in streaming**: the entire page was rendered on the server and sent as one block — a slow data fetch for any part of the page (e.g. a "Recommendations" widget) blocked sending the whole HTML.
- **No Server Components**: every page, even an essentially static one, was hydrated as a Client Component — all the JS needed for rendering ended up in the client bundle.
- **Data fetching via special functions** (`getServerSideProps`, `getStaticProps`) — these lived *next to* the component, but not *inside* it, and didn't support data co-location at the level of nested components: the whole page received props as one big object.

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

A route is created only by files with reserved names (`page.tsx`, `route.ts`, `layout.tsx`, etc.) — meaning you can freely put `components/`, `utils.ts`, `hooks.ts` next to `page.tsx` without accidentally turning them into routes. This is called **colocation**.

## The key difference: the default component model

```txt
Pages Router:  Page = Client Component
                (fully hydrated, getServerSideProps is a separate server-only layer)

App Router:    Page = Server Component by default
                ('use client' is an explicit opt-in for interactivity)
```

This changes how you think architecturally: in the App Router the question isn't "how do I fetch data for the page" but "which parts of the tree *need* to be interactive, and how do I minimize that surface". More on this in the Server vs Client Components article.

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

The key consequence: in the App Router, *nested* Server Components can independently fetch their own data — there's no need to thread everything through props from the top-level page. Next automatically deduplicates identical `fetch` requests within a single render (request memoization).

## Layouts and state preservation across navigation

In the Pages Router, shared UI (header, sidebar) usually lived in `_app.tsx` — the single "layout" for the entire app. Separate layouts for different sections required manual HOC/wrapper components, and navigating between pages re-rendered the **entire** layout (including `_app`).

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
DashboardLayout  — does NOT re-render (Sidebar keeps its state, scroll isn't reset)
page.tsx         — re-renders
```

This is a direct consequence of the Server Components model + React reconciliation at the tree level: on navigation, Next only requests the changed segment, while shared layouts stay mounted.

## Loading UI and error handling — built-in conventions

In the Pages Router, loading and error states were implemented manually (your own `if (loading) return <Spinner />`, your own error boundaries). The App Router introduces file conventions that Next automatically wraps in `<Suspense>` and an Error Boundary:

```txt
app/users/
 ├─ page.tsx     → main content
 ├─ loading.tsx  → automatically wraps page.tsx in <Suspense fallback={<Loading />}>
 └─ error.tsx    → automatically wraps page.tsx in an Error Boundary
```

```tsx
// app/users/loading.tsx
export default function Loading() {
  return <Skeleton rows={5} />;
}

// app/users/error.tsx — must be a Client Component
'use client';

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div>
      <p>Something went wrong: {error.message}</p>
      <button onClick={() => reset()}>Try again</button>
    </div>
  );
}
```

An important nuance: `error.tsx` only catches errors in *its own segment and below* — an error in a `layout.tsx` at the same level is caught by the *parent* segment's `error.tsx`, not the current one (a layout renders "outside" its own error boundary).

## Streaming

The Pages Router renders a page in full and sends one HTML document — a slow data fetch for any part of the page delays the TTFB for the whole page.

The App Router supports streaming out of the box via `<Suspense>`: the server can send the page shell immediately, and stream slow parts as separate chunks as they become ready (using HTTP chunked transfer encoding):

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

## Metadata and SEO

Pages Router: `_document.tsx` + manually inserting `<Head>` via `next/head` on every page.

App Router: a declarative Metadata API, static or dynamic:

```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from 'next';

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const post = await getPost(params.slug);
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: { images: [post.coverImage] },
  };
}
```

## What's left of the Pages Router

The Pages Router is officially supported, and both routers **can coexist in the same project** (Next prioritizes `app/` on route conflicts) — this is used for gradual migration of legacy projects. Most existing Next 12-14 codebases are still written with `pages/`, so in practice you're more likely to encounter the Pages Router in a real project than to start fresh with the App Router.

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

- **Can't explain why changing layouts per page is "more expensive" in the Pages Router** — because `_app.tsx` is the only layout level, and without nested layouts, shared UI either re-renders or requires custom workarounds (per-page layouts via a `getLayout` pattern — something the community invented, not part of the framework).

- **Thinking `error.tsx` catches every error in the app** — it doesn't catch errors in a `layout.tsx` at its own level, and it doesn't replace a global `global-error.tsx` at the root of `app/`.

- **"Server Components are the same thing as SSR in the Pages Router"** — SSR in the Pages Router still fully hydrates the component on the client (it's a Client Component, just with a server-rendered first pass). A Server Component in the App Router **never ships to the client JS bundle at all** — it's a fundamentally different model, not just "the same SSR with a new name".

- **Not knowing both routers can run simultaneously** — this is a key fact for migration discussions: moving from Pages to App Router is done incrementally, route by route, not as a big-bang rewrite.
