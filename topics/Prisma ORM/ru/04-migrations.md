# Prisma Migrations

## Что такое миграция

Migration — это версия изменений структуры базы данных.

---

Например:

Было:

```prisma
model User {
  id Int @id
}
```

---

Стало:

```prisma
model User {
  id Int @id

  email String
}
```

---

Необходимо изменить структуру БД.

---

# Зачем нужны миграции

Без миграций:

```txt
локальная база
стейджинг
прод
```

начнут отличаться.

---

Миграции позволяют гарантировать одинаковую схему.

---

# Главная идея

Schema

↓

Migration

↓

SQL

↓

Database

---

# migrate dev

Основная команда разработки.

---

```bash
npx prisma migrate dev
```

---

Что происходит:

1. Prisma читает schema.prisma
2. Сравнивает с текущим состоянием БД
3. Генерирует SQL
4. Создает migration файл
5. Выполняет migration
6. Обновляет Prisma Client

---

# Пример

Добавили поле:

```prisma
email String
```

---

Prisma создаст:

```sql
ALTER TABLE users
ADD COLUMN email TEXT;
```

---

# Migration Folder

Появится:

```txt
prisma/
 └─ migrations/
     └─ 20250101120000_add_email/
```

---

Внутри:

```sql
migration.sql
```

---

# Почему это хорошо

SQL остается под контролем.

---

Можно посмотреть:

```sql
ALTER TABLE ...
```

---

И понять что реально изменится.

---

# migrate deploy

Production команда.

---

```bash
npx prisma migrate deploy
```

---

Используется на:

```txt
CI/CD
Production
Docker
```

---

# Важно

На production обычно НЕ используют:

```bash
migrate dev
```

---

Только:

```bash
migrate deploy
```

---

# db push

Очень любят спрашивать.

---

```bash
npx prisma db push
```

---

Отличие:

```txt
изменяет БД
НО
не создает migration
```

---

Полезно для:

```txt
прототипов
локальной разработки
PoC
```

---

Не рекомендуется для production.

---

# migrate reset

Полностью пересоздает БД.

---

```bash
npx prisma migrate reset
```

---

Делает:

```txt
DROP DATABASE
CREATE DATABASE
apply migrations
run seed
```

---

Используется только локально.

---

# Shadow Database

Очень популярный senior вопрос.

---

Prisma использует временную БД
для проверки миграций.

---

Называется:

```txt
Shadow Database
```

---

Она нужна чтобы:

```txt
проверить migration history
выявить конфликты
оценить diff
```

---

# Почему Shadow DB важна

Без нее можно случайно
сгенерировать некорректную миграцию.

---

# Что происходит в CI/CD

Обычно:

```bash
npm run build

npx prisma migrate deploy

npm start
```

---

# Что делать если migration упала в production

Очень популярный вопрос.

---

Нельзя:

```txt
удалять migration руками
```

---

Правильно:

1. исправить проблему
2. создать новую migration
3. применить новую migration

---

# Seed

Prisma поддерживает заполнение тестовыми данными.

---

Пример:

```bash
npx prisma db seed
```

---

Используется для:

```txt
users
roles
permissions
demo data
```

---

# Migration Best Practices

Не удалять старые migration.

---

Каждая migration должна быть:

```txt
маленькой
понятной
атомарной
```

---

Проверять generated SQL.

---

Особенно если:

```txt
DROP COLUMN
DROP TABLE
ALTER TYPE
```

---

# Частый вопрос

Что является source of truth?

---

Ответ:

```txt
schema.prisma
```

---

Не база данных.

Не migration folder.

---

Именно schema.prisma.

---

# Interview Answer

Prisma Migrate — это система управления версиями схемы базы данных. Изменения описываются в schema.prisma, после чего Prisma генерирует SQL миграции, которые могут быть применены локально через migrate dev и в production через migrate deploy.