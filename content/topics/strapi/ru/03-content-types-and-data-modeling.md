# Content Types и Data Modeling в Strapi

## Три вида Content Types

Content Type — это описание одного вида контента: его имя, его поля и тип каждого поля. Вы пишете это описание один раз, а Strapi превращает его в таблицу базы данных, набор эндпоинтов API и форму редактирования в Admin Panel.

Если вы уже знаете другой стек, ближайшие аналоги — таблица в реляционной базе, модель Prisma или Entity в NestJS. Видов Content Type три, и различает их то, сколько записей может существовать:

- **Collection Type** — много записей одной формы: Articles, Products, Users.
- **Single Type** — ровно одна запись, для страниц в единственном числе: Homepage, Footer, настройки SEO (search engine optimization).
- **Component** — переиспользуемый блок полей, который хранится внутри другого типа: Address, блок SEO, элемент FAQ (frequently asked questions).

Файл ниже — это схема, которую Strapi пишет для Collection Type с именем Article. Ключ `attributes` в ней перечисляет поля. Это синтаксис схемы, и он никак не связан с обёрткой `attributes`, которую Strapi v4 надевал на ответы API.

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

Single Type — это Content Type ровно с одной записью, и следит за этим сам Strapi, а не ваша дисциплина. Он нужен для частей сайта, которые существуют в единственном числе: главная страница, подвал, экран глобальных настроек.

Разница видна в API. В адресе нет идентификатора, `/api/homepage` и есть весь путь, а ответ приходит объектом, а не массивом. Эндпоинта POST нет: тот же PUT создаёт запись при первом обращении и обновляет её при всех следующих. В схеме ниже есть ещё поле `dynamiczone`, о котором рассказывает раздел через один.

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
// PUT /api/homepage   — обновить (создаст запись, если её ещё нет)
// DELETE /api/homepage — удалить запись
// Нет POST: единственный экземпляр адресуется без id
```

## Components — переиспользуемые блоки

Component — это именованная группа полей, которую вы описываете один раз и переиспользуете во многих Content Types. Своего API у неё нет, самостоятельных записей тоже: Component существует только внутри того типа, который включил его в себя.

Поведение задаёт одна настройка. При `"repeatable": false` блок появляется один раз, и поле `seo` становится одним вложенным объектом. При `"repeatable": true` блок превращается в массив — так описывают список вопросов и ответов. Файл ниже описывает Component `shared.seo` и показывает оба способа его подключить.

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

Dynamic Zone — это поле, которое хранит упорядоченный список блоков, причём каждый блок может быть другим Component. Оно существует ради редактора: страницу можно собрать из частей — баннер, список возможностей, отзывы — в любом нужном порядке.

Схема перечисляет, какие Component допустимы в этой зоне, и ничего вне этого списка туда положить нельзя. Этим Dynamic Zone отличается от repeatable-компонента, где все элементы одного типа. В ответе каждый блок несёт поле `__component` с именем своего типа. Frontend переключается по этому полю и выбирает, какой React-компонент отрисовать.

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

```json
// Ответ API с Dynamic Zone (Strapi v5: без обёртки "attributes"):
{
  "data": {
    "id": 1,
    "documentId": "hgv1vny5cebq2l3czil1rpb3",
    "sections": [
      {
        "__component": "sections.hero-banner",
        "title": "Welcome",
        "subtitle": "We build amazing products",
        "image": { "id": 5, "url": "/uploads/hero.jpg" }
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
```

```javascript
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

Draft & Publish и i18n (internationalization, интернационализация) — это две настройки, которые включаются для каждого Content Type. Обе меняют то, что отдаёт API, поэтому и стоят рядом.

Настройка `"draftAndPublish": true` в схеме даёт каждой записи две версии. У черновика в `publishedAt` стоит `null`, и виден он только в Admin Panel. У опубликованной записи в `publishedAt` стоит дата, и именно её отдаёт публичный API.

По умолчанию в ответе приходят только опубликованные версии. Параметр `?status=draft` в запросе просит вместо них черновики, а для их чтения нужен токен с подходящим правом.

```txt
publishedAt === null   → версия-черновик
publishedAt !== null   → опубликованная версия

GET /api/articles               → опубликованные (по умолчанию)
GET /api/articles?status=draft  → черновики
```

Плагин i18n, который публикуется как `@strapi/plugin-i18n`, даёт каждой записи набор локализаций. Запрос вида `GET /api/articles?locale=de` вернёт немецкую версию. Каждое поле бывает либо localized, и тогда в каждом языке у него своё значение, либо non-localized, и тогда значение одно на все локали.

## Типы полей — полный справочник

У каждого поля в схеме есть `type`, и весь список типов короткий настолько, что его можно выучить за один присест. Тип решает сразу три вещи:

- какую колонку Strapi создаст в базе данных;
- какая валидация применится при записи значения;
- какой виджет увидит редактор в Admin Panel.

Справочник ниже сгруппирован по тому, что тип хранит. Базовые типы покрывают текст, числа, булевы значения и даты. Специальные добавляют поведение поверх обычного значения: поле `uid` генерирует slug, поле `password` хешируется при сохранении. Медиа и связи указывают на то, что живёт вне самой записи.

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

- **"Single Type можно создать несколько"** — нет. Single Type физически один — повторный PUT обновляет ту же запись. Если нужно несколько Homepage-подобных сущностей — используйте Collection Type.

- **"uid поле нужно заполнять вручную"** — нет. uid поле с `targetField` автоматически генерирует slug из указанного поля (title → my-article-title). Можно переопределить вручную, но по умолчанию генерируется автоматически при создании.
