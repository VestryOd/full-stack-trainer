# Реальные сценарии использования

## Сценарий 1 — Фоновая обработка задач

Самая распространённая точка входа в очереди сообщений для fullstack-инженеров: вынесение медленной или ненадёжной работы за пределы цикла HTTP-запроса.

**Паттерн:** HTTP-обработчик публикует сообщение о задаче и немедленно возвращает 202 Accepted. Отдельный воркер-процесс потребляет сообщение и выполняет реальную работу.

```txt
HTTP Request → API Server → [Queue: jobs] → Worker Process
                ↓
         202 Accepted (мгновенно)          (медленная работа здесь)
```

### Пайплайн обработки изображений

```ts
// api-server/routes/upload.ts
import { Router } from 'express';
import { getChannel } from '../rabbitmq';

const router = Router();

router.post('/images', async (req, res) => {
  // 1. Сохраняем оригинал в S3 сразу
  const s3Key = await s3.upload(req.file);

  // 2. Публикуем задачу — не обрабатываем синхронно
  const channel = await getChannel();
  channel.publish(
    'jobs',
    'image.resize',
    Buffer.from(JSON.stringify({
      jobId: crypto.randomUUID(),
      s3Key,
      userId: req.user.id,
      variants: ['thumbnail', 'medium', 'large'],
    })),
    { persistent: true, messageId: crypto.randomUUID() },
  );

  // 3. Возвращаем немедленно — клиент опрашивает или использует websocket для получения результата
  res.status(202).json({ status: 'processing', s3Key });
});
```

```ts
// worker/image-processor.ts
import sharp from 'sharp';

const VARIANTS = {
  thumbnail: { width: 150, height: 150 },
  medium:    { width: 800, height: 600 },
  large:     { width: 1920, height: 1080 },
};

await channel.prefetch(3); // максимум 3 изображения одновременно

channel.consume('image-processing', async (msg) => {
  if (!msg) return;

  const job = JSON.parse(msg.content.toString()) as ImageJob;

  try {
    const original = await s3.download(job.s3Key);

    // Параллельная обработка всех вариантов
    await Promise.all(
      job.variants.map(async (variant) => {
        const resized = await sharp(original)
          .resize(VARIANTS[variant])
          .webp({ quality: 85 })
          .toBuffer();

        const variantKey = job.s3Key.replace('.jpg', `-${variant}.webp`);
        await s3.upload(variantKey, resized);
      }),
    );

    // Уведомляем инициатора о завершении через событие
    channel.publish(
      'jobs',
      'image.processed',
      Buffer.from(JSON.stringify({ jobId: job.jobId, variants: job.variants })),
      { persistent: true },
    );

    channel.ack(msg);
  } catch (err) {
    // Временная ошибка S3? Повторить. Испорченное изображение? Dead-letter.
    const isRetryable = err instanceof S3Error || err instanceof NetworkError;
    channel.nack(msg, false, isRetryable);
  }
});
```

**Почему это лучше синхронной обработки:**
- HTTP-запрос возвращает за миллисекунды, а не секунды
- Воркер может работать на отдельной инфраструктуре (другой профиль CPU/RAM)
- Несколько воркеров обрабатывают разные изображения параллельно
- Всплески трафика загрузок не вызывают всплеска задержки обработки — они растят очередь

---

## Сценарий 2 — Развязка микросервисов через события

Сценарий с сервисом заказов, который возникает на каждом senior-собеседовании по системному дизайну.

**Проблема:** Оформляется заказ. Должны отреагировать downstream-системы: зарезервировать склад, сгенерировать счёт, отправить письмо, записать продажу в аналитику. Синхронные вызовы каждой цепляют их доступность к вашей.

```txt
❌ Жёсткая связность:
Order Service → Inventory Service (таймаут?)
             → Billing Service    (обслуживание?)
             → Email Service      (медленный SMTP?)
             → Analytics Service  (DDoS?)

Если ЛЮБОЙ downstream упадёт → оформление заказа падает

✅ Развязаны через события:
Order Service → [Exchange: order-events (fanout)]
                    ├──► [Queue: inventory]  → Inventory Service
                    ├──► [Queue: billing]    → Billing Service
                    ├──► [Queue: email]      → Email Service
                    └──► [Queue: analytics]  → Analytics Service

Order Service не знает ни об одном downstream-сервисе
Каждый сервис обрабатывает независимо в своём темпе
```

