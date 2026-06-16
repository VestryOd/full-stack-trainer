# Distributed Locks

## The Race Condition problem in distributed systems

```txt
Scenario: two services try to withdraw from the same account

Account balance = $100
Service A: reads $100, calculates $100 - $70 = $30
Service B: reads $100, calculates $100 - $80 = $20
Service A: writes $30
Service B: writes $20  ← overwrites A! Result $20 instead of rejection

Monolith: mutex.lock() → one thread at a time
Distributed: 3 service instances → local mutex doesn't help
Solution: Redis distributed lock — shared across all instances
```

## SET NX EX — the basic distributed lock

```typescript
import { createClient } from 'redis';
import { randomUUID } from 'crypto';

const redis = createClient({ url: process.env.REDIS_URL });

class RedisLock {
  constructor(private redis: ReturnType<typeof createClient>) {}

  async acquire(resource: string, ttlMs: number): Promise<string | null> {
    const lockKey = `lock:${resource}`;
    const token = randomUUID(); // unique owner token

    // SET NX EX — atomic: create ONLY if not exists + TTL
    const acquired = await this.redis.set(lockKey, token, {
      NX: true,          // set only if Not eXists
      PX: ttlMs,         // TTL in milliseconds
    });

    return acquired ? token : null; // null if lock is taken
  }

  async release(resource: string, token: string): Promise<boolean> {
    const lockKey = `lock:${resource}`;

    // CRITICAL: verify we are releasing OUR lock, not someone else's!
    // Without check: TTL expired → another process acquired lock → we accidentally release it
    // Lua script: atomic check + delete (can't do it with two separate commands!)
    const luaScript = `
      if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
      else
        return 0
      end
    `;

    const result = await this.redis.eval(luaScript, {
      keys: [lockKey],
      arguments: [token],
    }) as number;

    return result === 1;
  }
}

// Usage
async function processPayment(orderId: string, amount: number) {
  const lock = new RedisLock(redis);
  const token = await lock.acquire(`order:${orderId}`, 30_000); // 30 sec TTL

  if (!token) {
    throw new Error('Payment already being processed'); // lock is taken
  }

  try {
    // Critical section — only one instance at a time
    const account = await db.account.findUnique({ where: { orderId } });
    if (account.balance < amount) throw new Error('Insufficient funds');

    await db.account.update({
      where: { orderId },
      data: { balance: { decrement: amount } },
    });

    await db.payment.create({ data: { orderId, amount, status: 'completed' } });
  } finally {
    await lock.release(`order:${orderId}`, token);
  }
}
```

## Why a Lua script is required for release

```txt
Problem without Lua (two separate GET + DEL):

Process A: SET lock:123 "token-A" NX EX 5
Process A: ... working (delay > 5 sec) ...
Redis:      TTL expires → lock deleted
Process B:  SET lock:123 "token-B" NX EX 5  ← Process B acquires the lock
Process A:  GET lock:123 → "token-B"  ← sees someone else's token
Process A:  DEL lock:123  ← ERROR! deletes Process B's lock

Lua script: GET and DEL in one atomic operation
Redis single-threaded: nothing can interleave between check and delete
```

## Lock with retry and timeout

```typescript
async function acquireWithRetry(
  lock: RedisLock,
  resource: string,
  ttlMs: number,
  maxWaitMs: number,
): Promise<string> {
  const deadline = Date.now() + maxWaitMs;
  const retryDelayMs = 50;

  while (Date.now() < deadline) {
    const token = await lock.acquire(resource, ttlMs);
    if (token) return token;

    await new Promise(resolve => setTimeout(resolve, retryDelayMs + Math.random() * 50));
  }

  throw new Error(`Could not acquire lock for ${resource} within ${maxWaitMs}ms`);
}

// Usage: process an order, waiting up to 5 seconds for the lock
const token = await acquireWithRetry(lock, `order:${orderId}`, 30_000, 5_000);
```

## Redlock — reliability with multiple Redis nodes

