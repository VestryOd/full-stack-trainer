# Prisma vs TypeORM

## Fundamental difference in approach

TypeORM: **runtime ORM** — you describe Entities with decorators, TypeORM builds SQL metadata at runtime via reflection (`reflect-metadata`). Typing is partly inferred from decorators, but not all errors are caught at compile time.

Prisma: **schema-first, code-generation** — you describe `schema.prisma`, Prisma generates a fully typed client. All types are compile-time, not runtime. Changing a model without `prisma generate` → immediate TS error.

```typescript
// TypeORM — Entity + Decorator approach
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

// Complex QueryBuilder (TypeORM's main advantage)
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

// Complex query via $queryRaw (when there is no QueryBuilder)
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

## Comparison table

```txt
                    Prisma                        TypeORM
────────────────────────────────────────────────────────────
Approach:           Schema-first + codegen         Runtime decorators
TypeScript:         Excellent (compile-time)        Good (partly runtime)
Autocomplete:       Excellent                       Good
Migrations:         Automatic (schema diff)         Auto + manual (more control)
Query Builder:      None (only $queryRaw)           Powerful QueryBuilder
Complex JOINs:      $queryRaw (verbose)             QueryBuilder (cleaner)
Performance:        Comparable                      Comparable
Documentation:      Excellent                       Good (some parts outdated)
Ecosystem:          Growing fast                    Mature, more examples
New projects:       Preferred                       Less common
Legacy projects:    Costly migration                Stable
```

## Where TypeORM wins

```typescript
// 1. QueryBuilder — dynamic complex queries
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
// In Prisma: no QueryBuilder → either a dynamic where object (limited)
// or $queryRaw with manual string concatenation (unsafe without Prisma.sql)

// 2. ActiveRecord pattern (if used)
class User extends BaseEntity {
  @PrimaryGeneratedColumn() id: number;
  static findByEmail(email: string) {
    return this.findOne({ where: { email } });
  }
}
await User.findByEmail('alice@example.com'); // directly on the model
```

## Where Prisma wins

```typescript
// 1. Type Safety — errors at compile time
const user = await prisma.user.findUnique({
  where: { id: 1 },
  select: { email: true, naem: true }, // TS error: 'naem' does not exist
});
// Type of user: { email: string } | null — precisely known at compile time

// TypeORM: User | null — the full Entity, even if only 2 fields are needed
// + possible runtime errors from typos in field names

// 2. Nested writes — atomic operations over relations
await prisma.user.create({
  data: {
    email: 'alice@example.com',
    posts: { create: [{ title: 'Hello' }] },
    profile: { create: { bio: 'Engineer' } },
  },
}); // one transaction, one round-trip

// 3. select — precise projection without extra data
const publicUserData = await prisma.user.findMany({
  select: { id: true, name: true }, // will never return password/tokens
});
// Type: { id: number; name: string | null }[]  — exact, not User[]
```

## Decision strategy

```txt
Choose Prisma when:
  ✓ New TypeScript project (NestJS, Next.js, Express + TS)
  ✓ Team values type safety and developer experience
  ✓ CRUD-heavy application (SaaS, API, admin panel)
  ✓ Simple to moderately complex queries
  ✓ No existing TypeORM codebase

Choose TypeORM when:
  ✓ Existing codebase is already on TypeORM
  ✓ Many dynamic complex queries (QueryBuilder is critical)
  ✓ JavaScript project (not TypeScript) — Prisma's advantages disappear
  ✓ ActiveRecord pattern is required
  ✓ TypeORM-specific features are needed (Entity inheritance, etc.)

In practice: both can coexist in one project
  — Prisma for main CRUD, $queryRaw for complex analytical queries
  — Or TypeORM for the existing codebase + Prisma for new modules
```

## Common interview mistakes

- **"Prisma is faster than TypeORM"** — depends on the specific query. Both generate SQL and hand it to PostgreSQL. Performance difference is negligible for equivalent queries. The main difference is developer experience and type safety, not runtime performance.

- **"TypeORM is outdated"** — no. TypeORM is actively maintained and used in production. Prisma is more popular in new projects, but TypeORM has a huge installed base and a mature ecosystem. Both tools are valid.

- **"No QueryBuilder in Prisma is a critical drawback"** — for most CRUD applications, Prisma's `where` object is sufficient. `$queryRaw` with parameterized queries covers complex cases. TypeORM's QueryBuilder matters mainly for highly dynamic query construction (many runtime conditions).

- **"TypeORM migrations are more reliable than Prisma's"** — not clear-cut. TypeORM migrations are more manual (more control, more room for human error). Prisma Migrate automatically generates a SQL diff using a Shadow Database and keeps a versioned history — fewer human mistakes. For teams without deep SQL expertise: Prisma Migrate is more reliable.

- **"Migrating from TypeORM to Prisma is quick"** — no. It is a full replacement of the data access layer: Entity → Model, Repositories → PrismaClient, decorators → schema.prisma, QueryBuilder → Prisma API/$queryRaw. On a large project — weeks of work with high regression risk. Strategy: incremental migration module by module.
