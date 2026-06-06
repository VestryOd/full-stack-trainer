# Strapi Interview Questions

---

# 1. What is Strapi?

Strapi is an open-source headless CMS built on Node.js.

It lets you describe data models and automatically generates:

- Admin Panel
- REST API
- GraphQL API
- Permissions
- Database Schema

---

# 2. What is a Headless CMS?

A CMS without a built-in frontend.

---

Classic CMS:

```txt
Backend
+
Frontend
```

---

Headless CMS:

```txt
Backend
+
API
```

---

The frontend is developed separately.

---

# 3. Why is Strapi called a Headless CMS?

Because it is only responsible for:

```txt
content management
data storage
API
```

---

The frontend is absent.

---

# 4. How does Strapi differ from WordPress?

WordPress:

```txt
CMS + Templates + Frontend
```

---

Strapi:

```txt
CMS + API
```

---

# 5. What is Strapi built on?

Under the hood:

```txt
Node.js
Koa
REST API
GraphQL
Database Layer
```

---

# 6. Why does Strapi use Koa?

Koa provides:

```txt
Middleware Pipeline
Context Object
Asynchronous Architecture
```

---

Strapi builds its platform on top of Koa.

---

# 7. What is ctx in Strapi?

Koa Context.

---

Contains:

```txt
request
response
state
params
query
```

---

Analogous to:

```txt
req/res in Express
```

---

# 8. What is a Content Type?

The core entity in Strapi.

---

Similar to:

```txt
Database Table
ORM Model
Entity
```

---

# 9. What is a Collection Type?

An entity with many records.

---

Examples:

```txt
Articles
Products
Users
Categories
```

---

# 10. What is a Single Type?

An entity that exists in only one instance.

---

Examples:

```txt
Homepage
Footer
Header
Settings
```

---

# 11. When should you use a Collection Type?

When you need to store many records.

---

For example:

```txt
Blog Posts
Products
News
```

---

# 12. When should you use a Single Type?

When a record should exist only once.

---

For example:

```txt
Homepage
Site Settings
```

---

# 13. What is a Component?

A reusable data structure.

---

Example:

```txt
Address
```

---

Used in:

```txt
User
Company
Office
```

---

# 14. What is a Repeatable Component?

An array of components.

---

For example:

```txt
FAQ Items
```

---

# 15. What is a Dynamic Zone?

A set of blocks
that an editor can combine freely.

---

Example:

```txt
Hero
Gallery
FAQ
CTA
```

---

Very popular for landing pages.

---

# 16. What happens after a Content Type is created?

Strapi automatically creates:

- database tables
- REST API
- GraphQL API
- forms in the Admin Panel
- permissions

---

# 17. Which databases does Strapi support?

Main ones:

```txt
PostgreSQL
MySQL
SQLite
```

---

# 18. Does Strapi need its own database?

Yes.

---

Strapi always stores data in its own database.

---

# 19. Is Strapi a separate service?

Effectively yes.

---

The architecture often looks like this:

```txt
Next.js
 ↓
Strapi
 ↓
PostgreSQL
```

---

# 20. What does the request lifecycle look like?

```txt
Request
 ↓
Middleware
 ↓
Route
 ↓
Policy
 ↓
Controller
 ↓
Service
 ↓
Document Service
 ↓
Query Engine
 ↓
Database
```

---

# 21. What is a Controller?

Handles the request.

---

Responsible for:

```txt
request
response
```

---

# 22. Where should business logic be placed?

In:

```txt
Services
```

---

Not in the Controller.

---

# 23. What is a Service?

The business logic layer.

---

For example:

```txt
validation
aggregation
external APIs
```

---

# 24. What is the Document Service?

A high-level data access API in Strapi v5.

---

Example:

```js
strapi.documents(...)
```

---

# 25. What is the Query Engine?

A low-level data access layer.

---

Works beneath the Document Service.

---

# 26. How does the Document Service differ from the Query Engine?

Document Service:

```txt
high-level API
```

---

Query Engine:

```txt
low-level API
```

---

# 27. What is Middleware?

General request processing.

---

For example:

```txt
logging
CORS
request modification
```

---

# 28. What is a Policy?

An authorization mechanism.

---

It checks:

```txt
whether a route can be executed
or not
```

---

# 29. How is a Policy similar to a NestJS Guard?

Practically a direct analogy.

---

Both solve the task of:

```txt
Authorization
```

---

# 30. What is RBAC?

Role Based Access Control.

---

Access management through roles.

---

# 31. What roles exist by default?

```txt
Public
Authenticated
```

---

# 32. What does the Users & Permissions Plugin do?

Provides:

- JWT Auth
- Roles
- Permissions
- Registration
- Login

---

# 33. How does JWT work in Strapi?

After login:

```txt
JWT Token
```

---

The client sends:

```http
Authorization: Bearer TOKEN
```

---

# 34. What is a Lifecycle Hook?

A mechanism for executing code before or after data operations.

---

# 35. What Lifecycle Hooks exist?

Before an operation:

```txt
beforeCreate
beforeUpdate
beforeDelete
```

---

After an operation:

```txt
afterCreate
afterUpdate
afterDelete
```

---

# 36. When should you use a Lifecycle Hook?

For:

```txt
slug generation
audit logs
notifications
```

---

# 37. Where should you NOT write business logic?

In Lifecycle Hooks.

---

Better to use:

```txt
Service Layer
```

---

# 38. Can you create custom routes?

Yes.

---

For example:

```http
GET /api/articles/popular
```

---

# 39. Can you create custom controllers?

Yes.

---

This is standard practice.

---

# 40. Can you create custom services?

Yes.

---

That is usually where business logic lives.

---

# 41. What is the Upload Plugin?

A file management plugin.

---

Supports:

```txt
Local Storage
AWS S3
Cloudinary
Azure Blob
```

---

# 42. What is Draft & Publish?

A content publishing mechanism.

---

A record can be:

```txt
Draft
Published
```

---

# 43. What is the i18n Plugin?

A content localization plugin.

---

Allows storing:

```txt
English
German
French
```

versions of a single record.

---

# 44. Can GraphQL be used with Strapi?

Yes.

---

Through the GraphQL Plugin.

---

Strapi automatically generates a GraphQL Schema.

---

# 45. Can REST and GraphQL be used at the same time?

Yes.

---

This is a very common production scenario.

---

# 46. How would you implement an endpoint accessible only by Admins?

I would create a Policy:

```txt
role check
```

and attach it to the Route.

---

# 47. How is Strapi similar to NestJS?

NestJS:

```txt
Controller
Service
Repository
```

---

Strapi:

```txt
Controller
Service
Document Service
```

---

Architecturally very similar.

---

# 48. When is Strapi a good choice?

- CMS projects
- Landing Pages
- Blogs
- Marketing Sites
- Mobile Backends
- Content-heavy projects

---

# 49. When is Strapi a bad choice?

Complex domain logic.

---

For example:

```txt
Trading
Banking
ERP
High-load microservices
```

---

# 50. The Most Popular Senior Question

Why can Strapi be considered not just a CMS but a full-featured backend framework?

Answer:

Because Strapi provides a complete backend architecture with middleware, policies, controllers, services, RBAC, lifecycle hooks, plugins and database access. Beyond content management, it allows you to implement custom business logic and custom APIs in much the same way as a classic backend framework.
