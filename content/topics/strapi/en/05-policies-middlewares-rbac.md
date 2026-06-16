# Policies, Middlewares and RBAC

## Two authorization spaces in Strapi

Strapi has two separate user spaces with different authorization mechanisms:

```txt
End Users (plugin users-permissions):
  Users who register via the API (/api/auth/local/register)
  JWT tokens, Public/Authenticated roles + custom ones
  RBAC by Content Type and action (find/findOne/create/update/delete)
  Configured in Admin Panel → Settings → Roles

Admin Users (plugin admin):
  Admin Panel users (editors, managers)
  Email/password login, session cookies
  Separate RBAC system with granular permissions
  API tokens (for CI/CD, external integrations)
```

## RBAC for End Users

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

```typescript
// Global policy: src/policies/is-admin.ts
export default async (policyContext, config, { strapi }) => {
  const { user } = policyContext.state;

  if (!user) return false; // not authenticated

  // Check role
  const userWithRole = await strapi.entityService.findOne('plugin::users-permissions.user', user.id, {
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

```txt
Criterion         Policy                          Middleware
──────────────────────────────────────────────────────────────────────
NestJS analogue   Guard                           Middleware
Purpose           Authorization (allow/deny)      Request processing
Where applied     Route.config.policies[]         Route.config.middlewares[] or globally
ctx access        Via policyContext               Directly via ctx
Return value      Boolean (true=allow, false=403) void (call next() or not)
Order             AFTER middleware                BEFORE policy
User context      ctx.state.user already set      Depends on order (auth middleware runs first)
```

## Common interview mistakes

- **"Policy and Middleware are the same thing"** — no. Middleware runs earlier (before routing and Policy). Middleware has no knowledge of the Handler. A Policy checks access to a specific route, knows about the Handler, and has access to the user via `policyContext.state.user`. Analogy: Middleware = Express middleware, Policy = NestJS Guard.

- **"RBAC for End Users and Admin Users is one system"** — no. End Users (`plugin::users-permissions`) — JWT auth, Public/Authenticated roles, permissions on Content Type actions. Admin Users — a separate system with session cookies, different roles and permissions. They do not overlap.

- **"If a Policy returns false — the error is 401"** — no. By default it's 403 (Forbidden). 401 (Unauthorized) means there is no JWT token at all. 403 means the token exists but permissions are insufficient. This can be customized by throwing an exception in the Policy: `throw new PolicyError('Custom message', { policy: 'is-admin' })`.

- **"Global middleware only applies to /api/* routes"** — no. Global middleware applies to all routes including the admin panel (/admin/*) and upload (/api/upload). Route-specific middleware only applies to the specified route.

- **"Policies can be bypassed by calling the Service directly"** — technically yes. If you call `strapi.service().method()` directly (e.g., in a lifecycle hook or Cron Job) — the Policy is not applied. Policies only work in the HTTP pipeline. This is an architectural feature: business rules for internal calls must be checked explicitly in the Service.
