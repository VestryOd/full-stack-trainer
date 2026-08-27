# Routes, Controllers and Services

## Auto-generation vs customization

When a Content Type is created, Strapi automatically creates a Route, Controller, and Service with full CRUD, that is create, read, update and delete. Customization is needed when the standard CRUD is not enough: custom endpoints, aggregation, external APIs, complex business logic.

```typescript
// Auto-generated Route (src/api/article/routes/article.ts):
import { factories } from '@strapi/strapi';

export default factories.createCoreRouter('api::article.article');
// Generates:
// GET    /api/articles
// GET    /api/articles/:id
// POST   /api/articles
// PUT    /api/articles/:id
// DELETE /api/articles/:id

// Auto-generated Controller:
export default factories.createCoreController('api::article.article');

// Auto-generated Service:
export default factories.createCoreService('api::article.article');
```

## Custom Controller — extending the standard one

A controller is a file of methods that a route hands the request to. Strapi calls those methods actions. The controller owns the HTTP side of the work: read parameters from `ctx`, call a service, return a response.

The factory `createCoreController` takes a second argument, a function that receives `{ strapi }` and returns an object of actions. An action named after a standard one (`find`, `findOne`, `create`, `update`, `delete`) replaces it, and any other name adds a new endpoint. Inside a replaced action, `super.find(ctx)` still runs the original implementation.

Two helpers show up below. The helper `sanitizeOutput` removes the fields the current user is not allowed to read, which is role-based access control (RBAC) applied to the response. The helper `transformResponse` wraps the result into the standard shape with `data` and `meta`.

```typescript
// src/api/article/controllers/article.ts
import { factories } from '@strapi/strapi';

export default factories.createCoreController(
  'api::article.article',
  ({ strapi }) => ({
    // Override the find method to add a views counter
    async find(ctx) {
      // Call the original find via super
      const { data, meta } = await super.find(ctx);

      // Additional logic
      strapi.log.info(`Articles list fetched, count: ${meta.pagination.total}`);

      return { data, meta };
    },

    // Add a custom endpoint
    async popular(ctx) {
      const articles = await strapi
        .service('api::article.article')
        .findPopular(ctx.query);

      return this.transformResponse(articles);
    },

    // sanitizeOutput — removes fields without permissions (important!)
    async findOne(ctx) {
      const { id } = ctx.params;
      const { query } = ctx;

      const entity = await strapi.service('api::article.article').findOne(id, query);
      const sanitizedEntity = await this.sanitizeOutput(entity, ctx);

      return this.transformResponse(sanitizedEntity);
    },
  }),
);
```

## Custom Service — business logic

A service is a set of reusable functions that holds the business logic of an API. Once that logic lives outside the controller, several controllers, hooks or Cron Jobs can call the same code instead of copying it.

The factory `createCoreService` has the same two-argument shape as the controller factory. Methods returned from it become callable as `strapi.service('api::article.article').findPopular(...)`, which is exactly how the controller above reaches this file.

Three kinds of logic follow:

- a filtered read through the Document Service;
- a create that also notifies an external system;
- an aggregation that counts three Content Types in parallel.

```typescript
// src/api/article/services/article.ts
import { factories } from '@strapi/strapi';

export default factories.createCoreService(
  'api::article.article',
  ({ strapi }) => ({
    // Extend the standard service with a custom method
    async findPopular(params = {}) {
      return strapi.documents('api::article.article').findMany({
        ...params,
        filters: {
          ...(params.filters ?? {}),
          publishedAt: { $notNull: true },
        },
        sort: { views: 'desc' },
        populate: ['author', 'category', 'coverImage'],
        pagination: { limit: 10 },
      });
    },

    // Business logic with an external API call
    async createWithNotification(data: Record<string, unknown>) {
      const article = await strapi.documents('api::article.article').create({ data });

      // Notify subscribers (external service)
      try {
        await fetch(process.env.WEBHOOK_URL!, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event: 'article.published',
            articleId: article.documentId,
          }),
        });
      } catch (error) {
        strapi.log.error('Failed to notify webhook', error);
      }

      return article;
    },

    // Aggregating data from multiple entities
    async getDashboardStats() {
      const [articles, authors, categories] = await Promise.all([
        strapi.documents('api::article.article').count({
          filters: { publishedAt: { $notNull: true } },
        }),
        strapi.documents('api::author.author').count({}),
        strapi.documents('api::category.category').count({}),
      ]);

      return { articles, authors, categories };
    },
  }),
);
```

