# Транзакции и производительность в Prisma

## Транзакции — два режима

В Prisma два вида транзакций. Оба превращаются в три одинаковые команды PostgreSQL: `BEGIN`, `COMMIT`, `ROLLBACK`. Это команды SQL (Structured Query Language) — языка, на котором говорит сама база данных, а Prisma пишет их за вас.

```typescript
// Режим 1: Sequential (batch) — последовательный массив операций,
// результаты между ними недоступны
const [user, profile] = await prisma.$transaction([
  prisma.user.create({ data: { email: 'alice@example.com' } }),
  prisma.profile.create({ data: { bio: 'Engineer', userId: 1 } }), // нет доступа к user.id!
]);
// Применять, когда операции независимы и все данные известны заранее

// Режим 2: Interactive (интерактивный) — колбэк, результат одной
// операции доступен в следующей
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
  timeout: 5000,                   // мс, по умолчанию 5000 — после истечения ROLLBACK
  maxWait: 2000,                   // мс ожидания соединения из пула
});
```

## Уровни изоляции (isolation levels) — когда они важны

```typescript
// Уровни изоляции PostgreSQL через Prisma
type IsolationLevel = 
  | 'ReadUncommitted'  // грязное чтение (не рекомендуется)
  | 'ReadCommitted'    // по умолчанию в PostgreSQL: видит только
                       // зафиксированные (COMMIT) данные
  | 'RepeatableRead'   // один снимок данных на всю транзакцию,
                       // нет неповторяющихся чтений (non-repeatable reads)
  | 'Serializable';    // строжайший: транзакции как будто выполняются последовательно

// Пример: финансовая операция с Serializable
await prisma.$transaction(async (tx) => {
  const account = await tx.account.findUnique({ where: { id: accountId } });
  
  // Без Serializable: другая транзакция может изменить balance
  // между findUnique и update
  // С Serializable: PostgreSQL обнаружит конфликт → одна из транзакций упадёт
  // Приложение должно повторить её при SerializationFailure (код ошибки 40001)

  if (account.balance < amount) throw new Error('Insufficient funds');
  await tx.account.update({
    where: { id: accountId },
    data: { balance: { decrement: amount } },
  });
}, { isolationLevel: 'Serializable' });
```

## Блокировки — `SELECT FOR UPDATE` через `$queryRaw`

```typescript
// В Prisma нет встроенного API для FOR UPDATE
// Решение — $queryRaw внутри транзакции

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
// FOR UPDATE: другие транзакции, которые пытаются сделать UPDATE или
// SELECT FOR UPDATE по этой же строке, будут ждать конца текущей транзакции
```

## Проблема N+1 — диагностика и лечение

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

// РЕШЕНИЕ 2: groupBy + агрегация (один SQL-запрос)
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

// Диагностика: включить логирование запросов
const prisma = new PrismaClient({ log: ['query'] });
// Смотреть, сколько запросов уходит в консоль на один HTTP-запрос
```

## Пул соединений (connection pool) — настройка

```typescript
// PrismaClient держит пул соединений по умолчанию
// Размер пула по умолчанию: min(10, max_connections / 2)
// Для production настраивать явно

const prisma = new PrismaClient({
  datasources: {
    db: {
      url: `${process.env.DATABASE_URL}?connection_limit=20&pool_timeout=10`,
    },
  },
});
// connection_limit=20 → максимум 20 соединений в пуле
// pool_timeout=10 → ждать соединение 10 секунд, потом бросить ошибку

// В NestJS: PrismaService — синглтон, один пул на всё приложение
// Никогда не создавать new PrismaClient() на каждый запрос!

// Для serverless (AWS Lambda, Vercel):
// connection_limit=1 — у каждого экземпляра функции одно соединение
// Рекомендуется Prisma Accelerate или PgBouncer перед Lambda:
// они держат общий пул соединений
```

## select вместо include — оптимизация ответа

```typescript
// ПЛОХО: загружать весь объект User, когда нужны только id и email
const users = await prisma.user.findMany({
  include: { posts: true, profile: true }, // загрузит всё, включая пароли и токены
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

// ПЛОХО: глубоко вложенный include
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

## Массовые операции (bulk)

```typescript
// createMany — вставить много записей за один запрос
await prisma.post.createMany({
  data: posts.map(p => ({ title: p.title, authorId: userId })),
  skipDuplicates: true,
});
// Ограничение: createMany не умеет создавать связанные записи (nested create)

// updateMany — обновить по условию
const { count } = await prisma.post.updateMany({
  where: { authorId: userId, published: false },
  data: { published: true },
});

// deleteMany — удалить по условию
await prisma.post.deleteMany({
  where: { createdAt: { lt: new Date('2020-01-01') } },
});

// Для массовой вставки со связями или очень больших объёмов → $executeRaw
await prisma.$executeRaw`
  INSERT INTO posts (title, author_id, created_at)
  SELECT title, ${userId}, NOW()
  FROM json_array_elements_text(${JSON.stringify(titles)}::json) as title
`;
```

## Типичные ошибки на интервью

- **"Prisma $transaction сама защищает от состояний гонки"** — нет, не автоматически. Уровень изоляции по умолчанию — `ReadCommitted`. При параллельных транзакциях возможны неповторяющиеся чтения (non-repeatable reads) и фантомные чтения (phantom reads). Для критичных операций берите `isolationLevel: 'Serializable'` или `SELECT FOR UPDATE` через `$queryRaw`.

- **"Sequential-транзакция лучше Interactive"** — зависит от задачи. Sequential быстрее: нет накладных расходов (overhead) на удержание открытой транзакции. Зато результат одной операции нельзя использовать в следующей. Interactive нужен, когда между шагами есть логика: проверка условия или использование сгенерированного id.

- **"include всегда решает N+1"** — нет. Глубоко вложенный `include` (user → posts → comments → author) может дать тяжёлый JOIN с декартовым произведением. Альтернативы: `$queryRaw` с явным JOIN, `groupBy` с агрегацией или два отдельных запроса с `WHERE id IN (...)`.

- **"Пул соединений настраивать не нужно"** — для production нужно. Размера по умолчанию может не хватить под нагрузкой, а для serverless он наоборот избыточен. Для Lambda и Vercel: `connection_limit=1` плюс PgBouncer или Prisma Accelerate. Без нормальной настройки пула появятся ошибки "connection count exceeded".

- **"timeout в $transaction — это время выполнения SQL"** — нет. Это лимит на **всю** транзакцию, включая время работы вашего колбэка. Параметр `maxWait` — другое число: сколько ждать свободное соединение из пула. Поэтому медленный колбэк (например, вызов внешнего API внутри транзакции) съедает timeout и приводит к ROLLBACK. Вызовы внешних API держите за пределами транзакции.
