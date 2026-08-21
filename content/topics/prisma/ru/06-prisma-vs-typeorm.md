# Prisma против TypeORM

## Фундаментальная разница в подходе

Оба инструмента — это ORM (Object-Relational Mapping, «объектно-реляционное отображение»): слой, который переводит ваши классы и вызовы методов в SQL (Structured Query Language) — язык, на котором говорит база данных. Разница в том, **когда** строится это отображение.

TypeORM строит его в рантайме, то есть во время выполнения программы. Вы описываете сущности (Entity) с декораторами, а TypeORM собирает метаданные для SQL уже на ходу, через рефлексию (`reflect-metadata`). Типы частично выводятся из декораторов, поэтому часть ошибок компилятор не поймает.

Prisma работает по-другому: **сначала схема, потом кодогенерация** (schema-first). Вы описываете `schema.prisma`, а Prisma генерирует по ней полностью типизированный клиент. Все типы известны на этапе компиляции, а не во время выполнения. Изменили модель и не запустили `prisma generate` → сразу же ошибка TS.

```typescript
// TypeORM — подход через сущности с декораторами
import { Entity, PrimaryGeneratedColumn, Column, ManyToOne } from 'typeorm';

@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true })
  email: string;

  @Column({ nullable: true })
  name: string | null;

  @Column({ default: true })
  isActive: boolean;

  @OneToMany(() => Post, post => post.author)
  posts: Post[];
}

// TypeORM — Repository / QueryBuilder API
const userRepo = dataSource.getRepository(User);

const users = await userRepo.find({
  where: { isActive: true },
  relations: ['posts'],
  order: { createdAt: 'DESC' },
  take: 10,
});

// Сложный QueryBuilder (главное преимущество TypeORM)
const result = await userRepo
  .createQueryBuilder('u')
  .leftJoinAndSelect('u.posts', 'p')
  .where('u.isActive = :active', { active: true })
  .andWhere('p.publishedAt > :date', { date: new Date('2024-01-01') })
  .orderBy('u.createdAt', 'DESC')
  .skip(0)
  .take(20)
  .getManyAndCount();
```

```prisma
// Prisma — Schema (schema.prisma)
model User {
  id       String  @id @default(uuid())
  email    String  @unique
  name     String?
  isActive Boolean @default(true)
  posts    Post[]
  @@map("users")
}
```

```typescript
// Prisma — Client API
const users = await prisma.user.findMany({
  where: { isActive: true },
  include: { posts: true },
  orderBy: { createdAt: 'desc' },
  take: 10,
});

// Сложный запрос через $queryRaw (когда нет QueryBuilder)
const result = await prisma.$queryRaw<User[]>`
  SELECT u.*, COUNT(p.id)::int as post_count
  FROM users u
  LEFT JOIN posts p ON p.author_id = u.id AND p.published_at > '2024-01-01'
  WHERE u.is_active = true
  GROUP BY u.id
  ORDER BY u.created_at DESC
  LIMIT 20
`;
```

## Сравнительная таблица

```txt
                Prisma                  TypeORM
────────────────────────────────────────────────────────────────
Подход:         схема + кодогенерация   декораторы в рантайме
TypeScript:     отлично (компиляция)    хорошо (частью рантайм)
Автокомплит:    превосходный            хороший
Миграции:       авто (diff схемы)       авто + вручную, контроль
Query builder:  нет, только $queryRaw   мощный QueryBuilder
Сложные JOIN:   $queryRaw, многословно  QueryBuilder, чище
Скорость:       сопоставима             сопоставима
Документация:   отличная                хорошая, местами старая
Экосистема:     быстро растёт           зрелая, больше примеров
Новые проекты:  предпочтительно         реже
Старый код:     миграция дорогая        стабильно
```

## Где TypeORM выигрывает

