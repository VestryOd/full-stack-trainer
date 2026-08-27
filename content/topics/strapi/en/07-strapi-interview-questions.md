# Strapi Interview Questions

## Group 1: Architecture and Concept

**Q: What is Strapi and how does it differ from WordPress?**

Strapi is an open-source headless CMS (content management system) built on Node.js, and more precisely on Koa.js. "Headless" means it has no presentation layer: there is no built-in frontend for end users.

WordPress is the contrast. It carries both the backend, written in PHP (hypertext preprocessor), and the frontend as templates, and the two are tightly coupled. Strapi gives editors an Admin Panel and gives everybody else an API to call. That API comes in two forms, REST (representational state transfer) and GraphQL, and any client can use it: React, Next.js, a mobile app.

The whole way you work with Strapi follows from that split. You define Content Types. From them Strapi generates the admin interface, the database schema and the endpoints to create, read, update and delete (CRUD) entries. It also builds the role-based access control (RBAC) entries that decide which role may call what.

**Q: What happens under the hood when you create a Content Type in Strapi?**

Creating a Content Type writes one file, and every other piece of Strapi reacts to that file. It is `schema.json`, stored in `src/api/<name>/content-types/<name>/`, and it is the single source of truth for the shape of your data. The database is not touched until the server restarts, which is why the order below matters.

1. Strapi writes `schema.json` into `src/api/<name>/content-types/<name>/`.
2. On the next startup Strapi reads that schema and runs its automatic migration. The table is created or altered in PostgreSQL, MySQL or SQLite, and every relation gets its own link table.
3. It registers the generated routes: `GET`, `POST`, `PUT` and `DELETE` on `/api/<plural-name>`.
4. It builds a core router, controller and service from the `createCoreRouter`, `createCoreController` and `createCoreService` factories.
5. The Admin Panel refreshes, so editors see the new type right away.
6. The new routes appear under Settings, in the roles of the Users & Permissions plugin. There you tick the actions you want to grant to the Public and Authenticated roles.

The tool that writes `schema.json` for you, the Content-Type Builder, is available in the development environment only. In production the schema is ordinary code: you edit `schema.json` by hand, commit it, and deploy.

**Q: Does Strapi use Express or something else?**

Koa.js. Key differences from Express: a single `ctx` object instead of `req/res`, native async/await without wrappers, onion-model middleware (vs linear next()). Strapi adds on top of Koa: router, Plugin system, Document Service, Admin Panel (embedded React app).

---

## Group 2: Content Types and Data Modeling

**Q: What is the difference between Collection Type, Single Type, and Component?**

The difference is how many entries each one holds, and whether it gets an API of its own. A Collection Type manages many entries of the same shape. A Single Type manages exactly one entry, which is what a homepage or a footer needs. A Component is a reusable block of fields with no entries and no API at all: it exists only inside a Content Type.

| | Collection Type | Single Type | Component |
|---|---|---|---|
| Entries | many | exactly one | none of its own |
| Examples | Articles, Products, Authors | Homepage, Footer, global search-engine settings | address block, question-and-answer item |
| Read | `GET /api/articles` for the list, `GET /api/articles/:documentId` for one | `GET /api/homepage` returns an object, not an array | no endpoint |
| Write | `POST` creates, `PUT` and `DELETE` work by `documentId` | `PUT /api/homepage` creates or updates, `DELETE` removes | no endpoint |

Two details catch people out. A Single Type has no `POST` at all: `PUT /api/homepage` creates the entry the first time and updates it on every call after that. It does have `DELETE`, which the documentation lists next to `GET` and `PUT`.

A Component cannot exist on its own. Its schema lives in `src/components/<category>/`, and it reaches the API only as a field of the Content Type that includes it. Mark that field `repeatable: true` and it becomes an array of components of the same type.

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

Draft & Publish lets editors work on content without immediate publication. `publishedAt === null` → Draft (not visible via the public API). `publishedAt !== null` → Published. The public API returns **only** Published records by default. Drafts are only visible in the Admin Panel or via an Admin API token. Important for content teams: an editor prepares content, a senior editor approves and publishes it.

