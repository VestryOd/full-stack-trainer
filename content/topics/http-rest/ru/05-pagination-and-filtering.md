<!-- verified: 2026-06-23, corrections: 0 -->
# Пагинация и фильтрация

## Зачем это отдельная тема

Пагинация и фильтрация кажутся простыми — пока не сталкиваешься с таблицей на 50 миллионов записей, real-time лентой или бесконечным скроллом. Тогда выясняется, что `LIMIT 20 OFFSET 1000000` убивает базу данных, "страница 2" показывает дубликаты при одновременной вставке, а простой фильтр `?status=active` превращается в `?status[]=active&status[]=pending&createdAfter=2024-01-01`.

---

## Offset-Based Pagination (офсетная пагинация)

Самый распространённый подход. Клиент указывает "пропустить N записей, взять M".

```txt
Варианты синтаксиса:
GET /users?page=2&limit=20
GET /users?offset=20&limit=20  (page=2 → offset=(2-1)*20=20)
GET /users?skip=20&take=20     (Prisma-стиль)
```

### Как это работает в SQL

```sql
-- page=2, limit=20
SELECT * FROM users
ORDER BY created_at DESC
LIMIT 20 OFFSET 20;
```

### Структура ответа

```json
{
  "data": [...],
  "pagination": {
    "page": 2,
    "limit": 20,
    "total": 1547,
    "totalPages": 78,
    "hasNext": true,
    "hasPrev": true
  }
}
```

Или через заголовки (GitHub-стиль):
```http
X-Total-Count: 1547
Link: <https://api.example.com/users?page=3&limit=20>; rel="next",
      <https://api.example.com/users?page=1&limit=20>; rel="prev",
      <https://api.example.com/users?page=78&limit=20>; rel="last"
```

### Проблемы offset-пагинации

**1. Производительность на больших offset'ах**

```sql
-- Выглядит безобидно:
SELECT * FROM users ORDER BY created_at DESC LIMIT 20 OFFSET 1000000;

-- На самом деле: БД читает и отбрасывает 1 000 000 строк,
-- потом возвращает 20. Полный скан индекса.
-- На таблице 10M записей — секунды ожидания.
```

**2. Дрейф данных (data drift)**

```txt
Начальное состояние: [A, B, C, D, E, F]

Клиент получил page=1: [A, B, C]
Кто-то удалил A.
Клиент запрашивает page=2: [D, E, F] → OFFSET 3 → [E, F, ...]
                                                      ↑ D пропущен!

Или кто-то вставил X в начало:
Клиент запрашивает page=2: OFFSET 3 → [C, D, E]
                                        ↑ C дублируется!
```

**3. Невозможность параллельной обработки**

Нельзя узнать "страница от X до Y включительно" для параллельного скачивания.

### Когда использовать offset

- Пользователь переходит к конкретной странице ("перейти на страницу 42")
- Данные меняются редко (справочники, каталоги)
- Таблица относительно небольшая (до ~100K записей)
- Нужен `total` для отображения счётчика

---

## Cursor-Based Pagination (курсорная пагинация)

Вместо "пропустить N записей" — "дать мне записи после этой конкретной записи". Курсор — это непрозрачный указатель на позицию в наборе данных.

```txt
GET /users?limit=20                    ← первая страница
GET /users?cursor=eyJpZCI6MjB9&limit=20 ← следующая (cursor из предыдущего ответа)
```

### Как это работает

```json
// Ответ первой страницы:
{
  "data": [
    { "id": 1, "name": "Alice" },
    ...
    { "id": 20, "name": "Bob" }
  ],
  "pagination": {
    "nextCursor": "eyJpZCI6MjB9",
    "hasNext": true
  }
}
```

Курсор — base64-encoded JSON с данными для следующего запроса:
```typescript
// Кодирование:
const cursor = Buffer.from(JSON.stringify({ id: lastItem.id })).toString("base64url");

// Декодирование:
const { id } = JSON.parse(Buffer.from(cursor, "base64url").toString());
```

### SQL под капотом

```sql
-- Первая страница:
SELECT * FROM users
ORDER BY id DESC
LIMIT 20;

-- Следующая (cursor содержит id=20):
SELECT * FROM users
WHERE id < 20
ORDER BY ID DESC
LIMIT 20;
```

Это keyset pagination: вместо `OFFSET` — условие `WHERE`. Индекс используется эффективно вне зависимости от позиции.

### Курсор по составному ключу

Если сортировка не по уникальному полю (например, по `created_at`), нужен составной курсор:

```sql
-- created_at может быть у нескольких записей одинаковым
SELECT * FROM posts
WHERE (created_at, id) < ('2024-01-15 10:00:00', 42)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

Курсор кодирует оба поля:
```typescript
const cursor = Buffer.from(
  JSON.stringify({ createdAt: lastItem.createdAt, id: lastItem.id })
).toString("base64url");
```

### Преимущества и ограничения курсорной пагинации

```txt
Преимущества:
  ✅ Стабильная: вставки/удаления не ломают пагинацию
  ✅ Производительная: O(log n) по индексу вместо O(n) при большом offset
  ✅ Идеальна для бесконечного скролла и real-time лент
  ✅ Работает правильно при конкурентных изменениях

