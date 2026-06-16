# Policies, Middlewares и RBAC

## Два вида авторизации в Strapi

Strapi имеет два отдельных пользовательских пространства с разными механизмами авторизации:

```txt
End Users (plugin users-permissions):
  Пользователи которые регистрируются через API (/api/auth/local/register)
  JWT токены, роли Public/Authenticated + кастомные
  RBAC по Content Types и actions (find/findOne/create/update/delete)
  Настраивается в Admin Panel → Settings → Roles

Admin Users (plugin admin):
  Пользователи Admin Panel (редакторы, менеджеры)
  Email/password логин, session cookies
  Отдельная система RBAC с granular permissions
  API tokens (для CI/CD, внешних интеграций)
```

## RBAC для End Users

```typescript
// Admin Panel → Settings → Users & Permissions → Roles

// Public role (неавторизованные пользователи):
// Обычно: GET /api/articles (find, findOne) — открыто
// POST/PUT/DELETE — запрещено

// Authenticated role (JWT users):
// Доступ к created-by своим контентом
// Дополнительные права по бизнес-логике

// Кастомная роль "Editor":
// find, findOne, create, update — разрешено
// delete — запрещено
// Доступ только к своим записям (createdBy filter)

// Программная проверка прав в Service:
async updateArticle(documentId: string, data: any, user: any) {
  const article = await strapi.documents('api::article.article').findOne({
    documentId,
    fields: ['id'],
    populate: { createdBy: { fields: ['id'] } },
  });

  // Проверить ownership
  if (article.createdBy?.id !== user.id && user.role.name !== 'Admin') {
    throw new Error('Forbidden: not the owner');
  }

  return strapi.documents('api::article.article').update({ documentId, data });
}
```

## Policy — аналог Guard в NestJS

```typescript
// Global policy: src/policies/is-admin.ts
export default async (policyContext, config, { strapi }) => {
  const { user } = policyContext.state;

  if (!user) return false; // не авторизован

  // Проверить роль
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

// Применение в route:
{
  method: 'PUT',
  path: '/articles/:id',
  handler: 'article.update',
  config: {
    policies: [
      'global::is-admin',          // ИЛИ
      'api::article.is-owner',     // оба должны вернуть true
    ],
  },
}

// Policy с конфигурацией:
export default async (policyContext, config, { strapi }) => {
  const requiredRole = config.role ?? 'Admin'; // config из route
  return policyContext.state.user?.role?.name === requiredRole;
};

// Route:
config: { policies: [{ name: 'global::has-role', config: { role: 'Editor' } }] }
```

## Middleware — обработка запроса до Policy

```typescript
// Global middleware: src/middlewares/request-logger.ts
export default () => {
  return async (ctx, next) => {
    const start = Date.now();

    await next(); // вызвать следующий middleware / controller

    const duration = Date.now() - start;
    strapi.log.info(`${ctx.method} ${ctx.url} - ${ctx.status} (${duration}ms)`);
  };
};

// Регистрация global middleware в config/middlewares.ts:
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
  'global::request-logger', // кастомный
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

// Применение в route:
{
  method: 'POST',
  path: '/articles',
  handler: 'article.create',
  config: {
    middlewares: ['api::article.check-rate-limit'],
  },
}
```

## API Tokens — для машинных клиентов

```typescript
// Admin Panel → Settings → API Tokens → Create

// Типы токенов:
// Read-only  — только GET запросы
// Full-access — все методы
// Custom     — granular permissions per Content Type

// Использование:
// curl -H "Authorization: Bearer <token>" https://api.example.com/api/articles

// В кастомном коде — проверить токен:
const verifyApiToken = async (token: string) => {
  // Strapi делает это автоматически для всех /api/* routes
  // Но если нужно вручную:
  const tokenRecord = await strapi.db.query('admin::api-token').findOne({
    where: { accessKey: token },
    populate: ['permissions'],
  });
  return tokenRecord;
};
```

## Policy vs Middleware — ключевые различия

```txt
Критерий          Policy                          Middleware
──────────────────────────────────────────────────────────────────────
Аналог в NestJS   Guard                           Middleware
Назначение        Authorization (allow/deny)      Обработка запроса
Где применяется   Route.config.policies[]         Route.config.middlewares[] или глобально
Доступ к ctx      Через policyContext             Напрямую ctx
Возврат           Boolean (true=allow, false=403) void (вызвать next() или не вызывать)
Порядок           ПОСЛЕ middleware                ДО policy
User context      ctx.state.user уже доступен     Зависит от порядка (auth middleware раньше)
```

## Типичные ошибки на интервью

- **"Policy и Middleware — одно и то же"** — нет. Middleware выполняется раньше (до routing и Policy). Middleware не знает о Handler. Policy — это проверка доступа к конкретному route, знает о Handler, имеет доступ к user через `policyContext.state.user`. Аналогия: Middleware = Express middleware, Policy = NestJS Guard.

- **"RBAC для End Users и Admin Users — одна система"** — нет. End Users (`plugin::users-permissions`) — JWT auth, роли Public/Authenticated, права на Content Type actions. Admin Users — отдельная система с session cookies, разными ролями и permissions. Они не пересекаются.

- **"Если Policy вернула false — ошибка 401"** — нет. По умолчанию 403 (Forbidden). 401 (Unauthorized) — если нет JWT токена вообще. 403 — если токен есть но прав недостаточно. Можно кастомизировать выбрасывая исключение в Policy: `throw new PolicyError('Custom message', { policy: 'is-admin' })`.

- **"Global middleware применяется только к /api/* routes"** — нет. Global middleware применяется ко всем routes включая admin panel (/admin/*) и upload (/api/upload). Route-specific middleware — только к указанному route.

- **"Можно обойти Policy через прямой вызов Service"** — технически да. Если ты вызываешь `strapi.service().method()` напрямую (например в lifecycle hook или Cron Job) — Policy не применяется. Policy работает только в HTTP pipeline. Это особенность архитектуры: бизнес-правила для внутренних вызовов нужно проверять в Service явно.
