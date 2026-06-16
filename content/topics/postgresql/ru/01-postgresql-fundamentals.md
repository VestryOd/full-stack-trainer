<!-- verified: 2026-06-05, corrections: 0 -->
# PostgreSQL Fundamentals

## PostgreSQL — не просто "реляционная БД", а объектно-реляционная СУБД с богатой системой типов

PostgreSQL — open-source ОРСУБД (объектно-реляционная система управления базами данных). Ключевые слова:

```txt
"объектно-реляционная" — поддерживает наследование таблиц,
пользовательские типы (CREATE TYPE), перегрузку операторов,
собственные агрегатные функции. Это выходит за рамки стандарта
SQL:2016 и стандартной реляционной модели (Кодда).

"открытый исходный код" — код полностью открыт (лицензия
PostgreSQL, схожа с MIT), активно развивается сообществом
с 1996 года, контролируется PostgreSQL Global Development Group.
```

На интервью важно: "PostgreSQL — самая продвинутая open-source реляционная БД" — стандартная формулировка самого проекта. Отличие от MySQL: PostgreSQL строже следует стандарту SQL, лучше поддерживает сложные JOIN'ы, имеет MVCC без блокировок чтения (подробнее — [MVCC, Locks, and Vacuum]).

## Путь SQL-запроса через внутренние слои PostgreSQL

```txt
Приложение (psql / Prisma / pg)
        │  SQL-текст по TCP (протокол PostgreSQL wire protocol)
        ▼
  ┌─────────────────────────────────────┐
  │  Parser      — строит AST из SQL   │
  │  Analyzer    — разрешает имена     │
  │               (таблицы, столбцы,   │
  │               типы) → Query Tree   │
  │  Rewriter    — применяет правила   │
  │               (VIEW expansion,     │
  │               RLS-политики)        │
  │  Planner/    — строит несколько    │
  │  Optimizer     планов, выбирает    │
  │               план с минимальной   │
  │               оценочной стоимостью │
  │  Executor    — выполняет план,     │
  │               возвращает строки    │
  └─────────────────────────────────────┘
        │
        ▼
  Buffer Manager (shared_buffers — кэш страниц в RAM)
        │  промах кэша
        ▼
  Storage (heap files, index files на диске)
```

```txt
Senior-нюанс: планировщик (Planner) — наиболее сложная часть.
Он оценивает стоимость через статистику (pg_statistic, собираемую
ANALYZE), выбирает между Seq Scan, Index Scan, Bitmap Scan,
Hash Join, Merge Join и т.д. Неверная статистика → неверный план
→ медленный запрос. Подробнее — [Query Planner and EXPLAIN].
```

## Иерархия объектов: Cluster → Database → Schema → Table → Row → Column

```txt
Cluster     — весь экземпляр PostgreSQL (один postmaster-процесс,
              один data directory). Содержит НЕСКОЛЬКО databases.

Database    — логически изолированный контейнер. Транзакция не
              может затронуть данные в ДРУГОЙ базе (cross-database
              запросы — только через dblink/postgres_fdw).

Schema      — пространство имён внутри базы. По умолчанию: public.
              Один экземпляр: несколько схем (например, одна схема
              на клиента в multi-tenant SaaS).

Table       — набор строк одного "типа" (одной структуры столбцов).
              Физически — heap file (куча страниц по 8 КБ).

Row (tuple) — одна запись. PostgreSQL называет строку "tuple"
              во внутренней документации.

Column      — атрибут таблицы. Имеет тип данных и набор constraints.
```

```sql
-- Демонстрация иерархии
CREATE DATABASE app_db;

\c app_db

CREATE SCHEMA billing;

CREATE TABLE billing.invoices (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES public.users(id),
    amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Типы данных — выбор типа влияет на размер, индексы и поведение

```sql
-- Числа
INTEGER        -- 4 байта, -2.1млрд..+2.1млрд
BIGINT         -- 8 байт, ±9.2×10^18  ← для user_id, счётчиков
SERIAL         -- автоинкремент на INTEGER (реализован через SEQUENCE)
BIGSERIAL      -- автоинкремент на BIGINT (предпочтительно для PK)
NUMERIC(p, s)  -- произвольная точность, точные деньги; медленнее float
REAL / FLOAT8  -- IEEE 754 float; не для денег (потеря точности)

