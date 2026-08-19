<!-- verified: 2026-06-05, corrections: 0 -->
# Уровни изоляции транзакций

## Зачем нужны уровни изоляции — и почему "полная изоляция" стоит дорого

Уровень изоляции — это настройка, которая решает, **какие данные видит одна транзакция, пока другие меняют те же данные**. В PostgreSQL их четыре, и отличаются они только тем, какие аномалии пропускают.

Теоретически правильный ответ был бы такой: «каждая транзакция видит только то, что увидела бы при строго последовательном выполнении». Но это требует блокировки на каждую операцию, а она убивает параллелизм. Поэтому уровень изоляции — это компромисс между строгостью гарантии и производительностью.

Стандарт SQL определяет все четыре уровня через список **аномалий**, которые каждый уровень запрещает. SQL расшифровывается как Structured Query Language — стандартный язык запросов к реляционным данным.

## Три классические аномалии конкурентности — с механикой, а не просто определениями

### Dirty Read — чтение незакоммиченных данных

```sql
-- Транзакция A
BEGIN;
UPDATE accounts SET balance = 0 WHERE id = 1;
-- (COMMIT ещё не было)

-- Транзакция B (при Dirty Read — проблемный сценарий)
SELECT balance FROM accounts WHERE id = 1; -- вернёт 0
-- Если A сделает ROLLBACK — B прочитала данные, которых не существовало
```

PostgreSQL **не** допускает dirty read ни на одном уровне изоляции, включая `READ UNCOMMITTED`. Причина — MVCC. Multi-Version Concurrency Control, многоверсионность, хранит несколько версий каждой строки, и читатель видит только версии, помеченные как закоммиченные. Подробнее — [MVCC, блокировки и VACUUM](./05-mvcc-locks-vacuum.md).

### Non-Repeatable Read — повторный SELECT возвращает другой результат

```sql
-- Транзакция A (READ COMMITTED)
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- → 100

-- Транзакция B
UPDATE accounts SET balance = 200 WHERE id = 1;
COMMIT;

-- Транзакция A снова
SELECT balance FROM accounts WHERE id = 1;  -- → 200 (!!)
-- Внутри одной транзакции один и тот же SELECT дал разные результаты
COMMIT;
```

Почему это проблема: транзакция A могла уже использовать первое значение, 100, для бизнес-решения. Теперь второй `SELECT` противоречит первому внутри одной логической операции.

### Phantom Read — повторный SELECT возвращает другое количество строк

```sql
-- Транзакция A (REPEATABLE READ в стандарте SQL)
BEGIN;
SELECT COUNT(*) FROM orders WHERE status = 'NEW';  -- → 5

-- Транзакция B
INSERT INTO orders (status) VALUES ('NEW');
COMMIT;

-- Транзакция A
SELECT COUNT(*) FROM orders WHERE status = 'NEW';  -- → 6 (phantom!)
COMMIT;
```

Отличие от non-repeatable read: там **меняется** существующая строка, а здесь **появляются** новые строки или исчезают старые.

В PostgreSQL `REPEATABLE READ` защищает и от phantom read — благодаря снапшоту MVCC. В стандарте `REPEATABLE READ` слабее: он обещает защиту только от non-repeatable read.

### Serialization Anomaly — результат не соответствует ни одному последовательному порядку

```sql
-- Обе транзакции идут ОДНОВРЕМЕННО, шаги чередуются.
-- Правило: суммарный баланс по всем счетам не должен падать ниже 900.

-- Транзакция A:
BEGIN;
SELECT SUM(balance) FROM accounts;  -- → 1000
-- 1000 - 100 = 900, значит снять 100 можно
UPDATE accounts SET balance = balance - 100 WHERE id = 1;

-- Транзакция B (в это же время):
BEGIN;
SELECT SUM(balance) FROM accounts;  -- → 1000 (та же сумма!)
-- B считает то же самое по тому же числу
UPDATE accounts SET balance = balance - 100 WHERE id = 2;

-- Транзакция A:
COMMIT;

-- Транзакция B:
COMMIT;
-- Суммарный баланс теперь 800 — правило нарушено.
```

