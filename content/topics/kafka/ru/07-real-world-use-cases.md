# Kafka в реальных проектах — практические сценарии

## Сценарий 1: Event Streaming — поток событий для нескольких потребителей

Это сценарий, ради которого Kafka и создавалась. И лучший способ показать, почему здесь она выигрывает у очереди.

### Архитектура: заказы в e-commerce

Пользователь размещает заказ. Этот факт интересен четырём независимым системам.
Order Service публикует его один раз, в один топик из 12 партиций (partitions):

```txt
  [Order Service]  ──▶  топик "order-events"
     (producer)          12 партиций, ключ = orderId
                         хранение 30 дней
```

Четыре группы потребителей (consumer groups) читают этот же топик, каждая
в своём темпе:

| Группа потребителей | Что она делает с событием заказа |
|---|---|
| Inventory | Резервирует товар на складе |
| Notification | Отправляет email и push-уведомления |
| Analytics | Обновляет дашборды продаж |
| Fraud Detection | Проверяет покупку на мошеннические паттерны |

**Почему это лучше, чем очередь:**
- Order Service ничего не знает о системах ниже по потоку. Он просто публикует факт
- Добавление группы Fraud Detection не требует изменений в Order Service
- Analytics упала на 3 часа → перезапустилась → догнала все пропущенные события
- Можно воспроизвести историю заказов за последние 30 дней для новой модели
  машинного обучения

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
  orderId: string;          // ключ партиции
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

**Event Sourcing** — архитектурный паттерн. Состояние сущности здесь — не текущий снимок в таблице базы данных (БД). Это последовательность событий, которые к этому состоянию привели.

```txt
Традиционный подход (state-based):
  orders, одна строка таблицы:
    { id: "ord-1", status: "shipped", amount: 1500,
      updatedAt: "..." }
  
  Вопрос: "Почему статус shipped, а не delivered?"
  Ответ: неизвестно — мы храним только текущее состояние.

Event Sourcing подход:
  order-events лог (у всех событий orderId "ord-1"):
    [0] ORDER_PLACED    { amount: 1500, items: [...] }
    [1] PAYMENT_OK      { method: "card", txId: "tx-42" }
    [2] ORDER_CONFIRMED { warehouseId: "wh-3" }
    [3] ORDER_SHIPPED   { trackingId: "TRK-99", carrier: "FedEx" }
  
  Текущее состояние = применить все события по порядку.
  Полная история всегда доступна.
  Можно "перемотать" до любого момента.
```

Kafka — идеальное хранилище для лога event sourcing: только дозапись (append-only), высокая пропускная способность, долгое хранение, много независимых читателей.

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

Классический стек ELK (Elasticsearch, Logstash, Kibana), перед которым стоит
Kafka:

```txt
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ Service A  │  │ Service B  │  │ Service C  │
    │ пишет логи │  │ пишет логи │  │ пишет логи │
    │ в stdout   │  │ в stdout   │  │ в stdout   │
    └────────────┘  └────────────┘  └────────────┘
           ▼               ▼               ▼
        ┌────────────────────────────────────┐
        │ Filebeat / Fluentd (сборщик логов) │
        │ Читает логи из файлов и stdout,    │
        │ затем пишет их в Kafka             │
        └────────────────────────────────────┘
                           ▼
           Topic: "application-logs"
           Retention: 3 days
           Partitions: 24 (key = serviceId)
          ▼                 ▼               ▼
  ┌───────────────┐  ┌────────────┐  ┌─────────────┐
  │ Logstash      │  │ Monitoring │  │ S3 Archiver │
  │ пишет в       │  │ алерты     │  │ долгое      │
  │ Elasticsearch │  │ на ошибки  │  │ хранение    │
  └───────────────┘  └────────────┘  └─────────────┘
```

**Зачем Kafka в этой цепочке, а не напрямую в Elasticsearch?**

Без Kafka: Filebeat → Elasticsearch напрямую. Проблемы:
- Elasticsearch перегружается при всплесках трафика
- Логи теряются, если Elasticsearch недоступен
- Нет возможности повторно обработать логи (например, при изменении индекса)

С Kafka: Kafka выступает как буфер. При перегрузке Elasticsearch — логи накапливаются в Kafka, Logstash берёт их в своём темпе. При падении Elasticsearch — логи не теряются, они в логе Kafka.

## Сценарий 4: Change Data Capture (CDC)

