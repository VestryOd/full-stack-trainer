# Strapi Interview Questions

## Группа 1: Архитектура и концепция

**Q: Что такое Strapi и чем он отличается от WordPress?**

Strapi — open-source headless CMS на Node.js (Koa.js). "Headless" означает отсутствие presentation layer — нет встроенного frontend для конечных пользователей. WordPress объединяет backend (PHP) и frontend (шаблоны) — frontend жёстко связан с CMS. Strapi предоставляет только Admin Panel для редакторов и REST/GraphQL API для любых клиентов (React, Next.js, мобильное приложение). Архитектура: Developer создаёт Content Types → Strapi автоматически генерирует Admin UI, CRUD API, RBAC, schema.

**Q: Что происходит под капотом когда создаёшь Content Type в Strapi?**

```txt
1. Strapi создаёт schema.json в src/api/<name>/content-types/<name>/
2. При следующем запуске Strapi читает schema и синхронизирует БД:
   - Создаёт/обновляет таблицу в PostgreSQL/MySQL/SQLite
   - Создаёт таблицы для relations (junction tables для M2M)
3. Регистрирует автогенерированные routes: GET/POST/PUT/DELETE /api/<plural-name>
4. Создаёт core controller и service на основе factories
5. Обновляет Admin Panel — новый Content Type появляется в UI
6. Создаёт RBAC entries для нового Content Type (Public, Authenticated роли)

Content-Type Builder в dev mode → изменения в schema.json → restart → миграция БД
В production: только ручное редактирование schema.json + деплой
```

**Q: Strapi использует Express или что-то другое?**

Koa.js. Ключевые отличия от Express: единый `ctx` объект вместо `req/res`, нативный async/await без обёрток, onion-model middleware (вместо next() линейного). Strapi добавляет поверх Koa: router, Plugin system, Document Service, Admin Panel (embedded React app).

---

## Группа 2: Content Types и Data Modeling

**Q: В чём разница между Collection Type, Single Type и Component?**

```txt
Collection Type — множество записей, полный CRUD API
  Примеры: Articles, Products, Authors
  API: GET /api/articles (список), GET /api/articles/:id (одна)

Single Type — один экземпляр, всегда одна запись
  Примеры: Homepage, Footer, Global SEO Settings
  API: GET /api/homepage (не массив), PUT /api/homepage (обновить)
  Нет POST и DELETE

Component — переиспользуемый блок полей, нет своего API
  Примеры: SEO, Address, FAQ Item
  Всегда хранится внутри родительского Content Type
  Repeatable Component — массив компонентов одного типа
```

**Q: Что такое Dynamic Zone и когда её использовать?**

Dynamic Zone — массив компонентов разных типов. Позволяет редактору собирать страницу из блоков в любом порядке. Каждый элемент содержит `__component` поле для идентификации типа.

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

// Использовать когда:
// ✓ Marketing/Landing pages с гибкой структурой
// ✓ Page Builder для редакторов
// ✓ Разные страницы имеют разный набор блоков
// ✗ Когда структура фиксированная — Component проще
```

**Q: Чем Draft & Publish важен для production?**

Draft & Publish позволяет редакторам работать с контентом без немедленной публикации. `publishedAt === null` → Draft (не видно через публичный API). `publishedAt !== null` → Published. Public API по умолчанию возвращает ТОЛЬКО Published записи. Draft видны только в Admin Panel или через Admin API token. Важно для контент-команд: редактор готовит материал, старший редактор утверждает и публикует.

---

## Группа 3: Кастомизация — Routes, Controllers, Services

**Q: Как добавить кастомный endpoint в Strapi?**

```typescript
// 1. Создать route в отдельном файле (не в core route):
// src/api/article/routes/custom-article.ts
export default {
  routes: [{
    method: 'GET',
    path: '/articles/popular',
    handler: 'article.popular',
    config: { auth: false }, // публичный
  }],
};

// 2. Добавить метод в Controller:
// src/api/article/controllers/article.ts
export default factories.createCoreController('api::article.article', ({ strapi }) => ({
  async popular(ctx) {
    const articles = await strapi.service('api::article.article').findPopular();
    return this.transformResponse(articles);
  },
}));

// 3. Добавить метод в Service:
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

**Q: Зачем sanitizeOutput и почему его нельзя пропустить?**

`sanitizeOutput` убирает из ответа поля на которые у текущего пользователя нет прав (согласно RBAC). Без него кастомный контроллер может вернуть чувствительные данные (email, password hash, internal fields) публичному endpoint. Стандартные CRUD методы делают это автоматически. В кастомных методах нужно вызывать явно: `await this.sanitizeOutput(entity, ctx)` перед `this.transformResponse()`.

**Q: Document Service vs Query Engine — когда что использовать?**

```txt
Document Service (рекомендуется, v5+):
  strapi.documents('api::article.article').findMany(...)
  ✓ Поддерживает Draft & Publish (автоматически фильтрует)
  ✓ Поддерживает i18n локали
  ✓ Автоматическая sanitization
  ✓ populate с вложенными relations
  Используй для: стандартных CRUD операций, 90% случаев

Query Engine (низкоуровневый):
  strapi.db.query('api::article.article').findMany(...)
  ✓ Больше контроля над SQL-like запросами
  ✓ Сложные JOIN-подобные операции
  ✗ Нет автоматической Draft & Publish фильтрации
  ✗ Нет автоматической i18n поддержки
  Используй для: сложных кастомных запросов, агрегации
```

---

## Группа 4: Безопасность — Policies, Middleware, RBAC

