# Authentication vs Authorization

## One of the Most Popular Questions

Asked very directly:

```txt
What is the difference between
Authentication
and
Authorization?
```

---

# Authentication

Answers the question:

```txt
Who are you?
```

---

The user proves:

```txt
their identity
```

---

Examples:

```txt
Password

JWT

OAuth

SSO
```

---

# Authorization

Answers the question:

```txt
What are you allowed to do?
```

---

After Authentication.

---

Example

A user logged in.

---

Authentication:

```txt
this is indeed Maksym
```

---

Authorization:

```txt
can they delete a user
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

Very popular question.

---

Permissions are determined by role.

---

For example:

```txt
Admin

Manager

User
```

---

# ABAC

Attribute Based Access Control.

---

Decision depends on attributes.

---

For example:

```txt
department

country

ownership
```

---

# RBAC Example

```txt
Admin
 ↓
Delete User
```

---

# ABAC Example

```txt
Owner
 ↓
Edit Own Profile
```

---

# JWT and Authorization

After verifying the JWT:

```txt
userId

roles

permissions
```

---

Are used for authorization.

---

# Common Question

Can you do Authorization without Authentication?

Answer:

Practically no.

You need to know who the user is first.

---

# Common Question

What is RBAC?

Answer:

An access control model based on user roles.

---

# Interview Answer

Authentication verifies a user's identity, while Authorization determines their access rights. Authentication is typically performed first, and then Authorization is performed based on roles or permissions.
