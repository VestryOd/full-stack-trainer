# Связи и запросы в Prisma

## Типы связей

Prisma поддерживает три типа связей: один-к-одному, один-ко-многим и многие-ко-многим. Все три она превращает в обычный SQL — язык, на котором она разговаривает с PostgreSQL. Связь в базе — это внешний ключ FK (foreign key) в дочерней таблице, а чтение вместе со связями — это `JOIN`.

Разница только в том, на какой стороне живёт этот ключ. Модель, в которой стоит `@relation(fields: [...])`, и есть носитель колонки с ключом.

```prisma
// Один-к-одному: у User ровно один Profile
// Внешний ключ — на стороне дочерней модели (Profile.userId)
model User {
  id      Int      @id @default(autoincrement())
  profile Profile?  // может быть пустым — Profile необязателен
}

model Profile {
  id     Int    @id @default(autoincrement())
  bio    String?
  userId Int    @unique  // именно @unique даёт один-к-одному
  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
}

// Один-ко-многим: у User много Post
model User {
  id    Int    @id @default(autoincrement())
  posts Post[]  // виртуальное поле — колонки в базе нет
}

model Post {
  id       Int  @id @default(autoincrement())
  authorId Int
  author   User @relation(fields: [authorId], references: [id])
}

// Многие-ко-многим, явная связка (рекомендация для production)
// — когда в таблице-связке нужны дополнительные поля
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

// Многие-ко-многим, неявная связка: доп. полей нет,
// и таблицу-связку Prisma создаёт сама
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

## onDelete / onUpdate — что делать со связанными строками

`onDelete` и `onUpdate` задают ссылочные действия (referential actions): что произойдёт с дочерними строками, когда родительскую строку удаляют или меняют ей `id`.

```prisma
model Post {
  authorId Int
  author   User @relation(fields: [authorId], references: [id],
    onDelete: Cascade,  // удалили User → удалятся все его Post
    onUpdate: Cascade   // сменился User.id → обновится Post.authorId
  )
}

// Варианты:
// Cascade  — каскадное удаление и обновление (самый частый)
// Restrict — запретить удаление, пока есть связанные строки
// SetNull  — записать в ключ NULL (поле должно быть authorId Int?)
// NoAction — Prisma ничего не делает, проверяет сама база
// SetDefault — записать в ключ значение по умолчанию
```

## Запросы — find*, create, update, delete

```typescript
// findUnique — только по полям @id или @unique, возвращает T | null
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
    email: { contains: '@company.com', mode: 'insensitive' }, // LIKE без регистра
    name: { not: null },
  },
  orderBy: [{ createdAt: 'desc' }, { name: 'asc' }],
  take: 20,    // LIMIT
  skip: 40,    // OFFSET — пагинация по смещению
});

// count + aggregate
const total = await prisma.user.count({ where: { isActive: true } });
const stats = await prisma.order.aggregate({
  _sum: { amount: true },
  _avg: { amount: true },
  _count: true,
  where: { status: 'COMPLETED' },
});

// upsert — создать, если нет; иначе обновить
const user = await prisma.user.upsert({
  where: { email: 'alice@example.com' },
  create: { email: 'alice@example.com', name: 'Alice' },
  update: { name: 'Alice Updated' },
});

// createMany / updateMany / deleteMany — массовые операции
await prisma.post.createMany({
  data: [{ title: 'A', authorId: 1 }, { title: 'B', authorId: 1 }],
  skipDuplicates: true, // не падать на конфликтах UNIQUE
});

await prisma.post.deleteMany({ where: { authorId: 1 } });
```

## include vs select — загрузка связей

`include` добавляет к записи её связи, оставляя все поля модели. `select` наоборот: возвращает ровно те поля, которые вы перечислили.

```typescript
// include: подтянуть связанные записи (внутри — JOIN)
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

// select: взять только нужные поля (проекция, projection)
const userNames = await prisma.user.findMany({
  select: {
    id: true,
    email: true,
    posts: {          // select вместе со связью — так можно
      select: { title: true, createdAt: true },
      where: { published: true },
    },
  },
});
// Тип результата точный:
// { id: number; email: string; posts: { title: string; ... }[] }

