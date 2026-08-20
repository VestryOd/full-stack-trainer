# Production Architecture and Best Practices

## Where Next.js sits in the stack

A production Next.js app is not the whole backend. It is a rendering layer plus a BFF (Backend For Frontend) layer, and it occupies one well-defined slot:

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

Every architectural question below is about where you draw the lines inside that slot. Interviewers phrase it in a few ways:

- "How would you architect a Next.js project?"
- "Where does Next end and the backend begin?"
- "What goes into Server Actions vs Route Handlers?"

## Option 1: Next.js as a thin frontend layer

```txt
Next.js (UI, SSR/SSG)
 ↓
NestJS API (business logic, auth, DB)
 ↓
PostgreSQL
```

Next is responsible only for rendering and UX (user experience); all business logic lives in a separate backend service. This is a well-understood, common setup. It fits especially well when a backend already exists and serves several clients — web, mobile, a partner API. Next is then just one more API consumer.

## Option 2: Next.js as a BFF (Backend For Frontend)

```txt
Browser
 ↓
Next.js (aggregates, transforms, caches)
 ↓
 ├─→ User Service
 ├─→ Product Service
 └─→ Order Service
      ↓
     PostgreSQL / a separate DB per service
```

Next aggregates data from multiple microservices and exposes a single, screen-tailored API to the frontend (via Route Handlers or directly through Server Components). The frontend doesn't know about the internal service topology — all that complexity is encapsulated in the BFF.

**Where the BFF-vs-full-backend line falls** is a practical question. A BFF is good at *aggregating and transforming data for the UI (user interface)*. Think: combining data from three services into one JSON for a specific screen, or caching at the Next layer.

