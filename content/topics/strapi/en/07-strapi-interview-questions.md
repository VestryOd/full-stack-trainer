# Strapi Interview Questions

## Group 1: Architecture and Concept

**Q: What is Strapi and how does it differ from WordPress?**

Strapi is an open-source headless CMS built on Node.js (Koa.js). "Headless" means no presentation layer — no built-in frontend for end users. WordPress bundles the backend (PHP) and frontend (templates) — the frontend is tightly coupled to the CMS. Strapi provides only an Admin Panel for editors and a REST/GraphQL API for any client (React, Next.js, mobile app). Architecture: Developer creates Content Types → Strapi automatically generates Admin UI, CRUD API, RBAC, and DB schema.

**Q: What happens under the hood when you create a Content Type in Strapi?**

```txt
1. Strapi creates schema.json in src/api/<name>/content-types/<name>/
2. On the next startup Strapi reads the schema and syncs the DB:
   - Creates/updates the table in PostgreSQL/MySQL/SQLite
   - Creates tables for relations (junction tables for M2M)
3. Registers auto-generated routes: GET/POST/PUT/DELETE /api/<plural-name>
4. Creates a core controller and service based on factories
5. Updates the Admin Panel — the new Content Type appears in the UI
6. Creates RBAC entries for the new Content Type (Public, Authenticated roles)

Content-Type Builder in dev mode → changes to schema.json → restart → DB migration
In production: only manual schema.json editing + deploy
```

**Q: Does Strapi use Express or something else?**

Koa.js. Key differences from Express: a single `ctx` object instead of `req/res`, native async/await without wrappers, onion-model middleware (vs linear next()). Strapi adds on top of Koa: router, Plugin system, Document Service, Admin Panel (embedded React app).

---

## Group 2: Content Types and Data Modeling

**Q: What is the difference between Collection Type, Single Type, and Component?**

```txt
Collection Type — multiple records, full CRUD API
  Examples: Articles, Products, Authors
  API: GET /api/articles (list), GET /api/articles/:id (one)

Single Type — one instance, always one record
  Examples: Homepage, Footer, Global SEO Settings
  API: GET /api/homepage (not an array), PUT /api/homepage (update)
  No POST or DELETE

Component — reusable field block, no API of its own
  Examples: SEO, Address, FAQ Item
  Always stored inside the parent Content Type
  Repeatable Component — array of components of the same type
```

**Q: What is a Dynamic Zone and when should you use it?**

A Dynamic Zone is an array of components of different types. It lets an editor assemble a page from blocks in any order. Each element contains a `__component` field to identify its type.

```javascript
// schema.json:
"sections": {
  "type": "dynamiczone",
  "components": ["sections.hero", "sections.faq", "sections.cta"]
}

// API response:
"sections": [
  { "__component": "sections.hero", "title": "Welcome" },
  { "__component": "sections.faq", "items": [...] }
]

// Use when:
// ✓ Marketing/Landing pages with flexible structure
// ✓ Page Builder for editors
// ✓ Different pages have different sets of blocks
// ✗ When the structure is fixed — Component is simpler
```

**Q: Why is Draft & Publish important for production?**

Draft & Publish lets editors work on content without immediate publication. `publishedAt === null` → Draft (not visible via the public API). `publishedAt !== null` → Published. The public API returns ONLY Published records by default. Drafts are only visible in the Admin Panel or via an Admin API token. Important for content teams: an editor prepares content, a senior editor approves and publishes it.

---

## Group 3: Customization — Routes, Controllers, Services

**Q: How do you add a custom endpoint in Strapi?**

```typescript
// 1. Create a route in a separate file (not in the core route):
// src/api/article/routes/custom-article.ts
export default {
  routes: [{
    method: 'GET',
    path: '/articles/popular',
    handler: 'article.popular',
    config: { auth: false }, // public
  }],
};

// 2. Add a method to the Controller:
// src/api/article/controllers/article.ts
export default factories.createCoreController('api::article.article', ({ strapi }) => ({
  async popular(ctx) {
    const articles = await strapi.service('api::article.article').findPopular();
    return this.transformResponse(articles);
  },
}));

// 3. Add a method to the Service:
export default factories.createCoreService('api::article.article', ({ strapi }) => ({
  async findPopular() {
    return strapi.documents('api::article.article').findMany({
      filters: { publishedAt: { $notNull: true } },
      sort: { views: 'desc' },
      pagination: { limit: 10 },
    });
  },
}));
```

**Q: Why is sanitizeOutput needed and why can't you skip it?**

`sanitizeOutput` removes from the response fields the current user has no permissions for (according to RBAC). Without it, a custom controller may return sensitive data (email, password hash, internal fields) to a public endpoint. Standard CRUD methods do this automatically. In custom methods it must be called explicitly: `await this.sanitizeOutput(entity, ctx)` before `this.transformResponse()`.

**Q: Document Service vs Query Engine — when to use which?**

```txt
Document Service (recommended, v5+):
  strapi.documents('api::article.article').findMany(...)
  ✓ Supports Draft & Publish (automatically filters)
  ✓ Supports i18n locales
  ✓ Automatic sanitization
  ✓ populate with nested relations
  Use for: standard CRUD operations, 90% of cases

Query Engine (low-level):
  strapi.db.query('api::article.article').findMany(...)
  ✓ More control over SQL-like queries
  ✓ Complex JOIN-like operations
  ✗ No automatic Draft & Publish filtering
  ✗ No automatic i18n support
  Use for: complex custom queries, aggregation
```