```typescript
// 1. QueryBuilder — динамические сложные запросы
async function findUsers(filters: UserFilters) {
  const qb = userRepo.createQueryBuilder('u');

  if (filters.name) {
    qb.andWhere('u.name ILIKE :name', { name: `%${filters.name}%` });
  }
  if (filters.roleIds?.length) {
    qb.innerJoin('u.roles', 'r')
      .andWhere('r.id IN (:...roleIds)', { roleIds: filters.roleIds });
  }
  if (filters.hasPublishedPosts) {
    qb.innerJoin('u.posts', 'p', 'p.published = true');
  }

  return qb.orderBy('u.createdAt', 'DESC').getMany();
}
// В Prisma нет QueryBuilder → либо динамический объект where (возможности
// ограничены), либо $queryRaw со склейкой строк (небезопасно без Prisma.sql)

// 2. Паттерн ActiveRecord (если он используется в проекте)
class User extends BaseEntity {
  @PrimaryGeneratedColumn() id: number;
  static findByEmail(email: string) {
    return this.findOne({ where: { email } });
  }
}
await User.findByEmail('alice@example.com'); // прямо на модели
```

## Где Prisma выигрывает

```typescript
// 1. Типобезопасность — ошибки видны уже при компиляции
const user = await prisma.user.findUnique({
  where: { id: 1 },
  select: { email: true, naem: true }, // ошибка TS: поля 'naem' не существует
});
// Тип user: { email: string } | null — точно знаем, что вернётся

// TypeORM: User | null — вся сущность, даже если нужны только 2 поля
// + опечатка в имени поля упадёт уже во время выполнения

// 2. Вложенная запись (nested writes) — атомарные операции над связями
await prisma.user.create({
  data: {
    email: 'alice@example.com',
    posts: { create: [{ title: 'Hello' }] },
    profile: { create: { bio: 'Engineer' } },
  },
}); // одна транзакция, один поход в базу

// 3. select — точная выборка полей, без лишних данных
const publicUserData = await prisma.user.findMany({
  select: { id: true, name: true }, // никогда не вернёт пароли и токены
});
// Тип: { id: number; name: string | null }[]  — точный, не User[]
```

## Стратегия выбора

```txt
Выбирайте Prisma, когда:
  ✓ Новый проект на TypeScript (NestJS, Next.js, Express + TS)
  ✓ Команда ценит типобезопасность и удобство разработки
  ✓ Приложение в основном про CRUD (SaaS, API, админка)
  ✓ Запросы простые или средней сложности
  ✓ Нет старой кодовой базы на TypeORM

Выбирайте TypeORM, когда:
  ✓ Существующая кодовая база уже на TypeORM
  ✓ Много динамических сложных запросов (QueryBuilder критичен)
  ✓ Проект на JavaScript, без TypeScript — плюсы Prisma пропадают
  ✓ Нужен паттерн ActiveRecord
  ✓ Нужны фичи только TypeORM (наследование сущностей и т. п.)

На практике: два инструмента могут жить в одном проекте
  — Prisma для основного CRUD, $queryRaw для сложной аналитики
  — Или TypeORM для существующего кода + Prisma для новых модулей
```

## Типичные ошибки на интервью

- **"Prisma быстрее TypeORM"** — зависит от конкретного запроса. Оба генерируют SQL и передают его PostgreSQL. На одинаковых запросах разница в производительности минимальна. Главное различие — удобство разработки и типобезопасность, а не скорость во время выполнения.

- **"TypeORM устарел"** — нет. TypeORM активно поддерживается и работает в production. Prisma популярнее в новых проектах, но на TypeORM написано огромное количество кода, и экосистема у него зрелая. Оба инструмента рабочие.

- **"В Prisma нет QueryBuilder — это критичный минус"** — большинству CRUD-приложений хватает объекта `where`. CRUD — это create, read, update, delete: четыре обычные операции над записями. Сложные случаи закрывает `$queryRaw` с параметризованными запросами. QueryBuilder из TypeORM важен там, где запрос собирается очень динамично: десятки условий решаются во время выполнения.

- **"Миграции TypeORM надёжнее"** — не однозначно. Миграции TypeORM пишутся руками: больше контроля, но и больше места для человеческой ошибки. Prisma Migrate сама генерирует SQL-diff через Shadow Database и хранит версионированную историю. Мест для ошибки остаётся меньше. Для команд без глубокого опыта в SQL надёжнее Prisma Migrate.

- **"Переход с TypeORM на Prisma — быстрая операция"** — нет. Это полная замена слоя доступа к данным: Entity → model, репозитории → PrismaClient, декораторы → `schema.prisma`, QueryBuilder → Prisma API и `$queryRaw`. На большом проекте это недели работы с высоким риском регрессий. Стратегия одна: постепенная миграция по модулям.
