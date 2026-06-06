# Server Components vs Client Components

## The Most Popular Topic in Modern Next.js

Many developers confuse:

```txt
SSR
```

and

```txt
Server Components
```

---

These are NOT the same thing.

---

# What is a Server Component

A component that executes only on the server.

---

It never reaches the browser.

---

Example:

```tsx
export default async function Page() {

  const users =
    await getUsers();

  return (...);
}
```

---

This is a Server Component.

---

# What This Means

```txt
code runs on the server
```

---

After rendering:

```txt
HTML is sent to the client
```

---

But the component itself:

```txt
never reaches the browser
```

---

# What is a Client Component

A component that executes in the browser.

---

You need to explicitly mark it:

```tsx
'use client';
```

---

Example:

```tsx
'use client';

export default function Counter() {

  const [count, setCount] =
    useState(0);

  ...
}
```

---

# Why 'use client' is Needed

Because App Router considers:

```txt
all components to be Server Components
```

by default.

---

# What You Cannot Use in a Server Component

A very popular question.

---

Cannot use:

```txt
useState
useEffect
useRef
window
document
event handlers
```

---

For example:

```tsx
<button onClick={...}>
```

---

Error.

---

# Why Not

Because the component
does not exist in the browser.

---

# What You Can Use in a Server Component

Can use:

```txt
fetch()
database queries
server logic
filesystem
env variables
```

---

A very powerful capability.

---

# Example

```tsx
const users =
  await prisma.user.findMany();
```

---

No API.

No fetch.

No additional backend.

---

# A Big Advantage

Less JavaScript.

---

Client Component:

```txt
HTML
+
JS
```

---

Server Component:

```txt
HTML only
```

---

Smaller bundle.

---

Faster loading.

---

# Composition Pattern

A very popular question.

---

The recommended approach:

```txt
maximize Server Components
minimize Client Components
```

---

Example:

```txt
Page
 ↓
ProductList
 ↓
ProductCard
 ↓
AddToCartButton
```

---

The first three:

```txt
Server Components
```

---

The last one:

```txt
Client Component
```

---

Because it needs:

```txt
onClick
```

---

# SSR vs Server Components

The most popular question.

---

SSR:

```txt
renders on the server
BUT
the component is then hydrated
in the browser
```

---

Server Component:

```txt
never
runs
in the browser
```

---

A very big difference.

---

# Passing Data

Server Component:

```tsx
<UserList users={users} />
```

---

Passes data down.

---

Client Component receives:

```txt
regular props
```

---

# Can You Import Client into Server?

Yes.

---

This is done very often.

---

```txt
Server
 ↓
Client
```

---

# Can You Import Server into Client?

No.

---

Because the browser cannot execute server code.

---

# Common Question

Why are Server Components faster?

---

Reasons:

```txt
less JS
less hydration
smaller bundle
data is closer to the server
```

---

# Common Question

When to use a Client Component?

---

When you need:

```txt
useState
useEffect
browser APIs
event handlers
```

---

# Common Question

When to use a Server Component?

---

Almost always.

---

Especially for:

```txt
Data Fetching
SEO Pages
Static Content
Lists
Tables
```

---

# Interview Answer

Server Components run only on the server and never appear in the client JavaScript bundle. They are ideal for data fetching and displaying content. Client Components run in the browser and are used for interactivity, state, and working with browser APIs. In App Router all components are Server Components by default, and Client Components are marked with the `'use client'` directive.
