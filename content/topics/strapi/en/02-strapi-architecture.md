# Strapi Architecture

## Full request lifecycle

Strapi runs on Koa.js, a minimalist Node.js framework whose whole job is to hand a request down a chain of functions called middleware. Every request that reaches Strapi walks the same stops in the same order.

Knowing that order is the practical part, because it tells you where your own code belongs. The diagram below draws the whole path. Here is what each stop is for:

- **Global middleware** — the work done for every request. It checks CORS (cross-origin resource sharing), parses the body, and catches errors. It also reads the JWT (JSON web token) or API token that identifies the caller.
- **Router** — matches the URL and the HTTP verb to a single handler.
- **Route middleware** — the same idea as global middleware, but attached to one route only.
- **Policies** — answer one yes-or-no question: may this caller do this? A policy that returns `false` stops the request, and the controller never runs.
- **Controller** — reads the request and builds the response body.
- **Service** — holds the business logic, so that several controllers can share it.
- **Document Service** — the data API a service calls. It works with documents rather than table rows.
- **Query Engine** — turns those calls into SQL (structured query language) for PostgreSQL, MySQL or SQLite.

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
  Policies            — authorization (like a Guard in NestJS)
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

Koa hands your function a single object called the context, written `ctx`, where Express hands you two objects named `req` and `res`. Everything about the request and the response lives on that one object.

Three properties carry almost all the traffic. The `ctx.request` property holds the incoming request, including the parsed query string. The `ctx.state` property holds whatever earlier middleware put there, which is how Strapi passes the signed-in user along as `ctx.state.user`. Assigning to `ctx.body` is how you send a response, so there is no `res.json()` call to make.

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

The Document Service is the API you call from your own code to read and write content. It arrived in Strapi v5 and replaced the Entity Service of version 4. The rename is not cosmetic: it addresses documents by a `documentId` string instead of rows by a number.

It is not an ORM (object-relational mapper) sitting on your tables. The Query Engine one level below does the translation, which is why these calls read the same whichever database you run.

You reach it as `strapi.documents('api::article.article')`, passing the unique identifier of a Content Type. Every method takes one options object, so filters, populate, sort and pagination are named keys rather than positional arguments.

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

A Strapi project splits into two top-level folders, and after that the layout is predictable enough to navigate blind. The `config/` folder holds settings: the database connection, the server port and its secrets, the list of global middleware, and plugin options.

The `src/` folder holds your code. Each Content Type gets one folder under `src/api/`. Inside it sit the four pieces Strapi generated for that type: the schema, the controller, the routes and the service. You edit those files to add behaviour, but you do not move them, because Strapi locates them by path. The tree below shows the shape for a single Content Type named article.

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

Strapi and NestJS overlap enough that the differences are easy to list, and most of them follow from one decision. Strapi generates its API from a schema; NestJS asks you to write that API by hand.

Everything in the table is a consequence of that choice. Strapi has no DI (dependency injection) container, because there is little to wire up automatically. Instead there is one global `strapi` object you ask for things by name. NestJS has no admin interface because it does not know what your data means. Read the rows as trade-offs, not as a scoreboard.

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

A plugin is a package that adds features to Strapi without you editing Strapi itself. The official ones, maintained by the Strapi team, cover GraphQL, i18n (internationalization), authentication, file upload, and SEO (search engine optimization) fields. A plugin can add routes, services, content types and screens in the Admin Panel.

Writing your own plugin means exporting an object with lifecycle functions from `strapi-server.ts`. Two of them matter first. The `register` function runs before the server starts, ahead of database and routing setup. The code below uses it to announce a custom field type. The `bootstrap` function runs after all plugins are loaded, once the database, routes and permissions are ready.

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

- **"Document Service is a Database ORM"** — no. Document Service is Strapi's data abstraction layer, independent of the database type. Underneath it, the Query Engine translates calls into SQL. Document Service does not talk to PostgreSQL/MySQL directly.

- **"The data schema can be changed in production via the Admin Panel"** — no. The Content-Type Builder — the graphical user interface (GUI) for creating schemas — is only available in dev mode. In production, the Content-Type Builder is disabled. The schema is stored in `schema.json` files and changed through code with a subsequent deploy.

- **"Strapi is serverless"** — no. Strapi is a stateful server with a persistent process (Koa HTTP server). Running Strapi in Lambda/serverless requires special adapters and has cold start issues. For production: PM2 (a process manager for Node.js), Docker, Railway, Render, or Strapi Cloud.

- **"Without a DI container, Strapi can't organize dependencies"** — there is the global `strapi` object. Via `strapi.service('api::article.article')`, `strapi.plugin('upload').service('upload')`, `strapi.db.query('api::article.article')`. Not as typed as NestJS DI, but sufficient for most tasks.
