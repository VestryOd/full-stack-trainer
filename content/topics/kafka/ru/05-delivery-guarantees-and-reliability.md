# Гарантии доставки и надёжность

## Три семантики доставки — что они означают точно

В Kafka (и в распределённых системах в целом) говорят о трёх уровнях гарантий доставки. Важно понимать, что каждая из них описывает не только продюсера или только consumer'а, а **весь путь сообщения**: запись → хранение → чтение → обработка.

### At-Most-Once (не более одного раза)

Сообщение будет обработано **ноль или один раз**. Дублирования нет, но возможна потеря.

```txt
Producer                Broker              Consumer
   │                       │                    │
   │── send(msg) ─────────►│                    │
   │◄─ ack ───────────────│                    │
   │                       │── deliver(msg) ───►│
   │                       │                    │── обработка...
   │                       │                    │   CRASH 💥
   │                       │                    │
   │                       │                    │── restart
   │                       │                    │   читает с offset ПОСЛЕ msg
   │                       │                    │   → msg потеряна безвозвратно
```

Когда возникает в Kafka:
- **Producer**: `acks: 0` — не ждёт подтверждения от брокера
- **Consumer**: `autoCommit: true` + коммит произошёл ДО завершения обработки
- Consumer прочитал сообщение, сдвинул offset, затем упал — сообщение не обработано, offset уже сохранён

Когда уместно: метрики, аналитика кликов, логи с высоким объёмом — где небольшая потеря данных допустима, а задержка от retry неприемлема.

### At-Least-Once (не менее одного раза)

Сообщение будет обработано **один или более раз**. Потери нет, но возможны дубликаты.

```txt
Producer                Broker              Consumer
   │                       │                    │
   │── send(msg) ─────────►│                    │
   │                       │── deliver(msg) ───►│
   │                       │                    │── обработка успешна ✓
   │                       │                    │── commit(offset) → CRASH 💥
   │                       │                    │
   │                       │                    │── restart
   │                       │                    │   читает с ТОГО ЖЕ offset
   │                       │                    │── обработка снова ✓ (дубликат!)
```

Когда возникает в Kafka:
- **Producer**: `acks: 1` или `acks: -1` без idempotent — при retry продюсер может записать дубликат
- **Consumer**: `autoCommit: false` + ручной коммит после обработки — при сбое до коммита, сообщение перечитывается

Когда уместно: большинство реальных систем работают на at-least-once, компенсируя дубликаты идемпотентностью на стороне consumer'а (см. ниже).

### Exactly-Once (ровно один раз)

Сообщение будет обработано **ровно один раз** — без потерь и без дубликатов.

```txt
Теоретически:
  Producer ──► Broker ──► Consumer
  Гарантия: каждое сообщение записано и обработано ровно один раз

  В реальности: два механизма в связке:
  1. Idempotent Producer + Transactions (на стороне записи)
  2. Idempotent Consumer (на стороне чтения)
```

Exactly-once — самый сложный и дорогостоящий режим. Kafka реализует его через два механизма.

## Idempotent Producer — exactly-once запись

**Idempotent producer (идемпотентный продюсер)** — это продюсер, который может безопасно выполнять retry записи без создания дубликатов.

**Проблема без idempotent producer**:

```txt
t=0  Producer отправляет msg[seq=5]
t=1  Брокер записал msg[seq=5], отправляет ACK
t=2  ACK потерян в сети (network blip)
t=3  Producer timeout → retry → отправляет msg[seq=5] снова
t=4  Брокер записывает msg[seq=5] ВТОРОЙ РАЗ → дубликат в логе
```

**Решение — idempotent producer**:

Kafka присваивает каждому продюсеру уникальный **Producer ID (PID)**. Каждое сообщение получает монотонно возрастающий **sequence number** в рамках PID + partition. Брокер отслеживает последний sequence number от каждого PID и **отбрасывает дубликаты**:

```txt
t=0  Producer (PID=42) отправляет msg[seq=5]
t=1  Брокер записал msg[PID=42, seq=5], отправляет ACK
t=2  ACK потерян
t=3  Producer retry → отправляет msg[PID=42, seq=5] снова
t=4  Брокер видит PID=42, seq=5 — уже записано → отбрасывает, отправляет ACK
     → дубликата нет
```

