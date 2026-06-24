# Kafka в Node.js — практическое руководство (kafkajs)

## Установка и подключение

**kafkajs** — наиболее зрелый Kafka-клиент для Node.js с поддержкой TypeScript из коробки.

```bash
npm install kafkajs
```

Объект `Kafka` — точка входа, из которой создаются продюсеры и консьюмеры. Его создают один раз и переиспользуют:

```ts
// kafka/client.ts
import { Kafka, logLevel } from 'kafkajs';

export const kafka = new Kafka({
  clientId: 'order-service',       // идентификатор приложения — виден в логах брокера
  brokers: ['localhost:9092'],      // список брокеров; в prod — несколько адресов
  logLevel: logLevel.WARN,
});
```

`clientId` — это не аутентификация, а метка для наблюдаемости: она отображается в метриках брокера и помогает понять, какой сервис вызывает проблемы.

В продакшне указывают несколько брокеров — клиент использует их для discovery кластера (подключиться к любому одному достаточно, чтобы узнать об остальных):

```ts
brokers: [
  'kafka-1.internal:9092',
  'kafka-2.internal:9092',
  'kafka-3.internal:9092',
],
```

## Продюсер: отправка сообщений

### Базовая инициализация

```ts
// kafka/producer.ts
import { kafka } from './client';

const producer = kafka.producer();

export async function startProducer() {
  await producer.connect();
  console.log('Producer connected');
}

export async function stopProducer() {
  await producer.disconnect();
}
```

`producer.connect()` устанавливает TCP-соединение с брокерами. Вызывать при старте сервиса один раз — создавать продюсер на каждый запрос дорого.

### Отправка без ключа (round-robin)

```ts
await producer.send({
  topic: 'user-events',
  messages: [
    { value: JSON.stringify({ type: 'PAGE_VIEW', path: '/home', userId: null }) },
    { value: JSON.stringify({ type: 'PAGE_VIEW', path: '/about', userId: null }) },
  ],
});
```

Подходит для событий, где порядок между ними не важен: логи, аналитика кликов, метрики.

### Отправка с ключом (гарантия порядка)

```ts
// kafka/order-producer.ts
import { kafka } from './client';

const producer = kafka.producer();

export async function publishOrderEvent(
  orderId: string,
  event: { type: string; payload: Record<string, unknown> },
) {
  await producer.send({
    topic: 'order-events',
    messages: [
      {
        key: orderId,          // все события одного заказа → один партишн
        value: JSON.stringify({
          ...event,
          occurredAt: new Date().toISOString(),
        }),
        headers: {
          'content-type': 'application/json',
          'schema-version': '1',
        },
      },
    ],
  });
}

// Использование:
await publishOrderEvent('order-101', { type: 'ORDER_PLACED', payload: { amount: 1500 } });
await publishOrderEvent('order-101', { type: 'PAYMENT_COMPLETED', payload: { method: 'card' } });
await publishOrderEvent('order-101', { type: 'ORDER_SHIPPED', payload: { trackingId: 'TRK-99' } });
```

### Батчинг: отправка нескольких сообщений за раз

Один вызов `send` может содержать массив сообщений. Kafka отправляет их как один батч — это эффективнее, чем N отдельных вызовов:

```ts
const events = orders.map((order) => ({
  key: order.id,
  value: JSON.stringify({ type: 'ORDER_PLACED', payload: order }),
}));

await producer.send({ topic: 'order-events', messages: events });
```

### Настройки надёжности продюсера

```ts
const producer = kafka.producer({
  // acks — сколько брокеров должны подтвердить запись:
  // 0 = fire-and-forget (быстро, но можно потерять сообщения)
  // 1 = leader подтвердил (по умолчанию)
  // -1 / 'all' = leader + все in-sync replicas подтвердили (максимальная надёжность)
});

await producer.send({
  topic: 'order-events',
  acks: -1,   // переопределить на уровне отдельного send
  messages: [{ key: 'order-101', value: '...' }],
});
```

`acks: -1` в связке с `idempotent: true` (настройка брокера) даёт exactly-once семантику на стороне записи. Подробнее — в статье о гарантиях доставки.

## Консьюмер: чтение сообщений

### Базовая инициализация

```ts
// kafka/consumer.ts
import { kafka } from './client';

const consumer = kafka.consumer({
  groupId: 'order-processor',   // имя consumer group — ключевой параметр
});

export async function startConsumer() {
  await consumer.connect();
  await consumer.subscribe({ topics: ['order-events'], fromBeginning: false });
  // fromBeginning: true  → читать с самого начала лога (replay)
  // fromBeginning: false → читать только новые сообщения (по умолчанию)
}

export async function stopConsumer() {
  await consumer.disconnect();
}
```

