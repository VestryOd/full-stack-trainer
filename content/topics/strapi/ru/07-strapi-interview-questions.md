<!-- verified: 2026-06-05, corrections: 0 -->
# Strapi Interview Questions

---

# 1. Что такое Strapi?

Strapi — это open-source headless CMS на Node.js.

Позволяет описывать модели данных и автоматически генерирует:

- Admin Panel
- REST API
- GraphQL API
- Permissions
- Database Schema

---

# 2. Что такое Headless CMS?

CMS без встроенного frontend.

---

Классическая CMS:

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

Frontend разрабатывается отдельно.

---

# 3. Почему Strapi называют Headless CMS?

Потому что он отвечает только за:

```txt
управление контентом
хранение данных
API
```

---

Frontend отсутствует.

---

# 4. Чем Strapi отличается от WordPress?

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

# 5. На чем построен Strapi?

Под капотом:

```txt
Node.js
Koa
REST API
GraphQL
Database Layer
```

---

# 6. Почему Strapi использует Koa?

Koa предоставляет:

```txt
Middleware Pipeline
Context Object
Асинхронную архитектуру
```

---

Strapi строит свою платформу поверх Koa.

---

# 7. Что такое ctx в Strapi?

Koa Context.

---

Содержит:

```txt
request
response
state
params
query
```

---

Аналог:

```txt
req/res в Express
```

---

# 8. Что такое Content Type?

Основная сущность Strapi.

---

Похоже на:

```txt
Database Table
ORM Model
Entity
```

---

# 9. Что такое Collection Type?

Сущность с множеством записей.

---

Примеры:

```txt
Articles
Products
Users
Categories
```

---

# 10. Что такое Single Type?

Сущность, существующая в единственном экземпляре.

---

Примеры:

```txt
Homepage
Footer
Header
Settings
```

---

# 11. Когда использовать Collection Type?

Когда требуется хранить множество записей.

---

Например:

```txt
Blog Posts
Products
News
```

---

# 12. Когда использовать Single Type?

Когда запись должна существовать только одна.

---

Например:

```txt
Homepage
Site Settings
```

---

# 13. Что такое Component?

Переиспользуемая структура данных.

---

Пример:

```txt
Address
```

---

Используется в:

```txt
User
Company
Office
```

---

# 14. Что такое Repeatable Component?

Массив компонентов.

---

Например:

```txt
FAQ Items
```

---

# 15. Что такое Dynamic Zone?

Набор блоков,
которые редактор может комбинировать самостоятельно.

---

Пример:

```txt
Hero
Gallery
FAQ
CTA
```

---

Очень популярно для landing pages.

---

# 16. Что происходит после создания Content Type?

Strapi автоматически создает:

- таблицы БД
- REST API
- GraphQL API
- формы в Admin Panel
- permissions

---

# 17. Какие базы данных поддерживает Strapi?

Основные:

```txt
PostgreSQL
MySQL
SQLite
```

---

# 18. Нужна ли Strapi собственная база данных?

Да.

---

Strapi всегда хранит данные в собственной БД.

---

# 19. Является ли Strapi отдельным сервисом?

Фактически да.

---

Часто архитектура выглядит так:

```txt
Next.js
 ↓
Strapi
 ↓
PostgreSQL
```

---

# 20. Как выглядит жизненный цикл запроса?

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

# 21. Что такое Controller?

Обрабатывает запрос.

---

Отвечает за:

```txt
request
response
```

---

# 22. Где должна находиться бизнес-логика?

В:

```txt
Services
```

---

Не в Controller.

---

# 23. Что такое Service?

Слой бизнес-логики.

---

Например:

```txt
валидация
агрегация
внешние API
```

---

# 24. Что такое Document Service?

Высокоуровневый API доступа к данным в Strapi v5.

---

Пример:

```js
strapi.documents(...)
```

---

# 25. Что такое Query Engine?

