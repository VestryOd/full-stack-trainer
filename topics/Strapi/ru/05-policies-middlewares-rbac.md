# Policies, Middlewares и RBAC

## Самое важное понимание

В Strapi безопасность строится на нескольких уровнях.

---

Упрощенно:

```txt
Request
 ↓
Middleware
 ↓
Authentication
 ↓
Policy
 ↓
Controller
 ↓
Service
```

---

# Authentication vs Authorization

Очень популярный вопрос.

---

Authentication:

```txt
Кто ты?
```

---

Например:

```txt
JWT
Login
Access Token
```

---

Authorization:

```txt
Что тебе разрешено?
```

---

Например:

```txt
Admin
Editor
Reader
```

---

# Users & Permissions Plugin

Один из важнейших плагинов Strapi.

---

Предоставляет:

```txt
Users
Roles
Permissions
JWT Auth
Registration
Login
```

---

Фактически это готовая система авторизации.

---

# Public Role

По умолчанию есть:

```txt
Public
```

---

Это:

```txt
неавторизованный пользователь
```

---

Например:

```txt
анонимный посетитель сайта
```

---

# Authenticated Role

Вторая стандартная роль.

---

```txt
Authenticated
```

---

Пользователь выполнил:

```txt
login
```

---

И получил JWT.

---

# RBAC

Role Based Access Control.

---

Очень популярный термин.

---

Идея:

```txt
Role
 ↓
Permissions
```

---

Пример:

```txt
Admin
Editor
Viewer
```

---

# Пример

Editor:

```txt
read articles
create articles
update articles
```

---

Viewer:

```txt
read articles
```

---

# Как работает в Strapi

Для каждого endpoint можно указать:

```txt
разрешен
или
запрещен
```

---

Например:

```http
GET /api/articles
```

---

Разрешить:

```txt
Public
```

---

А:

```http
POST /api/articles
```

---

Только:

```txt
Authenticated
```

---

# JWT

По умолчанию Strapi использует:

```txt
JWT
```

---

После логина:

```http
POST /api/auth/local
```

---

Получаем:

```json
{
  "jwt": "...",
  "user": {...}
}
```

---

Дальше клиент отправляет:

```http
Authorization: Bearer token
```

---

# Middleware

Первый уровень обработки запроса.

---

Очень похоже на Koa middleware.

---

Пример:

```js
module.exports = (config, { strapi }) => {

  return async (ctx, next) => {

    console.log(ctx.request.url);

    await next();
  };
};
```

---

# Middleware может

```txt
логировать
добавлять данные
изменять request
изменять response
останавливать запрос
```

---

# Порядок Middleware

Очень важно.

---

Работают цепочкой.

---

```txt
Middleware A
 ↓
Middleware B
 ↓
Controller
```

---

После ответа:

```txt
Controller
 ↑
Middleware B
 ↑
Middleware A
```

---

Почти как Koa.

---

# Policy

Очень любят спрашивать.

---

Policy похожа на Guard в NestJS.

---

Главная задача:

```txt
разрешить
или
запретить
выполнение Route
```

---

# Пример

Только Admin.

---

```js
module.exports = async (
  policyContext,
  config,
  { strapi }
) => {

  return (
    policyContext.state.user.role
      .name === 'Admin'
  );
};
```

---

# Где применяется

Route:

```js
{
  method: 'GET',
  path: '/reports',
  handler: 'report.find',
  config: {
    policies: [
      'global::is-admin'
    ]
  }
}
```

---

# Policy vs Middleware

Очень популярный вопрос.

---

Middleware:

```txt
общая обработка запроса
```

---

Policy:

```txt
проверка доступа
```

---

# Частый вопрос

Чем Policy похожа на NestJS Guard?

---

Почти прямой аналог.

---

Nest:

```txt
Guard
```

---

Strapi:

```txt
Policy
```

---

Обе решают:

```txt
Authorization
```

---

# Полный Flow

```txt
Request
 ↓
Middleware
 ↓
JWT Validation
 ↓
Policy
 ↓
Controller
 ↓
Service
```

---

# Interview Answer

Strapi использует RBAC через Users & Permissions Plugin. Authentication обычно реализуется через JWT, а Authorization — через роли и разрешения. Middleware используются для общей обработки запросов, а Policies являются аналогом Guards в NestJS и отвечают за контроль доступа к endpoint'ам.