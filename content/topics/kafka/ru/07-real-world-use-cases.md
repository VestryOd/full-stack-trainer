# Kafka в реальных проектах — практические сценарии

## Сценарий 1: Event Streaming — поток событий для нескольких потребителей

Это самый классический Kafka-сценарий и лучший способ объяснить, почему Kafka подходит лучше очереди.

### Архитектура: заказы в e-commerce

Пользователь размещает заказ. Этот факт интересен четырём независимым системам:

```txt
                        ┌─────────────────────────────────────────┐
                        │         Kafka Cluster                    │
                        │                                          │
[Order Service] ───────►│  Topic: "order-events"                  │
  (Producer)            │  Partitions: 12 (key = orderId)         │
                        │  Retention: 30 days                      │
                        └──────────────┬──────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼                  ▼
  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │ Inventory Group  │  │ Notification     │  │ Analytics Group  │  │ Fraud Detection  │
  │                  │  │ Group            │  │                  │  │ Group            │
  │ Резервирует      │  │ Отправляет email │  │ Обновляет        │  │ Проверяет паттерн│
  │ товар на складе  │  │ и push-уведомл.  │  │ дашборды продаж  │  │ покупки          │
  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

**Почему это лучше, чем очередь:**
- Order Service не знает о downstream-системах — он просто публикует факт
- Добавление Fraud Detection Group не требует изменений в Order Service
- Analytics упала на 3 часа → перезапустилась → догнала все пропущенные события
- Можно воспроизвести историю заказов за последние 30 дней для новой ML-модели

### Структура событий

```ts
// types/order-events.ts
type OrderEventType =
  | 'ORDER_PLACED'
  | 'PAYMENT_COMPLETED'
  | 'PAYMENT_FAILED'
  | 'ORDER_CONFIRMED'
  | 'ORDER_SHIPPED'
  | 'ORDER_DELIVERED'
  | 'ORDER_CANCELLED';

interface OrderEvent {
  eventId: string;          // уникальный ID события (для идемпотентности)
  eventType: OrderEventType;
  orderId: string;          // ключ партишна
  userId: string;
  occurredAt: string;       // ISO timestamp
  payload: Record<string, unknown>;
}

// Producer в Order Service
async function publishOrderEvent(event: OrderEvent): Promise<void> {
  await producer.send({
    topic: 'order-events',
    messages: [{
      key: event.orderId,
      value: JSON.stringify(event),
      headers: { 'event-type': Buffer.from(event.eventType) },
    }],
  });
}
```

```ts
// Consumer в Inventory Service
await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    const event = JSON.parse(message.value!.toString()) as OrderEvent;

    // Обрабатываем только нужные типы событий
    if (event.eventType === 'ORDER_CONFIRMED') {
      await inventoryService.reserve({
        orderId: event.orderId,
        items: event.payload.items as OrderItem[],
      });
    }

    await consumer.commitOffsets([{
      topic, partition,
      offset: (Number(message.offset) + 1).toString(),
    }]);
  },
});
```

## Сценарий 2: Event Sourcing — лог как источник правды

**Event Sourcing** — архитектурный паттерн, при котором состояние сущности определяется не текущим снапшотом в таблице БД, а последовательностью событий, которые к нему привели.

```txt
Традиционный подход (state-based):
  orders таблица: { id: "ord-1", status: "shipped", amount: 1500, updatedAt: "..." }
  
  Вопрос: "Почему статус shipped, а не delivered?"
  Ответ: неизвестно — мы храним только текущее состояние.

Event Sourcing подход:
  order-events лог:
    [0] ORDER_PLACED    { orderId: "ord-1", amount: 1500, items: [...] }
    [1] PAYMENT_OK      { orderId: "ord-1", method: "card", txId: "tx-42" }
    [2] ORDER_CONFIRMED { orderId: "ord-1", warehouseId: "wh-3" }
    [3] ORDER_SHIPPED   { orderId: "ord-1", trackingId: "TRK-99", carrier: "FedEx" }
  
  Текущее состояние = применить все события по порядку.
  Полная история всегда доступна.
  Можно "перемотать" до любого момента.
