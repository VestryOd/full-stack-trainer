# Prisma Transactions and Performance

## Транзакции — два режима

Prisma предоставляет два вида транзакций. Оба транслируются в `BEGIN / COMMIT / ROLLBACK` в PostgreSQL.

```typescript
// Режим 1: Sequential (batch) — массив операций, результаты недоступны между ними
const [user, profile] = await prisma.$transaction([
  prisma.user.create({ data: { email: 'alice@example.com' } }),
  prisma.profile.create({ data: { bio: 'Engineer', userId: 1 } }), // нет доступа к user.id!
]);
// Используй когда: операции независимы и все данные известны заранее

// Режим 2: Interactive — callback, результат одной операции используется в следующей
await prisma.$transaction(async (tx) => {
  const user = await tx.user.create({
    data: { email: 'alice@example.com' },
  });

  // user.id известен → можно использовать в следующей операции
  await tx.profile.create({
    data: { bio: 'Engineer', userId: user.id },
  });

  const balance = await tx.account.findUnique({
    where: { userId: user.id },
  });

  if (!balance || balance.amount < 100) {
    throw new Error('Insufficient funds'); // автоматически → ROLLBACK
  }

  await tx.account.update({
    where: { userId: user.id },
    data: { amount: { decrement: 100 } },
  });
}, {
  isolationLevel: 'Serializable', // опционально: задать уровень изоляции
  timeout: 5000,                   // ms, default 5000 — после истечения ROLLBACK
  maxWait: 2000,                   // ms ожидания получения соединения из pool
});
```

## Isolation Levels и когда они нужны

```typescript
// PostgreSQL isolation levels через Prisma
type IsolationLevel = 
  | 'ReadUncommitted'  // грязное чтение (не рекомендуется)
  | 'ReadCommitted'    // default в PostgreSQL — видит только COMMIT-нутые данные
  | 'RepeatableRead'   // один snapshot на всю транзакцию, нет non-repeatable reads
  | 'Serializable';    // строжайший: транзакции как будто выполняются последовательно

// Пример: финансовая операция с Serializable
await prisma.$transaction(async (tx) => {
  const account = await tx.account.findUnique({ where: { id: accountId } });
  
  // Без Serializable: другая транзакция может изменить balance между findUnique и update
  // С Serializable: PostgreSQL обнаружит конфликт → одна из транзакций получит error
  // Приложение должно повторить транзакцию при SerializationFailure (error code 40001)
  
  if (account.balance < amount) throw new Error('Insufficient funds');
  await tx.account.update({ where: { id: accountId }, data: { balance: { decrement: amount } } });
}, { isolationLevel: 'Serializable' });
```

## Блокировки — SELECT FOR UPDATE через $queryRaw

```typescript
// Prisma не имеет встроенного API для FOR UPDATE
// Используй $queryRaw внутри транзакции

await prisma.$transaction(async (tx) => {
  // SELECT FOR UPDATE — блокирует строку до конца транзакции
  const [account] = await tx.$queryRaw<Account[]>`
    SELECT * FROM accounts WHERE id = ${accountId} FOR UPDATE
  `;
  
  if (account.balance < amount) {
    throw new Error('Insufficient funds');
  }
  
  await tx.account.update({
    where: { id: accountId },
    data: { balance: { decrement: amount } },
  });
});
// FOR UPDATE: другие транзакции которые пытаются UPDATE/SELECT FOR UPDATE эту строку
// будут ждать пока текущая транзакция не завершится
```

## N+1 проблема — диагностика и лечение

```typescript
// ПРОБЛЕМА: N+1
const users = await prisma.user.findMany(); // 1 запрос
for (const user of users) {
  // N отдельных запросов — по одному на каждого пользователя!
  const posts = await prisma.post.count({ where: { authorId: user.id } });
}

// РЕШЕНИЕ 1: include (JOIN)
const usersWithPosts = await prisma.user.findMany({
  include: { posts: { select: { id: true } } },
});
const result = usersWithPosts.map(u => ({ ...u, postCount: u.posts.length }));

// РЕШЕНИЕ 2: groupBy + aggregate (один SQL запрос)
const postCounts = await prisma.post.groupBy({
  by: ['authorId'],
  _count: { id: true },
  where: { authorId: { in: users.map(u => u.id) } },
});

// РЕШЕНИЕ 3: $queryRaw с COUNT (максимальный контроль)
const result = await prisma.$queryRaw<{ id: number; post_count: number }[]>`
  SELECT u.id, COUNT(p.id)::int as post_count
  FROM users u
  LEFT JOIN posts p ON p.author_id = u.id
  GROUP BY u.id
