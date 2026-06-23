# Ключевые концепции RabbitMQ

## AMQP — протокол, на котором говорит RabbitMQ

RabbitMQ реализует **AMQP** (Advanced Message Queuing Protocol, Расширенный протокол очередей сообщений) — открытый wire-level протокол для middleware, ориентированного на сообщения. "Wire-level" означает, что протокол определяет точные байты, передаваемые по сети, — любая клиентская библиотека на любом языке, реализующая AMQP, может работать с RabbitMQ без привязки к вендору.

RabbitMQ использует AMQP 0-9-1 (существует также AMQP 1.0 — другой и несовместимый стандарт; RabbitMQ поддерживает его через плагин, но 0-9-1 — нативный). Когда вы используете `amqplib` в Node.js, вы говорите именно на AMQP 0-9-1.

Ключевое понимание AMQP, которое отличает RabbitMQ от более простых систем: **продюсеры никогда не публикуют напрямую в очереди**. Они публикуют в **exchange** (обменник), который решает, куда маршрутизировать сообщение. Именно это косвенное звено делает модель маршрутизации RabbitMQ такой гибкой.

## Четыре строительных блока

```txt
┌──────────────────────────────────────────────────────────────────┐
│                         RabbitMQ Broker                          │
│                                                                  │
│  Producer ──► Exchange ──(binding)──► Queue ──► Consumer        │
│                  │                                               │
│                  └──(binding)──► Queue ──► Consumer             │
└──────────────────────────────────────────────────────────────────┘
```

### Exchange (Обменник)

Exchange принимает сообщения от продюсеров и маршрутизирует их в очереди по заданным правилам. Exchange **не хранит** сообщения — только маршрутизирует. Если сообщение пришло в exchange, но ни одна очередь не подходит, оно либо удаляется, либо возвращается продюсеру (зависит от флага `mandatory`).

В каждом RabbitMQ-экземпляре предварительно объявлены несколько exchange:
- `""` (пустая строка) — **default exchange**, маршрутизирует напрямую в очередь, чьё имя совпадает с routing key
- `amq.direct`, `amq.topic`, `amq.fanout`, `amq.headers` — стандартные exchange для каждого типа

### Queue (Очередь)

Queue — это то место, где сообщения ждут, пока потребитель не будет готов их обработать. Очереди имеют параметры, управляющие поведением:

```ts
await channel.assertQueue('my-queue', {
  durable: true,      // переживает перезапуск брокера
  exclusive: false,   // другие соединения могут использовать (true = удалить при отключении)
  autoDelete: false,  // не удалять, когда последний потребитель отключается
  arguments: {
    'x-message-ttl': 60000,            // сообщения истекают через 60с, если не обработаны
    'x-dead-letter-exchange': 'dlx',   // куда идут истёкшие/отклонённые сообщения
    'x-max-length': 10000,             // максимум сообщений в очереди
  },
});
```

### Binding (Привязка)

Binding — это связь между exchange и очередью с опциональным **binding key** (ключом привязки). Он указывает exchange: "отправляй подходящие сообщения в эту очередь." Одна очередь может иметь несколько привязок от нескольких exchange; один exchange — несколько привязок к нескольким очередям.

```ts
// Связываем exchange 'orders' с очередью 'email-notifications' по ключу 'order.placed'
await channel.bindQueue('email-notifications', 'orders', 'order.placed');
```

### Routing Key (Ключ маршрутизации)

Routing key — строка, которую продюсер прикрепляет к сообщению при публикации. Exchange использует её (вместе с алгоритмом, специфичным для своего типа) чтобы решить, в какие очереди доставить сообщение.

```ts
channel.publish(
  'orders',           // имя exchange
  'order.placed',     // routing key — используется exchange для маршрутизации
  Buffer.from(JSON.stringify(payload)),
  { persistent: true },
);
```

## Четыре типа exchange

Это ядро мощи RabbitMQ — и то, что чаще всего проверяют на интервью.

