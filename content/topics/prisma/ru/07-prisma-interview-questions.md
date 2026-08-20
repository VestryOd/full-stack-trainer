# Prisma — вопросы на интервью (уровень senior)

## Группа 1: архитектура и подход

**В чём принципиальное отличие Prisma от TypeORM?**

Оба инструмента связывают ваш код с таблицами, но делают это в разные моменты. TypeORM — во время выполнения программы, Prisma — заранее, генерацией кода. Оба они ORM (Object-Relational Mapping, «объектно-реляционное отображение»): слой, который переводит классы и вызовы методов в SQL (Structured Query Language) — язык, на котором говорит база данных.

```typescript
// TypeORM — сущности с декораторами, метаданные читаются во время выполнения
@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid') id: string;
  @Column({ unique: true }) email: string;
}
const users = await userRepo.find({ where: { isActive: true } });
// Тип users: User[] — вся сущность, даже если нужны два поля

// Prisma — клиент сгенерирован из schema.prisma
const user = await prisma.user.findUnique({
  where: { id: 1 },
  select: { email: true, naem: true }, // ошибка TS: поля 'naem' нет
});
// Тип user: { email: string } | null — известен ещё при компиляции
```

- **TypeORM** работает в рантайме: сущности с декораторами, метаданные собираются во время выполнения через `reflect-metadata`. Часть ошибок обнаруживается только там же, в рантайме.
- **Prisma** идёт от схемы к коду (schema-first): `schema.prisma` → `prisma generate` → типизированный клиент. Все типы известны при компиляции, поэтому опечатка в имени поля — ошибка TS, а не падение в рантайме.
- **Плюс Prisma** — точный вывод типов: возвращается `{ id: number; email: string }`, а не `User`. Ваша IDE (Integrated Development Environment — редактор кода) подскажет ровно эти поля.
- **Плюс TypeORM** — QueryBuilder для запросов, которые собираются динамически.

---

**Что происходит, когда вы изменяете schema.prisma?**

Само по себе — ничего. Файл только описывает желаемое состояние, а превращают его в реальность две команды.

```bash
# 1. Создать миграцию и применить её
npx prisma migrate dev --name add_user_email
# → сравнивает схему с текущим состоянием БД через Shadow Database
# → пишет prisma/migrations/20240101120000_add_user_email/migration.sql
# → применяет этот SQL к базе разработчика
# → сам запускает prisma generate

# 2. Только перегенерировать клиент, без миграции
npx prisma generate
# Нужно после любого изменения schema.prisma без migrate dev
```

- `prisma migrate dev` сравнивает схему с текущим состоянием БД (базы данных). Затем генерирует файл SQL-миграции и применяет его к базе разработчика.
- `prisma generate` перегенерирует клиент TypeScript. Внутри `migrate dev` это происходит автоматически.

Пропустите `generate` — типы TypeScript останутся старыми, и редактор начнёт подчёркивать поля, которые на самом деле есть. Пропустите `migrate dev` — база разойдётся со схемой.

---

**Что такое Shadow Database и зачем она нужна?**

Shadow Database («теневая база») — временная база данных, которую Prisma создаёт во время `migrate dev`. Она нужна, чтобы вычислить точную разницу между историей миграций и текущей схемой.

```txt
Shadow Database — временная БД на время работы migrate dev:

1. Prisma применяет к ней все существующие миграции
2. Применяет к ней текущее состояние schema.prisma
3. Сравнивает два состояния → генерирует новый migration.sql
4. Удаляет теневую базу

Без неё Prisma не знает реального состояния основной БД:
там могут быть правки, сделанные руками и не описанные ни одной
миграцией.
```

Для управляемых баз вроде Supabase или PlanetScale теневую базу нужно указать отдельно:

```prisma
datasource db {
  provider          = "postgresql"
  url               = env("DATABASE_URL")
  shadowDatabaseUrl = env("SHADOW_DATABASE_URL") // отдельная база для разработки
}
```

---

**Что такое PrismaClient и как правильно его инициализировать в NestJS?**

PrismaClient — сгенерированный класс TypeScript, через который идут все запросы. Он управляет пулом соединений и передаёт запросы в Prisma Query Engine — нативный бинарник на Rust.

