# Strapi Architecture

## Полный request lifecycle

Strapi построен на Koa.js — минималистичный Node.js фреймворк с middleware pipeline. Архитектура аналогична NestJS: request проходит через middleware → router → policy → controller → service → Document Service → DB.

```txt
HTTP Request
      ↓
  Koa Middleware Stack
  ├── CORS
  ├── Body Parser
  ├── Authentication (JWT/API Token)
  └── Error Handler
      ↓
  Router              — сопоставляет URL с handler
      ↓
  Route Middlewares   — route-специфичные middleware
      ↓
  Policies            — authorization checks (аналог Guard в NestJS)
      ↓
  Controller          — обработка request/response
      ↓
  Service             — бизнес-логика
      ↓
  Document Service    — Strapi ORM (v5+; раньше: Entity Service)
      ↓
  Query Engine        — генерация SQL/ORM запросов
      ↓
  Database (PostgreSQL / MySQL / SQLite)
```

## Koa Context vs Express req/res

```javascript
// Koa использует единый ctx объект вместо двух параметров req/res
// В custom Controller или Middleware:
module.exports = {
  async find(ctx) {
    // ctx.request — входящий запрос
    const { page, pageSize } = ctx.request.query;
    const user = ctx.state.user; // установлен auth middleware

    // ctx.response / ctx.body — ответ
    const result = await strapi.service('api::article.article').find({
      pagination: { page, pageSize },
    });

    ctx.body = result; // Koa-способ установить ответ
  },
};

// Отличие от Express:
// Express: (req, res) => { res.json(data) }
// Koa:     (ctx) => { ctx.body = data }
// Koa поддерживает async/await из коробки без express-async-errors
```

## Document Service — центральный API для данных (v5+)

```javascript
// Document Service — единый API для работы с данными в Strapi v5
// Заменил Entity Service из v4

// В Service / Controller:
const strapi = require('@strapi/strapi');

// findMany — список записей с фильтрами
const articles = await strapi.documents('api::article.article').findMany({
  filters: { publishedAt: { $notNull: true } },
  populate: ['author', 'category'],
  sort: { publishedAt: 'desc' },
  pagination: { page: 1, pageSize: 10 },
});

// findOne — одна запись
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

## Структура файлов Strapi проекта

```txt
my-strapi-project/
├── config/
│   ├── database.ts          — подключение к БД
│   ├── server.ts            — port, host, JWT secret
│   ├── middlewares.ts       — глобальные middleware
│   └── plugins.ts           — конфигурация плагинов
├── src/
│   ├── api/
│   │   └── article/         — Content Type "article"
│   │       ├── content-types/
│   │       │   └── article/
│   │       │       └── schema.json   — определение схемы
│   │       ├── controllers/
│   │       │   └── article.ts        — кастомный контроллер
│   │       ├── routes/
│   │       │   └── article.ts        — кастомные routes
│   │       └── services/
│   │           └── article.ts        — кастомный сервис
│   ├── extensions/           — расширения встроенных сервисов
│   └── middlewares/          — кастомные global middleware
├── public/
│   └── uploads/              — загруженные файлы (если не S3)
└── .env                      — DATABASE_URL, JWT_SECRET, ...
```

## Strapi vs NestJS архитектурное сравнение

```txt
Концепция          Strapi                    NestJS
──────────────────────────────────────────────────────────────
HTTP Framework     Koa                       Express/Fastify
Routing            Auto (Content Types)      Manual (@Controller)
DI Container       Нет (глобальный strapi)   Да (@Injectable)
Controller         JS/TS объект + factory    @Controller class
Service            JS/TS объект + factory    @Injectable class
Authorization      Policies                  Guards
Data Access        Document Service          Prisma/TypeORM/custom
Schema             JSON file (auto)          Code-first или ORM
Admin UI           Встроенная               Нет
Extensibility      Plugins                   Modules
```

## Plugins — расширяемость Strapi

```javascript
// Официальные плагины:
// @strapi/plugin-graphql    — GraphQL API
// @strapi/plugin-i18n       — интернационализация
// @strapi/plugin-users-permissions — auth (JWT, OAuth)
// @strapi/plugin-upload     — file upload (local/S3/Cloudinary)
// @strapi/plugin-seo        — SEO meta fields

// Кастомный плагин (собственный):
// src/plugins/my-plugin/strapi-server.ts
module.exports = {
  register({ strapi }) {
    // Регистрация кастомных сервисов, контроллеров, routes
    strapi.customFields.register({
      name: 'color',
      plugin: 'my-plugin',
      type: 'string',
    });
  },

  bootstrap({ strapi }) {
    // Инициализация после старта Strapi
    strapi.log.info('My plugin initialized');
  },
};
```

## Типичные ошибки на интервью

- **"Strapi использует Express"** — нет. Strapi использует Koa.js. Ключевое отличие: Koa использует единый `ctx` объект вместо `req/res`, поддерживает async/await нативно, меньше встроенной функциональности (более минималистичный).

- **"Document Service — это Database ORM"** — нет. Document Service — это абстракция Strapi над данными, не зависящая от типа БД. Под ним работает Query Engine который транслирует вызовы в SQL. Document Service не обращается напрямую к PostgreSQL/MySQL.

- **"Схему данных можно менять в production через Admin Panel"** — нет. Content-Type Builder (GUI для создания схем) доступен только в dev mode. В production Content Type Builder отключён. Схема хранится в `schema.json` файлах и меняется через код с последующим деплоем.

- **"Strapi — это serverless"** — нет. Strapi — это stateful сервер с постоянным process (Koa HTTP сервер). Запуск Strapi в Lambda/serverless требует специальных адаптеров и имеет cold start проблемы. Для production: PM2, Docker, Railway, Render или Strapi Cloud.

- **"У Strapi нет DI контейнера, значит нельзя организовать зависимости"** — есть глобальный объект `strapi`. Через `strapi.service('api::article.article')`, `strapi.plugin('upload').service('upload')`, `strapi.db.query('api::article.article')`. Не типизировано как NestJS DI, но достаточно для большинства задач.
