# Prisma Migrations

## Зачем нужны миграции

Миграция — это версионированное изменение схемы БД. Без миграций три окружения (local, staging, production) постепенно расходятся, и выкатка нового кода ломается из-за несоответствия схем. Prisma Migrate хранит историю изменений в папке `prisma/migrations/` под git-контролем: каждое изменение — отдельный SQL-файл с таймстемпом.

```txt
Workflow:
  1. Изменить schema.prisma
  2. npx prisma migrate dev   → сгенерировать migration.sql + применить + regenerate Client
  3. git add prisma/migrations/  → зафиксировать migration в репозитории
  4. CI/CD: npx prisma migrate deploy  → применить pending migrations на production
```

## Команды Prisma Migrate

```bash
# Разработка — создать и применить migration (+ regenerate Client)
npx prisma migrate dev --name add_user_email
# → создаёт: prisma/migrations/20240101120000_add_user_email/migration.sql
# → применяет SQL к dev БД
# → запускает prisma generate

# Production / CI — применить pending migrations (без генерации, без интерактива)
npx prisma migrate deploy
# → читает prisma/migrations/ → находит непримененные → применяет по порядку
# → НЕ создаёт новых migrations, НЕ изменяет schema.prisma

# Просмотр статуса migrations
npx prisma migrate status
# → показывает applied / pending migrations

# Прототипирование — синхронизировать БД со schema.prisma БЕЗ создания migration файла
npx prisma db push
# Использовать только локально для PoC — теряет историю изменений!

# Сброс БД (только локально!)
npx prisma migrate reset
# → DROP all tables → apply all migrations from scratch → run seed
# НИКОГДА не запускать на production

# Генерация Client без migration
npx prisma generate
# Нужно после любого изменения schema.prisma без migrate dev
```

## Структура папки migrations

```txt
prisma/
└─ migrations/
   ├─ 20240101120000_init/
   │   └─ migration.sql          ← CREATE TABLE statements
   ├─ 20240115083000_add_email/
   │   └─ migration.sql          ← ALTER TABLE users ADD COLUMN email TEXT
   ├─ 20240201140000_add_posts/
   │   └─ migration.sql          ← CREATE TABLE posts + FK
   └─ migration_lock.toml        ← провайдер БД (не менять вручную)
```

```sql
-- Пример migration.sql
-- 20240115083000_add_email/migration.sql

-- AlterTable
ALTER TABLE "users" ADD COLUMN "email" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");
```

## Shadow Database — зачем нужна

```txt
Shadow Database — временная БД, которую Prisma создаёт при migrate dev:

1. Prisma применяет ВСЕ существующие migrations на Shadow DB
2. Применяет текущий state schema.prisma на Shadow DB
3. Сравнивает разницу → генерирует новую migration.sql
4. Удаляет Shadow DB

Зачем: чтобы сгенерировать ТОЧНЫЙ SQL diff.
Без Shadow DB: Prisma не знает текущее реальное состояние БД
(вдруг там есть изменения сделанные вручную?).

Настройка (обязательно для managed DB типа Supabase/PlanetScale):
datasource db {
  provider          = "postgresql"
  url               = env("DATABASE_URL")
  shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // отдельная dev БД
}
```

## CI/CD pipeline с Prisma

```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    steps:
      - name: Build
        run: npm run build

      - name: Run migrations
        run: npx prisma migrate deploy
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}

      - name: Start server
        run: npm start
```

```txt
Важно: порядок обязателен
  1. migrate deploy — ПЕРЕД стартом нового кода
  2. Новый код должен быть обратно совместим со СТАРОЙ схемой
     (в момент раскатки работают два экземпляра: старый и новый код)

Безопасная добавка колонки:
  Migration 1: ALTER TABLE ADD COLUMN name TEXT  (nullable — не ломает старый код)
  Deploy новый код (заполняет name)
  Migration 2: ALTER TABLE ALTER COLUMN name SET NOT NULL  (когда все записи заполнены)
```

## Опасные миграции — что проверять перед deploy

```sql
-- ОПАСНО: блокирует таблицу на всё время операции
ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;
-- На таблице 10M строк — блокировка на минуты

-- БЕЗОПАСНО: добавить nullable сначала, потом заполнить, потом NOT NULL
ALTER TABLE users ADD COLUMN age INT;  -- migration 1: nullable, мгновенно
-- (background job: UPDATE users SET age = 0 WHERE age IS NULL)
ALTER TABLE users ALTER COLUMN age SET NOT NULL;  -- migration 2: после заполнения

-- ОПАСНО: переименование поля — сломает работающий код
ALTER TABLE users RENAME COLUMN email TO email_address;
-- Правильно: добавить новую колонку → скопировать данные → убрать старую (3 migration)

-- ОПАСНО: DROP COLUMN с данными
ALTER TABLE users DROP COLUMN metadata;
-- Всегда проверять что колонка не используется в коде ДО migration
```

## Seeding — тестовые данные

```typescript
// prisma/seed.ts
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  // upsert вместо create — можно запускать несколько раз
  await prisma.user.upsert({
    where: { email: 'admin@example.com' },
    update: {},
    create: {
      email: 'admin@example.com',
      name: 'Admin',
      role: 'ADMIN',
    },
  });

  await prisma.user.createMany({
    data: Array.from({ length: 10 }, (_, i) => ({
      email: `user${i}@example.com`,
      name: `User ${i}`,
    })),
    skipDuplicates: true,
  });
}

main().finally(() => prisma.$disconnect());
```

```json
// package.json
{
  "prisma": {
    "seed": "ts-node prisma/seed.ts"
  }
}
```

```bash
npx prisma db seed          # запустить seed вручную
npx prisma migrate reset    # сброс + seed автоматически
```

## Типичные ошибки на интервью

- **"migrate dev можно использовать в production"** — нет. `migrate dev` создаёт Shadow DB, генерирует новые migrations, интерактивный режим. Для production: `migrate deploy` — только применяет pending migrations, не создаёт новых. В CI/CD всегда `migrate deploy`.

- **"Можно удалить migration файл если передумали"** — нельзя если migration уже применена на staging/production. Удаление нарушает историю. Правильный путь: создать новую migration которая отменяет изменения (reverse migration). Если migration ещё не применена нигде — можно удалить файл и `prisma migrate dev` пересоздаст.

- **"db push делает то же самое что migrate dev"** — нет. `db push` напрямую изменяет БД без создания migration файла. Нет истории, нельзя воспроизвести на другом окружении, не отслеживается в git. Использовать только для быстрого прототипирования локально.

- **"NOT NULL колонку можно добавить за один шаг"** — опасно на больших таблицах. `ADD COLUMN name TEXT NOT NULL DEFAULT 'value'` → PostgreSQL блокирует таблицу для перезаписи всех строк. Правило: добавить nullable → заполнить данными → сделать NOT NULL. Три отдельных migration с деплоями между ними.

- **"schema.prisma — это не настоящий source of truth, БД важнее"** — нет. В Prisma: schema.prisma — source of truth. migrations — история изменений schema. БД — результат применения migrations. Если БД и schema расходятся (ручные изменения в БД) — `prisma migrate dev` это обнаружит и попросит разрешить конфликт.