`fromBeginning` применяется только если для данной `groupId` ещё нет сохранённого offset'а. Если группа уже читала топик — Kafka возобновит с сохранённого offset'а независимо от этой настройки.

### Обработка сообщений — базовый паттерн

```ts
await consumer.run({
  eachMessage: async ({ topic, partition, message }) => {
    const key = message.key?.toString();
    const value = message.value?.toString();

    if (!value) return;

    const event = JSON.parse(value) as { type: string; payload: unknown };

    console.log({
      topic,
      partition,
      offset: message.offset,   // строка! не число
      key,
      event,
    });

    await handleOrderEvent(event);
    // offset автоматически коммитится после возврата этой функции
    // (поведение по умолчанию при autoCommit: true)
  },
});
```

Обратите внимание: `message.offset` — это **строка**, не число. Так устроен kafkajs. При сравнении или арифметике нужно конвертировать: `Number(message.offset)`.

## Auto Commit vs Manual Commit — самый важный trade-off

Это ключевой вопрос для понимания гарантий доставки. Разберём оба режима с их последствиями.

### Auto Commit (по умолчанию)

```ts
const consumer = kafka.consumer({
  groupId: 'order-processor',
});

await consumer.run({
  autoCommit: true,                          // значение по умолчанию
  autoCommitInterval: 5000,                  // коммитить каждые 5 секунд
  autoCommitThreshold: 100,                  // или каждые 100 сообщений
  eachMessage: async ({ message }) => {
    await handleOrderEvent(JSON.parse(message.value!.toString()));
  },
});
```

**Как работает**: kafkajs периодически (по таймеру или по числу сообщений) коммитит текущий offset автоматически, независимо от результата обработки.

```txt
Auto Commit — сценарий потери сообщения:

t=0s   Consumer получил msg[offset=10]
t=1s   Consumer получил msg[offset=11]
t=2s   Consumer получил msg[offset=12]
t=3s   Consumer получил msg[offset=13]
t=4s   Consumer получил msg[offset=14]
t=5s   AUTO COMMIT → offset=14 сохранён в Kafka
t=6s   Consumer получил msg[offset=15]
t=6.5s Consumer УПАЛ в середине обработки offset=15

→ Consumer перезапускается, читает с offset=15 ✓ (не потеряно)

Но другой сценарий:
t=0s   Consumer получил msg[offset=10..14]
t=5s   AUTO COMMIT → offset=14 сохранён
t=5.5s Consumer получил msg[offset=15]
t=5.8s AUTO COMMIT → offset=15 сохранён (коммит ДО завершения обработки!)
t=6s   Consumer упал в середине обработки offset=15

→ Consumer перезапускается, читает с offset=16 ✗ (offset=15 потерян!)
```

Auto commit дает **at-most-once** семантику: сообщение может быть потеряно, если коммит произошёл до завершения обработки. Подходит для некритичных данных (аналитика, метрики), где небольшая потеря допустима.

### Manual Commit — at-least-once семантика

```ts
const consumer = kafka.consumer({ groupId: 'order-processor' });

await consumer.run({
  autoCommit: false,   // отключаем автокоммит
  eachMessage: async ({ topic, partition, message }) => {
    const event = JSON.parse(message.value!.toString());

    try {
      await handleOrderEvent(event);

      // Коммитим ПОСЛЕ успешной обработки
      await consumer.commitOffsets([{
        topic,
        partition,
        offset: (Number(message.offset) + 1).toString(),
        // +1: offset означает "следующее сообщение для чтения"
      }]);
    } catch (err) {
      // Не коммитим — сообщение будет перечитано после перезапуска
      console.error('Failed to process message, will retry:', err);
      throw err; // kafkajs остановит обработку
    }
  },
});
```

```txt
Manual Commit — at-least-once:

t=0s   Consumer получил msg[offset=15]
t=1s   handleOrderEvent() успешно завершилась
t=1s   commitOffsets([offset=16]) → offset сохранён
t=2s   Consumer получил msg[offset=16]
t=2.5s Consumer УПАЛ во время handleOrderEvent()

→ Перезапуск: читает с offset=16 (15 уже закоммичен, 16 — нет)
→ offset=16 будет обработан повторно ✓ (at-least-once)
→ Потери нет, но возможна двойная обработка
```

**Почему offset + 1?** В Kafka "закоммитить offset X" означает "я прочитал X-1, следующее сообщение для меня — X". То есть коммитят не последний обработанный offset, а следующий за ним.

