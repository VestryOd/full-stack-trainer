<!-- verified: 2026-06-05, corrections: 0 -->
# MVCC, Locks и VACUUM

## Главная проблема любой базы данных

Представим:

Пользователь A читает данные.

Одновременно пользователь B обновляет данные.

Возникает вопрос:

```txt
Что должен увидеть пользователь A?
```

Старые данные?

Новые данные?

Ждать завершения UPDATE?

---

# Наивное решение

Использовать блокировки.

Например:

```txt
Reader берет lock
Writer ждет
```

или

```txt
Writer берет lock
Reader ждет
```

---

Проблема:

Под нагрузкой всё начинает блокировать друг друга.

---

# Решение PostgreSQL

MVCC

Multi-Version Concurrency Control

---

Главная идея MVCC

PostgreSQL не изменяет строку напрямую.

Он создает новую версию строки.

---

Допустим есть запись:

```txt
id=1
balance=100
```

---

UPDATE

```sql
UPDATE accounts
SET balance = 200
WHERE id = 1;
```

---

Что происходит на самом деле

НЕ:

```txt
100 → 200
```

---

А:

```txt
Version 1
balance = 100

Version 2
balance = 200
```

---

Старая версия остается существовать.

---

# Почему это круто

Reader может читать:

```txt
Version 1
```

Пока Writer создает:

```txt
Version 2
```

---

Получаем:

```txt
Readers don't block writers
Writers don't block readers
```

---

Это одна из главных причин высокой производительности PostgreSQL.

---

# Tuple Versions

Каждая строка в PostgreSQL содержит служебные поля.

Упрощенно:

```txt
xmin
xmax
```

---

# xmin

Transaction ID создавшей транзакции.

---

Например:

```txt
Transaction #100
INSERT row
```

---

Тогда:

```txt
xmin = 100
```

---

# xmax

Transaction ID удалившей строку.

---

Например:

```txt
Transaction #200
DELETE row
```

---

Тогда:

```txt
xmax = 200
```

---

# Как работает SELECT

Когда транзакция делает:

```sql
SELECT *
FROM users;
```

PostgreSQL смотрит:

```txt
мой snapshot
xmin
xmax
```

---

И решает:

```txt
видна строка
или не видна
```

---

# Snapshot

При старте транзакции создается snapshot.

---

Snapshot содержит:

```txt
какие транзакции завершены
какие активны
```

---

Поэтому две транзакции могут видеть разные версии одной строки.

---

# Пример MVCC

Transaction A

```sql
BEGIN;
SELECT balance;
```

Видит:

```txt
100
```

---

Transaction B

```sql
UPDATE balance=200;
COMMIT;
```

---

Transaction A снова делает:

```sql
SELECT balance;
```

---

Repeatable Read:

```txt
100
```

---

Read Committed:

```txt
200
```

---

# Проблема MVCC

Старые версии строк остаются.

---

Например:

```sql
UPDATE users
SET name='John';
```

---

Старая версия строки не удаляется сразу.

---

Появляется:

```txt
dead tuple
```

---

# Dead Tuple

Строка больше никому не нужна.

Но всё еще лежит на диске.

---

Пример

```txt
Version 1 ← dead
Version 2 ← active
```

---

Со временем их становится много.

---

# Что будет без очистки

Таблицы начинают расти.

---

Например:

```txt
100 MB данных
```

через год:

```txt
5 GB таблица
```

---

Хотя живых данных всё еще:

```txt
100 MB
```

---

Это называется:

```txt
table bloat
```

---

# VACUUM

VACUUM очищает dead tuples.

---

Он:

```txt
находит старые версии строк
освобождает место
обновляет статистику
```

---

# Важно

VACUUM НЕ уменьшает размер файла.

Он делает место доступным для повторного использования.

---

# VACUUM FULL

Другой режим.

---

Он:

```txt
перестраивает таблицу
возвращает место ОС
```

---

Но:

```txt
берет ACCESS EXCLUSIVE LOCK
```

---

Поэтому используется редко.

---

# AUTOVACUUM

В большинстве случаев работает автоматически.

---

Специальный процесс PostgreSQL:

```txt
autovacuum worker
```

---

Следит за:

```txt
dead tuples
statistics
table bloat
```

---

# Почему нельзя отключать Autovacuum

Очень популярный вопрос.

---

Если отключить:

```txt
dead tuples растут
индексы раздуваются
таблицы растут
производительность падает
```

---

Через некоторое время база начнет деградировать.

---

# Locks

MVCC не отменяет блокировки полностью.

---

PostgreSQL всё еще использует locks.

---

Но гораздо реже.

---

# Row Lock

Блокируется отдельная строка.

---

Например:

```sql
SELECT *
FROM users
WHERE id = 1
FOR UPDATE;
```

---

Теперь никто не может изменить эту строку.

---

# Когда нужен FOR UPDATE

Очень любят спрашивать.

---

Например:

```txt
остатки товара
баланс счета
бронирование мест
```

---

Чтобы избежать race condition.

---

# Table Lock

Блокируется вся таблица.

---

Например:

```sql
ALTER TABLE users
ADD COLUMN age INTEGER;
```

---

Некоторые DDL операции берут table lock.

---

# Deadlock

Transaction A

```txt
lock row1
ждет row2
```

---

Transaction B

```txt
lock row2
ждет row1
```

---

Получается цикл.

---

PostgreSQL обнаруживает deadlock автоматически.

---

Одну транзакцию завершает ошибкой:

```txt
deadlock detected
```

---

# Senior Interview Answer

Что такое MVCC?

MVCC (Multi-Version Concurrency Control) — механизм конкурентного доступа PostgreSQL, при котором UPDATE создает новую версию строки вместо изменения существующей. Благодаря этому чтение и запись практически не блокируют друг друга. Старые версии строк очищаются процессом VACUUM.
