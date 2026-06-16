# Content Types и Data Modeling в Strapi

## Три вида Content Types

Content Type — основная единица моделирования в Strapi. Аналог таблицы в БД + Prisma Model + NestJS Entity. Три варианта:

```txt
Collection Type  — множество записей (Articles, Products, Users)
Single Type      — один экземпляр (Homepage, Footer, SEO Settings)
Component        — переиспользуемый блок полей (Address, SEO, FAQ Item)
```

```json
// Пример schema.json для Collection Type "Article":
// src/api/article/content-types/article/schema.json
{
  "kind": "collectionType",
  "collectionName": "articles",
  "info": {
    "singularName": "article",
    "pluralName": "articles",
    "displayName": "Article"
  },
  "options": {
    "draftAndPublish": true
  },
  "attributes": {
    "title": {
      "type": "string",
      "required": true,
      "maxLength": 255
    },
    "slug": {
      "type": "uid",
      "targetField": "title"
    },
    "content": {
      "type": "richtext"
    },
    "coverImage": {
      "type": "media",
      "multiple": false,
      "allowedTypes": ["images"]
    },
    "author": {
      "type": "relation",
      "relation": "manyToOne",
      "target": "api::author.author",
      "inversedBy": "articles"
    },
    "category": {
      "type": "relation",
      "relation": "manyToOne",
      "target": "api::category.category"
    },
    "tags": {
      "type": "relation",
      "relation": "manyToMany",
      "target": "api::tag.tag"
    }
  }
}
```

## Single Type — уникальные страницы сайта

```json
// src/api/homepage/content-types/homepage/schema.json
{
  "kind": "singleType",
  "collectionName": "homepages",
  "info": {
    "singularName": "homepage",
    "pluralName": "homepages",
    "displayName": "Homepage"
  },
  "attributes": {
    "heroTitle": { "type": "string" },
    "heroSubtitle": { "type": "text" },
    "heroImage": { "type": "media", "multiple": false },
    "sections": {
      "type": "dynamiczone",
      "components": [
        "sections.hero",
        "sections.features",
        "sections.testimonials",
        "sections.faq"
      ]
    }
  }
}

// API для Single Type:
// GET /api/homepage   — одна запись (не массив!)
// PUT /api/homepage   — обновить
// Нет POST и DELETE — один экземпляр всегда
```

## Components — переиспользуемые блоки

```json
// src/components/shared/seo.json
{
  "collectionName": "components_shared_seos",
  "info": {
    "displayName": "SEO",
    "icon": "search"
  },
  "attributes": {
    "metaTitle": { "type": "string", "required": true },
    "metaDescription": { "type": "text", "required": true },
    "keywords": { "type": "string" },
    "ogImage": { "type": "media", "multiple": false }
  }
}

// Использование в Article:
"seo": {
  "type": "component",
  "repeatable": false,
  "component": "shared.seo"
}

// Repeatable Component — массив блоков:
"faqItems": {
  "type": "component",
  "repeatable": true,
  "component": "sections.faq-item"
}
// faqItems: [{ question: "...", answer: "..." }, { ... }]
```

## Dynamic Zone — конструктор страниц

```json
// Позволяет редактору собирать страницу из разных блоков в любом порядке
"sections": {
  "type": "dynamiczone",
  "components": [
    "sections.hero-banner",
    "sections.feature-list",
    "sections.testimonials",
    "sections.faq",
    "sections.cta-button"
  ]
}
```

```javascript
// Ответ API с Dynamic Zone:
{
  "data": {
    "id": 1,
    "attributes": {
      "sections": [
        {
          "__component": "sections.hero-banner",
          "title": "Welcome",
          "subtitle": "We build amazing products",
          "image": { "data": { "id": 5, "attributes": { "url": "/uploads/hero.jpg" } } }
        },
        {
          "__component": "sections.faq",
          "items": [
            { "question": "How does it work?", "answer": "..." }
          ]
        }
      ]
    }
  }
}

// Frontend (Next.js) рендерит компонент по __component:
function renderSection(section) {
  switch (section.__component) {
    case 'sections.hero-banner': return <HeroBanner {...section} />;
    case 'sections.faq':         return <FAQ items={section.items} />;
    default: return null;
  }
}
```

## Draft & Publish и i18n

```txt
Draft & Publish (включено в schema "options.draftAndPublish: true"):
  Draft     — видно только в Admin Panel, не возвращается в API
  Published — возвращается публичным API
  
  publishedAt === null → Draft
  publishedAt !== null → Published

  API по умолчанию возвращает ТОЛЬКО Published записи.
  Для получения Draft: нужен API token с правом "draft" или в Admin Panel.

i18n (плагин @strapi/plugin-i18n):
  Каждая запись имеет localizations
  GET /api/articles?locale=de → немецкая версия
  Поля могут быть localized (разные значения per locale)
  или non-localized (одно значение для всех локалей)
```

## Типы полей — полный справочник

```txt
Базовые:
  string      — короткий текст (VARCHAR)
  text        — длинный текст (TEXT)
  richtext    — HTML/Markdown редактор
  number      — целое или дробное (integer / decimal)
  boolean     — true/false
  date        — дата (DATE)
  datetime    — дата + время (TIMESTAMP)
  time        — только время

Специальные:
  uid         — slug, автогенерация из targetField
  email       — валидация email
  password    — хеширование при сохранении
  enumeration — enum значения
  json        — произвольный JSON объект
  blocks      — Strapi Blocks Editor (rich content)

Медиа:
  media       — файл/изображение через Upload plugin

Связи:
  relation    — oneToOne, oneToMany, manyToOne, manyToMany
  component   — встроенный компонент
  dynamiczone — массив разнотипных компонентов
```

## Типичные ошибки на интервью

- **"Component — это то же самое что Collection Type"** — нет. Component не имеет своего API, не создаёт самостоятельной сущности. Это переиспользуемый блок полей, который всегда хранится внутри родительского Content Type. Collection Type — самостоятельная сущность с собственным API.

- **"Dynamic Zone — это просто массив"** — частично. Dynamic Zone — массив, но каждый элемент может быть разного типа компонента (в отличие от Repeatable Component, где все элементы одного типа). Под капотом Strapi хранит `__component` поле для определения типа при десериализации.

- **"Draft записи не видны в API"** — правильно, но с нюансом. Через публичный API (без API token или с публичными правами) Draft недоступны. Но с Admin API token (с правами content-manager) Draft доступны. Для frontend preview (предпросмотр Draft контента) используют Strapi Preview Mode.

- **"Single Type можно создать несколько"** — нет. Single Type физически один — повторный PUT обновляет ту же запись. Если нужно несколько Homepage-подобных сущностей — используй Collection Type.

- **"uid поле нужно заполнять вручную"** — нет. uid поле с `targetField` автоматически генерирует slug из указанного поля (title → my-article-title). Можно переопределить вручную, но по умолчанию генерируется автоматически при создании.
