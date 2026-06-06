<!-- verified: 2026-06-05, corrections: 0 -->
# Content Types и Data Modeling в Strapi

## Самая важная концепция Strapi

Весь Strapi построен вокруг:

```txt
Content Types
```

---

Можно считать:

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

Например:

```txt
Article
Category
Author
Product
```

---

Каждый Content Type становится:

```txt
Database Table
REST API
GraphQL Type
Admin UI Form
```

---

# Collection Type

Самый распространенный вариант.

---

Представим:

```txt
Articles
```

---

У нас может быть:

```txt
Article 1
Article 2
Article 3
Article 4
```

---

Количество записей не ограничено.

---

Это:

```txt
Collection Type
```

---

# Пример

```txt
Article
```

Поля:

```txt
title
slug
content
publishedAt
```

---

После создания Strapi автоматически генерирует:

```http
GET /api/articles

GET /api/articles/:id

POST /api/articles

PUT /api/articles/:id

DELETE /api/articles/:id
```

---

Очень похоже на CRUD.

---

# Single Type

Очень популярный вопрос.

---

Single Type существует только в одном экземпляре.

---

Пример:

```txt
Homepage
```

---

Нельзя создать:

```txt
Homepage 1
Homepage 2
Homepage 3
```

---

Существует только:

```txt
Homepage
```

---

# Типичные Single Types

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
много записей
```

---

Single:

```txt
одна запись
```

---

# Component

Одна из сильнейших сторон Strapi.

---

Представим:

```txt
Address
```

---

Поля:

```txt
country
city
street
zip
```

---

Этот блок нужен:

```txt
User
Company
Office
```

---

Чтобы не копировать поля,
создаем:

```txt
Component
```

---

# Использование

```txt
User
 └─ Address Component

Company
 └─ Address Component
```

---

Очень похоже на:

```txt
Embedded Value Object
```

---

# Repeatable Component

Массив компонентов.

---

Пример:

```txt
FAQ
```

---

Один элемент:

```txt
question
answer
```

---

На странице может быть:

```txt
10 FAQ элементов
```

---

Используем:

```txt
Repeatable Component
```

---

# Dynamic Zone

Очень любят спрашивать.

---

Уникальная фича Strapi.

---

Позволяет собирать страницу
из разных блоков.

---

Пример:

```txt
Hero Section
Gallery
Testimonials
FAQ
CTA
```

---

Редактор может сам выбирать:

```txt
какие блоки будут на странице
```

---

Схема:

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

Очень удобно для маркетинговых сайтов.

---

# Relationships

Поддерживаются стандартные связи.

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

Встроенная поддержка файлов.

---

Например:

```txt
avatar
coverImage
gallery
```

---

Файлы хранятся через:

```txt
Upload Plugin
```

---

Локально.

Или:

```txt
AWS S3
Cloudinary
Azure Blob
```

---

# Draft & Publish

Очень популярная возможность.

---

Контент может быть:

```txt
Draft
```

или

```txt
Published
```

---

Пока запись не опубликована:

```txt
frontend ее не увидит
```

---

# Internationalization (i18n)

Плагин локализации.

---

Например:

```txt
English
German
French
```

---

Одна статья.

Несколько языковых версий.

---

# Что происходит под капотом

Создаем:

```txt
Article
```

---

Strapi автоматически:

1. Создает таблицу.
2. Создает связи.
3. Обновляет Admin UI.
4. Генерирует API.
5. Генерирует GraphQL типы.

---

# Частый вопрос

Что бы вы использовали для Homepage?

Ответ:

```txt
Single Type
```

---

Для Blog Posts?

Ответ:

```txt
Collection Type
```

---

# Interview Answer

Strapi использует Content Types как основную единицу моделирования данных. Collection Types предназначены для хранения множества записей, а Single Types — для уникальных сущностей, таких как Homepage или Settings. Для переиспользования структуры данных используются Components, а для построения гибких страниц — Dynamic Zones.