# Headless CMS и Strapi

## Что такое Headless CMS

Традиционные CMS (WordPress, Drupal) объединяют backend и frontend в одном приложении: контент хранится в БД, рендеринг происходит на сервере через PHP-шаблоны. Frontend жёстко привязан к конкретной CMS.

Headless CMS убирает "голову" — presentation layer. Остаётся только Content Management + API. Frontend (React, Next.js, мобильное приложение) сам решает как отображать данные.

```txt
Traditional CMS:                    Headless CMS (Strapi):
──────────────────                  ──────────────────────────────────
Editor                              Editor
  ↓                                   ↓
WordPress/Drupal                    Strapi Admin
  ↓                                   ↓
PHP Templates                       REST API / GraphQL
  ↓                                   ↓
HTML → Browser                      React / Next.js / Mobile / TV App
                                    (каждый клиент рендерит сам)
```

## Что такое Strapi

Strapi — open-source headless CMS на Node.js (под капотом Koa.js). Разработчик описывает модели данных (Content Types), Strapi автоматически генерирует:

- REST API и GraphQL API
- Admin Panel для управления контентом
- RBAC (Role-Based Access Control)
- Media upload (S3, Cloudinary)
- Webhooks

```txt
Strapi stack:
  Node.js + Koa.js              — HTTP сервер
  @strapi/database              — ORM (SQLite / PostgreSQL / MySQL)
  Admin Panel (React)           — embedded frontend для редакторов
  Content-Type Builder          — GUI для создания схем (только dev mode)
  Plugin system                 — расширяемость (i18n, GraphQL, email, ...)
```

## REST API из коробки

```typescript
// После создания Content Type "Article" Strapi генерирует:
// GET    /api/articles                — список статей
// GET    /api/articles/:id            — одна статья
// POST   /api/articles                — создать
// PUT    /api/articles/:id            — обновить
// DELETE /api/articles/:id            — удалить

// Запрос с фильтрацией, сортировкой, пагинацией, populate:
// GET /api/articles?
//   filters[category][name][$eq]=Tech&
//   sort[0]=publishedAt:desc&
//   pagination[page]=1&
//   pagination[pageSize]=10&
//   populate[author][fields][0]=name&
//   populate[author][fields][1]=avatar

// Ответ:
{
  "data": [
    {
      "id": 1,
      "attributes": {
        "title": "Getting Started with Strapi",
        "publishedAt": "2024-01-15T10:00:00.000Z",
        "author": {
          "data": {
            "id": 5,
            "attributes": { "name": "Alice", "avatar": "..." }
          }
        }
      }
    }
  ],
  "meta": {
    "pagination": { "page": 1, "pageSize": 10, "total": 42, "pageCount": 5 }
  }
}
```

## Strapi vs традиционный NestJS/Express

```txt
Критерий              Strapi                        NestJS/Express
──────────────────────────────────────────────────────────────────────
Time-to-first-API     Минуты (GUI builder)          Часы/дни (ручной код)
Кастомизация          Ограничена плагинами          Полная свобода
Бизнес-логика         Через хуки/кастомные routes   Нет ограничений
Масштабируемость      Средняя (monolith)            Высокая (microservices)
Admin Panel           Встроенная                    Нужно строить
RBAC                  Встроенный                    Нужно строить
Подходит для          CMS, маркетинг, каталоги      Любая сложная логика
Не подходит для       High-load, сложный domain     Простой CMS (overkill)
```

## Когда выбирать Strapi

```txt
Strapi — хороший выбор:
  ✓ Marketing site / корпоративный сайт
  ✓ Blog, новостной портал
  ✓ E-commerce каталог (не платёжная логика)
  ✓ Mobile app backend с простыми CRUD операциями
  ✓ MVP где нужно быстро получить API
  ✓ Команда включает non-developer редакторов

Strapi — плохой выбор:
  ✗ Сложная бизнес-логика (trading, banking, ERP)
  ✗ High-load (>10k req/sec — Strapi не масштабируется горизонтально просто)
  ✗ Microservices (Strapi — монолит)
  ✗ Нужен полный контроль над БД схемой
  ✗ Нестандартная авторизация
```

## Типичные ошибки на интервью

- **"Strapi заменяет NestJS"** — нет. Strapi — CMS для управления контентом. NestJS — фреймворк для создания любых Node.js приложений. Strapi использует Koa внутри и не является альтернативой NestJS/Express для сложной бизнес-логики.

- **"Headless CMS не имеет admin panel"** — нет. "Headless" означает что нет публичного frontend (presentation layer). Admin Panel для редакторов — есть. Strapi включает полноценный React-based admin UI. "Headless" = нет шаблонизации для конечных пользователей.

- **"Strapi работает только с REST"** — нет. Strapi поддерживает GraphQL через официальный плагин `@strapi/plugin-graphql`. После установки плагина автоматически генерируются queries, mutations и subscriptions для всех Content Types.

- **"Content Types в Strapi можно создавать в production"** — нет. Content-Type Builder доступен только в development mode. В production изменения схемы делаются через код (schema files в `src/api/`) и деплоятся как обычный код. Это принципиально важно для стабильности production.

- **"Strapi v4 и v5 — одно и то же"** — нет. Strapi v5 (2024) — крупный breaking change: новый Document Service API вместо Entity Service, новый query engine, улучшенная типизация. API ответы имеют другую структуру (убраны вложенные `attributes`). Важно уточнять версию в разговоре об API структуре.
