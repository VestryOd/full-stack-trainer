# Redis — вопросы на интервью (Senior)

## Группа 1: Архитектура и производительность

**Почему Redis работает быстро?**

Три причины: (1) данные в RAM — чтение из памяти ~100 нс против ~10 мс с диска; (2) однопоточный Event Loop — не нужны mutex/lock на данные, нет накладных расходов на переключение контекста; (3) оптимизированные структуры данных — Hash Table для String/Hash, Skip List для Sorted Set, Linked List для List — операции O(1)–O(log N) без сложного планировщика.

---

**Разве однопоточность не является ограничением?**

Нет. Команды Redis выполняются за микросекунды (SET/GET — ~1–10 мкс), поэтому один поток обрабатывает сотни тысяч операций в секунду. Ограничение — не CPU для команд, а сетевой I/O и диск. Начиная с Redis 6.0 сетевой I/O вынесен в отдельные потоки (threaded I/O), persistence (RDB/AOF) тоже выполняется в фоне через fork. Главный поток остаётся однопоточным — это гарантирует атомарность каждой команды без блокировок.

---

**Когда Redis уступает PostgreSQL и когда дополняет его?**

Redis уступает PostgreSQL в: транзакциях с несколькими таблицами (MVCC, ACID), JOIN и сложных запросах, долгосрочном хранении с полнотекстовым поиском, случаях когда RAM ограничен. Redis дополняет PostgreSQL: кеш горячих данных (Cache-Aside), счётчики (INCR — атомарно без транзакции), rate limiting, сессии, очереди задач, pub/sub. Типичная архитектура: PostgreSQL — источник правды, Redis — слой ускорения чтения.

---

**Что такое Eviction Policy и какую выбрать?**

Eviction Policy — стратегия вытеснения при исчерпании `maxmemory`. Варианты:
- `noeviction` — возвращать ошибку при записи (для persistent store)
- `allkeys-lru` — выселять давно не использованные ключи среди всех (рекомендуется для cache)
- `volatile-lru` — LRU только среди ключей с TTL
- `allkeys-lfu` — выселять редко используемые (лучше при hot/cold распределении)
- `volatile-ttl` — выселять ближайшие к истечению срока

Для cache-only Redis: `allkeys-lru` или `allkeys-lfu`. Для mixed (cache + persistent): `volatile-lru` — тогда persistent ключи без TTL не вытесняются.

---

## Группа 2: Структуры данных

**Какие структуры данных предоставляет Redis и их сложность?**

```txt
String  — O(1) GET/SET/INCR/SETNX
Hash    — O(1) HGET/HSET, O(N) HGETALL (N = кол-во полей)
List    — O(1) LPUSH/RPOP/LLEN, O(N) LRANGE
Set     — O(1) SADD/SISMEMBER, O(N) SMEMBERS, O(N) SINTER/SUNION
Sorted Set — O(log N) ZADD/ZRANK, O(log N + M) ZRANGEBYSCORE (M = результатов)
HyperLogLog — O(1) PFADD/PFCOUNT, ~1.5% погрешность, max 12KB
Bitmap  — O(1) SETBIT/GETBIT, O(N) BITCOUNT
Stream  — O(1) XADD, O(log N) XRANGE/XREAD
```

---

**Когда использовать Hash вместо отдельных String ключей?**

Hash — когда нужно хранить несколько атрибутов одного объекта: `HSET user:123 name "Alice" age "30" email "alice@..."`. Преимущества: один ключ вместо трёх (`user:123:name`, `user:123:age`), экономия памяти (Redis оптимизирует маленькие Hash через ziplist/listpack), атомарное чтение нескольких полей через `HMGET`. Ограничение: `HGETALL` O(N) — не использовать для хэшей с тысячами полей.

---

**Как реализовать leaderboard с обновлением рейтинга в реальном времени?**