---

## Group 4: Security — Policies, Middleware, RBAC

**Q: What is the difference between a Policy and Middleware in Strapi?**

```txt
Policy (analogous to NestJS Guard):
  - Purpose: authorization check (allow/deny)
  - Returns boolean (true = allow, false = 403)
  - Runs AFTER middleware
  - Knows about the current Handler and user (ctx.state.user)
  - Applied to specific routes via route.config.policies[]

Middleware (analogous to Koa/Express middleware):
  - Purpose: request processing/transformation
  - Calls await next() or ends the response
  - Runs BEFORE Policy
  - Has no knowledge of the specific Handler
  - Can be global or route-specific
```

**Q: What types of authorization does Strapi have?**

```typescript
// 1. JWT (End Users via Users & Permissions plugin):
// POST /api/auth/local → { jwt, user }
// Requests: Authorization: Bearer <jwt>

// 2. API Token (machine clients):
// Admin Panel → Settings → API Tokens
// Types: Read-only, Full-access, Custom (per Content Type + action)
// Requests: Authorization: Bearer <api-token>

// 3. Admin Session (Admin Panel users):
// Email/password, session cookies
// Separate RBAC with granular permissions

// Difference JWT vs API Token:
// JWT — for end users (registration/login via API)
// API Token — for server integrations (CI/CD, Next.js server-side fetch)
```

---

## Group 5: Lifecycle Hooks and automation

**Q: When to use a Lifecycle Hook instead of a Service?**

```txt
Lifecycle Hook (beforeCreate/afterCreate/...):
  ✓ Automatic data mutation before saving (slug, permalink)
  ✓ Audit — log every operation on the model
  ✓ Cache invalidation on record update
  ✓ Data-level validation (beforeDelete: check dependencies)
  ✗ NOT complex business logic (hidden, hard to test)
  ✗ NOT external API calls (unexpected side effects)

Service:
  ✓ Business logic, explicit and testable
  ✓ Aggregation, calculations, rules
  ✓ Interaction with external systems
  ✓ Reusable from Controller, Cron Job, another Service
```

**Q: How do you avoid duplicate Cron Jobs when scaling horizontally?**

When multiple Strapi instances are running, each starts its own Cron Jobs independently. Solutions: (1) Distributed lock via Redis — acquire a lock with TTL before executing the task, only one instance does the work; (2) move the Cron to a separate worker process/Lambda running as a single instance; (3) use BullMQ for a task queue with a single worker.

**Q: What is bootstrap in src/index.ts and why is it needed?**

```typescript
// bootstrap is called once at Strapi startup after plugins are loaded
export default {
  async bootstrap({ strapi }) {
    // Subscribe to events
    strapi.eventHub.on('entry.create', handler);

    // Seed data on first run
    const count = await strapi.documents('api::category.category').count({});
    if (count === 0) {
      await strapi.documents('api::category.category').create({ data: { name: 'General' } });
    }

    // Register Cron Jobs
    // Configure external connections
  },

  register({ strapi }) {
    // Called BEFORE bootstrap, BEFORE plugins are loaded
    // Register custom providers, fields, extensions
  },
};
```

---

## Group 6: Integration and production

**Q: How do you correctly connect Next.js to Strapi?**

```typescript
// Server side of Next.js — use an API Token (not JWT):
// - API Token does not expire on server restart
// - No user session needed on the server

// next.config.js: env.STRAPI_API_TOKEN (Full-access or Custom)

// lib/strapi.ts:
async function fetchStrapi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${process.env.STRAPI_URL}/api/${endpoint}`, {
    headers: {
      'Authorization': `Bearer ${process.env.STRAPI_API_TOKEN}`,
      'Content-Type': 'application/json',
    },
    ...options,
  });

  if (!res.ok) throw new Error(`Strapi error: ${res.status}`);
  return res.json();
}

// ISR (Incremental Static Regeneration) + Webhook for invalidation:
// Strapi Webhook → POST /api/revalidate → next.revalidatePath()
export async function getStaticProps() {
  const data = await fetchStrapi('articles?populate=*');
  return { props: { articles: data.data }, revalidate: 3600 };
}
```

**Q: What is needed for a production Strapi deploy?**

```txt
DB: PostgreSQL (not SQLite — SQLite is for dev only)
Files: AWS S3 or Cloudinary (not local — local files are lost when scaling horizontally)
ENV variables:
  DATABASE_URL, JWT_SECRET, APP_KEYS (4 keys!), API_TOKEN_SALT, ADMIN_JWT_SECRET
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET
Deploy: Railway, Render, Strapi Cloud, Docker (not Vercel — no persistent process)
Admin Panel: NODE_ENV=production disables Content-Type Builder (correct)
Content-Type changes: via code (schema.json) + deploy (like normal code)
CORS: config/middlewares.ts → origin: ['https://yourfrontend.com']
```

**Q: Strapi v4 vs v5 — main differences?**

```txt
Strapi v4 (old):
  Entity Service API: strapi.entityService.findMany(...)
  Response: { data: [{ id, attributes: { title, ... } }] }

Strapi v5 (new, 2024):
  Document Service API: strapi.documents('api::...').findMany(...)
  Response: { data: [{ id, documentId, title, ... }] } ← no nested attributes!
  documentId: string ID (instead of numeric id in v4)
  Draft & Publish improved: versioning support

Critical for integration:
  v4: data.attributes.title
  v5: data.title  ← direct access
```
