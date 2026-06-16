<!-- verified: 2026-06-05, corrections: 0 -->
# MVCC, Locks и VACUUM

## MVCC — фундаментальный механизм PostgreSQL, объясняющий почему "читатели не блокируют писателей"

Наивное решение конкурентного доступа — блокировки: Reader берёт shared lock, Writer ждёт; Writer берёт exclusive lock, все Readers ждут. Это работает, но превращается в узкое место под нагрузкой.

PostgreSQL решает это через **MVCC (Multi-Version Concurrency Control)**: вместо блокировки строки при чтении — хранить несколько версий одной строки одновременно. Каждая транзакция видит консистентный "снапшот" данных на момент своего старта, не блокируя других.

## Как UPDATE на самом деле работает — не "перезапись", а "создание новой версии"

```sql
UPDATE accounts SET balance = 200 WHERE id = 1;
```

```txt
Что ПРОИСХОДИТ ФИЗИЧЕСКИ:
  1. Старая строка (balance=100) НЕ УДАЛЯЕТСЯ. В её xmax
     записывается Transaction ID (XID) текущей транзакции.
  2. В heap вставляется НОВАЯ строка (balance=200) с xmin =
     XID текущей транзакции.
  3. При COMMIT: новая версия становится "видимой" для
     транзакций, стартовавших после COMMIT.
  4. Старая версия (xmax != 0) становится "мёртвой" — dead tuple.

Heap-файл после UPDATE (упрощённо):
  ┌──────────────────────────────┐
  │ xmin=100, xmax=200, bal=100  │  ← dead tuple (xmax заполнен)
  ├──────────────────────────────┤
  │ xmin=200, xmax=0,   bal=200  │  ← live tuple (xmax=0 → живой)
  └──────────────────────────────┘
```

```txt
Ключевые поля каждого tuple в heap:
  xmin  — XID транзакции, создавшей строку (INSERT или UPDATE)
  xmax  — XID транзакции, "удалившей" строку (DELETE или UPDATE-old)
          0 = строка живая (не удалена)
  infomask — битовые флаги (committed, aborted и т.д.)
  ctid  — указатель на самую свежую версию строки
          (UPDATE-цепочка: ctid старой → новая версия)
```

## Снапшот транзакции — как PostgreSQL решает "что видно?"

```txt
При старте транзакции (в момент первого оператора для READ
COMMITTED, в момент BEGIN для REPEATABLE READ) PostgreSQL
создаёт снапшот, содержащий:

  xmin   — минимальный активный XID в момент снапшота
  xmax   — следующий XID, который будет выдан
  xip    — список активных (незавершённых) транзакций

Строка ВИДИМА для транзакции, если:
  1. xmin < snapshot.xmin  (создана до снапшота)
     ИЛИ xmin входит в "завершённые до снапшота"
     (через pg_clog/pg_xact — commit log)
  2. xmax = 0 ИЛИ xmax относится к aborted транзакции
     ИЛИ xmax >= snapshot.xmax (создана после снапшота)

Это объясняет поведение уровней изоляции:
  READ COMMITTED:   снапшот обновляется на каждый оператор
  REPEATABLE READ:  снапшот создаётся один раз на транзакцию
```

## HOT Update — оптимизация для частых UPDATE одной строки

```txt
Обычный UPDATE: новая версия строки → в неё нужно обновить
ВСЕ индексы (новый ctid). Это дорого при множестве индексов.

HOT (Heap-Only Tuple) Update: если:
  1. Новая версия влезает на ту же heap-страницу, что и старая
  2. Обновляемый столбец НЕ индексирован

...то PostgreSQL создаёт цепочку внутри страницы:
  ctid старой строки → ctid новой строки (на той же странице)

Индексы НЕ обновляются — они по-прежнему указывают на старую
строку, а из неё PostgreSQL проходит по HOT-цепочке к актуальной
версии. Экономия: нет page split в индексах, меньше WAL, быстрее.

Практическое следствие: fillfactor < 100 для таблиц с частыми
UPDATE позволяет HOT Update резервировать свободное место на
странице для новых версий:
  ALTER TABLE accounts SET (fillfactor = 70);
  -- 30% каждой страницы зарезервировано для HOT Updates
```

