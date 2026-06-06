# Headless CMS and Strapi

## What is a CMS

CMS (Content Management System) —
a system for managing content.

---

Classic examples:

```txt
WordPress
Drupal
Joomla
```

---

A CMS typically contains:

```txt
Database
Admin Panel
Templates
Frontend
```

---

Diagram:

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

# The Problem with Classic CMSs

The frontend is tightly coupled to the backend.

---

For example:

```txt
WordPress
 ↓
PHP Templates
 ↓
HTML
```

---

Hard to use with:

```txt
React
Next.js
Mobile Apps
IoT
```

---

# What is a Headless CMS

Headless CMS removes the frontend.

---

Only the following remains:

```txt
Content Management
+
API
```

---

Diagram:

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

# Why It's Called Headless

Because the following is absent:

```txt
Head
=
Presentation Layer
```

---

Only this remains:

```txt
Body
=
Content Backend
```

---

# Example

Content:

```txt
Article
```

---

An editor changes an article via the admin panel.

---

Strapi saves it to:

```txt
Database
```

---

The frontend fetches it via:

```http
GET /api/articles
```

---

# What is Strapi

Strapi is an open-source headless CMS
written in Node.js.

---

Under the hood:

```txt
Node.js
Koa
Database Layer
Admin Panel
REST API
GraphQL API
```

---

# The Main Idea of Strapi

A developer describes models.

---

For example:

```txt
Article
Category
Author
```

---

Strapi automatically creates:

```txt
Database Schema
Admin UI
REST API
GraphQL API
Permissions
```

---

# Why Strapi is Popular

Very fast to get started.

---

Without writing code you get:

```txt
CRUD
Admin Panel
RBAC
Media Upload
API
```

---

# When Strapi is a Good Fit

- marketing websites
- corporate websites
- blogs
- catalogs
- e-commerce CMS
- mobile backend

---

# When Strapi May Not Be a Good Fit

Very complex business logic.

---

For example:

```txt
Banking
Trading
ERP
High-load systems
```

---

In those cases, the following are more common:

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

# Interview Answer

A Headless CMS is a CMS that is only responsible for storing and managing content and provides an API to retrieve it. Unlike classic CMSs, the frontend is completely separated from the backend. Strapi is a popular headless CMS built on Node.js that automatically generates an API and an admin panel based on data models.
