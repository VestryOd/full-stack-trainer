# Основы Prisma

## Что такое Prisma и зачем она нужна

Prisma — это ORM (Object-Relational Mapping, «объектно-реляционное отображение») для Node.js. ORM — слой, который переводит вызовы на TypeScript в SQL, то есть в язык запросов, на котором говорит база данных.

Ключевое отличие от TypeORM и Sequelize — порядок работы: сначала схема, потом код (schema-first). Разработчик описывает модели в `schema.prisma`, а Prisma генерирует по ним клиент, типизированный под эту конкретную схему.

Что это даёт на практике: `prisma.user.findMany()` возвращает `User[]` со всеми полями, и дописывать обобщённые типы (Generic) руками не нужно. Опечатка в имени поля становится ошибкой компиляции, а не ошибкой во время выполнения (runtime).

```txt
Компоненты Prisma:
  schema.prisma   — модели, связи, datasource, generator
  Prisma Client   — сгенерированный TypeScript API
                    (node_modules/.prisma/client)
  Prisma Migrate  — миграции: schema.prisma → SQL → база
  Prisma Studio   — графический интерфейс к данным (по желанию)

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
// Создание клиента (в NestJS — один экземпляр через PrismaService)
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient({
  log: ['query', 'error'], // логировать SQL-запросы в разработке
});

// CRUD — создать, прочитать, изменить, удалить
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
// prisma.service.ts — один общий экземпляр клиента на всё приложение
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
  ✓ проектов на TypeScript (NestJS, Next.js, Express + TS)
  ✓ приложений, где почти всё — это CRUD, то есть создать,
     прочитать, изменить, удалить (SaaS, админки, API)
  ✓ команд с разным уровнем SQL — типизация снижает ошибки
  ✓ быстрого старта: схема + миграция + готовый клиент
  ✓ GraphQL-бэкендов (Prisma + Pothos/Nexus = мало кода-обвязки)

Prisma не подходит или потребует обходных приёмов:
  ✗ сложные аналитические запросы: оконные функции,
     CTE (общие табличные выражения), LATERAL JOIN
     → решение: prisma.$queryRaw`SELECT ... OVER (PARTITION BY ...)`
  ✗ массовая вставка и обновление тысяч строк
     → createMany не поддерживает skipDuplicates со связями;
       для массовых операций: $executeRaw или pg-copy-streams
  ✗ динамические запросы с условными JOIN
     → TypeORM QueryBuilder в этом сценарии гибче
```

## $queryRaw и $executeRaw — когда нужен SQL

```typescript
// $queryRaw — вернуть типизированные результаты
// Внимание: шаблонный литерал (Prisma.sql) обязателен — защита от SQL-инъекций
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

// Никогда не использовать строковую интерполяцию:
// ✗ await prisma.$queryRaw(`SELECT * FROM users WHERE id = ${userId}`) // SQL-инъекция!
// ✓ await prisma.$queryRaw`SELECT * FROM users WHERE id = ${userId}`   // параметризованный
```

## Типичные ошибки на интервью

- **"Prisma — это база данных"** — нет. Prisma — это ORM поверх уже существующей базы. Данные хранит PostgreSQL, MySQL или SQLite, а Prisma только собирает и выполняет запросы к ним. Путь запроса: `prisma.user.findMany()` → Prisma Client → Query Engine на Rust → SQL → PostgreSQL.

- **"Prisma генерирует неэффективные запросы"** — частично правда для проблемы N+1, то есть когда на список из N записей уходит N+1 запросов. Но это лечится: `include` и `select` заставляют Prisma сделать `JOIN`. Для сложных запросов остаётся `$queryRaw`. Что именно уходит в базу, видно через `log: ['query']` в `PrismaClient`.

- **"PrismaClient можно создавать в каждом запросе"** — нет. `PrismaClient` держит пул соединений (connection pool), и каждый новый экземпляр открывает свой. В NestJS нужен один общий экземпляр: `PrismaService extends PrismaClient`. Новый экземпляр на каждый запрос — это утечка соединений и просадка производительности.

- **"Prisma Migrate и Prisma Client — одно и то же"** — нет. Migrate — инструмент разработчика, команда в терминале: `prisma migrate dev` генерирует SQL-миграции. Client — библиотека, которая работает во время выполнения и делает запросы к базе. В production запускают `prisma migrate deploy` — он применяет ещё не применённые миграции. Client к этому моменту уже собран в бандл приложения.

- **"После изменения schema.prisma изменения сразу доступны"** — нет, нужны два шага:
  - `prisma migrate dev` — создать миграцию и применить её к базе;
  - `prisma generate` — перегенерировать Client.

  Если изменить схему и не запустить `generate`, останутся старыми и типы TypeScript, и код клиента во время выполнения.
