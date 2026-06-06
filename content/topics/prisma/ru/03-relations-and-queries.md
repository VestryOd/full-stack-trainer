<!-- verified: 2026-06-05, corrections: 0 -->
# Prisma Relations and Queries

## Главная идея Relations

Prisma описывает связи между моделями.

Под капотом это всё равно обычные:

```txt
Foreign Keys
JOIN
Reference Constraints
```

в PostgreSQL.

---

# One-To-One

Пример:

```txt
User
 ↓
Profile
```

---

# Prisma Schema

```prisma
model User {
  id      Int      @id @default(autoincrement())
  profile Profile?
}

model Profile {
  id      Int @id @default(autoincrement())

  userId  Int @unique

  user    User @relation(
    fields: [userId],
    references: [id]
  )
}
```

---

# Почему @unique

Потому что:

```txt
один User
=
один Profile
```

---

# SQL аналог

```sql
profile.user_id UNIQUE
```

---

# One-To-Many

Самая популярная связь.

---

Пример:

```txt
User
 ↓
Posts
```

---

# Prisma Schema

```prisma
model User {
  id    Int    @id @default(autoincrement())

  posts Post[]
}

model Post {
  id     Int @id @default(autoincrement())

  userId Int

  user User @relation(
    fields: [userId],
    references: [id]
  )
}
```

---

# SQL аналог

```sql
posts.user_id REFERENCES users(id)
```

---

# Many-To-Many

Очень частый вопрос.

---

Пример:

```txt
Users
 ↕
Roles
```

---

# Implicit Many-To-Many

Prisma может создать join table автоматически.

---

```prisma
model User {
  id    Int @id @default(autoincrement())

  roles Role[]
}

model Role {
  id    Int @id @default(autoincrement())

  users User[]
}
```

---

Prisma создаст промежуточную таблицу сам.

---

# Explicit Many-To-Many

Используется чаще в production.

---

Потому что можно хранить дополнительные поля.

---

Пример:

```prisma
model UserRole {
  userId Int
  roleId Int

  assignedAt DateTime @default(now())

  user User @relation(
    fields: [userId],
    references: [id]
  )

  role Role @relation(
    fields: [roleId],
    references: [id]
  )

  @@id([userId, roleId])
}
```

---

# SELECT Queries

Получить всех пользователей.

```ts
const users = await prisma.user.findMany();
```

---

Получить одного.

```ts
const user = await prisma.user.findUnique({
  where: {
    id: 1,
  },
});
```

---

# findUnique

Используется только для:

```txt
Primary Key
Unique Fields
```

---

# findFirst

Ищет первую подходящую запись.

---

```ts
await prisma.user.findFirst({
  where: {
    isActive: true,
  },
});
```

---

# WHERE

Фильтрация.

---

```ts
await prisma.user.findMany({
  where: {
    email: 'max@test.com',
  },
});
```

---

# AND

```ts
where: {
  AND: [
    { active: true },
    { age: { gt: 18 } },
  ]
}
```

---

# OR

```ts
where: {
  OR: [
    { role: 'ADMIN' },
    { role: 'MODERATOR' },
  ]
}
```

---

# LIKE аналог

```ts
where: {
  email: {
    contains: '@gmail.com',
  },
}
```

---

# include

Очень важная тема.

---

Получить пользователя и посты.

```ts
await prisma.user.findMany({
  include: {
    posts: true,
  },
});
```

---

Под капотом Prisma выполнит JOIN.

---

# select

Позволяет вернуть только нужные поля.

---

```ts
await prisma.user.findMany({
  select: {
    id: true,
    email: true,
  },
});
```

---

Очень полезно для performance.

---

# include vs select

include:

```txt
добавляет relations
```

---

select:

```txt
ограничивает поля
```

---

# Nested Select

```ts
await prisma.user.findMany({
  select: {
    id: true,
    posts: {
      select: {
        title: true,
      },
    },
  },
});
```

---

# Create

```ts
await prisma.user.create({
  data: {
    email: 'max@test.com',
  },
});
```

---

# Update

```ts
await prisma.user.update({
  where: {
    id: 1,
  },
  data: {
    email: 'new@test.com',
  },
});
```

---

# Delete

```ts
await prisma.user.delete({
  where: {
    id: 1,
  },
});
```

---

# Nested Writes

Очень любят спрашивать.

---

Можно создать User и Post одним запросом.

---

```ts
await prisma.user.create({
  data: {
    email: 'max@test.com',

    posts: {
      create: [
        {
          title: 'First Post',
        },
      ],
    },
  },
});
```

---

# connect

Связать существующую запись.

---

```ts
await prisma.post.create({
  data: {
    title: 'Post',

    user: {
      connect: {
        id: 1,
      },
    },
  },
});
```

---

# connectOrCreate

Очень популярно.

---

Если записи нет:

```txt
создать
```

Если есть:

```txt
подключить
```

---

```ts
connectOrCreate: {
  where: {
    email: 'max@test.com',
  },
  create: {
    email: 'max@test.com',
  },
}
```

---

# Pagination

offset pagination

```ts
skip: 20
take: 10
```

---

cursor pagination

```ts
cursor: {
  id: 100
}
```

---

Cursor pagination предпочтительнее для больших таблиц.

---

# Частый вопрос

Что лучше:

```ts
include
```

или

несколько запросов?

---

Ответ:

Зависит от объема данных.

Большой include может привести
к очень тяжелым JOIN запросам.

---

# Interview Answer

Relations в Prisma являются абстракцией над Foreign Keys. Prisma поддерживает One-To-One, One-To-Many и Many-To-Many отношения и предоставляет удобный API через include, select, nested writes, connect и connectOrCreate.
