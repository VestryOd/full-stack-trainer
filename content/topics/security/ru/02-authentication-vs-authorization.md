# Authentication vs Authorization

## Один из самых популярных вопросов

Очень часто задают прямо так:

```txt
Чем отличается
Authentication
от
Authorization?
```

---

# Authentication

Отвечает на вопрос:

```txt
Кто ты?
```

---

Пользователь доказывает:

```txt
свою личность
```

---

Примеры:

```txt
Password

JWT

OAuth

SSO
```

---

# Authorization

Отвечает на вопрос:

```txt
Что тебе можно?
```

---

После Authentication.

---

Пример

Пользователь вошел.

---

Authentication:

```txt
это действительно Максим
```

---

Authorization:

```txt
может ли он удалить пользователя
```

---

# Flow

```txt
Login
 ↓
Authentication
 ↓
JWT
 ↓
Authorization
 ↓
Protected Resource
```

---

# RBAC

Role Based Access Control.

---

Очень популярный вопрос.

---

Права определяются ролью.

---

Например:

```txt
Admin

Manager

User
```

---

# ABAC

Attribute Based Access Control.

---

Решение зависит от атрибутов.

---

Например:

```txt
department

country

ownership
```

---

# Пример RBAC

```txt
Admin
 ↓
Delete User
```

---

# Пример ABAC

```txt
Owner
 ↓
Edit Own Profile
```

---

# JWT и Authorization

После проверки JWT:

```txt
userId

roles

permissions
```

---

Используются для авторизации.

---

# Частый вопрос

Можно ли делать Authorization без Authentication?

Ответ:

Практически нет.

Сначала нужно понять кто пользователь.

---

# Частый вопрос

Что такое RBAC?

Ответ:

Модель контроля доступа, основанная на ролях пользователей.

---

# Interview Answer

Authentication подтверждает личность пользователя, а Authorization определяет его права доступа. Обычно сначала выполняется Authentication, а затем на основе ролей или разрешений выполняется Authorization.