**Q: Чем Policy отличается от Middleware в Strapi?**

```txt
Policy (аналог NestJS Guard):
  - Назначение: authorization check (allow/deny)
  - Возвращает boolean (true = пропустить, false = 403)
  - Выполняется ПОСЛЕ middleware
  - Знает о текущем Handler и пользователе (ctx.state.user)
  - Применяется к конкретным routes через route.config.policies[]

Middleware (аналог Koa/Express middleware):
  - Назначение: обработка/трансформация запроса
  - Вызывает await next() или завершает ответ
  - Выполняется ДО Policy
  - Не знает о конкретном Handler
  - Может быть global или route-specific
```

**Q: Какие есть типы авторизации в Strapi?**

```typescript
// 1. JWT (End Users через Users & Permissions plugin):
// POST /api/auth/local → { jwt, user }
// Запросы: Authorization: Bearer <jwt>

// 2. API Token (машинные клиенты):
// Admin Panel → Settings → API Tokens
// Типы: Read-only, Full-access, Custom (per Content Type + action)
// Запросы: Authorization: Bearer <api-token>

// 3. Admin Session (Admin Panel users):
// Email/password, session cookies
// Отдельный RBAC с granular permissions

// Разница JWT vs API Token:
// JWT — для конечных пользователей (регистрация/логин через API)
// API Token — для серверных интеграций (CI/CD, Next.js server-side fetch)
```

---

## Группа 5: Lifecycle Hooks и автоматизация

**Q: Когда использовать Lifecycle Hook вместо Service?**

```txt
Lifecycle Hook (beforeCreate/afterCreate/...):
  ✓ Автоматическая мутация данных перед сохранением (slug, permalink)
  ✓ Аудит — логировать каждую операцию с моделью
  ✓ Очистка кеша при обновлении записи
  ✓ Валидация на уровне данных (beforeDelete: проверить зависимости)
  ✗ НЕ сложная бизнес-логика (hidden, трудно тестировать)
  ✗ НЕ вызовы внешних API (неожиданные side effects)

Service:
  ✓ Бизнес-логика, явная и тестируемая
  ✓ Агрегация, расчёты, правила
  ✓ Взаимодействие с внешними системами
  ✓ Переиспользуется из Controller, Cron Job, другого Service
```

**Q: Как избежать дублирования Cron Job при horizontal scaling?**

При нескольких инстансах Strapi каждый запускает свои Cron Jobs независимо. Решения: (1) Distributed lock через Redis — перед выполнением задачи получить lock с TTL, только один инстанс выполнит работу; (2) вынести Cron в отдельный worker процесс/Lambda который запускается в единственном экземпляре; (3) использовать BullMQ для очереди задач с единственным worker.

**Q: Что такое bootstrap в src/index.ts и зачем он нужен?**

```typescript
// bootstrap вызывается один раз при старте Strapi после загрузки плагинов
export default {
  async bootstrap({ strapi }) {
    // Подписаться на события
    strapi.eventHub.on('entry.create', handler);

    // Seed данные при первом запуске
    const count = await strapi.documents('api::category.category').count({});
    if (count === 0) {
      await strapi.documents('api::category.category').create({ data: { name: 'General' } });
    }

    // Зарегистрировать Cron Jobs
    // Настроить внешние connections
  },

  register({ strapi }) {
    // Вызывается ДО bootstrap, ДО загрузки плагинов
    // Регистрировать кастомные providers, поля, расширения
  },
};
```

---

## Группа 6: Интеграция и production

**Q: Как правильно соединить Next.js с Strapi?**

```typescript
// Серверная сторона Next.js — использовать API Token (не JWT):
// - API Token не истекает при перезапуске сервера
// - Не нужна сессия пользователя на сервере

// next.config.js: env.STRAPI_API_TOKEN (Full-access или Custom)

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

// ISR (Incremental Static Regeneration) + Webhook для инвалидации:
// Strapi Webhook → POST /api/revalidate → next.revalidatePath()
export async function getStaticProps() {
  const data = await fetchStrapi('articles?populate=*');
  return { props: { articles: data.data }, revalidate: 3600 };
}
```

**Q: Что нужно для production деплоя Strapi?**

```txt
БД: PostgreSQL (не SQLite — SQLite только для dev)
Files: AWS S3 или Cloudinary (не local — при горизонтальном масштабировании local files теряются)
ENV variables:
  DATABASE_URL, JWT_SECRET, APP_KEYS (4 ключа!), API_TOKEN_SALT, ADMIN_JWT_SECRET
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET
Деплой: Railway, Render, Strapi Cloud, Docker (не Vercel — нет persistent process)
Admin Panel: NODE_ENV=production отключает Content-Type Builder (правильно)
Content-Type changes: через code (schema.json) + deploy (как обычный код)
CORS: config/middlewares.ts → origin: ['https://yourfrontend.com']
```

**Q: Strapi v4 vs v5 — главные различия?**

```txt
Strapi v4 (старый):
  Entity Service API: strapi.entityService.findMany(...)
  Ответ: { data: [{ id, attributes: { title, ... } }] }

Strapi v5 (новый, 2024):
  Document Service API: strapi.documents('api::...').findMany(...)
  Ответ: { data: [{ id, documentId, title, ... }] } ← нет вложенного attributes!
  documentId: строковый ID (вместо числового id в v4)
  Draft & Publish улучшен: версионирование

Критично при интеграции:
  v4: data.attributes.title
  v5: data.title  ← прямой доступ
```
