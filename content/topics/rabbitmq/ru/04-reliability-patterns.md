# Паттерны надёжности

## Гарантии доставки — что на самом деле означают термины

Три термина всплывают на каждом интервью по очередям сообщений. Их часто перечисляют как список, не понимая, что каждый из них требует от вашего кода.

### At-most-once (не более одного раза)

Брокер доставляет сообщение один раз, а может и вовсе не доставить. Если потребитель упал до обработки — сообщение потеряно навсегда.

```txt
Producer ──► Broker ──► Consumer
                         ↓
                    (падает до обработки)
                         ↓
                    Сообщение потеряно навсегда
```

В RabbitMQ это происходит при использовании `noAck: true`. Брокер удаляет сообщение из очереди в момент доставки — до того, как потребитель что-либо с ним сделал.

**Когда приемлемо:** Fire-and-forget телеметрия, метрики, доставка логов — там, где потеря 0.1% событий предпочтительнее сложности гарантированной доставки.

### At-least-once (хотя бы один раз)

Брокер доставляет сообщение и ждёт ack. Если потребитель упал или сделал nack — сообщение доставляется повторно. Потребитель может обработать одно и то же сообщение более одного раза.

```txt
Producer ──► Broker ──► Consumer (успешно обработал) ──► ack ──► Broker удаляет
Producer ──► Broker ──► Consumer (падает в процессе обработки)
                              ↓
                    Broker повторно доставляет другому потребителю
                         (сообщение обработано дважды)
```

Именно это RabbitMQ и гарантирует при `noAck: false` (по умолчанию) и `nack` с `requeue: true` при ошибке. **Это та гарантия, которую вы реально получаете** — и это означает, что потребители должны уметь обрабатывать дубликаты.

### Exactly-once (ровно один раз)

Каждое сообщение обрабатывается ровно один раз — даже при сбоях и сетевых проблемах. Звучит идеально, но в распределённых системах это крайне сложно реализовать — требуется координация между брокером, потребителем и хранилищем.

```txt
Настоящий exactly-once требует:
  - Брокер: дедупликация сообщений при приёме
  - Потребитель: обработка атомарна с ack
  - Хранилище: записи идемпотентны или транзакционны с ack
```

**RabbitMQ не предоставляет exactly-once "из коробки".** Kafka transactions + EOS (Exactly-Once Semantics) приближают к этому, но даже тогда exactly-once достигается на уровне приложения через идемпотентных потребителей — а не как гарантия самого брокера.

**Практический вывод:** Проектируйте системы под at-least-once и делайте потребителей идемпотентными. Это даёт безопасность exactly-once без его сложности.

## Идемпотентные потребители — практический путь к надёжности

**Идемпотентный** потребитель даёт одинаковый результат независимо от того, обработал он сообщение один раз или десять. Это стандартный ответ на проблему at-least-once доставки.

### Идемпотентность через уникальный messageId

```ts
import { type Channel, type ConsumeMessage } from 'amqplib';
import { redis } from './redis';
import { db } from './db';

async function processOrderPlaced(
  channel: Channel,
  msg: ConsumeMessage,
): Promise<void> {
  const messageId = msg.properties.messageId;
  const event = JSON.parse(msg.content.toString());

  if (!messageId) {
    // Нечего дедуплицировать — обрабатываем как есть или отправляем в DLQ
    channel.nack(msg, false, false);
    return;
  }

  // Проверяем, не обрабатывали ли мы уже это сообщение
  const alreadyProcessed = await redis.set(
    `processed:${messageId}`,
    '1',
    'NX',         // установить только если Not eXists
    'EX', 86400,  // TTL 24 часа
  );

  if (alreadyProcessed === null) {
    // Redis вернул null → ключ уже существует → дубликат
    console.log(`Дубликат сообщения ${messageId}, пропускаем`);
    channel.ack(msg); // ack, чтобы убрать из очереди
    return;
  }

  // Первый раз видим это сообщение — обрабатываем
  try {
    await db.orders.updateStatus(event.orderId, 'confirmed');
    await emailService.sendConfirmation(event.customerEmail, event.orderId);
    channel.ack(msg);
  } catch (err) {
    // Обработка не удалась — удаляем ключ Redis, чтобы можно было повторить
    await redis.del(`processed:${messageId}`);
    channel.nack(msg, false, false); // в DLQ после исчерпания попыток
  }
}
```

### Идемпотентность через upsert-семантику в БД

Для операций записи в базу данных проектируйте саму запись как идемпотентную:

```ts
// ❌ Не идемпотентно — при двойном запуске создаст две строки или увеличит дважды
await db.query(
  'INSERT INTO notifications (order_id, sent_at) VALUES ($1, NOW())',
  [orderId],
);

// ✅ Идемпотентно — ON CONFLICT делает операцию no-op при повторной обработке
await db.query(
  `INSERT INTO notifications (order_id, message_id, sent_at)
   VALUES ($1, $2, NOW())
   ON CONFLICT (message_id) DO NOTHING`,
  [orderId, messageId],
);

// ✅ Тоже идемпотентно — UPDATE с условием-стражем
await db.query(
  `UPDATE orders SET status = 'confirmed'
   WHERE id = $1 AND status = 'pending'`,
  [orderId],
);
```

Уникальный constraint в базе становится механизмом дедупликации — Redis не нужен.

## Повторные попытки с экспоненциальным backoff

`nack` с `requeue: true` повторяет мгновенно — сообщение возвращается в начало очереди и потребитель получает его снова через миллисекунды. При временных ошибках (downstream-сервис временно недоступен, сетевой сбой) нужно ждать перед повтором.

В RabbitMQ нет встроенной задержки повторов, но это реализуется через паттерн **delayed queue** с TTL + DLQ:

```txt
Основная очередь ──(ошибка)──► Retry Exchange ──► Retry Queue (TTL: 30с)
                                                          │
                                                  (TTL истекает)
                                                          │
                                                          ▼
                                          Dead Letter → Main Exchange → Main Queue
```

```ts
async function setupRetryTopology(channel: Channel): Promise<void> {
  // Основной exchange и очередь
  await channel.assertExchange('orders', 'topic', { durable: true });
  await channel.assertQueue('order-processing', {
    durable: true,
    arguments: {
      'x-dead-letter-exchange': 'orders.retry',  // при nack → retry exchange
    },
  });
  await channel.bindQueue('order-processing', 'orders', 'order.placed');

  // Retry exchange и очередь — сообщения ждут 30с, затем возвращаются
  await channel.assertExchange('orders.retry', 'direct', { durable: true });
  await channel.assertQueue('order-processing.retry', {
    durable: true,
    arguments: {
      'x-message-ttl': 30_000,                    // ждать 30с
      'x-dead-letter-exchange': 'orders',          // затем вернуться на основной exchange
      'x-dead-letter-routing-key': 'order.placed', // с исходным routing key
    },
  });
  await channel.bindQueue('order-processing.retry', 'orders.retry', 'order.placed');

  // Финальный DLQ — после исчерпания всех попыток
  await channel.assertExchange('orders.dlx', 'direct', { durable: true });
  await channel.assertQueue('orders.dead-letters', { durable: true });
  await channel.bindQueue('orders.dead-letters', 'orders.dlx', 'order.placed');
}
```

```ts
const MAX_RETRIES = 3;

async function processWithRetry(channel: Channel, msg: ConsumeMessage): Promise<void> {
  const retryCount = getRetryCount(msg); // читает x-death[0].count из заголовков

  try {
    await processOrder(JSON.parse(msg.content.toString()));
    channel.ack(msg);
  } catch (err) {
    if (retryCount >= MAX_RETRIES) {
      // Попытки исчерпаны — отправить в финальный DLQ
      await republishToDLQ(channel, msg);
      channel.ack(msg); // ack оригинала, чтобы retry queue не отправил его в DLQ снова
    } else {
      // nack без requeue → идёт на retry exchange (через x-dead-letter-exchange)
      // → ждёт 30с в retry queue → возвращается в основную очередь
      channel.nack(msg, false, false);
    }
  }
}

function getRetryCount(msg: ConsumeMessage): number {
  const deaths = msg.properties.headers['x-death'] as Array<{ count: number }> | undefined;
  return deaths?.[0]?.count ?? 0;
}

async function republishToDLQ(channel: Channel, msg: ConsumeMessage): Promise<void> {
  channel.publish(
    'orders.dlx',
    'order.placed',
    msg.content,
    { ...msg.properties, headers: { ...msg.properties.headers, 'x-final-failure': true } },
  );
}
```

### Экспоненциальный backoff через несколько retry-очередей

Для более гранулярного контроля — несколько очередей с нарастающими TTL:

