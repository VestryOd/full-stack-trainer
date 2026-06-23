# RabbitMQ в Node.js

## Установка amqplib

`amqplib` — стандартный Node.js-клиент для AMQP 0-9-1. Библиотека предоставляет два API: на колбэках (`amqplib/callbacks`) и на Promise (`amqplib`). Всегда используйте Promise-based API с `async/await`.

```bash
npm install amqplib
npm install --save-dev @types/amqplib
```

В продакшне необходимо обрабатывать переподключение и ошибки — наивный вызов одного `connect()` уронит процесс при обрыве сети:

```ts
import amqplib, { type Connection, type Channel } from 'amqplib';

interface RabbitMQClient {
  connection: Connection;
  channel: Channel;
}

async function createRabbitMQClient(url: string): Promise<RabbitMQClient> {
  const connection = await amqplib.connect(url);
  const channel = await connection.createChannel();

  // Без этих обработчиков ошибки "тихо" убивают процесс
  connection.on('error', (err) => console.error('RabbitMQ connection error:', err));
  connection.on('close', () => console.warn('RabbitMQ connection closed'));

  return { connection, channel };
}
```

В продакшн-приложениях (NestJS, Express-сервисы) это оборачивается в singleton-сервис с логикой переподключения. Библиотека `amqp-connection-manager` обрабатывает переподключение автоматически — разберём это в статье 04.

## Объявление топологии: assertExchange, assertQueue, bindQueue

Перед публикацией или потреблением нужно объявить топологию (exchange, очереди, привязки). Ключевой метод — `assert*`: создаёт ресурс, если не существует, или проверяет совпадение настроек, если существует. Неправильные настройки на существующей очереди приводят к ошибке на уровне канала.

```ts
async function setupTopology(channel: Channel): Promise<void> {
  // Объявляем exchange
  await channel.assertExchange('orders', 'topic', {
    durable: true,      // переживает перезапуск
    autoDelete: false,  // не удалять, когда нет привязанных очередей
  });

  // Объявляем очередь
  await channel.assertQueue('order-email-notifications', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.dlx',  // куда идут "мёртвые" сообщения
      'x-message-ttl': 300_000,                // TTL 5 минут
    },
  });

  // Привязка: маршрутизируем 'order.*' события в эту очередь
  await channel.bindQueue('order-email-notifications', 'orders', 'order.*');
}
```

Ключевой нюанс: и сервис-продюсер, и сервис-потребитель должны вызывать `assertExchange` и `assertQueue`. Вызовы идемпотентны — если топология уже существует с идентичными настройками, вызов ничего не делает. Так любой сервис может стартовать первым без ошибок.

## Публикация сообщений

```ts
interface OrderPlacedEvent {
  orderId: string;
  customerEmail: string;
  items: Array<{ sku: string; quantity: number; price: number }>;
  totalAmount: number;
  createdAt: string;
}

function publishOrderPlaced(channel: Channel, event: OrderPlacedEvent): boolean {
  const payload = Buffer.from(JSON.stringify(event));

  return channel.publish(
    'orders',           // exchange
    'order.placed',     // routing key
    payload,
    {
      persistent: true,                    // записать на диск — переживает перезапуск
      contentType: 'application/json',     // конвенция, RabbitMQ не проверяет
      messageId: crypto.randomUUID(),      // полезно для дедупликации
      timestamp: Math.floor(Date.now() / 1000),
      headers: {
        'x-service': 'order-service',     // произвольные заголовки для трассировки
      },
    },
  );
  // Возвращает false, если внутренний буфер записи заполнен (сигнал backpressure)
  // При false: прекратить публикацию до события 'drain' на канале
}
```

`channel.publish()` возвращает `false`, когда внутренний буфер записи канала заполнен. Это сигнал backpressure от RabbitMQ — если его игнорировать и продолжать публиковать, память иссякнет. Правильная реакция:

```ts
async function publishWithBackpressure(
  channel: Channel,
  exchange: string,
  routingKey: string,
  payload: Buffer,
  options: amqplib.Options.Publish,
): Promise<void> {
  const canSend = channel.publish(exchange, routingKey, payload, options);

  if (!canSend) {
    // Ждём, пока канал освободит буфер
    await new Promise<void>((resolve) => channel.once('drain', resolve));
  }
}
```

