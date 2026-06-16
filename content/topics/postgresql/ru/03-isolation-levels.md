<!-- verified: 2026-06-05, corrections: 0 -->
# Transaction Isolation Levels

## Зачем нужны уровни изоляции — и почему "полная изоляция" стоит дорого

Когда несколько транзакций работают конкурентно, возникает вопрос: **какие данные видит каждая транзакция?** Теоретически правильный ответ — "только те, что были бы видны при строго последовательном выполнении". Но это требует блокировок на каждую операцию, что убивает параллелизм.

Уровни изоляции — это компромисс между строгостью гарантий и производительностью. SQL-стандарт определяет 4 уровня через список **аномалий**, которые каждый уровень запрещает.

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

```txt
PostgreSQL: НЕ поддерживает Dirty Read ни на каком уровне изоляции
(включая READ UNCOMMITTED). Реализовано через MVCC (см.
[MVCC, Locks, and Vacuum]) — читатель видит только версии строк,
помеченные как committed.
```

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

```txt
Почему это проблема: транзакция A возможно использовала первое
значение (100) для принятия бизнес-решений — и теперь второй
SELECT противоречит первому внутри одной логической операции.
```

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

```txt
Отличие от Non-Repeatable Read: там ИЗМЕНЯЕТСЯ существующая строка,
здесь ПОЯВЛЯЮТСЯ новые строки (или исчезают). В REPEATABLE READ
PostgreSQL благодаря MVCC-снапшоту фактически защищает и от Phantom
Read (в отличие от стандартного Repeatable Read, который защищает
только от Non-Repeatable Read).
```

### Serialization Anomaly — результат не соответствует ни одному последовательному порядку

```sql
-- Транзакция A                  -- Транзакция B
BEGIN;                            BEGIN;
SELECT SUM(balance)               SELECT SUM(balance)
FROM accounts;  -- → 1000        FROM accounts;  -- → 1000

INSERT INTO audit                 INSERT INTO audit
VALUES ('sum=1000');              VALUES ('sum=1000');

COMMIT;                           COMMIT;
-- Итог: обе прочитали одно и то же значение и записали одно и то же.
-- При последовательном выполнении — одна из них прочитала бы уже изменённую сумму.
-- Это Serialization Anomaly — фиксируется только SERIALIZABLE.
```

## Четыре уровня изоляции PostgreSQL — что реально происходит

```txt
┌─────────────────────┬──────────────┬───────────────────┬───────────────┬───────────────────────┐
│ Уровень             │ Dirty Read   │ Non-Repeatable    │ Phantom Read  │ Serialization Anomaly │
│                     │              │ Read              │               │                       │
├─────────────────────┼──────────────┼───────────────────┼───────────────┼───────────────────────┤
│ READ UNCOMMITTED    │ невозможен*  │ возможен          │ возможен      │ возможен              │
│ READ COMMITTED      │ невозможен   │ возможен          │ возможен      │ возможен              │
│ REPEATABLE READ     │ невозможен   │ невозможен        │ невозможен*   │ возможен              │
│ SERIALIZABLE        │ невозможен   │ невозможен        │ невозможен    │ невозможен            │
└─────────────────────┴──────────────┴───────────────────┴───────────────┴───────────────────────┘

(*) PostgreSQL реализует READ UNCOMMITTED как READ COMMITTED.
(*) PostgreSQL REPEATABLE READ защищает от Phantom Read (бонус MVCC).
```

### READ COMMITTED — уровень по умолчанию, наиболее распространённый

```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED; -- или просто BEGIN (это дефолт)
```

```txt
Снапшот создаётся на момент КАЖДОГО ОПЕРАТОРА (statement-level snapshot).
Это означает:
  - SELECT #1 видит все коммиты ДО SELECT #1
  - SELECT #2 (позднее в той же транзакции) видит все коммиты ДО SELECT #2
    (включая те, что произошли между SELECT #1 и SELECT #2)

Это источник Non-Repeatable Read.

Типичный use case: 90%+ CRUD-приложений. Достаточно для большинства
операций, где не нужна консистентная картина данных на протяжении
всей транзакции.
```