### 1. Direct exchange (Прямой)

Маршрутизирует сообщение в очередь, если binding key **точно совпадает** с routing key.

```txt
Exchange: 'notifications' (тип: direct)

Привязки:
  'notifications' ──[email]──► queue: 'email-queue'
  'notifications' ──[sms]────► queue: 'sms-queue'
  'notifications' ──[push]───► queue: 'push-queue'

Сообщение с routing key 'email' → только в 'email-queue'
Сообщение с routing key 'sms'   → только в 'sms-queue'
```

```ts
import amqplib from 'amqplib';

const connection = await amqplib.connect('amqp://localhost');
const channel = await connection.createChannel();

// Настройка
await channel.assertExchange('notifications', 'direct', { durable: true });
await channel.assertQueue('email-queue', { durable: true });
await channel.assertQueue('sms-queue', { durable: true });
await channel.bindQueue('email-queue', 'notifications', 'email');
await channel.bindQueue('sms-queue', 'notifications', 'sms');

// Публикация — только email-queue получит это сообщение
channel.publish(
  'notifications',
  'email',
  Buffer.from(JSON.stringify({ userId: 42, message: 'Ваш заказ оформлен' })),
  { persistent: true },
);
```

**Применение:** Маршрутизация разных типов уведомлений, распределение задач по конкретным пулам воркеров, маршрутизация сообщений по тенантам.

### 2. Topic exchange (Тематический)

Маршрутизирует сообщение в очереди, чей binding key **совпадает с паттерном** с использованием wildcards (джокеров):
- `*` — совпадает ровно с одним словом (один сегмент, разделённый точками)
- `#` — совпадает с нулём или более словами

```txt
Exchange: 'events' (тип: topic)

Привязки:
  'events' ──[order.*]────────► queue: 'order-service'    → совпадает: order.placed, order.cancelled
  'events' ──[*.placed]───────► queue: 'analytics'        → совпадает: order.placed, payment.placed
  'events' ──[payment.#]──────► queue: 'billing-service'  → совпадает: payment.processed, payment.refund.initiated
  'events' ──[#]──────────────► queue: 'audit-log'        → совпадает со всем

Routing key 'order.placed':
  → order-service   ✓ (order.*)
  → analytics       ✓ (*.placed)
  → audit-log       ✓ (#)
  → billing-service ✗ (payment.# не совпадает)
```

```ts
await channel.assertExchange('events', 'topic', { durable: true });
await channel.assertQueue('order-service', { durable: true });
await channel.assertQueue('analytics', { durable: true });

await channel.bindQueue('order-service', 'events', 'order.*');
await channel.bindQueue('analytics', 'events', '*.placed');

// Это сообщение идёт В ОБЕ очереди
channel.publish(
  'events',
  'order.placed',
  Buffer.from(JSON.stringify({ orderId: '123' })),
  { persistent: true },
);

// Это сообщение идёт только в order-service (не совпадает с *.placed,
// потому что 'cancelled' ≠ 'placed')
channel.publish(
  'events',
  'order.cancelled',
  Buffer.from(JSON.stringify({ orderId: '123' })),
  { persistent: true },
);
```

**Применение:** Event-driven микросервисы, где разные сервисы интересуются разными подмножествами событий. Это наиболее гибкий тип exchange и наиболее часто используемый в продакшн-системах.

### 3. Fanout exchange (Веерный)

Игнорирует routing key полностью и маршрутизирует сообщение **во все очереди, привязанные к exchange**.

```txt
Exchange: 'order-events' (тип: fanout)

Привязки (routing key не важен — игнорируется):
  'order-events' ──► queue: 'email-service'
  'order-events' ──► queue: 'inventory-service'
  'order-events' ──► queue: 'analytics-service'

Любое сообщение в 'order-events' → все три очереди получают копию
```

