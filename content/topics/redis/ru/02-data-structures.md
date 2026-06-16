<!-- verified: 2026-06-05, corrections: 0 -->
# Redis Data Structures

## Обзор структур и их сложность

Redis — не просто key-value хранилище: каждая структура оптимизирована под конкретные паттерны доступа. Выбор структуры напрямую влияет на производительность и расход памяти.

```txt
String   → O(1) SET/GET, бинарные данные до 512MB
Hash     → O(1) HGET/HSET, O(N) HGETALL, поля объекта
List     → O(1) LPUSH/RPOP, O(N) LRANGE, двусторонняя очередь
Set      → O(1) SADD/SISMEMBER, O(N) SMEMBERS, уникальные значения
Sorted Set → O(log N) ZADD/ZRANGE, range queries по score
Stream   → O(1) XADD, O(N) XRANGE, append-only log
Bitmap   → O(1) SETBIT/GETBIT, битовые флаги
HyperLogLog → O(1) PFADD/PFCOUNT, ~0.81% error, 12KB памяти
```

## String — универсальная структура

```typescript
import { createClient } from 'redis';
const redis = createClient({ url: process.env.REDIS_URL });

// Простое значение (строка, число, JSON)
await redis.set('config:feature-flags', JSON.stringify({ darkMode: true, beta: false }));
await redis.set('user:123:token', 'eyJhbGciOiJIUzI1...', { EX: 86400 });

// Атомарные числовые операции
await redis.set('stats:page-views', '0');
const views = await redis.incr('stats:page-views');   // атомарный +1
await redis.incrBy('stats:page-views', 10);            // атомарный +10
await redis.decr('stats:page-views');                  // атомарный -1

// SETNX — set if not exists (basis для простых locks)
const acquired = await redis.setNX('lock:job:123', '1');
if (acquired) {
  await redis.expire('lock:job:123', 30);
  // ... do work
}
// Лучше: SET key value NX EX 30 (атомарно)
await redis.set('lock:job:123', '1', { NX: true, EX: 30 });

// GETSET / GETDEL
const old = await redis.getDel('session:abc'); // получить и удалить
```

## Hash — объект с полями

```typescript
// Hash vs JSON String: Hash позволяет обновлять отдельные поля без десериализации
// JSON String: прочитать всё → десериализовать → изменить → сериализовать → записать
// Hash: HSET user:123 email "new@email.com" → только одно поле

// Запись объекта
await redis.hSet('user:123', {
  name: 'Alice',
  email: 'alice@example.com',
  role: 'admin',
  loginCount: '0',
});

// Чтение одного поля
const email = await redis.hGet('user:123', 'email');

// Чтение всех полей
const user = await redis.hGetAll('user:123');
// → { name: 'Alice', email: 'alice@example.com', role: 'admin', loginCount: '0' }

// Атомарный инкремент поля
await redis.hIncrBy('user:123', 'loginCount', 1);

// Проверка существования поля
const hasField = await redis.hExists('user:123', 'email');

// Удаление поля
await redis.hDel('user:123', 'temporaryToken');

// Когда Hash лучше JSON String:
// ✓ Частые обновления отдельных полей
// ✓ Нужно читать только некоторые поля
// ✗ Нужна вложенность (Hash плоский — нет nested objects)
// ✗ Весь объект всегда читается целиком (тогда JSON String проще)
```

## List — двусторонняя очередь / стек

```typescript
// List = doubly linked list: O(1) push/pop с обоих концов, O(N) по индексу

// Queue (FIFO): LPUSH + RPOP
await redis.lPush('jobs:email', JSON.stringify({ to: 'user@example.com', template: 'welcome' }));
const job = await redis.rPop('jobs:email');

// Stack (LIFO): LPUSH + LPOP
await redis.lPush('history:user:123', 'page-A');
await redis.lPush('history:user:123', 'page-B');
const last = await redis.lPop('history:user:123'); // 'page-B'

// BLPOP — blocking pop (consumer ждёт сообщения)
const result = await redis.blPop('jobs:email', 5); // timeout 5 сек
// → { key: 'jobs:email', element: '...' } или null при timeout

// Ограничение длины (sliding window log)
await redis.lPush('recent:events', JSON.stringify(event));
await redis.lTrim('recent:events', 0, 99); // хранить только последние 100

// LRANGE — получить диапазон
const recent = await redis.lRange('recent:events', 0, -1); // все
const top10 = await redis.lRange('recent:events', 0, 9);   // первые 10

// List длина
const len = await redis.lLen('jobs:email');
```

## Set — уникальные значения и операции над множествами

