# Prisma Relations and Queries

## Типы связей

Prisma поддерживает три типа связей — все они транслируются в стандартные Foreign Keys и JOIN в PostgreSQL. Разница только в том, на какой стороне живёт FK.

```prisma
// One-to-One: User имеет ровно один Profile
// FK на стороне "дочерней" модели (Profile.userId)
model User {
  id      Int      @id @default(autoincrement())
  profile Profile?  // nullable — Profile может не существовать
}

model Profile {
  id     Int    @id @default(autoincrement())
  bio    String?
  userId Int    @unique  // @unique обеспечивает one-to-one (не one-to-many)
  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
}

// One-to-Many: User имеет много Posts
model User {
  id    Int    @id @default(autoincrement())
  posts Post[]  // виртуальное поле — нет колонки в БД
}

model Post {
  id       Int  @id @default(autoincrement())
  authorId Int
  author   User @relation(fields: [authorId], references: [id])
}

// Many-to-Many explicit (production рекомендация)
// — когда нужны дополнительные поля на join table
model UserRole {
  userId     Int
  roleId     Int
  assignedAt DateTime @default(now())
  assignedBy String?

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
  role Role @relation(fields: [roleId], references: [id], onDelete: Cascade)

  @@id([userId, roleId])
  @@index([roleId])
}

// Many-to-Many implicit (когда доп. полей не нужно — Prisma создаёт join table сама)
model Post {
  id   Int   @id @default(autoincrement())
  tags Tag[]
}
model Tag {
  id    Int    @id @default(autoincrement())
  posts Post[]
}
// → Prisma создаёт таблицу "_PostToTag" автоматически
```

## onDelete / onUpdate — Referential Actions

```prisma
model Post {
  authorId Int
  author   User @relation(fields: [authorId], references: [id],
    onDelete: Cascade,  // при удалении User → удалить все его Posts
    onUpdate: Cascade   // при изменении User.id → обновить Post.authorId
  )
}

// Варианты:
// Cascade  — каскадное удаление/обновление (самый популярный)
// Restrict — запретить удаление если есть связанные записи (защита данных)
// SetNull  — установить FK = NULL (поле должно быть nullable: authorId Int?)
// NoAction — нет действия на уровне Prisma (проверка на уровне БД)
// SetDefault — установить default значение FK
```

## Запросы — find*, create, update, delete

```typescript
// findUnique — только для @id или @unique полей, возвращает T | null
const user = await prisma.user.findUnique({ where: { id: 1 } });

// findFirst — первая запись по условию, возвращает T | null
const active = await prisma.user.findFirst({
  where: { isActive: true },
  orderBy: { createdAt: 'desc' },
});

// findMany — все записи по условию
const users = await prisma.user.findMany({
  where: {
    AND: [
      { isActive: true },
      { createdAt: { gte: new Date('2024-01-01') } },
    ],
    OR: [
      { role: 'ADMIN' },
      { role: 'EDITOR' },
    ],
    email: { contains: '@company.com', mode: 'insensitive' }, // case-insensitive LIKE
    name: { not: null },
  },
  orderBy: [{ createdAt: 'desc' }, { name: 'asc' }],
  take: 20,    // LIMIT
  skip: 40,    // OFFSET — offset pagination
});

// count + aggregate
const total = await prisma.user.count({ where: { isActive: true } });
const stats = await prisma.order.aggregate({
  _sum: { amount: true },
  _avg: { amount: true },
  _count: true,
  where: { status: 'COMPLETED' },
});

// upsert — create if not exists, else update
const user = await prisma.user.upsert({
  where: { email: 'alice@example.com' },
  create: { email: 'alice@example.com', name: 'Alice' },
  update: { name: 'Alice Updated' },
});

// createMany / updateMany / deleteMany — bulk операции
await prisma.post.createMany({
  data: [{ title: 'A', authorId: 1 }, { title: 'B', authorId: 1 }],
  skipDuplicates: true, // игнорировать конфликты unique
});

await prisma.post.deleteMany({ where: { authorId: 1 } });
```

## include vs select — загрузка связей

```typescript
// include: загрузить связанные записи (JOIN под капотом)
const userWithPosts = await prisma.user.findUnique({
  where: { id: 1 },
  include: {
    posts: {
      where: { published: true },
      orderBy: { createdAt: 'desc' },
      take: 5,
      include: { tags: true }, // вложенный include
    },
    profile: true,
  },
});

// select: выбрать только нужные поля (projection)
const userNames = await prisma.user.findMany({
  select: {
    id: true,
    email: true,
    posts: {          // select + relation — работает
      select: { title: true, createdAt: true },
      where: { published: true },
    },
  },
});
// Результат строго типизирован: { id: number; email: string; posts: { title: string; ... }[] }

// include vs select нельзя использовать одновременно на одном уровне
// ✗ { include: { posts: true }, select: { id: true } } — ошибка TS
// ✓ select: { id: true, posts: { select: { title: true } } } — корректно
```

