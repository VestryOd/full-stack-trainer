# SQL Injection and Input Validation

## One of the Oldest Attacks

But still encountered today.

---

# What is SQL Injection

An attack
in which the user
influences the SQL query.

---

# Bad Example

```ts
const query =

`SELECT *
 FROM users
 WHERE email='${email}'`;
```

---

The user enters:

```txt
' OR 1=1 --
```

---

We get:

```sql
SELECT *
FROM users
WHERE email=''
OR 1=1
```

---

Result:

```txt
all users
```

---

# More Dangerous Example

```txt
DROP TABLE users
```

---

# Why This Works

Because user input
is mixed with SQL.

---

# Parameterized Query

The main defense.

---

Correct:

```ts
db.query(
 "SELECT * FROM users WHERE email=$1",
 [email]
);
```

---

Now:

```txt
SQL

and

data
```

---

Are separated.

---

# ORM

Very popular question.

---

Prisma:

```ts
prisma.user.findMany(...)
```

---

By default:

```txt
safe
```

---

# But

Dangerous:

```ts
$queryRawUnsafe(...)
```

---

# Validation

The next important topic.

---

Never trust:

```txt
Frontend
```

---

Never.

---

# Why

Anyone can send a request via:

```http
curl

Postman

Swagger
```

---

# Validation Must Be on the Backend

Always.

---

# DTO Validation

NestJS example.

---

```ts
@IsEmail()
email: string;
```

---

# ValidationPipe

```ts
whitelist: true
```

---

Removes extra fields.

---

# Very Important Example

A user sends:

```json
{
 "email":"...",
 "role":"admin"
}
```

---

If the role field is not in the DTO:

```txt
it will be removed
```

---

# Sanitization

Very frequently asked.

---

Validation:

```txt
is the data correct?
```

---

Sanitization:

```txt
is the data safe?
```

---

# Example

Input:

```html
<script>alert()</script>
```

---

After sanitization:

```txt
remove dangerous HTML
```

---

# File Upload Validation

Very popular question.

---

Never trust:

```txt
filename

extension
```

---

Always check:

```txt
mime type

file size

content type
```

---

# Mass Assignment

Very frequently asked.

---

The problem.

---

There is a model:

```ts
User
```

---

A user sends:

```json
{
 "name":"Max",
 "role":"admin"
}
```

---

If blindly saved:

```ts
db.create(req.body)
```

---

We get:

```txt
privilege escalation
```

---

# Solution

Use:

```txt
DTO

Whitelist

Field Mapping
```

---

# Common Question

Does an ORM protect against SQL Injection?

Answer:

In most cases yes.

---

But raw queries can still be vulnerable.

---

# Common Question

Why can't you trust Frontend Validation?

Answer:

Because the client can be bypassed and any request can be sent directly.

---

# Common Question

What is Mass Assignment?

Answer:

A vulnerability where a user can pass fields they should not be allowed to modify.

---

# Common Question

What is more important: Validation or Sanitization?

Answer:

Both.

Validation checks data correctness, while Sanitization makes data safe.

---

# Interview Answer

SQL Injection occurs when user input is mixed with SQL code. The main defense is parameterized queries and ORMs. Additionally, the server must always perform validation and sanitization of incoming data regardless of frontend checks.