-- Строки
TEXT           -- переменная длина, нет ограничения (предпочтительно)
VARCHAR(n)     -- как TEXT, но с ограничением длины (в PostgreSQL нет
               -- разницы в производительности vs TEXT — оба VARLENA)
CHAR(n)        -- фиксированная длина, дополняется пробелами — почти
               -- никогда не нужен в современных приложениях

-- Дата и время
DATE           -- только дата (без времени суток)
TIMESTAMP      -- дата + время, без часового пояса (хранит "стену")
TIMESTAMPTZ    -- дата + время + UTC-нормализация (рекомендуется для
               -- всего, что будет показано пользователям разных TZ)
INTERVAL       -- промежуток времени (INTERVAL '3 months')

-- Булево
BOOLEAN        -- TRUE / FALSE / NULL (три состояния)

-- JSON
JSON           -- хранит исходный текст JSON как есть (парсинг при
               -- каждом обращении)
JSONB          -- бинарный JSON: разобран при вставке, поддерживает
               -- GIN-индексы, операторы @>, ?, #>. Предпочтительно.
               -- Единственный downside: потеря порядка ключей и
               -- дублирующихся ключей (как dict в Python)

-- UUID
UUID           -- 128-бит UUID; хранится эффективнее, чем TEXT(36)
               -- gen_random_uuid() (встроено в PostgreSQL 13+)

-- Массивы
INTEGER[]      -- массив любого типа (нативная поддержка PostgreSQL,
TEXT[]         -- НЕ JSON-массив). Поиск через оператор @> или ANY().
```

```txt
Senior-практика: всегда предпочитать TIMESTAMPTZ вместо TIMESTAMP.
TIMESTAMP без TZ хранит "локальное" время без информации о зоне —
при смене настройки timezone сервера/клиента данные начнут
интерпретироваться неверно. TIMESTAMPTZ нормализует к UTC при
хранении, возвращает в TZ сессии при чтении.
```

## Constraints — встроенная защита целостности данных

```sql
CREATE TABLE orders (
    id          BIGSERIAL PRIMARY KEY,           -- NOT NULL + UNIQUE
    user_id     BIGINT NOT NULL
                  REFERENCES users(id)
                  ON DELETE RESTRICT             -- запрещает удаление
                  ON DELETE SET NULL,            -- или: обнуляет ссылку
                  ON DELETE CASCADE,             -- или: удаляет каскадно
    status      TEXT NOT NULL
                  CHECK (status IN ('pending','paid','cancelled')),
    total       NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    email       TEXT UNIQUE,                     -- NULL не нарушает UNIQUE
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Отложенные constraints (проверяются в КОНЦЕ транзакции, не на каждой строке)
ALTER TABLE orders
  ADD CONSTRAINT fk_user
  FOREIGN KEY (user_id) REFERENCES users(id)
  DEFERRABLE INITIALLY DEFERRED;
```

```txt
Senior-нюанс: UNIQUE в PostgreSQL допускает НЕСКОЛЬКО NULL (потому
что NULL ≠ NULL в SQL-стандарте). Если нужно уникальное поле с
единственным NULL, используют UNIQUE + NULL-специфичный partial
index: CREATE UNIQUE INDEX ON t(col) WHERE col IS NOT NULL.

ON DELETE RESTRICT vs ON DELETE NO ACTION: оба запрещают удаление
родительской строки, если есть дочерние. Разница: RESTRICT проверяет
немедленно внутри оператора; NO ACTION можно сделать DEFERRED
(проверка в конце транзакции).
```

## Связи и нормализация — практический уровень

```sql
-- Many-to-Many через junction table
CREATE TABLE user_roles (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)             -- составной PK исключает дубли
);

