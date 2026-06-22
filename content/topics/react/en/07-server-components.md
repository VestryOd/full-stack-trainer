# Server Components

## The mental model shift

Before React Server Components (RSC), React always ran on the client. Server-side rendering (SSR) meant "run the same React code on the server to produce HTML, then rehydrate it on the client." The code was identical — it ran in both environments.

RSC introduces a fundamental split:

```txt
BEFORE RSC:
  All components run on the client.
  SSR = run client components on the server too (for initial HTML).
  Every component ships its JS to the browser.

WITH RSC:
  Server Components run ONLY on the server.
  Client Components run on the client (and also on the server for SSR).
  Server Components never ship their code to the browser.
  The boundary between them is explicit: 'use client'.
```

This is not just a performance optimization — it is a different way of thinking about where code lives.

---

## What runs where

```txt
SERVER COMPONENTS                       CLIENT COMPONENTS
─────────────────────────────────────   ────────────────────────────────────
Run: server only (build time or request time)
                                        Run: browser + server (for SSR)
Can: async/await directly               Can: useState, useEffect, event handlers
Can: access DB, filesystem, env vars    Can: use browser APIs (window, localStorage)
Can: import heavy server-only libs      Can: use refs, context (as provider or consumer)
     (no bundle size impact)
Cannot: useState, useEffect             Cannot: access DB/filesystem directly
Cannot: browser APIs                    Cannot: async component body (currently)
Cannot: event handlers                  Cannot: import server-only modules
```

```tsx
// SERVER COMPONENT — runs on the server, result is serialized and sent to the client
// No 'use client' = server component by default in Next.js App Router

import { db } from '@/lib/db'; // db client — never sent to the browser

async function ProductList() {
  const products = await db.product.findMany(); // direct DB access, no API needed

  return (
    <ul>
      {products.map(p => (
        <li key={p.id}>
          {p.name} — ${p.price}
          <AddToCartButton productId={p.id} /> {/* Client Component */}
        </li>
      ))}
    </ul>
  );
}
```

```tsx
// CLIENT COMPONENT — runs on the browser (and also on the server for SSR)
'use client';

import { useState } from 'react';

function AddToCartButton({ productId }: { productId: string }) {
  const [added, setAdded] = useState(false);

  return (
    <button onClick={() => setAdded(true)}>
      {added ? 'Added ✓' : 'Add to Cart'}
    </button>
  );
}
```

---

## The serialization boundary

When a Server Component renders a Client Component, it cannot pass arbitrary JavaScript objects across the boundary — only **serializable values**. The server produces a JSON-like wire format (the RSC payload) that the client deserializes.

```txt
SERVER                          WIRE FORMAT              CLIENT
──────────────────────────────────────────────────────────────
Server Component renders        →  RSC payload (JSON-like)  →  Client hydrates
                                   - React element trees
                                   - serialized props
                                   - references to Client
                                     Component chunks
```

**What can cross the serialization boundary (props from Server to Client Components):**

```tsx
// ✅ Serializable — safe to pass as props:
<ClientComp
  str="hello"
  num={42}
  bool={true}
  arr={[1, 2, 3]}
  obj={{ name: 'Alice' }}
  date={new Date().toISOString()} // serialize dates to strings
  node={<AnotherServerComponent />} // React elements ARE serializable
/>
```

**What CANNOT cross the boundary:**

```tsx
// ❌ Not serializable — cannot pass as props to Client Components:
<ClientComp
  fn={() => console.log('hi')}    // functions — not serializable
  classInstance={new MyClass()}   // class instances with methods
  symbol={Symbol('id')}           // Symbols
  map={new Map()}                 // Map, Set, WeakMap
  undefined={undefined}           // undefined (JSON doesn't have it)
/>
```

Functions cannot cross from server to client — they would need to be serialized as code, which is a security risk. This is why event handlers must live in Client Components.

### Passing children — the "lifting" pattern

The most powerful escape hatch: a Server Component can render a Client Component and pass *other Server Components* as `children`:

```tsx
// ✅ Server Component can be passed as children to a Client Component:
// This works because children are React elements — serializable.

// ServerPage.tsx (Server Component):
import { ClientShell } from './ClientShell';
import { HeavyServerComponent } from './HeavyServerComponent';

export default function Page() {
  return (
    <ClientShell>
      <HeavyServerComponent /> {/* Server Component passed as children */}
    </ClientShell>
  );
}

// ClientShell.tsx (Client Component):
'use client';
import { useState } from 'react';

export function ClientShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(!open)}>Toggle</button>
      {open && children} {/* children is already rendered HTML from the server */}
    </div>
  );
}
```