```ts
const RETRY_DELAYS_MS = [5_000, 30_000, 300_000]; // 5с, 30с, 5 минут

async function setupExponentialRetry(channel: Channel): Promise<void> {
  for (let attempt = 0; attempt < RETRY_DELAYS_MS.length; attempt++) {
    await channel.assertQueue(`order-processing.retry.${attempt}`, {
      durable: true,
      arguments: {
        'x-message-ttl': RETRY_DELAYS_MS[attempt],
        'x-dead-letter-exchange': 'orders',
        'x-dead-letter-routing-key': 'order.placed',
      },
    });
  }
}

// В потребителе: маршрутизируем в нужную retry-очередь по номеру попытки
function getRetryQueueName(retryCount: number): string {
  const idx = Math.min(retryCount, RETRY_DELAYS_MS.length - 1);
  return `order-processing.retry.${idx}`;
}
```

## Publisher confirms — уверенность, что брокер получил сообщение

По умолчанию `channel.publish()` — это fire-and-forget на уровне TCP: брокер мог не получить сообщение, если соединение оборвалось до того, как буфер сбросился. **Publisher confirms** (режим подтверждений) заставляют канал ждать явного ack от брокера для каждого опубликованного сообщения.

```ts
async function publishWithConfirm(
  channel: Channel,
  exchange: string,
  routingKey: string,
  payload: Buffer,
): Promise<void> {
  // Включаем confirm mode — нужно сделать до любых публикаций на этом канале
  await channel.confirmSelect();

  const confirmed = await new Promise<boolean>((resolve) => {
    channel.publish(exchange, routingKey, payload, { persistent: true });

    // waitForConfirms резолвится, когда брокер подтвердит все pending-сообщения
    channel.waitForConfirms()
      .then(() => resolve(true))
      .catch(() => resolve(false));
  });

  if (!confirmed) {
    throw new Error(`Брокер отклонил сообщение в ${exchange}/${routingKey}`);
  }
}
```

Канал в confirm mode имеет накладные расходы (на каждое сообщение — round trip для ack). При высокой нагрузке используйте пакетные подтверждения: публикуем N сообщений, затем один `waitForConfirms()`.

```ts
// Пакетная публикация с подтверждением
async function batchPublishWithConfirm(
  channel: Channel,
  messages: Array<{ exchange: string; routingKey: string; payload: Buffer }>,
): Promise<void> {
  await channel.confirmSelect();

  for (const { exchange, routingKey, payload } of messages) {
    channel.publish(exchange, routingKey, payload, { persistent: true });
  }

  // Одно ожидание подтверждения на весь пакет
  await channel.waitForConfirms();
}
```

## Паттерн Transactional Outbox

Самый распространённый пробел в надёжности event-driven систем: вы сохраняете данные в БД и публикуете сообщение двумя отдельными операциями. Если процесс упал между ними — либо запись в БД есть без сообщения, либо сообщение опубликовано без записи.

```ts
// ❌ Классическое race condition — эти две операции НЕ атомарны
async function placeOrder(orderData: OrderData): Promise<void> {
  await db.orders.create(orderData);               // ← что если упасть здесь?
  await rabbitmq.publish('order.placed', orderData); // ← или здесь?
}
```

**Transactional Outbox** (транзакционный журнал исходящих) решает это: сообщение записывается в таблицу `outbox` в той же транзакции БД, что и бизнес-данные. Отдельный relay-процесс читает outbox и публикует в RabbitMQ.

```sql
-- Миграция: создаём outbox-таблицу
CREATE TABLE outbox (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type    TEXT NOT NULL,
  payload       JSONB NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  published_at  TIMESTAMPTZ  -- NULL = ещё не опубликовано
);
```

```ts
// Шаг 1: атомарная запись — бизнес-данные + запись в outbox в одной транзакции
async function placeOrder(orderData: OrderData): Promise<void> {
  await db.transaction(async (trx) => {
    const order = await trx.orders.create(orderData);

    // Записываем событие в outbox — та же транзакция, что и создание заказа
    await trx.query(
      `INSERT INTO outbox (event_type, payload) VALUES ($1, $2)`,
      ['order.placed', JSON.stringify({ orderId: order.id, ...orderData })],
    );
  });
  // Если любая запись падает — вся транзакция откатывается, осиротевших событий нет
}
```