```ts
await channel.assertExchange('order-events', 'fanout', { durable: true });
await channel.assertQueue('email-service', { durable: true });
await channel.assertQueue('inventory-service', { durable: true });
await channel.assertQueue('analytics-service', { durable: true });

// Привязываем все очереди — '' как routing key это конвенция для fanout (всё равно игнорируется)
await channel.bindQueue('email-service', 'order-events', '');
await channel.bindQueue('inventory-service', 'order-events', '');
await channel.bindQueue('analytics-service', 'order-events', '');

// Все три очереди получают это сообщение
channel.publish(
  'order-events',
  '',  // routing key игнорируется
  Buffer.from(JSON.stringify({ orderId: '123', total: 99.99 })),
  { persistent: true },
);
```

**Применение:** Широковещательная рассылка событий всем заинтересованным сервисам. Классический пример: событие "заказ оформлен" в e-commerce, которое должно дойти до email-сервиса, склада, биллинга и аналитики — одновременно и независимо.

**Важно:** Fanout реализует Pub/Sub: каждый сервис имеет свою очередь (получает собственную копию и обрабатывает независимо), а exchange доставляет во все.

### 4. Headers exchange (На основе заголовков)

Маршрутизирует на основе **заголовков сообщения** (key-value метаданные), а не routing key. Привязка указывает, какие заголовки должны совпасть.

```ts
await channel.assertExchange('reports', 'headers', { durable: true });
await channel.assertQueue('pdf-reports', { durable: true });
await channel.assertQueue('csv-reports', { durable: true });

// Привязка с правилами сопоставления заголовков
await channel.bindQueue('pdf-reports', 'reports', '', {
  'x-match': 'all',   // ВСЕ заголовки должны совпасть
  format: 'pdf',
  region: 'eu',
});
await channel.bindQueue('csv-reports', 'reports', '', {
  'x-match': 'any',   // ЛЮБОЙ заголовок должен совпасть
  format: 'csv',
});

// Это идёт в pdf-reports (format=pdf И region=eu — оба совпадают)
channel.publish('reports', '', Buffer.from('...'), {
  headers: { format: 'pdf', region: 'eu', requestId: 'abc123' },
});

// Это идёт в csv-reports (format=csv совпадает)
channel.publish('reports', '', Buffer.from('...'), {
  headers: { format: 'csv', region: 'us' },
});
```

**Применение:** Маршрутизация на основе метаданных сообщения без кодирования информации маршрутизации в строку routing key. На практике используется редко — topic exchange покрывает большинство потребностей в маршрутизации и читается понятнее.

## Сравнение типов exchange

```txt
┌──────────────┬──────────────────────────┬──────────────────────────────────────────┐
│ Exchange     │ Маршрутизирует по        │ Типичное применение                      │
├──────────────┼──────────────────────────┼──────────────────────────────────────────┤
│ Direct       │ Точному совпадению ключа │ Маршрутизация задач, типы уведомлений    │
│ Topic        │ Паттерну с wildcards     │ Event-driven микросервисы                │
│ Fanout       │ Ничему (игнорирует ключ) │ Широковещание, Pub/Sub                   │
│ Headers      │ Значениям заголовков     │ Маршрутизация по атрибутам сообщения     │
└──────────────┴──────────────────────────┴──────────────────────────────────────────┘
```

## Default exchange — полезный шорткат

Default exchange (пустая строка `""`) — это предварительно объявленный direct exchange с особым правилом: **каждая очередь автоматически привязана к нему со своим именем в качестве routing key**.

Поэтому можно делать так, не объявляя exchange вовсе:

```ts
// Объявление exchange не нужно — используется default exchange
await channel.assertQueue('my-tasks', { durable: true });

// Это маршрутизируется в 'my-tasks' через default exchange
channel.sendToQueue(
  'my-tasks',
  Buffer.from(JSON.stringify({ task: 'process-image', imageId: '456' })),
  { persistent: true },
);
```

