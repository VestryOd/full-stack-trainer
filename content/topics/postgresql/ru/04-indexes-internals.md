<!-- verified: 2026-06-05, corrections: 0 -->
# Indexes and Internals

## Индекс — отдельная структура данных, торгующая пространством и скоростью записи на скорость чтения

Без индекса `WHERE email = 'max@test.com'` на таблице из 10M строк — это Sequential Scan: PostgreSQL читает ВСЕ страницы heap-файла (8 КБ каждая) и проверяет каждую строку. Сложность O(n).

Индекс — отдельная структура, хранящая отображение значений столбца → физическое расположение строк (page + offset). Стоимость: дополнительное дисковое пространство + overhead на каждую запись (INSERT/UPDATE/DELETE должны обновлять структуру индекса).

## B-Tree — индекс по умолчанию, и почему он работает для большинства задач

```txt
B-Tree (Balanced Tree) — сбалансированное дерево, где:
  - каждый узел содержит упорядоченные ключи и указатели на
    дочерние узлы (или heap-строки на листьях)
  - все листовые узлы — на одной глубине (дерево сбалансировано)
  - листья связаны между собой (двусвязный список) → эффективны
    range-запросы (BETWEEN, <, >)

           [50]
         /      \
     [25]        [75]
    /    \      /    \
[10,20] [30,40] [60,70] [80,90]
```

```txt
Высота B-Tree при 1 000 000 строк ≈ log₁₀₀(1 000 000) ≈ 3 уровня
(PostgreSQL B-Tree узлы хранят сотни ключей, не двоичное дерево).
Реальный поиск: 3-4 I/O операции vs 10 000+ страниц для Seq Scan.

B-Tree поддерживает: =, <, <=, >, >=, BETWEEN, LIKE 'prefix%',
IS NULL, ORDER BY (sorted index → sort можно пропустить).
Не поддерживает: LIKE '%suffix', полнотекстовый поиск, операторы @>.
```

## Внутренности: как PostgreSQL хранит данные и индексы на диске

```txt
Heap file (таблица):
  ┌───────────┬───────────┬───────────┐
  │  Page 0   │  Page 1   │  Page 2   │  ← страницы по 8 КБ
  │ (8192 B)  │ (8192 B)  │ (8192 B)  │
  └───────────┴───────────┴───────────┘

Каждая страница содержит:
  - PageHeader (24 байта)
  - ItemIdData (массив указателей на строки)
  - Free space (пустое место для новых строк)
  - Tuple data (сами строки — tuples)

Каждая строка (tuple) содержит:
  - HeapTupleHeader (23 байта): xmin, xmax (для MVCC),
    natts, infomask...
  - Данные столбцов

Индекс (B-Tree файл):
  - такие же 8-КБ страницы, но внутри — B-Tree узлы
  - листовые страницы B-Tree хранят (key_value, ctid),
    где ctid = (page_number, item_offset) — физическое
    расположение строки в heap
```

## Composite Index и Left Prefix Rule — самый частый вопрос на интервью

```sql
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
```

```txt
Составной индекс хранит ключи как (user_id, status) — ОТСОРТИРОВАННЫЕ
сначала по user_id, потом по status внутри одного user_id.

Индекс РАБОТАЕТ для:
  WHERE user_id = 5                        ← только левый префикс
  WHERE user_id = 5 AND status = 'paid'    ← оба поля
  WHERE user_id = 5 AND status > 'paid'    ← range на правом поле
  ORDER BY user_id, status                 ← сортировка

Индекс НЕ РАБОТАЕТ эффективно для:
  WHERE status = 'paid'                    ← правый столбец без левого
    (PostgreSQL может сделать Index Scan с фильтром, но
    эффективность падает до O(n) — нужно просмотреть весь индекс)

Почему: данные в индексе отсортированы по (user_id, status). Без
фиксации user_id = X нельзя "прыгнуть" к нужному status — он
разбросан по всему индексу в разных user_id-секциях.
```

```sql
-- Правильный порядок столбцов в составном индексе:
-- 1. Столбцы с equality conditions (=) — первыми
-- 2. Столбцы с range conditions (<, >, BETWEEN) — последними
-- 3. Столбцы только для ORDER BY/GROUP BY — в конце

-- Запрос: WHERE user_id = 5 AND created_at > '2024-01-01'
-- Правильный индекс: (user_id, created_at), НЕ (created_at, user_id)
CREATE INDEX idx ON orders(user_id, created_at);
```

## Partial Index — индексируем только нужное подмножество строк

```sql
-- Индекс только для активных пользователей
CREATE INDEX idx_users_email_active ON users(email)
WHERE is_active = true;

-- Индекс для неоплаченных заказов (предположим, их 5% от всех)
CREATE INDEX idx_orders_pending ON orders(created_at)
WHERE status = 'pending';
```

```txt
Преимущества:
  - Размер индекса = % строк, удовлетворяющих WHERE condition
    (5% неоплаченных → индекс в 20 раз меньше полного)
  - Меньший индекс → быстрее умещается в shared_buffers (RAM-кэш)
  - Запросы с тем же WHERE condition автоматически используют индекс

Ограничение: запрос ДОЛЖЕН содержать то же условие в WHERE
(или более строгое), иначе Planner не сможет использовать partial index.
```

## Covering Index — Index-Only Scan без обращения к heap

