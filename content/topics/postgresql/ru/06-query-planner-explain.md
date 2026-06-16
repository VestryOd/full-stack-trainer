<!-- verified: 2026-06-05, corrections: 0 -->
# Query Planner и EXPLAIN ANALYZE

## Планировщик — наиболее сложная часть PostgreSQL, от которой зависит разница между 5 мс и 5 минут

SQL — декларативный язык: вы описываете **что** хотите получить, а не **как**. Задача планировщика (Planner/Optimizer) — преобразовать декларативное "что" в конкретный план выполнения: какие индексы использовать, в каком порядке обходить таблицы, какой алгоритм JOIN применить.

```txt
SQL-текст
    │  Parser: AST
    ↓
Query Tree
    │  Rewriter: VIEW expansion, RLS
    ↓
Logical Plan
    │  Planner: перебор планов, оценка стоимости каждого
    ↓
Best Physical Plan
    │  Executor: выполнение
    ↓
Результат
```

## Модель стоимости (Cost Model) — что именно оценивает Planner

```txt
PostgreSQL Planner — cost-based optimizer. Он не знает точного
времени выполнения, но оценивает "стоимость" каждого плана в
условных единицах:

  seq_page_cost     = 1.0    (стоимость чтения одной страницы
                              при Sequential Scan — базовая единица)
  random_page_cost  = 4.0    (стоимость случайного доступа к странице —
                              Index Scan делает random I/O)
  cpu_tuple_cost    = 0.01   (обработка одной строки)
  cpu_index_tuple_cost = 0.005
  cpu_operator_cost = 0.0025

Стоимость плана = сумма всех I/O и CPU операций по этим параметрам.
Planner выбирает план с МИНИМАЛЬНОЙ оценочной стоимостью.
```

```txt
Почему random_page_cost = 4.0 по умолчанию, но часто нужно уменьшить:
  HDD: случайный I/O дороже последовательного в 10-100x → 4.0 оправдан
  SSD: случайный I/O дороже последовательного в ~2x → нужно снизить до 1.1-2.0
  
  ALTER SYSTEM SET random_page_cost = 1.1;  -- для SSD/NVMe
  SELECT pg_reload_conf();
  
  Без этой настройки на SSD-сервере PostgreSQL будет ИЗБЕГАТЬ Index
  Scan в пользу Seq Scan, считая index access "дорогим".
```

## Методы доступа к данным — что выбирает Planner

```sql
EXPLAIN SELECT * FROM users WHERE email = 'max@test.com';
```

```txt
Sequential Scan (Seq Scan):
  Читает ВСЕ страницы таблицы подряд (sequential I/O — быстро).
  Когда используется:
    - нет индекса на столбец
    - индекс есть, но selectivity низкая (много строк совпадает)
    - таблица маленькая (индекс medленнее из-за overhead)
    - после масштабного UPDATE (table bloat → много пустых страниц)
  Стоимость: O(n) = seq_page_cost × N_pages + cpu_tuple_cost × N_rows

Index Scan:
  1. Обход B-Tree: O(log N)
  2. Для каждого найденного ключа: random I/O в heap (ctid → строка)
  Когда используется: высокая selectivity (мало строк совпадает)
  Стоимость: O(log N + K × random_page_cost), где K = кол-во строк

Bitmap Index Scan + Bitmap Heap Scan:
  1. Сначала: обход индекса, строится in-memory bitmap (set page numbers)
  2. Потом: страницы heap читаются В ПОРЯДКЕ (sequential I/O!)
  Когда используется: средняя selectivity (много строк, но не все)
  Advantage vs Index Scan: re-sort pages → sequential I/O вместо random
  Стоимость: между Seq Scan и Index Scan

Index Only Scan:
  Все нужные данные в индексе (key + INCLUDE столбцы).
  Heap может НЕ читаться (если Visibility Map говорит "all-visible").
  Самый быстрый вариант для covering indexes.
```

## Алгоритмы JOIN — три принципиально разных подхода

```txt
Nested Loop Join:
  FOR EACH row IN outer_table:
    FOR EACH row IN inner_table WHERE join_condition:
      output
  Стоимость: O(N × M) — хорошо только для малых таблиц
  Или: O(N × log M) если на inner_table есть индекс
  Когда: маленький outer result set, есть индекс на inner

Hash Join:
  1. Build phase: строит hash table из МЕНЬШЕЙ таблицы
  2. Probe phase: FOR EACH row IN larger_table → lookup in hash table
  Стоимость: O(N + M) — отлично для больших таблиц без индекса
  Ограничение: hash table должен влезть в work_mem
  Когда: large non-indexed joins, equality conditions (=)

Merge Join:
  Обе таблицы отсортированы по ключу JOIN → один проход O(N + M)
  Стоимость: O(N×log N + M×log M) если нужна сортировка,
             O(N + M) если уже отсортированы (sorted index)
  Когда: обе таблицы большие, есть индекс или ORDERED BY
```

## EXPLAIN и EXPLAIN ANALYZE — читаем вывод

```sql
EXPLAIN ANALYZE BUFFERS
SELECT u.id, u.email, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.email
ORDER BY order_count DESC
LIMIT 10;
```

