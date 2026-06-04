# Prisma Fundamentals

## Что такое Prisma

Prisma — это TypeScript-first ORM toolkit.

Главная идея Prisma:

- описать структуру данных в schema.prisma
- автоматически сгенерировать типизированный клиент
- работать с базой через TypeScript API

---

# ORM

ORM = Object Relational Mapping.

---

Без ORM:

```sql
SELECT *
FROM users;
```

---

С ORM:

```ts
await prisma.user.findMany();
```

---

# Почему Prisma стала популярной

До Prisma чаще использовали:

- TypeORM
- Sequelize
- MikroORM

---

Prisma предложила:

```txt
Schema First
Strong Typing
Generated Client
Excellent DX
```

---

# Главная идея Prisma

Разработчик описывает модели:

```prisma
model User {
  id    Int    @id
  email String
}
```

---

После этого Prisma генерирует:

```ts
prisma.user.findMany()
prisma.user.create()
prisma.user.update()
prisma.user.delete()
```

---

# Из чего состоит Prisma

Prisma состоит из нескольких частей.

---

# Prisma Schema

Файл:

```txt
schema.prisma
```

---

Описывает:

- модели
- связи
- datasource
- generator

---

# Prisma Client

Сгенерированный TypeScript API.

---

Пример:

```ts
await prisma.user.findMany();
```

---

# Prisma Migrate

Система миграций.

---

Позволяет:

```txt
изменить schema
↓
сгенерировать SQL
↓
применить изменения
```

---

# Prisma Engine

Низкоуровневый слой,
который взаимодействует с базой данных.

---

# Архитектура

Frontend
↓
NestJS
↓
Prisma Client
↓
Prisma Engine
↓
PostgreSQL

---

# Почему Prisma не заменяет PostgreSQL

Очень важный вопрос.

---

Prisma НЕ хранит данные.

Prisma НЕ выполняет SQL самостоятельно.

---

Она генерирует запросы к базе данных.

---

То есть:

```txt
Prisma
=
абстракция над SQL
```

---

# Когда Prisma особенно хороша

- TypeScript проекты
- NestJS
- GraphQL
- CRUD-heavy приложения
- SaaS продукты

---

# Когда Prisma может быть неудобна

Очень сложные SQL запросы.

Например:

```txt
сложные аналитические запросы
оконные функции
нестандартные PostgreSQL возможности
```

Тогда используют:

```ts
$queryRaw
```

---

# Prisma Client Example

```ts
const users = await prisma.user.findMany();
```

---

Создание записи:

```ts
await prisma.user.create({
  data: {
    email: 'max@test.com',
  },
});
```

---

Обновление:

```ts
await prisma.user.update({
  where: {
    id: 1,
  },
  data: {
    name: 'Max',
  },
});
```

---

# Плюсы Prisma

- отличная типизация
- автокомплит
- простой API
- миграции
- удобство разработки

---

# Минусы Prisma

- дополнительный слой абстракции
- не всегда удобно для сложного SQL
- иногда нужен raw SQL

---

# Краткий ответ для интервью

Prisma — это TypeScript-first ORM toolkit, который использует schema-first подход. Разработчик описывает модели в schema.prisma, после чего Prisma генерирует типизированный клиент для работы с базой данных.