```typescript
// Redlock algorithm (npm package: redlock)
// Protects against: a single Redis node crashing after granting a lock (SPOF)

import Redlock from 'redlock';
import { createClient } from 'redis';

// 3-5 independent Redis instances (separate machines, not sentinel/cluster)
const clients = [
  createClient({ url: 'redis://redis-1:6379' }),
  createClient({ url: 'redis://redis-2:6379' }),
  createClient({ url: 'redis://redis-3:6379' }),
];

await Promise.all(clients.map(c => c.connect()));

const redlock = new Redlock(clients, {
  retryCount: 3,
  retryDelay: 200,   // ms between retries
  driftFactor: 0.01, // compensate for clock drift (1%)
});

// Acquire lock from a majority (2/3 nodes)
async function processWithRedlock(orderId: string) {
  // lock is automatically released at the end of the using block (or in finally)
  await using lock = await redlock.acquire([`lock:order:${orderId}`], 30_000);

  // If 2/3 instances confirmed the lock → safe to proceed
  await processPaymentLogic(orderId);
  // lock.release() is called automatically
}
```

```txt
Redlock algorithm:
1. Start clock: startTime = currentTime
2. Try SET NX PX on all N nodes (small timeout to avoid hanging)
3. If quorum (>N/2) replied OK AND elapsed < ttl*0.1 → lock acquired
4. Effective TTL = TTL - elapsed - clockDrift
5. If quorum not reached → DEL on all nodes, retry

When Redlock is overkill:
  Single Redis instance with Sentinel → sufficient for most applications
  Redlock: for critical infrastructure where losing a lock = serious problem
```

## Redis Lock vs PostgreSQL FOR UPDATE

```typescript
// PostgreSQL SELECT FOR UPDATE — alternative to Redis lock
// Use when the operation already talks to PostgreSQL anyway

// With PostgreSQL (no Redis needed):
await prisma.$transaction(async (tx) => {
  const account = await tx.$queryRaw`
    SELECT * FROM accounts WHERE id = ${accountId} FOR UPDATE
  `;
  // Row is locked for the duration of the transaction
  // Another request on the same row → waits for the transaction to complete
  await tx.account.update({
    where: { id: accountId },
    data: { balance: { decrement: amount } },
  });
});

// Use Redis Lock when:
// - The operation spans multiple DBs/services
// - You need to lock an external API call (not just the DB)
// - A lock is needed without a transaction (e.g., rate-limit on an endpoint)
// - Cron job: only one instance should run the job
```

## Common interview mistakes

- **"SET NX EX is an atomic operation"** — yes, it's one atomic command. But wrong usage: `SET lock NX` without `EX` → if the process crashes → deadlock forever. Always: `SET lock token NX EX <seconds>` or `PX <milliseconds>`.

- **"DEL is enough to release the lock"** — no. Scenario: Process A acquires lock (TTL=5s), stalls for 6s → TTL expires → Process B acquires lock → Process A resumes → `DEL lock` → Process B loses its lock. Correct: Lua script: GET + compare token + DEL atomically.

- **"Redlock is needed for any production lock"** — for most applications, Single Redis + Sentinel (or Redis Cluster) is sufficient. Redlock is only needed when there are strict consistency requirements and losing a lock on a single-node failure is truly catastrophic. Martin Kleppmann also pointed out that even Redlock doesn't provide 100% guarantees under GC pauses.

- **"Redis Lock replaces PostgreSQL transactions"** — different tools. If the operation is atomic within a single PostgreSQL transaction — use `FOR UPDATE` or transaction serialization. Redis Lock is needed for cross-service coordination or when a lock is needed before the transaction begins.

- **"Lock TTL can be chosen arbitrarily"** — TTL must be greater than the maximum expected duration of the critical section + a buffer. Too short → lock expires while the process is still working → another process acquires it → race condition. Too long → if the process crashes, the resource stays locked for too long. Typical: 2-10x the expected operation time.
