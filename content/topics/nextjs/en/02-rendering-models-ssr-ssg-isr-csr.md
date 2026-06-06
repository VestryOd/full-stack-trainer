# Rendering Models: CSR, SSR, SSG, ISR

## The Most Popular Next.js Topic

If only one question is asked about Next,
it is usually:

```txt
SSR
SSG
ISR
CSR
```

---

# What is Rendering

Rendering is the process of producing the HTML of a page.

---

The question is:

```txt
Where is the HTML created?
When is the HTML created?
```

---

The answer determines the rendering model.

---

# CSR

Client Side Rendering.

---

Classic React SPA.

---

The process:

```txt
Browser
 ↓
Download JS
 ↓
Execute React
 ↓
Fetch Data
 ↓
Render HTML
```

---

# Example

```tsx
useEffect(() => {
  fetch(...)
}, []);
```

---

HTML appears only after JavaScript executes.

---

# Pros of CSR

- less server load
- good UX after loading
- interactivity

---

# Cons of CSR

- poor SEO
- slow First Paint
- empty HTML

---

# SSR

Server Side Rendering.

---

HTML is created on the server
on every request.

---

Diagram:

```txt
Request
 ↓
Server Render
 ↓
HTML
 ↓
Browser
```

---

Example (Page Router):

```ts
getServerSideProps()
```

---

Every request:

```txt
a new render
```

---

# Pros of SSR

- excellent SEO
- up-to-date data
- fast First Paint

---

# Cons of SSR

- server load
- higher TTFB
- less caching

---

# SSG

Static Site Generation.

---

HTML is generated:

```txt
at build time
```

---

Before any users arrive.

---

Diagram:

```txt
Build
 ↓
HTML
 ↓
CDN
 ↓
Users
```

---

Example:

```ts
getStaticProps()
```

---

# Pros of SSG

- very fast
- excellent cache-ability
- ideal for CDN

---

# Cons of SSG

Data can become stale.

---

# When to Use SSG

```txt
Blog
Marketing Pages
Docs
Landing Pages
```

---

# ISR

Incremental Static Regeneration.

---

A combination of:

```txt
SSG
+
SSR
```

---

Interviewers love asking about this.

---

# How ISR Works

At build time:

```txt
HTML is created
```

---

After:

```ts
revalidate: 60
```

---

Next can regenerate the page.

---

# Diagram

```txt
Request
 ↓
Old Cached Page
 ↓
Background Regeneration
 ↓
New Page
```

---

The user does not wait for the render.

---

# Example

```ts
export async function
getStaticProps() {

  return {
    props: {...},

    revalidate: 60,
  };
}
```

---

# When to Use ISR

```txt
E-commerce
Catalogs
News
CMS Content
```

---

Data changes but not every second.

---

# Hydration

A very popular question.

---

After SSR:

```txt
HTML already exists
```

---

But there is no interactivity yet.

---

React needs to:

```txt
attach event listeners
```

---

This process is called:

```txt
Hydration
```

---

# Hydration Flow

```txt
Server Render HTML
 ↓
Browser receives HTML
 ↓
JS bundle downloads
 ↓
Hydration
 ↓
Interactive UI
```

---

# Hydration Mismatch

A very popular Senior question.

---

The server rendered:

```txt
Hello
```

---

The client renders:

```txt
Hello World
```

---

React sees the differences.

---

We get:

```txt
Hydration Mismatch
```

---

# Typical Example

```tsx
<Date.now()>
```

---

On the server:

```txt
10:00
```

---

On the client:

```txt
10:01
```

---

The results differ.

---

# Rendering Model Comparison

| Model | HTML is generated |
|---------|---------|
| CSR | Browser |
| SSR | Request Time |
| SSG | Build Time |
| ISR | Build + Revalidation |

---

# What Interviewers Love to Ask

Which model to choose?

---

Blog:

```txt
SSG
```

---

Product Catalog:

```txt
ISR
```

---

Dashboard:

```txt
CSR
```

---

Personalized Page:

```txt
SSR
```

---

# Interview Answer

CSR renders HTML on the client after JavaScript loads. SSR creates HTML on the server on every request. SSG generates HTML at build time. ISR allows periodically regenerating static pages without a full rebuild. The choice of model depends on SEO requirements, data freshness, and performance.