```typescript
// Set: уникальные строки, O(1) добавление/проверка/удаление

// Tags для поста
await redis.sAdd('post:123:tags', 'redis', 'caching', 'backend');
await redis.sAdd('post:123:tags', 'redis'); // дубликат — игнорируется

// Проверка членства (мгновенная)
const isTagged = await redis.sIsMember('post:123:tags', 'redis'); // true

// Список всех тегов
const tags = await redis.sMembers('post:123:tags');

// Followers/Following
await redis.sAdd('user:123:following', 'user:456', 'user:789');
await redis.sAdd('user:456:following', 'user:123', 'user:789');

// Взаимные подписки (intersection)
const mutual = await redis.sInter('user:123:following', 'user:456:following');
// → ['user:789']

// Операции над множествами
const union = await redis.sUnion('user:123:following', 'user:456:following');
const diff = await redis.sDiff('user:123:following', 'user:456:following');

// Случайный элемент (для лотерей, случайных рекомендаций)
const random = await redis.sRandMember('post:123:tags');

// Rate limiting с Set (уникальные IP за последний час)
await redis.sAdd(`visitors:${hourKey}`, clientIp);
const uniqueVisitors = await redis.sCard(`visitors:${hourKey}`);
```

## Sorted Set — ранжированные данные

```typescript
// Sorted Set: уникальные элементы со score (float), O(log N) вставка/обновление
// Внутри: Skip List + Hash Table → быстрые range queries по score

// Leaderboard
await redis.zAdd('leaderboard:game', [
  { score: 5000, value: 'user:alice' },
  { score: 7500, value: 'user:bob' },
  { score: 3200, value: 'user:carol' },
]);

// Топ-3 (по убыванию score)
const top3 = await redis.zRangeWithScores('leaderboard:game', 0, 2, { REV: true });
// → [{ value: 'user:bob', score: 7500 }, ...]

// Ранг пользователя (0-based, от наименьшего)
const rank = await redis.zRank('leaderboard:game', 'user:alice');
const rankRev = await redis.zRevRank('leaderboard:game', 'user:alice'); // от наибольшего

// Обновить score (атомарно)
await redis.zIncrBy('leaderboard:game', 1000, 'user:alice');

// Score пользователя
const score = await redis.zScore('leaderboard:game', 'user:alice');

// Range по score (например, все с > 5000 очков)
const highScorers = await redis.zRangeByScore('leaderboard:game', 5001, '+inf');

// Sliding Window Rate Limiting с Sorted Set:
const now = Date.now();
const windowMs = 60_000; // 1 минута

await redis.zAdd(`ratelimit:${userId}`, [{ score: now, value: `${now}` }]);
await redis.zRemRangeByScore(`ratelimit:${userId}`, '-inf', now - windowMs);
const count = await redis.zCard(`ratelimit:${userId}`);
if (count > 100) throw new Error('Rate limit exceeded');
await redis.expire(`ratelimit:${userId}`, 60);
```

## HyperLogLog и Bitmap

```typescript
// HyperLogLog: приблизительный подсчёт уникальных элементов
// ~12KB памяти независимо от количества элементов, ~0.81% погрешность

// Уникальные посетители
await redis.pfAdd('visitors:2024-01-01', 'user:123', 'user:456', 'user:789');
await redis.pfAdd('visitors:2024-01-01', 'user:123'); // дубликат — не считается
const uniqueCount = await redis.pfCount('visitors:2024-01-01'); // ~3

// Объединение нескольких HLL (уникальные за неделю)
await redis.pfMerge('visitors:week', 'visitors:2024-01-01', 'visitors:2024-01-02');

// Bitmap: битовые флаги, O(1) SETBIT/GETBIT
// Пример: отслеживание активных дней пользователя (365 бит = 45 байт)
const dayOfYear = 15;
await redis.setBit(`user:123:activity:2024`, dayOfYear, 1);
const wasActive = await redis.getBit(`user:123:activity:2024`, dayOfYear);

// BITCOUNT: количество активных дней
const activeDays = await redis.bitCount(`user:123:activity:2024`);
```

## Типичные ошибки на интервью

- **"Для хранения пользователя всегда лучше Hash"** — зависит от паттерна. Hash оптимален при частых обновлениях отдельных полей. Если объект всегда читается/записывается целиком — JSON String с `SET`/`GET` проще и быстрее (`HGETALL` делает несколько операций vs один `GET`).

- **"List подходит для очереди с несколькими consumers"** — List без дополнительной логики не подходит: если несколько consumers делают `RPOP`, сообщение получает только один, но нет acknowledgment — при падении consumer сообщение теряется. Для надёжных очередей: BullMQ (поверх Redis) или SQS.

- **"Sorted Set медленнее Set"** — для ZADD/ZRANK: O(log N) vs O(1) для Set. Но Sorted Set даёт range queries по score, которых у Set нет вообще. Выбор зависит от нужных операций, не просто от "скорости".

- **"SMEMBERS безопасно для больших Set"** — SMEMBERS блокирует Redis на время выполнения (single-threaded). Для Set с миллионами элементов — использовать `SSCAN` (cursor-based итерация, не блокирует). То же правило для `KEYS *` vs `SCAN`, `HGETALL` для больших Hash vs `HSCAN`.

- **"HyperLogLog точнее чем обычный счётчик"** — HyperLogLog приблизительный (~0.81% погрешность). Если нужна точность — использовать Set (но память O(N)) или обычный инкремент в DB. HyperLogLog для аналитики где допустима погрешность: уникальные посетители за день, уникальные IP.