```txt
Пример вывода (упрощённо):
 Limit  (cost=1245.67..1245.70 rows=10 width=40)
        (actual time=23.456..23.458 rows=10 loops=1)
   ->  Sort  (cost=1245.67..1248.17 rows=1000 width=40)
             (actual time=23.454..23.455 rows=10 loops=1)
         Sort Key: count(o.id) DESC
         Sort Method: top-N heapsort  Memory: 26kB
         ->  HashAggregate  (cost=...)
               (actual time=22.1..22.8 rows=1000 loops=1)
               ->  Hash Left Join  (cost=...)
                     Hash Cond: (o.user_id = u.id)
                     ->  Index Scan using idx_users_created
                           on users u
                           Index Cond: (created_at > '2024-01-01')
                           (actual time=0.08..5.2 rows=5000 loops=1)
                     ->  Hash  (cost=...)
                           Buckets: 32768  Batches: 1  Memory Usage: 1024kB
                           ->  Seq Scan on orders o
                               (actual time=0.02..8.3 rows=85000 loops=1)
 Planning Time: 1.2 ms
 Execution Time: 23.5 ms
```

```txt
Ключевые метрики для анализа:

1. cost=start..total:
   - start cost: время до первой строки (важно для LIMIT)
   - total cost: оценочная полная стоимость
   Если actual rows сильно отличается от estimated rows → плохая
   статистика → нужен ANALYZE

2. actual time=X..Y rows=Z loops=N:
   - X: время до первой строки
   - Y: время до последней строки
   - Z: фактически возвращено строк
   - loops=N: узел выполнялся N раз (важно для Nested Loop inner)
   Реальное время = Y × N

3. Buffers (с BUFFERS):
   - shared hit=X: прочитано страниц из shared_buffers (RAM) — быстро
   - shared read=Y: прочитано страниц с диска — медленно
   Высокое shared read → не влезает в кэш или нет кэша

4. КРАСНЫЕ ФЛАГИ в EXPLAIN ANALYZE:
   - Seq Scan на большой таблице с WHERE → нужен индекс
   - estimated rows << actual rows (rows=1000 vs actual=100000)
     → устаревшая статистика → ANALYZE
   - Nested Loop с loops=10000 → 10000 обращений к inner → нужен индекс
   - Sort Method: external merge Disk → work_mem слишком мал
     (SET work_mem = '256MB' для тяжёлых аналитических запросов)
```

## Типичные причины медленных запросов и диагностика

```sql
-- 1. Нет индекса / не тот индекс
EXPLAIN ANALYZE SELECT * FROM orders WHERE status = 'pending' AND user_id = 42;
-- Если Seq Scan: добавить индекс (user_id, status) или (status, user_id)

-- 2. Устаревшая статистика
ANALYZE orders;  -- обновить статистику
-- Или проверить: SELECT * FROM pg_stat_user_tables WHERE relname = 'orders';
-- n_dead_tup большой → нужен VACUUM

-- 3. Неверный join order / hash join без памяти
SET work_mem = '256MB';  -- для сессии (не globally!)
EXPLAIN ANALYZE ...;     -- повторить и сравнить план

-- 4. Функция в WHERE ломает использование индекса
-- ПЛОХО: WHERE LOWER(email) = 'max@test.com' — не использует idx_users_email
-- ХОРОШО: создать функциональный индекс
CREATE INDEX idx_users_email_lower ON users (LOWER(email));

-- 5. Implicit cast ломает индекс
-- Если user_id типа BIGINT, а передаётся VARCHAR:
WHERE user_id = '42'  -- implicit cast VARCHAR→BIGINT → индекс обычно не используется
-- Исправление: передавать правильный тип
WHERE user_id = 42
```

## pg_stat_statements — мониторинг медленных запросов в production

```sql
-- Включить расширение (в postgresql.conf):
-- shared_preload_libraries = 'pg_stat_statements'

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Топ-10 самых дорогих запросов
SELECT
  round(total_exec_time::numeric, 2) AS total_ms,
  calls,
  round(mean_exec_time::numeric, 2)  AS avg_ms,
  round((100 * total_exec_time / sum(total_exec_time) OVER ())::numeric, 1) AS pct,
  left(query, 100) AS query_snippet
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

## Связь с другими темами

```txt
[Indexes and Internals]       — типы индексов и когда Planner
                                 их выбирает; selectivity и Left
                                 Prefix Rule
[MVCC, Locks, and Vacuum]     — autovacuum/ANALYZE обновляет
                                 статистику для Planner; HOT Update
                                 и его влияние на планы
[Isolation Levels]            — уровень изоляции влияет на снапшот,
                                 используемый при планировании
                                 (редко, но важно для edge cases)
```

## Типичные ошибки на интервью

- **"EXPLAIN показывает реальное время выполнения"** — EXPLAIN без ANALYZE показывает только ОЦЕНОЧНУЮ стоимость (cost) без реального выполнения. Только EXPLAIN ANALYZE реально выполняет запрос и показывает фактическое время и строки.

- **"Planner всегда выбирает правильный план"** — Planner ошибается при устаревшей статистике (actual rows >> estimated rows в EXPLAIN ANALYZE), при нестандартном распределении данных (частые значения в non-uniform columns), при correlation = 0 (случайный порядок строк).

- **"Index Scan всегда быстрее Seq Scan"** — Seq Scan может быть быстрее при низкой selectivity (возвращает много строк), на SSD где random vs sequential I/O разница невелика, и всегда быстрее для маленьких таблиц.

- **"random_page_cost всегда должен оставаться 4.0"** — это значение оптимально для HDD. На SSD нужно снизить до 1.1-2.0, иначе Planner будет избегать Index Scan.

- **"work_mem — глобальная настройка для всего сервера"** — work_mem выделяется ПЕР-ОПЕРАЦИИ (sort, hash) и ПЕР-СОЕДИНЕНИЮ. SET work_mem = '1GB' при 100 конкурентных соединениях = потенциальные 100 ГБ RAM. Правильно: SET work_mem локально в сессии для тяжёлых аналитических запросов.
