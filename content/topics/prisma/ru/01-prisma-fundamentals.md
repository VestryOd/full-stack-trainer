# Prisma Fundamentals

## Что такое Prisma и зачем она нужна

Prisma — TypeScript-first ORM toolkit для Node.js. Ключевое отличие от TypeORM/Sequelize: schema-first подход — разработчик описывает модели в `schema.prisma`, а Prisma генерирует полностью типизированный клиент под конкретную схему. Это значит что `prisma.user.findMany()` возвращает `User[]` со всеми полями без дополнительных Generic-аннотаций, а опечатка в имени поля — ошибка компиляции, не runtime-ошибка.

```txt
Компоненты Prisma:
  schema.prisma   — описание моделей, связей, datasource, generator
  Prisma Client   — сгенерированный TypeScript API (node_modules/.prisma/client)
  Prisma Migrate  — система миграций: schema.prisma → SQL → применить к БД
  Prisma Studio   — GUI для просмотра и редактирования данных (опционально)

Стек запроса:
  NestJS Service
    ↓
  Prisma Client (TypeScript)
    ↓
  Prisma Query Engine (Rust, нативный бинарник)
    ↓
  PostgreSQL / MySQL / SQLite / SQL Server / MongoDB
```

## Минимальная конфигурация

```prisma
// schema.prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String?
  createdAt DateTime @default(now())
  posts     Post[]
}

model Post {
  id       Int    @id @default(autoincrement())
  title    String
  authorId Int
  author   User   @relation(fields: [authorId], references: [id])
}
```

```typescript
// Инициализация (singleton для NestJS — через PrismaService)
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient({
  log: ['query', 'error'], // логировать SQL запросы в dev
});

// CRUD — базовые операции
const user = await prisma.user.create({
  data: { email: 'alice@example.com', name: 'Alice' },
});

const users = await prisma.user.findMany({
  where: { name: { not: null } },
  orderBy: { createdAt: 'desc' },
  take: 10,
  skip: 0,
});

const updated = await prisma.user.update({
  where: { id: user.id },
  data: { name: 'Alice Smith' },
});

await prisma.user.delete({ where: { id: user.id } });
```

## PrismaService в NestJS

```typescript
// prisma.service.ts — стандартный singleton в NestJS
import { Injectable, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';

@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  async onModuleInit() {
    await this.$connect();
  }

  async onModuleDestroy() {
    await this.$disconnect();
  }
}

// prisma.module.ts
@Global()
@Module({
  providers: [PrismaService],
  exports: [PrismaService],
})
export class PrismaModule {}

// users.service.ts — использование
@Injectable()
export class UsersService {
  constructor(private prisma: PrismaService) {}

  async findAll() {
    return this.prisma.user.findMany();
  }
}
```

## Когда Prisma подходит и когда нет

```txt
Prisma подходит для:
  ✓ TypeScript проекты (NestJS, Next.js, Express + TS)
  ✓ CRUD-heavy приложения (SaaS, admin panels, APIs)
  ✓ Команды с разным уровнем SQL — типизация снижает ошибки
  ✓ Rapid development — schema + migrate + generated client = быстро
  ✓ GraphQL backends (Prisma + Pothos/Nexus = minimal boilerplate)

Prisma НЕ подходит или требует workaround:
  ✗ Сложные аналитические запросы (window functions, CTE, LATERAL JOIN)
     → решение: prisma.$queryRaw`SELECT ... OVER (PARTITION BY ...)`
  ✗ Bulk insert/update тысяч записей
     → Prisma createMany не поддерживает skipDuplicates с relations;
       для bulk: $executeRaw или pg-copy-streams
  ✗ Динамическое построение запросов с условными JOIN
     → TypeORM QueryBuilder более гибкий в этом сценарии
```

## $queryRaw и $executeRaw — когда нужен SQL

```typescript
// $queryRaw — вернуть типизированные результаты
// Внимание: Prisma.sql template literal обязателен для защиты от SQL injection
const result = await prisma.$queryRaw<{ id: number; rank: number }[]>`
  SELECT id, RANK() OVER (ORDER BY score DESC) as rank
  FROM users
  WHERE created_at > ${new Date('2024-01-01')}
`;

// $executeRaw — для UPDATE/DELETE без возврата данных
const count = await prisma.$executeRaw`
  UPDATE users SET last_seen = NOW() WHERE id = ${userId}
`;
// Возвращает количество затронутых строк

// НИКОГДА не использовать строковую интерполяцию:
// ✗ await prisma.$queryRaw(`SELECT * FROM users WHERE id = ${userId}`) // SQL injection!
// ✓ await prisma.$queryRaw`SELECT * FROM users WHERE id = ${userId}`   // параметризованный
```

## Типичные ошибки на интервью

- **"Prisma — это база данных"** — нет. Prisma — ORM поверх существующей БД. Данные хранит PostgreSQL/MySQL/SQLite, Prisma только генерирует и выполняет запросы к ней. `prisma.user.findMany()` → Prisma Client → Rust Query Engine → SQL → PostgreSQL.

- **"Prisma генерирует неэффективные запросы"** — частично правда для N+1 проблемы (без `include`), но Prisma умеет генерировать JOIN через `include`/`select`. Для сложных запросов: `$queryRaw`. Генерируемые запросы можно посмотреть через `log: ['query']` в PrismaClient.

- **"PrismaClient можно создавать в каждом запросе"** — нет. PrismaClient управляет connection pool. В NestJS — один singleton `PrismaService extends PrismaClient`. Создание нового экземпляра в каждом запросе → утечка соединений и деградация производительности.

- **"Prisma Migrate и Prisma Client — одно и то же"** — нет. Migrate — инструмент разработки (CLI): `prisma migrate dev` → генерирует SQL миграции. Client — runtime библиотека: выполняет запросы к БД. В production запускают `prisma migrate deploy` (применяет pending миграции), Client уже скомпилирован в бандле.

- **"После изменения schema.prisma изменения сразу доступны"** — нет. Нужно: (1) `prisma migrate dev` — создать миграцию и применить к БД; (2) `prisma generate` — перегенерировать Client. Если только изменить schema без `generate` — TypeScript типы старые, рантайм тоже старый.
