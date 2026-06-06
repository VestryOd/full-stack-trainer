# App Router vs Page Router

## History

Before Next.js 13 there was only:

```txt
Pages Router
```

---

Structure:

```txt
pages/
```

---

For example:

```txt
pages/
 ├─ index.tsx
 ├─ about.tsx
 └─ blog/[id].tsx
```

---

After Next.js 13 came:

```txt
App Router
```

---

Structure:

```txt
app/
```

---

Today this is the recommended way to develop.

---

# Why App Router Was Created

A very popular question.

---

Pages Router was good for:

```txt
SSR
SSG
ISR
```

---

But had poor support for:

```txt
Streaming
Nested Layouts
Server Components
```

---

App Router was created for that.

---

# Pages Router

Example.

---

```txt
pages/
 ├─ users/
 │   └─ index.tsx
```

---

Route:

```txt
/users
```

---

# Data Fetching

Used:

```ts
getServerSideProps()
getStaticProps()
getStaticPaths()
```

---

# Example

```ts
export async function
getServerSideProps() {

  const users =
    await getUsers();

  return {
    props: {
      users
    }
  };
}
```

---

# App Router

Structure:

```txt
app/
 ├─ users/
 │   └─ page.tsx
```

---

Route:

```txt
/users
```

---

# Data Fetching

Now:

```ts
await fetch()
```

directly inside a component.

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

# The Most Important Difference

Pages Router:

```txt
Page
=
Client Component
```

---

App Router:

```txt
Page
=
Server Component
by default
```

---

This is critically important.

---

# Layouts

One of the main advantages.

---

Pages Router:

usually:

```txt
_app.tsx
```

---

Or:

```txt
manual wrapping
```

---

# App Router

Built-in Layouts.

---

```txt
app/
 ├─ layout.tsx
 ├─ dashboard/
 │   ├─ layout.tsx
 │   └─ page.tsx
```

---

Every route segment
can have its own Layout.

---

# Nested Layouts

Interviewers love asking about this.

---

Diagram:

```txt
Root Layout
 ↓
Dashboard Layout
 ↓
Page
```

---

There is no full unmounting.

---

This improves UX.

---

# Loading UI

Pages Router:

usually manual.

---

App Router:

built in.

---

```txt
loading.tsx
```

---

Example:

```txt
app/users/loading.tsx
```

---

While data is loading:

```txt
Loading UI is shown
```

---

# Error Handling

Built in.

---

```txt
error.tsx
```

---

For a route segment.

---

# Streaming

A very important topic.

---

Pages Router:

```txt
render everything
then send
```

---

App Router:

```txt
send in chunks
```

---

The user sees content sooner.

---

# Server Components

The main reason App Router was created.

---

App Router is built around:

```txt
React Server Components
```

---

# What Remained from Pages Router

It is still supported.

---

Many legacy projects:

```txt
Next 12
Next 13
Next 14
```

still use:

```txt
pages/
```

---

# When You Will Meet Pages Router

On almost any existing project.

---

# Interview Question

What is the main difference of App Router?

Answer:

App Router is built around React Server Components, built-in Layouts, Streaming, and a new Data Fetching model. Unlike Pages Router it allows running most logic on the server by default.