```ts
// order-service/order.service.ts
export class OrderService {
  constructor(
    private db: Database,
    private channel: Channel,
  ) {}

  async placeOrder(input: PlaceOrderInput): Promise<Order> {
    const order = await this.db.transaction(async (trx) => {
      const created = await trx.orders.create({
        userId: input.userId,
        items: input.items,
        totalAmount: input.totalAmount,
        status: 'pending',
      });

      // Запись в outbox в той же транзакции (см. статью 04)
      await trx.outbox.create({
        eventType: 'order.placed',
        payload: {
          orderId: created.id,
          userId: created.userId,
          items: created.items,
          totalAmount: created.totalAmount,
          placedAt: new Date().toISOString(),
        },
      });

      return created;
    });

    return order;
    // Публикация события происходит через outbox relay — не здесь
  }
}
```

```ts
// inventory-service/consumer.ts — полностью независим
channel.consume('inventory', async (msg) => {
  if (!msg) return;
  const event = JSON.parse(msg.content.toString());

  try {
    await Promise.all(
      event.items.map((item: OrderItem) =>
        db.inventory.reserve(item.sku, item.quantity, event.orderId),
      ),
    );

    // Публикуем компенсирующее событие при нехватке товара
    channel.publish('order-events', 'order.inventory-reserved',
      Buffer.from(JSON.stringify({ orderId: event.orderId })),
      { persistent: true },
    );

    channel.ack(msg);
  } catch (err) {
    if (err instanceof InsufficientStockError) {
      // Компенсирующее событие: сообщить order service об отмене
      channel.publish('order-events', 'order.inventory-failed',
        Buffer.from(JSON.stringify({ orderId: event.orderId, reason: err.message })),
        { persistent: true },
      );
      channel.ack(msg); // ack — это ожидаемая бизнес-логика, не системная ошибка
    } else {
      channel.nack(msg, false, false); // неожиданная ошибка → dead-letter
    }
  }
});
```

**Ключевое понимание:** Order Service не импортирует и не вызывает inventory, billing или email сервисы. Добавление новой downstream-реакции (например, обнаружение мошенничества) требует нулевых изменений в order service — просто добавить новую привязку к fanout exchange.

---

## Сценарий 3 — Ограничение нагрузки на downstream-сервисы

**Проблема:** Внешний API (платёжный шлюз, SMS-провайдер, сервис доставки email) имеет rate limits. Ваша система может генерировать запросы быстрее, чем API позволяет. Без очереди вы либо добавляете сложное клиентское троттлирование, либо получаете 429.

```txt
Запросы пользователей (всплеск) → [Queue: sms-outbox] → SMS Worker (управляемая скорость)
                                                               ↓
                                                   Внешний SMS API (rate limit)
```

```ts
// sms-worker/index.ts
const SMS_RATE_LIMIT_PER_SECOND = 10;

await channel.prefetch(SMS_RATE_LIMIT_PER_SECOND);

channel.consume('sms-outbox', async (msg) => {
  if (!msg) return;

  const { phoneNumber, message, campaignId } = JSON.parse(msg.content.toString());

  try {
    await twilioClient.messages.create({
      body: message,
      from: process.env.TWILIO_FROM,
      to: phoneNumber,
    });

    await db.smsLog.create({ phoneNumber, campaignId, status: 'sent', sentAt: new Date() });
    channel.ack(msg);
  } catch (err) {
    if (err instanceof TwilioRateLimitError) {
      // Откатываемся и возвращаем сообщение в очередь
      await sleep(1000);
      channel.nack(msg, false, true); // requeue — будет подхвачено через момент
    } else {
      channel.nack(msg, false, false); // dead-letter
    }
  }
});

// Очередь выступает буфером: всплески из 10 000 SMS ставятся в очередь
// и обрабатываются с безопасной скоростью 10/сек — внешний API не перегружается
```

**Prefetch как ограничитель скорости:** Установка `prefetch(N)` ограничивает in-flight сообщения на воркер. При N воркерах с `prefetch(10)` у вас 10N параллельных запросов к внешнему API. Настраивайте N × prefetch так, чтобы оставаться в пределах rate limit.

---

## Сценарий 4 — Email-уведомления через fan-out

Разные типы событий должны запускать отправку email. Вместо того чтобы каждый сервис звонил в email-сервис напрямую, они публикуют события, на которые email-сервис подписывается через topic exchange.

```txt
Exchange: 'notifications' (topic)

order-service    ──[order.placed]────────►
payment-service  ──[payment.failed]──────► [Queue: email-notifications] → Email Worker
auth-service     ──[user.registered]─────►
billing-service  ──[subscription.renewed]►
```