---

## Group 3: Customization — Routes, Controllers, Services

**Q: How do you add a custom endpoint in Strapi?**

A custom endpoint is three small pieces in three files. The route declares the URL, the controller action handles the request, and the service method does the actual work. Write the route in your own file under `src/api/<name>/routes/`, separate from the generated core route file. The `handler` string wires the pieces together: `'article.popular'` means the `popular` action of the `article` controller.

Two settings in the route config are worth knowing before you read the code. Routes require authentication by default, so `config: { auth: false }` is what makes this one public. The `createCoreController` and `createCoreService` factories keep the five generated actions in place: `find`, `findOne`, `create`, `update` and `delete`. Your own method sits next to them and replaces nothing.

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

Use the Document Service for almost everything, and reach for the Query Engine only when you know exactly why. The documentation puts it plainly: in most cases you should not use the Query Engine, and should use the Document Service instead.

The Document Service is the higher layer, and it understands Strapi's own content structures — components, dynamic zones, draft and published versions, locales. The Query Engine sits underneath it and works directly with database rows, which is why it knows nothing about any of that.

| | Document Service | Query Engine |
|---|---|---|
| Call | `strapi.documents('api::article.article')` | `strapi.db.query('api::article.article')` |
| Works with | Strapi content structures | database rows and joins |
| Draft & Publish | understood, filtered for you | ignored |
| Locales | understood | ignored |
| Components, dynamic zones | understood | not aware of them |
| Populating relations | nested relations supported | manual |
| Identifier | `documentId` | numeric `id` |
| Use for | ordinary reads and writes, some 90% of the code | complex custom queries and aggregation |

The one thing neither of them does is strip fields the caller may not see. The Document Service is a data-access layer with no idea who is asking, so it can return private fields. The built-in REST and GraphQL routes sanitize on the way out. A custom controller that calls the Document Service directly has to do it itself.

---

## Group 4: Security — Policies, Middleware, RBAC

**Q: What is the difference between a Policy and Middleware in Strapi?**

A policy decides whether a request is allowed through. A middleware changes what the request or the response looks like. That is the whole distinction, and it explains why the documentation calls a policy a read-only validation step.

A policy can block the route, but rewriting the request is not its job. A middleware wraps everything that comes after it in the chain, and it can act both before that work and after it. The middleware itself decides when to call `await next()`.

| | Policy | Middleware |
|---|---|---|
| Purpose | allow the request or deny it | process and transform the request or response |
| Signature | `(policyContext, config, { strapi })` | `(context, next)` |
| Lets the request through by | returning `true`, or returning nothing at all | calling `await next()` |
| Stops the request by | returning `false` | returning without calling `next()` |
| Scope | attached to a route through `config.policies` | global for the whole server, or one route |
| Sees the handler | yes, and the user in `ctx.state.user` | no |

Order matters when you debug. Global middlewares run first, before the request has even been matched to a route. Only then does Strapi reach the route's own policies and route middlewares, and the controller after those. On the way out the response travels back through the route middlewares and the global middlewares.

If you know NestJS, a policy is its Guard. If you know Koa or Express, a Strapi middleware is the same idea, with the onion shape Koa already gives you.

**Q: What types of authorization does Strapi have?**

Strapi has three, and each is meant for a different kind of caller: end users, machines, and the people who work in the Admin Panel. Picking the wrong one is the usual reason a token suddenly stops working.

