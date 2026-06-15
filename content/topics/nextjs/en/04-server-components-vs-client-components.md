# Server Components vs Client Components

## SSR ≠ Server Components — the distinction that matters most

This is probably the most common point of confusion in Next.js interviews. SSR is about *when* (at which stage) HTML is generated. Server Components are about *where the component's code runs and whether it ships to the client bundle at all*.

```txt
SSR (Pages Router / Client Component with SSR):
  the component renders on the server into HTML
  → HTML is sent to the browser
  → the component's JS is ALSO sent
  → React hydrates it — the component "comes alive" in the browser

Server Component (App Router):
  the component renders on the server into HTML / RSC Payload
  → HTML is sent to the browser
  → this component's JS is NOT sent at all
  → no hydration happens for it — there's nothing to "wake up"
```

A Server Component isn't "the SSR version of a component" — it's a component that **doesn't exist on the client at all**. If it has no interactive parts, its code is simply unnecessary outside the server, and Next doesn't send it.

## Server Components — what they are and what they can do

By default, **every** component in `app/` is a Server Component. These are async functions that can talk to server resources directly:

```tsx
// app/users/page.tsx — Server Component (no 'use client')
import { db } from '@/lib/db';

export default async function UsersPage() {
  // Direct database query — no separate API layer needed
  const users = await db.user.findMany({ select: { id: true, name: true, email: true } });

  return (
    <ul>
      {users.map((u) => (
        <li key={u.id}>{u.name} — {u.email}</li>
      ))}
    </ul>
  );
}
```

Available:

```txt
fetch() with extended caching
direct database queries (Prisma, Drizzle, raw SQL)
filesystem access, env variables
reading cookies()/headers()
running "heavy" dependencies (markdown parsers, image processing)
  that shouldn't end up in the client bundle
```

Not available — because a Server Component has **no lifecycle in the browser**:

```tsx
// ❌ Compile/runtime error in a Server Component
export default function Page() {
  const [count, setCount] = useState(0); // useState unavailable
  useEffect(() => {});                     // useEffect unavailable
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
  // an event handler can't be passed as a prop — see serialization below
}
```

## Client Components — explicit opt-in

`'use client'` doesn't mean "make this component client-side" — it's a marker for a **module boundary**: everything imported from a file with this directive (and everything *that* module imports) joins the client dependency graph.

```tsx
// app/components/Counter.tsx
'use client';

import { useState } from 'react';

export function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount((c) => c + 1)}>{count}</button>;
}
```

An important, often-missed nuance: **the directive applies to the whole module and everything it imports**. If `Counter.tsx` imports a helper from `utils/date.ts`, that helper also ends up in the client bundle, even if it contains no browser APIs itself — it sits "downstream" of the `'use client'` boundary.

## Composing Server and Client components together

### Server → Client: allowed, and normal

```tsx
// app/products/page.tsx — Server Component
import { AddToCartButton } from './AddToCartButton'; // Client Component

export default async function ProductsPage() {
  const products = await getProducts();

  return (
    <ul>
      {products.map((p) => (
        <li key={p.id}>
          {p.name} — ${p.price}
          <AddToCartButton productId={p.id} /> {/* data passed as props */}
        </li>
      ))}
    </ul>
  );
}
```

### Client → Server: not directly, but there's a "slots" pattern via children

You **can't** import a Server Component directly inside a Client Component — at the moment the Client Component renders on the client, it has no access to the server resources the imported component would need. But you can pass a Server Component as `children`/a prop *while still on the server*, before crossing the boundary:

```tsx
// app/components/ClientWrapper.tsx
'use client';

export function ClientWrapper({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setIsOpen((v) => !v)}>Toggle</button>
      {isOpen && children}
    </div>
  );
}

// app/page.tsx — Server Component
import { ClientWrapper } from './components/ClientWrapper';
import { ServerOnlyContent } from './ServerOnlyContent'; // Server Component

export default function Page() {
  return (
    <ClientWrapper>
      <ServerOnlyContent /> {/* rendered on the server BEFORE being passed to ClientWrapper */}
    </ClientWrapper>
  );
}
```

`ServerOnlyContent` renders on the server as part of the parent Server Component **before** its result (an RSC payload, not source code) is passed to `ClientWrapper` as `children`. From `ClientWrapper`'s perspective it's just an opaque React node — it doesn't "know" there was server code inside, and can't affect it (e.g. wrap it in a condition based on client state and force it to re-render on the server).

## What can cross the Server → Client boundary as props

The `'use client'` boundary is a **serialization boundary**. A Server Component serializes props into a special RSC format (JSON-like, but with support for `Promise`/`Date` and a few other types) that's sent to the client. This creates constraints:

