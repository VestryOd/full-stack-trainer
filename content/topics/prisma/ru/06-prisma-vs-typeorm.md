# Prisma vs TypeORM

## Фундаментальная разница в подходе

TypeORM: **runtime ORM** — описываешь Entity с декораторами, TypeORM строит SQL метаданные во время выполнения через reflection (`reflect-metadata`). Типизация частично выводится из decorators, но не все ошибки ловятся на этапе компиляции.

Prisma: **schema-first, code-generation** — описываешь `schema.prisma`, Prisma генерирует полностью типизированный клиент. Все типы — compile-time, не runtime. Изменение модели без `prisma generate` → немедленная ошибка TS.

```typescript
// TypeORM — Entity + Decorator подход
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
                    Prisma                      TypeORM
─────────────────────────────────────────────────────────
Подход:             Schema-first + codegen       Runtime decorators
TypeScript:         Excellent (compile-time)      Good (частично runtime)
Автокомплит:        Превосходный                 Хороший
Миграции:           Автоматические (schema diff)  Авто + ручные (надёжнее)
Query Builder:      Нет (только $queryRaw)        Мощный QueryBuilder
Сложные JOIN:       $queryRaw (verbose)           QueryBuilder (чище)
Производительность: Сопоставимо                  Сопоставимо
Документация:       Отличная                     Хорошая (но устаревшая)
Ecosystem:          Растёт быстро                 Зрелый, больше примеров
Новые проекты:      Предпочтительно              Реже
Legacy проекты:     Дорогая миграция              Стабильно
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
    qb.innerJoin('u.roles', 'r').andWhere('r.id IN (:...roleIds)', { roleIds: filters.roleIds });
  }
  if (filters.hasPublishedPosts) {
    qb.innerJoin('u.posts', 'p', 'p.published = true');
  }

  return qb.orderBy('u.createdAt', 'DESC').getMany();
}
// В Prisma: нет QueryBuilder → нужен либо динамический where object (ограничено)
// либо $queryRaw с ручной string concatenation (небезопасно без Prisma.sql)

// 2. ActiveRecord pattern (если используется)
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
// 1. Type Safety — ошибки на compile-time
const user = await prisma.user.findUnique({
  where: { id: 1 },
  select: { email: true, naem: true }, // TS ошибка: 'naem' не существует
});
// Тип user: { email: string } | null — точно знаем что вернётся

// TypeORM: User | null — весь Entity, даже если нужны только 2 поля
// + возможны runtime ошибки если опечатка в имени поля

// 2. Nested writes — атомарные операции над relations
await prisma.user.create({
  data: {
    email: 'alice@example.com',
    posts: { create: [{ title: 'Hello' }] },
    profile: { create: { bio: 'Engineer' } },
  },
}); // одна транзакция, один round-trip

// 3. select — точный projection без лишних данных
const publicUserData = await prisma.user.findMany({
  select: { id: true, name: true }, // никогда не вернёт password/tokens
});
// Тип: { id: number; name: string | null }[]  — точный, не User[]
```

## Стратегия выбора

```txt
Выбирай Prisma когда:
  ✓ Новый TypeScript проект (NestJS, Next.js, Express + TS)
  ✓ Команда ценит type safety и developer experience
  ✓ CRUD-heavy приложение (SaaS, API, admin panel)
  ✓ Простые или средней сложности запросы
  ✓ Нет legacy кодовой базы на TypeORM

Выбирай TypeORM когда:
  ✓ Существующая кодовая база уже на TypeORM
  ✓ Много динамических сложных запросов (QueryBuilder критичен)
  ✓ Проект на JavaScript (не TypeScript) — преимущества Prisma теряются
  ✓ Нужен ActiveRecord pattern
  ✓ Требуются специфические TypeORM-фичи (Entity inheritance, etc.)

Практика: можно использовать оба в одном проекте
  — Prisma для основного CRUD, $queryRaw для сложных аналитических запросов
  — Или TypeORM + Prisma для новых модулей
```

## Типичные ошибки на интервью

- **"Prisma быстрее TypeORM"** — зависит от конкретного запроса. Оба генерируют SQL и передают его PostgreSQL. Разница в производительности минимальна для одинаковых запросов. Главное различие — developer experience и type safety, не runtime performance.

- **"TypeORM устарел"** — нет. TypeORM активно поддерживается и используется в production. Prisma популярнее в новых проектах, но TypeORM имеет огромную кодовую базу и mature ecosystem. Оба инструмента валидны.

- **"В Prisma нет QueryBuilder — это критичный минус"** — для большинства CRUD приложений `where` объекта Prisma достаточно. `$queryRaw` с параметризованными запросами покрывает сложные кейсы. QueryBuilder TypeORM важен только при очень динамичном построении запросов (десятки условий в runtime).

- **"Миграции TypeORM надёжнее Prisma"** — не однозначно. TypeORM миграции более ручные (больше контроля, больше возможностей для ошибки). Prisma Migrate автоматически генерирует SQL diff с Shadow Database и хранит историю — меньше человеческих ошибок. Для команд без глубокого SQL опыта: Prisma Migrate надёжнее.

- **"Переход с TypeORM на Prisma — быстрая операция"** — нет. Это полная замена слоя доступа к данным: Entity → Model, Repositories → PrismaClient, декораторы → schema.prisma, QueryBuilder → Prisma API/$queryRaw. На большом проекте — недели работы с высоким риском регрессий. Стратегия: постепенная миграция по модулям.
