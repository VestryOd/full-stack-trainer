# Prisma Schema and Models

## Структура schema.prisma

`schema.prisma` — единственный source of truth для структуры БД в Prisma-проекте. Состоит из трёх блоков: datasource (подключение к БД), generator (что генерировать), model (определения таблиц).

```prisma
// schema.prisma — полная структура

generator client {
  provider = "prisma-client-js"
  // output = "../src/generated/client" // можно указать кастомный путь
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  // shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // нужен для migrate dev на prod БД
}

// Enum — тип, общий для нескольких моделей
enum UserRole {
  ADMIN
  EDITOR
  VIEWER
}

model User {
  id        String   @id @default(uuid())         // UUID primary key
  email     String   @unique                        // UNIQUE constraint
  name      String?                                 // nullable (NULL в SQL)
  role      UserRole @default(VIEWER)
  isActive  Boolean  @default(true)
  score     Decimal  @default(0) @db.Decimal(10, 2) // точный decimal для денег
  metadata  Json?                                   // JSON поле (PostgreSQL jsonb)

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt                     // Prisma обновляет автоматически

  posts     Post[]   // one-to-many: у User много Post
  profile   Profile? // one-to-one: у User один Profile (опционально)

  @@index([email, createdAt])                      // составной индекс
  @@map("users")                                   // имя таблицы в БД (по умолчанию = "User")
}
```

## Типы данных и их SQL-аналоги

```prisma
// Prisma types → PostgreSQL types
String    → TEXT (или VARCHAR с @db.VarChar(255))
Int       → INTEGER
BigInt    → BIGINT
Float     → DOUBLE PRECISION
Decimal   → DECIMAL / NUMERIC — используй для денег, не Float!
Boolean   → BOOLEAN
DateTime  → TIMESTAMP WITH TIME ZONE
Json      → JSONB (PostgreSQL) / JSON (MySQL)
Bytes     → BYTEA — для бинарных данных
String[]  → TEXT[] — массивы (только PostgreSQL)

// @db модификаторы — уточнить тип на уровне БД
email  String @db.VarChar(255)  // ограничить длину
price  Decimal @db.Decimal(10, 2) // 10 цифр, 2 после запятой
bio    String @db.Text           // явно TEXT (не VARCHAR)
```

## Атрибуты полей

```prisma
model Product {
  // Primary Keys
  id     Int    @id @default(autoincrement())  // SERIAL / INTEGER
  uuid   String @id @default(uuid())           // UUID v4
  cuid   String @id @default(cuid())           // CUID — collision-resistant ID

  // Constraints
  sku    String @unique                         // UNIQUE
  email  String @unique

  // Defaults
  status String @default("active")             // строковый default
  count  Int    @default(0)
  flag   Boolean @default(false)
  createdAt DateTime @default(now())           // NOW() в SQL
  updatedAt DateTime @updatedAt                // триггер обновления

  // Mapping
  productName String @map("product_name")      // camelCase в TS, snake_case в БД
  
  // Ignore field in migrations (вычисляемые поля)
  // computedField String? @ignore — не создаёт колонку в БД
}
```

## Составные ограничения на уровне модели

```prisma
model OrderItem {
  orderId   Int
  productId Int
  quantity  Int

  order   Order   @relation(fields: [orderId], references: [id])
  product Product @relation(fields: [productId], references: [id])

  @@id([orderId, productId])       // составной Primary Key (many-to-many join table)
  @@unique([orderId, productId])   // составной UNIQUE (альтернатива @@id)
  @@index([productId])             // индекс для foreign key (важно для производительности)
  @@map("order_items")
}
```

## Индексы — когда и зачем

```prisma
model Post {
  id        Int      @id @default(autoincrement())
  title     String
  slug      String   @unique             // автоматически создаёт индекс
  authorId  Int
  status    String   @default("draft")
  createdAt DateTime @default(now())

  // Явные индексы — для полей в WHERE/ORDER BY
  @@index([authorId])                   // FK всегда индексировать
  @@index([status, createdAt(sort: Desc)]) // составной с сортировкой
  // Для full-text search:
  // @@index([title], type: BrinIndex)  // PostgreSQL BRIN для временных серий
}
```

```txt
Правило: всегда индексировать:
  ✓ Foreign key поля (authorId, userId, orderId)
  ✓ Поля в частых WHERE условиях (status, type, isActive)
  ✓ Поля в ORDER BY если в WHERE уже есть другие условия
  ✗ НЕ индексировать boolean поля с низкой кардинальностью (isActive = true/false)
     → планировщик часто игнорирует такой индекс и делает seq scan
```

## Enum — когда лучше String

```prisma
enum OrderStatus {
  PENDING
  CONFIRMED
  SHIPPED
  DELIVERED
  CANCELLED
}

model Order {
  id     Int         @id @default(autoincrement())
  status OrderStatus @default(PENDING)
}
```

```typescript
// TypeScript: Prisma импортирует enum как object
import { OrderStatus } from '@prisma/client';

const orders = await prisma.order.findMany({
  where: { status: OrderStatus.PENDING },
});

// Но: PostgreSQL Enum сложно менять в migration (нельзя удалить значение)
// Альтернатива: String + @db.VarChar(50) — более гибко при частых изменениях
```

## Типичные ошибки на интервью

- **"Prisma работает с любым именем таблицы автоматически"** — нет. По умолчанию: model `User` → таблица `"User"` (с кавычками, чувствительна к регистру в PostgreSQL). Для `snake_case`: всегда добавлять `@@map("users")`. Без `@@map` на PostgreSQL возможны ошибки если кто-то создаёт таблицу без кавычек.

- **"Float подходит для цен"** — нет. `Float` — IEEE 754 floating point, даёт ошибки округления: `0.1 + 0.2 = 0.30000000000000004`. Для денег: `Decimal @db.Decimal(10, 2)` в schema + `Decimal.js` или хранить в копейках как `Int`. Никогда не использовать Float для финансовых расчётов.

- **"@updatedAt обновляется автоматически всегда"** — обновляется при любой Prisma update операции, но НЕ при `$executeRaw`. Если обновлять через raw SQL — `updatedAt` не обновится. Также: `@updatedAt` устанавливается на стороне Prisma Client, не через триггер в БД.

- **"Индекс на каждое поле ускоряет запросы"** — нет. Индексы замедляют INSERT/UPDATE (нужно обновить индексную структуру). Избыточные индексы: занимают место, замедляют запись, могут не использоваться планировщиком. Индексировать только поля в реальных `WHERE`/`JOIN`/`ORDER BY` запросах.

- **"UUID лучше autoincrement всегда"** — зависит от задачи. UUID: нет предсказуемой последовательности (безопаснее для публичных API), можно генерировать на клиенте, удобно для merge данных из нескольких БД. Autoincrement: компактнее (4 байта vs 16), лучше locality для B-tree индексов (новые записи в конец). Для внутренних ID + JOIN: `autoincrement`. Для публичных ресурсов: `uuid`.
