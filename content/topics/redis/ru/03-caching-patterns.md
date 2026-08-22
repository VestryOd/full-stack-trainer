<!-- verified: 2026-06-05, corrections: 0 -->
# Паттерны кэширования в Redis

## Cache-Aside (Lazy Loading) — самый распространённый паттерн

При Cache-Aside кэшем управляет само приложение. На чтение оно сначала смотрит в Redis. Если там пусто — это промах, cache miss — приложение читает PostgreSQL, кладёт результат в Redis с TTL и возвращает его. TTL (time to live) — сколько секунд ключ проживёт, прежде чем Redis его удалит.

Отсюда и второе название, lazy loading: в кэш попадает только то, что кто-то реально запросил. На запись кэш не обновляют, а удаляют. Следующее чтение само положит туда свежие данные.

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
  ✓ Отказ Redis → запросы идут в базу (graceful degradation)
  ✓ Схема базы и схема кэша независимы

Cache-Aside недостатки:
  ✗ Первый запрос после истечения TTL: всегда Cache MISS
  ✗ Race condition: два процесса могут одновременно читать
    базу и писать в кэш
  ✗ Устаревшие данные возможны между обновлением базы и
    инвалидацией кэша
```

## Write-Through — синхронная запись в кэш и базу

Write-Through обновляет кэш на том же пути кода, что и запись в базу. Поэтому кэш никогда не устаревает. Плата за это — в кэш попадают строки, которые могут никому не понадобиться, а отказ Redis теперь способен уронить запрос на запись.

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

## Write-Behind (Write-Back) — асинхронная запись в базу

Write-Behind подтверждает запись сразу, как только её принял Redis, а в базу её позже переносит фоновый процесс. Записи становятся очень быстрыми, но всё, что Redis ещё не сбросил в базу, теряется при его падении.

```txt
Редкий паттерн:
  Запись → Redis (быстро) → фоновый процесс → база данных
  (с задержкой)

Когда оправдан:
  Счётчики (page views, likes) — точность до секунды не важна
  Analytics events — можно flush раз в минуту
  Session updates — активность пользователя

Риски:
  При падении Redis до flush → данные теряются
  Реализация сложна: нужен надёжный flush процесс
  (BullMQ job, cron)

Пример: накопление page views
  INCR page:123:views (в Redis, мгновенно)
  Каждые 30 сек: flush accumulated counts в PostgreSQL
```

## Cache Stampede (Thundering Herd) — проблема и решения

Stampede случается, когда истекает один популярный ключ и все запросы в этот момент разом получают промах. Все они одновременно идут в базу. Три решения ниже либо дают пересчитать значение только одному запросу, либо разводят истечение ключей во времени.

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

Penetration — обратная проблема: запрошенной строки нет нигде, поэтому в кэш ничего не попадает и каждый запрос доходит до базы. Лечится это тем, что кэшируют само отсутствие данных, либо отсекают ключ ещё до запроса.

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

Stampede — это один горячий ключ, а avalanche — тысячи никак не связанных ключей, истекающих в одну и ту же секунду. Обычно это происходит после деплоя: все ключи записали в один момент и с одинаковым TTL. Разведите сроки истечения — и нагрузка останется ровной.

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

## Паттерн хранения сессий

У сессий, чёрных списков токенов и счётчиков rate limiting одна форма: короткоживущие ключи, потерю которых можно пережить. Ровно для этого и нужен TTL — Redis убирает их за вами, и никакой cron не требуется.

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
async function checkRateLimit(
  identifier: string,
  maxRequests: number,
  windowSec: number,
): Promise<boolean> {
  const key = `ratelimit:${identifier}:${Math.floor(Date.now() / 1000 / windowSec)}`;
  const count = await redis.incr(key);
  if (count === 1) await redis.expire(key, windowSec * 2);
  return count <= maxRequests;
}
```

## Типичные ошибки на интервью

- **"Cache-Aside — единственный правильный паттерн"** — зависит от требований. Write-Through: если устаревание кэша недопустимо. Write-Behind: если нужны сверхбыстрые записи с eventual consistency. Read-Through, встроенный в некоторые ORM — библиотеки объектно-реляционного отображения: кэш сам идёт в базу при промахе, а приложение о кэше вообще не знает.

- **"Cache Invalidation = просто удалить ключ"** — в распределённой системе это не так. Когда инстансов приложения несколько, удаление ключа открывает гонку:

```txt
1. Instance A обновляет базу, затем удаляет ключ в кэше
2. Instance B читает ту же строку — но с реплики, которая
   ещё не догнала мастер, и получает СТАРОЕ значение
3. Instance B записывает это старое значение в кэш
4. Все читают устаревшие данные, пока не истечёт TTL
```

  Что помогает: короткий TTL поверх явной инвалидации либо инвалидация по событиям.

- **"Кэшировать всё, что можно"** — кэш добавляет сложность (инвалидация, устаревшие данные, cache penetration). Кэшировать стоит: дорогие запросы (тяжёлые JOIN), внешние API с rate limits, статические данные. Не стоит: простые запросы по первичному ключу (B-Tree индекс PostgreSQL и так быстрый) и данные, которые меняются очень часто.

- **"TTL решает все проблемы с устареванием"** — нет. При TTL=1ч данные могут быть устаревшими до часа после обновления. Для критичных данных (баланс, остатки на складе) инвалидируйте кэш при каждом обновлении, а не полагайтесь на один TTL. TTL — страховочная сетка, а не основной механизм.

- **"Cache Stampede редкий кейс"** — при высоком трафике это реальная проблема. При популярном ключе с TTL=60 сек и 10k запросов в секунду каждую минуту до 10k запросов разом уходят в базу. Mutex lock или probabilistic early expiration (обновлять кэш за N секунд до истечения TTL) обязательны.
