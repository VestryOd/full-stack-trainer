# Prisma — вопросы на интервью (Senior)

## Группа 1: Архитектура и подход

**В чём принципиальное отличие Prisma от TypeORM?**

TypeORM — runtime ORM: Entity с декораторами, метаданные строятся во время выполнения через `reflect-metadata`. Часть ошибок обнаруживается только в runtime. Prisma — schema-first с code generation: `schema.prisma` → `prisma generate` → типизированный клиент. Все типы compile-time: опечатка в имени поля — ошибка TS, не runtime. Преимущество Prisma: точный inference (`{ id: number; email: string }` вместо `User`), превосходный автокомплит в IDE. Преимущество TypeORM: QueryBuilder для динамически сложных запросов.

---

**Что происходит когда ты изменяешь schema.prisma?**

Изменение schema.prisma само по себе ничего не делает. Нужно два шага: (1) `prisma migrate dev` — сравнивает schema с текущим состоянием БД (через Shadow Database), генерирует SQL migration файл, применяет к dev БД; (2) `prisma generate` — перегенерирует TypeScript клиент (в `migrate dev` происходит автоматически). Если пропустить `generate` — TypeScript типы устарели, IDE выдаёт ошибки. Если пропустить `migrate dev` — БД не синхронизирована со schema.

---

**Что такое Shadow Database и зачем она нужна?**

Shadow Database — временная БД, создаваемая Prisma при `migrate dev`. Workflow: (1) применить ВСЕ существующие migrations на Shadow DB; (2) применить текущее состояние schema.prisma напрямую на Shadow DB; (3) сравнить два состояния → сгенерировать точный SQL diff. Без Shadow DB: невозможно определить точную дельту между реальным состоянием БД (с возможными ручными изменениями) и schema.prisma. Для managed DB (Supabase, PlanetScale): нужна отдельная `SHADOW_DATABASE_URL` в конфиге.

---

**Что такое PrismaClient и как правильно его инициализировать в NestJS?**

PrismaClient — сгенерированный TypeScript класс, управляющий connection pool и выполнением запросов через Prisma Query Engine (Rust). В NestJS: один singleton `PrismaService extends PrismaClient`, зарегистрированный как `@Global()` модуль. `OnModuleInit` → `$connect()`, `OnModuleDestroy` → `$disconnect()`. Создавать `new PrismaClient()` в каждом запросе — утечка соединений и деградация производительности (каждый экземпляр создаёт отдельный connection pool).

---

## Группа 2: Schema и модели

**Когда использовать UUID вместо autoincrement и наоборот?**

UUID (`@default(uuid())`): нет предсказуемой последовательности (безопаснее для публичных API — нельзя угадать чужой id), можно генерировать на клиенте до insert, удобно при слиянии данных из нескольких БД. Минус: 16 байт vs 4 байта, хуже locality в B-tree индексах (новые записи не в конце → page splits). Autoincrement: компактный, предсказуемый порядок, лучше производительность индекса для bulk вставок. Правило: внутренние ID для JOIN → `autoincrement`. Публичные API ресурсы (`/users/:id`) → `uuid`. Альтернатива: ULID или CUID — временно-сортируемые UUID.

---

**Почему Decimal, а не Float для денежных значений?**

`Float` — IEEE 754 double precision, даёт ошибки округления: `0.1 + 0.2 = 0.30000000000000004`. Накопленные ошибки в финансовых расчётах приводят к расхождениям в копейках и центах. `Decimal @db.Decimal(10, 2)` — точная фиксированная точность, без ошибок представления. Альтернатива: хранить деньги в целых числах (копейки/центы) как `Int` — тогда Float вопрос не стоит. В коде использовать `Decimal.js` для арифметики с Prisma Decimal значениями.

---

**Когда добавлять индекс, а когда нет?**

Добавлять индекс: Foreign Key поля (всегда — Prisma не создаёт FK индексы автоматически), поля в частых `WHERE` условиях (email, status, userId), поля в `ORDER BY` при наличии других `WHERE` условий. Не добавлять: boolean поля с низкой кардинальностью (isActive=true/false — планировщик часто игнорирует, делает seq scan), поля без реальных `WHERE` запросов (индексы замедляют INSERT/UPDATE), избыточные индексы покрывающие уже имеющийся составной индекс.

---

## Группа 3: Relations и queries

**Объясни разницу между implicit и explicit Many-to-Many.**

Implicit M2M: `Post[] tags Tag[]` без явной join table → Prisma создаёт скрытую `_PostToTag` таблицу. Простота, но нельзя добавить поля на join table, нельзя напрямую запрашивать join table через Prisma API. Explicit M2M: явная модель `UserRole` с `@@id([userId, roleId])` и дополнительными полями (assignedAt, assignedBy). Production рекомендация: explicit — больше контроля, можно добавить поля без migration сложности, `prisma.userRole.findMany()` — прямые запросы к join table. Implicit только для очень простых M2M без доп. данных.

---

**В чём разница между include и select и можно ли их комбинировать?**

`include: { posts: true }` — загрузить ВСЕ поля User + все связанные Post записи. `select: { id: true, email: true }` — загрузить ТОЛЬКО указанные поля, без связей. На одном уровне использовать одновременно нельзя (`{ include, select }` — ошибка TypeScript). Комбинирование: `select: { id: true, posts: { select: { title: true } } }` — select с вложенным select для relation. Для performance: `select` лучше — не грузит лишние поля (пароли, токены), меньше данных по сети, точный TypeScript тип вместо всего Entity.

---