Sorted Set: `ZADD leaderboard <score> <userId>`. Обновление: `ZINCRBY leaderboard 10 user:123` — атомарно увеличить score. Топ-10: `ZREVRANGE leaderboard 0 9 WITHSCORES`. Ранг пользователя: `ZREVRANK leaderboard user:123` — O(log N). Для sliding window рейтинга по времени: score = timestamp в миллисекундах, `ZRANGEBYSCORE` по диапазону времени + `ZREMRANGEBYSCORE` для удаления старых записей.

---

**Зачем HyperLogLog если есть Set?**

HyperLogLog считает уникальные значения с ~1.5% погрешностью, занимая максимум 12KB независимо от количества элементов. Set с миллионом элементов занимает ~50MB+. Для точного счёта уникальных пользователей за день: Set. Для аналитики (DAU, уникальные просмотры) где 1.5% погрешность допустима: `PFADD dau:2024-01-15 userId` → `PFCOUNT dau:2024-01-15`. Объединение нескольких дней: `PFMERGE dau:week dau:2024-01-15 dau:2024-01-16`.

---

## Группа 3: Паттерны кеширования

**Объясните Cache-Aside и его недостатки.**

Cache-Aside (lazy loading): при чтении — сначала Redis, при miss — PostgreSQL → запись в Redis → возврат. При обновлении — обновить БД → `DEL` ключ из Redis (не SET — race condition: параллельный читатель может записать старые данные между UPDATE и SET). Недостатки: (1) первый запрос после истечения TTL — всегда Cache Miss, (2) при сбое Redis в момент `DEL` — stale data до истечения TTL. Write-Through: писать в Redis и БД одновременно при каждом обновлении — нет stale data, но пишем в кеш данные которые могут не понадобиться.

---

**Что такое Cache Stampede и как предотвратить?**

Cache Stampede (Thundering Herd): 1000 параллельных запросов приходят в момент когда TTL ключа истёк → все идут в БД → перегрузка. Решения: (1) Mutex Lock — первый процесс ставит lock (`SET mutex:key 1 NX EX 5`), остальные ждут и потом читают из кеша; реализуется через Lua-скрипт для атомарного check+get. (2) Random TTL jitter — вместо фиксированного TTL=3600 использовать `3600 + random(0, 300)` — ключи истекают в разное время, нагрузка размазывается. (3) Background refresh — обновлять кеш асинхронно до истечения TTL (probabilistic early recomputation).

---

**Что такое Cache Penetration и Bloom Filter?**

Cache Penetration: запросы к данным которых нет ни в Redis ни в PostgreSQL (например, `GET /users/999999` — несуществующий пользователь). Каждый раз — Cache Miss → запрос в БД → `NULL` → ничего не кешируется → следующий такой же запрос снова идёт в БД. Решения: (1) кешировать `null` — `SET user:999999 "null" EX 60` — при чтении проверять `if cached === "null" return null`; (2) Bloom Filter — вероятностная структура данных, дающая ответ "точно нет" или "вероятно есть", проверять перед обращением к БД. Bloom Filter: false positive возможен, false negative — нет.

---

**Как реализовать rate limiting через Redis?**

Sliding window counter через INCR + EXPIRE:
```typescript
const key = `ratelimit:${userId}:${Math.floor(Date.now() / 60000)}`;
const count = await redis.incr(key);
if (count === 1) await redis.expire(key, 60);
if (count > 100) throw new Error('Rate limit exceeded');
```
Проблема: окно сбрасывается каждую минуту, возможен burst 200 запросов на стыке минут. Точный sliding window: Sorted Set с timestamp как score — `ZADD ratelimit:userId <timestamp> <uuid>`, удалять старые: `ZREMRANGEBYSCORE key 0 <timestamp-60s>`, считать: `ZCARD`. Точнее, но дороже по памяти.

---

## Группа 4: Pub/Sub и Streams

**В чём разница между Pub/Sub и Streams?**

