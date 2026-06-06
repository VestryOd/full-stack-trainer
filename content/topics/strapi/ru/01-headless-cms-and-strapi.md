<!-- verified: 2026-06-05, corrections: 0 -->
# Headless CMS и Strapi

## Что такое CMS

CMS (Content Management System) —
система управления контентом.

---

Классический пример:

```txt
WordPress
Drupal
Joomla
```

---

Обычно CMS содержит:

```txt
Database
Admin Panel
Templates
Frontend
```

---

Схема:

```txt
Editor
 ↓
CMS
 ↓
HTML
 ↓
Browser
```

---

# Проблема классических CMS

Frontend жестко связан с backend.

---

Например:

```txt
WordPress
 ↓
PHP Templates
 ↓
HTML
```

---

Сложно использовать:

```txt
React
Next.js
Mobile Apps
IoT
```

---

# Что такое Headless CMS

Headless CMS убирает frontend.

---

Остается только:

```txt
Content Management
+
API
```

---

Схема:

```txt
Editor
 ↓
Strapi
 ↓
API
 ↓
React
Mobile
Next.js
TV App
```

---

# Почему называется Headless

Потому что отсутствует:

```txt
Head
=
Presentation Layer
```

---

Есть только:

```txt
Body
=
Content Backend
```

---

# Пример

Контент:

```txt
Article
```

---

Редактор меняет статью через админку.

---

Strapi сохраняет:

```txt
Database
```

---

Frontend получает:

```http
GET /api/articles
```

---

# Что такое Strapi

Strapi — open-source headless CMS,
написанная на Node.js.

---

Под капотом:

```txt
Node.js
Koa
Database Layer
Admin Panel
REST API
GraphQL API
```

---

# Главная идея Strapi

Разработчик описывает модели.

---

Например:

```txt
Article
Category
Author
```

---

Strapi автоматически создает:

```txt
Database Schema
Admin UI
REST API
GraphQL API
Permissions
```

---

# Почему Strapi популярен

Очень быстрый старт.

---

Без написания кода можно получить:

```txt
CRUD
Admin Panel
RBAC
Media Upload
API
```

---

# Когда Strapi подходит

- маркетинговые сайты
- корпоративные сайты
- блоги
- каталоги
- e-commerce CMS
- mobile backend

---

# Когда Strapi может не подойти

Очень сложная бизнес-логика.

---

Например:

```txt
Banking
Trading
ERP
High-load systems
```

---

Тогда чаще используют:

```txt
NestJS
Spring
ASP.NET
```

---

# Headless CMS vs Traditional CMS

Traditional CMS:

```txt
Backend + Frontend
```

---

Headless CMS:

```txt
Backend only
```

---

# Интервью ответ

Headless CMS — это CMS, которая отвечает только за хранение и управление контентом и предоставляет API для его получения. В отличие от классических CMS, frontend полностью отделен от backend. Strapi является популярной headless CMS на Node.js, которая автоматически генерирует API и административную панель на основе моделей данных.