Выполните их одну за другой — вторая прочитает 900 и остановится. Выполните одновременно — каждая читает сумму до того, как запись другой попадёт в базу, и результат не совпадает ни с одним последовательным порядком. Это и есть serialization anomaly, и ловит её только `SERIALIZABLE`. Её бытовая форма разобрана ниже в отдельном разделе под именем write-skew.

## Четыре уровня изоляции PostgreSQL — что реально происходит

| Уровень | Dirty Read | Non-Repeatable Read | Phantom Read | Serialization Anomaly |
|---|---|---|---|---|
| `READ UNCOMMITTED` | невозможен* | возможен | возможен | возможен |
| `READ COMMITTED` | невозможен | возможен | возможен | возможен |
| `REPEATABLE READ` | невозможен | невозможен | невозможен* | возможен |
| `SERIALIZABLE` | невозможен | невозможен | невозможен | невозможен |

Обе клетки со звёздочкой — это добавка PostgreSQL, а не поведение стандарта. PostgreSQL реализует `READ UNCOMMITTED` как `READ COMMITTED`, а его `REPEATABLE READ` защищает ещё и от phantom read — это бонус MVCC.

### READ COMMITTED — уровень по умолчанию, наиболее распространённый

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED; -- или просто BEGIN (это дефолт)
```

Снапшот создаётся в начале **каждого оператора**, то есть это снапшот уровня оператора. Это значит:

- `SELECT` №1 видит все коммиты, случившиеся до `SELECT` №1.
- `SELECT` №2, который идёт позже в той же транзакции, видит все коммиты до `SELECT` №2 — включая те, что произошли между №1 и №2.

Отсюда и берётся non-repeatable read.

Типичный сценарий: больше 90% CRUD-приложений (create, read, update, delete — создание, чтение, обновление, удаление). Этого хватает для любой операции, которой не нужна единая картина данных на всю транзакцию.

### REPEATABLE READ — снапшот на момент BEGIN

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

Снапшот создаётся **один раз**, на момент первого оператора в транзакции. В PostgreSQL это либо момент `BEGIN`, либо момент первого `SELECT` — зависит от контекста. Все последующие `SELECT` в транзакции видят этот единственный снапшот, независимо от новых коммитов других транзакций.

Специфика PostgreSQL: механизм здесь — MVCC, а не диапазонные блокировки, как в Oracle. Поэтому `REPEATABLE READ` защищает и от phantom read: строки, вставленные другой транзакцией после вашего снапшота, просто не видны.

Запись всё равно может упасть. Допустим, ваша транзакция обновляет или удаляет строку, которую после создания снапшота изменила и закоммитила другая транзакция. Тогда PostgreSQL откатит вашу транзакцию:

```txt
ERROR:  could not serialize access due to concurrent update
```

Это сообщение принадлежит `REPEATABLE READ`, а не `SERIALIZABLE`. Его SQLSTATE — 40001, так что логика повтора та же. SQLSTATE — это пятисимвольный код ошибки, который несёт каждая ошибка PostgreSQL.

Когда нужен: финансовая аналитика, отчёты, агрегации — всё, где важна консистентная картина на момент начала запроса.

### SERIALIZABLE — полная изоляция через SSI

```sql
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

PostgreSQL реализует `SERIALIZABLE` через SSI, то есть Serializable Snapshot Isolation. Он обходится без традиционных блокировок чтения, потому что они убивают параллелизм. Вместо этого он отслеживает зависимости чтения и записи между транзакциями.

Иногда совместный результат двух конкурентных транзакций не совпадает ни с одним последовательным порядком этих же транзакций. PostgreSQL это замечает и роняет одну из них:

```txt
ERROR:  could not serialize access due to read/write dependencies
        among transactions
HINT:   The transaction might succeed if retried.
```

Так о себе сообщает проверка SSI, и выдать это сообщение может только `SERIALIZABLE`. При этом транзакция на `SERIALIZABLE` может получить и ошибку «concurrent update» выше. Правило «первый писатель побеждает» из `REPEATABLE READ` работает и здесь.

