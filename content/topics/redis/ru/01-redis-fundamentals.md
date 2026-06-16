<!-- verified: 2026-06-05, corrections: 0 -->
# Redis Fundamentals

## Что такое Redis и почему он быстрый

Redis (Remote Dictionary Server) — in-memory data store: все данные в RAM, операции выполняются за микросекунды. Не просто кэш — поддерживает богатые структуры данных, Pub/Sub, Streams, Lua scripting, транзакции.

```txt
Почему Redis быстрее PostgreSQL на порядки:

1. In-Memory:
   PostgreSQL: данные на диске → buffer pool в RAM → disk I/O при miss
   Redis: всё в RAM, нет disk I/O для чтения/записи
   Latency: Redis ~100μs, PostgreSQL ~1-10ms (при cache miss — 10-100ms)

2. Single-Threaded Event Loop:
   Один поток для всех команд → нет race conditions, нет mutex overhead
   Похоже на Node.js event loop: I/O не блокирует, команды выполняются атомарно
   Команды типа GET/SET/INCR = O(1), выполняются за <<1ms
   Многопоточность в Redis 6+: только для I/O (network, persistence), не для команд

3. Оптимизированные структуры данных:
   Hash Table для String/Hash
   Skip List для Sorted Set (O(log N) range queries)
   Linked List для List
   Radix Tree для Streams
```

## Redis как дополнение к PostgreSQL

```txt
Стандартная архитектура: PostgreSQL (source of truth) + Redis (fast layer)

Cache-Aside (самый популярный паттерн):
  1. Request → проверить Redis
  2. Cache HIT → вернуть из Redis (без DB)
  3. Cache MISS → читать из PostgreSQL → записать в Redis с TTL → вернуть

Типичное применение в fullstack:
  Cache:        ответы API, результаты сложных SQL запросов
  Sessions:     JWT blacklist, server-side sessions
  Rate Limiting: счётчики запросов (INCR + EXPIRE)
  Leaderboard:  Sorted Set по score
  Pub/Sub:      real-time notifications (но лучше Kafka/SQS для reliability)
  Queue:        List + BLPOP (или лучше BullMQ поверх Redis)
  Distributed Lock: SET NX EX (Redlock алгоритм)
```

## Основные операции и TTL

```typescript
import { createClient } from 'redis';

const redis = createClient({ url: process.env.REDIS_URL });
await redis.connect();

// SET с TTL
await redis.set('user:123', JSON.stringify(user), { EX: 3600 }); // 1 час
// или
await redis.setEx('user:123', 3600, JSON.stringify(user));

// GET
const cached = await redis.get('user:123');
const user = cached ? JSON.parse(cached) : null;

// Атомарный инкремент (счётчик запросов для rate limiting)
const count = await redis.incr('rate:user:123');
if (count === 1) {
  await redis.expire('rate:user:123', 60); // сбросить через 60 сек
}

// TTL check
const ttl = await redis.ttl('user:123'); // секунд до истечения, -1 = нет TTL, -2 = не существует

// DEL
await redis.del('user:123');

// EXISTS
const exists = await redis.exists('user:123'); // 1 или 0
```

## Eviction Policies — что делать при нехватке памяти

```txt
maxmemory-policy в redis.conf (или через CONFIG SET):

noeviction (default):
  Новые записи отклоняются с ошибкой OOM
  Когда: Redis как основная БД (нельзя терять данные)

allkeys-lru:
  Удаляем наименее недавно используемые ключи (из всех)
  Когда: общий кэш, не все ключи имеют TTL

volatile-lru:
  LRU только среди ключей с TTL
  Когда: кэш с TTL + отдельные persistent ключи (sessions) без TTL

allkeys-lfu:
  Least Frequently Used (Redis 4+) — считает частоту, не только давность
  Когда: hot/cold data с неравномерным доступом

volatile-ttl:
  Первым удаляется ключ с ближайшим TTL
  Когда: важно освобождать "самые старые" данные

Рекомендация для кэша: allkeys-lru или allkeys-lfu
Рекомендация для сессий: volatile-lru (сессии с TTL, lock keys без TTL)
```

## Redis Cluster vs Sentinel vs Standalone

```txt
Standalone (один сервер):
  Dev, low-traffic production
  Нет HA: при падении → downtime

Sentinel (HA без sharding):
  Master + Replica(s) + 3+ Sentinel процессов
  Sentinel мониторит Master, при падении — автоматический failover
  Один shard → весь dataset на одном node
  Когда: нужна HA, dataset помещается в RAM одного сервера

Cluster (horizontal sharding):
  16384 hash slots распределены по N master nodes
  Каждый master: replica для HA
  key → CRC16(key) % 16384 → slot → node
  Когда: dataset > RAM одного сервера, или нужен throughput >100k ops/sec
  
  Ограничение Cluster: multi-key операции только если все ключи в одном slot
  Hash tags: {user}:123 и {user}:456 → одинаковый slot (фигурные скобки)
```

## Типичные ошибки на интервью

- **"Redis — это просто кэш"** — Redis поддерживает: Sorted Sets (leaderboards, priority queues), Streams (append-only log, как Kafka light), Pub/Sub, Lua scripting, distributed locks, геопространственные индексы (GEOADD/GEORADIUS), HyperLogLog (approximate cardinality). Это полноценная структура данных in-memory.

- **"Redis однопоточный значит медленный при нагрузке"** — наоборот. Single-threaded Event Loop: нет context switching, нет mutex overhead, команды атомарны. Redis обрабатывает >1M ops/sec на одном ядре. Узкое место — обычно network, не CPU.

- **"Данные в Redis всегда теряются при перезапуске"** — Redis поддерживает persistence: RDB (periodic snapshots) и AOF (append-only log каждой команды). В production: AOF + RDB для надёжности. Но для кэша intentionally без persistence = быстрее.

- **"TTL — гарантированное удаление через N секунд"** — lazy expiration: ключ помечается как expired, но физически удаляется при следующем GET или background sweep (каждые 100ms удаляется часть expired ключей). Под нагрузкой возможна небольшая задержка удаления.

- **"SET + EXPIRE — атомарная операция"** — нет! `SET key value` + `EXPIRE key 60` — два отдельных вызова. Между ними процесс может упасть → ключ без TTL (утечка памяти). Правильно: `SET key value EX 60` (атомарно в одной команде) или `SETEX`.