## Custom Route

A route maps one HTTP method and one path to one controller action. The core router already generates the five standard endpoints, so a route file of your own is only needed for anything beyond them.

Custom routes go in their own file inside the same `routes/` folder. Strapi loads every file in that folder in alphabetical order, so keeping custom entries apart from the core router keeps the two from clashing. Each entry sets `method`, `path` and `handler`, where `article.popular` means the `popular` action of the article controller.

The optional `config` object carries the guards. Routes require authentication by default, and `auth: false` opens one to anyone. The `policies` array lists the checks that must pass. The `middlewares` array lists code that runs around the handler.

```typescript
// src/api/article/routes/custom-article.ts
// IMPORTANT: custom routes in a separate file to avoid conflicts with core routes
export default {
  routes: [
    {
      method: 'GET',
      path: '/articles/popular',
      handler: 'article.popular',
      config: {
        policies: [],
        middlewares: [],
        auth: false, // public endpoint
      },
    },
    {
      method: 'GET',
      path: '/articles/dashboard/stats',
      handler: 'article.dashboardStats',
      config: {
        // auth: {} — requires authentication (default)
        policies: ['global::is-admin'], // custom Policy
      },
    },
    {
      method: 'POST',
      path: '/articles/:id/publish',
      handler: 'article.publish',
      config: {
        // middlewares: ['api::article.check-ownership'],
      },
    },
  ],
};
```

## Query Engine vs Document Service

Strapi offers two ways to reach the database, and they are not interchangeable. The Document Service is the default in v5. It understands Draft & Publish, internationalization (i18n), populate and sanitization, and it addresses records by `documentId`.

The Query Engine sits one level lower. It maps almost directly onto SQL (structured query language) and skips those features. The documentation recommends it only when the Document Service cannot express the query you need.

The vocabulary differs, and that is the quickest way to tell the two apart in code. The Document Service takes `filters`, `sort` and `pagination`. The Query Engine takes `where`, `orderBy`, `limit` and `offset`.

```typescript
// Document Service (recommended, v5+):
// High-level API, handles populate, Draft & Publish, i18n, sanitization
const articles = await strapi.documents('api::article.article').findMany({
  filters: { author: { name: { $contains: 'Alice' } } },
  populate: ['author', 'tags'],
});

// Query Engine (low-level, v4+):
// Direct SQL-like queries, no automatic sanitization
// Use when Document Service is not flexible enough
const result = await strapi.db.query('api::article.article').findMany({
  where: { publishedAt: { $notNull: true } },
  orderBy: { createdAt: 'desc' },
  populate: { author: true, tags: true },
  limit: 10,
  offset: 0,
});

// Raw SQL (last resort):
const [rows] = await strapi.db.connection.raw(
  'SELECT id, title, views FROM articles WHERE views > ? ORDER BY views DESC LIMIT ?',
  [1000, 10],
);
```

## Common interview mistakes

- **"All logic goes in the Controller"** — anti-pattern. The Controller handles HTTP: read parameters from ctx, call the Service, return the response. Business logic (validation, aggregation, external calls) belongs in the Service. Thick Controller = harder to test, harder to reuse.

- **"factories.createCoreController() can't be extended"** — it can. The second argument is a function that returns an object with methods. Call the standard method via `super.find(ctx)`. Any method can be overridden or a custom one added.

- **"sanitizeOutput is not needed if you write the controller yourself"** — it is needed. `sanitizeOutput` removes fields the current user has no permissions for (RBAC). Without it, the service may return user emails to a public endpoint. Always call `this.sanitizeOutput(entity, ctx)` before `this.transformResponse()`.

- **"Custom routes should be added to the same file as the core route"** — no. Core routes go in `routes/article.ts` (via `createCoreRouter`), custom ones in a separate file (`routes/custom-article.ts`). Strapi loads all `.ts` files from the `routes/` folder. Mixing them causes conflicts.

- **"Document Service and Query Engine are the same thing"** — no. Document Service (v5) is a high-level API with Draft & Publish, i18n, populate, and sanitization support. Query Engine is a low-level SQL-like API without these abstractions. Document Service is recommended for most tasks; Query Engine is for complex custom queries.
