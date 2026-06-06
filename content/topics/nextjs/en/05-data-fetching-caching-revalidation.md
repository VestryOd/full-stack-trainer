# Data Fetching, Caching, and Revalidation

## The Biggest Change in App Router

In Pages Router there were:

```ts
getServerSideProps()
getStaticProps()
getStaticPaths()
```

---

In App Router the primary API is:

```ts
fetch()
```

---

# Data Fetching in App Router

Example:

```tsx
export default async function Page() {

  const res =
    await fetch(
      'https://api.com/users'
    );

  const users =
    await res.json();

  return (...);
}
```

---

Very important to understand:

```txt
fetch runs on the server
```

---

Not in the browser.

---

# Why This Matters

You can use:

```txt
Database
Private APIs
Environment Variables
```

---

Without leaking data to the client.

---

# Automatic Caching

A very popular question.

---

In regular React:

```txt
fetch
=
a new request every time
```

---

In App Router (Next.js 13/14):

```txt
fetch is cached
by default
```

---

In Next.js 15 this behavior changed.

---

# Default Behavior

```ts
await fetch(...)
```

---

Next.js 13/14 default:

```txt
force-cache
```

Next.js 15 default:

```txt
no-store
```

---

In Next.js 15 caching must be specified explicitly.

---

# force-cache

Explicitly specify:

```ts
fetch(url, {
  cache: 'force-cache'
});
```

---

Behavior:

```txt
static result
```

---

Similar to:

```txt
SSG
```

---

# no-store

A very popular question.

---

```ts
fetch(url, {
  cache: 'no-store'
});
```

---

Every request:

```txt
a new fetch
```

---

Similar to:

```txt
SSR
```

---

# Comparison

force-cache:

```txt
cache it
```

---

no-store:

```txt
never cache
```

---

# Revalidation

The most important topic.

---

Imagine:

```txt
Product Catalog
```

---

Updated:

```txt
every 5 minutes
```

---

SSR is too expensive.

---

SSG goes stale too quickly.

---

Use:

```txt
ISR
```

---

Via:

```ts
next: {
  revalidate: 300
}
```

---

# Example

```ts
fetch(url, {
  next: {
    revalidate: 60
  }
});
```

---

Meaning:

```txt
cache for 60 seconds
```

---

After that:

```txt
regenerate
```

---

# Revalidate Path

Interviewers love asking about this.

---

When content has changed.

---

For example:

```txt
a new article
```

---

You can manually invalidate the cache.

---

```ts
revalidatePath('/blog');
```

---

The next request:

```txt
will create a new page
```

---

# Revalidate Tag

Even more powerful.

---

Assign a tag.

---

```ts
fetch(url, {
  next: {
    tags: ['products']
  }
});
```

---

After an update:

```ts
revalidateTag('products');
```

---

All related data is invalidated.

---

Very convenient for CMS.

---

# generateStaticParams

Equivalent to:

```txt
getStaticPaths
```

from Pages Router.

---

Example:

```tsx
export async function
generateStaticParams() {

  return [
    { id: '1' },
    { id: '2' }
  ];
}
```

---

At build time:

```txt
pages are created
```

---

# Dynamic Rendering

A very popular question.

---

What makes a page dynamic?

---

For example:

```ts
cookies()
headers()
```

---

or:

```ts
cache: 'no-store'
```

---

Next understands:

```txt
this page cannot be statically cached
```

---

# Request Memoization

A very interesting topic.

---

If within a single render:

```ts
fetch('/users')
```

is called 5 times

---

Next will execute:

```txt
one request
```

---

The rest from memory.

---

# What Interviewers Love to Ask

How does App Router fetch differ from browser fetch?

---

Answer:

In App Router, fetch is integrated with Next.js's caching and revalidation system and supports server rendering and automatic caching by default.

---

# Interview Answer

In App Router data is typically loaded through the built-in fetch API. Unlike browser fetch it is integrated with Next.js's caching system. Cache is controlled via cache: 'force-cache', cache: 'no-store', revalidate, revalidatePath, and revalidateTag. This allows flexible mixing of static and dynamic rendering.