```

Kafka — идеальное хранилище для event sourcing лога: append-only, высокий throughput, долгосрочное хранение, несколько reader'ов.

```ts
// Восстановление состояния заказа из лога событий
async function rebuildOrderState(orderId: string): Promise<Order> {
  // В реальном event sourcing читают из специализированного
  // event store. Здесь показана концепция.
  const events = await getEventsFromLog('order-events', orderId);

  return events.reduce((state, event) => {
    switch (event.eventType) {
      case 'ORDER_PLACED':
        return { ...state, status: 'pending', amount: event.payload.amount };
      case 'PAYMENT_OK':
        return { ...state, status: 'paid' };
      case 'ORDER_SHIPPED':
        return { ...state, status: 'shipped', trackingId: event.payload.trackingId };
      default:
        return state;
    }
  }, {} as Order);
}
```

## Сценарий 3: Log Aggregation — централизованный сбор логов

Каждый микросервис пишет логи в stdout. Как их централизовать, индексировать и анализировать?

```txt
Классический ELK-стек с Kafka:

  ┌────────────┐    ┌────────────┐    ┌────────────┐
  │ Service A  │    │ Service B  │    │ Service C  │
  │ (logs →    │    │ (logs →    │    │ (logs →    │
  │  stdout)   │    │  stdout)   │    │  stdout)   │
  └─────┬──────┘    └─────┬──────┘    └─────┬──────┘
        │                 │                 │
        ▼                 ▼                 ▼
  ┌─────────────────────────────────────────────────┐
  │          Filebeat / Fluentd (log shipper)        │
  │  Читает логи из файлов/stdout, пишет в Kafka     │
  └──────────────────────┬──────────────────────────┘
                         │
                         ▼
               Topic: "application-logs"
               Retention: 3 days
               Partitions: 24 (key = serviceId)
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
  ┌──────────┐   ┌──────────┐   ┌──────────────┐
  │Logstash  │   │Monitoring│   │ S3 Archiver  │
  │→ Elastic │   │(alerts   │   │ (долгосрочное│
  │  search  │   │ на errors│   │  хранение)   │
  └──────────┘   └──────────┘   └──────────────┘
```

**Зачем Kafka в этой цепочке, а не напрямую в Elasticsearch?**

Без Kafka: Filebeat → Elasticsearch напрямую. Проблемы:
- Elasticsearch перегружен при пиках (spike трафика в несколько раз)
- Логи теряются если Elasticsearch недоступен
- Нет возможности повторно обработать логи (например, при изменении индекса)

С Kafka: Kafka выступает как буфер. При перегрузке Elasticsearch — логи накапливаются в Kafka, Logstash берёт их в своём темпе. При падении Elasticsearch — логи не теряются, они в логе Kafka.

## Сценарий 4: Change Data Capture (CDC)

**Change Data Capture (CDC)** — это механизм захвата изменений в базе данных и публикации их как потока событий. Вместо того чтобы опрашивать БД ("что изменилось за последнюю минуту?"), CDC подписывается на бинарный лог репликации самой БД.

```txt
Как CDC работает с PostgreSQL:

  PostgreSQL имеет Write-Ahead Log (WAL) — бинарный журнал всех изменений.
  WAL используется для репликации standby-серверов.
  
  Debezium (популярный CDC-коннектор) читает WAL как обычный replica:
  
  ┌──────────────┐         ┌───────────┐         ┌─────────────────────────┐
  │  PostgreSQL  │──WAL───►│  Debezium │────────►│  Kafka Topic            │
  │              │         │ (Kafka    │         │  "postgres.public.orders"│
  │  INSERT order│         │  Connect) │         │                          │
  │  UPDATE order│         └───────────┘         │  [insert-event]          │
  │  DELETE order│                               │  [update-event]          │
  └──────────────┘                               │  [delete-event]          │
                                                 └─────────────────────────┘
                                                           │
                                   ┌───────────────────────┼───────────────┐
                                   │                       │               │
                                   ▼                       ▼               ▼
                             [Search Index]         [Analytics]      [Audit Log]
                             (Elasticsearch)        (ClickHouse)     (S3)
```

**Структура CDC-события** (формат Debezium):

```ts
interface DebeziumOrderEvent {
  before: OrderRecord | null;  // состояние ДО изменения (null для INSERT)
  after: OrderRecord | null;   // состояние ПОСЛЕ изменения (null для DELETE)
  op: 'c' | 'u' | 'd' | 'r';  // create, update, delete, read (snapshot)
  ts_ms: number;               // timestamp изменения в БД
  source: {
    table: string;
    db: string;
    lsn: number;               // позиция в WAL
  };
}
```

**Зачем CDC вместо прямых событий из кода?**

```txt
Подход 1: события из кода (Outbox Pattern):
  await db.transaction(async (tx) => {
    await tx.orders.create(order);
    await kafka.send('order-created', order);  // проблема: atomicity!
  });
  
  Проблема: транзакция в БД и запись в Kafka не атомарны.
  Если Kafka недоступна — заказ создан, событие не отправлено.

Подход 2: Transactional Outbox:
  await db.transaction(async (tx) => {
    await tx.orders.create(order);
    await tx.outbox.insert({ topic: 'order-created', payload: order });
    // Всё в одной транзакции БД → атомарно
  });
  // Отдельный процесс читает outbox и пишет в Kafka

Подход 3: CDC (Debezium):
  await db.orders.create(order);  // просто пишем в БД
  // Debezium автоматически захватывает изменение из WAL и пишет в Kafka
  // Гарантия: если изменение в БД — оно будет в Kafka (WAL читается как replica)
```

CDC особенно ценен, когда нужно синхронизировать данные между разными хранилищами без изменения кода приложения.

## Сценарий 5: Real-Time Analytics Pipeline

```txt
E-commerce аналитика в реальном времени:

  Источники данных:
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ Order Service│  │ User Service │  │ Product Svc  │  │ Web Frontend │
  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
         │                 │                 │                 │
         ▼                 ▼                 ▼                 ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                     Kafka Topics                                      │
  │  "order-events"  "user-events"  "product-views"  "click-stream"      │
  └──────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
  ┌────────────────────┐  ┌───────────────────┐  ┌────────────────────┐
  │   Kafka Streams /  │  │   ClickHouse /     │  │    Elasticsearch   │
  │   Apache Flink     │  │   Apache Druid     │  │    (поиск,         │
  │   (real-time       │  │   (OLAP-хранилище  │  │     аналитика)     │
  │    агрегация)      │  │    для дашбордов)  │  │                    │
  └────────────────────┘  └───────────────────┘  └────────────────────┘
         │
         │ Агрегированные метрики в реальном времени:
         ├── revenue per minute
         ├── conversion rate (views → purchases)
         ├── top products last 5 minutes
         └── active users right now
```

**Пример простой агрегации с kafkajs:**

```ts
// Подсчёт заказов по статусам за скользящее окно
// (в реальном prod используют Kafka Streams или Flink)
const orderCounts: Record<string, number> = {};

await consumer.run({
  autoCommit: true,
  eachMessage: async ({ message }) => {
    const event = JSON.parse(message.value!.toString()) as OrderEvent;

    if (event.eventType === 'ORDER_PLACED') {
      const minute = event.occurredAt.slice(0, 16); // "2024-01-15T14:32"
      orderCounts[minute] = (orderCounts[minute] ?? 0) + 1;

      // Каждую минуту публикуем агрегат
      await metricsProducer.send({
        topic: 'order-metrics',
        messages: [{
          key: minute,
          value: JSON.stringify({ minute, count: orderCounts[minute] }),
        }],
      });
    }
  },
});
```

## Разобранный пример: полная архитектура заказов

Соберём вместе все сценарии в одну реальную архитектуру.

```txt
                                     KAFKA CLUSTER
                    ┌─────────────────────────────────────────────────────┐
                    │                                                       │
[Order Service] ──►│  "order-events"     (12 partitions, 30d retention)  │
[Payment Svc]   ──►│  "payment-events"   (6 partitions, 30d retention)   │
[User Service]  ──►│  "user-events"      (6 partitions, 7d retention)    │
[CDC/Debezium]  ──►│  "db.public.orders" (12 partitions, 7d retention)   │
[Filebeat]      ──►│  "app-logs"         (24 partitions, 3d retention)   │
                    │                                                       │
                    └──────────────────────┬──────────────────────────────┘
                                           │
        ┌──────────────────────────────────┼──────────────────────────────────┐
        │                                  │                                  │
        ▼                                  ▼                                  ▼
┌─────────────────┐            ┌─────────────────────┐            ┌─────────────────┐
│  Операционные   │            │     Аналитика        │            │  Инфраструктура │
│  Consumer Groups│            │   Consumer Groups    │            │                 │
│                 │            │                      │            │                 │
│ inventory-svc   │            │ clickhouse-sink      │            │ elasticsearch   │
│ notification-svc│            │ (OLAP для дашбордов) │            │ (логи + поиск)  │
│ fraud-detection │            │                      │            │                 │
│ recommendation  │            │ real-time-metrics    │            │ s3-archiver     │
│   -engine       │            │ (kafka streams)      │            │ (cold storage)  │
└─────────────────┘            └─────────────────────┘            └─────────────────┘
        │                                  │
        │ at-least-once +                  │ at-most-once OK
        │ idempotent consumer              │ (потеря метрики некритична)
        │ (потеря заказа недопустима)      │
```

**Что делает эту архитектуру масштабируемой:**

1. **Развязка продюсеров и consumer'ов**: Order Service не знает о Fraud Detection или Analytics. Они добавлены позже без изменений в Order Service.

2. **Независимые скорости**: Notification Service работает в реальном времени (lag < 1 сек). Analytics-pipeline может отставать на минуты — это допустимо. Каждый читает в своём темпе.

3. **Replay для новых сервисов**: Recommendation Engine добавлен через 6 месяцев после старта. Он читает с offset=0 всю 30-дневную историю заказов и обучает модель на реальных данных.

4. **Изоляция сбоев**: Fraud Detection упала — заказы продолжают создаваться, уведомления отправляются. Когда Fraud Detection восстановится, она проверит все пропущенные заказы.

## Типичные ошибки на интервью

**"Event Sourcing и Event Streaming — одно и то же"**

Нет. Event Streaming — это технический паттерн: поток событий через Kafka. Event Sourcing — архитектурный паттерн: состояние системы определяется историей событий (а не текущим снапшотом в БД). Kafka отлично подходит как хранилище для Event Sourcing, но можно делать Event Sourcing без Kafka (EventStore DB, PostgreSQL с таблицей событий) и Event Streaming без Event Sourcing (Kafka для логов или CDC без ES-паттерна).

**"CDC — это просто опрос БД по расписанию (polling)"**

Нет. CDC через WAL (Debezium) — это подписка на бинарный лог репликации, не polling. Polling ("SELECT WHERE updated_at > last_check") имеет проблемы: задержка (минимум интервал опроса), потеря событий (если строка изменилась дважды между опросами — первое изменение невидимо), нагрузка на БД. CDC из WAL: нет polling, минимальная задержка (<1 сек), захватывает каждое изменение.

**"Для real-time аналитики достаточно обычного consumer'а на kafkajs"**

Для простых метрик — да. Для сложных агрегаций (windows, joins между топиками, stateful обработка) — нет. Для этого существуют специализированные фреймворки: Kafka Streams (Java/Scala), Apache Flink, Apache Spark Streaming. В Node.js-сервисах kafka обычно используется как transport, а агрегация — в специализированных инструментах.

**"Новый сервис должен читать только свежие данные — с момента своего запуска"**

Это проектное решение, а не требование Kafka. Новый сервис может начать с `fromBeginning: true` и прочитать всю историю (в пределах retention), что часто ценно: рекомендательная система, обученная на исторических данных, работает лучше с первого дня. Решение "читать только новые" теряет эту возможность.

**"Kafka Streams — это что-то очень сложное, для больших компаний"**

Kafka Streams — библиотека (не отдельный кластер), которая работает в рамках обычного JVM-приложения. Для Node.js-разработчика: Kafka Streams не применимы напрямую, но концептуально важны знать, что они существуют и решают задачу stateful stream processing. На практике Node.js-команды часто используют ksqlDB (SQL поверх Kafka) или отдают агрегацию в ClickHouse/Druid.