Pub/Sub: ephemeral, fire-and-forget, нет хранения. Если subscriber offline — сообщение теряется. Идеально для: broadcasting WebSocket событий между инстансами, cache invalidation, live dashboard. Streams: append-only persistent log с уникальными ID. Сообщения хранятся до явного удаления. Consumer Groups — каждое сообщение достаётся одному consumer (load balancing). ACK (XACK) — подтверждение обработки, без ACK сообщение остаётся pending и может быть обработано повторно. Streams — это Redis-аналог Kafka для low/medium throughput (~100k/sec).

---

**Почему нельзя использовать одно соединение для subscribe и обычных команд?**

После `SUBSCRIBE`/`PSUBSCRIBE` соединение переходит в режим подписки: разрешены только `SUBSCRIBE`, `UNSUBSCRIBE`, `PSUBSCRIBE`, `PUNSUBSCRIBE`, `PING`, `QUIT`. Попытка выполнить `SET`/`GET` вернёт ошибку. Поэтому всегда нужно два клиента: один для подписки (subscriber connection), другой для команд (publisher/command connection). В ioredis subscriber клиент создаётся через `redis.duplicate()`.

---

**Как масштабировать WebSocket с несколькими инстансами NestJS?**

Проблема: клиент подключён к инстансу A, событие генерируется на инстансе B → клиент не получает. Решение через Redis Pub/Sub: при событии на инстансе B → `redis.publish('user:123:events', JSON.stringify(event))`. Каждый инстанс подписывается на канал пользователя → при получении сообщения ищет WebSocket соединение этого пользователя на СВОЁМ инстансе → отправляет. Socket.IO предоставляет `@socket.io/redis-adapter` — официальная реализация этого же паттерна.

---

**Когда использовать Consumer Groups vs несколько SUBSCRIBE?**

Несколько `SUBSCRIBE` на один канал: fan-out — каждый получает ВСЕ сообщения (уведомления нескольким независимым сервисам). Consumer Group: competing consumers — каждое сообщение достаётся ОДНОМУ consumer из группы (load balancing обработки). Если есть 3 worker'а для обработки заказов и нужно чтобы каждый заказ обрабатывался ровно один раз — Consumer Group. Если событие должно попасть и в service уведомлений и в service аналитики — разные Consumer Groups на одном Stream (каждая группа получает все сообщения независимо).

---

## Группа 5: Distributed Locks

**Как реализовать distributed lock и почему важен уникальный токен?**

`SET lock:resource <uuid> NX PX 30000` — атомарно: создать только если не существует + TTL 30 секунд. UUID (уникальный токен) нужен чтобы освободить только СВОЙ lock. Сценарий без токена: Process A захватил lock (TTL=5s), завис на 6 сек → TTL истёк → Process B захватил lock → Process A возобновился → `DEL lock` → случайно освободил чужой lock. С токеном: `GET lock` → если значение совпадает с нашим UUID → `DEL lock`. Но GET + DEL — два отдельных шага, между которыми может истечь TTL, поэтому обязателен Lua-скрипт.

---

**Почему для освобождения lock нужен Lua-скрипт?**

Между `GET lock` (проверка токена) и `DEL lock` (удаление) — не атомарный промежуток. Если TTL истёк именно между ними: Process B захватил lock после GET, а Process A выполняет DEL и удаляет чужой lock. Lua-скрипт выполняется атомарно (Redis single-threaded гарантирует: между командами внутри Lua никто не вклинится):
```lua
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
```
Вернёт 1 (успешно удалено) или 0 (токен не совпал — lock уже у другого).

---

**Когда использовать Redlock вместо обычного Redis lock?**

Redlock нужен при строгих требованиях к надёжности: один Redis инстанс — Single Point of Failure. Если Redis упал сразу после выдачи lock — новый Master (после Sentinel failover) не знает об этом lock → два процесса одновременно считают что у них lock. Redlock: `N` независимых Redis инстансов (3 или 5), lock считается полученным только если `>N/2` инстансов ответили успехом за время `< TTL * 0.1`. Даже если один инстанс упал — quorum сохраняется. Для большинства приложений: Single Redis + Sentinel достаточно. Redlock — для критичной инфраструктуры (финансовые операции, распределённые транзакции).

