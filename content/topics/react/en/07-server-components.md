# Server Components

## The mental model shift

Before React Server Components (RSC), React always ran on the client. Server-side rendering (SSR) meant one thing: run the same React code on the server to produce HTML. The client then rehydrated that HTML, attaching event handlers and state to the markup the server had sent. The code was identical, and it ran in both environments.

RSC introduces a fundamental split:

```txt
BEFORE RSC:
  All components run on the client.
  SSR = run client components on the server too (for initial HTML).
  Every component ships its JS to the browser.

WITH RSC:
  Server Components run ONLY on the server.
  Client Components run on the client, and on the server for SSR.
  Server Components never ship their code to the browser.
  The boundary between them is explicit: 'use client'.
```

This is not just a performance optimization — it is a different way of thinking about where code lives.

---

## What runs where

| | Server Components | Client Components |
|---|---|---|
| Runs on | server only, at build or request time | browser, plus the server for SSR |
| `useState`, `useEffect` | no | yes |
| Event handlers | no | yes |
| Browser APIs (`window`, `localStorage`) | no | yes |
| `async`/`await` in the component body | yes | no, not supported yet |
| Database, filesystem, env vars | direct access | no direct access |
| Heavy server-only libraries | yes, and no bundle cost | no |
| Refs and context | no | yes, as provider or consumer |

A **server-only** module is one that must never reach the browser: a database client, a file reader, a module holding a secret key.

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

When a Server Component renders a Client Component, it cannot pass arbitrary JavaScript objects across the boundary. Only **serializable values** may cross. The server produces the RSC payload: a JSON-like **wire format**, which means the shape the data takes while it travels over the network. The client deserializes that payload.

```txt
Server                     wire format                Client
────────────────────────────────────────────────────────────
Server Component  ──▶  RSC payload (JSON-like)  ──▶  client
renders                                              hydrates
                       - React element trees
                       - serialized props
                       - references to Client Component chunks
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

**What cannot cross the boundary:**

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

**'use client' propagates downward.** Once a component is a Client Component, every component it imports becomes one too. That holds even when those components carry no `'use client'` of their own. The directive marks the root of a client subtree, not individual components.

```txt
Page (Server)
  → imports ProductList (Server)
      → imports AddToCart ('use client')   ← the boundary
          → imports Button (no directive)

Button has no directive of its own. A Client Component imported it,
so Button is a Client Component too.
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

Traditional SSR: the server renders the entire page to HTML, sends it all at once, then the client downloads JS and hydrates everything. The metric this hurts is TTFB — time to first byte, the delay before the first byte of the response reaches the browser.

```txt
Traditional SSR
  Server: ──── render the whole page ──── send all HTML ──▶
  Client: ──────────────────── receive ──── hydrate ──▶

  TTFB is long: nothing is sent until everything is rendered.
```

Streaming SSR (React 18): the server sends HTML in chunks as components finish rendering. The client starts rendering and hydrating as soon as the first chunk arrives. The first chunk is the **shell** — the part of the page that does not wait for any data.

```txt
Streaming SSR (React 18)
  Server: send shell ─ render A ─ send A ─ render B ─ send B ──▶
  Client: show shell ─── hydrate A ────────── hydrate B ──▶

  TTFB is short: the shell goes out immediately.
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

Streaming also enables selective hydration: the client can hydrate components in priority order.

```txt
The user clicks a component that is not hydrated yet

  React moves that component to the front of the queue
  and hydrates it before the ones that loaded earlier.
```

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
  const color = `#${Math.random().toString(16).slice(2, 8)}`; // differs per run
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

This suppresses the warning but does not prevent the mismatch. The client will still update the DOM — the Document Object Model, the tree of objects the browser builds from the page — after hydration. Use it sparingly.

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
Yes. A Server Component can import and render a Client Component. That Client Component goes into the client bundle and is hydrated in the browser.

```txt
Server Component  ── imports ──▶  Client Component    ✓
Client Component  ── imports ──▶  Server Component    ✗
Client Component  ◀─ children ──  Server Component    ✓
```

The reverse direction is restricted. A Client Component cannot import a Server Component — the import fails. Server-only code such as `fs`, `db` or a `'server-only'` import cannot run in the browser. A Client Component *can* receive a Server Component as `children`, which arrives as an already-rendered, serialized element.

**"Can a Server Component use useState?"**
No. Server Components have no lifecycle and no state — they run once on the server and produce static output. If you need interactivity, that piece must be a Client Component.

```txt
data fetching, static rendering  →  Server Component
interactivity, state, effects    →  Client Component
```

**"What is the RSC payload?"**
It is the serialized output of a Server Component tree — the JSON-like wire format React sends to the client. It carries three kinds of rows:

```txt
RSC payload — simplified shape

  tree    ["$","ul",null,{"children":[ ... ]}]
          the virtual DOM tree the server render produced

  client  a reference to the chunk holding <AddToCartButton>
          tells the client which JS file to load

  props   {"productId":"42"}
          the serialized props for that Client Component
```

The client takes the payload, renders the Client Component tree from it, and hydrates the result against the server-generated HTML. The payload is not the same thing as the HTML the server sent. It is consumed by the React runtime, not by the browser's HTML parser.

**"Does 'use client' mean the component only runs on the client?"**
No. Client Components run on the client **and** on the server. On the server they run for SSR, and for SSG — static site generation, rendering pages to HTML at build time.

`'use client'` means something narrower. This component and its subtree use client-side React features: state, effects, browser APIs. So they must be included in the client bundle. The directive marks the server/client boundary, not a "never run on the server" boundary.

**"What is the difference between Server Actions and API routes?"**
API routes are explicit HTTP endpoints. You define the route, handle the request, parse the body and return a response. Server Actions are functions marked with `'use server'`, and the framework exposes them as POST endpoints for you.

| | API route | Server Action |
|---|---|---|
| How you define it | a route file with a request handler | a function marked `'use server'` |
| How you call it | `fetch` to a URL | like a normal function |
| Serialization and transport | you write it | the framework does it |
| Works without JavaScript | no | yes, through `<form action={...}>` |
| Cache invalidation | your own code | `revalidatePath` / `revalidateTag` |
| Best for | public APIs used by third parties | internal form submits and mutations |

Because a Server Action can call `revalidatePath` or `revalidateTag` itself, it can invalidate cached data without a full page reload.
