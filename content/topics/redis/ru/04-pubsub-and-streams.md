<!-- verified: 2026-06-05, corrections: 0 -->
# Redis Pub/Sub и Streams

## Pub/Sub — fire-and-forget messaging

Redis Pub/Sub: publisher публикует в channel, все активные subscribers получают копию. Ephemeral — нет хранения, нет истории. Если subscriber отключён в момент публикации — сообщение теряется.

```typescript
import { createClient } from 'redis';

// Publisher
const publisher = createClient({ url: process.env.REDIS_URL });
await publisher.connect();

await publisher.publish('notifications', JSON.stringify({
  type: 'ORDER_CREATED',
  userId: 'user-123',
  orderId: 'order-456',
}));

// Subscriber (отдельное соединение — подписка блокирует соединение для команд)
const subscriber = createClient({ url: process.env.REDIS_URL });
await subscriber.connect();

// Pattern subscribe (glob patterns)
await subscriber.pSubscribe('notifications*', (message, channel) => {
  const event = JSON.parse(message);
  console.log(`Event on ${channel}:`, event);
});

// Subscribe на конкретный канал
await subscriber.subscribe('notifications', (message) => {
  const event = JSON.parse(message);
  handleNotification(event);
});

// Важно: subscriber connection нельзя использовать для SET/GET
// Нужно создавать отдельные connections: одно для subscribe, одно для publish/commands
```

```txt
Pub/Sub: когда подходит и когда нет

Подходит:
  ✓ WebSocket broadcasting: сервер А → Redis Pub/Sub → сервер B → client
  ✓ Live dashboard updates (потеря одного обновления некритична)
  ✓ Cache invalidation между несколькими инстансами сервиса
  ✓ Real-time notifications (дублирование если offline → OK)

НЕ подходит:
  ✗ Критичные бизнес-события (order, payment) — потеря недопустима
  ✗ Background jobs — нужна retry logic
  ✗ Несколько независимых consumers — каждый получает всё (не load balancing)
  ✗ Replay событий — истории нет
```

## Redis Streams — persistent append-only log

Streams (Redis 5+) — аналог Kafka light: append-only log с уникальными ID, consumer groups, acknowledgement. Сообщения хранятся до явного удаления или trim.

```typescript
// XADD — добавить запись в stream
// ID format: <milliseconds>-<sequence> или * для auto-generation
const messageId = await redis.xAdd('orders', '*', {
  event: 'ORDER_CREATED',
  userId: 'user-123',
  orderId: 'order-456',
  amount: '99.99',
  timestamp: Date.now().toString(),
});
// → '1700000000000-0' (auto-generated ID)

// XLEN — размер stream
const len = await redis.xLen('orders');

// XRANGE — читать диапазон
const messages = await redis.xRange('orders', '-', '+'); // все сообщения
const recent = await redis.xRange('orders', '1700000000000-0', '+'); // с определённого ID

// XREAD — читать новые сообщения (polling)
const newMessages = await redis.xRead([
  { key: 'orders', id: '$' }, // $ = только новые (с момента подключения)
], { COUNT: 10, BLOCK: 5000 }); // BLOCK: ждать до 5 сек если нет сообщений

// XTRIM — ограничить размер stream
await redis.xTrim('orders', 'MAXLEN', '~', 10000); // ~ = approximate (быстрее)
```

## Consumer Groups — надёжная параллельная обработка

```typescript
// Consumer Group: несколько workers делят поток (каждое сообщение → один worker)
// + Acknowledgement: сообщение pending пока не XACK

// Создать группу ($ = начать с новых сообщений, 0 = с начала)
try {
  await redis.xGroupCreate('orders', 'order-processors', '$', { MKSTREAM: true });
} catch (err) {
  if (!err.message.includes('BUSYGROUP')) throw err; // группа уже существует
}

// Worker читает сообщения из группы
async function processOrderWorker(workerId: string) {
  while (true) {
    // XREADGROUP: читать до 10 сообщений для этого worker
    const messages = await redis.xReadGroup(
      'order-processors',
      workerId,           // consumer ID внутри группы
      [{ key: 'orders', id: '>' }], // > = новые непрочитанные сообщения
      { COUNT: 10, BLOCK: 5000 }
    );

    if (!messages) continue; // timeout, нет новых сообщений

    for (const { name: stream, messages: msgs } of messages) {
      for (const { id, message } of msgs) {
        try {
          await handleOrderEvent(message);
          // ACK: подтвердить успешную обработку
          await redis.xAck('orders', 'order-processors', id);
        } catch (err) {
          console.error(`Failed to process message ${id}:`, err);
          // Не делаем XACK → сообщение остаётся pending → retry возможен
        }
      }
    }
  }
}

// Проверить pending сообщения (не подтверждённые)
const pending = await redis.xPending('orders', 'order-processors', '-', '+', 10);
// Если сообщение pending слишком долго → возможно worker упал → XCLAIM для другого worker

// XCLAIM: переназначить pending сообщение другому worker
const claimed = await redis.xClaim('orders', 'order-processors', 'worker-2', 30000, [messageId]);
// 30000ms = idle время, после которого можно XCLAIM
```