```ts
// Шаг 2: relay-процесс — читает outbox и публикует в RabbitMQ
async function relayOutboxMessages(
  db: DatabaseClient,
  channel: Channel,
): Promise<void> {
  await channel.confirmSelect();

  // SELECT FOR UPDATE SKIP LOCKED предотвращает обработку одной строки двумя relay-инстансами
  const pending = await db.query<OutboxRow>(
    `SELECT * FROM outbox
     WHERE published_at IS NULL
     ORDER BY created_at
     LIMIT 100
     FOR UPDATE SKIP LOCKED`,
  );

  for (const row of pending.rows) {
    channel.publish(
      'orders',
      row.event_type,
      Buffer.from(row.payload),
      { persistent: true, messageId: row.id },
    );
  }

  await channel.waitForConfirms();

  // Помечаем как опубликованные только после подтверждения от брокера
  const ids = pending.rows.map((r) => r.id);
  await db.query(
    `UPDATE outbox SET published_at = NOW() WHERE id = ANY($1)`,
    [ids],
  );
}

// Запускаем relay по интервалу
setInterval(() => relayOutboxMessages(db, channel), 1000);
```

Паттерн Outbox даёт **exactly-once публикацию** (at-least-once к брокеру, но `message_id` на стороне потребителя обрабатывает дедупликацию) без распределённых транзакций.

## Poison messages — обнаружение и обработка

**Poison message** (отравленное сообщение) — сообщение, которое вызывает краш потребителя при каждой попытке обработки: сломанный payload, неожиданная версия схемы, баг, проявляющийся на конкретных данных. Без защиты потребитель входит в бесконечный цикл краш-передоставка.

Детекция: заголовки `x-death` накапливаются при каждой повторной доставке. Когда `count` превышает порог — сообщение ядовито.

```ts
async function safeConsume(channel: Channel, msg: ConsumeMessage): Promise<void> {
  const deathCount = getDeathCount(msg);

  if (deathCount >= MAX_RETRIES) {
    // Сообщение повторялось слишком много раз — помещаем в карантин
    await quarantineMessage(msg);
    channel.ack(msg); // убираем из очереди без повторной постановки в очередь
    return;
  }

  try {
    await processMessage(msg);
    channel.ack(msg);
  } catch (err) {
    const isPoison = isPoisonError(err); // например: ошибка парсинга JSON, валидация схемы

    if (isPoison) {
      // Не повторяем структурно сломанное сообщение — сразу в карантин
      await quarantineMessage(msg);
      channel.ack(msg);
    } else {
      channel.nack(msg, false, false); // → retry queue
    }
  }
}

async function quarantineMessage(msg: ConsumeMessage): Promise<void> {
  // Сохраняем в БД для ручной проверки
  await db.query(
    `INSERT INTO quarantined_messages (message_id, queue, payload, headers, quarantined_at)
     VALUES ($1, $2, $3, $4, NOW())`,
    [
      msg.properties.messageId,
      msg.fields.routingKey,
      msg.content.toString(),
      JSON.stringify(msg.properties.headers),
    ],
  );

  // Уведомляем команду
  await alerting.send(`Poison message в карантине: ${msg.properties.messageId}`);
}
```

## Типичные ошибки на интервью

- **"RabbitMQ обеспечивает exactly-once доставку"** — нет. RabbitMQ даёт at-most-once (с `noAck`) или at-least-once (с ack и nack/requeue). Exactly-once — задача уровня приложения, решаемая через идемпотентных потребителей.

- **"Могу сделать потребителя идемпотентным, просто проверив `if processed then skip` перед работой"** — проверка и работа — это две отдельные операции. Если потребитель упал между проверкой и работой, при следующей доставке проверка пройдёт и работа будет пропущена. Проверка должна быть атомарна с записью (уникальный constraint в БД, Redis SET NX + удаление при ошибке).

- **"`nack` с `requeue: true` — это безопасный механизм повторов"** — он повторяет мгновенно, без задержки, бесконечно. При перманентной ошибке (сломанный payload, отсутствующая зависимость) это создаёт плотный цикл, который может насытить и потребителя, и брокера. Всегда используйте задержку и максимальное число попыток.

- **"Transactional Outbox переусложнён — достаточно try/catch вокруг публикации"** — try/catch не поможет, если процесс упал после записи в БД и до запуска публикации. Outbox — единственный способ гарантировать атомарность записи в БД и публикации сообщения без распределённых транзакций.

- **"Publisher confirms означают, что потребитель обработал сообщение"** — нет. Publisher confirms означают, что **брокер** получил и сохранил сообщение. Обработал ли потребитель — это совершенно отдельная история (для этого нужны consumer acks).

- **"Отравленные сообщения в конце концов обработаются, если повторять достаточно много раз"** — если сообщение каждый раз вызывает краш, больше повторов не помогут. Повторы предназначены для временных сбоев; отравленное сообщение имеет перманентную причину отказа (обычно баг или несовпадение схемы). Обнаружьте его рано, поместите в карантин и устраните корневую причину.