```typescript
// prisma.service.ts — стандартный синглтон в NestJS
@Injectable()
export class PrismaService extends PrismaClient
  implements OnModuleInit, OnModuleDestroy {
  async onModuleInit() {
    await this.$connect();
  }

  async onModuleDestroy() {
    await this.$disconnect();
  }
}

// prisma.module.ts — @Global(), чтобы один экземпляр видели все модули
@Global()
@Module({ providers: [PrismaService], exports: [PrismaService] })
export class PrismaModule {}
```

- В NestJS экземпляр строго один: синглтон `PrismaService extends PrismaClient`, зарегистрированный как `@Global()`-модуль.
- `OnModuleInit` → `$connect()`, `OnModuleDestroy` → `$disconnect()`.
- Создавать `new PrismaClient()` на каждый запрос нельзя: это утечка соединений и просадка производительности, потому что каждый экземпляр открывает свой пул.

---

## Группа 2: схема и модели

**Когда использовать UUID вместо autoincrement и наоборот?**

Для внутренних идентификаторов, по которым вы соединяете таблицы, берите `autoincrement`, а для тех, что торчат в публичном API, — `uuid`. UUID (Universally Unique Identifier) — случайное 128-битное значение вместо счётчика.

```prisma
model Order {
  id       Int    @id @default(autoincrement())  // внутренний: 4 байта, по порядку
  publicId String @unique @default(uuid())       // виден в /orders/:publicId
}
```

- **Что даёт UUID:**
  - нет предсказуемой последовательности, поэтому чужой идентификатор нельзя угадать по своему — это безопаснее для публичных API;
  - значение можно сгенерировать на клиенте, ещё до вставки;
  - легко сливать данные из нескольких баз.
- **Чем UUID расплачивается:** 16 байт вместо 4 и худшая локальность в B-дереве индекса. Новые записи попадают не только в конец индекса. Из-за этого случаются расщепления страниц (page splits): база разрывает заполненную страницу индекса на две.
- **Что даёт autoincrement:** компактный ключ, предсказуемый порядок и лучшую скорость индекса при массовых вставках.
- **Правило:** внутренние идентификаторы для соединений → `autoincrement`; публичные ресурсы вида `/users/:id` → `uuid`.
- **Между этими крайностями:** ULID (Universally Unique Lexicographically Sortable Identifier) и CUID (Collision-resistant Unique Identifier). Они остаются уникальными, но ещё и сортируются по времени создания.

---

**Почему Decimal, а не Float для денежных значений?**

Потому что `Float` не хранит большинство десятичных дробей точно, а деньги — это как раз десятичные дроби.

```prisma
model Payment {
  wrongAmount Float                       // ✗ 0.1 + 0.2 = 0.30000000000000004
  amount      Decimal @db.Decimal(10, 2)  // ✓ точно: 10 цифр, 2 после запятой
  amountCents Int                         // ✓ альтернатива: хранить копейки
}
```

- `Float` — число двойной точности в формате `IEEE 754`, стандарте двоичной плавающей запятой почти во всех языках. Он даёт ошибки округления.
- В финансовых расчётах эти ошибки накапливаются и всплывают расхождениями в копейках и центах.
- `Decimal @db.Decimal(10, 2)` — точная фиксированная точность, без ошибок представления.
- Альтернатива — хранить деньги целыми числами: копейки или центы в поле `Int`. Тогда вопрос про Float не возникает вообще.
- В коде для арифметики со значениями Prisma `Decimal` используйте `Decimal.js`.

---

**Когда добавлять индекс, а когда нет?**

Индексируйте те колонки, по которым вы действительно фильтруете и сортируете, и не трогайте те, которые планировщик всё равно проигнорирует.

```prisma
model Post {
  id        Int      @id @default(autoincrement())
  authorId  Int
  status    String   @default("draft")
  createdAt DateTime @default(now())

  @@index([authorId])                       // внешний ключ — индексировать всегда
  @@index([status, createdAt(sort: Desc)])  // составной, с направлением сортировки
}
```

- **Индекс нужен:**
  - на поля внешнего ключа, FK (Foreign Key) — всегда, потому что Prisma не создаёт индексы для FK сама;
  - на поля в частых условиях `WHERE`: email, status, userId;
  - на поля в `ORDER BY`, если в запросе есть и другие условия `WHERE`.
- **Индекс не нужен:**
  - на boolean-поля с низкой кардинальностью вроде `isActive = true/false` — планировщик часто игнорирует такой индекс и делает seq scan, то есть читает таблицу целиком;
  - на поля, по которым реальных запросов нет: каждый индекс замедляет `INSERT` и `UPDATE`;
  - на колонку, которую уже покрывает начало существующего составного индекса.