## Pub/Sub vs Streams vs List (Queue) — матрица выбора

```txt
                    Pub/Sub         List (Queue)      Streams
Хранение:           Нет             Да (в памяти)     Да (persistent)
Delivery:           At-most-once    At-least-once*     At-least-once
Multiple consumers: Fan-out         Point-to-point     Groups (sharding) + Fan-out
ACK:                Нет             Нет (RPOP=delete)  Да (XACK)
History/Replay:     Нет             Нет               Да
Ordering:           Per channel     FIFO              Да (по ID)
Backpressure:       Нет             BLPOP blocks      BLOCK option

*List: BLPOP получает и удаляет атомарно, но нет ACK → если worker упал после RPOP

Pub/Sub: real-time broadcasting, cache invalidation, WebSocket relay
List:    simple job queue (с BullMQ поверх него)
Streams: reliable event log, event sourcing, audit trail

Streams vs Kafka:
  Streams: Redis в инфраструктуре уже есть → zero extra cost, low throughput (~100k/сек)
  Kafka:   dedicated streaming, миллионы событий/сек, retention дни/недели, экосистема
```

## Практический пример: WebSocket + Pub/Sub для scaling

```typescript
// Проблема: 2 инстанса NestJS, клиент подключён к инстансу A
// Событие происходит на инстансе B → клиент не получит его
// Решение: Redis Pub/Sub как message bus между инстансами

// На инстансе B (когда событие происходит):
await redis.publish(`user:${userId}:events`, JSON.stringify({
  type: 'NEW_MESSAGE',
  chatId,
  message: { id, text, timestamp },
}));

// На каждом инстансе (при старте):
await subscriber.subscribe(`user:${userId}:events`, (message) => {
  const event = JSON.parse(message);
  // Найти WebSocket соединение этого пользователя на ЭТОМ инстансе
  const socket = socketManager.getSocket(userId);
  if (socket) socket.emit('event', event);
});

// Масштабирование: Socket.IO имеет официальный Redis adapter для этого паттерна
// @socket.io/redis-adapter использует именно Pub/Sub под капотом
```

## Типичные ошибки на интервью

- **"Redis Pub/Sub — надёжный message broker как RabbitMQ"** — Pub/Sub ephemeral: нет хранения, нет retry, нет acknowledgement. Subscriber offline → сообщение потеряно навсегда. Для надёжной доставки: Redis Streams с Consumer Groups или SQS/RabbitMQ.

- **"Subscriber соединение можно использовать для других команд"** — нет. После `SUBSCRIBE`/`PSUBSCRIBE` соединение переходит в subscribe mode: допустимы только `SUBSCRIBE`, `UNSUBSCRIBE`, `PSUBSCRIBE`, `PUNSUBSCRIBE`, `PING`, `QUIT`. Для других команд нужно отдельное соединение.

- **"Redis Streams = полноценная замена Kafka"** — нет. Streams: in-memory (с опциональной persistence), throughput ~100k-500k/сек, retention ограничен памятью. Kafka: disk-based, миллионы событий/сек, retention дни/недели/бессрочно, встроенное partitioning, богатая экосистема (Kafka Connect, Kafka Streams). Streams — Kafka light для небольших нагрузок.

- **"XACK не нужен если обработка прошла успешно"** — без XACK сообщение вечно остаётся в pending list. При переполнении pending list → утечка памяти. Всегда делать XACK после успешной обработки, и иметь логику для retry/claim pending сообщений.

- **"Consumer Groups делают то же что и несколько SUBSCRIBE"** — разница: несколько `SUBSCRIBE` на канал — каждый получает все сообщения (fan-out). Consumer Group — каждое сообщение получает ровно один consumer (load balancing). Для параллельной обработки без дублирования → Consumer Groups.