`sendToQueue` — это синтаксический сахар для `publish('', queueName, ...)` — публикует в default exchange с именем очереди как routing key. Подходит для простых случаев, но при росте системы явные exchange дают больше гибкости (можно добавить нового потребителя в topic exchange, не меняя продюсер).

## Virtual hosts (виртуальные хосты)

RabbitMQ использует **virtual hosts** (vhosts, виртуальные хосты) для логической изоляции — аналогично тому, как разные базы данных в PostgreSQL изолированы друг от друга. У каждого vhost свой набор exchange, очередей, привязок и прав пользователей.

```ts
// Подключение к конкретному vhost
const connection = await amqplib.connect('amqp://user:password@localhost:5672/my-app');
//                                                                               ^^^^^^^^
//                                                                               имя vhost
```

По умолчанию используется vhost `/`. В продакшне правильная практика — давать каждому приложению собственный vhost, а не использовать общий дефолтный.

## Channels — соединения без накладных расходов

Соединение с RabbitMQ — это TCP-соединение: дорого открывать. **Channel** (канал) — лёгкое виртуальное соединение, мультиплексированное поверх одного TCP-соединения. На практике: одно соединение на процесс, каналы — по необходимости (на поток, на операцию или на потребителя).

```ts
const connection = await amqplib.connect('amqp://localhost');

// Одно соединение, несколько каналов
const publisherChannel = await connection.createChannel();
const consumerChannel = await connection.createChannel();

// Каналы в amqplib не потокобезопасны — не используйте один канал
// для параллельных async-операций
```

Частая ошибка с amqplib: переиспользование одного канала и для публикации, и для потребления в высоконагруженном приложении. Best practice — отдельные каналы для публикации и потребления, никогда не вызывать методы канала конкурентно из двух async-операций на одном канале.

## Типичные ошибки на интервью

- **"Продюсеры публикуют напрямую в очереди"** — нет. Продюсеры публикуют в exchange. Exchange маршрутизирует в очереди через привязки. Это фундаментальное архитектурное решение AMQP, и ошибка здесь сразу сигнализирует о незнакомстве с протоколом.

- **"В topic exchange * совпадает с нулём или более словами"** — нет, `*` совпадает ровно с одним словом. `#` совпадает с нулём или более. Это важное различие: `order.*` совпадает с `order.placed`, но НЕ с `order.payment.processed` и НЕ с `order` (ноль сегментов). Используйте `order.#`, если нужны все под-события.

- **"Fanout — это то же самое, что broadcast всем потребителям одной очереди"** — нет. Fanout рассылает всем **очередям**, привязанным к exchange. Каждая очередь затем независимо доставляет своим потребителям. Если нужны конкурирующие потребители (балансировка нагрузки) — ставьте нескольких потребителей на одну очередь. Если каждый должен получить сообщение — своя очередь для каждого, все привязаны к одному fanout exchange.

- **"Если поставить несколько потребителей на одну очередь, каждый получит каждое сообщение"** — нет, очереди так не работают. Несколько потребителей на одной очереди — это конкурирующие потребители (round-robin балансировка нагрузки): каждое сообщение получает ровно один потребитель. Для "каждый получает копию" нужен Pub/Sub: один fanout/topic exchange, по одной очереди на каждого потребителя.

- **"Привязки — просто конфигурация, на производительность не влияют"** — не совсем. При каждой публикации сообщение проверяется по всем привязкам exchange. Для topic exchange с тысячами привязок сопоставление с паттерном имеет стоимость. На практике это редко становится узким местом, но это честный ответ.

- **"Default exchange особенный — он работает иначе, чем другие direct exchange"** — он ДЕЙСТВИТЕЛЬНО особенный в одном: каждая очередь автоматически привязана к нему со своим именем как binding key. Вы не можете вручную привязать очереди к нему (нельзя воспроизвести поведение auto-binding на custom exchange). В остальном он ведёт себя как любой direct exchange.