**Что такое N+1 и как его диагностировать и исправить в Prisma?**

N+1: один запрос на список (`findMany` → N записей) + N отдельных запросов для связанных данных в цикле. Диагностика: `log: ['query']` в PrismaClient — видеть все SQL запросы при одном HTTP запросе. Решения: (1) `include` — JOIN всё за один запрос; (2) `groupBy` + `_count` — агрегация за один запрос; (3) `$queryRaw` с явным `LEFT JOIN ... GROUP BY`; (4) два запроса с `WHERE id IN (...)` — иногда эффективнее тяжёлого JOIN. Глубокий вложенный `include` может дать декартово произведение — хуже чем N+1.

---

## Группа 4: Transactions и performance

**Когда использовать Sequential $transaction, а когда Interactive?**

Sequential (`$transaction([op1, op2])`): когда операции независимы и все данные известны заранее. Быстрее — нет overhead на удержание открытой транзакции. Ограничение: результат op1 недоступен для op2 (порядок выполнения гарантирован, но в runtime PostgreSQL может оптимизировать). Interactive (`$transaction(async tx => { ... })`): когда результат предыдущего шага нужен для следующего (создать User → получить id → создать Profile). Позволяет: условная логика внутри транзакции, throw Error → автоматически ROLLBACK. Параметры: `timeout` (максимальное время транзакции), `maxWait` (ожидание connection из pool), `isolationLevel`.

---

**Как реализовать SELECT FOR UPDATE в Prisma?**

Prisma не имеет встроенного API для `FOR UPDATE`. Решение: `$queryRaw` внутри `$transaction`:
```typescript
await prisma.$transaction(async (tx) => {
  const [row] = await tx.$queryRaw`SELECT * FROM accounts WHERE id = ${id} FOR UPDATE`;
  // row заблокирована — другие транзакции ждут
  await tx.account.update({ where: { id }, data: { balance: { decrement: amount } } });
});
```
Когда нужен `FOR UPDATE`: параллельные транзакции читают одну строку → оба видят `balance=100` → оба списывают → итог $0 вместо ошибки. `FOR UPDATE` блокирует строку: второй `SELECT FOR UPDATE` ждёт завершения первой транзакции.

---

**Как правильно настроить connection pool для production?**

Параметры в DATABASE_URL: `?connection_limit=20&pool_timeout=10`. `connection_limit` — максимум соединений (default: min(10, max_connections/2)). `pool_timeout` — время ожидания соединения из pool в секундах (default: 10). Для serverless (Lambda, Vercel): `connection_limit=1` — каждая функция имеет одно соединение, иначе тысячи холодных стартов создадут тысячи соединений. Для serverless: добавить PgBouncer или Prisma Accelerate перед PostgreSQL. Признак неправильного pooling: "too many connections" ошибки или высокий `pool_timeout` error rate.

---

## Группа 5: Migrations в production

**Как безопасно добавить NOT NULL колонку в таблицу с миллионами строк?**

Нельзя за один шаг: `ADD COLUMN name TEXT NOT NULL DEFAULT 'value'` → PostgreSQL блокирует таблицу для перезаписи всех строк → downtime. Безопасный путь (три отдельных deploy): (1) Migration: `ADD COLUMN name TEXT` — nullable, мгновенно, не блокирует; (2) Deploy нового кода: заполняет `name` для новых записей + background job заполняет старые; (3) Migration: `ALTER COLUMN name SET NOT NULL` — когда все строки заполнены. Каждый deploy должен быть backward-compatible с предыдущей schema.

---

**Что делать если migration упала в production?**

Нельзя: удалять migration файл, менять migration.sql вручную после apply, запускать `migrate reset`. Правильно: (1) понять что именно упало (Prisma хранит статус в `_prisma_migrations` таблице); (2) если migration частично применена — написать новую migration которая откатывает изменения; (3) исправить проблему в новой migration; (4) `migrate deploy` применит исправленную migration. Мониторинг: в CI/CD всегда проверять exit code `migrate deploy`, добавить health check после migration.

---

## Группа 6: Raw SQL и сложные запросы

**Когда использовать $queryRaw вместо Prisma API?**

`$queryRaw` нужен для: (1) оконных функций (`ROW_NUMBER()`, `RANK()`, `LAG()`/`LEAD()`); (2) рекурсивных CTE (`WITH RECURSIVE`); (3) `LATERAL JOIN`; (4) специфичных PostgreSQL операторов (`@>`, `&&` для jsonb/arrays); (5) агрегаций которых нет в Prisma API (`PERCENTILE_CONT`, `ARRAY_AGG`, `STRING_AGG`); (6) `SELECT FOR UPDATE`; (7) batch UPDATE с разными значениями (`UPDATE ... SET ... FROM (VALUES ...)`). Всегда использовать `Prisma.sql` template literal — никогда string concatenation → SQL injection.

---

**Почему Prisma не заменяет знание PostgreSQL?**

Prisma — абстракция, генерирующая SQL. Производительность определяется: наличием индексов (Prisma не создаёт индексы для FK автоматически), уровнем изоляции транзакций (MVCC, deadlock), качеством SQL (EXPLAIN ANALYZE покажет seq scan вместо index scan), настройкой PostgreSQL (work_mem, shared_buffers, autovacuum). Типичный сценарий: Prisma запрос медленный → `log: ['query']` → видим SQL → `EXPLAIN ANALYZE` → missing index или неэффективный JOIN → добавляем `@@index` или переписываем `$queryRaw`. ORM убирает boilerplate, но не убирает необходимость понимать как работает БД.