У обоих сообщений SQLSTATE равен 40001. Приложение **обязано** перехватывать этот код и повторять транзакцию.

Когда нужен: банковские операции с балансами и лимитами, биллинг и любой случай, где write-skew anomaly может нарушить бизнес-инвариант.

## Write-Skew Anomaly — аномалия, которую не видят REPEATABLE READ

```sql
-- Пример: два врача не могут одновременно уйти "на дежурство" —
-- хотя бы один должен быть в клинике

-- Транзакция A (Врач 1 уходит)
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM doctors WHERE on_call = true;  -- → 2
-- "Есть кому остаться"
UPDATE doctors SET on_call = false WHERE id = 1;
COMMIT;

-- Транзакция B (Врач 2 уходит, конкурентно с A)
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT COUNT(*) FROM doctors WHERE on_call = true;  -- → 2 (тот же снапшот!)
-- "Есть кому остаться"
UPDATE doctors SET on_call = false WHERE id = 2;
COMMIT;

-- Итог: оба ушли, в клинике никого. Это write-skew.
-- SERIALIZABLE обнаружит конфликт и откатит одну транзакцию.
```

Write-skew — это класс аномалий, где каждая транзакция по отдельности не нарушает инвариант, а вместе они его нарушают. `REPEATABLE READ` предотвращает non-repeatable read и phantom read, но **не** write-skew: каждая транзакция действительно видела корректный снапшот.

## Как установить уровень изоляции в приложении

```ts
// Prisma — уровень изоляции на уровне транзакции
await prisma.$transaction(
  async (tx) => {
    const total = await tx.account.aggregate({ _sum: { balance: true } });
    // Весь отчёт строится на основе консистентного снапшота
    await tx.report.create({ data: { total: total._sum.balance } });
  },
  { isolationLevel: Prisma.TransactionIsolationLevel.RepeatableRead }
);

// Serializable — для критических финансовых операций
await prisma.$transaction(
  async (tx) => { /* ... */ },
  { isolationLevel: Prisma.TransactionIsolationLevel.Serializable }
);
```

```sql
-- raw SQL
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
-- или
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
-- (до первого оператора в транзакции)
```

## Связь с другими темами

- [ACID и транзакции](./02-acid-transactions.md) — I (изоляция) как один из четырёх принципов ACID: атомарность, консистентность, изоляция, устойчивость.
- [MVCC, блокировки и VACUUM](./05-mvcc-locks-vacuum.md) — механизм MVCC, за счёт которого PostgreSQL строит снапшоты без блокировок чтения.
- [Планировщик запросов и EXPLAIN](./06-query-planner-explain.md) — уровень изоляции влияет на выбор планировщика в редких случаях.

## Типичные ошибки на интервью

- **"`READ UNCOMMITTED` позволяет читать незакоммиченные данные в PostgreSQL"** — не позволяет. PostgreSQL реализует `READ UNCOMMITTED` как `READ COMMITTED`, а dirty read физически невозможен из-за MVCC.

- **"`REPEATABLE READ` и `SERIALIZABLE` — одно и то же, просто разные названия"** — это не так. Write-skew anomaly — целый класс аномалий, который `REPEATABLE READ` допускает, а `SERIALIZABLE` запрещает.

- **"`SERIALIZABLE` блокирует все другие транзакции"** — он не блокирует ничего. PostgreSQL реализует его через SSI, а SSI отслеживает зависимости вместо явных блокировок чтения. Параллелизм сохраняется, а цена — ошибки сериализации, которые надо повторять.

- **"Уровень изоляции по умолчанию — `SERIALIZABLE`, это самый безопасный"** — по умолчанию стоит `READ COMMITTED`. `SERIALIZABLE` нужно запрашивать явно, и он требует логики повтора в приложении.

- **"Phantom read невозможен в `REPEATABLE READ` по стандарту SQL"** — стандарт как раз допускает его на этом уровне. PostgreSQL даёт более сильную гарантию через снапшот MVCC, но это особенность реализации, а не требование стандарта.
