# Strapi Architecture

## Full request lifecycle

Strapi is built on Koa.js — a minimalist Node.js framework with a middleware pipeline. The architecture is similar to NestJS: a request passes through middleware → router → policy → controller → service → Document Service → DB.

```txt
HTTP Request
      ↓
  Koa Middleware Stack
  ├── CORS
  ├── Body Parser
  ├── Authentication (JWT/API Token)
  └── Error Handler
      ↓
  Router              — matches URL to handler
      ↓
  Route Middlewares   — route-specific middleware
      ↓
  Policies            — authorization checks (analogous to Guards in NestJS)
      ↓
  Controller          — request/response handling
      ↓
  Service             — business logic
      ↓
  Document Service    — Strapi ORM (v5+; previously: Entity Service)
      ↓
  Query Engine        — generates SQL/ORM queries
      ↓
  Database (PostgreSQL / MySQL / SQLite)
```

## Koa Context vs Express req/res

```javascript
// Koa uses a single ctx object instead of two parameters (req/res)
// In a custom Controller or Middleware:
module.exports = {
  async find(ctx) {
    // ctx.request — incoming request
    const { page, pageSize } = ctx.request.query;
    const user = ctx.state.user; // set by auth middleware

    // ctx.response / ctx.body — the response
    const result = await strapi.service('api::article.article').find({
      pagination: { page, pageSize },
    });

    ctx.body = result; // the Koa way to set the response
  },
};

// Difference from Express:
// Express: (req, res) => { res.json(data) }
// Koa:     (ctx) => { ctx.body = data }
// Koa supports async/await natively without express-async-errors
```

## Document Service — the central data API (v5+)

```javascript
// Document Service — the unified API for data in Strapi v5
// Replaces Entity Service from v4

// In a Service / Controller:
const strapi = require('@strapi/strapi');

// findMany — list of records with filters
const articles = await strapi.documents('api::article.article').findMany({
  filters: { publishedAt: { $notNull: true } },
  populate: ['author', 'category'],
  sort: { publishedAt: 'desc' },
  pagination: { page: 1, pageSize: 10 },
});

// findOne — one record
const article = await strapi.documents('api::article.article').findOne({
  documentId: 'abc123',
  populate: ['author'],
});

// create
const newArticle = await strapi.documents('api::article.article').create({
  data: { title: 'New Article', content: '...' },
});

// update
await strapi.documents('api::article.article').update({
  documentId: 'abc123',
  data: { title: 'Updated Title' },
});

// publish / unpublish — D&P (Draft & Publish)
await strapi.documents('api::article.article').publish({ documentId: 'abc123' });
```

## Strapi project file structure

```txt
my-strapi-project/
├── config/
│   ├── database.ts          — DB connection
│   ├── server.ts            — port, host, JWT secret
│   ├── middlewares.ts       — global middleware
│   └── plugins.ts           — plugin configuration
├── src/
│   ├── api/
│   │   └── article/         — Content Type "article"
│   │       ├── content-types/
│   │       │   └── article/
│   │       │       └── schema.json   — schema definition
│   │       ├── controllers/
│   │       │   └── article.ts        — custom controller
│   │       ├── routes/
│   │       │   └── article.ts        — custom routes
│   │       └── services/
│   │           └── article.ts        — custom service
│   ├── extensions/           — extensions to built-in services
│   └── middlewares/          — custom global middleware
├── public/
│   └── uploads/              — uploaded files (if not using S3)
└── .env                      — DATABASE_URL, JWT_SECRET, ...
```

## Strapi vs NestJS architectural comparison

```txt
Concept            Strapi                    NestJS
──────────────────────────────────────────────────────────────
HTTP Framework     Koa                       Express/Fastify
Routing            Auto (Content Types)      Manual (@Controller)
DI Container       No (global strapi object) Yes (@Injectable)
Controller         JS/TS object + factory    @Controller class
Service            JS/TS object + factory    @Injectable class
Authorization      Policies                  Guards
Data Access        Document Service          Prisma/TypeORM/custom
Schema             JSON file (auto)          Code-first or ORM
Admin UI           Built-in                  None
Extensibility      Plugins                   Modules
```

## Plugins — Strapi extensibility

```javascript
// Official plugins:
// @strapi/plugin-graphql    — GraphQL API
// @strapi/plugin-i18n       — internationalization
// @strapi/plugin-users-permissions — auth (JWT, OAuth)
// @strapi/plugin-upload     — file upload (local/S3/Cloudinary)
// @strapi/plugin-seo        — SEO meta fields

// Custom plugin:
// src/plugins/my-plugin/strapi-server.ts
module.exports = {
  register({ strapi }) {
    // Register custom services, controllers, routes
    strapi.customFields.register({
      name: 'color',
      plugin: 'my-plugin',
      type: 'string',
    });
  },

  bootstrap({ strapi }) {
    // Initialization after Strapi starts
    strapi.log.info('My plugin initialized');
  },
};
```

## Common interview mistakes

- **"Strapi uses Express"** — no. Strapi uses Koa.js. Key difference: Koa uses a single `ctx` object instead of `req/res`, supports async/await natively, and has less built-in functionality (more minimalist).

- **"Document Service is a Database ORM"** — no. Document Service is Strapi's data abstraction layer, independent of the DB type. Underneath it, the Query Engine translates calls into SQL. Document Service does not talk to PostgreSQL/MySQL directly.

- **"The data schema can be changed in production via the Admin Panel"** — no. The Content-Type Builder (GUI for creating schemas) is only available in dev mode. In production, the Content-Type Builder is disabled. The schema is stored in `schema.json` files and changed through code with a subsequent deploy.

- **"Strapi is serverless"** — no. Strapi is a stateful server with a persistent process (Koa HTTP server). Running Strapi in Lambda/serverless requires special adapters and has cold start issues. For production: PM2, Docker, Railway, Render, or Strapi Cloud.

- **"Without a DI container, Strapi can't organize dependencies"** — there is the global `strapi` object. Via `strapi.service('api::article.article')`, `strapi.plugin('upload').service('upload')`, `strapi.db.query('api::article.article')`. Not as typed as NestJS DI, but sufficient for most tasks.