// include и select нельзя писать вместе на одном уровне
// ✗ { include: { posts: true }, select: { id: true } } — ошибка TS
// ✓ select: { id: true, posts: { select: { title: true } } } — так верно
```

## Вложенная запись — связанные записи за один запрос

Вложенная запись (nested write) — это создание или изменение связанных записей внутри одного вызова Prisma. Такой вызов Prisma сама заворачивает в транзакцию: либо запишется всё, либо ничего.

```typescript
// create с вложенным create: User и его Post за один запрос
const user = await prisma.user.create({
  data: {
    email: 'alice@example.com',
    profile: {
      create: { bio: 'Senior Engineer' },  // заодно создать Profile
    },
    posts: {
      create: [
        { title: 'First post' },
        { title: 'Second post' },
      ],
    },
  },
  include: { profile: true, posts: true }, // вернуть вместе со связями
});

// connect — привязать уже существующую запись
await prisma.post.update({
  where: { id: 1 },
  data: {
    tags: {
      connect: [{ id: 1 }, { id: 2 }],     // добавить теги
      disconnect: [{ id: 3 }],              // убрать тег
      set: [{ id: 1 }],                     // оставить ровно эти, прежние отвязать
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

## Пагинация — по смещению или по курсору

Пагинация бывает двух видов. По смещению (offset) — «пропусти 20 строк, отдай следующие 10». По курсору (cursor) — «отдай 10 строк после вот этого `id`».

```typescript
// Пагинация по смещению — простая, но медленная на больших таблицах
const page2 = await prisma.post.findMany({
  skip: 20,   // OFFSET 20
  take: 10,   // LIMIT 10
  orderBy: { createdAt: 'desc' },
});
// Проблема: при OFFSET 1000000 PostgreSQL всё равно читает 1000010 строк

// Пагинация по курсору — для больших таблиц и бесконечной прокрутки
const nextPage = await prisma.post.findMany({
  cursor: { id: lastSeenId },   // начать после этого id
  take: 10,
  skip: 1,                       // пропустить сам курсор
  orderBy: { id: 'asc' },
});
// Внутри: WHERE id > lastSeenId LIMIT 10 → O(log N) по индексу
```

## Проблема N+1 и её решение

N+1 — это когда на список из N записей уходит N+1 запросов: один за самим списком и ещё по одному за связями каждой строки.

```typescript
// N+1: на каждого user уходит отдельный запрос к posts
const users = await prisma.user.findMany();
for (const user of users) {
  const posts = await prisma.post.findMany({ where: { authorId: user.id } });
  // 1 запрос на findMany + N запросов на posts = N+1
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

- **"include всегда делает `JOIN`"** — не совсем. В Prisma 5 и новее `include` в большинстве случаев превращается в `JOIN`, но для некоторых схем запроса Prisma делает отдельный `SELECT ... WHERE id IN (...)`. Включите `log: ['query']` — и увидите настоящий SQL, а не предположение о нём.

- **"select и include нельзя использовать вместе"** — нельзя только на одном уровне. `{ select, include }` в одном объекте — ошибка TypeScript. А вкладывать друг в друга можно: `select: { id: true, posts: { select: { title: true } } }` вернёт два поля пользователя и по одному полю каждого поста.

- **"Неявная связка многие-ко-многим лучше для production"** — наоборот. Явная таблица-связка — это ваша собственная модель, поэтому в ней можно:
  - добавлять поля вроде `assignedAt` или `role`;
  - обращаться к ней напрямую: `prisma.userRole.findMany()`;
  - настраивать каскадное удаление для каждой стороны отдельно.

- **"findUnique быстрее findFirst"** — да. `findUnique` превращается в `WHERE id = ?` по индексированному полю. То же условие в `findFirst` даёт тот же результат, но Prisma не обязательно оптимизирует его так же. Берите `findUnique`, когда ищете по полям `@id` или `@unique`.

- **"Пагинация по курсору всегда лучше, чем по смещению"** — курсор лучше на больших таблицах и в бесконечной прокрутке. Но по курсору нельзя прыгнуть на произвольную страницу: до страницы 50 придётся пройти страницы с 1 по 49. Значит, для интерфейса с нумерованными страницами берите смещение, а для бесконечной прокрутки и API — курсор.