---

## Группа 3: связи и запросы

**Объясните разницу между implicit и explicit Many-to-Many.**

В неявной связи «многие ко многим», M2M (Many-to-Many), Prisma сама создаёт и скрывает связующую таблицу. В явной вы описываете эту таблицу сами, обычной моделью.

```prisma
// Неявная M2M — связующей модели нет, Prisma создаёт "_PostToTag" сама
model Post {
  id   Int   @id @default(autoincrement())
  tags Tag[]
}
model Tag {
  id    Int    @id @default(autoincrement())
  posts Post[]
}

// Явная M2M — связующая таблица описана моделью и может нести поля
model UserRole {
  userId     Int
  roleId     Int
  assignedAt DateTime @default(now())
  assignedBy String?

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
  role Role @relation(fields: [roleId], references: [id], onDelete: Cascade)

  @@id([userId, roleId])
  @@index([roleId])
}
```

- **Неявная** проще, но скрытая таблица недоступна. Добавить в неё поля нельзя, запросить её напрямую через Prisma API тоже нельзя.
- **Явная** — рекомендация для production. Контроля больше, поля вроде `assignedAt` или `assignedBy` добавляются без сложных миграций, а `prisma.userRole.findMany()` читает связующую таблицу напрямую.
- Неявную связь берите только для совсем простых случаев, где никаких дополнительных данных нет.

---

**В чём разница между include и select и можно ли их комбинировать?**

`include` отдаёт модель целиком плюс перечисленные связи, а `select` — только перечисленные поля. На одном уровне работает что-то одно, зато внутри `select` может быть вложенный `select`.

```typescript
// include: все поля User + все связанные записи Post
const a = await prisma.user.findUnique({
  where: { id: 1 },
  include: { posts: true },
});

// select: только перечисленные поля, связи — только если их тоже перечислить
const b = await prisma.user.findMany({
  select: { id: true, posts: { select: { title: true } } },
});

// ✗ include и select на одном уровне → ошибка TypeScript
// { include: { posts: true }, select: { id: true } }
```

По производительности `select` лучше как выбор по умолчанию:

- он не грузит поля, которых вы не просили, включая пароли и токены;
- по сети идёт меньше данных;
- тип TypeScript получается точным, а не «вся сущность целиком».

---

**Что такое N+1 и как его диагностировать и исправить в Prisma?**

N+1 — это один запрос за списком плюс ещё по одному запросу на каждый элемент списка, обычно внутри цикла. Для диагностики включите `log: ['query']` и посчитайте SQL-запросы на один HTTP-запрос.

```typescript
// Диагностика: все SQL-запросы одного HTTP-запроса видны в консоли
const prisma = new PrismaClient({ log: ['query'] });

// ПРОБЛЕМА: 1 запрос за пользователями + N запросов за счётчиками
const users = await prisma.user.findMany();
for (const user of users) {
  const count = await prisma.post.count({ where: { authorId: user.id } });
}

// РЕШЕНИЕ 1: include — всё одним запросом с JOIN
const withPosts = await prisma.user.findMany({
  include: { posts: { select: { id: true } } },
});

// РЕШЕНИЕ 2: groupBy + _count — агрегация одним запросом
const counts = await prisma.post.groupBy({
  by: ['authorId'],
  _count: { id: true },
});

// РЕШЕНИЕ 3: $queryRaw с явным LEFT JOIN ... GROUP BY
const rows = await prisma.$queryRaw<{ id: number; post_count: number }[]>`
  SELECT u.id, COUNT(p.id)::int AS post_count
  FROM users u LEFT JOIN posts p ON p.author_id = u.id
  GROUP BY u.id
`;
```

- **Решение 4, о котором забывают:** два запроса, где второй идёт с `WHERE id IN (...)`. Иногда это дешевле одного тяжёлого `JOIN`.

Главная ловушка — глубоко вложенный `include`. Цепочка `user → posts → comments → author` может дать декартово произведение: все комбинации строк из соединяемых таблиц. Это хуже, чем исходная проблема N+1.

---

## Группа 4: транзакции и производительность

**Когда использовать Sequential $transaction, а когда Interactive?**

Sequential — когда операции независимы и все данные известны заранее. Interactive — когда следующему шагу нужен результат предыдущего.