## Потребление сообщений и подтверждения

Здесь сосредоточена большая часть сложности. Потребитель подписывается на очередь и получает сообщения через колбэк. Критическое решение после обработки каждого сообщения: **подтвердить** (сообщить RabbitMQ "готово, удаляй") или **отклонить** (сообщить "не удалось, что делать дальше?").

```ts
async function startEmailConsumer(channel: Channel): Promise<void> {
  // Устанавливаем prefetch ДО начала потребления — критично для производительности
  await channel.prefetch(10); // максимум 10 неподтверждённых сообщений одновременно

  await channel.consume('order-email-notifications', async (msg) => {
    if (msg === null) {
      // null означает, что потребитель отменён (например, очередь удалена)
      console.warn('Consumer cancelled by broker');
      return;
    }

    const event = JSON.parse(msg.content.toString()) as OrderPlacedEvent;

    try {
      await emailService.sendOrderConfirmation(event.customerEmail, event.orderId);

      // ✅ Успех: удалить из очереди
      channel.ack(msg);
    } catch (err) {
      console.error('Failed to send email:', err);

      const isRetryable = isTransientError(err);
      const retryCount = (msg.properties.headers['x-retry-count'] as number) ?? 0;

      if (isRetryable && retryCount < 3) {
        // ❌ Отклонить и вернуть в очередь — RabbitMQ доставит повторно
        // ПРЕДУПРЕЖДЕНИЕ: без задержки это создаёт плотный цикл повторов
        channel.nack(msg, false, true);  // (msg, multiple, requeue)
      } else {
        // ❌ Отклонить без возврата — пойдёт в dead-letter queue (если настроена)
        channel.nack(msg, false, false);
      }
    }
  }, {
    noAck: false,  // НИКОГДА не ставьте true в продакшне — потеряете сообщения при краше
  });
}
```

### Три метода подтверждения

```ts
// ACK — успех, удалить сообщение из очереди
channel.ack(msg);
channel.ack(msg, true);  // allUpTo: true — подтвердить ЭТО и все ранее доставленные

// NACK — ошибка, с выбором дальнейшей судьбы
channel.nack(msg, false, true);   // requeue: true  — вернуть в эту очередь
channel.nack(msg, false, false);  // requeue: false — отбросить или в dead-letter

// REJECT — то же что nack, но только для одного сообщения (нет allUpTo)
channel.reject(msg, true);   // вернуть в очередь
channel.reject(msg, false);  // в dead-letter или отбросить
```

`nack` с `requeue: true` опасен без задержки — сообщение немедленно возвращается в начало очереди и доставляется снова, потенциально тысячи раз в секунду. Правильный паттерн повторных попыток с backoff разбирается в статье 04.

### Режим noAck — когда это уместно

```ts
// noAck: true — RabbitMQ удаляет сообщение в момент доставки
// Потребитель никогда не отправляет ack
channel.consume('analytics-events', (msg) => {
  if (msg) analyticsService.record(msg.content.toString());
}, { noAck: true });
```

`noAck: true` имеет смысл **только** там, где потеря сообщений приемлема — для fire-and-forget аналитики, метрик или логирования, где пропускная способность важнее гарантий доставки. Никогда не используйте для бизнес-критичных операций.

## Prefetch count — важнейший параметр настройки

Без prefetch RabbitMQ доставляет все сообщения из очереди потребителю так быстро, как может. Если в очереди 50 000 сообщений, а потребитель обрабатывает медленно, все 50 000 окажутся в памяти потребителя — вы фактически переместили очередь из управляемого хранилища RabbitMQ в heap вашего приложения.

```ts
// Без prefetch: брокер отправляет ВСЕ сообщения сразу
// С prefetch: брокер держит сообщения, пока потребитель не подтвердит и не освободит слот
await channel.prefetch(10);

// Prefetch на потребителя vs на канал
await channel.prefetch(10);          // на потребителя (по умолчанию)
await channel.prefetch(100, true);   // на канал (суммарно по всем потребителям канала)
```

Как выбрать значение:

