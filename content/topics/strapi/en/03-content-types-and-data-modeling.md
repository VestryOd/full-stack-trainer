# Content Types and Data Modeling in Strapi

## The Most Important Concept in Strapi

All of Strapi is built around:

```txt
Content Types
```

---

You can think of them as:

```txt
Content Type
≈
Entity
≈
Database Table
≈
Prisma Model
```

---

For example:

```txt
Article
Category
Author
Product
```

---

Each Content Type becomes:

```txt
Database Table
REST API
GraphQL Type
Admin UI Form
```

---

# Collection Type

The most common variant.

---

Imagine:

```txt
Articles
```

---

We can have:

```txt
Article 1
Article 2
Article 3
Article 4
```

---

The number of records is unlimited.

---

This is a:

```txt
Collection Type
```

---

# Example

```txt
Article
```

Fields:

```txt
title
slug
content
publishedAt
```

---

After creation, Strapi automatically generates:

```http
GET /api/articles

GET /api/articles/:id

POST /api/articles

PUT /api/articles/:id

DELETE /api/articles/:id
```

---

Very similar to CRUD.

---

# Single Type

A very popular interview question.

---

A Single Type exists in only one instance.

---

Example:

```txt
Homepage
```

---

You cannot create:

```txt
Homepage 1
Homepage 2
Homepage 3
```

---

Only one exists:

```txt
Homepage
```

---

# Typical Single Types

```txt
Homepage
Footer
Header
SEO Settings
Company Settings
Contacts Page
```

---

# Collection vs Single

Collection:

```txt
many records
```

---

Single:

```txt
one record
```

---

# Component

One of Strapi's strongest features.

---

Imagine:

```txt
Address
```

---

Fields:

```txt
country
city
street
zip
```

---

This block is needed by:

```txt
User
Company
Office
```

---

To avoid duplicating fields,
we create a:

```txt
Component
```

---

# Usage

```txt
User
 └─ Address Component

Company
 └─ Address Component
```

---

Very similar to:

```txt
Embedded Value Object
```

---

# Repeatable Component

An array of components.

---

Example:

```txt
FAQ
```

---

One item:

```txt
question
answer
```

---

A page may have:

```txt
10 FAQ items
```

---

We use a:

```txt
Repeatable Component
```

---

# Dynamic Zone

A very popular interview topic.

---

A unique Strapi feature.

---

Allows building a page
from different blocks.

---

Example:

```txt
Hero Section
Gallery
Testimonials
FAQ
CTA
```

---

The editor can choose:

```txt
which blocks will be on the page
```

---

Diagram:

```txt
Page
 ↓
Dynamic Zone
 ↓
Hero
Gallery
FAQ
CTA
```

---

Very convenient for marketing websites.

---

# Relationships

Standard relations are supported.

---

One-To-One

```txt
User
 ↓
Profile
```

---

One-To-Many

```txt
Author
 ↓
Articles
```

---

Many-To-Many

```txt
Article
 ↕
Tags
```

---

# Media Fields

Built-in file support.

---

For example:

```txt
avatar
coverImage
gallery
```

---

Files are stored via the:

```txt
Upload Plugin
```

---

Locally.

Or via:

```txt
AWS S3
Cloudinary
Azure Blob
```

---

# Draft & Publish

A very popular feature.

---

Content can be:

```txt
Draft
```

or

```txt
Published
```

---

While a record is not published:

```txt
the frontend won't see it
```

---

# Internationalization (i18n)

Localization plugin.

---

For example:

```txt
English
German
French
```

---

One article.

Multiple language versions.

---

# What Happens Under the Hood

We create:

```txt
Article
```

---

Strapi automatically:

1. Creates the table.
2. Creates relations.
3. Updates the Admin UI.
4. Generates an API.
5. Generates GraphQL types.

---

# Frequent Question

What would you use for a Homepage?

Answer:

```txt
Single Type
```

---

For Blog Posts?

Answer:

```txt
Collection Type
```

---

# Interview Answer

Strapi uses Content Types as the primary unit of data modeling. Collection Types are designed to store many records, while Single Types are for unique entities such as Homepage or Settings. Components are used for reusing data structures, and Dynamic Zones are used for building flexible pages.