Низкоуровневый слой доступа к данным.

---

Работает под Document Service.

---

# 26. Чем Document Service отличается от Query Engine?

Document Service:

```txt
высокоуровневый API
```

---

Query Engine:

```txt
низкоуровневый API
```

---

# 27. Что такое Middleware?

Общая обработка запросов.

---

Например:

```txt
логирование
CORS
модификация request
```

---

# 28. Что такое Policy?

Механизм авторизации.

---

Проверяет:

```txt
можно выполнять route
или нельзя
```

---

# 29. Чем Policy похожа на NestJS Guard?

Практически прямой аналог.

---

Обе решают задачу:

```txt
Authorization
```

---

# 30. Что такое RBAC?

Role Based Access Control.

---

Управление доступом через роли.

---

# 31. Какие роли существуют по умолчанию?

```txt
Public
Authenticated
```

---

# 32. Что делает Users & Permissions Plugin?

Предоставляет:

- JWT Auth
- Roles
- Permissions
- Registration
- Login

---

# 33. Как работает JWT в Strapi?

После логина:

```txt
JWT Token
```

---

Клиент передает:

```http
Authorization: Bearer TOKEN
```

---

# 34. Что такое Lifecycle Hook?

Механизм выполнения кода до или после операций с данными.

---

# 35. Какие Lifecycle Hooks существуют?

До операции:

```txt
beforeCreate
beforeUpdate
beforeDelete
```

---

После операции:

```txt
afterCreate
afterUpdate
afterDelete
```

---

# 36. Когда использовать Lifecycle Hook?

Для:

```txt
slug generation
audit logs
notifications
```

---

# 37. Где НЕ стоит писать бизнес-логику?

В Lifecycle Hooks.

---

Лучше использовать:

```txt
Service Layer
```

---

# 38. Можно ли создавать собственные маршруты?

Да.

---

Например:

```http
GET /api/articles/popular
```

---

# 39. Можно ли создавать собственные контроллеры?

Да.

---

Это стандартная практика.

---

# 40. Можно ли создавать собственные сервисы?

Да.

---

Обычно именно там хранится бизнес-логика.

---

# 41. Что такое Upload Plugin?

Плагин работы с файлами.

---

Поддерживает:

```txt
Local Storage
AWS S3
Cloudinary
Azure Blob
```

---

# 42. Что такое Draft & Publish?

Механизм публикации контента.

---

Запись может быть:

```txt
Draft
Published
```

---

# 43. Что такое i18n Plugin?

Плагин локализации контента.

---

Позволяет хранить:

```txt
English
German
French
```

версии одной записи.

---

# 44. Можно ли использовать GraphQL со Strapi?

Да.

---

Через GraphQL Plugin.

---

Strapi автоматически генерирует GraphQL Schema.

---

# 45. Можно ли использовать REST и GraphQL одновременно?

Да.

---

Это очень частый production сценарий.

---

# 46. Как бы вы реализовали endpoint доступный только Admin?

Создал бы Policy:

```txt
проверка роли
```

и подключил её к Route.

---

# 47. Чем Strapi похож на NestJS?

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

Архитектурно очень похожи.

---

# 48. Когда Strapi хороший выбор?

- CMS проекты
- Landing Pages
- Blogs
- Marketing Sites
- Mobile Backends
- Content-heavy проекты

---

# 49. Когда Strapi плохой выбор?

Сложная доменная логика.

---

Например:

```txt
Trading
Banking
ERP
High-load microservices
```

---

# 50. Самый популярный Senior вопрос

Почему Strapi можно считать не просто CMS, а полноценным backend framework?

Ответ:

Потому что Strapi предоставляет полноценную backend архитектуру с middleware, policies, controllers, services, RBAC, lifecycle hooks, plugins и доступом к базе данных. Помимо управления контентом он позволяет реализовывать собственную бизнес-логику и кастомные API практически так же, как классический backend framework.