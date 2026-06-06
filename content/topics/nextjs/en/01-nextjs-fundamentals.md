# Next.js Fundamentals

## What is Next.js

Next.js is a Full-Stack React Framework.

---

Very important to understand:

```txt
React
≠
Next.js
```

---

React provides:

```txt
Components
Hooks
State
Virtual DOM
```

---

Next.js is built on top of React and adds:

```txt
Routing
SSR
SSG
ISR
Middleware
API Routes
Image Optimization
SEO
Caching
```

---

# Why Next.js Was Created

To solve the problems of SPA.

---

# Problem #1

SEO.

---

A typical React SPA:

```html
<body>
  <div id="root"></div>
</body>
```

---

A search crawler sees an almost empty page.

---

This was especially problematic in the past.

---

# Problem #2

Large First Load.

---

In a SPA the process is:

```txt
HTML
↓
JS Bundle Download
↓
React Mount
↓
API Requests
↓
Render
```

---

The user waits a long time.

---

# Problem #3

Data Fetching.

---

React for a long time gave no answer to:

```txt
When to fetch data?
Where to fetch data?
```

---

Every team solved it differently.

---

# What Next.js Provides

Next allows rendering a page:

```txt
on the server
at build time
partially
dynamically
```

---

# Next.js = Opinionated Framework

A very common interview question.

---

What does it mean:

```txt
Opinionated
```

---

The framework prescribes:

```txt
project structure
routing
rendering model
data fetching
```

---

Instead of complete freedom.

---

# Fullstack Framework

The next common question.

---

Why Fullstack?

---

Because Next contains:

```txt
Frontend
Backend
```

---

For example:

```txt
React Components
```

---

And at the same time:

```txt
API Routes
Server Actions
Middleware
```

---

# Main Parts of Next.js

Simplified:

```txt
Routing
Rendering
Data Fetching
Caching
Optimization
```

---

# Routing

Next automatically builds routes.

---

For example:

```txt
pages/about.tsx
```

---

Becomes:

```txt
/about
```

---

# Code Splitting

A very important topic.

---

In a React SPA:

```txt
1 large bundle
```

---

In Next:

```txt
bundle per route
```

---

The user downloads only the code they need.

---

# Built-In Optimizations

Next includes:

```txt
Image Optimization
Font Optimization
Code Splitting
Tree Shaking
Minification
Streaming
```

---

# API Routes

You can write backend code directly inside Next.

---

For example:

```ts
/api/users
```

---

You get:

```txt
Backend Endpoint
```

---

# Middleware

Allows executing code before the page renders.

---

Examples:

```txt
Authentication
Geo Routing
A/B Testing
Redirects
```

---

# Why Companies Love Next.js

One project:

```txt
Frontend
+
Backend
+
SSR
+
SEO
```

---

Instead of multiple services.

---

# React vs Next

React:

```txt
UI Library
```

---

Next:

```txt
Application Framework
```

---

# The Most Important Idea

Next.js does not replace React.

---

Next uses React as its rendering engine.

---

# Interview Answer

Next.js is a full-stack framework built on top of React that solves problems of SEO, first-load performance, routing, data fetching, and server-side rendering. It provides built-in mechanisms for SSR, SSG, ISR, routing, caching, and backend functionality through API Routes and Server Actions.