**Change Data Capture (CDC)** — это механизм захвата изменений в базе данных и публикации их как потока событий. Вместо того чтобы опрашивать БД ("что изменилось за последнюю минуту?"), CDC подписывается на бинарный лог репликации самой БД.

PostgreSQL имеет Write-Ahead Log (WAL) — бинарный журнал всех изменений. Его уже читают резервные реплики (standby). Debezium (популярный CDC-коннектор) читает тот же WAL, и для PostgreSQL он выглядит как ещё одна реплика.

```txt
  ┌──────────────┐        ┌──────────┐        ┌─────────────────┐
  │ PostgreSQL   │  WAL   │ Debezium │        │ Kafka topic     │
  │              │───────▶│ (Kafka   │───────▶│ "postgres.      │
  │ INSERT order │        │ Connect) │        │  public.orders" │
  │ UPDATE order │        └──────────┘        │                 │
  │ DELETE order │                            │ [insert-event]  │
  └──────────────┘                            │ [update-event]  │
                                              │ [delete-event]  │
                                              └─────────────────┘

              Из этого топика независимо читают трое:
               ▼                   ▼                 ▼
     ┌──────────────────┐  ┌──────────────┐  ┌───────────────┐
     │ Поисковый индекс │  │ Аналитика    │  │ Журнал аудита │
     │ (Elasticsearch)  │  │ (ClickHouse) │  │ (S3)          │
     └──────────────────┘  └──────────────┘  └───────────────┘
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
Подход 1: события из кода:
  await db.transaction(async (tx) => {
    await tx.orders.create(order);
    // проблема: не атомарно!
    await kafka.send('order-created', order);
  });
  
  Проблема: транзакция в БД и запись в Kafka не атомарны.
  Если Kafka недоступна — заказ создан, событие не отправлено.

Подход 2: Transactional Outbox:
  await db.transaction(async (tx) => {
    await tx.orders.create(order);
    await tx.outbox.insert({
      topic: 'order-created', payload: order,
    });
    // Всё в одной транзакции БД → атомарно
  });
  // Отдельный процесс читает outbox и пишет в Kafka

Подход 3: CDC (Debezium):
  await db.orders.create(order);  // просто пишем в БД
  // Debezium захватывает изменение из WAL и пишет его в Kafka.
  // Гарантия: если изменение попало в БД, оно попадёт и в
  // Kafka, потому что WAL читается как обычная реплика.
```

CDC особенно ценен, когда нужно синхронизировать данные между разными хранилищами без изменения кода приложения.

## Сценарий 5: Real-Time Analytics Pipeline

Конвейер аналитики интернет-магазина в реальном времени. OLAP — это
оперативная аналитическая обработка (online analytical processing). Так
называют хранилище, заточенное под агрегирующие запросы по многим строкам,
а не под чтение по одной строке.

```txt
       ┌────────────────────────────────────────────────┐
       │ Источники данных: Order Service, User Service, │
       │ Product Service, Web Frontend                  │
       └────────────────────────────────────────────────┘
                                ▼
               ┌─────────────────────────────────┐
               │ Kafka topics                    │
               │ "order-events"   "user-events"  │
               │ "product-views"  "click-stream" │
               └─────────────────────────────────┘
            ▼                     ▼                   ▼
  ┌───────────────────┐  ┌─────────────────┐  ┌───────────────┐
  │ Kafka Streams /   │  │ ClickHouse /    │  │ Elasticsearch │
  │ Apache Flink      │  │ Apache Druid    │  │ (поиск,       │
  │ (агрегация в      │  │ (OLAP-хранилище │  │ аналитика)    │
  │ реальном времени) │  │ для дашбордов)  │  │               │
  └───────────────────┘  └─────────────────┘  └───────────────┘
```

Ветка Kafka Streams / Flink считает те метрики, на которые смотрит бизнес:
выручку в минуту, конверсию из просмотров в покупки, топ товаров за последние
5 минут и число активных пользователей прямо сейчас.

**Пример простой агрегации с kafkajs:**