1. **JWT (JSON Web Token) for end users.** This is the Users & Permissions plugin. The user logs in with `POST /api/auth/local` and gets back a `jwt` field and a `user` field. Every later request carries the token in an `Authorization: Bearer <jwt>` header, and what the user may do comes from the role — Public or Authenticated.
2. **API token for machine clients.** You create it in the Admin Panel under Settings, and it is tied to no user account at all. A token is Read-only, Full access or Custom. Custom is granted per content type and per action, while a Read-only token can call only `find` and `findOne`. The lifetime is one of four choices: 7, 30 or 90 days, or unlimited. It travels in the same `Authorization: Bearer` header.
3. **Admin session for Admin Panel users.** An administrator signs in with an email and a password and gets a session. Access is then governed by a separate layer of role-based access control with its own fine-grained permissions. That layer decides who may edit a content type, not who may read `/api/articles`.

Choose between the first two by asking who holds the credential. A JWT belongs to a person and is obtained by logging in, and a server rendering a page cannot log in as anybody. An API token belongs to your deployment, which makes it the right thing for a server-side fetch in Next.js or for a build pipeline.

---

## Group 5: Lifecycle Hooks and automation

**Q: When to use a Lifecycle Hook instead of a Service?**

Use a lifecycle hook when something has to happen on every write to a model, whatever code did the writing. Use a service when the logic is a piece of business behaviour that somebody calls on purpose.

A hook lives in `src/api/<name>/content-types/<name>/lifecycles.ts`. It fires on paired model events: `beforeCreate` and `afterCreate`, `beforeUpdate` and `afterUpdate`, `beforeDelete` and `afterDelete`. Read events such as `beforeFindMany` are there too.

Good reasons to reach for a lifecycle hook:

- Filling a field automatically before saving, such as a slug or a permalink.
- Auditing: writing a log line for every operation on the model.
- Clearing a cache when a record changes.
- Validation at the data level, for example checking dependencies in `beforeDelete`.

What belongs in a service instead:

- Business logic you want to read, reuse and test on its own.
- Aggregation, calculations and rules.
- Talking to external systems.
- Anything a controller, a cron job or another service should be able to call.

The rule behind the two lists is visibility. A hook is invisible from the call site, so complex logic buried in one is hard to follow and hard to test. An external API call from a hook turns every save into a side effect nobody asked for.

Keep hooks thin for a second reason too. They run on Strapi's own data layer, and code that goes around that layer does not trigger them. Talking to the knex query builder directly is the usual way to lose your hooks without noticing.

**Q: How do you avoid duplicate Cron Jobs when scaling horizontally?**

Every instance runs the whole application, cron jobs included. With three instances behind a load balancer the nightly job fires three times. The fix always has the same shape: either give the instances one shared thing to compete for, or take the job away from them entirely.

Three ways to get exactly one execution:

- **A distributed lock in Redis.** Before running the task an instance takes a lock with a TTL (time to live — the delay after which the lock releases itself). Only the instance holding the lock does the work, and the expiry keeps a crashed instance from holding it forever.
- **A separate worker.** Move the cron out of the web instances into its own process, or into a scheduled function that runs as a single instance.
- **A job queue.** Put the task on a queue such as BullMQ and run exactly one worker against it.

**Q: What is bootstrap in src/index.ts and why is it needed?**

`bootstrap` is the function Strapi calls once on every server start. It runs after the application has finished setting itself up, and before the backend server starts listening. That timing is the whole point. By then you have the full `strapi` object, so you can query the database, subscribe to events and register cron jobs.

`src/index.ts` exports a second function next to it, `register`, and the two are not interchangeable. The `register` function is the very first thing that happens when a Strapi application starts, before any setup at all. Nothing is available there yet: no database, no routes, no policies.

| | `register` | `bootstrap` |
|---|---|---|
| Runs | first, before any setup | after setup, before the server listens |
| Available to you | almost nothing yet | the full `strapi` object |
| Use for | custom fields, providers, plugin extensions | seeding data, event subscriptions, cron jobs |

The example below seeds a default category on the first run. That is `bootstrap` work by definition: it touches the database, so it could not live in `register`.

