# Headless CMS and Strapi

## What is a Headless CMS

CMS stands for content management system: an application where editors create and publish site content without touching code. Traditional systems such as WordPress and Drupal bundle the backend and the frontend into a single application.

Content is stored in a database, and the server renders pages from templates written in PHP (the language both engines are built on). The frontend is therefore tightly coupled to the CMS.

A headless CMS removes the "head" — the presentation layer. What is left is content management plus an API. The frontend (React, Next.js, a mobile app) decides for itself how to display the data.

```txt
Traditional CMS:                Headless CMS (Strapi):
──────────────────              ──────────────────────────────────
Editor                          Editor
  ↓                               ↓
WordPress/Drupal                Strapi Admin
  ↓                               ↓
PHP Templates                   REST API / GraphQL
  ↓                               ↓
HTML → Browser                  React / Next.js / Mobile / TV App
                                (each client renders on its own)
```

## What is Strapi

Strapi is an open-source headless CMS written in Node.js, with Koa.js as its HTTP layer. You describe your data models, which Strapi calls Content Types, and it generates the running application from that description. Two of the generated pieces are APIs over the same data: REST (representational state transfer) and GraphQL. Nothing in the list below is code you write:

- REST API and GraphQL API
- Admin Panel for content management
- RBAC (role-based access control)
- Media upload to external storage: Amazon Simple Storage Service (S3) or Cloudinary
- Webhooks

Five pieces make up the stack that produces all of this:

- **Node.js with Koa.js** — the HTTP server that receives requests.
- **`@strapi/database`** — the ORM (object-relational mapper), the layer that turns method calls into database queries. It works with SQLite, PostgreSQL and MySQL.
- **Admin Panel, written in React** — a frontend embedded in the same process, the one editors log into.
- **Content-Type Builder** — the GUI (graphical user interface) for drawing schemas. It is available in development mode only.
- **Plugin system** — the extension point for i18n (internationalization), GraphQL, email and more.

## REST API out of the box

Once you save a Content Type, Strapi builds a full set of HTTP endpoints for it, and you write no routing code at all. A type named Article gets five endpoints under `/api/articles`: list, read one, create, update, delete. The reading endpoints take query parameters that replace code you would otherwise write by hand:

- `filters` narrows the result down to records matching a condition.
- `sort` sets the order.
- `pagination` cuts the result into pages.
- `populate` pulls related records into the answer, such as the article's author.

Every answer has the same two top-level keys. The `data` key carries the records and `meta` carries the pagination counters. Each record shows a numeric `id`, a string `documentId`, and its own fields directly on it. Strapi v5 returns those fields flat, while version 4 wrapped them in an `attributes` object.

```typescript
// After creating a "Article" Content Type, Strapi generates:
// GET    /api/articles                — list articles
// GET    /api/articles/:id            — one article
// POST   /api/articles                — create
// PUT    /api/articles/:id            — update
// DELETE /api/articles/:id            — delete

// Request with filtering, sorting, pagination, populate:
// GET /api/articles?
//   filters[category][name][$eq]=Tech&
//   sort[0]=publishedAt:desc&
//   pagination[page]=1&
//   pagination[pageSize]=10&
//   populate[author][fields][0]=name&
//   populate[author][fields][1]=avatar

// Response (Strapi v5: no "attributes" wrapper, documentId next to id):
{
  "data": [
    {
      "id": 1,
      "documentId": "hgv1vny5cebq2l3czil1rpb3",
      "title": "Getting Started with Strapi",
      "publishedAt": "2024-01-15T10:00:00.000Z",
      "author": {
        "id": 5,
        "documentId": "znrlzntu9ei5onjvwfaalu2v",
        "name": "Alice",
        "avatar": "..."
      }
    }
  ],
  "meta": {
    "pagination": { "page": 1, "pageSize": 10, "total": 42, "pageCount": 5 }
  }
}
```

## Strapi vs traditional NestJS/Express

Strapi and a hand-written NestJS or Express service answer different questions, so the comparison is about cost rather than quality. Strapi hands you a working API and an editing interface in minutes, and in exchange you stay inside what its plugins allow. A hand-written service costs hours or days before the first endpoint replies, and in exchange nothing about it is fixed.

Read the table below as a list of trade-offs. Each row names something one side gives you for free and the other side charges for.

| Criterion | Strapi | NestJS/Express |
|---|---|---|
| Time to first API | Minutes, in the Content-Type Builder | Hours or days of manual code |
| Customization | Limited to plugins | Full freedom |
| Business logic | Through hooks and custom routes | No restrictions |
| Scalability | Medium, because it is a monolith | High, up to microservices |
| Admin Panel | Built in | Must be built |
| RBAC | Built in | Must be built |
| Good for | Content sites, marketing, catalogs | Any complex logic |
| Not good for | High load, complex domain | A simple content site (overkill) |

## When to choose Strapi

The decision comes down to one question: is the hard part of your project the content or the rules? Strapi fits projects where editors change text and images every day, and where the server mostly reads those records back out. It stops being the right tool when the value sits in logic such as pricing, settlements or approval workflows.

That code has to live somewhere Strapi does not own, and forcing it into hooks makes both halves worse. The two lists below cover most real cases.

**Strapi is a good choice for:**

- Marketing sites and corporate websites.
- Blogs and news portals.
- E-commerce catalogs — the product data, not the payment logic.
- Mobile app backends with simple create, read, update and delete operations.
- An MVP (minimum viable product) where you need an API quickly.
- Teams that include editors who are not developers.

**Strapi is a bad choice for:**

- Complex business logic: trading, banking, ERP (enterprise resource planning).
- High load. Above roughly 10k requests per second Strapi does not scale horizontally with any ease.
- Microservices, because Strapi is a monolith.
- Projects that need full control over the database schema.
- Non-standard authorization.

## Common interview mistakes

- **"Strapi replaces NestJS"** — no. Strapi is a CMS for content management. NestJS is a framework for building any Node.js application. Strapi uses Koa internally and is not an alternative to NestJS/Express for complex business logic.

- **"Headless CMS has no admin panel"** — no. "Headless" means there is no public frontend (presentation layer). An Admin Panel for editors is there. Strapi includes a full admin interface written in React. "Headless" = no templating for end users.

- **"Strapi only works with REST"** — no. Strapi supports GraphQL via the official `@strapi/plugin-graphql` plugin. After installing the plugin, queries, mutations, and subscriptions are automatically generated for all Content Types.

- **"Content Types in Strapi can be created in production"** — no. The Content-Type Builder is only available in development mode. In production, schema changes are made via code (schema files in `src/api/`) and deployed like normal code. This is critically important for production stability.

- **"Strapi v4 and v5 are the same thing"** — no. Strapi v5 (2024) is a major breaking change: new Document Service API instead of Entity Service, new query engine, improved typing. API responses have a different structure (nested `attributes` have been removed). Always clarify the version when discussing the API structure.