## Nested Writes — связанные записи за один запрос

```typescript
// create с вложенным create (User + Posts за один запрос = одна транзакция)
const user = await prisma.user.create({
  data: {
    email: 'alice@example.com',
    profile: {
      create: { bio: 'Senior Engineer' },  // создать Profile
    },
    posts: {
      create: [
        { title: 'First post' },
        { title: 'Second post' },
      ],
    },
  },
  include: { profile: true, posts: true }, // вернуть с relations
});

// connect — связать существующую запись
await prisma.post.update({
  where: { id: 1 },
  data: {
    tags: {
      connect: [{ id: 1 }, { id: 2 }],     // добавить теги
      disconnect: [{ id: 3 }],              // убрать тег
      set: [{ id: 1 }],                     // установить ровно эти теги (disconnect old)
    },
  },
});

// connectOrCreate — найти или создать
await prisma.post.create({
  data: {
    title: 'Post',
    author: {
      connectOrCreate: {
        where: { email: 'alice@example.com' },
        create: { email: 'alice@example.com', name: 'Alice' },
      },
    },
  },
});
```

## Пагинация — offset vs cursor

```typescript
// Offset pagination — простая, но медленная на больших таблицах
const page2 = await prisma.post.findMany({
  skip: 20,   // OFFSET 20
  take: 10,   // LIMIT 10
  orderBy: { createdAt: 'desc' },
});
// Проблема: OFFSET 1000000 — PostgreSQL всё равно читает 1000010 строк

// Cursor pagination — для больших таблиц и бесконечного скролла
const nextPage = await prisma.post.findMany({
  cursor: { id: lastSeenId },   // начать после этого id
  take: 10,
  skip: 1,                       // пропустить сам курсор
  orderBy: { id: 'asc' },
});
// Под капотом: WHERE id > lastSeenId LIMIT 10 → O(log N) через индекс
```

## N+1 проблема и её решение

```typescript
// N+1: для каждого user выполняется отдельный запрос к posts
const users = await prisma.user.findMany();
for (const user of users) {
  const posts = await prisma.post.findMany({ where: { authorId: user.id } });
  // 1 запрос для findMany + N запросов для posts = N+1
}

// Решение: include — один запрос с JOIN
const usersWithPosts = await prisma.user.findMany({
  include: { posts: true },
  // Prisma выполнит: SELECT users.*, posts.* FROM users LEFT JOIN posts ON ...
});

// Для сложных случаев: prisma.$queryRaw с явным JOIN
const result = await prisma.$queryRaw<UserWithCount[]>`
  SELECT u.id, u.email, COUNT(p.id)::int as post_count
  FROM users u
  LEFT JOIN posts p ON p.author_id = u.id
  GROUP BY u.id
`;
```

## Типичные ошибки на интервью

- **"include всегда делает JOIN"** — не совсем. Prisma 5+ использует `JOIN` для include в большинстве случаев, но для некоторых паттернов может делать отдельный `SELECT ... WHERE id IN (...)`. Включить `log: ['query']` чтобы видеть реальный SQL.

- **"select и include нельзя использовать вместе"** — нельзя на одном уровне (`{ select, include }` — ошибка), но можно: `select: { id: true, posts: { select: { title: true } } }` — select с вложенным select для relation.

- **"Implicit Many-to-Many лучше для production"** — нет. Explicit Many-to-Many (явная join table) рекомендуется для production: можно добавить поля (`assignedAt`, `role`), можно напрямую запрашивать join table (`prisma.userRole.findMany()`), проще управлять каскадным удалением.

- **"findUnique быстрее findFirst"** — да, потому что `findUnique` транслируется в `WHERE id = ?` по индексированному полю. `findFirst` с тем же условием эквивалентен, но может не быть оптимизирован компилятором Prisma. Используй `findUnique` когда ищешь по `@id` или `@unique` полям.

- **"Cursor pagination всегда лучше offset"** — cursor лучше для больших таблиц и бесконечного скролла. Но cursor-based pagination не поддерживает произвольный переход на страницу (нельзя перейти на страницу 50 без прохождения страниц 1-49). Для UI с нумерованными страницами: offset. Для бесконечного скролла/API: cursor.