В kafkajs:

```ts
const producer = kafka.producer({
  idempotent: true,   // включает idempotent producer
  // автоматически устанавливает:
  // acks: -1 (все ISR должны подтвердить)
  // maxInFlightRequests: 5 (не больше 5 неподтверждённых запросов)
  // retries: Number.MAX_SAFE_INTEGER (бесконечные retry)
});
```

**Что даёт idempotent producer**: exactly-once запись **в один партишн одного топика**. Дубликаты при retry устранены.

**Что НЕ даёт**: не защищает от дубликатов при обработке consumer'ом — это только половина пути.

## Kafka Transactions — exactly-once между топиками

Idempotent producer устраняет дубликаты в рамках одной операции записи. Но что если нужно атомарно записать в несколько топиков, или атомарно обработать сообщение + записать результат?

**Kafka Transactions** позволяют атомарно:
- Прочитать из топика A
- Обработать данные
- Записать результат в топик B
- Закоммитить offset (пометить как обработано)

Всё или ничего — если что-то пошло не так, транзакция откатывается.

```txt
Kafka Transactions — концептуально:

  beginTransaction()
    ├── consume(topic: "orders", offset=10)     ← читаем заказ
    ├── produce(topic: "payments", msg=payReq)  ← создаём запрос на оплату
    └── commitTransaction()                      ← атомарно фиксируем всё

  Если crash между produce и commit:
    → транзакция откатывается
    → offset НЕ коммитится
    → consumer перечитает orders[offset=10]
    → payments не получит частичный результат
```

В kafkajs:

```ts
const producer = kafka.producer({
  idempotent: true,
  transactionalId: 'order-payment-processor',  // уникальный ID для транзакций
});

const transaction = await producer.transaction();
try {
  // Записать в топик результатов
  await transaction.send({
    topic: 'payment-requests',
    messages: [{ key: orderId, value: JSON.stringify(paymentRequest) }],
  });

  // Атомарно закоммитить offset из входного топика
  await transaction.sendOffsets({
    consumerGroupId: 'order-processor',
    topics: [{
      topic: 'order-events',
      partitions: [{ partition, offset: (Number(offset) + 1).toString() }],
    }],
  });

  await transaction.commit();
} catch (err) {
  await transaction.abort();
  throw err;
}
```

**Честная оговорка**: Kafka Transactions работают на уровне Kafka → Kafka. Если результат записывается в базу данных или внешний сервис, гарантия exactly-once уже не держится — база данных не участвует в Kafka-транзакции. В большинстве реальных систем вместо транзакций используют идемпотентных consumer'ов.

## Idempotent Consumer — практическое решение

**Idempotent consumer (идемпотентный consumer)** — consumer, который при повторной обработке одного и того же сообщения даёт тот же результат, что и при первой.

Это самый распространённый подход в реальных системах, потому что:
1. Не требует Kafka Transactions (сложная настройка)
2. Работает, даже если результат пишется в базу данных или вызывает внешний API
3. Справляется с at-least-once семантикой без дублирования эффектов

```ts
// Пример идемпотентной обработки через PostgreSQL
async function handleOrderPlaced(event: { orderId: string; userId: string; amount: number }) {
  // INSERT OR IGNORE — если orderId уже есть, ничего не делаем
  await db.query(`
    INSERT INTO orders (id, user_id, amount, status, created_at)
    VALUES ($1, $2, $3, 'pending', NOW())
    ON CONFLICT (id) DO NOTHING
  `, [event.orderId, event.userId, event.amount]);
  // Повторный вызов с тем же orderId → нет ошибки, нет дубликата
}
```

```ts
// Идемпотентность через версионирование (optimistic locking)
async function handlePaymentCompleted(event: { orderId: string; version: number }) {
  const updated = await db.query(`
    UPDATE orders
    SET status = 'paid', version = $2
    WHERE id = $1 AND version = $2 - 1
  `, [event.orderId, event.version]);

  if (updated.rowCount === 0) {
    // Либо уже обновлено (дубликат), либо конфликт версии
    // В обоих случаях — безопасно игнорировать
    return;
  }
}
```