```ts
// Подсчёт заказов по статусам за скользящее окно
// (в реальной эксплуатации используют Kafka Streams или Flink)
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

Соберём вместе все сценарии в одну реальную архитектуру. Пять продюсеров пишут
в пять топиков одного кластера:

| Продюсер | Топик | Партиций | Хранение |
|---|---|---|---|
| Order Service | `order-events` | 12 | 30 дней |
| Payment Service | `payment-events` | 6 | 30 дней |
| User Service | `user-events` | 6 | 7 дней |
| CDC / Debezium | `db.public.orders` | 12 | 7 дней |
| Filebeat | `app-logs` | 24 | 3 дня |

Эти топики читают три семейства групп потребителей:

| Семейство | Группы потребителей |
|---|---|
| Операционные | `inventory-svc`, `notification-svc`, `fraud-detection`, `recommendation-engine` |
| Аналитика | `clickhouse-sink`, который наполняет аналитическое хранилище для дашбордов, и `real-time-metrics` на Kafka Streams |
| Инфраструктура | `elasticsearch` для логов и поиска, `s3-archiver` для холодного хранения |

Двум семействам нужны разные гарантии доставки. Операционные группы работают
в режиме at-least-once с идемпотентным потребителем: каждое событие
обрабатывается, иногда больше одного раза, и повтор не вредит. Терять заказ
нельзя. Аналитические группы могут работать в режиме at-most-once, где событие
обрабатывается один раз или теряется. Потеря одной метрики некритична.

**Что делает эту архитектуру масштабируемой:**

1. **Развязка продюсеров и потребителей**: Order Service не знает о Fraud Detection или Analytics. Они добавлены позже без изменений в Order Service.

2. **Независимые скорости**: у каждой группы своё отставание (lag) — расстояние между самым новым сообщением в партиции и последним, которое эта группа обработала. Notification Service держит отставание меньше секунды. Конвейер аналитики может отставать на минуты, и это допустимо. Каждая группа читает в своём темпе.

3. **Повторное чтение (replay) для новых сервисов**: Recommendation Engine добавлен через 6 месяцев после старта. Он читает с offset=0 всю 30-дневную историю заказов и обучает модель на реальных данных.

4. **Изоляция сбоев**: Fraud Detection упала — заказы продолжают создаваться, уведомления отправляются. Когда Fraud Detection восстановится, она проверит все пропущенные заказы.

## Типичные ошибки на интервью

**"Event Sourcing и Event Streaming — одно и то же"**

Нет. Event Streaming — это технический паттерн: поток событий через Kafka. Event Sourcing — архитектурный паттерн: состояние системы выводится из истории событий, а не из текущего снимка в БД.

Kafka отлично подходит как хранилище для Event Sourcing, но эти две вещи независимы. Event Sourcing можно делать без Kafka — в EventStoreDB или в обычной таблице событий PostgreSQL. Event Streaming можно делать без Event Sourcing: Kafka для логов или CDC, где событийного состояния нет вообще.

**"CDC — это просто опрос БД по расписанию (polling)"**

Нет. CDC через WAL (Debezium) — это подписка на бинарный лог репликации, а не опрос по расписанию. У опроса запросом `SELECT WHERE updated_at > last_check` три проблемы:

- **Задержка.** Изменение не видно раньше, чем пройдёт интервал опроса.
- **Потеря событий.** Если строка изменилась дважды между двумя опросами, первое изменение не видно вообще.
- **Нагрузка.** Каждый опрос — ещё один запрос к боевой базе.

У CDC из WAL нет ни одной из них: опроса нет, задержка меньше секунды, захватывается каждое изменение.

**"Для аналитики в реальном времени достаточно обычного потребителя на kafkajs"**

Для простых метрик — да. Для сложных агрегаций нет: это оконные агрегации (windowing), соединения между топиками (joins) и обработка с состоянием (stateful). Для них существуют специализированные фреймворки: Kafka Streams (Java/Scala), Apache Flink, Apache Spark Streaming. В сервисах на Node.js Kafka обычно используют как транспорт, а агрегацию отдают этим инструментам.

**"Новый сервис должен читать только свежие данные — с момента своего запуска"**

Это проектное решение, а не требование Kafka. Новый сервис может начать с `fromBeginning: true` и прочитать всю историю, которую топик ещё хранит, в пределах срока хранения. Это часто ценно. Рекомендательная система, обученная на исторических данных, работает лучше с первого дня. Если выбрать "читать только новые", эта возможность потеряна навсегда.

**"Kafka Streams — это что-то очень сложное, для больших компаний"**

Kafka Streams — это библиотека, а не отдельный кластер, и работает она внутри обычного приложения на JVM (виртуальной машине Java). Разработчику на Node.js применить её напрямую нельзя. Знать о ней всё равно важно: это стандартный ответ на обработку потока с состоянием.

На практике команды на Node.js пишут потоковые запросы в ksqlDB. Он кладёт SQL (язык структурированных запросов) поверх Kafka. Второй вариант — отдать агрегацию в ClickHouse или Druid.
