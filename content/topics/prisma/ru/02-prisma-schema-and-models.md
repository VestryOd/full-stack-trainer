<!-- verified: 2026-06-05, corrections: 0 -->
# Prisma Schema and Models

## Главный файл Prisma

Весь проект строится вокруг:

```txt
schema.prisma
```

---

# Структура schema.prisma

Обычно состоит из:

```prisma
datasource db {}

generator client {}

model User {}
```

---

# Datasource

Описывает подключение к базе.

Пример:

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

---

# Generator

Генерирует Prisma Client.

```prisma
generator client {
  provider = "prisma-client-js"
}
```

---

# Model

Описывает таблицу.

Пример:

```prisma
model User {
  id    Int
  email String
}
```

---

# Как Prisma превращает модель в таблицу

Модель:

```prisma
model User {
  id    Int    @id
  email String
}
```

---

Превращается примерно в:

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL
);
```

---

# Основные типы

## String

```prisma
name String
```

---

## Int

```prisma
age Int
```

---

## Boolean

```prisma
active Boolean
```

---

## DateTime

```prisma
createdAt DateTime
```

---

## Float

```prisma
price Float
```

---

## Json

```prisma
settings Json
```

---

# Nullable поля

Обозначаются через:

```prisma
String?
```

---

Пример:

```prisma
middleName String?
```

---

SQL аналог:

```sql
NULL
```

---

# Primary Key

```prisma
id Int @id
```

---

# Auto Increment

```prisma
id Int @id @default(autoincrement())
```

---

SQL:

```sql
SERIAL
```

---

# UUID

Очень популярно.

```prisma
id String @id @default(uuid())
```

---

# Unique

```prisma
email String @unique
```

---

SQL:

```sql
UNIQUE(email)
```

---

# Default

```prisma
createdAt DateTime @default(now())
```

---

# UpdatedAt

Очень популярная штука.

```prisma
updatedAt DateTime @updatedAt
```

---

Prisma обновляет поле автоматически.

---

# Enum

Пример:

```prisma
enum UserRole {
  ADMIN
  USER
}
```

---

Использование:

```prisma
role UserRole
```

---

# Индексы

Простой индекс:

```prisma
@@index([email])
```

---

Составной индекс:

```prisma
@@index([email, createdAt])
```

---

Уникальный составной индекс:

```prisma
@@unique([userId, roleId])
```

---

# Mapping

Иногда имя модели отличается от имени таблицы.

---

Например:

```prisma
model User {
  id Int @id
  @@map("users")
}
```

---

# Поле тоже можно переименовать

```prisma
email String @map("email_address")
```

---

# Полная модель

```prisma
model User {
  id        String   @id @default(uuid())
  email     String   @unique
  name      String?
  isActive  Boolean  @default(true)

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  @@index([email])
}
```

---

# Что происходит после изменения схемы

Изменяем:

```prisma
name String?
```

---

Запускаем:

```bash
npx prisma migrate dev
```

---

Prisma:

1. Сравнивает схему
2. Генерирует SQL
3. Создает migration
4. Применяет изменения
5. Генерирует новый Prisma Client

---

# Частый вопрос

Что является source of truth?

Ответ:

schema.prisma.

Именно схема считается основным описанием структуры данных.

---

# Краткий ответ для интервью

Schema.prisma — центральный файл Prisma. В нем описываются модели, связи, datasource и настройки генерации клиента. На основе schema.prisma Prisma создает миграции и генерирует полностью типизированный Prisma Client.
