# ACID и Transactions

## Что такое Transaction

Transaction — это группа операций, которая выполняется как единое целое.

Классический пример:

Перевод денег между счетами.

```txt
Account A -> -100$
Account B -> +100$
```

Обе операции должны либо выполниться вместе, либо не выполниться вообще.

---

# Пример транзакции

```sql
BEGIN;

UPDATE accounts
SET balance = balance - 100
WHERE id = 1;

UPDATE accounts
SET balance = balance + 100
WHERE id = 2;

COMMIT;
```

---

# Что если произошла ошибка?

Тогда:

```sql
ROLLBACK;
```

и база откатит изменения.

---

# ACID

ACID — набор гарантий, которые предоставляет PostgreSQL.

---

# A — Atomicity

Либо всё выполняется.

Либо ничего.

Пример:

```txt
UPDATE A
UPDATE B
```

Если UPDATE B упал:

```txt
UPDATE A тоже откатывается
```

---

# C — Consistency

После завершения транзакции база должна оставаться в корректном состоянии.

Пример:

Есть ограничение:

```sql
balance >= 0
```

Транзакция не может оставить данные в невалидном состоянии.

---

# I — Isolation

Параллельные транзакции не должны мешать друг другу.

Например:

```txt
User A обновляет запись
User B читает запись
```

СУБД должна контролировать это взаимодействие.

---

# D — Durability

После COMMIT данные гарантированно сохраняются.

Даже если:

- приложение упало
- сервер перезагрузился

---

# Жизненный цикл транзакции

```txt
BEGIN
 ↓
SQL операции
 ↓
COMMIT
```

или

```txt
BEGIN
 ↓
Ошибка
 ↓
ROLLBACK
```

---

# Автокоммит

По умолчанию PostgreSQL работает в режиме автокоммита.

Например:

```sql
UPDATE users
SET name = 'Max'
WHERE id = 1;
```

Фактически выполняется как:

```sql
BEGIN;
UPDATE ...
COMMIT;
```

---

# Когда нужны транзакции

Используйте транзакции, если:

- изменяется несколько таблиц
- данные должны измениться одновременно
- существует риск частичного обновления

---

# Пример без транзакции

```sql
UPDATE orders;
UPDATE inventory;
```

Если второй запрос упадет:

```txt
order изменен
inventory нет
```

Данные испорчены.

---

# Пример с транзакцией

```sql
BEGIN;

UPDATE orders;
UPDATE inventory;

COMMIT;
```

Либо оба изменения сохранятся.

Либо оба откатятся.

---

# Savepoint

Позволяет делать частичный откат.

```sql
BEGIN;

UPDATE users;

SAVEPOINT before_payment;

UPDATE payments;

ROLLBACK TO before_payment;

COMMIT;
```

---

# Deadlock

Deadlock возникает когда:

Transaction A ждёт B.

Transaction B ждёт A.

Пример:

```txt
A держит row1
B держит row2

A хочет row2
B хочет row1
```

Получаем цикл ожидания.

---

# Что делает PostgreSQL

PostgreSQL обнаруживает deadlock автоматически.

Одна из транзакций будет завершена ошибкой:

```txt
deadlock detected
```

---

# Практические рекомендации

Всегда:

- держите транзакции короткими
- не выполняйте сетевые вызовы внутри транзакции
- не держите транзакцию открытой дольше необходимого
- обновляйте строки в одинаковом порядке

---

# Prisma Transaction Example

```ts
await prisma.$transaction([
  prisma.user.create(...),
  prisma.profile.create(...),
]);
```

---

# NestJS + Prisma Example

```ts
await this.prisma.$transaction(async (tx) => {
  const user = await tx.user.create(...);

  await tx.profile.create({
    data: {
      userId: user.id,
    },
  });
});
```

---

# Интервью-ответ

Что такое транзакция?

Transaction — это группа операций, выполняемых как единое целое. PostgreSQL гарантирует ACID-свойства: атомарность, согласованность, изолированность и долговечность данных. Если одна операция внутри транзакции завершается ошибкой, все изменения откатываются через ROLLBACK.