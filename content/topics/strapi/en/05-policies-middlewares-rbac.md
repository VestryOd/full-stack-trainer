# Policies, Middlewares and RBAC

## Two authorization spaces in Strapi

Strapi has two separate user spaces, and each has its own role-based access control (RBAC). Permissions there belong to a role, not to a person. The two systems never overlap, and confusing them is the most common mistake in this area.

| | End users | Admin users |
|---|---|---|
| Who they are | People who read your content through a front end | Editors and managers who work inside the admin panel |
| Plugin | `users-permissions` | `admin` |
| How they sign in | Through the API, for example `POST /api/auth/local/register` | Email and password |
| What holds the session | A JWT (JSON Web Token) in the `Authorization` header | Cookies |
| Roles | Built-in Public and Authenticated, plus any custom ones | Its own roles, separate from the end-user ones |
| Permissions | Per Content Type and per action: find, findOne, create, update, delete | Fine-grained permissions across the admin panel |
| Where configured | Admin Panel → Settings → Roles | Admin Panel → Settings |
| Machine clients | — | API tokens, which let a program call the API without a user account |

## RBAC for End Users

The block below is mostly a map of what you tick in the admin panel. For every role and every Content Type you allow or forbid the five actions: find, findOne, create, update and delete.

Three roles cover most projects. Public is what an unauthenticated visitor gets. Authenticated is what any logged-in user gets. A custom role such as Editor sits between them: it may create and update, but not delete.

Role permissions stop at the Content Type. They can say who may update articles, but not who may update this particular article. Ownership has to be checked in code. The service at the end of the block shows the usual shape. Load the record, compare `createdBy` with the current user, and throw if they differ.

```typescript
// Admin Panel → Settings → Users & Permissions → Roles

// Public role (unauthenticated users):
// Typically: GET /api/articles (find, findOne) — open
// POST/PUT/DELETE — forbidden

// Authenticated role (JWT users):
// Access to content created by themselves
// Additional permissions based on business logic

// Custom role "Editor":
// find, findOne, create, update — allowed
// delete — forbidden
// Access only to own records (createdBy filter)

// Programmatic permission check in Service:
async updateArticle(documentId: string, data: any, user: any) {
  const article = await strapi.documents('api::article.article').findOne({
    documentId,
    fields: ['id'],
    populate: { createdBy: { fields: ['id'] } },
  });

  // Check ownership
  if (article.createdBy?.id !== user.id && user.role.name !== 'Admin') {
    throw new Error('Forbidden: not the owner');
  }

  return strapi.documents('api::article.article').update({ documentId, data });
}
```

## Policy — analogous to a Guard in NestJS

A policy is a function that runs on every request to its route, before the controller, and decides whether that request may continue. It returns `true` to allow and `false` to block. Returning nothing at all counts as "do not block", so an explicit return matters. If you already know NestJS, this is its Guard.

Every policy receives `policyContext`, a wrapper around the controller context that behaves the same for both of Strapi's query layers. The current user sits at `policyContext.state.user`, and route parameters at `policyContext.params`.

Where the file lives decides how a route refers to it. A file in `src/policies/` is global and is named `global::is-admin`. A file in `src/api/article/policies/` belongs to that API and is named `api::article.is-owner`. The last example takes options from the route: the object form passes `config`, which the function reads as `config.role`.

```typescript
// Global policy: src/policies/is-admin.ts
export default async (policyContext, config, { strapi }) => {
  const { user } = policyContext.state;

  if (!user) return false; // not authenticated

  // Check role
  const userWithRole = await strapi.db.query('plugin::users-permissions.user').findOne({
    where: { id: user.id },
    populate: ['role'],
  });

  return userWithRole?.role?.name === 'Admin';
};

// Route-specific policy: src/api/article/policies/is-owner.ts
export default async (policyContext, config, { strapi }) => {
  const { user } = policyContext.state;
  const { id } = policyContext.params;

  const article = await strapi.documents('api::article.article').findOne({
    documentId: id,
    populate: { createdBy: { fields: ['id'] } },
  });

  return article?.createdBy?.id === user?.id;
};

// Application in a route:
{
  method: 'PUT',
  path: '/articles/:id',
  handler: 'article.update',
  config: {
    policies: [
      'global::is-admin',          // OR
      'api::article.is-owner',     // both must return true
    ],
  },
}

// Policy with configuration:
export default async (policyContext, config, { strapi }) => {
  const requiredRole = config.role ?? 'Admin'; // config from route
  return policyContext.state.user?.role?.name === requiredRole;
};

// Route:
config: { policies: [{ name: 'global::has-role', config: { role: 'Editor' } }] }
```

## Middleware — request processing before Policy

A middleware is a function that wraps the request. It can inspect it, change it, and decide whether to pass it further. Strapi follows the Koa convention here, so a middleware receives `ctx` and `next`, and calling `await next()` hands control to whatever comes next. Code placed after that call runs on the way back out, which is how the logger below measures duration.

Global middlewares run on every request, before routing and before any policy. They are listed in `config/middlewares.ts` and run in the order of that array. The `strapi::` entries are the built-in ones, and a custom file in `src/middlewares/` joins them as `global::request-logger`.