```ts
// email-service/setup.ts
async function setupEmailConsumer(channel: Channel): Promise<void> {
  await channel.assertExchange('notifications', 'topic', { durable: true });
  await channel.assertQueue('email-notifications', {
    durable: true,
    arguments: { 'x-dead-letter-exchange': 'notifications.dlx' },
  });

  // Подписываемся на ВСЕ события уведомлений от любого сервиса
  await channel.bindQueue('email-notifications', 'notifications', '#');

  await channel.prefetch(20);

  channel.consume('email-notifications', async (msg) => {
    if (!msg) return;

    const routingKey = msg.fields.routingKey; // 'order.placed', 'user.registered' и т.д.
    const event = JSON.parse(msg.content.toString());

    const template = getEmailTemplate(routingKey);
    if (!template) {
      // Неизвестный тип события — ack и игнорируем
      channel.ack(msg);
      return;
    }

    try {
      await sendEmail({
        to: event.userEmail ?? event.customerEmail,
        subject: template.subject(event),
        html: template.render(event),
      });

      channel.ack(msg);
    } catch (err) {
      channel.nack(msg, false, false);
    }
  });
}

function getEmailTemplate(routingKey: string): EmailTemplate | null {
  const templates: Record<string, EmailTemplate> = {
    'order.placed':          { subject: (e) => `Заказ #${e.orderId} подтверждён`, render: renderOrderConfirmed },
    'payment.failed':        { subject: () => 'Ошибка оплаты — требуется действие', render: renderPaymentFailed },
    'user.registered':       { subject: () => 'Добро пожаловать!', render: renderWelcome },
    'subscription.renewed':  { subject: (e) => `Подписка продлена — ${e.amount}₽`, render: renderRenewal },
  };
  return templates[routingKey] ?? null;
}
```

**Зачем topic exchange вместо прямых вызовов:** Добавление нового типа уведомления (например, `shipment.dispatched`) не требует изменений в email-сервисе — просто добавьте шаблон. Привязка `#` в topic exchange автоматически перехватывает всё.

---

## Сценарий 5 — Полный пайплайн заказа (пример для system design)

Это та архитектура, которую вы бы нарисовали на system design интервью для e-commerce платформы. Объединяет все паттерны из предыдущих статей.

```txt
┌─────────────────── ПАЙПЛАЙН ЗАКАЗА ──────────────────────────────────────────┐
│                                                                               │
│  [POST /orders]                                                               │
│       │                                                                       │
│       ▼                                                                       │
│  [Order Service]  ──(outbox relay)──► Exchange: 'order-events' (topic)       │
│       │                                    │                                  │
│       ▼                               ┌────┴────────────────────┐             │
│  [DB: orders]                         ▼                         ▼             │
│  [DB: outbox]          ┌──[Queue: inventory]──►   ┌──[Queue: email]──►       │
│                        │   Inventory Service  │   │   Email Service  │       │
│                        └──────────────────────┘   └──────────────────┘       │
│                                    │                                          │
│                          ┌─────────┴──────────┐                              │
│                          ▼                    ▼                               │
│                 order.inventory-    order.inventory-                          │
│                 reserved            failed                                    │
│                          │                │                                   │
│                          ▼                ▼                                   │
│               [Queue: payment]   [Queue: order-updates]                      │
│               Payment Service    Order Service (компенсация саги)            │
│                          │                                                    │
│                          ▼                                                    │
│             payment.processed / payment.failed                                │
│                          │                                                    │
│                          ▼                                                    │
│               [Queue: order-updates]                                          │
│               Order Service обновляет статус                                  │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

Это **сага на основе хореографии (choreography-based saga)** — каждый сервис реагирует на события и публикует свои. Нет центрального координатора; сервисы общаются через шину сообщений.

```ts
// order-service/saga-handler.ts
// Слушает события downstream-сервисов и обновляет статус заказа

channel.consume('order-updates', async (msg) => {
  if (!msg) return;

  const routingKey = msg.fields.routingKey;
  const event = JSON.parse(msg.content.toString());

  switch (routingKey) {
    case 'order.inventory-reserved':
      await db.orders.updateStatus(event.orderId, 'inventory_reserved');
      break;

    case 'order.inventory-failed':
      // Компенсирующая транзакция: отменить заказ
      await db.orders.updateStatus(event.orderId, 'cancelled');
      // Уведомить клиента
      channel.publish('notifications', 'order.cancelled',
        Buffer.from(JSON.stringify(event)), { persistent: true });
      break;

    case 'payment.processed':
      await db.orders.updateStatus(event.orderId, 'confirmed');
      channel.publish('notifications', 'order.confirmed',
        Buffer.from(JSON.stringify(event)), { persistent: true });
      break;

    case 'payment.failed':
      await db.orders.updateStatus(event.orderId, 'payment_failed');
      // Освободить резерв на складе
      channel.publish('order-events', 'order.inventory-release',
        Buffer.from(JSON.stringify(event)), { persistent: true });
      break;
  }

  channel.ack(msg);
});
```

### Почему эта архитектура устойчива к сбоям

```txt
Сбой 1: Email Service недоступен
  → событие order.placed лежит в очереди 'email'
  → Inventory и Payment продолжают работу нормально
  → При восстановлении Email Service обрабатывает накопленные события
  → Клиент получает письмо с задержкой, но заказ обработан корректно

