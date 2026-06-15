# Production Architecture and Best Practices

## The level of these questions

This section is about architectural decisions made not by "the developer building a feature" but by whoever is responsible for how the application scales, deploys, and runs in production. Typical phrasings: "how would you architect a Next.js project", "where's the boundary between Next and the rest of the backend", "what goes into Server Actions vs Route Handlers".

```txt
Browser
 ↓
CDN / Edge
 ↓
Next.js (rendering + BFF layer)
 ↓
Backend APIs / Microservices
 ↓
Database
```

## Option 1: Next.js as a thin frontend layer

```txt
Next.js (UI, SSR/SSG)
 ↓
NestJS API (business logic, auth, DB)
 ↓
PostgreSQL
```

Next is responsible only for rendering and UX; all business logic lives in a separate backend service. This is a well-understood, common setup, especially when a backend already exists and serves multiple clients (web, mobile, partner API) — Next is just one more API consumer here.

## Option 2: Next.js as a BFF (Backend For Frontend)

```txt
Browser
 ↓
Next.js (aggregates, transforms, caches)
 ↓
┌──────────────┬──────────────┬──────────────┐
User Service    Product Service   Order Service
 ↓
PostgreSQL / separate DBs per service
```

Next aggregates data from multiple microservices and exposes a single, screen-tailored API to the frontend (via Route Handlers or directly through Server Components). The frontend doesn't know about the internal service topology — all that complexity is encapsulated in the BFF.

**Where the BFF-vs-full-backend line falls** is a practical question: a BFF is good for *aggregating and transforming data for the UI* (combining data from 3 services into one JSON for a specific screen, caching at the Next layer), but it shouldn't become the home for business logic with side effects spanning multiple domains (e.g. "place an order", which must atomically deduct stock, create a payment, and send a notification) — that's the responsibility of domain services with their own transactional guarantees.

## Server Actions vs Route Handlers — when to use which

This is one of the most common "practical" Next.js interview questions, and "both — for the backend" isn't a sufficient answer.

```tsx
// Server Action — a mutation triggered by a form/UI in this same app
'use server';

import { revalidatePath } from 'next/cache';

export async function createComment(formData: FormData) {
  const text = formData.get('text');
  if (typeof text !== 'string' || text.trim().length === 0) {
    return { error: 'Comment cannot be empty' };
  }

  await db.comment.create({ data: { text, postId: formData.get('postId') as string } });
  revalidatePath('/posts'); // invalidate the cache right after the mutation
  return { success: true };
}
```

```tsx
// app/posts/[id]/page.tsx
import { createComment } from './actions';

export default function PostPage() {
  return (
    <form action={createComment}>
      <textarea name="text" />
      <button type="submit">Send</button>
    </form>
  );
}
```

```ts
// Route Handler — a public API endpoint, called from outside (not just the UI)
// app/api/webhooks/stripe/route.ts
export async function POST(request: Request) {
  const signature = request.headers.get('stripe-signature');
  const body = await request.text();

  const event = stripe.webhooks.constructEvent(body, signature!, process.env.STRIPE_WEBHOOK_SECRET!);
  // ... handle the event
  return new Response('ok', { status: 200 });
}
```

| | Server Actions | Route Handlers |
|---|---|---|
| Who calls it | Forms and UI code in this same app | Any client: webhooks, mobile apps, third-party services |
| Contract | Implicit (tied to a specific form/function) | An explicit, versionable REST/JSON contract |
| Typical uses | CRUD mutations, forms, optimistic UI with `useOptimistic` | Webhooks, public APIs, integrations, OAuth callbacks |
| Cache invalidation | `revalidatePath`/`revalidateTag` right in the action | Usually too, often via a separate `/api/revalidate` |

The anti-pattern is building a public API out of Server Actions (they create implicit, "magic" endpoints under the hood, not meant for external consumers and without versioning), or conversely, creating a Route Handler for every UI form, losing progressive enhancement (`<form action={...}>` works even without JS).

## Edge Runtime vs Node.js Runtime

```ts
// app/api/heavy/route.ts
export const runtime = 'nodejs'; // default for Route Handlers

// app/api/light/route.ts
export const runtime = 'edge'; // runs on the Edge (V8 isolates)
```

| | Node.js Runtime | Edge Runtime |
|---|---|---|
| Available APIs | Full Node.js (`fs`, `net`, native modules) | Web-standard APIs (fetch, crypto, Streams) |
| Cold start | Higher | Minimal/none |
| Geography | One region (or several, depending on hosting) | Close to the user, many edge locations |
| ORM (Prisma, etc.) | Works out of the box | Needs an Edge-compatible driver/adapter |
| Bundle size | No hard limits | Size limits (typically ~1-4 MB depending on the provider) |

A practical rule of thumb: anything that talks to a traditional relational DB via a standard TCP driver (Prisma with `pg`) needs the Node runtime. Edge fits lightweight, latency-critical operations: geo-based logic, simple token checks, proxying to external APIs.

## Caching strategy — not "one model", but a map per screen

