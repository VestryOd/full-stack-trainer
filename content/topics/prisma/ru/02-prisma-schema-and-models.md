# Схема и модели Prisma

## Структура schema.prisma

`schema.prisma` — единственный источник истины (source of truth) для структуры базы данных в проекте на Prisma. Чего нет в этом файле, того для Prisma не существует.

Файл состоит из блоков трёх видов:

- `datasource` — к какой базе подключаться;
- `generator` — что генерировать из схемы;
- `model` — определение одной таблицы.

```prisma
// schema.prisma — полная структура

generator client {
  provider = "prisma-client-js"
  // output = "../src/generated/client" // можно указать кастомный путь
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  // shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // для migrate dev на prod-базе
}

// Enum — тип, общий для нескольких моделей
enum UserRole {
  ADMIN
  EDITOR
  VIEWER
}

model User {
  id        String   @id @default(uuid())         // первичный ключ: UUID v4
  email     String   @unique                        // ограничение UNIQUE
  name      String?                                 // может быть NULL
  role      UserRole @default(VIEWER)
  isActive  Boolean  @default(true)
  score     Decimal  @default(0) @db.Decimal(10, 2) // точные дроби для денег
  metadata  Json?                                   // поле JSON (в PostgreSQL jsonb)

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt                     // Prisma обновляет сама

  posts     Post[]   // один-ко-многим: у User много Post
  profile   Profile? // один-к-одному: у User один Profile (или ни одного)

  @@index([email, createdAt])                      // составной индекс
  @@map("users")                                   // имя таблицы (иначе было бы "User")
}
```

## Типы данных и их аналоги в SQL

Каждый тип Prisma превращается в конкретный тип колонки в SQL — языке, на котором Prisma разговаривает с базой. Ниже соответствия для PostgreSQL.

```prisma
// Prisma types → PostgreSQL types
String    → TEXT (или VARCHAR с @db.VarChar(255))
Int       → INTEGER
BigInt    → BIGINT
Float     → DOUBLE PRECISION
Decimal   → DECIMAL / NUMERIC — для денег только он, не Float!
Boolean   → BOOLEAN
DateTime  → TIMESTAMP WITH TIME ZONE
Json      → JSONB (PostgreSQL) / JSON (MySQL)
Bytes     → BYTEA — для бинарных данных
String[]  → TEXT[] — массивы (только PostgreSQL)

// Модификаторы @db — уточнить тип на уровне базы
email  String @db.VarChar(255)  // ограничить длину
price  Decimal @db.Decimal(10, 2) // 10 цифр, 2 после запятой
bio    String @db.Text           // явно TEXT (не VARCHAR)
```

## Атрибуты полей

```prisma
model Product {
  // Первичные ключи
  id     Int    @id @default(autoincrement())  // SERIAL / INTEGER
  uuid   String @id @default(uuid())           // UUID v4: 128 случайных бит
  cuid   String @id @default(cuid())           // CUID: короткий id без коллизий

  // Ограничения
  sku    String @unique                         // UNIQUE
  email  String @unique

  // Значения по умолчанию
  status String @default("active")             // строковый default
  count  Int    @default(0)
  flag   Boolean @default(false)
  createdAt DateTime @default(now())           // NOW() в SQL
  updatedAt DateTime @updatedAt                // обновление при каждом update

  // Переименование
  productName String @map("product_name")      // camelCase в TS, snake_case в базе

  // Поле вне миграций (вычисляемые значения)
  // computedField String? @ignore — колонка в базе не создаётся
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

  @@id([orderId, productId])       // составной первичный ключ (таблица-связка)
  @@unique([orderId, productId])   // составной UNIQUE (альтернатива @@id)
  @@index([productId])             // индекс по внешнему ключу — важен для скорости
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
  @@index([authorId])                   // внешний ключ индексируем всегда
  @@index([status, createdAt(sort: Desc)]) // составной с сортировкой
  // Для full-text search:
  // @@index([title], type: BrinIndex)  // PostgreSQL BRIN для временных серий
}
```

```txt
Правило: индексировать всегда
  ✓ поля-внешние ключи (authorId, userId, orderId)
  ✓ поля из частых условий WHERE (status, type, isActive)
  ✓ поля из ORDER BY, если в WHERE уже есть другие условия
  ✗ но не boolean-поля с низкой кардинальностью, то есть
     всего с двумя значениями (isActive = true/false)
     → планировщик такой индекс обычно игнорирует и читает
       таблицу целиком (последовательное чтение, seq scan)
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
// В TypeScript Prisma отдаёт enum как обычный объект
import { OrderStatus } from '@prisma/client';

const orders = await prisma.order.findMany({
  where: { status: OrderStatus.PENDING },
});

// Но: enum в PostgreSQL трудно менять миграцией (значение не удалить)
// Альтернатива: String + @db.VarChar(50) — гибче при частых изменениях
```

## Типичные ошибки на интервью

- **"Prisma работает с любым именем таблицы автоматически"** — нет. По умолчанию модель `User` превращается в таблицу `"User"`: в кавычках и с учётом регистра, если база PostgreSQL. Хотите `snake_case` — добавляйте `@@map("users")`. Без `@@map` на PostgreSQL легко получить ошибку, если кто-то создаст ту же таблицу без кавычек.

- **"Float подходит для цен"** — нет. `Float` — это двоичное число с плавающей точкой (стандарт IEEE 754), а в двоичном виде `0.1` не представляется точно. Отсюда `0.1 + 0.2 = 0.30000000000000004`. Для денег: `Decimal @db.Decimal(10, 2)` в схеме плюс `Decimal.js`, либо хранить копейки в `Int`. Для финансовых расчётов `Float` не годится никогда.

- **"@updatedAt обновляется автоматически всегда"** — обновляется при любом `update` через Prisma, но не при `$executeRaw`. Если менять строку через сырой SQL, `updatedAt` останется прежним. И ещё: значение подставляет Prisma Client, а не триггер в базе.

- **"Индекс на каждое поле ускоряет запросы"** — нет. Индексы замедляют `INSERT` и `UPDATE`: при каждой записи надо обновить ещё и индекс. Лишние индексы занимают место, тормозят запись и всё равно могут не пригодиться планировщику. Индексируйте только те поля, которые реально стоят в `WHERE`, `JOIN` или `ORDER BY`.

- **"UUID лучше autoincrement всегда"** — зависит от задачи. UUID (universally unique identifier) — это 128-битный случайный идентификатор. Его нельзя угадать по соседнему значению, поэтому он безопаснее для публичных API. Ещё его можно сгенерировать на клиенте и удобно сливать данные из нескольких баз.

  У `autoincrement` другие плюсы. Он компактнее: 4 байта против 16. И он лучше по локальности (locality) для индексов B-tree — новые строки ложатся в конец индекса, а не в случайное место. Для внутренних идентификаторов и `JOIN` берите `autoincrement`, для публичных ресурсов — `uuid`.
