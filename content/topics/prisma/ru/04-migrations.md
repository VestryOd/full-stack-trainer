# Миграции в Prisma

## Зачем нужны миграции

Миграция — это версионированное изменение схемы базы данных. Без миграций три окружения (локальное, staging, production) постепенно расходятся, и выкатка нового кода ломается из-за несоответствия схем.

Prisma Migrate хранит историю изменений в папке `prisma/migrations/` под контролем git. Каждое изменение — отдельный файл на SQL (Structured Query Language — язык запросов к базе) с временной меткой в имени.

```txt
Как это работает:
  1. Изменить schema.prisma
  2. npx prisma migrate dev
     → создать migration.sql, применить его, обновить клиент
  3. git add prisma/migrations/
     → зафиксировать миграцию в репозитории
  4. В CI/CD: npx prisma migrate deploy
     → применить на production то, что ещё не применено
```

## Команды Prisma Migrate

```bash
# Разработка — создать и применить миграцию, обновить клиент
npx prisma migrate dev --name add_user_email
# → создаёт: prisma/migrations/20240101120000_add_user_email/migration.sql
# → применяет SQL к локальной базе
# → запускает prisma generate

# Production и CI — применить то, что ещё не применено
# (без генерации новых, без вопросов в терминале)
npx prisma migrate deploy
# → читает prisma/migrations/ → берёт неприменённые → применяет по порядку
# → не создаёт новых миграций и не меняет schema.prisma

# Статус миграций
npx prisma migrate status
# → показывает применённые и ожидающие миграции

# Прототип — подогнать базу под schema.prisma без файла миграции
npx prisma db push
# Только локально и только для черновика (PoC, proof of concept):
# история изменений при этом не сохраняется!

# Сброс базы (только локально!)
npx prisma migrate reset
# → удалить все таблицы → применить все миграции заново → залить seed
# Никогда не запускать на production

# Перегенерировать клиент без миграции
npx prisma generate
# Нужно после любого изменения schema.prisma без migrate dev
```

## Структура папки migrations

```txt
prisma/
└─ migrations/
   ├─ 20240101120000_init/
   │   └─ migration.sql          ← команды CREATE TABLE
   ├─ 20240115083000_add_email/
   │   └─ migration.sql          ← ALTER TABLE users ADD COLUMN
   ├─ 20240201140000_add_posts/
   │   └─ migration.sql          ← CREATE TABLE posts + внешний ключ
   └─ migration_lock.toml        ← вид базы (руками не менять)
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

Shadow Database, или теневая база, — это временная база, которую Prisma создаёт на время работы `migrate dev` и потом удаляет. Нужна она затем, чтобы получить точную разницу (diff) между схемой и историей миграций.

```txt
Что происходит при migrate dev:

1. Prisma применяет к теневой базе все существующие миграции
2. Применяет к ней же текущее состояние schema.prisma
3. Сравнивает результаты → пишет новый migration.sql
4. Удаляет теневую базу

Без теневой базы Prisma не знает реального состояния схемы:
а если в базу кто-то внёс изменения руками?

Настройка (обязательна для облачных баз вроде Supabase
и PlanetScale):
datasource db {
  provider          = "postgresql"
  url               = env("DATABASE_URL")
  shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // отдельная база
}
```

## Миграции в CI/CD

CI/CD — это continuous integration и continuous delivery, то есть автоматическая сборка и выкатка. Миграции в такой сборке применяются отдельным шагом, до запуска нового кода.

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
  1. migrate deploy — до старта нового кода, не после
  2. Новый код должен работать и со старой схемой тоже:
     в момент раскатки живут два экземпляра, старый и новый

Как безопасно добавить колонку:
  Миграция 1: ALTER TABLE ADD COLUMN name TEXT
              (допускает NULL — старый код не ломается)
  Деплой нового кода, который заполняет name
  Миграция 2: ALTER TABLE ALTER COLUMN name SET NOT NULL
              (когда все строки уже заполнены)
```

## Опасные миграции — что проверять перед деплоем

```sql
-- Опасно: таблица заблокирована на всё время операции
ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;
-- На таблице в 10 млн строк это блокировка на минуты

-- Безопасно: сначала NULL, потом заполнить, потом NOT NULL
ALTER TABLE users ADD COLUMN age INT;  -- миграция 1: мгновенно
-- (фоновая задача: UPDATE users SET age = 0 WHERE age IS NULL)
ALTER TABLE users ALTER COLUMN age SET NOT NULL;  -- миграция 2

-- Опасно: переименование поля ломает работающий код
ALTER TABLE users RENAME COLUMN email TO email_address;
-- Правильно: новая колонка → скопировать данные → убрать старую,
-- то есть три отдельные миграции

-- Опасно: DROP COLUMN с данными
ALTER TABLE users DROP COLUMN metadata;
-- Сначала убедиться, что колонка не нужна коду, и только потом миграция
```

## Заливка тестовых данных — seed

```typescript
// prisma/seed.ts
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  // upsert вместо create — сид можно запускать много раз подряд
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
npx prisma db seed          # залить тестовые данные вручную
npx prisma migrate reset    # сброс базы, и seed запустится сам
```

## Типичные ошибки на интервью

- **"migrate dev можно использовать в production"** — нет. `migrate dev` создаёт теневую базу, генерирует новые миграции и задаёт вопросы в терминале. Для production есть `migrate deploy`: он только применяет неприменённые миграции и новых не создаёт. В CI/CD всегда `migrate deploy`.

- **"Можно удалить файл миграции, если передумали"** — нельзя, если миграция уже применена на staging или production: удаление файла ломает историю. Правильный путь — новая миграция, которая отменяет изменения (обратная, reverse migration). Если миграция ещё нигде не применялась, файл можно удалить: `prisma migrate dev` создаст его заново.

- **"db push делает то же самое, что migrate dev"** — нет. `db push` меняет базу напрямую и файла миграции не создаёт. Значит: нет истории, нельзя повторить на другом окружении, ничего не видно в git. Годится только для быстрого прототипа на своей машине.

- **"Колонку `NOT NULL` можно добавить за один шаг"** — на больших таблицах это опасно. `ADD COLUMN name TEXT NOT NULL DEFAULT 'value'` заставляет PostgreSQL заблокировать таблицу и перезаписать все строки. Правило: добавить колонку с `NULL` → заполнить данными → включить `NOT NULL`. Это три отдельные миграции с деплоями между ними.

- **"schema.prisma — не настоящий источник истины, база важнее"** — нет. В Prisma источник истины (source of truth) — это `schema.prisma`. Миграции — история его изменений, а база — результат их применения. Если база и схема разошлись из-за ручных правок, `prisma migrate dev` это заметит и попросит разрешить конфликт.