```tsx
// ❌ Can't pass a function — functions don't serialize
<ClientButton onSave={() => saveToDb(id)} />

// ✅ OK: primitives, objects, arrays, Date, Promise (for streaming/Suspense)
<ClientButton productId={id} createdAt={product.createdAt} />

// ✅ OK: Server Actions are a special case — Next turns a reference
// to a server function into a protected "action id"
<form action={createOrder}>
  <ClientSubmitButton />
</form>
```

This is a common cause of the `Functions cannot be passed directly to Client Components` runtime error — usually it happens when a developer passes a callback from a Server Component out of habit, the way you would in plain React.

## `server-only` and protecting against accidental imports

Because the `'use client'` boundary is determined by the *import graph*, it's easy to accidentally pull server code (with secrets, direct DB access) into the client bundle — a simple example: a utility file with a function that reads `process.env.DB_PASSWORD` gets imported by both a Server and a Client component.

The `server-only` package (and its counterpart `client-only`) adds build-time protection:

```ts
// lib/db.ts
import 'server-only';

export const db = new PrismaClient();
```

If this module ends up in a Client Component's dependency graph, the build fails with an explicit error instead of leaking secrets into the production bundle.

## Why Server Components are faster — the concrete mechanisms

```txt
1. Less JS in the bundle
   Client Component  → HTML + the component's JS + dependencies (ship to the bundle)
   Server Component  → only the render result (HTML/RSC payload), 0 bytes of JS

2. Less hydration work
   Every Client Component requires React, during hydration, to reconcile
   the server HTML with a virtual DOM and attach event handlers.
   Server Component — no hydration at all, no client CPU cost.

3. Direct data access
   A Server Component can hit the database directly — no extra
   "browser → API → DB" round trip that a Client Component would need.

4. Heavy dependencies never reach the client
   E.g. a markdown parser (remark/rehype) or a formatting library
   is only used on the server — the client doesn't pay for its weight.
```

## Composition pattern: "maximize Server, minimize Client"

The recommended strategy is to push the `'use client'` boundary as far down the tree as possible, keeping only the parts that genuinely need interactivity client-side:

```txt
ProductsPage (Server)
 └─ ProductList (Server)        — renders the list, fetches data
     └─ ProductCard (Server)     — static card
         └─ AddToCartButton (Client) — needs onClick → useState/useTransition
```

The anti-pattern is marking `'use client'` at the top level "for convenience" (e.g. because something deep inside needs one interactive element). This turns the entire subtree into a Client Component — including all the data fetching, which now has to be rewritten via `useEffect`/react-query, and all the dependency weight.

## Context and providers — unavoidably Client

React Context (via `useContext`/`createContext` with state) only works in the browser, so theme providers, React Query, auth state, etc. must be Client Components — but they're usually isolated into a thin layer at the root of the tree:

```tsx
// app/providers.tsx
'use client';

import { ThemeProvider } from 'next-themes';

export function Providers({ children }: { children: React.ReactNode }) {
  return <ThemeProvider attribute="class">{children}</ThemeProvider>;
}

// app/layout.tsx — Server Component
import { Providers } from './providers';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers> {/* children can be a Server Component */}
      </body>
    </html>
  );
}
```

Important: `RootLayout` itself stays a Server Component — the `'use client'` boundary is localized to `Providers`, and anything passed as `children` can remain server-rendered thanks to the "slots" pattern described above.

## Common interview mistakes

- **"Server Components are just a new name for SSR"** — no. An SSR component in the Pages Router still hydrates and ships its JS to the client. A Server Component never ships JS at all — there's no concept of hydration for it.

- **"`'use client'` only makes that one component client-side"** — the directive defines a *module* boundary and applies to everything that module imports. It's easy to forget that helper utilities imported by a Client Component also end up in the bundle.

- **"You can just pass a function from a Server Component to a Client Component as a callback"** — no, props are serialized via the RSC protocol, and functions don't serialize (except the special case of Server Actions). This is a classic runtime error for people new to the App Router.

- **"If one element needs interactivity, mark the whole page `'use client'`"** — an anti-pattern that turns the entire subtree into client code. The right approach is to push interactivity down into a small leaf component.

- **"A Server Component can never be used inside a Client Component"** — it can, but only via the `children`/slots pattern: the Server Component renders on the server *before* crossing the boundary and is passed as an already-rendered React node, not as an importable component.

- **Not knowing about the `server-only`/`client-only` packages** — these are the standard way to enforce at build time that a module with secrets or browser APIs doesn't accidentally cross the boundary through an import chain.