---

**Redis Lock vs PostgreSQL SELECT FOR UPDATE — когда что выбрать?**

PostgreSQL `FOR UPDATE`: блокирует строку на время транзакции, автоматически снимается при commit/rollback, не нужен Redis. Использовать когда: операция атомарна внутри одной PostgreSQL транзакции. Redis Lock: использовать когда: (1) операция затрагивает несколько сервисов/БД; (2) нужна блокировка до начала транзакции; (3) блокировать внешний API-вызов (не только БД); (4) Cron job — только один инстанс должен запускать job. Пример: Redis Lock → вызов Payment API → запись в БД. `FOR UPDATE` не поможет для Payment API.

---

## Группа 6: Persistence и High Availability

**Чем RDB отличается от AOF и что выбрать для production?**

RDB (Redis Database): бинарный снапшот всей памяти через `BGSAVE` (fork + Copy-on-Write). Плюсы: компактный файл, быстрое восстановление при рестарте. Минусы: потеря данных между снапшотами (минуты). AOF (Append Only File): лог каждой write-команды, `appendfsync everysec` — потеря максимум 1 секунды. Плюсы: минимальная потеря данных, читаемый формат. Минусы: файл больше, медленнее восстановление на большом логе. Production рекомендация: RDB + AOF вместе — при рестарте Redis использует AOF (точнее), RDB — для быстрого disaster recovery. Cache-only Redis: оба выключить.

---

**Что такое AOF Rewrite и почему он нужен?**

AOF накапливает всю историю команд: 1000 `INCR counter` → 1000 строк в AOF. Но конечное состояние — один ключ с одним значением. `BGREWRITEAOF` (или автоматический при `auto-aof-rewrite-percentage 100`) перезаписывает AOF в минимальный эквивалентный набор команд: 1000 `INCR` → один `SET counter 1000`. Выполняется в background через fork, не блокирует Redis. Без Rewrite: AOF бесконечно растёт, восстановление при рестарте занимает всё больше времени.

---

**В чём разница между Sentinel и Cluster?**

Sentinel: мониторинг и автоматический failover без шардинга. 3+ Sentinel процессов следят за Master. При падении: vote → один Sentinel инициирует failover → Replica становится Master → клиенты обновляют адрес. Весь dataset на одном Master (одна копия). Использовать: HA нужна, данные помещаются в RAM одного сервера. Redis Cluster: шардинг (16384 hash slots) + HA. Данные распределены по N Master нодам, каждый Master имеет Replicas. Автоматический failover внутри кластера. Ограничение: multi-key операции работают только для ключей в одном hash slot. Использовать: dataset не помещается в RAM одного сервера.

---

**Когда правильно выключить persistence у Redis?**

Для cache-only Redis: `appendonly no` + `save ""` (отключить RDB). Обоснование: при потере данных кеша — просто Cache Miss, PostgreSQL — источник правды. Persistence добавляет overhead: RDB fork может влиять на latency при большом dataset, AOF вызывает disk I/O. Конфигурация cache-only: `maxmemory 2gb` + `maxmemory-policy allkeys-lru` + persistence off. НЕ выключать если Redis используется как: job queue (BullMQ), distributed locks с критичными ресурсами, primary store для сессий где logout при рестарте недопустим.

---

**Что такое replica lag и как он влияет на приложение?**

Репликация в Redis асинхронная: Master записывает команду → отправляет Replica → Replica применяет. Lag обычно <1ms, но при высокой нагрузке или медленной сети — сотни мс. Последствие: чтение с Replica сразу после записи в Master может вернуть устаревшие данные (stale read). Решение для критичных чтений: читать с Master. Для некритичных (кеш, аналитика): Replica допустима. В приложении: два клиента — `masterClient` для записи и критичных чтений, `replicaClient` для масштабирования некритичных чтений. При Sentinel failover: клиент должен переподключиться к новому Master через Sentinel endpoint (не хардкодить адрес Master).