`;

// Диагностика: включить query logging
const prisma = new PrismaClient({ log: ['query'] });
// Смотреть на количество запросов в консоли при одном HTTP запросе
```

## Connection Pool — настройка

```typescript
// PrismaClient использует connection pool по умолчанию
// Размер пула: min(10, max_connections / 2) по умолчанию
// Для production: явно настроить

const prisma = new PrismaClient({
  datasources: {
    db: {
      url: `${process.env.DATABASE_URL}?connection_limit=20&pool_timeout=10`,
    },
  },
});
// connection_limit=20 → максимум 20 соединений в пуле
// pool_timeout=10 → ждать 10 сек получения соединения, потом throw error

// В NestJS: PrismaService — singleton, один connection pool на всё приложение
// НИКОГДА не создавать new PrismaClient() в каждом запросе!

// Для serverless (AWS Lambda, Vercel):
// connection_limit=1 — каждый инстанс функции имеет одно соединение
// Рекомендуется: Prisma Accelerate или PgBouncer для connection pooling перед Lambda
```

## select вместо include — оптимизация ответа

```typescript
// ПЛОХО: загружать весь User объект когда нужны только id и email
const users = await prisma.user.findMany({
  include: { posts: true, profile: true }, // загружает ВСЁ включая пароли, токены
});

// ХОРОШО: запрашивать только нужные поля
const users = await prisma.user.findMany({
  select: {
    id: true,
    email: true,
    name: true,
    posts: {
      select: { id: true, title: true, createdAt: true },
      where: { published: true },
      orderBy: { createdAt: 'desc' },
      take: 3,
    },
  },
});
// Меньше данных по сети, меньше памяти, быстрее сериализация в JSON

// ПЛОХО: глубокий вложенный include
const data = await prisma.user.findMany({
  include: {
    posts: {
      include: {
        comments: {
          include: { author: { include: { profile: true } } },
        },
      },
    },
  },
});
// Может генерировать тяжёлый JOIN с декартовым произведением
```

## Bulk операции

```typescript
// createMany — вставить много записей за один запрос
await prisma.post.createMany({
  data: posts.map(p => ({ title: p.title, authorId: userId })),
  skipDuplicates: true,
});
// Ограничение: createMany не поддерживает nested create (relations)

// updateMany — обновить по условию
const { count } = await prisma.post.updateMany({
  where: { authorId: userId, published: false },
  data: { published: true },
});

// deleteMany — удалить по условию
await prisma.post.deleteMany({
  where: { createdAt: { lt: new Date('2020-01-01') } },
});

// Для bulk insert с relations или больших объёмов → $executeRaw
await prisma.$executeRaw`
  INSERT INTO posts (title, author_id, created_at)
  SELECT title, ${userId}, NOW()
  FROM json_array_elements_text(${JSON.stringify(titles)}::json) as title
`;
```

## Типичные ошибки на интервью

- **"Prisma $transaction гарантирует изоляцию от race conditions"** — нет автоматически. Уровень изоляции по умолчанию — `ReadCommitted`. При параллельных транзакциях возможны Non-Repeatable Reads и Phantom Reads. Для критичных операций: `isolationLevel: 'Serializable'` или `SELECT FOR UPDATE` через `$queryRaw`.

- **"Sequential транзакция лучше Interactive"** — зависит от задачи. Sequential быстрее (нет overhead на удержание транзакции открытой), но не позволяет использовать результат одной операции в следующей. Interactive — когда нужна логика между шагами (условия, использование сгенерированного id).

- **"include решает N+1 всегда"** — нет. Deep nested include (user → posts → comments → author) может генерировать тяжёлые JOIN с декартовым произведением. Альтернатива: `$queryRaw` с явным JOIN, или `groupBy` + aggregate, или разбить на два отдельных запроса с `WHERE id IN (...)`.

- **"Connection pool настраивать не нужно"** — нужно для production. Default pool size может быть недостаточен под нагрузкой или избыточен для serverless. Для Lambda/Vercel: `connection_limit=1` + PgBouncer/Prisma Accelerate. Без правильного pooling: "connection count exceeded" ошибки.

- **"timeout в $transaction — сколько времени выполняется SQL"** — нет. `timeout` — максимальное время ВСЕЙ транзакции (включая время выполнения callback). `maxWait` — время ожидания получения соединения из pool. Если callback медленный (например, внешний API внутри транзакции) → timeout → ROLLBACK. Внешние API вызовы не должны быть внутри транзакции.