```typescript
// bootstrap is called once at Strapi startup after plugins are loaded
export default {
  async bootstrap({ strapi }) {
    // Subscribe to events
    strapi.eventHub.on('entry.create', handler);

    // Seed data on first run
    const count = await strapi.documents('api::category.category').count({});
    if (count === 0) {
      await strapi.documents('api::category.category').create({
        data: { name: 'General' },
      });
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

On the server use an API token, never a user's JWT. The server has no user to log in as. A token created in the Admin Panel belongs to the deployment, not to a person. Keep it in an environment variable, read it only in server code, and send it in an `Authorization: Bearer` header.

Wrap the calls in one typed helper instead of scattering `fetch` around the app. The helper below builds the address from `STRAPI_URL`, attaches the token, and throws when the response fails. A broken payload never reaches a component.

The second half of the example is about staying fast without serving stale pages. ISR (incremental static regeneration) hands every visitor a page that was rendered ahead of time. Once that page is older than `revalidate` seconds — one hour here — the next request still gets the cached copy. Next.js rebuilds the page in the background and serves the fresh one from then on.

When an hour is too long to wait, add on-demand revalidation. A Strapi webhook calls a route in your Next.js app the moment an editor publishes, and that route invalidates the affected path.

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

Every item below follows from one fact: Strapi is a long-running Node.js server that owns state. It needs a database it can share and a home for uploaded files outside the container's own disk. It also needs a process that stays alive between requests.

- **Database.** Strapi supports SQLite 3, MySQL 8.0+, MariaDB 10.3+ and PostgreSQL 14.0+. Choose PostgreSQL for production. A SQLite database is one file on the instance's local disk. Two instances cannot share that file, and a redeploy on ephemeral hosting wipes it.
- **File uploads.** The default provider stores files locally on the server, which has exactly the same problem. Switch to one of the official providers backed by object storage: Amazon S3 (Simple Storage Service) or Cloudinary.
- **Environment variables.** The generated `.env` documents `APP_KEYS`, `API_TOKEN_SALT`, `ADMIN_JWT_SECRET`, `TRANSFER_TOKEN_SALT` and `JWT_SECRET`, plus the `DATABASE_*` group. `APP_KEYS` is a comma-separated list, and the generated file ships four values in it. Add whatever your storage provider needs, such as an access key, a secret and a bucket name.
- **Hosting.** Strapi's deployment guides cover Strapi Cloud, AWS (Amazon Web Services), Azure, DigitalOcean App Platform and Heroku. They also recommend pm2 to keep the process alive. A platform built around short-lived serverless functions is the wrong shape, which is why Vercel hosts the Next.js frontend and not the Strapi backend.
- **Admin panel and schema.** The Content-Type Builder is available in the development environment only. In production you change a content type by editing `schema.json`, committing it and deploying it like any other code.
- **CORS (cross-origin resource sharing).** It is configured in `config/middlewares.ts`, in the `strapi::cors` entry. The `origin` option defaults to `*`. In production set it to the list of front-end origins you actually serve.

**Q: Strapi v4 vs v5 — main differences?**

The difference you meet every day is the response shape. Version 5 removed the `attributes` wrapper, so the fields of an entry sit directly on it. Underneath that sits the identifier. Every document in v5 has a stable string `documentId` next to the numeric `id`, and the REST routes address documents by it.

The API you call changed with it. The v4 Entity Service, `strapi.entityService`, gave way to the Document Service, `strapi.documents(...)`. Draft & Publish was reworked in the same release, and the Document Service carries `publish`, `unpublish` and `discardDraft` for it.

The block below keeps both forms side by side. Read the v4 half as history, not as something to copy into a new project.

```txt
Strapi v4 (old):
  Entity Service API: strapi.entityService.findMany(...)
  Response: { data: [{ id, attributes: { title, ... } }] }

Strapi v5 (new, 2024):
  Document Service API: strapi.documents('api::...').findMany(...)
  Response: { data: [{ id, documentId, title, ... }] }
  ↑ no nested attributes, unlike v4
  documentId: string ID (instead of numeric id in v4)
  Draft & Publish improved: versioning support

Critical for integration:
  v4: data.attributes.title
  v5: data.title  ← direct access
```
