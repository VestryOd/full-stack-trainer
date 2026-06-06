# SEO, Metadata, and Performance

## Why SEO Matters for Next.js

One of the main reasons Next.js was created:

```txt
SEO
```

---

A typical React SPA:

```html
<body>
  <div id="root"></div>
</body>
```

---

A search crawler gets an almost empty page.

---

SSR and SSG solve this problem.

---

# What You Need for SEO

Minimum set:

```txt
Title
Description
Canonical
OpenGraph
Robots
Sitemap
Structured Data
```

---

# Metadata API

The modern way in App Router.

---

Example:

```ts
export const metadata = {
  title: 'Products',
  description: 'Product Catalog',
};
```

---

Next automatically creates:

```html
<title>Products</title>

<meta
  name="description"
/>
```

---

# Dynamic Metadata

A very popular question.

---

Example:

```tsx
export async function
generateMetadata({ params }) {

  const product =
    await getProduct(
      params.id
    );

  return {
    title: product.name,
  };
}
```

---

For each product:

```txt
its own title
```

---

# OpenGraph

Controls link previews.

---

For example:

```txt
Facebook
LinkedIn
Telegram
Slack
```

---

Example:

```ts
export const metadata = {

  openGraph: {
    title: 'Product',
    description: 'Details',
    images: ['/cover.jpg']
  }
};
```

---

# Twitter Cards

Similar mechanism.

---

Used by Twitter/X.

---

# Canonical URL

A very popular question.

---

Problem:

```txt
/product/1

/product/1?sort=asc
```

---

Same content.

---

Search engine considers:

```txt
duplicates
```

---

Solution:

```html
<link rel="canonical" />
```

---

# robots.txt

Tells search engines:

```txt
what to index
what not to index
```

---

In Next you can create:

```txt
app/robots.ts
```

---

Example:

```ts
export default function robots() {

  return {
    rules: {
      userAgent: '*',
      allow: '/'
    }
  };
}
```

---

# sitemap.xml

A list of pages on the site.

---

Greatly helps SEO.

---

In Next:

```txt
app/sitemap.ts
```

---

Example:

```ts
export default function sitemap() {

  return [
    {
      url: '/'
    },
    {
      url: '/products'
    }
  ];
}
```

---

# Structured Data

Schema.org.

---

Interviewers love asking about this.

---

Allows Google to understand:

```txt
Product
Article
Review
Organization
```

---

Example:

```json
{
 "@type": "Product"
}
```

---

# next/image

One of the strongest optimizations in Next.

---

Problem:

```html
<img src="big.jpg" />
```

---

The browser downloads:

```txt
the original image
```

---

# Next Image

```tsx
<Image
  src={...}
  width={300}
  height={300}
/>
```

---

Automatically provides:

```txt
responsive sizes
lazy loading
modern formats
optimization
```

---

# Lazy Loading

The image loads:

```txt
only when needed
```

---

Improves:

```txt
LCP
```

---

# next/font

A very popular question.

---

Problem:

```txt
Google Fonts
```

---

An additional network request.

---

# Solution

```ts
import {
  Roboto
} from 'next/font/google';
```

---

Next:

```txt
downloads the font in advance
```

---

Improves:

```txt
CLS
FCP
```

---

# Core Web Vitals

Very important.

---

Google uses:

```txt
LCP
CLS
INP
```

---

# LCP

Largest Contentful Paint.

---

Speed of displaying
the main content.

---

# CLS

Cumulative Layout Shift.

---

Layout jumps.

---

# INP

Interaction to Next Paint.

---

UI responsiveness
to user actions.

---

# Hydration

A very popular question.

---

After SSR:

```txt
HTML already exists
```

---

But events are not yet working.

---

React attaches them.

---

This is:

```txt
Hydration
```

---

# Hydration Mismatch

Interviewers love asking about this.

---

Server:

```txt
10:00
```

---

Client:

```txt
10:01
```

---

We get:

```txt
Hydration Error
```

---

# Typical Causes

```tsx
Date.now()
Math.random()
window
localStorage
```

---

During rendering.

---

# Streaming

A very modern topic.

---

Before:

```txt
render everything
then send
```

---

Now:

```txt
send in chunks
```

---

The user sees the UI faster.

---

# Suspense

Used together with Streaming.

---

```tsx
<Suspense
 fallback={<Loading />}
>
  <Products />
</Suspense>
```

---

# Interview Answer

Next.js provides built-in SEO tools through the Metadata API, robots.txt, and sitemap.xml. For performance, next/image, next/font, Streaming, Suspense, and Server Components are used. Special attention should be paid to Core Web Vitals and avoiding Hydration Mismatch errors.
