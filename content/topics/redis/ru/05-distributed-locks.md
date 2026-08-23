<!-- verified: 2026-06-05, corrections: 0 -->
# Распределённые блокировки

## Проблема Race Condition в распределённых системах

Race condition — это когда два процесса читают одно и то же значение, а потом оба записывают результат, посчитанный по устаревшему чтению. Внутри одного процесса это лечится мьютексом. У трёх инстансов сервиса общего мьютекса нет, поэтому блокировка должна лежать там, где её видят все.

```txt
Сценарий: два сервиса пытаются списать деньги с одного счёта

Account balance = $100
Service A: читает $100, вычисляет $100 - $70 = $30
Service B: читает $100, вычисляет $100 - $80 = $20
Service A: записывает $30
Service B: записывает $20  ← перезаписывает A! Итог $20

Монолит: mutex.lock() → один поток за раз
Distributed: 3 инстанса сервиса → локальный mutex не помогает
Решение: Redis distributed lock — общий для всех инстансов
```

## SET NX EX — базовая распределённая блокировка

Одна команда — и блокировка готова. NX означает «not exists»: Redis запишет ключ, только если его ещё нет, поэтому гонку выигрывает ровно один вызывающий. `EX` и `PX` задают TTL (time to live) — срок жизни ключа в секундах или миллисекундах, чтобы упавший процесс не держал блокировку вечно.

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

    // Критично: проверить, что освобождаем свой lock, а не чужой!
    // Без проверки: TTL истёк, lock захватил другой процесс,
    // и мы освободим чужую блокировку
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

Проверка токена и удаление ключа — два обращения к серверу, и в промежутке между ними у блокировки может смениться владелец. Lua убирает этот промежуток: весь скрипт Redis выполняет как одну команду.

```txt
Проблема без Lua (два отдельных GET + DEL):

Process A: SET lock:123 "token-A" NX EX 5
Process A: ... работает (задержка 5+ сек) ...
Redis:      TTL истёк → lock удалён
Process B:  SET lock:123 "token-B" NX EX 5  ← B захватил lock
Process A:  GET lock:123 → "token-B"  ← видит чужой токен
Process A:  DEL lock:123  ← ОШИБКА! удаляет чужой lock

Lua script: GET и DEL в одной атомарной операции
Redis однопоточен: между check и delete никто не вклинится
```

## Lock с retry и timeout

Не получить блокировку — это ещё не ошибка: обычно достаточно подождать и попробовать снова. Добавьте к каждой попытке небольшую случайную задержку, чтобы ожидающие процессы не стучались в один и тот же момент.

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

Один узел Redis — единая точка отказа. Если он умрёт сразу после выдачи блокировки, сменщик о ней ничего не знает, и блокировку заберёт второй процесс. Redlock размазывает блокировку по нескольким независимым узлам и считает её взятой, только если согласилось большинство.

```typescript
// Redlock алгоритм (npm-пакет: redlock)
// Защищает от падения одиночного Redis сразу после выдачи lock

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
  // Если 2/3 инстансов подтвердили lock → безопасно работать
  const lock = await redlock.acquire([`lock:order:${orderId}`], 30_000);
  try {
    await processPaymentLogic(orderId);
  } finally {
    await lock.release(); // освобождаем даже при исключении
  }
}

// В TypeScript 5.2+ есть форма короче: `await using` сам вызовет
// lock.release() при выходе из блока:
// await using lock = await redlock.acquire([...], 30_000);
```

```txt
Redlock: алгоритм
1. Запустить clock: startTime = currentTime
2. Попробовать SET NX PX на всех N нодах (малый timeout,
   чтобы не зависнуть на мёртвой ноде)
3. Если quorum (>N/2) ответили OK И elapsed < ttl*0.1 → lock получен
4. Effective TTL = TTL - elapsed - clockDrift
5. Если quorum не достигнут → DEL на всех нодах, retry

Когда Redlock избыточен:
  Один инстанс Redis с Sentinel → хватает большинству
  Redlock: для критичной инфраструктуры, где потеря lock —
  серьёзная проблема
```

## Redis Lock vs PostgreSQL FOR UPDATE

Если вся операция и так укладывается в одну транзакцию PostgreSQL, Redis не нужен: `SELECT ... FOR UPDATE` блокирует строку, а commit снимает блокировку. Redis-блокировка нужна, когда критическая секция выходит за пределы этой транзакции.

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

- **"Для release достаточно `DEL`"** — нет. Process A захватил lock с TTL=5 сек и завис на 6 сек. TTL истёк, lock захватил Process B. Process A очнулся, выполнил `DEL lock` — и Process B потерял свою блокировку. Правильно: Lua-скрипт, который атомарно делает `GET`, сверяет токен и вызывает `DEL`.

- **"Redlock нужен для любого production lock"** — для большинства приложений Single Redis + Sentinel (или Redis Cluster) достаточно. Redlock нужен только при жёстких требованиях к консистентности и недопустимости потери lock при сбое одной ноды. Martin Kleppmann ([разбор Redlock](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)) указывал, что даже Redlock не даёт 100% гарантии при паузах сборки мусора (GC).

- **"Redis Lock заменяет PostgreSQL транзакции"** — разные инструменты. Если операция атомарна внутри одной PostgreSQL транзакции — используйте `FOR UPDATE` или сериализацию транзакций. Redis Lock нужен для координации между сервисами или когда lock нужен до начала транзакции.

- **"TTL lock можно выбирать произвольно"** — TTL должен быть больше максимального ожидаемого времени критической секции + буфер. Слишком маленький TTL → lock истечёт пока процесс работает → другой захватит lock → race condition. Слишком большой → при сбое процесса ресурс заблокирован надолго. Typical: 2-10x ожидаемого времени операции.
