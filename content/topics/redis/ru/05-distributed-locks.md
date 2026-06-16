<!-- verified: 2026-06-05, corrections: 0 -->
# Distributed Locks

## Проблема Race Condition в distributed системах

```txt
Сценарий: два сервиса пытаются списать деньги с одного счёта

Account balance = $100
Service A: читает $100, вычисляет $100 - $70 = $30
Service B: читает $100, вычисляет $100 - $80 = $20
Service A: записывает $30
Service B: записывает $20  ← перезаписывает A! Итог $20 вместо отклонения

Монолит: mutex.lock() → один поток за раз
Distributed: 3 инстанса сервиса → локальный mutex не помогает
Решение: Redis distributed lock — общий для всех инстансов
```

## SET NX EX — базовый distributed lock

```typescript
import { createClient } from 'redis';
import { randomUUID } from 'crypto';

const redis = createClient({ url: process.env.REDIS_URL });

class RedisLock {
  constructor(private redis: ReturnType<typeof createClient>) {}

  async acquire(resource: string, ttlMs: number): Promise<string | null> {
    const lockKey = `lock:${resource}`;
    const token = randomUUID(); // уникальный токен владельца

    // SET NX EX — атомарно: создать ТОЛЬКО если не существует + TTL
    const acquired = await this.redis.set(lockKey, token, {
      NX: true,          // set only if Not eXists
      PX: ttlMs,         // TTL в миллисекундах
    });

    return acquired ? token : null; // null если lock занят
  }

  async release(resource: string, token: string): Promise<boolean> {
    const lockKey = `lock:${resource}`;

    // КРИТИЧНО: проверить что освобождаем СВОЙ lock, не чужой!
    // Без проверки: TTL истёк → другой процесс захватил lock → мы случайно освобождаем его lock
    // Lua script: атомарная проверка + удаление (нельзя делать двумя отдельными командами!)
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

// Использование
async function processPayment(orderId: string, amount: number) {
  const lock = new RedisLock(redis);
  const token = await lock.acquire(`order:${orderId}`, 30_000); // 30 сек TTL

  if (!token) {
    throw new Error('Payment already being processed'); // lock занят
  }

  try {
    // Критическая секция — только один инстанс
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

## Почему Lua script обязателен для release

```txt
Проблема без Lua (два отдельных GET + DEL):

Process A: SET lock:123 "token-A" NX EX 5
Process A: ... работает (задержка 5+ сек) ...
Redis:      TTL истёк → lock удалён
Process B:  SET lock:123 "token-B" NX EX 5  ← Process B захватил lock
Process A:  GET lock:123 → "token-B"  ← видит чужой токен
Process A:  DEL lock:123  ← ОШИБКА! удаляет чужой lock

Lua script: GET и DEL в одной атомарной операции
Redis single-threaded: между check и delete никто не может вклиниться
```

## Lock с retry и timeout

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

// Использование: обрабатывать заказ с ожиданием до 5 сек
const token = await acquireWithRetry(lock, `order:${orderId}`, 30_000, 5_000);
```

## Redlock — надёжность с несколькими Redis нодами

```typescript
// Redlock алгоритм (ioredis-based библиотека: redlock npm package)
// Защищает от: одиночного Redis упавшего после выдачи lock (SPOF)

import Redlock from 'redlock';
import { createClient } from 'redis';

// 3-5 независимых Redis инстансов (разные машины, не sentinel/cluster)
const clients = [
  createClient({ url: 'redis://redis-1:6379' }),
  createClient({ url: 'redis://redis-2:6379' }),
  createClient({ url: 'redis://redis-3:6379' }),
];

await Promise.all(clients.map(c => c.connect()));

const redlock = new Redlock(clients, {
  retryCount: 3,
  retryDelay: 200,  // ms между попытками
  driftFactor: 0.01, // компенсация clock drift (1%)
});

// Получение lock через большинство (2/3 нод)
async function processWithRedlock(orderId: string) {
  // lock автоматически освобождается в конце using block (или в finally)
  await using lock = await redlock.acquire([`lock:order:${orderId}`], 30_000);

  // Если 2/3 инстансов подтвердили lock → безопасно работать
  await processPaymentLogic(orderId);
  // lock.release() вызывается автоматически
}
```

```txt
Redlock: алгоритм
1. Запустить clock: startTime = currentTime
2. Попробовать SET NX PX на всех N нодах (малый timeout чтобы не зависнуть)
3. Если quorum (>N/2) ответили OK И elapsed < ttl*0.1 → lock получен
4. Effective TTL = TTL - elapsed - clockDrift
5. Если quorum не достигнут → DEL на всех нодах, retry

Когда Redlock избыточен:
  Single Redis инстанс с Sentinel → достаточно для большинства приложений
  Redlock: для критичной инфраструктуры где потеря lock = серьёзная проблема
```

## Redis Lock vs PostgreSQL FOR UPDATE

```typescript
// PostgreSQL SELECT FOR UPDATE — alternative к Redis lock
// Использовать когда операция всё равно обращается к PostgreSQL

// С PostgreSQL (не нужен Redis):
await prisma.$transaction(async (tx) => {
  const account = await tx.$queryRaw`
    SELECT * FROM accounts WHERE id = ${accountId} FOR UPDATE
  `;
  // Строка заблокирована на время транзакции
  // Другой запрос на ту же строку → ждёт завершения транзакции
  await tx.account.update({
    where: { id: accountId },
    data: { balance: { decrement: amount } },
  });
});

// С Redis lock (нужен когда):
// - Операция затрагивает несколько БД/сервисов
// - Нужно заблокировать внешний API вызов (не только БД)
// - Нужна блокировка без транзакции (например, rate limit на endpoint)
// - Cron job: только один инстанс должен запускать job
```

## Типичные ошибки на интервью

- **"SET NX EX — атомарная операция"** — да, это одна атомарная команда. Но неправильное использование: `SET lock NX` без `EX` → если процесс упал → deadlock навсегда. Всегда `SET lock token NX EX <seconds>` или `PX <milliseconds>`.

- **"Для release достаточно DEL"** — нет. Сценарий: Process A захватил lock (TTL=5сек), завис на 6 сек → TTL истёк → Process B захватил lock → Process A возобновился → `DEL lock` → Process B потерял lock. Правильно: Lua script: GET + compare token + DEL атомарно.

- **"Redlock нужен для любого production lock"** — для большинства приложений Single Redis + Sentinel (или Redis Cluster) достаточно. Redlock нужен только при жёстких требованиях к консистентности и недопустимости потери lock при сбое одной ноды. Martin Kleppmann ([Kleppmann Critique](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)) указывал, что даже Redlock не даёт 100% гарантии при GC паузах.

- **"Redis Lock заменяет PostgreSQL транзакции"** — разные инструменты. Если операция атомарна внутри одной PostgreSQL транзакции — используй `FOR UPDATE` или сериализацию транзакций. Redis Lock нужен для cross-service координации или когда lock нужен до начала транзакции.

- **"TTL lock можно выбирать произвольно"** — TTL должен быть больше максимального ожидаемого времени критической секции + буфер. Слишком маленький TTL → lock истечёт пока процесс работает → другой захватит lock → race condition. Слишком большой → при сбое процесса ресурс заблокирован надолго. Typical: 2-10x ожидаемого времени операции.