### REPEATABLE READ — снапшот на момент BEGIN

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

```txt
Снапшот создаётся ОДИН РАЗ — на момент первого оператора в транзакции
(в PostgreSQL — в момент BEGIN или первого SELECT, в зависимости от
контекста). Все последующие SELECT в транзакции видят этот снапшот,
независимо от новых коммитов других транзакций.

PostgreSQL-специфика: благодаря реализации через MVCC (а не через
диапазонные блокировки, как в Oracle), REPEATABLE READ также
защищает от Phantom Read — строки, вставленные другой транзакцией
после создания снапшота, не видны.

Когда нужен: финансовая аналитика, отчёты, агрегации, где важна
консистентная картина на момент начала запроса.
```

### SERIALIZABLE — полная изоляция через SSI

```sql
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

```txt
PostgreSQL реализует SERIALIZABLE через SSI (Serializable Snapshot
Isolation) — не через традиционные блокировки чтения (которые убивают
параллелизм), а через отслеживание зависимостей между транзакциями
(read/write dependencies).

Если PostgreSQL обнаруживает, что результат конкурентного выполнения
двух транзакций не эквивалентен ни одному последовательному порядку
их выполнения — одна транзакция завершается ошибкой:
ERROR: could not serialize access due to concurrent update

Приложение ДОЛЖНО перехватывать SQLSTATE 40001 и повторять транзакцию.

Когда нужен: банковские операции с балансами/лимитами, биллинг,
ситуации где write-skew anomaly может привести к нарушению бизнес-инвариантов.
```

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
SELECT COUNT(*) FROM doctors WHERE on_call = true;  -- → 2 (читает тот же снапшот!)
-- "Есть кому остаться"
UPDATE doctors SET on_call = false WHERE id = 2;
COMMIT;

-- Итог: оба ушли, в клинике никого. Это write-skew.
-- SERIALIZABLE обнаружит конфликт и откатит одну транзакцию.
```

```txt
Write-Skew — это класс аномалий, при которых каждая транзакция
по отдельности не нарушает инвариант, но их совместное выполнение
нарушает. REPEATABLE READ предотвращает non-repeatable read и phantom
read, но НЕ write-skew (каждая транзакция видела корректный снапшот).
```

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

```txt
[ACID and Transactions]         — I (Isolation) как один из четырёх
                                   принципов ACID
[MVCC, Locks, and Vacuum]       — механизм MVCC, за счёт которого
                                   PostgreSQL реализует снапшоты без
                                   блокировок чтения
[Query Planner and EXPLAIN]     — уровень изоляции влияет на
                                   выбор планировщика в edge cases
```

## Типичные ошибки на интервью

- **"READ UNCOMMITTED позволяет читать незакоммиченные данные в PostgreSQL"** — PostgreSQL реализует READ UNCOMMITTED как READ COMMITTED; dirty reads физически невозможны из-за MVCC.

- **"REPEATABLE READ и SERIALIZABLE — одно и то же, просто разные названия"** — не объяснять Write-Skew Anomaly как класс аномалий, который REPEATABLE READ допускает, а SERIALIZABLE — нет.

- **"SERIALIZABLE блокирует все другие транзакции"** — PostgreSQL реализует SERIALIZABLE через SSI (отслеживание зависимостей), а не через явные блокировки чтения; параллелизм сохраняется, ценой возможных серийных ошибок.

- **"Уровень изоляции по умолчанию — SERIALIZABLE, это самый безопасный"** — по умолчанию READ COMMITTED; SERIALIZABLE требует явного указания и повторной логики в приложении.

- **"Phantom Read невозможен в REPEATABLE READ в стандарте SQL"** — стандарт допускает Phantom Read на уровне REPEATABLE READ; PostgreSQL даёт более сильную гарантию (MVCC-снапшот), но это специфика реализации, а не требование стандарта.
