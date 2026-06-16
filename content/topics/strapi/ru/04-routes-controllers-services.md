# Routes, Controllers и Services

## Автогенерация vs кастомизация

При создании Content Type Strapi автоматически создаёт Route, Controller и Service с полным CRUD. Кастомизация нужна когда стандартного CRUD недостаточно: нестандартные endpoints, агрегация, внешние API, сложная бизнес-логика.

```typescript
// Автогенерированный Route (src/api/article/routes/article.ts):
import { factories } from '@strapi/strapi';

export default factories.createCoreRouter('api::article.article');
// Генерирует:
// GET    /api/articles
// GET    /api/articles/:id
// POST   /api/articles
// PUT    /api/articles/:id
// DELETE /api/articles/:id

// Автогенерированный Controller:
export default factories.createCoreController('api::article.article');

// Автогенерированный Service:
export default factories.createCoreService('api::article.article');
```

## Кастомный Controller — расширение стандартного

```typescript
// src/api/article/controllers/article.ts
import { factories } from '@strapi/strapi';

export default factories.createCoreController(
  'api::article.article',
  ({ strapi }) => ({
    // Переопределить метод find для добавления views counter
    async find(ctx) {
      // Вызвать оригинальный find через super
      const { data, meta } = await super.find(ctx);

      // Дополнительная логика
      strapi.log.info(`Articles list fetched, count: ${meta.pagination.total}`);

      return { data, meta };
    },

    // Добавить кастомный endpoint
    async popular(ctx) {
      const articles = await strapi
        .service('api::article.article')
        .findPopular(ctx.query);

      return this.transformResponse(articles);
    },

    // sanitizeOutput — убирает поля без разрешений (важно!)
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

## Кастомный Service — бизнес-логика

```typescript
// src/api/article/services/article.ts
import { factories } from '@strapi/strapi';

export default factories.createCoreService(
  'api::article.article',
  ({ strapi }) => ({
    // Расширить стандартный сервис кастомным методом
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

    // Бизнес-логика с вызовом внешнего API
    async createWithNotification(data: Record<string, unknown>) {
      const article = await strapi.documents('api::article.article').create({ data });

      // Уведомить подписчиков (внешний сервис)
      try {
        await fetch(process.env.WEBHOOK_URL!, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ event: 'article.published', articleId: article.documentId }),
        });
      } catch (error) {
        strapi.log.error('Failed to notify webhook', error);
      }

      return article;
    },

    // Агрегация данных из нескольких сущностей
    async getDashboardStats() {
      const [articles, authors, categories] = await Promise.all([
        strapi.documents('api::article.article').count({ filters: { publishedAt: { $notNull: true } } }),
        strapi.documents('api::author.author').count({}),
        strapi.documents('api::category.category').count({}),
      ]);

      return { articles, authors, categories };
    },
  }),
);
```

## Кастомный Route

```typescript
// src/api/article/routes/custom-article.ts
// ВАЖНО: кастомные routes в отдельном файле, иначе конфликт с core routes
export default {
  routes: [
    {
      method: 'GET',
      path: '/articles/popular',
      handler: 'article.popular',
      config: {
        policies: [],
        middlewares: [],
        auth: false, // публичный endpoint
      },
    },
    {
      method: 'GET',
      path: '/articles/dashboard/stats',
      handler: 'article.dashboardStats',
      config: {
        // auth: {} — требует аутентификации (default)
        policies: ['global::is-admin'], // кастомная Policy
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

```typescript
// Document Service (рекомендуется, v5+):
// Высокоуровневый API, обрабатывает populate, Draft & Publish, i18n, sanitization
const articles = await strapi.documents('api::article.article').findMany({
  filters: { author: { name: { $contains: 'Alice' } } },
  populate: ['author', 'tags'],
});

// Query Engine (низкоуровневый, v4+):
// Прямые SQL-like запросы, нет автоматической sanitization
// Используй когда Document Service недостаточно гибок
const result = await strapi.db.query('api::article.article').findMany({
  where: { publishedAt: { $notNull: true } },
  orderBy: { createdAt: 'desc' },
  populate: { author: true, tags: true },
  limit: 10,
  offset: 0,
});

// Raw SQL (крайний случай):
const [rows] = await strapi.db.connection.raw(
  'SELECT id, title, views FROM articles WHERE views > ? ORDER BY views DESC LIMIT ?',
  [1000, 10],
);
```

## Типичные ошибки на интервью

- **"Вся логика в Controller"** — антипаттерн. Controller отвечает за HTTP: читать параметры из ctx, вызвать Service, вернуть ответ. Бизнес-логика (валидация, агрегация, внешние вызовы) — в Service. Thick Controller = сложнее тестировать, сложнее переиспользовать.

- **"factories.createCoreController() нельзя расширить"** — можно. Второй аргумент — функция, возвращающая объект с методами. Через `super.find(ctx)` вызывается стандартный метод. Можно переопределить любой метод или добавить кастомный.

- **"sanitizeOutput не нужен если ты сам пишешь контроллер"** — нужен. `sanitizeOutput` убирает поля на которые у текущего пользователя нет прав (RBAC). Без него сервис может вернуть email пользователей публичному endpoint. Всегда вызывай `this.sanitizeOutput(entity, ctx)` перед `this.transformResponse()`.

- **"Кастомный route нужно добавить в тот же файл что и core route"** — нет. Core routes в `routes/article.ts` (через `createCoreRouter`), кастомные — в отдельном файле (`routes/custom-article.ts`). Strapi загружает все `.ts` файлы из папки `routes/`. Смешивание приведёт к конфликтам.

- **"Document Service и Query Engine — одно и то же"** — нет. Document Service (v5) — высокоуровневый API с поддержкой Draft & Publish, i18n, populate, sanitization. Query Engine — низкоуровневый SQL-like API без этих абстракций. Document Service рекомендован для большинства задач, Query Engine — для сложных кастомных запросов.