```txt
Prefetch = 1:
  ✓ Абсолютно честное распределение — каждый потребитель обрабатывает одно сообщение за раз
  ✗ Высокая задержка: потребитель должен ack перед получением следующего сообщения
  ✗ Низкая пропускная способность: нет конвейерного параллелизма
  Подходит для: тяжёлых, медленных задач, где нужна строгая упорядоченность на потребителя

Prefetch = 10–50:
  ✓ Хороший баланс для большинства нагрузок
  ✓ Допускает конвейерный параллелизм внутри потребителя
  ✓ Всё ещё ограничивает потребление памяти
  Подходит для: типичной фоновой обработки задач

Prefetch = 100+:
  ✓ Высокая пропускная способность при быстрой обработке
  ✗ Больше сообщений буферизовано в памяти потребителя
  ✗ При краше потребителя требуется повторная доставка большего числа сообщений
  Подходит для: быстрых, лёгких по I/O потребителей
```

## Dead Letter Queues (DLQ, очереди мёртвых писем)

**DLQ** — это место, куда попадают сообщения, которые невозможно обработать. Сообщение становится "мёртвым" в трёх случаях:
1. Оно отклонено с `requeue: false` (`nack` или `reject`)
2. Истёк его TTL (time-to-live) до обработки потребителем
3. Очередь достигла лимита `x-max-length`, и сообщение вытесняется

```ts
async function setupWithDeadLetter(channel: Channel): Promise<void> {
  // 1. Объявляем dead letter exchange (DLX)
  await channel.assertExchange('orders.dlx', 'direct', { durable: true });

  // 2. Объявляем dead letter queue (DLQ)
  await channel.assertQueue('orders.dead-letters', { durable: true });

  // 3. Привязываем DLQ к DLX
  await channel.bindQueue('orders.dead-letters', 'orders.dlx', 'order-emails');

  // 4. Объявляем основную очередь с настроенным DLX
  await channel.assertQueue('order-email-notifications', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.dlx',       // куда идут dead letters
      'x-dead-letter-routing-key': 'order-emails',   // routing key в DLX
      'x-message-ttl': 300_000,                      // TTL 5 минут
    },
  });
}
```

Когда сообщение попадает в DLQ, RabbitMQ автоматически добавляет заголовки:

```ts
// В потребителе DLQ эти заголовки объясняют, ПОЧЕМУ сообщение умерло
channel.consume('orders.dead-letters', (msg) => {
  if (!msg) return;

  const deathInfo = msg.properties.headers['x-death'] as Array<{
    queue: string;
    reason: 'rejected' | 'expired' | 'maxlen';
    count: number;
    time: Date;
    exchange: string;
    'routing-keys': string[];
  }>;

  console.error('Dead letter received:', {
    reason: deathInfo[0].reason,
    originalQueue: deathInfo[0].queue,
    retryCount: deathInfo[0].count,
    payload: msg.content.toString(),
  });

  // Типичные стратегии для DLQ:
  // 1. Алерт + ручная проверка
  // 2. Сохранить в БД для анализа
  // 3. Повторить с экспоненциальным backoff (перепубликовать в исходную очередь с задержкой)
  channel.ack(msg);
});
```

## Полный пример: продюсер + потребитель

Объединим всё вышесказанное в паттерн, который используется в реальных Node.js-микросервисах:

```ts
// rabbitmq.ts — общая настройка
import amqplib, { type Channel, type Connection } from 'amqplib';

const RABBITMQ_URL = process.env.RABBITMQ_URL ?? 'amqp://localhost';

let connection: Connection | null = null;
let publisherChannel: Channel | null = null;

export async function getPublisherChannel(): Promise<Channel> {
  if (!connection) {
    connection = await amqplib.connect(RABBITMQ_URL);
  }
  if (!publisherChannel) {
    publisherChannel = await connection.createChannel();
  }
  return publisherChannel;
}

export async function setupTopology(channel: Channel): Promise<void> {
  await channel.assertExchange('orders', 'topic', { durable: true });
  await channel.assertExchange('orders.dlx', 'direct', { durable: true });

  await channel.assertQueue('orders.dead-letters', { durable: true });
  await channel.bindQueue('orders.dead-letters', 'orders.dlx', 'order-emails');

  await channel.assertQueue('order-email-notifications', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.dlx',
      'x-dead-letter-routing-key': 'order-emails',
    },
  });
  await channel.bindQueue('order-email-notifications', 'orders', 'order.placed');
}
```