```typescript
// Sequential — массив операций, результатов между ними нет
const [user, profile] = await prisma.$transaction([
  prisma.user.create({ data: { email: 'alice@example.com' } }),
  prisma.profile.create({ data: { bio: 'Engineer', userId: 1 } }),
]);

// Interactive — колбэк: user.id доступен на следующем шаге
await prisma.$transaction(async (tx) => {
  const user = await tx.user.create({ data: { email: 'bob@example.com' } });
  await tx.profile.create({ data: { bio: 'Engineer', userId: user.id } });

  const account = await tx.account.findUnique({ where: { userId: user.id } });
  if (!account) throw new Error('No account'); // → автоматический ROLLBACK
}, {
  timeout: 5000,   // мс: лимит на всю транзакцию
  maxWait: 2000,   // мс: сколько ждать соединение из пула
  isolationLevel: 'Serializable',
});
```

- **Sequential** (`$transaction([op1, op2])`) быстрее: не нужно держать транзакцию открытой, пока работает ваш код. Ограничение то же самое: результат `op1` недоступен в `op2`. Порядок выполнения при этом гарантирован, хотя PostgreSQL во время выполнения может оптимизировать запросы.
- **Interactive** (`$transaction(async tx => { ... })`) нужен для цепочек: создать User → взять его id → создать Profile. Внутри можно ветвить логику, а брошенный Error превращается в автоматический ROLLBACK.
- Параметры: `timeout` (максимальное время всей транзакции), `maxWait` (сколько ждать соединение из пула) и `isolationLevel`.

---

**Как реализовать `SELECT FOR UPDATE` в Prisma?**

Встроенного API для `FOR UPDATE` в Prisma нет, поэтому его пишут как `$queryRaw` внутри `$transaction`.

```typescript
await prisma.$transaction(async (tx) => {
  const [row] = await tx.$queryRaw`
    SELECT * FROM accounts WHERE id = ${id} FOR UPDATE
  `;
  // строка заблокирована — другие транзакции ждут эту
  await tx.account.update({
    where: { id },
    data: { balance: { decrement: amount } },
  });
});
```

Зачем эта блокировка. Две параллельные транзакции читают одну строку и обе видят `balance=100`. Обе списывают, и на счёте оказывается $0 вместо ошибки у одной из них. `FOR UPDATE` блокирует строку, поэтому второй `SELECT FOR UPDATE` ждёт, пока первая транзакция завершится.

---

**Как правильно настроить пул соединений для production?**

Параметрами в строке подключения `DATABASE_URL`: `?connection_limit=20&pool_timeout=10`.

```typescript
const prisma = new PrismaClient({
  datasources: {
    db: {
      url: `${process.env.DATABASE_URL}?connection_limit=20&pool_timeout=10`,
    },
  },
});
```

- `connection_limit` — максимум соединений. До Prisma 6 по умолчанию `num_physical_cpus * 2 + 1`. С Prisma 7 значение задаёт драйверный адаптер, и обычно это 10.
- `pool_timeout` — сколько секунд ждать соединение из пула, прежде чем упасть с ошибкой. По умолчанию 10.
- Для serverless (Lambda, Vercel): `connection_limit=1`, по одному соединению на экземпляр функции. Иначе тысячи холодных стартов откроют тысячи соединений.
- Там же поставьте перед PostgreSQL PgBouncer или Prisma Accelerate, чтобы экземпляры функций делили один пул.

Признаки неправильной настройки конкретные: ошибки "too many connections" или частые ошибки по `pool_timeout`.

---

## Группа 5: миграции в production

**Как безопасно добавить колонку `NOT NULL` в таблицу с миллионами строк?**

Только в три отдельных деплоя, никогда за один шаг. От `ADD COLUMN name TEXT NOT NULL DEFAULT 'value'` PostgreSQL заблокирует таблицу и перезапишет все строки. На миллионах строк эта блокировка и есть ваш простой.

```sql
-- миграция 1: nullable-колонка — мгновенно, без перезаписи таблицы
ALTER TABLE users ADD COLUMN name TEXT;

-- выкатить новый код и дождаться, пока данные заполнятся

-- миграция 2: включить ограничение, когда значение есть у всех строк
ALTER TABLE users ALTER COLUMN name SET NOT NULL;
```

