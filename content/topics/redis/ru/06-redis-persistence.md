<!-- verified: 2026-06-05, corrections: 0 -->
# Redis Persistence

## RDB — периодические снапшоты

RDB (Redis Database) — бинарный снапшот всей памяти Redis на момент времени. Сохраняется в `dump.rdb` через fork процесс (родитель продолжает обрабатывать команды, дочерний пишет на диск через Copy-On-Write).

```txt
redis.conf — настройка RDB:
  save 3600 1     # snapshot если за 1 час изменился хотя бы 1 ключ
  save 300 100    # snapshot если за 5 мин изменилось 100+ ключей
  save 60 10000   # snapshot если за 1 мин изменилось 10000+ ключей
  
  dbfilename dump.rdb
  dir /var/lib/redis

Ручной snapshot:
  BGSAVE   # асинхронно в background (не блокирует)
  SAVE     # синхронно (блокирует Redis — не использовать в production!)
  
  LASTSAVE # timestamp последнего успешного RDB

RDB преимущества:
  ✓ Компактный бинарный файл (меньше AOF)
  ✓ Быстрое восстановление при рестарте (replay не нужен)
  ✓ Минимальный I/O overhead (только при snapshot)
  ✓ Удобен для disaster recovery (один файл)

RDB недостатки:
  ✗ Потеря данных: всё что записано после последнего snapshot
  ✗ Fork для snapshot: при >10GB данных fork overhead заметен
```

## AOF — append-only log каждой команды

AOF (Append Only File) — лог каждой write команды. При рестарте Redis воспроизводит весь лог для восстановления состояния.

```txt
redis.conf — настройка AOF:
  appendonly yes
  appendfilename "appendonly.aof"
  
  # fsync политика (главный trade-off):
  appendfsync always    # fsync после каждой команды → максимальная надёжность, медленно
  appendfsync everysec  # fsync раз в секунду → компромисс (рекомендуется)
  appendfsync no        # OS решает когда → быстро, но возможна потеря при сбое

AOF Rewrite (сжатие лога):
  Со временем AOF растёт: 1000 INCR → можно заменить одним SET
  auto-aof-rewrite-percentage 100  # rewrite если AOF вырос в 2x от base
  auto-aof-rewrite-min-size 64mb   # но не раньше чем AOF достиг 64MB
  BGREWRITEAOF  # ручной rewrite (background, не блокирует)

AOF преимущества:
  ✓ Максимум потеря 1 секунды данных (с everysec)
  ✓ Читаемый формат (можно вручную исправить при повреждении)
  ✓ appendonly yes + everysec → достаточно для большинства production случаев

AOF недостатки:
  ✗ Файл больше RDB (хранит историю команд, не конечное состояние)
  ✗ Восстановление медленнее (replay всего лога)
  ✗ При appendfsync always — заметный I/O overhead
```

## RDB + AOF вместе (Production рекомендация)

```txt
Комбинация: redis.conf
  save 3600 1        # RDB для fast restart
  appendonly yes     # AOF для minimal data loss
  appendfsync everysec

При рестарте (если оба включены):
  Redis использует AOF — он точнее (меньше потеря данных)

Стратегия:
  Cache-only Redis:  persistence off (maxmemory + eviction policy)
  Session/Queue:     AOF everysec (1 сек потеря допустима)
  Primary DB mode:   AOF always + RDB (максимальная надёжность, медленнее)
```

## Replication — Master/Replica

```typescript
// redis.conf для Replica:
// replicaof <master-ip> <master-port>
// masterauth <password>

// Программно можно проверить роль:
// ROLE → ['master', offset, [[replica-ip, replica-port, offset], ...]]
//     или ['slave', master-ip, master-port, state, offset]

// В Node.js с ioredis — отдельные clients:
const masterClient = new Redis({ host: 'redis-master', port: 6379 });
const replicaClient = new Redis({ host: 'redis-replica', port: 6379 });

// Writes → master
await masterClient.set('user:123', JSON.stringify(user));

// Reads → replica (read scaling)
const cached = await replicaClient.get('user:123');
// Важно: replication асинхронная → возможен lag в несколько мс
```

```txt
Replication:
  Master → асинхронная репликация → Replica(s)
  Replica: read-only (по умолчанию), снижает нагрузку на master
  Replica lag: обычно <1ms при стабильном соединении
  При падении Master: replica не становится master автоматически
  → нужен Sentinel или Redis Cluster

Redis Sentinel (HA без шардинга):
  3+ Sentinel процессов мониторят Master
  При сбое: Sentinel vote → выбирают нового Master → обновляют DNS
  Клиент подключается к Sentinel → получает адрес текущего Master
  Failover: ~10-30 секунд
  
  Ограничение: весь dataset на одном Master (нет шардинга)
  Подходит: когда нужна HA, но данные помещаются в RAM одного сервера

Redis Cluster (шардинг + HA):
  16384 hash slots → распределены по N мастер-нодам
  Каждый master имеет replicas
  key → CRC16(key) % 16384 → slot → node
  Автоматический failover внутри cluster
  Ограничение: multi-key операции только для ключей в одном slot
```

## Persistence выключена — когда это правильно

```txt
Redis как ephemeral cache (maxmemory + allkeys-lru):
  appendonly no
  save ""  # отключить RDB

Когда подходит:
  Cache layer поверх PostgreSQL — при потере кэша просто Cache MISS
  Session storage если допустимо logout пользователей при рестарте
  Rate limiting counters — reset при рестарте приемлем

Когда НЕ подходит:
  BullMQ job queue — задачи потеряются при перезапуске
  Distributed locks с критичными ресурсами
  Redis как primary database для любых данных
```

## Типичные ошибки на интервью

- **"Redis теряет данные при перезапуске"** — только без persistence. С AOF `everysec`: потеря максимум 1 секунда данных. С `always`: нет потери (каждая команда синхронно на диск, но медленно). Для критичных данных: AOF + RDB комбинация.

- **"RDB лучше AOF"** — разные trade-offs. RDB: быстрый restart, компактный, потеря данных до нескольких минут. AOF: медленный restart при большом логе, больше места, потеря до 1 сек. Production: оба вместе.

- **"Replica автоматически становится Master при падении"** — нет. Без Sentinel или Cluster: replica остаётся replica. Нужен Sentinel для автоматического failover. Без Sentinel: ручная смена (`REPLICAOF NO ONE` на replica, обновить DNS/config).

- **"Redis Cluster решает все проблемы масштабирования"** — Cluster добавляет сложность. Multi-key операции (`MGET`, `MSET`, Lua scripts) работают только если все ключи в одном hash slot. Если ключи на разных нодах → ошибка. Решение: hash tags `{prefix}:key` или избегать cross-slot операций.

- **"SAVE безопасен в production"** — `SAVE` блокирует Redis до завершения snapshotting. При большом dataset — секунды блокировки. В production только `BGSAVE` (background, через fork, не блокирует обработку команд).
