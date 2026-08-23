<!-- verified: 2026-06-05, corrections: 0 -->
# Основы Redis

## Что такое Redis и почему он быстрый

Redis (Remote Dictionary Server) — хранилище данных, которое держит всё в памяти. Данные лежат в RAM (оперативной памяти), а не на диске, поэтому одна операция занимает микросекунды. Это не просто кэш: Redis поддерживает богатые структуры данных, Pub/Sub, Streams, Lua scripting и транзакции.

```txt
Почему Redis быстрее PostgreSQL на порядки:

1. In-Memory:
   PostgreSQL: данные на диске → buffer pool в RAM → disk I/O
   при промахе
   Redis: всё в RAM, нет disk I/O для чтения и записи
   Latency: Redis ~100μs, PostgreSQL ~1-10ms
   PostgreSQL при cache miss: 10-100ms

2. Single-Threaded Event Loop:
   Один поток для всех команд → нет race conditions,
   нет mutex overhead
   Как event loop в Node.js: I/O не блокирует поток,
   а каждая команда выполняется атомарно
   Команды типа GET/SET/INCR = O(1), выполняются за <<1ms
   Многопоточность в Redis 6+: только для I/O (network,
   persistence) — команды по-прежнему в одном потоке

3. Оптимизированные структуры данных:
   Hash Table для String/Hash
   Skip List для Sorted Set (O(log N) range queries)
   Linked List для List
   Radix Tree для Streams
```

## Redis как дополнение к PostgreSQL

Redis не заменяет реляционную базу. Обычное разделение такое: PostgreSQL владеет данными, а Redis держит быструю копию того, что читают часто.

```txt
Стандартная архитектура:
  PostgreSQL = источник правды, Redis = быстрый слой сверху

Cache-Aside (самый популярный паттерн):
  1. Request → проверить Redis
  2. Cache HIT → вернуть из Redis (без обращения к базе)
  3. Cache MISS → читать из PostgreSQL → записать в Redis
     с TTL → вернуть

Типичное применение в fullstack:
  Cache:       ответы API, результаты сложных SQL-запросов
  Sessions:    JWT blacklist, server-side sessions
  Rate limit:  счётчики запросов (INCR + EXPIRE)
  Leaderboard: Sorted Set по score
  Pub/Sub:     real-time notifications (Kafka или SQS,
               если доставку нужно гарантировать)
  Queue:       List + BLPOP (или BullMQ поверх Redis)
  Locks:       SET NX EX (алгоритм Redlock)
```

## Основные операции и TTL

TTL (time to live) — срок жизни ключа: через столько секунд Redis удалит его сам. Это главный инструмент, который не даёт кэшу расти бесконечно.

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
// -1 = ключ есть, но TTL не задан; -2 = ключа не существует
const ttl = await redis.ttl('user:123'); // секунд до истечения

// DEL
await redis.del('user:123');

// EXISTS
const exists = await redis.exists('user:123'); // 1 или 0
```

## Eviction Policies — что делать при нехватке памяти

Политика вытеснения говорит Redis, какие ключи выбрасывать, когда достигнут лимит `maxmemory`. Выберете не ту — и Redis либо начнёт отклонять запись, либо тихо удалит нужную сессию.

```txt
maxmemory-policy в redis.conf (или через CONFIG SET):

noeviction (по умолчанию):
  Новые записи отклоняются с ошибкой нехватки памяти
  Когда: Redis как основная база (нельзя терять данные)

allkeys-lru:
  Удаляем наименее недавно используемые ключи (из всех)
  Когда: общий кэш, не все ключи имеют TTL

volatile-lru:
  LRU только среди ключей с TTL
  Когда: кэш с TTL плюс отдельные постоянные ключи
  (sessions) без TTL

allkeys-lfu:
  Least Frequently Used (Redis 4+) — считает частоту,
  а не только давность
  Когда: hot/cold data с неравномерным доступом

volatile-ttl:
  Первым удаляется ключ с ближайшим TTL
  Когда: важно освобождать "самые старые" данные

Рекомендация для кэша: allkeys-lru или allkeys-lfu
Рекомендация для сессий: volatile-lru
  (у сессий TTL есть, у lock keys — нет)
```

## Redis Cluster vs Sentinel vs Standalone

Это три формы развёртывания, а не три набора функций. Standalone — один сервер, Sentinel добавляет автоматический failover, Cluster добавляет к нему ещё и шардинг.

```txt
Standalone (один сервер):
  Dev, low-traffic production
  Нет отказоустойчивости: при падении → downtime

Sentinel (отказоустойчивость без шардинга):
  Master + Replica(s) + 3+ Sentinel процессов
  Sentinel мониторит Master, при падении — failover
  Один shard → весь dataset на одном узле
  Когда: нужен автоматический failover, и данные
  помещаются в RAM одного сервера

Cluster (horizontal sharding):
  16384 hash slots распределены по N master nodes
  У каждого master есть replica для failover
  key → контрольная сумма CRC16 % 16384 → slot → node
  Когда: dataset > RAM одного сервера, или нужен
  throughput выше 100k ops/sec

  Ограничение Cluster: multi-key операции работают,
  только если все ключи попали в один slot
  Hash tags: {user}:123 и {user}:456 → один slot (фигурные скобки)
```

## Типичные ошибки на интервью

- **"Redis — это просто кэш"** — это полноценное хранилище структур данных в памяти. Кроме обычных строк оно даёт:
  - Sorted Sets для leaderboards и очередей с приоритетом.
  - Streams — append-only log, лёгкий аналог Kafka.
  - Pub/Sub, Lua scripting и распределённые блокировки.
  - Геопространственные индексы (`GEOADD`/`GEORADIUS`) и HyperLogLog для приблизительной мощности множества.

- **"Redis однопоточный значит медленный при нагрузке"** — наоборот. Single-threaded Event Loop: нет context switching, нет mutex overhead, команды атомарны. Redis обрабатывает >1M ops/sec на одном ядре. Узкое место — обычно сеть, а не процессор.

- **"Данные в Redis всегда теряются при перезапуске"** — Redis поддерживает persistence: RDB (периодические снапшоты) и AOF (append-only log каждой команды). В production: AOF + RDB для надёжности. Но для намеренно эфемерного кэша без persistence быстрее.

- **"TTL — гарантированное удаление через N секунд"** — истечение ленивое. Ключ помечается как expired, а физически удаляется при следующем GET. Ещё есть фоновая уборка: каждые 100ms удаляется часть просроченных ключей. Под нагрузкой возможна небольшая задержка удаления.

- **"SET + EXPIRE — атомарная операция"** — нет! `SET key value` + `EXPIRE key 60` — два отдельных вызова. Между ними процесс может упасть → ключ без TTL (утечка памяти). Правильно: `SET key value EX 60` (атомарно в одной команде) или `SETEX`.