Route middlewares are the narrow kind. A file in `src/api/article/middlewares/` is referenced as `api::article.check-rate-limit` and runs only for routes that list it. A middleware that returns without calling `next()` ends the request right there. That is how the rate limiter below answers with 429.

```typescript
// Global middleware: src/middlewares/request-logger.ts
export default () => {
  return async (ctx, next) => {
    const start = Date.now();

    await next(); // call next middleware / controller

    const duration = Date.now() - start;
    strapi.log.info(`${ctx.method} ${ctx.url} - ${ctx.status} (${duration}ms)`);
  };
};

// Register global middleware in config/middlewares.ts:
export default [
  'strapi::errors',
  'strapi::security',
  'strapi::cors',
  'strapi::logger',
  'strapi::query',
  'strapi::body',
  'strapi::session',
  'strapi::favicon',
  'strapi::public',
  'global::request-logger', // custom
];

// Route-specific middleware: src/api/article/middlewares/check-rate-limit.ts
export default () => {
  const requestCounts = new Map<string, number>();

  return async (ctx, next) => {
    const ip = ctx.request.ip;
    const count = (requestCounts.get(ip) ?? 0) + 1;
    requestCounts.set(ip, count);

    if (count > 100) {
      ctx.status = 429;
      ctx.body = { error: 'Too many requests' };
      return;
    }

    await next();
  };
};

// Application in a route:
{
  method: 'POST',
  path: '/articles',
  handler: 'article.create',
  config: {
    middlewares: ['api::article.check-rate-limit'],
  },
}
```

## API Tokens — for machine clients

An API token is a long secret string that lets a program call the content API without a user account. You create it in Admin Panel → Settings → API Tokens and choose how long it lives: 7, 30 or 90 days, or unlimited.

The caller sends it in the `Authorization` header as a bearer token, exactly like the curl line below. Strapi verifies it automatically on `/api/*` routes, so writing that check by hand is rarely necessary.

Three token types decide how much the holder may do:

- Read-only allows only the `find` and `findOne` actions.
- Full access allows every method.
- Custom lets you tick permissions per Content Type.

The helper at the end reads the token record straight from the database with the Query Engine.

```typescript
// Admin Panel → Settings → API Tokens → Create

// Token types:
// Read-only  — GET requests only
// Full-access — all methods
// Custom     — granular permissions per Content Type

// Usage:
// curl -H "Authorization: Bearer <token>" https://api.example.com/api/articles

// In custom code — verify the token:
const verifyApiToken = async (token: string) => {
  // Strapi does this automatically for all /api/* routes
  // But if needed manually:
  const tokenRecord = await strapi.db.query('admin::api-token').findOne({
    where: { accessKey: token },
    populate: ['permissions'],
  });
  return tokenRecord;
};
```

## Policy vs Middleware — key differences

Both sit between the request and the controller, and both can stop it, which is why they get mixed up. The difference is one of intent. A policy answers a single yes-or-no question about permission. A middleware shapes the request and the response around the handler.

Everything else follows from that. A policy returns a boolean and only reads. A middleware controls the flow with `next()` and may change the request. A global middleware runs before routing, so it cannot know which handler will be reached. A policy is attached to one route and sees `ctx.state.user` already filled in.

| Criterion | Policy | Middleware |
|---|---|---|
| NestJS analogue | Guard | Middleware |
| Purpose | Authorization: allow or deny | Request processing |
| Where applied | `Route.config.policies[]` | `Route.config.middlewares[]`, or globally |
| Access to ctx | Through `policyContext` | Directly through `ctx` |
| Return value | Boolean: `true` allows, `false` gives 403 | void: call `next()` or do not |
| Order | After middleware | Before policy |
| User context | `ctx.state.user` already set | Depends on order, the auth middleware runs first |

## Common interview mistakes

- **"Policy and Middleware are the same thing"** — no. Middleware runs earlier (before routing and Policy). Middleware has no knowledge of the Handler. A Policy checks access to a specific route, knows about the Handler, and has access to the user via `policyContext.state.user`. Analogy: Middleware = Express middleware, Policy = NestJS Guard.

- **"RBAC for End Users and Admin Users is one system"** — no. End Users (`plugin::users-permissions`) — JWT auth, Public/Authenticated roles, permissions on Content Type actions. Admin Users — a separate system with session cookies, different roles and permissions. They do not overlap.

- **"If a Policy returns false — the error is 401"** — no. By default it's 403 (Forbidden). 401 (Unauthorized) means there is no JWT token at all. 403 means the token exists but permissions are insufficient. This can be customized by throwing an exception in the Policy: `throw new PolicyError('Custom message', { policy: 'is-admin' })`.

- **"Global middleware only applies to /api/* routes"** — no. Global middleware applies to all routes including the admin panel (/admin/*) and upload (/api/upload). Route-specific middleware only applies to the specified route.

- **"Policies can be bypassed by calling the Service directly"** — technically yes. If you call `strapi.service().method()` directly (e.g., in a lifecycle hook or Cron Job) — the Policy is not applied. Policies only work in the HTTP pipeline. This is an architectural feature: business rules for internal calls must be checked explicitly in the Service.
