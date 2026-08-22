# Redis Persistence

## RDB — periodic snapshots

RDB (Redis Database) — a binary snapshot of the entire Redis memory at a point in time. Saved to `dump.rdb` via a fork process (parent keeps handling commands, child writes to disk via Copy-On-Write).

```txt
redis.conf — RDB configuration:
  save 3600 1     # snapshot if 1+ key changed in 1 hour
  save 300 100    # snapshot if 100+ keys changed in 5 min
  save 60 10000   # snapshot if 10000+ keys changed in 1 min

  dbfilename dump.rdb
  dir /var/lib/redis

Manual snapshot:
  BGSAVE   # asynchronously in the background (non-blocking)
  SAVE     # synchronously (blocks Redis — never use in production!)

  LASTSAVE # timestamp of the last successful RDB

RDB advantages:
  ✓ Compact binary file (smaller than AOF)
  ✓ Fast recovery on restart (no replay needed)
  ✓ Minimal I/O overhead (only during snapshot)
  ✓ Convenient for disaster recovery (single file)

RDB disadvantages:
  ✗ Data loss: everything written after the last snapshot
  ✗ Fork for the snapshot: at >10GB of data the fork costs
```

## AOF — append-only log of every command

AOF (Append Only File) — a log of every write command. On restart, Redis replays the full log to restore state.

```txt
redis.conf — AOF configuration:
  appendonly yes
  appendfilename "appendonly.aof"

  # fsync policy (the main trade-off):
  appendfsync always    # fsync after every command
                        # → maximum reliability, slow
  appendfsync everysec  # fsync once per second
                        # → compromise (recommended)
  appendfsync no        # the OS decides when → fast, but
                        # data can be lost on a crash

AOF Rewrite (log compaction):
  Over time AOF grows: 1000 INCR → can be replaced with one SET
  auto-aof-rewrite-percentage 100  # rewrite when the AOF has
                                   # doubled from its base size
  auto-aof-rewrite-min-size 64mb   # but not before AOF hits 64MB
  BGREWRITEAOF  # manual rewrite (background, non-blocking)

AOF advantages:
  ✓ Maximum data loss: 1 second (with everysec)
  ✓ Human-readable format (can manually fix on corruption)
  ✓ appendonly yes + everysec → sufficient for most production cases

AOF disadvantages:
  ✗ Larger file than RDB (stores command history, not final state)
  ✗ Slower recovery (replay of the entire log)
  ✗ appendfsync always → noticeable I/O overhead
```

## RDB + AOF together (production recommendation)

The two are not competitors. RDB gives you a small file and a fast restart, AOF gives you a small loss window, and running both costs little. On restart Redis prefers the AOF, because it is the more accurate of the two.

```txt
Combination: redis.conf
  save 3600 1        # RDB for fast restart
  appendonly yes     # AOF for minimal data loss
  appendfsync everysec

On restart (if both are enabled):
  Redis uses AOF — it's more precise (less data loss)

Strategy:
  Cache-only Redis:  persistence off (maxmemory + eviction policy)
  Session/Queue:     AOF everysec (1 sec loss acceptable)
  Primary DB mode:   AOF always + RDB (maximum reliability, slower)
```

## Replication — Master/Replica

A replica is a read-only copy that follows one master. You set it up in the config file, not in application code:

```txt
# redis.conf on the replica
replicaof <master-ip> <master-port>
masterauth <password>
```

To check what a node currently is, run the `ROLE` command. A master answers `['master', offset, [list of replicas]]`, a replica answers `['slave', master-ip, master-port, state, offset]`.

In Node.js with ioredis, keep two separate clients — one for writes, one for scaled reads:

```typescript
const masterClient = new Redis({ host: 'redis-master', port: 6379 });
const replicaClient = new Redis({ host: 'redis-replica', port: 6379 });

// Writes → master
await masterClient.set('user:123', JSON.stringify(user));

// Reads → replica (read scaling)
const cached = await replicaClient.get('user:123');
// Important: replication is async → possible lag of a few ms
```

```txt
Replication:
  Master → async replication → Replica(s)
  Replica: read-only (by default), offloads reads from master
  Replica lag: usually <1ms on a stable connection
  If Master fails: replica does NOT become master automatically
  → Sentinel or Redis Cluster is required

Redis Sentinel (HA without sharding):
  3+ Sentinel processes monitor the Master
  On failure: Sentinel vote → elect new Master → update DNS
  Client connects to Sentinel → gets current Master address
  Failover: ~10-30 seconds

  Limitation: full dataset on one Master (no sharding)
  Use when: HA is needed, dataset fits in one server's RAM

Redis Cluster (sharding + HA):
  16384 hash slots → distributed across N master nodes
  Each master has replicas
  key → CRC16(key) % 16384 → slot → node
  Automatic failover within the cluster
  Limitation: multi-key ops work only within one hash slot
```

## Persistence disabled — when it's the right choice

Turning persistence off is a real option, not a shortcut. It is correct exactly when losing the whole dataset costs you nothing but a slow first request.

```txt
Redis as ephemeral cache (maxmemory + allkeys-lru):
  appendonly no
  save ""  # disable RDB

When this fits:
  Cache layer on top of PostgreSQL — data loss = a Cache MISS
  Session storage if user logouts on restart are acceptable
  Rate limiting counters — reset on restart is acceptable

When it does NOT fit:
  BullMQ job queue — jobs will be lost on restart
  Distributed locks for critical resources
  Redis as primary database for any data
```

## Common interview mistakes

- **"Redis loses data on restart"** — only without persistence. With AOF `everysec`: maximum loss is 1 second of data. With `always`: no loss (every command is synchronously flushed to disk, but slower). For critical data: AOF + RDB combination.

- **"RDB is better than AOF"** — different trade-offs. RDB: fast restart, compact, data loss up to several minutes. AOF: slower restart with large log, more disk space, loss up to 1 sec. Production: both together.

- **"Replica automatically becomes Master when the Master fails"** — no. Without Sentinel or Cluster: the replica stays a replica. Sentinel is needed for automatic failover. Without Sentinel you promote by hand. Run `REPLICAOF NO ONE` on the replica, then update the config or the DNS (domain name system) record that clients follow.

- **"Redis Cluster solves all scaling problems"** — Cluster adds complexity. Multi-key operations (`MGET`, `MSET`, Lua scripts) only work if all keys are in the same hash slot. If keys are on different nodes → error. Solution: hash tags `{prefix}:key` or avoid cross-slot operations.

- **"SAVE is safe in production"** — `SAVE` blocks Redis until snapshotting is complete. With a large dataset — seconds of blocking. In production, always use `BGSAVE` (background, via fork, doesn't block command processing).