```ts
// order-service/producer.ts
import { getPublisherChannel, setupTopology } from './rabbitmq';

export async function publishOrderPlaced(orderId: string, email: string): Promise<void> {
  const channel = await getPublisherChannel();
  await setupTopology(channel);

  const event = { orderId, customerEmail: email, createdAt: new Date().toISOString() };

  channel.publish(
    'orders',
    'order.placed',
    Buffer.from(JSON.stringify(event)),
    { persistent: true, messageId: crypto.randomUUID() },
  );
}
```

```ts
// email-service/consumer.ts
import amqplib from 'amqplib';
import { setupTopology } from './rabbitmq';

async function startConsumer(): Promise<void> {
  const connection = await amqplib.connect(process.env.RABBITMQ_URL ?? 'amqp://localhost');
  const channel = await connection.createChannel();

  await setupTopology(channel);
  await channel.prefetch(5);

  console.log('Email consumer started');

  await channel.consume('order-email-notifications', async (msg) => {
    if (!msg) return;

    try {
      const event = JSON.parse(msg.content.toString());
      await sendEmail(event.customerEmail, `Заказ ${event.orderId} подтверждён`);
      channel.ack(msg);
    } catch (err) {
      // Неустранимая ошибка: отправить в dead-letter
      channel.nack(msg, false, false);
    }
  });
}

startConsumer().catch(console.error);
```

## Graceful shutdown (корректное завершение)

Потребитель, который завершается без подтверждения сообщений в процессе обработки, вызывает их повторную доставку — это нормально. Но резкое уничтожение соединения в середине обработки может оставить сообщения в неопределённом состоянии. Правильный паттерн:

```ts
async function startWithGracefulShutdown(): Promise<void> {
  const connection = await amqplib.connect('amqp://localhost');
  const channel = await connection.createChannel();
  let isShuttingDown = false;

  const shutdown = async () => {
    if (isShuttingDown) return;
    isShuttingDown = true;

    console.log('Завершаем работу потребителя...');

    // Отменяем потребителя — брокер перестаёт доставлять новые сообщения
    await channel.cancel('my-consumer-tag');

    // Ждём завершения in-flight обработки
    await new Promise((resolve) => setTimeout(resolve, 2000));

    await channel.close();
    await connection.close();
    process.exit(0);
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  await channel.consume('my-queue', async (msg) => {
    if (msg && !isShuttingDown) {
      await processMessage(msg);
      channel.ack(msg);
    }
  }, { consumerTag: 'my-consumer-tag' });
}
```

## Типичные ошибки на интервью

- **"`noAck: true` везде, потому что подтверждения добавляют накладные расходы"** — это безвозвратно теряет сообщения при краше потребителя в середине обработки. Накладные расходы на ack ничтожны по сравнению с реальной работой по обработке. Отключайте ack только для по-настоящему одноразовых данных.

- **"Prefetch не важен, это мелкая оптимизация"** — в продакшне это не опционально. Без prefetch очередь с накопленными сообщениями выгружает всё на первого подключившегося потребителя, перегружая его. Prefetch — это то, что заставляет конкурирующих потребителей честно делить нагрузку.

- **"При ошибке всегда надо делать `nack` с `requeue: true`"** — это создаёт бесконечный цикл повторной доставки, если само сообщение сломано ("отравленное сообщение"). Правильный паттерн: считать попытки в заголовках, делать nack с requeue для устранимых ошибок до определённого лимита, затем отправлять в dead-letter. Никогда не повторять бесконечно.

- **"Можно использовать один канал для публикации в нескольких конкурентных async-операциях"** — каналы в amqplib не потокобезопасны. Конкурентные вызовы `channel.publish()` из нескольких async-операций могут перемежаться, вызывая ошибки протокола. Используйте один канал на async-контекст или сериализуйте доступ.

- **"Dead letter queue — то же самое, что retry queue"** — они служат разным целям. DLQ — конечная точка для сообщений, исчерпавших все попытки обработки; retry queue — временная остановка с задержкой перед повторной доставкой. Некоторые паттерны повторов используют оба (retry queue → после N попыток → DLQ).

- **Не ждать `channel.assertQueue` / `channel.assertExchange`** — эти методы возвращают Promise. Если не `await`, очередь может не существовать к моменту первой публикации, что молча потеряет сообщение (или бросит ошибку, убившую канал).
