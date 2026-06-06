<!-- verified: 2026-06-05, corrections: 0 -->
# Transaction Isolation Levels

## Зачем вообще нужны уровни изоляции

Представим:

Есть две транзакции:

Transaction A

```sql
BEGIN;
```

Transaction B

```sql
BEGIN;
```

Обе работают с одними и теми же данными.

Возникает вопрос:

Что должна видеть каждая транзакция?

- незакоммиченные данные?
- старые данные?
- новые данные?
- изменения других транзакций?

Для этого существуют уровни изоляции.

---

# Какие проблемы пытаются решить

## Dirty Read

Транзакция читает данные другой транзакции,
которая еще не выполнила COMMIT.

---

Пример

Transaction A:

```sql
BEGIN;

UPDATE accounts
SET balance = 0
WHERE id = 1;
```

COMMIT еще не выполнен.

---

Transaction B:

```sql
SELECT balance
FROM accounts;
```

Получает:

```txt
0
```

---

После этого:

```sql
ROLLBACK;
```

---

Получается:

Transaction B прочитала данные,
которых никогда не существовало.

Это Dirty Read.

---

# Non-Repeatable Read

Один и тот же SELECT внутри транзакции
возвращает разные результаты.

---

Transaction A:

```sql
BEGIN;

SELECT balance
FROM accounts
WHERE id = 1;
```

Результат:

```txt
100
```

---

Transaction B:

```sql
UPDATE accounts
SET balance = 200
WHERE id = 1;

COMMIT;
```

---

Transaction A снова делает:

```sql
SELECT balance
FROM accounts
WHERE id = 1;
```

Получает:

```txt
200
```

---

Внутри одной транзакции данные изменились.

Это Non-Repeatable Read.

---

# Phantom Read

Проблема не в изменении строки,
а в появлении новых строк.

---

Transaction A:

```sql
BEGIN;

SELECT *
FROM orders
WHERE status = 'NEW';
```

Получает:

```txt
5 rows
```

---

Transaction B:

```sql
INSERT INTO orders ...
COMMIT;
```

---

Transaction A повторяет запрос.

Теперь:

```txt
6 rows
```

---

Появился "фантом".

Это Phantom Read.

---

# SQL Standard Isolation Levels

Стандарт определяет:

```txt
Read Uncommitted
Read Committed
Repeatable Read
Serializable
```

---

# PostgreSQL и Read Uncommitted

Важно:

PostgreSQL НЕ поддерживает Dirty Read.

Поэтому:

```txt
Read Uncommitted
=
Read Committed
```

---

# Read Committed

Уровень по умолчанию.

Самый популярный.

---

Каждый SELECT видит только
закоммиченные данные.

---

Но каждый новый SELECT может видеть
новые коммиты других транзакций.

---

Разрешает:

```txt
Non-Repeatable Read
Phantom Read
```

---

Запрещает:

```txt
Dirty Read
```

---

Пример

SELECT #1

```txt
balance = 100
```

другая транзакция:

```txt
COMMIT
balance = 200
```

SELECT #2

```txt
balance = 200
```

---

# Repeatable Read

В PostgreSQL реализован через MVCC snapshot.

---

Когда транзакция начинается:

```sql
BEGIN;
```

создается snapshot данных.

---

Все SELECT внутри транзакции
видят именно этот snapshot.

---

Даже если другие транзакции выполнят:

```sql
COMMIT;
```

данные для текущей транзакции
не изменятся.

---

Запрещает:

```txt
Dirty Read
Non-Repeatable Read
Phantom Read*
```

(*) В PostgreSQL благодаря MVCC фактически и phantom reads тоже предотвращаются.

---

Пример

Transaction A:

```sql
BEGIN;
```

видит:

```txt
balance = 100
```

---

Transaction B:

```sql
UPDATE ...
COMMIT;
```

---

Transaction A:

```sql
SELECT ...
```

всё еще видит:

```txt
balance = 100
```

---

# Serializable

Самый строгий уровень.

---

PostgreSQL пытается сделать вид,
будто все транзакции выполнялись
последовательно одна за другой.

---

Если возникает конфликт:

PostgreSQL завершает одну транзакцию ошибкой:

```txt
could not serialize access
```

---

Приложение должно повторить транзакцию.

---

# Как выбрать уровень

## Read Committed

90% приложений.

Подходит для:

```txt
CRUD
CMS
обычных бизнес-приложений
```

---

## Repeatable Read

Когда важна консистентная картина данных.

Например:

```txt
финансовая аналитика
отчеты
агрегации
```

---

## Serializable

Когда важна абсолютная корректность.

Например:

```txt
банковские операции
биржи
биллинг
```

---

# Интервью вопрос

Почему PostgreSQL может обеспечивать Repeatable Read без тотальных блокировок?

Ответ:

Благодаря MVCC.
Каждая транзакция работает со своим snapshot данных,
а не блокирует все строки для чтения.