Ограничения:
  ❌ Нельзя прыгнуть на страницу 42 напрямую
  ❌ Нельзя показать "страница 2 из 78"
  ❌ Обычно только "вперёд" (назад — сложнее, нужен реверсный курсор)
  ❌ Нет общего count без COUNT(*) запроса (дорогого на больших таблицах)
```

### Двунаправленная курсорная пагинация

```json
{
  "data": [...],
  "pagination": {
    "startCursor": "eyJpZCI6MX0",
    "endCursor": "eyJpZCI6MjB9",
    "hasNextPage": true,
    "hasPreviousPage": false
  }
}
```

GraphQL (Relay) использует именно эту модель:
```graphql
{
  users(first: 20, after: "cursor") {
    edges { node { id name } cursor }
    pageInfo { hasNextPage endCursor }
  }
}
```

---

## Сравнение подходов

```txt
┌─────────────────────┬──────────────────┬──────────────────────┐
│                     │ Offset/Page      │ Cursor               │
├─────────────────────┼──────────────────┼──────────────────────┤
│ Переход на страницу │ ✅ Просто         │ ❌ Невозможно        │
│ Общее количество    │ ✅ Есть           │ ❌ Сложно            │
│ Бесконечный скролл  │ ⚠️ Drift-проблемы │ ✅ Идеально           │
│ Производительность  │ ❌ O(n) при >100K │ ✅ O(log n) всегда   │
│ Стабильность        │ ❌ Drift при DML  │ ✅ Стабильна         │
│ Простота реализации │ ✅ Просто         │ ⚠️ Сложнее           │
│ Real-time лента     │ ❌ Не подходит    │ ✅ Идеально           │
└─────────────────────┴──────────────────┴──────────────────────┘

Правило выбора:
  Классическая таблица с номером страницы → offset
  Бесконечный скролл / лента / большие данные → cursor
```

---

## Фильтрация

### Простые фильтры через query params

```txt
GET /users?status=active
GET /users?role=admin&status=active          (AND)
GET /products?categoryId=5&inStock=true
GET /orders?userId=42
```

### Множественные значения (OR по одному полю)

```txt
Вариант 1 — повторяющийся параметр (предпочтительно):
GET /users?status=active&status=pending

Вариант 2 — массив в скобках:
GET /users?status[]=active&status[]=pending

Вариант 3 — через запятую:
GET /users?status=active,pending
```

Express парсит повторяющиеся параметры как массив автоматически (при `req.query.status`).

### Операторы сравнения

Для числовых и временных фильтров нужны операторы:

```txt
Вариант 1 — суффикс:
GET /orders?totalGte=100&totalLte=500
GET /users?createdAfter=2024-01-01&createdBefore=2024-12-31

Вариант 2 — скобочная нотация:
GET /orders?total[gte]=100&total[lte]=500
GET /users?created[after]=2024-01-01

Вариант 3 — Prisma/API-стиль:
GET /orders?filter=total:gte:100,total:lte:500
```

Нет единого стандарта. Главное — документировать и быть последовательным.

### Поиск

```txt
GET /users?q=alice                   — полнотекстовый поиск
GET /users?search=alice              — то же, другое имя параметра
GET /products?name=iphone&fuzzy=true — fuzzy-поиск
```

На уровне SQL:
```sql
-- LIKE (простой):
WHERE name ILIKE '%alice%'

-- Full-text search (PostgreSQL):
WHERE to_tsvector('english', name || ' ' || email) @@ to_tsquery('english', 'alice')

-- Для серьёзного поиска: Elasticsearch, Meilisearch, pg_trgm
```

---

## Сортировка

```txt
Один столбец:
GET /users?sort=createdAt&order=desc
GET /users?sort=name&order=asc
GET /users?sort=-createdAt            (минус = desc — популярная конвенция)
GET /users?sort=+name                 (плюс = asc)

Несколько столбцов:
GET /users?sort=-createdAt,name       (desc by date, then asc by name)
GET /users?sort[0]=createdAt&sort[0]direction=desc&sort[1]=name
```

### Безопасность сортировки

Никогда не подставляйте поле сортировки напрямую в SQL:

```typescript
// ❌ SQL Injection:
const query = `SELECT * FROM users ORDER BY ${req.query.sort}`;

// ✅ Whitelist разрешённых полей:
const SORTABLE_FIELDS = new Set(["createdAt", "name", "email", "id"]);
const sortField = SORTABLE_FIELDS.has(req.query.sort as string)
  ? req.query.sort as string
  : "createdAt";