A production app almost never uses a single rendering model. A good answer to "how would you cache an e-commerce site" is a table, not a single word:

```txt
Homepage              → SSG + revalidate (hourly, content is nearly static)
Product categories     → ISR, revalidateTag('category-X') on assortment changes
Product page            → ISR + on-demand revalidation (webhook from CMS/PIM on price change)
Search/filters          → SSR or CSR (parameter combinations are unpredictable — caching isn't worth it)
Cart                     → CSR (state tied to a specific user's session/cookie)
Checkout                  → Server Actions / Route Handler with Node runtime (payments, side effects)
Account page              → SSR (cookies() for the session) or CSR with client-side data fetching
Admin panel                → CSR, often behind its own auth layer, no SEO needed
```

## Environment variables — a security boundary

```bash
# .env
DATABASE_URL=postgres://...          # server-only
STRIPE_SECRET_KEY=sk_live_...         # server-only
NEXT_PUBLIC_API_URL=https://api...    # ends up in the client bundle
```

```ts
// ❌ Dangerous — a secret accidentally used in code that could end up in a Client Component
export function getApiKey() {
  return process.env.STRIPE_SECRET_KEY; // if this module is imported by a 'use client' file —
}                                        // the value could be inlined into the bundle at build time

// ✅ Protected via server-only
import 'server-only';
export function getApiKey() {
  return process.env.STRIPE_SECRET_KEY;
}
```

The `NEXT_PUBLIC_*` convention isn't just a "convenient prefix" — it means **the variable's value is inlined into the JS bundle at build time**. This has a non-obvious practical consequence: changing a `NEXT_PUBLIC_*` value requires a **rebuild** — simply changing the env var in your container/hosting's runtime config isn't enough, the old value stays baked into the already-built bundle.

## Monitoring and observability

```txt
Error tracking:       Sentry, Bugsnag — especially important to capture errors
                        in Server Components and Client Components separately
Performance:          Vercel Analytics / Core Web Vitals, Datadog RUM
Server-side metrics:  logging for Route Handlers, Server Actions,
                        DB/external API request latency
```

A nuance specific to the App Router: an error in a Server Component happens on the server and **never appears in the browser console** — without server-side error tracking (Sentry with a server SDK), such errors can go completely unnoticed, with the team only seeing a generic "Something went wrong" from `error.tsx`.

## Deployment

```txt
Vercel       — the "native" platform, zero config for ISR/Edge/Streaming,
                but vendor lock-in for platform-specific features (e.g. on-demand ISR
                may behave differently on other platforms)
Self-hosted  — `next start` after `next build`, or Docker + a Node.js server;
                ISR/revalidation needs a persistent filesystem
                or an external cache store
Static export — `output: 'export'`, turns the app into pure static output
                (no dynamic Server Components, no Route Handlers,
                no Image Optimization API) — fine for simple sites
                with no server component, deployable to any static host
```

## End-to-end example: e-commerce

```txt
Homepage, categories        → SSG/ISR, CDN
Product page                 → ISR + revalidateTag via PIM webhook
Search                       → SSR (Route Handler proxies to Elasticsearch)
Cart                          → CSR + localStorage/cookie, synced via a Server Action
Checkout                       → Server Actions (create order) +
                                 Route Handler (payment provider webhook)
Account, orders                → SSR (cookies() for the session)
Admin                            → CSR, separate auth, runtime: 'nodejs' for all APIs
```

## The strongest senior answer

To "what matters most in a production Next.js app", a weak answer lists features (SSR/ISR/Server Actions). A strong answer says there's no single "correct" model — a production app is a *composition* of rendering, caching, and runtime decisions made **per screen**, based on SEO requirements, data freshness, latency, and compute cost. The architect's job isn't "picking a Next.js feature" — it's making sure that composition is explicit, documented, and doesn't degrade into a random scattering of `cache: 'no-store'` added reactively whenever a stale-data bug shows up.

## Common interview mistakes

- **"Next.js fully replaces the backend"** — in most production architectures, Next is a rendering and BFF layer, not the source of truth for business logic and data.

- **"Server Actions are just a new way to write APIs"** — they have a different invocation model (tied to specific forms/components, no stable public contract) and different use cases than Route Handlers.

- **Not knowing the Edge Runtime constrains your choice of ORM/DB drivers** — standard Prisma + `pg` doesn't work on Edge without an adapter; a common cause of "runtime errors in prod that didn't happen locally".

- **"NEXT_PUBLIC_ variables can be changed at runtime without a rebuild"** — no, they're inlined into the bundle at `next build` time. Changing them requires a rebuild.

- **Giving one answer to "how would you cache this site" without distinguishing screens** — a strong answer is a "page type → strategy" table, not a single solution for the whole app.

- **Not mentioning that Server Component errors are invisible in the browser** — critical for observability: without server-side error tracking, a chunk of production bugs is completely invisible to the team.

- **"Static export (`output: 'export'`) supports all App Router features"** — no, it excludes Server Actions, dynamic Route Handlers, the Image Optimization API, and any server-side dynamism — it's effectively a "static-only" mode.
