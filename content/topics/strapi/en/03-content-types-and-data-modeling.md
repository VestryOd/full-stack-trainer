# Content Types and Data Modeling in Strapi

## Three kinds of Content Types

A Content Type is a description of one kind of content: its name, its fields, and the type of each field. You write it once, and Strapi turns it into a database table, a set of API endpoints, and an editing form for the Admin Panel.

If you already know another stack, the nearest equivalents are a table in a relational database, a Prisma model, or an Entity in NestJS. Strapi has three kinds of Content Type, and what separates them is how many records can exist:

- **Collection Type** — many records of the same shape: Articles, Products, Users.
- **Single Type** — exactly one record, for pages that exist once: Homepage, Footer, SEO (search engine optimization) settings.
- **Component** — a reusable block of fields stored inside another type: Address, SEO block, FAQ (frequently asked questions) item.

The file below is the schema Strapi writes for a Collection Type named Article. Its `attributes` key is where the fields are listed. That key is schema syntax, and it is unrelated to the `attributes` wrapper that Strapi v4 put around API responses.

```json
// Example schema.json for Collection Type "Article":
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

## Single Type — unique site pages

A Single Type is a Content Type that has exactly one record, and Strapi enforces that rather than trusting you to keep it. Use it for parts of a site that exist once: the homepage, the footer, a global settings screen.

The difference shows up in the API. The path has no id in it — `/api/homepage` is the whole address — and the answer is an object rather than an array. There is no POST endpoint: the same PUT creates the record the first time and updates it on every call after that. The schema below also uses a `dynamiczone` field, which the section after next explains.

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

// API for a Single Type:
// GET /api/homepage   — one record (not an array!)
// PUT /api/homepage   — update (creates the record if it does not exist yet)
// DELETE /api/homepage — delete the record
// No POST: the single instance is addressed without an id
```

## Components — reusable field blocks

A Component is a named group of fields that you define once and reuse in many Content Types. It has no API of its own and no independent records: a Component exists only inside whatever type embeds it.

One setting decides how it behaves. With `"repeatable": false` the block appears once, so a `seo` field becomes a single nested object. With `"repeatable": true` the block becomes an array, which is how a list of FAQ entries is modelled. The file below defines a `shared.seo` Component and then shows both ways of attaching it.

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

// Usage in Article:
"seo": {
  "type": "component",
  "repeatable": false,
  "component": "shared.seo"
}

// Repeatable Component — array of blocks:
"faqItems": {
  "type": "component",
  "repeatable": true,
  "component": "sections.faq-item"
}
// faqItems: [{ question: "...", answer: "..." }, { ... }]
```

## Dynamic Zone — page builder

A Dynamic Zone is a field that holds an ordered list of blocks, where each block may be a different Component. It exists so an editor can assemble a page from parts: a hero banner, a feature list, testimonials, in whatever order the page needs.

The schema names the Components allowed in the zone, and nothing outside that list can be placed there. This is what separates it from a repeatable Component, where every element is the same Component. In the response each block carries a `__component` field naming its type. The frontend switches on that field to choose which React component to render.

```json
// Allows an editor to assemble a page from different blocks in any order
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
// API response with Dynamic Zone (Strapi v5: no "attributes" wrapper):
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
// Frontend (Next.js) renders components by __component:
function renderSection(section) {
  switch (section.__component) {
    case 'sections.hero-banner': return <HeroBanner {...section} />;
    case 'sections.faq':         return <FAQ items={section.items} />;
    default: return null;
  }
}
```

## Draft & Publish and i18n

Draft & Publish and i18n (internationalization) are two options you switch on per Content Type. Both of them change what the API gives back, so they belong together.

Setting `"draftAndPublish": true` in the schema gives every record two versions. A draft has `publishedAt` set to `null` and is visible in the Admin Panel. A published record has a date in `publishedAt` and is what the public API returns.

The default answer contains published versions only. Adding `?status=draft` to the request asks for the draft versions instead, and reading them needs a token with the matching permission.

```txt
publishedAt === null   → draft version
publishedAt !== null   → published version

GET /api/articles                 → published versions (the default)
GET /api/articles?status=draft    → draft versions
```

The i18n plugin, published as `@strapi/plugin-i18n`, gives each record a set of localizations. A request such as `GET /api/articles?locale=de` returns the German version. Each field is marked either localized or non-localized. A localized field holds a different value in every language. A non-localized one shares a single value across all locales.

## Field types — complete reference

Every field in a schema has a `type`, and the whole list of types is short enough to learn in one sitting. The type decides three things at once:

- the column Strapi creates in the database;
- the validation applied when a value is written;
- the widget an editor sees in the Admin Panel.

The reference below groups the types by what they hold. Basic types cover text, numbers, booleans and dates. Special types add behaviour on top of a plain value: a `uid` field generates a slug, and a `password` field is hashed on save. Media and relation types point at something that lives outside the record itself.

```txt
Basic:
  string      — short text (VARCHAR)
  text        — long text (TEXT)
  richtext    — HTML/Markdown editor
  number      — integer or decimal
  boolean     — true/false
  date        — date (DATE)
  datetime    — date + time (TIMESTAMP)
  time        — time only

Special:
  uid         — slug, auto-generated from targetField
  email       — email validation
  password    — hashed on save
  enumeration — enum values
  json        — arbitrary JSON object
  blocks      — Strapi Blocks Editor (rich content)

Media:
  media       — file/image via the Upload plugin

Relations:
  relation    — oneToOne, oneToMany, manyToOne, manyToMany
  component   — embedded component
  dynamiczone — array of mixed-type components
```

## Common interview mistakes

- **"A Component is the same as a Collection Type"** — no. A Component has no API of its own and does not create an independent entity. It is a reusable block of fields always stored inside a parent Content Type. A Collection Type is an independent entity with its own API.

- **"Dynamic Zone is just an array"** — partially. A Dynamic Zone is an array, but each element can be a different type of component. A Repeatable Component is the opposite: every element there is the same type. Under the hood, Strapi stores a `__component` field to determine the type during deserialization.

- **"Draft records are not visible in the API"** — correct, with a nuance. Via the public API (without an API token or with public permissions) Drafts are unavailable. But with an Admin API token (with content-manager permissions) Drafts are accessible. For frontend preview of Draft content, use Strapi Preview Mode.

- **"You can create multiple Single Types"** — no. A Single Type is physically one record — a repeated PUT updates the same record. If you need multiple Homepage-like entities, use a Collection Type.

- **"A uid field must be filled in manually"** — no. A uid field with `targetField` automatically generates a slug from the specified field (title → my-article-title). It can be overridden manually, but by default it is generated automatically on creation.