```sql
-- Запрос: SELECT id, email FROM users WHERE email = 'max@test.com'
-- Без INCLUDE: Index Scan (нашли строку в индексе → fetch из heap)
CREATE INDEX idx_users_email ON users(email);

-- С INCLUDE: Index-Only Scan (все нужные данные в индексе)
CREATE INDEX idx_users_email_covering ON users(email) INCLUDE (id);
```

```txt
Index-Only Scan работает только если:
  1. Все запрошенные в SELECT столбцы есть в индексе (key + INCLUDE)
  2. Visibility Map показывает, что страница heap "all-visible"
     (все строки на странице видимы всем транзакциям, т.е. VACUUM
     уже обработал страницу)

Без (2) PostgreSQL всё равно ходит в heap для проверки видимости
(MVCC). Свежетаблица с интенсивной записью часто не получит
benefit от Index-Only Scan.
```

## Специализированные типы индексов

```sql
-- GIN (Generalized Inverted Index) — для многозначных типов
-- JSONB, arrays, full-text search (tsvector)
CREATE INDEX idx_products_attrs ON products USING GIN (attributes);
CREATE INDEX idx_articles_search ON articles USING GIN (to_tsvector('english', body));
-- GIN строит инвертированный индекс: значение → множество строк
-- Быстр для @>, ?, ?|, @@; медленнее при записи (перестройка списков)

-- GiST (Generalized Search Tree) — для геометрии, ranges, PostGIS
CREATE INDEX idx_geom ON places USING GIST (location);
CREATE INDEX idx_range ON events USING GIST (during);  -- tstzrange
-- GiST поддерживает: &&, @>, <->, <<, >>...

-- BRIN (Block Range INdex) — для очень больших таблиц с корреляцией
-- Хранит мин/макс значение по диапазонам страниц (blcksz по умолчанию)
CREATE INDEX idx_logs_ts ON logs USING BRIN (created_at);
-- Эффективен когда: физический порядок строк коррелирует с значением
-- (временны́е ряды, append-only таблицы логов)
-- Размер индекса: несколько десятков КБ против десятков ГБ для B-Tree

-- Hash — O(1) для =, но не поддерживает range, не нужен WAL до pg 10
CREATE INDEX idx_users_email_hash ON users USING HASH (email);
-- В большинстве случаев B-Tree быстрее и функциональнее
```

## Когда планировщик НЕ использует индекс — и это правильно

```sql
-- Индекс на is_active (boolean), 99% строк = true
EXPLAIN SELECT * FROM users WHERE is_active = true;
-- → Seq Scan! (Planner оценил: индекс даст 99% строк,
--   Seq Scan дешевле чем 990 000 random I/O через индекс)

-- Индекс на is_active используется если:
EXPLAIN SELECT * FROM users WHERE is_active = false;
-- → Index Scan (1% строк — мало enough для random I/O быть выгоднее)
```

```txt
Планировщик принимает решение на основе статистики (pg_statistic):
  - n_distinct: количество уникальных значений
  - correlation: насколько физический порядок строк совпадает с
    порядком значений индекса (высокая корреляция → Seq Scan выгоднее)
  - most_common_vals / most_common_freqs: частоты значений

ANALYZE обновляет статистику. Устаревшая статистика → неверные планы.
В PostgreSQL 14+ autovacuum запускает ANALYZE автоматически.
```

## Цена индексов при записи — как оценить trade-off

```txt
Каждый индекс добавляет overhead к INSERT/UPDATE/DELETE:
  - INSERT → вставка новой записи в B-Tree (O(log n) с возможной
    page split)
  - UPDATE indexed column → логически DELETE + INSERT в B-Tree
    (в PostgreSQL UPDATE создаёт новую версию строки через MVCC,
    поэтому индексная запись старой версии становится "мёртвой")
  - DELETE → помечает запись индекса как мёртвую (physical delete
    при VACUUM)

Мёртвые записи в индексе → bloat. VACUUM убирает dead index entries.

Практика: не создавать индексы "на всякий случай". Каждый индекс
должен решать конкретную задачу, подтверждённую через EXPLAIN ANALYZE.
```

## Связь с другими темами

```txt
[MVCC, Locks, and Vacuum]       — почему UPDATE создаёт мёртвые
                                   записи в индексе и как VACUUM
                                   их убирает; HOT-update как
                                   оптимизация для index-free updates
[Query Planner and EXPLAIN]     — как использовать EXPLAIN ANALYZE
                                   для проверки использования
                                   индексов; cost model планировщика
[PostgreSQL Fundamentals]       — JSONB + GIN-индексы
```

## Типичные ошибки на интервью

- **"Индекс всегда ускоряет SELECT"** — планировщик выбирает Seq Scan, если селективность низкая (WHERE is_active = true при 99% true), потому что random I/O через индекс дороже последовательного чтения heap.

- **"Составной индекс (a, b) работает для WHERE b = ?"** — Left Prefix Rule: без левого столбца (`a`) в условии индекс используется неэффективно или не используется вовсе.

- **"Больше индексов = быстрее"** — каждый индекс замедляет INSERT/UPDATE/DELETE и увеличивает bloat при VACUUM.

- **"INCLUDE в индексе — то же самое, что добавить столбец в ключ"** — INCLUDE-столбцы не влияют на порядок сортировки в B-Tree (не участвуют в поиске по дереву), но включаются в листовые узлы для Index-Only Scan.

- **"BRIN-индекс подходит для всех таблиц"** — BRIN эффективен только когда физический порядок строк КОРРЕЛИРУЕТ с значением столбца (например, created_at в append-only таблице). Для случайно вставляемых данных BRIN бесполезен.
