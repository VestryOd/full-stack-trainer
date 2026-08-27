# Routes, Controllers и Services

## Автогенерация vs кастомизация

При создании Content Type Strapi автоматически создаёт Route, Controller и Service с полным CRUD, то есть создание, чтение, обновление и удаление записи. Кастомизация нужна когда стандартного CRUD недостаточно: нестандартные endpoints, агрегация, внешние API, сложная бизнес-логика.

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

Controller — это файл с методами, которым route передаёт запрос. В Strapi такие методы называют actions. Controller отвечает за сторону HTTP: прочитать параметры из `ctx`, вызвать Service и вернуть ответ.

Фабрика `createCoreController` принимает второй аргумент — функцию, которая получает `{ strapi }` и возвращает объект с методами. Метод, названный именем стандартного (`find`, `findOne`, `create`, `update`, `delete`), заменяет его, а любое другое имя добавляет новый endpoint. Внутри заменённого метода вызов `super.find(ctx)` по-прежнему выполняет оригинальную реализацию.

Ниже встретятся два помощника. Метод `sanitizeOutput` убирает поля, читать которые у текущего пользователя нет прав, — это управление доступом на основе ролей (RBAC) в применении к ответу. Метод `transformResponse` заворачивает результат в стандартную форму с полями `data` и `meta`.

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

Service — это набор переиспользуемых функций, в которых живёт бизнес-логика конкретного API. Когда логика вынесена из контроллера, один и тот же код могут вызвать несколько контроллеров, хуки или Cron Jobs, а не копировать его у себя.

Фабрика `createCoreService` устроена так же, как фабрика контроллера: те же два аргумента. Методы, которые она возвращает, доступны снаружи как `strapi.service('api::article.article').findPopular(...)`, и именно так до этого файла добирается контроллер выше.

Дальше идут три вида логики:

- чтение с фильтрами через Document Service;
- создание записи с уведомлением внешней системы;
- агрегация, которая параллельно считает три Content Type.

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

    // Агрегация данных из нескольких сущностей
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

## Кастомный Route

Route связывает один метод HTTP и один путь с одним методом контроллера. Стандартный router уже генерирует пять привычных endpoints, поэтому свой файл роутов нужен только для того, что выходит за их рамки.

Кастомные routes кладут в отдельный файл внутри той же папки `routes/`. Strapi загружает оттуда все файлы в алфавитном порядке, и разделение кастомных записей с core-роутером избавляет от конфликтов. У каждой записи есть `method`, `path` и `handler`, где `article.popular` означает метод `popular` контроллера article.

Необязательный объект `config` несёт защиту маршрута. По умолчанию route требует аутентификации, а `auth: false` открывает его всем. Массив `policies` перечисляет проверки, которые должны пройти. Массив `middlewares` перечисляет код, который выполняется вокруг обработчика.

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

До базы данных в Strapi есть два пути, и они не взаимозаменяемы. Document Service — способ по умолчанию в v5. Он понимает Draft & Publish, интернационализацию (i18n), populate и очистку ответа, а записи адресует по `documentId`.

Query Engine лежит уровнем ниже. Он почти напрямую ложится на SQL (язык структурированных запросов) и этих возможностей не даёт. Документация советует брать его только тогда, когда Document Service не выражает нужный запрос.

Отличить их в коде проще всего по словарю. Document Service принимает `filters`, `sort` и `pagination`. Query Engine принимает `where`, `orderBy`, `limit` и `offset`.

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
