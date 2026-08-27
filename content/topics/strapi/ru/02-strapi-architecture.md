# Strapi Architecture

## Полный request lifecycle

Strapi работает на Koa.js — минималистичном Node.js фреймворке, вся задача которого в том, чтобы передать запрос по цепочке функций, называемых middleware. Каждый запрос, доходящий до Strapi, проходит одни и те же остановки в одном и том же порядке.

Знание этого порядка и есть практическая часть: оно подсказывает, куда класть свой код. Диаграмма ниже рисует весь путь. Вот зачем нужна каждая остановка:

- **Глобальные middleware** — то, что выполняется для каждого запроса. Здесь проверяется CORS (cross-origin resource sharing), разбирается тело запроса и ловятся ошибки. Здесь же читается JWT (JSON web token) или API-токен, по которому опознают вызывающего.
- **Router** — сопоставляет URL и HTTP-глагол с одним обработчиком.
- **Route middleware** — то же самое, что глобальные middleware, но привязанное к одному маршруту.
- **Policies** — отвечают на один вопрос «да или нет»: можно ли этому вызывающему такое действие? Политика, вернувшая `false`, останавливает запрос, и контроллер не выполнится.
- **Controller** — читает запрос и собирает тело ответа.
- **Service** — держит бизнес-логику, чтобы её могли переиспользовать несколько контроллеров.
- **Document Service** — API для данных, который вызывает сервис. Он работает с документами, а не со строками таблиц.
- **Query Engine** — превращает эти вызовы в SQL (structured query language) для PostgreSQL, MySQL или SQLite.

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

Koa передаёт вашей функции один объект — контекст, который пишется как `ctx`. Express на его месте передаёт два объекта, `req` и `res`, а в Koa всё про запрос и про ответ лежит на одном объекте.

Почти вся работа идёт через три свойства. Свойство `ctx.request` — это входящий запрос, включая разобранную строку параметров. Свойство `ctx.state` хранит то, что положили туда предыдущие middleware: так Strapi передаёт дальше вошедшего пользователя в `ctx.state.user`. Присваивание в `ctx.body` — это и есть отправка ответа, вызова `res.json()` здесь нет.

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

Document Service — это API, который вы вызываете из своего кода, чтобы читать и писать контент. Он появился в Strapi v5 и заменил Entity Service из версии 4. Переименование не косметическое: он адресует документы по строке `documentId`, а не строки таблицы по числу.

Это не ORM (object-relational mapper), надстроенный над вашими таблицами. Переводом занимается Query Engine уровнем ниже, поэтому вызовы выглядят одинаково на любой базе данных.

Обращение к нему выглядит как `strapi.documents('api::article.article')`, где аргумент — уникальный идентификатор Content Type. Каждый метод принимает один объект опций, поэтому filters, populate, sort и pagination — это именованные ключи, а не позиционные аргументы.

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

Проект Strapi делится на две папки верхнего уровня, а дальше раскладка предсказуема настолько, что по ней можно ходить вслепую. В папке `config/` лежат настройки: подключение к базе данных, порт сервера и его секреты, список глобальных middleware и опции плагинов.

В папке `src/` лежит ваш код. Каждый Content Type получает одну папку внутри `src/api/`. В ней лежат четыре куска, которые Strapi сгенерировал для этого типа: схема, контроллер, маршруты и сервис. Эти файлы вы правите, чтобы добавить поведение, но не переносите: Strapi находит их по пути. Дерево ниже показывает форму для одного Content Type с именем article.

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

Strapi и NestJS пересекаются достаточно, чтобы различия легко перечислить, и почти все они следуют из одного решения. Strapi генерирует свой API по схеме, а NestJS просит написать этот API руками.

Всё в таблице — следствие этого выбора. У Strapi нет контейнера DI (dependency injection, внедрение зависимостей), потому что автоматически связывать почти нечего. Вместо него есть один глобальный объект `strapi`, у которого вы запрашиваете нужное по имени. У NestJS нет интерфейса администратора, потому что он не знает, что означают ваши данные.

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

Плагин — это пакет, который добавляет Strapi возможности, не заставляя вас править сам Strapi. Официальные плагины от команды Strapi закрывают GraphQL, i18n (internationalization, интернационализация), аутентификацию, загрузку файлов и поля для SEO (search engine optimization, оптимизация под поисковики). Плагин может добавлять маршруты, сервисы, типы контента и экраны в Admin Panel.

Свой плагин — это объект с функциями жизненного цикла, который экспортируется из `strapi-server.ts`. Первыми важны две. Функция `register` выполняется до старта сервера, раньше настройки базы данных и маршрутов. Код ниже объявляет в ней собственный тип поля. Функция `bootstrap` выполняется после загрузки всех плагинов, когда база данных, маршруты и права уже готовы.

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

- **"Document Service — это Database ORM"** — нет. Document Service — это абстракция Strapi над данными, не зависящая от типа базы данных. Под ним работает Query Engine, который транслирует вызовы в SQL. Document Service не обращается напрямую к PostgreSQL/MySQL.

- **"Схему данных можно менять в production через Admin Panel"** — нет. Content-Type Builder — графический интерфейс (GUI) для создания схем — доступен только в dev mode. В production Content Type Builder отключён. Схема хранится в `schema.json` файлах и меняется через код с последующим деплоем.

- **"Strapi — это serverless"** — нет. Strapi — это stateful сервер с постоянным process (Koa HTTP сервер). Запуск Strapi в Lambda/serverless требует специальных адаптеров и имеет cold start проблемы. Для production: PM2 (менеджер процессов для Node.js), Docker, Railway, Render или Strapi Cloud.

- **"У Strapi нет DI контейнера, значит нельзя организовать зависимости"** — есть глобальный объект `strapi`. Через `strapi.service('api::article.article')`, `strapi.plugin('upload').service('upload')`, `strapi.db.query('api::article.article')`. Не типизировано как NestJS DI, но достаточно для большинства задач.