What it should not become is the home for business logic with side effects that span domains. "Place an order" is the canonical example — it must atomically deduct stock, create a payment, and send a notification. That belongs to domain services with their own transactional guarantees.

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

  const secret = process.env.STRIPE_WEBHOOK_SECRET!;
  const event = stripe.webhooks.constructEvent(body, signature!, secret);
  // ... handle the event
  return new Response('ok', { status: 200 });
}
```

| | Server Actions | Route Handlers |
|---|---|---|
| Who calls it | Forms and UI code in this same app | Any client: webhooks, mobile apps, third-party services |
| Contract | Implicit (tied to a specific form/function) | An explicit, versionable REST (representational state transfer) contract |
| Typical uses | CRUD mutations (create, read, update, delete), forms, optimistic UI | Webhooks, public APIs, integrations, OAuth callbacks |
| Cache invalidation | `revalidatePath`/`revalidateTag` right in the action | Usually too, often via a separate `/api/revalidate` |

There are two anti-patterns here. One is building a public API out of Server Actions. Under the hood they create implicit, "magic" endpoints: no versioning, and not meant for external consumers.

The other is creating a Route Handler for every UI form. That loses progressive enhancement, since `<form action={...}>` works even without JS.

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
| Bundle size | No hard limits | Size limits (typically 1-4 megabytes) |

A practical rule of thumb: anything that opens a raw TCP (Transmission Control Protocol) connection to a relational DB (database) needs the Node runtime. Prisma with `pg` is the usual case. Edge fits lightweight, latency-critical work: geo-based logic, simple token checks, proxying to external APIs.

## Caching strategy — not "one model", but a map per screen

A production app almost never uses a single rendering model. A good answer to "how would you cache an e-commerce site" is a table, not a single word:

```txt
Homepage        → SSG + revalidate hourly (nearly static)
Categories      → ISR, revalidateTag('category-X') on changes
Product page    → ISR + on-demand revalidate (CMS/PIM webhook)
Search/filters  → SSR or CSR (param combos are unpredictable)
Cart            → CSR (state tied to the user's session/cookie)
Checkout        → Server Actions or Route Handler, Node runtime
Account page    → SSR (cookies() for the session) or CSR
Admin panel     → CSR, own auth layer, no SEO needed
```

## Environment variables — a security boundary

```bash
# .env
DATABASE_URL=postgres://...          # server-only
STRIPE_SECRET_KEY=sk_live_...         # server-only
NEXT_PUBLIC_API_URL=https://api...    # ends up in the client bundle
```

```ts
// ❌ Dangerous — a secret read in a module a Client Component may import
export function getApiKey() {
  // if a 'use client' file imports this module, the value can be
  // inlined into the client bundle at build time
  return process.env.STRIPE_SECRET_KEY;
}

// ✅ Protected via server-only
import 'server-only';
export function getApiKey() {
  return process.env.STRIPE_SECRET_KEY;
}
```

The `NEXT_PUBLIC_*` convention isn't just a "convenient prefix". It means **the variable's value is inlined into the JS bundle at build time**.

The consequence is non-obvious: changing a `NEXT_PUBLIC_*` value requires a **rebuild**. Editing the env var in your container or hosting runtime config isn't enough — the old value stays baked into the already-built bundle.

## Monitoring and observability

```txt
Error tracking:      Sentry, Bugsnag — capture Server Component
                       and Client Component errors separately
Performance:         Vercel Analytics, Core Web Vitals, Datadog
Server-side metrics: logs for Route Handlers and Server Actions,
                       DB and external API request latency
```

A nuance specific to the App Router: an error in a Server Component happens on the server and **never appears in the browser console**. Without server-side error tracking (Sentry with its server-side library, say) such errors can go completely unnoticed. The team sees only a generic "Something went wrong" from `error.tsx`.

## Deployment

```txt
Vercel        — "native" platform, zero config for ISR, Edge,
                 Streaming; vendor lock-in for platform-specific
                 features (on-demand ISR may differ elsewhere)
Self-hosted   — next start after next build, or Docker plus a
                 Node.js server; ISR needs a persistent filesystem
                 or an external cache store
Static export — output: 'export' turns the app into static files:
                 no dynamic Server Components, no Route Handlers,
                 no Image Optimization API. Fine for simple sites,
                 deployable to any static host
```

## End-to-end example: e-commerce

```txt
Homepage, categories → SSG/ISR served from the CDN
Product page         → ISR + revalidateTag via PIM webhook
Search               → SSR (Route Handler proxies to Elasticsearch)
Cart                 → CSR + localStorage/cookie, synced by a
                       Server Action
Checkout             → Server Actions (create order) + Route
                       Handler (payment provider webhook)
Account, orders      → SSR (cookies() for the session)
Admin                → CSR, separate auth, runtime: 'nodejs'
```

## The strongest senior answer

Asked "what matters most in a production Next.js app", a weak answer lists features: SSR (server-side rendering), ISR (incremental static regeneration), Server Actions.

A strong answer says there is no single "correct" model. A production app is a *composition* of rendering, caching, and runtime decisions made **per screen**. The inputs to each decision are SEO (search engine optimization) requirements, data freshness, latency, and compute cost.

The architect's job isn't "picking a Next.js feature". It is making sure that composition is explicit and documented. Otherwise it decays into `cache: 'no-store'` scattered around reactively, one line per stale-data bug.

## Common interview mistakes

- **"Next.js fully replaces the backend"** — no. In most production architectures Next is a rendering and BFF layer, not the source of truth for business logic and data.

- **"Server Actions are just a new way to write APIs"** — no. Their invocation model is different: tied to specific forms and components, with no stable public contract. Their use cases differ from Route Handlers too.

- **Not knowing the Edge Runtime constrains your choice of ORM and DB drivers** — standard Prisma with `pg` needs an adapter to run on Edge. This is a common cause of "runtime errors in prod that didn't happen locally".

- **"NEXT_PUBLIC_ variables can be changed at runtime without a rebuild"** — no, they're inlined into the bundle at `next build` time. Changing them requires a rebuild.

- **Giving one answer to "how would you cache this site" without distinguishing screens** — a strong answer is a "page type → strategy" table. A single solution for the whole app isn't one.

- **Not mentioning that Server Component errors are invisible in the browser** — this matters for observability. Without server-side error tracking, a chunk of production bugs stays completely invisible to the team.

- **"Static export (`output: 'export'`) supports all App Router features"** — no. It excludes Server Actions, dynamic Route Handlers, the Image Optimization API, and any server-side dynamism. It is effectively a "static-only" mode.
