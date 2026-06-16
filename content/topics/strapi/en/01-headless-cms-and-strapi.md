# Headless CMS and Strapi

## What is a Headless CMS

Traditional CMSes (WordPress, Drupal) bundle the backend and frontend into a single application: content is stored in a DB, rendering happens on the server via PHP templates. The frontend is tightly coupled to the CMS.

A headless CMS removes the "head" — the presentation layer. Only Content Management + API remains. The frontend (React, Next.js, mobile app) decides for itself how to display the data.

```txt
Traditional CMS:                    Headless CMS (Strapi):
──────────────────                  ──────────────────────────────────
Editor                              Editor
  ↓                                   ↓
WordPress/Drupal                    Strapi Admin
  ↓                                   ↓
PHP Templates                       REST API / GraphQL
  ↓                                   ↓
HTML → Browser                      React / Next.js / Mobile / TV App
                                    (each client renders on its own)
```

## What is Strapi

Strapi is an open-source headless CMS built on Node.js (Koa.js under the hood). The developer describes data models (Content Types), and Strapi automatically generates:

- REST API and GraphQL API
- Admin Panel for content management
- RBAC (Role-Based Access Control)
- Media upload (S3, Cloudinary)
- Webhooks

```txt
Strapi stack:
  Node.js + Koa.js              — HTTP server
  @strapi/database              — ORM (SQLite / PostgreSQL / MySQL)
  Admin Panel (React)           — embedded frontend for editors
  Content-Type Builder          — GUI for creating schemas (dev mode only)
  Plugin system                 — extensibility (i18n, GraphQL, email, ...)
```

## REST API out of the box

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

// Response:
{
  "data": [
    {
      "id": 1,
      "attributes": {
        "title": "Getting Started with Strapi",
        "publishedAt": "2024-01-15T10:00:00.000Z",
        "author": {
          "data": {
            "id": 5,
            "attributes": { "name": "Alice", "avatar": "..." }
          }
        }
      }
    }
  ],
  "meta": {
    "pagination": { "page": 1, "pageSize": 10, "total": 42, "pageCount": 5 }
  }
}
```

## Strapi vs traditional NestJS/Express

```txt
Criterion             Strapi                        NestJS/Express
──────────────────────────────────────────────────────────────────────
Time-to-first-API     Minutes (GUI builder)         Hours/days (manual code)
Customization         Limited to plugins            Full freedom
Business logic        Via hooks/custom routes       No restrictions
Scalability           Medium (monolith)             High (microservices)
Admin Panel           Built-in                      Must be built
RBAC                  Built-in                      Must be built
Good for              CMS, marketing, catalogs      Any complex logic
Not good for          High-load, complex domain     Simple CMS (overkill)
```

## When to choose Strapi

```txt
Strapi — a good choice:
  ✓ Marketing site / corporate website
  ✓ Blog, news portal
  ✓ E-commerce catalog (not payment logic)
  ✓ Mobile app backend with simple CRUD operations
  ✓ MVP where you need an API quickly
  ✓ Team includes non-developer editors

Strapi — a bad choice:
  ✗ Complex business logic (trading, banking, ERP)
  ✗ High-load (>10k req/sec — Strapi doesn't scale horizontally easily)
  ✗ Microservices (Strapi is a monolith)
  ✗ Need full control over the DB schema
  ✗ Non-standard authorization
```

## Common interview mistakes

- **"Strapi replaces NestJS"** — no. Strapi is a CMS for content management. NestJS is a framework for building any Node.js application. Strapi uses Koa internally and is not an alternative to NestJS/Express for complex business logic.

- **"Headless CMS has no admin panel"** — no. "Headless" means there is no public frontend (presentation layer). An Admin Panel for editors is there. Strapi includes a full React-based admin UI. "Headless" = no templating for end users.

- **"Strapi only works with REST"** — no. Strapi supports GraphQL via the official `@strapi/plugin-graphql` plugin. After installing the plugin, queries, mutations, and subscriptions are automatically generated for all Content Types.

- **"Content Types in Strapi can be created in production"** — no. The Content-Type Builder is only available in development mode. In production, schema changes are made via code (schema files in `src/api/`) and deployed like normal code. This is critically important for production stability.

- **"Strapi v4 and v5 are the same thing"** — no. Strapi v5 (2024) is a major breaking change: new Document Service API instead of Entity Service, new query engine, improved typing. API responses have a different structure (nested `attributes` have been removed). Always clarify the version when discussing the API structure.