```ts
// Идемпотентность через таблицу processed_events
async function processMessageIdempotently(
  messageId: string,
  handler: () => Promise<void>,
) {
  const alreadyProcessed = await db.query(
    'INSERT INTO processed_events (id) VALUES ($1) ON CONFLICT DO NOTHING RETURNING id',
    [messageId],
  );

  if (alreadyProcessed.rowCount === 0) {
    return; // уже обработано
  }

  await handler();
}

// Использование:
const messageId = `${topic}-${partition}-${offset}`;
await processMessageIdempotently(messageId, () => handleOrderEvent(event));
```

## Poison Message — как Kafka обрабатывает "ядовитые" сообщения

**Poison message (ядовитое сообщение)** — сообщение, которое consumer не может успешно обработать. Например: невалидный JSON, несовместимая схема, вызывает exception в бизнес-логике, зависит от недоступного сервиса.

**Проблема специфична для Kafka**: в отличие от RabbitMQ, Kafka не убирает сообщение из партишна. Если consumer падает при обработке и не коммитит offset — он снова получит то же сообщение после перезапуска. Бесконечный цикл.

```txt
Без обработки poison message:

  offset=42: [невалидное сообщение]

  Попытка 1: consumer получает offset=42 → exception → перезапуск
  Попытка 2: consumer получает offset=42 → exception → перезапуск
  ...
  Попытка N: то же самое

  → Consumer завис на offset=42. Весь партишн заморожен.
    Lag растёт. Новые сообщения не обрабатываются.
```

### Паттерн: Dead Letter Topic (DLT)

**Dead Letter Topic** — отдельный топик, куда отправляются сообщения, которые не удалось обработать после N попыток. После отправки в DLT offset коммитится, и основная обработка продолжается.

```txt
Нормальный путь:
  [order-events] ──► Consumer ──► обработка ──► commit offset

Путь для poison message:
  [order-events] ──► Consumer ──► 3 попытки → провал
                                  │
                                  ▼
                         [order-events.DLT] ──► отдельный consumer
                                  │              (алертинг, ручной разбор,
                         commit offset          повторная обработка)
```

```ts
// kafka/dead-letter-topic.ts
import { kafka } from './client';

const dlProducer = kafka.producer();
await dlProducer.connect();

export async function sendToDeadLetterTopic(
  originalTopic: string,
  message: { key: Buffer | null; value: Buffer | null; headers?: Record<string, Buffer> },
  error: Error,
  metadata: { partition: number; offset: string },
): Promise<void> {
  await dlProducer.send({
    topic: `${originalTopic}.DLT`,
    messages: [{
      key: message.key,
      value: message.value,
      headers: {
        ...message.headers,
        'dlt-original-topic': Buffer.from(originalTopic),
        'dlt-original-partition': Buffer.from(String(metadata.partition)),
        'dlt-original-offset': Buffer.from(metadata.offset),
        'dlt-error-message': Buffer.from(error.message),
        'dlt-error-type': Buffer.from(error.constructor.name),
        'dlt-failed-at': Buffer.from(new Date().toISOString()),
      },
    }],
  });
}
```

```ts
// Интеграция DLT в consumer с retry
const MAX_RETRIES = 3;

await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      try {
        const event = JSON.parse(message.value!.toString());
        await handleOrderEvent(event);

        await consumer.commitOffsets([{
          topic,
          partition,
          offset: (Number(message.offset) + 1).toString(),
        }]);
        return; // успешно — выходим
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        console.warn(`Attempt ${attempt}/${MAX_RETRIES} failed:`, lastError.message);

        if (attempt < MAX_RETRIES) {
          // Экспоненциальная задержка перед retry
          await new Promise((resolve) => setTimeout(resolve, 100 * 2 ** attempt));
        }
      }
    }

    // Все попытки исчерпаны — отправляем в DLT
    console.error('Sending message to DLT after all retries failed');
    await sendToDeadLetterTopic(topic, message, lastError!, { partition, offset: message.offset });

    // Коммитим offset — чтобы не застрять на этом сообщении навсегда
    await consumer.commitOffsets([{
      topic,
      partition,
      offset: (Number(message.offset) + 1).toString(),
    }]);
  },
});
```