## Dead Tuples и Table Bloat — почему таблицы "пухнут"

```txt
Каждый UPDATE и DELETE оставляют dead tuples:
  - UPDATE: старая версия строки с заполненным xmax
  - DELETE: единственная версия строки с заполненным xmax

Dead tuples занимают дисковое место и "загрязняют" страницы:
  SELECT *  → PostgreSQL читает страницу → видит dead tuple →
  проверяет видимость → tuple не виден → пропускает.
  Лишнее I/O при каждом Seq Scan.

Table bloat: после интенсивного UPDATE/DELETE таблица может
занимать в 5-10 раз больше места, чем содержит "живых" данных.
Это также означает, что индексы имеют "дыры" (dead index entries).
```

## VACUUM — механизм очистки dead tuples

```sql
-- Ручной запуск (обычно не нужен при настроенном autovacuum)
VACUUM users;

-- Со статистикой
VACUUM VERBOSE ANALYZE users;
```

```txt
Что делает VACUUM:
  1. Сканирует таблицу, ищет dead tuples
  2. Помечает их пространство как "свободное" (в FSM —
     Free Space Map) для повторного использования новыми строками
  3. Удаляет dead index entries (для каждого индекса таблицы)
  4. Обновляет Visibility Map (страницы, где все tuples "all-visible"
     → позволяет Index-Only Scan)
  5. Обновляет pg_class.relpages / reltuples (статистику для Planner)

Чего VACUUM НЕ делает:
  - НЕ возвращает освобождённое место ОС (страницы остаются в
    файле, просто помечаются как доступные для reuse)
  - НЕ дефрагментирует данные внутри страниц

VACUUM не берёт ACCESS EXCLUSIVE LOCK → можно запускать конкурентно
с обычными SELECT/INSERT/UPDATE/DELETE (берёт только ShareUpdateExclusiveLock).
```

## VACUUM FULL — радикальное средство от bloat

```sql
VACUUM FULL users;
-- Аналог: CLUSTER users USING idx_users_pk (с сортировкой)
```

```txt
VACUUM FULL:
  1. Перестраивает таблицу с нуля (CREATE TABLE ... AS SELECT live tuples)
  2. Перестраивает все индексы
  3. Возвращает освобождённое место ОС (файл уменьшается)

Цена: берёт ACCESS EXCLUSIVE LOCK на таблицу → ВСЕ запросы к таблице
блокируются на всё время выполнения. Для таблицы 100 ГБ — часы.

Альтернатива для production: pg_repack (расширение, которое делает
то же самое без долгой блокировки через временную таблицу + триггеры).
```

## Autovacuum — как настроить и почему нельзя отключать

```txt
autovacuum_vacuum_threshold    = 50      -- мин. количество dead tuples
autovacuum_vacuum_scale_factor = 0.2     -- + 20% от количества строк

Autovacuum запускается когда:
  dead_tuples > threshold + scale_factor * reltuples

Для таблицы с 1 000 000 строк: порог = 50 + 0.2 * 1 000 000 = 200 050 dead tuples.
При высоком UPDATE-rate это означает большой bloat до первого autovacuum.
```

```sql
-- Тюнинг autovacuum для горячих таблиц (много UPDATE/DELETE)
ALTER TABLE orders SET (
  autovacuum_vacuum_scale_factor = 0.01,  -- запускать раньше: 1% вместо 20%
  autovacuum_vacuum_threshold    = 100,   -- и меньший минимальный порог
  autovacuum_analyze_scale_factor = 0.005 -- обновлять статистику чаще
);
```

```txt
Почему нельзя отключать autovacuum (autovacuum = off):
  1. Table bloat → деградация производительности Seq Scan
  2. Index bloat → деградация Index Scan
  3. XID Wraparound (критическая ситуация): PostgreSQL использует
     32-битный XID (счётчик транзакций). После 2^32 ≈ 4 млрд
     транзакций происходит wraparound. VACUUM "замораживает"
     старые XID (обнуляет xmin для очень старых строк). Без
     VACUUM → PostgreSQL shutdown при достижении "опасного порога"
     с сообщением "database is not accepting commands to avoid
     wraparound data loss"
```

