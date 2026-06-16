<!-- verified: 2026-06-05, corrections: 0 -->
# Redis Caching Patterns

## Cache-Aside (Lazy Loading) — самый распространённый паттерн

```typescript
import { createClient } from 'redis';
import { PrismaClient } from '@prisma/client';

const redis = createClient({ url: process.env.REDIS_URL });
const prisma = new PrismaClient();

async function getUserById(userId: string) {
  const cacheKey = `user:${userId}`;

  // 1. Проверить Redis
  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached); // Cache HIT

  // 2. Cache MISS — читать из БД
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true, name: true, email: true, role: true },
  });

  if (!user) {
    // Кэшировать NULL на короткое время (защита от Cache Penetration)
    await redis.set(cacheKey, 'null', { EX: 30 });
    return null;
  }

  // 3. Записать в Redis с TTL
  await redis.set(cacheKey, JSON.stringify(user), { EX: 3600 }); // 1 час

  return user;
}

// Инвалидация при обновлении
async function updateUser(userId: string, data: Partial<User>) {
  const user = await prisma.user.update({ where: { id: userId }, data });
  await redis.del(`user:${userId}`); // удалить кэш, следующий GET обновит его
  return user;
}
```

```txt
Cache-Aside преимущества:
  ✓ Простота реализации
  ✓ Кэшируется только то, что реально запрашивается (lazy)
  ✓ Отказ Redis → запросы идут в DB (graceful degradation)
  ✓ DB schema и cache schema независимы

Cache-Aside недостатки:
  ✗ Первый запрос после истечения TTL: всегда Cache MISS (медленно)
  ✗ Race condition: два процесса могут одновременно читать из DB и записывать в cache
  ✗ Stale data возможен между обновлением DB и инвалидацией cache
```

## Write-Through — синхронная запись в cache и DB

```typescript
// Write-Through: запись в DB И cache происходит в одной операции
// Гарантия: cache всегда актуален

async function updateUserWriteThrough(userId: string, data: Partial<User>) {
  // Транзакционность: Redis и DB — разные системы, 100% consistency невозможна
  // Но для большинства кейсов достаточно sequential write:

  const user = await prisma.user.update({ where: { id: userId }, data });

  // Сразу обновляем cache с новыми данными
  await redis.set(`user:${userId}`, JSON.stringify(user), { EX: 3600 });

  return user;
}

// Минус: если Redis недоступен → запрос падает (можно обернуть в try/catch)
async function updateUserWriteThroughSafe(userId: string, data: Partial<User>) {
  const user = await prisma.user.update({ where: { id: userId }, data });

  try {
    await redis.set(`user:${userId}`, JSON.stringify(user), { EX: 3600 });
  } catch (err) {
    console.warn('Cache write failed, DB updated successfully', err);
    // Не фейлим запрос — DB обновлена, cache просто устареет
  }

  return user;
}
```

## Write-Behind (Write-Back) — асинхронная запись в DB

```txt
Редкий паттерн:
  Запись → Redis (быстро) → фоновый процесс → DB (с задержкой)

Когда оправдан:
  Счётчики (page views, likes) — точность не критична секунду в секунду
  Analytics events — можно flush раз в минуту
  Session updates — активность пользователя

Риски:
  При падении Redis до flush → данные теряются
  Реализация сложна: нужен надёжный flush процесс (BullMQ job, cron)

Пример: накопление page views
  INCR page:123:views (в Redis, мгновенно)
  Каждые 30 сек: flush accumulated counts в PostgreSQL
```

## Cache Stampede (Thundering Herd) — проблема и решения

```typescript
// Проблема: TTL истёк → 1000 concurrent запросов → все идут в DB → overload

// Решение 1: Mutex Lock (только один запрос обновляет cache)
async function getUserWithLock(userId: string) {
  const cacheKey = `user:${userId}`;
  const lockKey = `lock:${cacheKey}`;

  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached);

  // Попытка захватить lock (SET NX EX)
  const acquired = await redis.set(lockKey, '1', { NX: true, EX: 5 });

  if (acquired) {
    // Мы первые — читаем из DB и обновляем cache
    try {
      const user = await prisma.user.findUniqueOrThrow({ where: { id: userId } });
      await redis.set(cacheKey, JSON.stringify(user), { EX: 3600 });
      return user;
    } finally {
      await redis.del(lockKey);
    }
  } else {
    // Другой процесс обновляет — ждём и перечитываем
    await new Promise(resolve => setTimeout(resolve, 50));
    const retried = await redis.get(cacheKey);
    return retried ? JSON.parse(retried) : null;
  }
}

// Решение 2: Random TTL jitter (предотвращает одновременное истечение)
const BASE_TTL = 3600;
const jitter = Math.floor(Math.random() * 300); // ±300 сек
await redis.set(cacheKey, JSON.stringify(data), { EX: BASE_TTL + jitter });

// Решение 3: Stale-While-Revalidate
// Хранить данные с "мягким" и "жёстким" TTL
// При soft expiry → вернуть stale + фоновое обновление
// При hard expiry → полный refresh
```

