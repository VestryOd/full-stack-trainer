# Policies, Middlewares и RBAC

## Два вида авторизации в Strapi

В Strapi два отдельных пространства пользователей, и у каждого своё управление доступом на основе ролей (RBAC). Права там принадлежат роли, а не человеку. Эти две системы нигде не пересекаются, и путаница между ними — самая частая ошибка в теме.

| | End Users | Admin Users |
|---|---|---|
| Кто это | Люди, которые читают ваш контент через фронтенд | Редакторы и менеджеры, работающие внутри Admin Panel |
| Плагин | `users-permissions` | `admin` |
| Как входят | Через API, например `POST /api/auth/local/register` | По email и паролю |
| Чем держится сессия | Токен JWT (JSON Web Token) в заголовке `Authorization` | Cookies |
| Роли | Встроенные Public и Authenticated плюс любые кастомные | Свои роли, отдельные от пользовательских |
| Права | По Content Type и по действию: find, findOne, create, update, delete | Подробные права по всей Admin Panel |
| Где настраивается | Admin Panel → Settings → Roles | Admin Panel → Settings |
| Машинные клиенты | — | API tokens, позволяющие программе обращаться к API без учётной записи |

## RBAC для End Users

Блок ниже — это в основном карта того, что вы отмечаете галочками в Admin Panel. Для каждой роли и каждого Content Type вы разрешаете или запрещаете пять действий: find, findOne, create, update и delete.

Трёх ролей хватает большинству проектов. Public получает неавторизованный посетитель. Authenticated получает любой вошедший пользователь. Кастомная роль вроде Editor стоит между ними: ей можно создавать и обновлять, но не удалять.

Права роли заканчиваются на уровне Content Type. Они отвечают на вопрос, кому вообще можно обновлять статьи, но не на вопрос, кому можно обновить вот эту статью. Владение записью приходится проверять в коде. Сервис в конце блока показывает обычную форму такой проверки. Загрузите запись, сравните `createdBy` с текущим пользователем и бросьте ошибку, если они не совпали.

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

Policy — это функция, которая выполняется на каждом запросе к своему route до контроллера и решает, пропустить запрос дальше или нет. Она возвращает `true`, чтобы разрешить, и `false`, чтобы заблокировать. Если не вернуть ничего, Strapi считает, что блокировать вы не хотели, поэтому явный возврат важен. Если вы знаете NestJS, это его Guard.

Каждая policy получает `policyContext` — обёртку над контекстом контроллера, которая одинаково работает для обоих слоёв запросов Strapi. Текущий пользователь лежит в `policyContext.state.user`, а параметры маршрута — в `policyContext.params`.

Где лежит файл, тем и определяется его имя в route. Файл в `src/policies/` глобальный, и на него ссылаются как `global::is-admin`. Файл в `src/api/article/policies/` принадлежит этому API, и на него ссылаются как `api::article.is-owner`. Последний пример берёт настройки из route: форма с объектом передаёт `config`, а функция читает из него `config.role`.

```typescript
// Global policy: src/policies/is-admin.ts
export default async (policyContext, config, { strapi }) => {
  const { user } = policyContext.state;

  if (!user) return false; // не авторизован

  // Проверить роль
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

Middleware — это функция, которая оборачивает запрос. Она может его прочитать, изменить и решить, пропускать ли дальше. Strapi следует соглашению Koa, поэтому middleware получает `ctx` и `next`, а вызов `await next()` передаёт управление тому, что идёт следом. Код после этого вызова выполняется на обратном пути, и именно так логгер ниже измеряет длительность.

Global middleware выполняется на каждом запросе, до маршрутизации и до любой policy. Такие middleware перечислены в `config/middlewares.ts` и выполняются в порядке этого массива. Записи с префиксом `strapi::` — встроенные, а свой файл из `src/middlewares/` встаёт в тот же список как `global::request-logger`.

Route middleware — узкий вариант. Файл в `src/api/article/middlewares/` подключается как `api::article.check-rate-limit` и работает только для тех routes, которые его перечислили. Middleware, который вернул управление, не вызвав `next()`, обрывает запрос прямо здесь. Так ограничитель ниже и отвечает кодом 429.

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

API token — это длинная секретная строка, которая позволяет программе обращаться к контентному API без учётной записи пользователя. Создаётся он в Admin Panel → Settings → API Tokens, там же выбирается срок жизни: 7, 30 или 90 дней либо бессрочно.

Клиент присылает токен в заголовке `Authorization` как bearer-токен — ровно так, как в строке с curl ниже. Для маршрутов `/api/*` Strapi проверяет его сам, поэтому писать проверку руками почти никогда не нужно.

Три типа токена задают, сколько владельцу позволено:

- Read-only разрешает только действия `find` и `findOne`.
- Full access разрешает все методы.
- Custom позволяет отметить права по каждому Content Type.

Помощник в конце читает запись о токене прямо из базы через Query Engine.

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

Обе штуки стоят между запросом и контроллером, обе могут его остановить — отсюда и путаница. Разница в назначении. Policy отвечает на один вопрос про права: да или нет. Middleware формирует запрос и ответ вокруг обработчика.

Всё остальное следует из этого. Policy возвращает булево значение и только читает. Middleware управляет потоком через `next()` и может менять запрос. Global middleware выполняется до маршрутизации, поэтому не знает, до какого обработчика дойдёт дело. Policy привязана к одному route и видит уже заполненный `ctx.state.user`.

| Критерий | Policy | Middleware |
|---|---|---|
| Аналог в NestJS | Guard | Middleware |
| Назначение | Авторизация: разрешить или запретить | Обработка запроса |
| Где применяется | `Route.config.policies[]` | `Route.config.middlewares[]` или глобально |
| Доступ к ctx | Через `policyContext` | Напрямую через `ctx` |
| Возврат | Boolean: `true` разрешает, `false` даёт 403 | void: вызвать `next()` или не вызывать |
| Порядок | После middleware | До policy |
| User context | `ctx.state.user` уже доступен | Зависит от порядка, auth middleware раньше |

## Типичные ошибки на интервью

- **"Policy и Middleware — одно и то же"** — нет. Middleware выполняется раньше (до routing и Policy). Middleware не знает о Handler. Policy — это проверка доступа к конкретному route, знает о Handler, имеет доступ к user через `policyContext.state.user`. Аналогия: Middleware = Express middleware, Policy = NestJS Guard.

- **"RBAC для End Users и Admin Users — одна система"** — нет. End Users (`plugin::users-permissions`) — JWT auth, роли Public/Authenticated, права на Content Type actions. Admin Users — отдельная система с session cookies, разными ролями и permissions. Они не пересекаются.

- **"Если Policy вернула false — ошибка 401"** — нет. По умолчанию 403 (Forbidden). 401 (Unauthorized) — если нет JWT токена вообще. 403 — если токен есть но прав недостаточно. Можно кастомизировать выбрасывая исключение в Policy: `throw new PolicyError('Custom message', { policy: 'is-admin' })`.

- **"Global middleware применяется только к /api/* routes"** — нет. Global middleware применяется ко всем routes включая admin panel (/admin/*) и upload (/api/upload). Route-specific middleware — только к указанному route.

- **"Можно обойти Policy через прямой вызов Service"** — технически да. Если ты вызываешь `strapi.service().method()` напрямую (например в lifecycle hook или Cron Job) — Policy не применяется. Policy работает только в HTTP pipeline. Это особенность архитектуры: бизнес-правила для внутренних вызовов нужно проверять в Service явно.