## Locks — когда MVCC недостаточно

```sql
-- Оптимистичный подход (MVCC): две транзакции читают, потом UPDATE
-- Проблема: race condition при "check-then-act"
BEGIN;
SELECT balance FROM accounts WHERE id = 1;  -- читаем 100
-- Другая транзакция тоже прочитала 100 и делает UPDATE...
UPDATE accounts SET balance = balance - 50 WHERE id = 1;
COMMIT;

-- Пессимистичный подход: явная блокировка строки
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;
-- Теперь другие транзакции, пытающиеся делать SELECT ... FOR UPDATE
-- на эту строку, ЖДУТ до COMMIT/ROLLBACK
UPDATE accounts SET balance = balance - 50 WHERE id = 1;
COMMIT;
```

```sql
-- FOR UPDATE NOWAIT — немедленная ошибка вместо ожидания
SELECT * FROM orders WHERE id = 1 FOR UPDATE NOWAIT;
-- ERROR: could not obtain lock on row in relation "orders"

-- FOR UPDATE SKIP LOCKED — пропустить заблокированные строки
-- (паттерн для очередей задач: каждый worker берёт "свою" задачу)
SELECT * FROM tasks WHERE status = 'pending'
ORDER BY created_at
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

```txt
Уровни блокировок таблицы (от мягкого к жёсткому):
  AccessShareLock         — SELECT (берётся автоматически)
  RowShareLock            — SELECT ... FOR UPDATE
  RowExclusiveLock        — INSERT/UPDATE/DELETE
  ShareUpdateExclusiveLock — VACUUM, CREATE INDEX CONCURRENTLY
  ShareLock               — CREATE INDEX (non-concurrent)
  ExclusiveLock           — REFRESH MATERIALIZED VIEW CONCURRENTLY
  AccessExclusiveLock     — ALTER TABLE, VACUUM FULL, DROP TABLE
                           (блокирует ВСЁ, включая SELECT)

DDL-операции в production нужно делать с осторожностью — ALTER TABLE
берёт AccessExclusiveLock → блокирует все запросы к таблице.
```

## Связь с другими темами

```txt
[ACID and Transactions]       — как WAL обеспечивает Durability и
                                 Atomicity; deadlock как частный
                                 случай конкурентности
[Isolation Levels]            — снапшоты MVCC как основа
                                 READ COMMITTED / REPEATABLE READ
[Indexes and Internals]       — dead tuples в индексах, HOT Update
                                 как оптимизация, Index-Only Scan
                                 и Visibility Map
[Query Planner and EXPLAIN]   — устаревшая статистика из-за
                                 пропущенного ANALYZE → неверные планы
```

## Типичные ошибки на интервью

- **"UPDATE изменяет строку на месте"** — в PostgreSQL UPDATE создаёт новую версию строки (new tuple) и помечает старую как мёртвую через xmax. Старая версия остаётся в heap до VACUUM.

- **"MVCC полностью устраняет блокировки"** — MVCC устраняет блокировки чтения ("читатели не блокируют писателей"), но не устраняет блокировки записи на уровне строки (два конкурентных UPDATE одной строки — второй ждёт первого).

- **"VACUUM уменьшает размер файла таблицы"** — VACUUM только помечает место dead tuples как доступное для reuse. Физический размер файла уменьшает только VACUUM FULL (с ACCESS EXCLUSIVE LOCK) или pg_repack.

- **"autovacuum можно отключить, если делать VACUUM вручную"** — риск XID Wraparound: без регулярного "замораживания" старых XID PostgreSQL вынужден аварийно остановить приём запросов для защиты от потери данных.

- **"SELECT ... FOR UPDATE нужен для всех транзакций при чтении"** — FOR UPDATE нужен только при паттерне "check-then-act" (прочитал, проверил условие, обновил), где race condition может нарушить бизнес-инвариант. Для обычного чтения — MVCC достаточно.