## Cache Penetration — защита от несуществующих ключей

```typescript
// Атака/проблема: запросы на user:99999999 которого нет
// Каждый запрос: Redis MISS → DB query → null → не кэшируется → снова DB

// Решение 1: Cache NULL значение
async function getUserSafe(userId: string) {
  const cacheKey = `user:${userId}`;
  const cached = await redis.get(cacheKey);

  if (cached !== null) {
    // 'null' строка означает "не существует"
    return cached === 'null' ? null : JSON.parse(cached);
  }

  const user = await prisma.user.findUnique({ where: { id: userId } });

  if (!user) {
    // Кэшировать отсутствие с коротким TTL (30 сек)
    await redis.set(cacheKey, 'null', { EX: 30 });
    return null;
  }

  await redis.set(cacheKey, JSON.stringify(user), { EX: 3600 });
  return user;
}

// Решение 2: Bloom Filter (для продвинутого случая)
// Предварительно загрузить все существующие userId в Bloom Filter
// Перед Redis/DB проверкой: if (!bloomFilter.has(userId)) return null;
// RedisBloom (Redis Stack module): BF.ADD, BF.EXISTS
// ~0.01% false positive rate при правильной настройке
```

## Cache Avalanche — массовое истечение TTL

```typescript
// Cache Avalanche: множество разных ключей истекают одновременно
// Например: задеплоили новый сервис → все TTL начались с нуля → все истекут вместе

// Решение: Random TTL для разных типов данных
const TTL_BASE = {
  user: 3600,      // 1 час
  product: 1800,   // 30 минут
  category: 7200,  // 2 часа
};

function getRandomTTL(base: number, spread = 0.1): number {
  const delta = Math.floor(base * spread * (Math.random() * 2 - 1));
  return base + delta; // base ± 10%
}

// При деплое: постепенно прогреть кэш (cache warming)
// Не сбрасывать все ключи сразу — использовать rolling invalidation
```

## Session Storage паттерн

```typescript
// Типичное использование Redis для сессий / JWT blacklist

// JWT Blacklist (logout → invalid token)
async function invalidateToken(jti: string, expiresAt: number) {
  const ttl = Math.max(0, expiresAt - Math.floor(Date.now() / 1000));
  await redis.set(`blacklist:${jti}`, '1', { EX: ttl });
}

async function isTokenBlacklisted(jti: string): Promise<boolean> {
  const result = await redis.exists(`blacklist:${jti}`);
  return result === 1;
}

// Rate Limiting (INCR + EXPIRE — sliding counter)
async function checkRateLimit(identifier: string, maxRequests: number, windowSec: number): Promise<boolean> {
  const key = `ratelimit:${identifier}:${Math.floor(Date.now() / 1000 / windowSec)}`;
  const count = await redis.incr(key);
  if (count === 1) await redis.expire(key, windowSec * 2);
  return count <= maxRequests;
}
```

## Типичные ошибки на интервью

- **"Cache-Aside — единственный правильный паттерн"** — зависит от требований. Write-Through: если cache staleness недопустима. Write-Behind: если нужны сверхбыстрые записи с eventual consistency. Read-Through (в некоторых ORM/библиотеках): cache сам идёт в DB при MISS, приложение не знает о cache.

- **"Cache Invalidation = просто удалить ключ"** — в distributed системе (несколько инстансов) race condition: Instance A обновил DB, удалил cache → Instance B прочитал из DB (старые данные из-за replica lag) → записал в cache → стале данные. Решение: короткий TTL + явная инвалидация, или event-driven invalidation.

- **"Кэшировать всё, что можно"** — кэш добавляет сложность (invalidation, stale data, cache penetration). Кэшировать стоит: дорогие запросы (тяжёлые JOIN), внешние API с rate limits, статические данные. Не стоит: простые запросы по PK (PostgreSQL B-Tree index достаточно быстрый), данные которые меняются очень часто.

- **"TTL решает все проблемы с стейлнесс"** — нет. При TTL=1ч данные могут быть устаревшими до 1 часа после обновления. Для критичных данных (баланс, inventory) — cache invalidation при каждом обновлении, не TTL-only. TTL — как safety net, не основной механизм.

- **"Cache Stampede редкий кейс"** — при высоком трафике это реальная проблема. Если popular key с TTL=60 сек и 10k RPS — каждую минуту потенциально 10k запросов одновременно идут в DB. Mutex lock или probabilistic early expiration (обновлять cache за N секунд до истечения TTL) — обязательны.