```

---

## Sparse Fieldsets (выборка полей)

```txt
GET /users?fields=id,name,email
GET /users?select=id,name,email
GET /users?include=profile,orders     (включить связанные сущности)
GET /users?exclude=password,internalNotes
```

Полезно для:
- Уменьшения размера ответа (особенно для мобильных клиентов)
- Исключения чувствительных полей
- Производительности (SELECT только нужных полей)

Так же нужен whitelist:
```typescript
const ALLOWED_FIELDS = new Set(["id", "name", "email", "createdAt", "role"]);
const requestedFields = (req.query.fields as string)?.split(",") ?? [];
const fields = requestedFields.filter(f => ALLOWED_FIELDS.has(f));
```

---

## Полный пример: Express + Prisma

```typescript
import { Request, Response } from "express";
import { prisma } from "../lib/prisma";
import { z } from "zod";

const listUsersSchema = z.object({
  // Пагинация
  cursor: z.string().optional(),
  limit: z.coerce.number().int().min(1).max(100).default(20),
  // Фильтрация
  status: z.union([z.string(), z.array(z.string())]).optional(),
  role: z.string().optional(),
  q: z.string().optional(),
  // Сортировка
  sort: z.enum(["createdAt", "name", "email"]).default("createdAt"),
  order: z.enum(["asc", "desc"]).default("desc"),
});

export async function listUsers(req: Request, res: Response) {
  const parsed = listUsersSchema.safeParse(req.query);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.flatten() });
  }

  const { cursor, limit, status, role, q, sort, order } = parsed.data;

  // Декодируем курсор
  let cursorId: number | undefined;
  if (cursor) {
    try {
      const decoded = JSON.parse(Buffer.from(cursor, "base64url").toString());
      cursorId = decoded.id;
    } catch {
      return res.status(400).json({ error: "Invalid cursor" });
    }
  }

  // Строим фильтр
  const where: Record<string, unknown> = {};

  if (status) {
    const statuses = Array.isArray(status) ? status : [status];
    where.status = { in: statuses };
  }

  if (role) where.role = role;

  if (q) {
    where.OR = [
      { name: { contains: q, mode: "insensitive" } },
      { email: { contains: q, mode: "insensitive" } },
    ];
  }

  // Запрашиваем limit+1 для hasNext
  const users = await prisma.user.findMany({
    where,
    orderBy: { [sort]: order },
    take: limit + 1,
    ...(cursorId ? { cursor: { id: cursorId }, skip: 1 } : {}),
    select: { id: true, name: true, email: true, status: true, createdAt: true },
  });

  const hasNext = users.length > limit;
  const data = hasNext ? users.slice(0, limit) : users;

  const lastItem = data.at(-1);
  const nextCursor = hasNext && lastItem
    ? Buffer.from(JSON.stringify({ id: lastItem.id })).toString("base64url")
    : null;

  res.set("X-Total-Count", String(await prisma.user.count({ where })));

  res.json({
    data,
    pagination: { nextCursor, hasNext, limit },
  });
}
```

---

## Rate Limiting как защита пагинации

Большой `limit` или агрессивный скрейпинг через пагинацию могут перегрузить сервер. Стандартные меры:

```typescript
// Ограничиваем максимальный limit:
limit: z.coerce.number().int().min(1).max(100).default(20)

// Rate limiting на уровне middleware:
import rateLimit from "express-rate-limit";

const apiLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 минута
  max: 100,            // 100 запросов в минуту
  standardHeaders: true,
  legacyHeaders: false,
});

app.use("/api/", apiLimiter);
```

Ответ при превышении:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1719187260
```

---

## Типичные ошибки на интервью

- **"Offset-пагинация — это нормально всегда"** — нет. На таблицах >100K записей `OFFSET 50000` может занимать секунды. Для бесконечного скролла или real-time лент offset — неправильный выбор из-за drift.

- **"Курсор — это просто ID последней записи"** — не обязательно. Курсор — это непрозрачный токен, который клиент не должен интерпретировать. Внутри может быть составной ключ, timestamp + id, или любые данные для воспроизведения позиции. Непрозрачность — намеренная: сервер может изменить формат.

- **"OFFSET 0 = OFFSET ничего не пропускать, значит всегда быстро"** — `OFFSET 0` быстро, но `OFFSET 5000000` — нет. Именно для этого нужна курсорная пагинация.

- **"Для фильтрации по полю достаточно WHERE поле = value"** — нет индекса на поле фильтрации = полный скан таблицы. Типичная production-проблема: запрос работал быстро на тестовых данных, упал в прод при 10M записей.

- **"Сортировку можно сделать через ORDER BY req.query.sort"** — SQL injection. Поле сортировки всегда нужно валидировать через whitelist.

- **"total count нужен всегда"** — `COUNT(*)` на большой таблице с фильтрами может быть дорогим. Иногда правильный ответ: не возвращать точный total, а только `hasNext`. Instagram/Twitter/X не показывают "1 из 847 страниц".

- **"Cursor-based пагинация не поддерживает 'назад'"** — технически поддерживает, но требует реверсного курсора (сортировка в обратном направлении). Большинство реализаций делают только "вперёд", что достаточно для бесконечного скролла.