### eachBatch — ручной коммит для батчей

```ts
await consumer.run({
  autoCommit: false,
  eachBatch: async ({ batch, resolveOffset, heartbeat, commitOffsetsIfNecessary }) => {
    for (const message of batch.messages) {
      const event = JSON.parse(message.value!.toString());
      await handleOrderEvent(event);

      resolveOffset(message.offset);    // помечаем offset как обработанный
      await heartbeat();                 // не даём брокеру считать consumer'а мёртвым
                                         // при долгой обработке батча
    }

    await commitOffsetsIfNecessary();   // коммитим все resolveOffset'd offset'ы
  },
});
```

`eachBatch` даёт больше контроля: можно коммитить по частям, вызывать `heartbeat()` во время долгой обработки (важно, если обработка батча занимает больше `session.timeout.ms`).

## Конфигурация Consumer Group

```ts
const consumer = kafka.consumer({
  groupId: 'order-processor',

  sessionTimeout: 30000,          // мс: если нет heartbeat — consumer мёртв (default: 30000)
  heartbeatInterval: 3000,        // мс: как часто слать heartbeat (default: 3000)
  maxBytesPerPartition: 1048576,  // байт: макс размер данных за один fetch из одного партишна (1MB)
  minBytes: 1,                    // ждать минимум 1 байт перед ответом брокера
  maxBytes: 10485760,             // общий лимит на fetch (10MB)
  maxWaitTimeInMs: 5000,          // ждать до 5 сек если данных меньше minBytes
  retry: {
    initialRetryTime: 100,        // начальная пауза перед retry (мс)
    retries: 8,                   // количество попыток
  },
});
```

Критически важный параметр — `sessionTimeout`. Если обработка одного сообщения (или батча) занимает больше `sessionTimeout` без вызова `heartbeat()` — брокер считает consumer'а мёртвым и инициирует rebalancing. В `eachBatch` вызывайте `heartbeat()` внутри цикла.

## Consumer Lag — как отслеживать отставание

**Consumer lag (лаг консьюмера)** — это разница между последним offset'ом в партишне (конец лога) и текущим offset'ом группы. Lag = 0 означает, что consumer успевает в реальном времени.

```txt
Topic "order-events", Partition 0:
  Последний offset в партишне: 1050 (записано продюсером)
  Текущий offset группы:        980 (до сюда обработано)
  
  Consumer Lag = 1050 - 980 = 70 сообщений
```

Высокий и растущий lag — сигнал, что consumer не справляется с нагрузкой.

### Мониторинг lag из кода

```ts
// kafka/lag-monitor.ts
import { kafka } from './client';

const admin = kafka.admin();

export async function getConsumerLag(
  groupId: string,
  topic: string,
): Promise<{ partition: number; lag: number }[]> {
  await admin.connect();

  const [offsets, groupOffsets] = await Promise.all([
    admin.fetchTopicOffsets(topic),
    admin.fetchOffsets({ groupId, topics: [topic] }),
  ]);

  const groupTopic = groupOffsets.find((t) => t.topic === topic);
  if (!groupTopic) return [];

  const result = offsets.map(({ partition, offset: latestOffset }) => {
    const groupPartition = groupTopic.partitions.find((p) => p.partition === partition);
    const committedOffset = Number(groupPartition?.offset ?? '0');
    const latest = Number(latestOffset);
    return { partition, lag: Math.max(0, latest - committedOffset) };
  });

  await admin.disconnect();
  return result;
}

// Использование:
const lag = await getConsumerLag('order-processor', 'order-events');
console.log(lag);
// [{ partition: 0, lag: 12 }, { partition: 1, lag: 0 }, { partition: 2, lag: 45 }]
```

В продакшне lag обычно мониторится через Prometheus + kafkajs встроенные метрики или внешние инструменты: Kafka UI, Redpanda Console, Burrow, Datadog.

### Встроенные метрики kafkajs

```ts
const { CONNECT, DISCONNECT, REQUEST_TIMEOUT } = consumer.events;

consumer.on(consumer.events.FETCH, (event) => {
  // Вызывается после каждого poll — содержит число полученных сообщений
  console.log(`Fetched ${event.payload.numberOfBatches} batches`);
});

consumer.on(consumer.events.COMMIT_OFFSETS, (event) => {
  // Отслеживание коммитов
  console.log('Offsets committed:', event.payload.offsetsCommitted);
});
```

## Полный пример: сервис обработки заказов