### Consumer DLT — мониторинг и ручной разбор

```ts
// Отдельный consumer для DLT — для алертинга и анализа
const dltConsumer = kafka.consumer({ groupId: 'order-events-dlt-monitor' });

await dltConsumer.connect();
await dltConsumer.subscribe({ topics: ['order-events.DLT'], fromBeginning: true });

await dltConsumer.run({
  eachMessage: async ({ message }) => {
    const originalTopic = message.headers?.['dlt-original-topic']?.toString();
    const errorMessage = message.headers?.['dlt-error-message']?.toString();
    const failedAt = message.headers?.['dlt-failed-at']?.toString();

    // Отправить алерт в Slack/PagerDuty
    await alerting.send({
      severity: 'high',
      title: `Poison message in ${originalTopic}`,
      message: `Error: ${errorMessage} at ${failedAt}`,
      payload: message.value?.toString(),
    });
  },
});
```

## Итоговая таблица: когда какая семантика

```txt
┌──────────────────┬───────────────┬──────────────┬──────────────────────────────┐
│ Семантика        │ Потеря данных │ Дубликаты    │ Как достичь в Kafka          │
├──────────────────┼───────────────┼──────────────┼──────────────────────────────┤
│ At-most-once     │ Возможна      │ Нет          │ acks:0 или auto-commit       │
│                  │               │              │ до обработки                 │
├──────────────────┼───────────────┼──────────────┼──────────────────────────────┤
│ At-least-once    │ Нет           │ Возможны     │ acks:-1 + manual commit      │
│                  │               │              │ после обработки (стандарт)   │
├──────────────────┼───────────────┼──────────────┼──────────────────────────────┤
│ Exactly-once     │ Нет           │ Нет          │ Idempotent producer +        │
│                  │               │              │ Kafka Transactions (Kafka→   │
│                  │               │              │ Kafka), ИЛИ at-least-once +  │
│                  │               │              │ idempotent consumer          │
└──────────────────┴───────────────┴──────────────┴──────────────────────────────┘
```

## Типичные ошибки на интервью

**"Exactly-once — это просто включить флаг в Kafka"**

Нет. Exactly-once в Kafka — это комбинация: idempotent producer (`idempotent: true`) + транзакции (для Kafka→Kafka сценариев). Но это покрывает только запись в Kafka. Если consumer пишет результат в базу данных или вызывает внешний API — база не участвует в транзакции, и exactly-once уже не гарантирована. Большинство команд выбирают at-least-once + idempotent consumer, а не Kafka Transactions.

**"At-least-once — это неприемлемо для продакшна"**

Нет. At-least-once — стандарт в большинстве продакшн-систем. При правильно реализованном idempotent consumer'е (ON CONFLICT DO NOTHING, версионирование, таблица processed_events) дубликаты не создают проблем. Kafka Transactions добавляют сложность, которая оправдана только в конкретных сценариях (обработка финансовых транзакций, стриминговая обработка Kafka Streams).

**"Poison message просто вызовет исключение, и Kafka сама разберётся"**

Нет. Kafka не имеет встроенного механизма dead-letter на уровне брокера (в отличие от RabbitMQ). Без явной обработки consumer застрянет на одном сообщении навсегда. Паттерн DLT — ответственность разработчика, не брокера.

**"Retry с экспоненциальной задержкой решает проблему poison message"**

Частично. Retry помогает при временных сбоях (сеть, недоступный сервис). Но если сообщение содержит невалидные данные — никакое количество retry не исправит ситуацию. DLT нужен именно для таких случаев: обнаружить, изолировать, разобраться вручную, не блокируя поток.

**"Idempotent producer устраняет все дубликаты"**

Нет. Idempotent producer устраняет дубликаты на уровне записи в одну partition при retry. Он не защищает от дубликатов при обработке consumer'ом (consumer прочитал, обработал, упал до коммита → перечитает снова). Идемпотентность consumer'а — отдельная задача.
