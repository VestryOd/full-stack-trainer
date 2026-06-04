# Prisma Transactions and Performance

## Главное правило

Prisma не отменяет знания PostgreSQL.

---

Очень частая ошибка:

```txt
Я знаю Prisma
↓
Значит понимаю БД
```

---

На самом деле:

```txt
Prisma
↓
генерирует SQL
↓
PostgreSQL выполняет SQL
```

---

Поэтому:

- индексы
- MVCC
- транзакции
- planner

по-прежнему важны.

---

# Prisma Transactions

Простейший вариант.

---

```ts
await prisma.$transaction([
  prisma.user.create(...),
  prisma.profile.create(...),
]);
```

---

Под капотом:

```sql
BEGIN;

INSERT ...
INSERT ...

COMMIT;
```

---

Если один запрос падает:

```sql
ROLLBACK;
```

---

# Interactive Transactions

Более гибкий вариант.

---

```ts
await prisma.$transaction(async (tx) => {

  const user = await tx.user.create(...);

  await tx.profile.create(...);

});
```

---

Что происходит

Prisma:

```txt
BEGIN
↓
передает tx
↓
все операции используют одну транзакцию
↓
COMMIT
```

---

При ошибке:

```txt
ROLLBACK
```

---

# Когда использовать Interactive Transactions

Если результат предыдущего запроса
нужен следующему.

---

Пример:

```txt
создали User
↓
получили id
↓
создали Profile
```

---

# Isolation Levels

Prisma позволяет задавать уровень изоляции.

---

Например:

```ts
await prisma.$transaction(
  async (tx) => {},
  {
    isolationLevel: 'Serializable',
  }
);
```

---

Под капотом используется
изоляция PostgreSQL.

---

# Очень популярный вопрос

Гарантирует ли Prisma защиту от race conditions?

---

Ответ:

Нет.

---

Race conditions решаются:

```txt
PostgreSQL
locks
constraints
transactions
```

---

Не ORM.

---

# N+1 Problem

Очень любят спрашивать.

---

Представим:

```ts
const users = await prisma.user.findMany();
```

---

Далее:

```ts
for (const user of users) {
  await prisma.post.findMany(...);
}
```

---

Получаем:

```txt
1 запрос на пользователей
+
N запросов на посты
```

---

Это и есть:

```txt
N+1 Problem
```

---

# Как исправить

Использовать include.

---

```ts
await prisma.user.findMany({
  include: {
    posts: true,
  },
});
```

---

Теперь Prisma может получить данные
значительно эффективнее.

---

# include злоупотребление

Очень важная тема.

---

Плохо:

```ts
include: {
  posts: {
    include: {
      comments: {
        include: {
          author: true,
        }
      }
    }
  }
}
```

---

Можно получить огромный граф данных.

---

И запрос станет медленным.

---

# select

Лучше возвращать только нужные поля.

---

Плохо:

```ts
include: {
  posts: true
}
```

---

Лучше:

```ts
select: {
  id: true,
  email: true,
}
```

---

# Pagination

Очень популярно.

---

Плохо:

```ts
findMany()
```

на миллионе строк.

---

Лучше:

```ts
take: 20
```

---

# Offset Pagination

```ts
skip: 1000
take: 20
```

---

Минус:

Чем дальше страница,
тем медленнее запрос.

---

# Cursor Pagination

Лучше для больших таблиц.

---

```ts
cursor: {
  id: 100
}
```

---

Использует индекс.

---

# Connection Pool

Очень важная тема.

---

Prisma не создает новое соединение
на каждый запрос.

---

Используется connection pool.

---

Иначе:

```txt
1000 запросов
↓
1000 connections
```

---

PostgreSQL быстро перестанет отвечать.

---

# Bulk Operations

Очень полезно.

---

Плохо:

```ts
for (...) {
 create(...)
}
```

---

Лучше:

```ts
createMany()
```

---

То же самое:

```ts
updateMany()
deleteMany()
```

---

# Raw SQL

Иногда ORM недостаточно.

---

Prisma позволяет:

```ts
await prisma.$queryRaw`
  SELECT *
  FROM users
`;
```

---

Или:

```ts
await prisma.$executeRaw`
  UPDATE users ...
`;
```

---

# Когда нужен Raw SQL

Сложные аналитические запросы.

---

Window Functions.

---

CTE.

---

Database-specific оптимизации.

---

# Performance Checklist

Перед оптимизацией:

1. Проверить EXPLAIN ANALYZE
2. Проверить индексы
3. Проверить include
4. Проверить select
5. Проверить pagination
6. Проверить N+1

---

# Interview Answer

Prisma transactions являются оберткой над транзакциями базы данных. Для производительности важно избегать N+1 запросов, использовать select вместо избыточных include, применять pagination и помнить, что реальные проблемы производительности обычно решаются на уровне SQL и PostgreSQL, а не ORM.