# Routing, Layouts, and Middleware

## Routing in Next.js

One of the strongest features of Next.

---

Routes are built automatically.

---

Based on the folder structure.

---

# App Router

Example:

```txt
app/
 ├─ page.tsx
 ├─ about/
 │   └─ page.tsx
```

---

Routes:

```txt
/
/about
```

---

# Dynamic Routes

A very popular question.

---

Structure:

```txt
app/blog/[id]/page.tsx
```

---

Route:

```txt
/blog/123
```

---

We get:

```ts
params.id
```

---

# Nested Routes

```txt
app
 └─ dashboard
     └─ settings
         └─ page.tsx
```

---

Route:

```txt
/dashboard/settings
```

---

# Catch-All Routes

Example:

```txt
[...slug]
```

---

Suitable for:

```txt
CMS
Docs
Knowledge Base
```

---

Example URL:

```txt
/docs/react/hooks/useEffect
```

---

We get:

```ts
[
 'react',
 'hooks',
 'useEffect'
]
```

---

# Layout

The most important feature of App Router.

---

File:

```txt
layout.tsx
```

---

Wraps child pages.

---

Example:

```tsx
export default function Layout({
  children
}) {

  return (
    <>
      <Navbar />
      {children}
    </>
  );
}
```

---

# Root Layout

Mandatory.

---

```txt
app/layout.tsx
```

---

Equivalent to:

```html
<html>
<body>
```

---

at the application level.

---

# Nested Layouts

Interviewers love asking about this.

---

```txt
Root Layout
 ↓
Dashboard Layout
 ↓
Page
```

---

When navigating:

```txt
Dashboard → Settings
```

---

Dashboard Layout is not unmounted.

---

# Why This Matters

Less:

```txt
rerender
network requests
UI flickering
```

---

# Template

Rarely asked about.

---

But useful to know.

---

```txt
template.tsx
```

---

Similar to layout.

---

But:

```txt
remounts
on every navigation
```

---

# Loading UI

A very cool feature.

---

```txt
loading.tsx
```

---

Shown automatically.

---

While the page loads.

---

# Error Boundary

Built in.

---

```txt
error.tsx
```

---

Catches errors
for a specific route segment.

---

# Not Found

```txt
not-found.tsx
```

---

Automatic 404.

---

# Middleware

A very popular Senior question.

---

Middleware runs:

```txt
before routing
before rendering
```

---

# Where It Lives

```txt
middleware.ts
```

---

In the project root.

---

# Example

```ts
export function middleware(req) {

  return NextResponse.next();
}
```

---

# What Middleware Can Do

```txt
redirect
rewrite
auth
geo routing
ab testing
cookies
headers
```

---

# Authentication

The most common use case.

---

```ts
if (!token) {

  return NextResponse.redirect(
    '/login'
  );
}
```

---

# Rewrite

Interviewers love asking about this.

---

Redirect:

```txt
URL changes
```

---

Rewrite:

```txt
URL stays the same
```

---

Example:

```txt
/blog
```

---

We actually serve:

```txt
/news
```

---

The user does not notice.

---

# Geo Routing

Example.

---

User from:

```txt
Germany
```

---

Gets:

```txt
/de
```

---

User from:

```txt
France
```

---

Gets:

```txt
/fr
```

---

# A/B Testing

Middleware can distribute:

```txt
Variant A
Variant B
```

---

Before the page renders.

---

# Middleware Limitations

A very popular question.

---

Middleware runs on:

```txt
Edge Runtime
```

---

Therefore:

```txt
no access to Node API
```

---

For example:

```txt
fs
net
child_process
```

---

are unavailable.

---

# When to Use Middleware

Good for:

```txt
Auth
Redirects
Headers
Localization
A/B Tests
```

---

Bad for:

```txt
heavy business logic
database work
```

---

# Interview Answer

Routing in App Router is file-system based and supports dynamic, nested, and catch-all routes. Layouts allow preserving shared UI between navigations and reduce the number of re-renders. Middleware runs before the page renders and is used for authorization, redirects, localization, and A/B testing.