1. Миграция: `ADD COLUMN name TEXT` — nullable, мгновенно, без блокировки.
2. Деплой нового кода: он заполняет `name` для новых записей, а фоновая задача — для старых.
3. Миграция: `ALTER COLUMN name SET NOT NULL` — только когда все строки заполнены.

Каждый деплой должен оставаться обратно совместимым с предыдущей схемой: во время раскатки старый и новый код работают одновременно.

---

**Что делать, если миграция упала в production?**

Сначала выяснить, что именно упало, потом починить это новой миграцией. Историю переписывать нельзя.

```bash
npx prisma migrate status
# → какие миграции применены, какие ждут, какая упала
# Prisma держит это состояние в таблице _prisma_migrations
```

- **Нельзя:**
  - удалять файл миграции;
  - править `migration.sql` руками после применения;
  - запускать `migrate reset` — он удаляет все таблицы.
- **Нужно, по порядку:**
  1. Понять, что именно упало. Статус Prisma хранит в таблице `_prisma_migrations`.
  2. Если миграция применилась частично — написать новую, которая откатывает эти изменения.
  3. Исправить проблему в новой миграции.
  4. Запустить `migrate deploy` — он применит исправленную миграцию.

Про мониторинг: в CI/CD всегда проверяйте код возврата `migrate deploy`. CI/CD — это continuous integration и continuous delivery, автоматический конвейер сборки и выкладки. После шага миграции добавьте health check.

---

## Группа 6: сырой SQL и сложные запросы

**Когда использовать $queryRaw вместо Prisma API?**

Когда у Prisma API просто нет метода под нужный вам SQL. Таких случаев семь:

- оконные функции: `ROW_NUMBER()`, `RANK()`, `LAG()`/`LEAD()`;
- рекурсивные CTE (Common Table Expression, «общее табличное выражение» — именованный подзапрос из блока `WITH`), то есть `WITH RECURSIVE`;
- `LATERAL JOIN`;
- операторы, которые есть только в PostgreSQL: `@>`, `&&` для jsonb и массивов;
- агрегации, которых нет в Prisma API: `PERCENTILE_CONT`, `ARRAY_AGG`, `STRING_AGG`;
- `SELECT FOR UPDATE`;
- массовый `UPDATE`, где у каждой строки своё значение: `UPDATE ... SET ... FROM (VALUES ...)`.

```typescript
// Шаблонная строка Prisma.sql передаёт значения как параметры SQL
const result = await prisma.$queryRaw<{ id: number; rank: number }[]>`
  SELECT id, RANK() OVER (ORDER BY score DESC) as rank
  FROM users
  WHERE created_at > ${new Date('2024-01-01')}
`;

// ✗ никогда не склеивайте строку руками — это SQL-инъекция
// prisma.$queryRawUnsafe('SELECT * FROM users WHERE id = ' + userId)
```

Всегда используйте шаблонную строку `Prisma.sql` и никогда не склеивайте запрос из кусков. Именно через склейку строк и приходит SQL-инъекция.

---

**Почему Prisma не заменяет знание PostgreSQL?**

Потому что Prisma только генерирует SQL, а всё, от чего этот SQL быстрый или медленный, живёт внутри PostgreSQL.

```sql
EXPLAIN ANALYZE SELECT * FROM posts WHERE author_id = 42;
-- Seq Scan on posts   ← читает таблицу целиком: индекса на author_id нет
-- Index Scan using posts_author_id_idx on posts   ← после @@index
```

На производительность влияют четыре вещи, и ни одной из них Prisma не управляет:

- индексы — а индексы для внешних ключей Prisma сама не создаёт;
- уровень изоляции транзакций, за которым стоят MVCC (Multi-Version Concurrency Control) и взаимные блокировки. При MVCC PostgreSQL хранит несколько версий строки, поэтому читающие не блокируют пишущих;
- качество самого SQL — `EXPLAIN ANALYZE` покажет seq scan, то есть чтение всей таблицы, там где вы ждали index scan;
- настройки PostgreSQL: `work_mem`, `shared_buffers`, `autovacuum`.

Путь отладки всегда один и тот же:

- запрос Prisma работает медленно;
- `log: ['query']` показывает, какой SQL получился на самом деле;
- `EXPLAIN ANALYZE` по этому SQL показывает план;
- план называет причину: не хватает индекса или `JOIN` неэффективен;
- лечение — `@@index` в схеме или переписать запрос через `$queryRaw`.

ORM убирает рутинный код. Необходимость понимать, как работает база данных, он не убирает.
