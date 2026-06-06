<!-- verified: 2026-06-05, corrections: 0 -->
# Prisma vs TypeORM

## Самый популярный вопрос

Почему многие команды переходят с TypeORM на Prisma?

---

# Главная разница

TypeORM:

```txt
Runtime ORM
```

---

Prisma:

```txt
Schema First ORM
```

---

# TypeORM

Описываем Entity.

---

```ts
@Entity()
export class User {

  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  email: string;
}
```

---

TypeORM строит метаданные во время выполнения.

---

# Prisma

Описываем схему.

---

```prisma
model User {
  id Int @id
  email String
}
```

---

После этого Prisma генерирует Client.

---

# Type Safety

Огромный плюс Prisma.

---

TypeORM:

```txt
часть типов проверяется runtime
```

---

Prisma:

```txt
максимум ошибок ловится compile-time
```

---

# Autocomplete

Prisma обычно выигрывает.

---

Например:

```ts
prisma.user.findMany({
  select: {
```

IDE сразу показывает поля модели.

---

# Миграции

TypeORM:

```txt
часто приходится писать вручную
```

---

Prisma:

```txt
schema
↓
migration
↓
sql
```

---

Обычно проще.

---

# Сложные запросы

Здесь преимущество часто у TypeORM.

---

TypeORM имеет Query Builder.

---

```ts
createQueryBuilder()
```

---

Можно строить очень сложные запросы.

---

Prisma иногда требует:

```ts
$queryRaw()
```

---

# Learning Curve

Prisma проще изучить.

---

Особенно frontend/fullstack разработчикам.

---

# Production Experience

Сегодня большинство новых TypeScript проектов выбирают:

```txt
NestJS
+
Prisma
+
PostgreSQL
```

---

# Когда выбрать Prisma

- новый проект
- TypeScript
- CRUD-heavy приложение
- SaaS

---

# Когда выбрать TypeORM

- legacy проект
- сложные query builders
- уже есть большая кодовая база

---

# Таблица сравнения

| | Prisma | TypeORM |
|---|---|---|
| Typing | Excellent | Good |
| DX | Excellent | Good |
| Migrations | Excellent | Average |
| Learning Curve | Easy | Medium |
| Raw SQL | Supported | Supported |
| Query Builder | Limited | Strong |
| Popularity (new projects) | High | Medium |

---

# Interview Answer

Prisma использует schema-first подход и генерирует типизированный клиент, тогда как TypeORM строит ORM-модель во время выполнения через decorators и entities. Prisma обычно обеспечивает лучший TypeScript DX и более предсказуемую типизацию, а TypeORM предоставляет больше гибкости для сложных ORM-сценариев.
