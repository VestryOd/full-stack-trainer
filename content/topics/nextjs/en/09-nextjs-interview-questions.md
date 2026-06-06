# Next.js Interview Questions (Middle → Senior)

---

# 1. What is Next.js?

Next.js is a full-stack framework built on top of React.

Provides:

- Routing
- SSR
- SSG
- ISR
- API Routes
- Middleware
- Caching
- SEO tools

---

# 2. What React problems does Next.js solve?

- SEO
- Routing
- SSR
- Data Fetching
- Code Splitting
- Performance Optimization

---

# 3. Why is Next.js called a Fullstack Framework?

Because it contains:

```txt
Frontend
+
Backend
```

through:

- API Routes
- Server Actions
- Middleware

---

# 4. How does React differ from Next.js?

React:

```txt
UI Library
```

---

Next.js:

```txt
Application Framework
```

---

# 5. What is Rendering?

The process of generating HTML.

---

# 6. What is CSR?

Client Side Rendering.

HTML is created in the browser after JavaScript loads.

---

# 7. What is SSR?

Server Side Rendering.

HTML is created on the server on every request.

---

# 8. What is SSG?

Static Site Generation.

HTML is created at build time.

---

# 9. What is ISR?

Incremental Static Regeneration.

Allows regenerating static pages after deployment.

---

# 10. When to use SSR?

When you need:

- personalized data
- up-to-date data
- SEO

---

# 11. When to use SSG?

For:

- blogs
- landing pages
- documentation

---

# 12. When to use ISR?

For:

- online stores
- catalogs
- CMS content

---

# 13. What is Hydration?

The process of connecting React to already-existing HTML.

---

# 14. What is Hydration Mismatch?

When server HTML differs from client HTML.

---

# 15. Main causes of Hydration Mismatch?

```tsx
Date.now()
Math.random()
window
localStorage
```

during rendering.

---

# 16. What is App Router?

The new routing architecture of Next.js.

Built around:

- Server Components
- Streaming
- Nested Layouts

---

# 17. What is Pages Router?

The old routing system using the folder:

```txt
pages/
```

---

# 18. The main difference of App Router?

Server Components by default.

---

# 19. What is a Server Component?

A component that runs only on the server.

---

# 20. What is a Client Component?

A component that runs in the browser.

---

# 21. How do you mark a Client Component?

```tsx
'use client';
```

---

# 22. What cannot be used in Server Components?

- useState
- useEffect
- useRef
- window
- document
- event handlers

---

# 23. What can be used in Server Components?

- fetch
- database queries
- server code
- environment variables

---

# 24. Why are Server Components faster?

Because:

- less JS
- less hydration
- smaller bundle size

---

# 25. How does SSR differ from Server Components?

SSR answers:

```txt
Where is HTML created
```

---

Server Components:

```txt
Where React code runs
```

---

# 26. How does Data Fetching work in App Router?

Via:

```tsx
await fetch()
```

inside Server Components.

---

# 27. How does Next fetch differ from browser fetch?

Integrated with:

- caching
- revalidation
- rendering

---

# 28. What does cache: 'force-cache' do?

Uses the cached result.

---

# 29. What does cache: 'no-store' do?

Disables caching.

---

# 30. What is revalidate?

The cache lifetime.

---

Example:

```ts
revalidate: 60
```

---

# 31. What is revalidatePath?

Invalidates the cache for a specific route.

---

# 32. What is revalidateTag?

Invalidates the cache for a group of requests.

---

# 33. What is generateStaticParams?

Equivalent to getStaticPaths.

---

Used to generate dynamic routes at build time.

---

# 34. What does cookies() do?

Allows reading cookies on the server.

---

Using cookies() makes the page dynamic.

---

# 35. What does headers() do?

Allows reading HTTP headers on the server.

---

# 36. What is Dynamic Rendering?

When a page is rendered on every request.

---

# 37. What is Request Memoization?

Repeated fetch calls within a single render are not re-executed.

---

# 38. What is a Layout?

A wrapper component for a group of routes.

---

# 39. What is a Nested Layout?

Multiple nested layout levels.

---

For example:

```txt
Root Layout
 ↓
Dashboard Layout
 ↓
Page
```

---

# 40. Why is Layout better than a regular component?

It is not unmounted during navigation.

---

# 41. What is loading.tsx?

Automatic Loading UI.

---

# 42. What is error.tsx?

An Error Boundary for a route segment.

---

# 43. What is not-found.tsx?

A custom 404 page.

---

# 44. What is Middleware?

Code that runs before routing and rendering.

---

# 45. Where does Middleware live?

```txt
middleware.ts
```

---

# 46. What is Middleware used for?

- Auth
- Redirects
- A/B Tests
- Geo Routing
- Localization

---

# 47. How does rewrite differ from redirect?

Redirect:

```txt
changes the URL
```

---

Rewrite:

```txt
keeps the URL the same
```

---

# 48. What is the Metadata API?

The built-in SEO system.

---

# 49. How do you set the page title?

```ts
export const metadata = {
  title: 'Products'
}
```

---

# 50. What is generateMetadata()?

Allows creating SEO metadata dynamically.

---

# 51. What is OpenGraph?

Metadata for social networks.

---

# 52. What is robots.txt?

Site indexing rules for search engines.

---

# 53. What is sitemap.xml?

A list of site pages for search engines.

---

# 54. What is next/image?

An image optimization component.

---

Automatically provides:

- lazy loading
- responsive images
- optimization

---

# 55. What is next/font?

Built-in font optimization.

---

# 56. Which Core Web Vitals do you know?

- LCP
- CLS
- INP

---

# 57. What is Streaming?

Sending HTML in chunks.

---

# 58. What is Suspense?

A mechanism for showing fallback UI while waiting for data.

---

# 59. What are Server Actions?

A way to run server code without API Routes.

---

Example:

```tsx
'use server';
```

---

# 60. When to use Server Actions?

For:

- forms
- CRUD operations
- internal mutations

---

# 61. When is it better to use API Routes?

For:

- REST API
- Webhooks
- external integrations

---

# 62. What is Edge Runtime?

Running code on Edge Nodes.

---

Closer to the user.

---

# 63. What are the limitations of Edge Runtime?

No access to:

- fs
- net
- child_process

---

# 64. What is BFF?

Backend For Frontend.

---

Next aggregates data from multiple services.

---

# 65. How would you build an e-commerce?

```txt
Homepage → SSG

Catalog → ISR

Product → ISR

Cart → CSR

Checkout → Server Actions

Admin → CSR
```

---

# 66. How would you build a CMS project?

```txt
Next.js
 ↓
Strapi
 ↓
PostgreSQL
```

---

ISR + revalidateTag.

---

# 67. How would you explain the architecture of modern Next.js?

Modern Next.js is built around App Router, React Server Components, built-in Data Fetching, caching, and Streaming. Most logic runs on the server, and Client Components are used only where interactivity is needed.

---

# 68. The Most Popular Senior Question

Which rendering model should you choose for an application?

Answer:

There is no single correct model. A production application typically combines SSG, ISR, SSR, Server Components, and Client Components depending on the requirements for SEO, performance, data freshness, and user experience.