```ts
// services/order-consumer.service.ts
import { kafka } from '../kafka/client';
import { OrderRepository } from '../repositories/order.repository';
import { NotificationService } from './notification.service';

type OrderEvent =
  | { type: 'ORDER_PLACED'; payload: { orderId: string; userId: string; amount: number } }
  | { type: 'PAYMENT_COMPLETED'; payload: { orderId: string; method: string } }
  | { type: 'ORDER_SHIPPED'; payload: { orderId: string; trackingId: string } };

const consumer = kafka.consumer({ groupId: 'order-processor' });

async function handleEvent(event: OrderEvent): Promise<void> {
  switch (event.type) {
    case 'ORDER_PLACED':
      await OrderRepository.create(event.payload);
      await NotificationService.sendOrderConfirmation(event.payload.userId);
      break;
    case 'PAYMENT_COMPLETED':
      await OrderRepository.markPaid(event.payload.orderId);
      break;
    case 'ORDER_SHIPPED':
      await OrderRepository.updateTracking(event.payload.orderId, event.payload.trackingId);
      await NotificationService.sendShippingNotification(event.payload.orderId);
      break;
    default:
      // неизвестный тип — логируем, не падаем
      console.warn('Unknown event type:', (event as { type: string }).type);
  }
}

export async function startOrderConsumer(): Promise<void> {
  await consumer.connect();
  await consumer.subscribe({ topics: ['order-events'], fromBeginning: false });

  await consumer.run({
    autoCommit: false,
    eachMessage: async ({ topic, partition, message }) => {
      const raw = message.value?.toString();
      if (!raw) return;

      let event: OrderEvent;
      try {
        event = JSON.parse(raw) as OrderEvent;
      } catch {
        // невалидный JSON — логируем и пропускаем (poison message)
        console.error('Invalid JSON in message, skipping:', { topic, partition, offset: message.offset });
        await consumer.commitOffsets([{
          topic,
          partition,
          offset: (Number(message.offset) + 1).toString(),
        }]);
        return;
      }

      await handleEvent(event);

      await consumer.commitOffsets([{
        topic,
        partition,
        offset: (Number(message.offset) + 1).toString(),
      }]);
    },
  });
}

export async function stopOrderConsumer(): Promise<void> {
  await consumer.disconnect();
}
```

## Graceful Shutdown

Без graceful shutdown consumer не успевает закоммитить последний offset и следующий запуск перечитает уже обработанные сообщения:

```ts
// main.ts
import { startOrderConsumer, stopOrderConsumer } from './services/order-consumer.service';

async function main() {
  await startOrderConsumer();
  console.log('Order consumer started');

  const shutdown = async (signal: string) => {
    console.log(`Received ${signal}, shutting down gracefully...`);
    await stopOrderConsumer();   // disconnect коммитит pending offset'ы
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));  // Kubernetes pod stop
  process.on('SIGINT', () => shutdown('SIGINT'));    // Ctrl+C
}

main().catch(console.error);
```

## Типичные ошибки на интервью

**"Auto commit — это то же самое, что at-least-once"**

Нет. Auto commit по умолчанию даёт **at-most-once**: если коммит произошёл до завершения обработки, и consumer упал — сообщение потеряно. At-least-once требует ручного коммита ПОСЛЕ успешной обработки.

**"Manual commit предотвращает дублирование"**

Нет. Manual commit даёт at-least-once — при сбое после обработки и ДО коммита сообщение будет перечитано. Дублирование возможно. Для exactly-once нужна идемпотентная обработка на стороне consumer'а (например, `ON CONFLICT DO NOTHING` в PostgreSQL) или транзакции Kafka (сложнее).

**"commitOffsets([{ offset: message.offset }]) — правильный синтаксис"**

Почти. Нужно offset + 1: `{ offset: (Number(message.offset) + 1).toString() }`. Коммит offset'а X означает "следующее сообщение для чтения — X", то есть X-1 уже обработан. Частая ошибка — коммитить текущий offset, из-за чего одно сообщение всегда перечитывается.

**"Можно создавать нового продюсера / consumer на каждый HTTP-запрос"**

Нет. `connect()` устанавливает TCP-соединение с брокерами — дорогая операция. Продюсер и consumer создаются один раз при старте сервиса и переиспользуются.

**"fromBeginning: true всегда читает с начала"**

Нет. `fromBeginning` применяется только если для данной `groupId` нет сохранённого offset'а (новая группа или топик). Если offset уже есть — Kafka продолжит с него, игнорируя `fromBeginning`. Для принудительного replay нужно сбросить offset через Admin API.