`HeavyServerComponent` runs on the server and is serialized into the RSC payload as a React element. `ClientShell` receives it as `children` — a serialized subtree — not as a function it can call. The server component's code never reaches the browser.

---

## When 'use client' is required

`'use client'` is a **boundary marker**, not a "this component must run on the client" directive. It marks the point where the server component tree ends and the client component tree begins.

```tsx
// 'use client' is required when the component uses:

// 1. React state:
'use client';
const [count, setCount] = useState(0);

// 2. React effects:
'use client';
useEffect(() => { ... }, []);

// 3. Browser APIs:
'use client';
const width = window.innerWidth;

// 4. Event handlers (because they need closures with setState):
'use client';
<button onClick={handleClick}>

// 5. Context consumers (useContext):
'use client';
const theme = useContext(ThemeContext);

// 6. useRef, useReducer, useCallback, useMemo:
'use client';
const ref = useRef(null);
```

**'use client' propagates downward:** once a component is a Client Component, all components it imports are also treated as Client Components — even if they don't have `'use client'` themselves. The directive marks the root of a client subtree, not individual components.

```txt
Page (Server) ─── imports ──▶ ProductList (Server) ─── imports ──▶ AddToCart ('use client')
                                                                      └── Button (no directive)
                                                                            ↑ implicitly Client
                                                                              (imported by Client)
```

### The 'use server' directive

`'use server'` marks a function as a **Server Action** — a function that can be called from the client but runs on the server:

```tsx
// In a Server Component file:
async function createUser(formData: FormData) {
  'use server'; // this function runs on the server

  const name = formData.get('name') as string;
  await db.user.create({ data: { name } });
  revalidatePath('/users');
}

export default function NewUserForm() {
  return (
    <form action={createUser}>
      <input name="name" type="text" />
      <button type="submit">Create</button>
    </form>
  );
}
```

Or in a dedicated actions file with `'use server'` at the top:

```tsx
// actions.ts
'use server'; // all exports from this file are Server Actions

export async function deletePost(id: string) {
  await db.post.delete({ where: { id } });
  revalidatePath('/posts');
}

export async function updatePost(id: string, data: Partial<Post>) {
  await db.post.update({ where: { id }, data });
  revalidatePath(`/posts/${id}`);
}
```

Server Actions look like regular async functions but execute on the server. When called from a Client Component, they serialize their arguments, send an HTTP POST request to the server, execute, and return a serialized result. The client never sees the server-side code.

---

## Streaming SSR explained

Traditional SSR: the server renders the entire page to HTML, sends it all at once, then the client downloads JS and hydrates everything.

```txt
TRADITIONAL SSR:
  Server:  ──────────────── render all ────────────── send HTML ──▶
  Client:  ──────────────────────────────── receive ── hydrate ──▶
  TTFB:    long (must render everything before sending anything)
```

Streaming SSR (React 18): the server sends HTML in chunks as components finish rendering. The client starts rendering and hydrating as soon as the first chunk arrives.

```txt
STREAMING SSR (React 18):
  Server:  ── send shell ─── render A ─ send A ─── render B ─ send B ──▶
  Client:  ── receive & show shell ── receive & hydrate A ── receive & hydrate B ──▶
  TTFB:    fast (shell is sent immediately)
```

Suspense boundaries are the streaming split points:

```tsx
// Next.js App Router — streaming is automatic with Suspense:
export default async function Page() {
  return (
    <div>
      <Header />           {/* renders immediately — in the initial shell */}

      <Suspense fallback={<Skeleton />}>
        <SlowComponent />  {/* renders async — streamed when ready */}
      </Suspense>

      <Suspense fallback={<Skeleton />}>
        <AnotherSlow />    {/* renders async — streamed independently */}
      </Suspense>
    </div>
  );
}

async function SlowComponent() {
  await db.slowQuery();    // takes 800ms
  return <div>...</div>;
}
```

The browser receives and renders `<Header />` and both `<Skeleton />`s immediately (TTFB is fast). As each slow component finishes on the server, its HTML is streamed and injected into the page — Suspense boundaries are replaced with real content.

### Selective hydration

Streaming also enables selective hydration: the client can hydrate components in priority order. If the user clicks on a component that hasn't hydrated yet, React prioritizes hydrating it first (before hydrating other components that loaded before it).

---

## Hydration mismatch causes

Hydration is the process of the client-side React attaching event listeners and state to the server-rendered HTML. For hydration to succeed, the client must produce the exact same HTML that the server produced.

A **hydration mismatch** occurs when client and server render different output:

