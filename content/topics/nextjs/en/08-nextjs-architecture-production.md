# Production Architecture and Best Practices

## The Most Senior Block

Here the questions become:

```txt
How would you structure a project?
How would you scale Next?
How would you organize the architecture?
```

---

# Typical Architecture

```txt
Browser
 ↓
CDN
 ↓
Next.js
 ↓
Backend APIs
 ↓
Database
```

---

# Option 1

Next as Frontend.

---

```txt
Next
 ↓
NestJS
 ↓
PostgreSQL
```

---

A very common pattern.

---

# Option 2

BFF Architecture

---

Backend For Frontend.

---

```txt
Browser
 ↓
Next
 ↓
Microservices
```

---

Next aggregates data.

---

The frontend gets:

```txt
one API
```

---

# Why BFF is Convenient

The frontend does not know about:

```txt
User Service
Product Service
Order Service
```

---

Everything is hidden inside the BFF.

---

# Server Actions

A very popular topic.

---

Allows running server code
without API Routes.

---

Example:

```tsx
'use server';

export async function
createUser() {

}
```

---

Form:

```tsx
<form action={createUser}>
```

---

Without:

```txt
REST
GraphQL
API Route
```

---

# When to Use Server Actions

Good for:

```txt
forms
CRUD
mutations
```

---

Bad for:

```txt
public API
integrations
```

---

# API Routes

The older approach.

---

```txt
app/api/users/route.ts
```

---

Creates an endpoint.

---

```ts
export async function GET() {}
```

---

# When API Routes Are Better

When you need:

```txt
REST API
Webhook
External Integration
```

---

# Edge Runtime

A very popular question.

---

Code runs:

```txt
closer to the user
```

---

On Edge Nodes.

---

Not on the main server.

---

# Edge Limitations

No:

```txt
fs
net
child_process
```

---

Not all npm packages work.

---

# Caching Strategy

Interviewers love asking about this.

---

The main rule:

```txt
not everything SSR
not everything SSG
```

---

Typically:

```txt
Homepage → SSG

Product List → ISR

Product Page → ISR

Cart → CSR

Profile → SSR

Admin → CSR
```

---

# Environment Variables

Server:

```txt
process.env.SECRET
```

---

Client:

```txt
NEXT_PUBLIC_API_URL
```

---

A very popular question.

---

# Why NEXT_PUBLIC

Without it the variable:

```txt
will not appear in the client bundle
```

---

# Security

Never pass:

```txt
JWT Secret
DB Password
API Keys
```

---

to Client Components.

---

# Monitoring

A production project typically uses:

```txt
Sentry
Datadog
Application Insights
New Relic
```

---

# Deployment

The most common option:

```txt
Vercel
```

---

Also:

```txt
AWS
Docker
Kubernetes
Azure
GCP
```

---

# Very Popular Question

How would you build an e-commerce?

Answer:

```txt
Homepage → SSG

Categories → ISR

Products → ISR

Cart → Client State

Checkout → Server Actions/API

Admin Panel → CSR
```

---

# Very Popular Question

How would you build a CMS site?

Answer:

```txt
Next.js
 ↓
Strapi
 ↓
PostgreSQL
```

---

Pages:

```txt
ISR
```

---

After publishing an article:

```txt
revalidateTag
```

---

# The Strongest Senior Answer

What is the most important thing in a production Next.js application?

Answer:

There is no single universal rendering model. A production application typically combines SSG, ISR, SSR, Client Components, Server Components, caching, and revalidation depending on the requirements of each specific screen. The main task of the architect is to choose the right trade-off between SEO, performance, rendering cost, and data freshness.