Сбой 2: Payment Service падает в процессе обработки
  → payment.processed никогда не публикуется
  → Заказ остаётся в статусе 'inventory_reserved'
  → Таймаут-джоб (или ручное действие) может запустить компенсацию
  → Или: Payment Service переподключается и доообрабатывает in-flight сообщение

Сбой 3: Order Service падает после публикации, до ack в outbox
  → Outbox relay повторно публикует (at-least-once)
  → Downstream сервисы получают дублирующее событие
  → Идемпотентные потребители обрабатывают (ON CONFLICT DO NOTHING по order ID)
```

---

## Сценарий 6 — Пул воркеров для CPU-интенсивных задач

Когда есть CPU-интенсивная работа (генерация PDF, компиляция отчётов, экспорт данных), нужны несколько воркеров для параллельной обработки, с очередью в качестве буфера и балансировщика нагрузки.

```ts
// report-service/worker-pool.ts — запускаем N экземпляров

await channel.prefetch(1); // одна тяжёлая задача на воркер одновременно

channel.consume('report-generation', async (msg) => {
  if (!msg) return;

  const job = JSON.parse(msg.content.toString()) as ReportJob;

  console.log(`Воркер ${process.pid} обрабатывает отчёт ${job.reportId}`);

  try {
    // CPU-интенсивная работа — выполняется в процессе этого воркера
    const pdfBuffer = await generatePDFReport(job.params);
    const s3Url = await s3.upload(`reports/${job.reportId}.pdf`, pdfBuffer);

    // Уведомляем инициатора о готовности отчёта
    await db.reports.update(job.reportId, { status: 'ready', url: s3Url });
    await notifyUser(job.userId, s3Url);

    channel.ack(msg);
  } catch (err) {
    channel.nack(msg, false, false);
  }
});

// Масштабирование: docker-compose scale report-worker=5
// RabbitMQ раздаёт задачи по round-robin между 5 воркерами, каждый с prefetch=1
// → 5 отчётов генерируются одновременно, очередь опустошается в 5 раз быстрее
```

**История масштабирования:** При N воркер-процессах, потребляющих из одной очереди, RabbitMQ естественно распределяет работу. Масштабирование — запуск большего числа инстансов, никакого кода координации не требуется.

## Типичные ошибки на интервью

- **"Нужно использовать очередь для всего — так надёжнее"** — очереди добавляют сложность: сериализацию сообщений, жизненный цикл потребителей, идемпотентность, dead-letters, мониторинг. Для простого CRUD API, вызывающего один другой сервис, синхронный HTTP проще и понятнее. Используйте очереди, когда действительно нужна развязка или устойчивость.

- **"Пайплайн заказа выше — антипаттерн микросервисов, потому что сервисы связаны через события"** — связность через события — это слабая связность. Сервисы разделяют схему события (контракт), а не код и не прямые сетевые вызовы. Добавление, удаление или перезапуск сервиса не требует изменений в других. Антипаттерн — общая база данных, не общая шина событий.

- **"Сагу на основе хореографии сложно отлаживать"** — верно, труднее отследить запрос через несколько сервисов и очередей, чем через одну монолитную транзакцию. Ответ — не избегать хореографии, а инвестировать в distributed tracing (correlation ID на каждом сообщении, OpenTelemetry), чтобы отследить конкретный заказ через весь пайплайн.

- **"Использовать очередь для rate limiting — это костыль, нужно починить API-клиент"** — очередь И ЕСТЬ решение. Rate limit внешнего API — ограничение, которое нельзя изменить. Очередь развязывает трафик вашей системы от пропускной способности внешнего API — это именно то, для чего она предназначена.

- **"Фоновым задачам не нужны dead-letter queues — сбои редки"** — сбои случаются в продакшне, особенно при взаимодействии с внешними сервисами. Без DLQ провалившаяся задача тихо теряется. С DLQ провалившиеся задачи видны, можно настроить алерты и воспроизвести после исправления причины.

- **"Хореография vs оркестрация — нужно знать, что лучше"** — оба подхода обоснованы. Оркестрация (центральный координатор саги вызывает каждый сервис по порядку) легче понять и отладить. Хореография (сервисы реагируют на события) масштабируется лучше и не имеет единой точки отказа. Правильный ответ на интервью: "зависит от размера команды, количества сервисов и частоты изменения процесса — я применял оба".