-- JOIN — основа работы с нормализованными данными
SELECT u.id, u.name, r.name AS role
FROM users u
JOIN user_roles ur ON ur.user_id = u.id
JOIN roles r       ON r.id = ur.role_id
WHERE u.id = $1;
```

```txt
Нормальные формы (для интервью достаточно 3NF):
  1NF — атомарные значения (нет массивов/группировок в колонке),
        уникальные строки
  2NF — каждый неключевой атрибут зависит от ВСЕГО ключа
        (актуально для составных PK)
  3NF — нет транзитивных зависимостей (не-ключ не зависит от
        другого не-ключа)

Денормализация как осознанный trade-off:
  orders.total_amount — хранить предрасчитанную сумму вместо
  пересчёта SUM(items.price * items.qty) при каждом чтении.
  Цена: дублирование + риск рассинхронизации при прямых UPDATE
  на items без обновления orders.total_amount.
```

## JSONB — когда и как использовать с умом

```sql
CREATE TABLE products (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    attributes  JSONB                       -- dynamic / variable fields
);

INSERT INTO products (name, attributes)
VALUES ('iPhone 15', '{"color": "black", "storage": 256, "tags": ["phone","apple"]}');

-- Операторы JSONB
SELECT * FROM products WHERE attributes @> '{"color": "black"}';    -- содержит
SELECT attributes->>'color' FROM products WHERE id = 1;             -- достать строку
SELECT attributes->'storage' FROM products;                          -- достать JSON-value

-- GIN-индекс для операторов @>, ?, ?|, ?&
CREATE INDEX idx_products_attrs ON products USING GIN (attributes);

-- Для path-операторов (jsonb_path_ops) — меньший индекс, только @>
CREATE INDEX idx_products_attrs_path ON products
  USING GIN (attributes jsonb_path_ops);
```

```txt
Когда JSONB уместен:
  ✓ "Dynamic schema" — атрибуты, которые сильно отличаются между
    записями (product attributes в e-commerce)
  ✓ Хранение внешних API-ответов без нормализации (audit log)
  ✓ Быстрое прототипирование до стабилизации схемы

Когда JSONB — anti-pattern:
  ✗ Поля, по которым часто делаются WHERE/JOIN — они должны быть
    обычными столбцами с обычными B-Tree индексами
  ✗ Связи между сущностями — FOREIGN KEY в JSONB невозможен
  ✗ "Потому что гибко" — без реального обоснования dynamic schema
```

## Связь с другими темами

```txt
[ACID and Transactions]           — как PostgreSQL обеспечивает
                                      консистентность через транзакции
[Isolation Levels]                — как настраивается видимость
                                      изменений между конкурентными
                                      транзакциями
[Indexes and Internals]           — как ускорить SELECT на больших
                                      таблицах
[MVCC, Locks, and Vacuum]         — почему UPDATE в PostgreSQL не
                                      перезаписывает строку на месте
[Query Planner and EXPLAIN]       — как выбирается план выполнения
```

## Типичные ошибки на интервью

- **"TEXT vs VARCHAR — VARCHAR быстрее"** — в PostgreSQL оба типа используют одно и то же внутреннее представление (VARLENA); разница производительности нулевая. VARCHAR(n) добавляет только проверку длины.

- **"TIMESTAMP и TIMESTAMPTZ — одно и то же"** — не объяснять, что TIMESTAMP хранит "наивную" дату без TZ, что может привести к неверной интерпретации при смене TZ сервера или клиента.

- **"SERIAL — лучший способ создать автоинкремент"** — не знать, что SERIAL — это синтаксический сахар (CREATE SEQUENCE + DEFAULT nextval()), и что в современном PostgreSQL предпочтительны `GENERATED ALWAYS AS IDENTITY` или `BIGSERIAL` для совместимости с SQL-стандартом.

- **"UNIQUE запрещает два NULL"** — в PostgreSQL (как и в SQL-стандарте) NULL ≠ NULL, поэтому UNIQUE-индекс допускает несколько NULL-значений.

- **"JSONB нужен для гибкости"** — не объяснять конкретный trade-off: JSONB нарушает реляционную нормализацию, делает невозможными FOREIGN KEY-связи и INDEX на вложенные поля с хорошей селективностью через обычный B-Tree.