```tsx
// 1. Accessing browser-only APIs during render:
function Component() {
  // window is not defined on the server → renders '' on server, 'dark' on client
  const theme = window.localStorage.getItem('theme') ?? 'light';
  return <div className={theme}>...</div>;
}

// Fix: use useEffect (runs only on client) or a custom hook:
function Component() {
  const [theme, setTheme] = useState('light'); // same on server and client
  useEffect(() => {
    setTheme(localStorage.getItem('theme') ?? 'light'); // updates after hydration
  }, []);
  return <div className={theme}>...</div>;
}
```

```tsx
// 2. Date/time rendered differently on server and client:
function Timestamp() {
  return <span>{new Date().toLocaleTimeString()}</span>;
  // Server renders "10:30:00", client renders "10:30:01" → mismatch
}

// Fix: use a stable value or render time-sensitive data client-only:
function Timestamp() {
  const [time, setTime] = useState<string | null>(null);
  useEffect(() => {
    setTime(new Date().toLocaleTimeString());
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);
  }, []);
  return <span>{time}</span>; // null on server → no mismatch; updates on client
}
```

```tsx
// 3. Random values:
function Avatar() {
  const color = `#${Math.random().toString(16).slice(2, 8)}`; // different on server and client
  return <div style={{ background: color }} />;
}

// Fix: use a stable value derived from a prop (user ID, seed):
function Avatar({ userId }: { userId: string }) {
  const color = hashToColor(userId); // deterministic — same on server and client
  return <div style={{ background: color }} />;
}
```

```tsx
// 4. Conditional rendering based on browser-only info:
function Component() {
  if (typeof window !== 'undefined') {
    return <ClientOnlyContent />;
  }
  return null; // → different output on server vs client: null vs <ClientOnlyContent />
}

// Fix: use suppressHydrationWarning for known intentional mismatches,
// or use a mounted flag:
function Component() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null; // same on server and client (initially)
  return <ClientOnlyContent />;
}
```

### suppressHydrationWarning

For intentional, known mismatches (like a timestamp that will always differ), React provides an escape hatch:

```tsx
<time suppressHydrationWarning>
  {new Date().toLocaleTimeString()}
</time>
```

This suppresses the warning but does not prevent the mismatch — the client will still update the DOM after hydration. Use sparingly.

---

## RSC and bundle size

The most underappreciated benefit of Server Components: **zero client bundle contribution**.

```tsx
// This import stays on the server — NONE of it ships to the browser:
import { marked } from 'marked';           // 45 kB
import { highlight } from 'highlight.js';  // 200 kB
import { prisma } from '@/lib/prisma';     // + Prisma client

async function BlogPost({ slug }: { slug: string }) {
  const post = await prisma.post.findUnique({ where: { slug } });
  const html = marked(highlight(post!.content, { language: 'ts' }).value);
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
```

In a traditional client-side React app, importing `marked` and `highlight.js` would add ~245 kB to the JavaScript bundle. In a Server Component, these libraries execute on the server and only the rendered HTML is sent to the client.

---

## Common interview traps

**"Can a Server Component import a Client Component?"**
Yes. A Server Component can import and render a Client Component. The Client Component is included in the client bundle and hydrated on the browser. The reverse direction has restrictions: a Client Component cannot import a Server Component (the import would fail because server-only code like `fs`, `db`, or `'server-only'` imports cannot run in the browser). A Client Component *can* receive a Server Component as `children` — passed as an already-rendered serialized element.

**"Can a Server Component use useState?"**
No. Server Components have no lifecycle and no state — they run once on the server and produce static output. If you need interactivity, that piece must be a Client Component. The split is: data fetching and static rendering → Server Component; interactivity, state, effects → Client Component.

**"What is the RSC payload?"**
When a Server Component tree renders, React serializes the output into a special JSON-like wire format (the RSC payload). It contains: the virtual DOM tree from the server render, references to Client Component chunks (so the client knows which JS to load), and serialized props. The client receives this payload, uses it to render the Client Component tree, and hydrates the result against the server-generated HTML. It is not the same as the server-sent HTML — the RSC payload is consumed by the React runtime, not by the browser's HTML parser.

**"Does 'use client' mean the component only runs on the client?"**
No. Client Components run on the client AND on the server (for SSR/SSG). `'use client'` means: this component and its subtree use client-side React features (state, effects, browser APIs) and must be included in the client bundle. The `'use client'` directive marks the server/client boundary, not the "never run on server" boundary.

**"What is the difference between Server Actions and API routes?"**
API routes are explicit HTTP endpoints — you define the route, handle the request, parse the body, return a response. Server Actions are functions marked with `'use server'` that the framework automatically exposes as POST endpoints. You call them like normal functions from Client Components. The framework handles serialization, transport, and deserialization. Server Actions integrate with the React form model (`<form action={serverAction}>`) and can call `revalidatePath` / `revalidateTag` to invalidate cached data without a full page reload.
