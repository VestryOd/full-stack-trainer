# Content Types and Data Modeling in Strapi

## Three kinds of Content Types

A Content Type is the primary modeling unit in Strapi. It's analogous to a DB table + Prisma Model + NestJS Entity. Three variants:

```txt
Collection Type  — multiple records (Articles, Products, Users)
Single Type      — one instance (Homepage, Footer, SEO Settings)
Component        — reusable field block (Address, SEO, FAQ Item)
```

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
// PUT /api/homepage   — update
// No POST or DELETE — one instance always
```

## Components — reusable field blocks

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

```javascript
// API response with Dynamic Zone:
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

```txt
Draft & Publish (enabled in schema "options.draftAndPublish: true"):
  Draft     — visible only in Admin Panel, not returned by the API
  Published — returned by the public API
  
  publishedAt === null → Draft
  publishedAt !== null → Published

  API returns ONLY Published records by default.
  To get Drafts: need an API token with "draft" permission or use the Admin Panel.

i18n (plugin @strapi/plugin-i18n):
  Each record has localizations
  GET /api/articles?locale=de → German version
  Fields can be localized (different values per locale)
  or non-localized (one value for all locales)
```

## Field types — complete reference

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

- **"Dynamic Zone is just an array"** — partially. A Dynamic Zone is an array, but each element can be a different type of component (unlike a Repeatable Component, where all elements are the same type). Under the hood, Strapi stores a `__component` field to determine the type during deserialization.

- **"Draft records are not visible in the API"** — correct, with a nuance. Via the public API (without an API token or with public permissions) Drafts are unavailable. But with an Admin API token (with content-manager permissions) Drafts are accessible. For frontend preview of Draft content, use Strapi Preview Mode.

- **"You can create multiple Single Types"** — no. A Single Type is physically one record — a repeated PUT updates the same record. If you need multiple Homepage-like entities, use a Collection Type.

- **"A uid field must be filled in manually"** — no. A uid field with `targetField` automatically generates a slug from the specified field (title → my-article-title). It can be overridden manually, but by default it is generated automatically on creation.
