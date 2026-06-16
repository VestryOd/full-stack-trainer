<!-- verified: 2026-06-05, corrections: 0 -->
# SNS и Pub/Sub Architecture

## Что такое SNS и когда он нужен

SNS (Simple Notification Service) — managed Pub/Sub сервис AWS. Один publisher → один Topic → N subscribers получают копию сообщения одновременно. В отличие от SQS (point-to-point), SNS реализует fan-out: одно событие, много получателей.

```txt
SQS (Point-to-Point):
  Order Service → SQS → один Consumer
  Если Consumer медленный → сообщение ждёт в очереди
  Если нужны 3 Consumer → 3 разных SQS очереди → 3 отдельных вызова

SNS (Pub/Sub):
  Order Service → SNS Topic → все подписчики получают копию
  Добавить нового потребителя → просто подписать его на Topic
  Order Service не знает о существовании конкретных потребителей
```

## Topic и подписчики — типы интеграций

```typescript
import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';

const sns = new SNSClient({ region: process.env.AWS_REGION });

// Publisher: публикация события
async function publishOrderCreated(order: Order): Promise<void> {
  await sns.send(new PublishCommand({
    TopicArn: process.env.ORDER_TOPIC_ARN!,
    Message: JSON.stringify({
      orderId: order.id,
      userId: order.userId,
      total: order.total,
      items: order.items,
    }),
    Subject: 'OrderCreated', // полезно для email подписчиков
    MessageAttributes: {     // для SNS Message Filtering
      eventType: { DataType: 'String', StringValue: 'OrderCreated' },
      region: { DataType: 'String', StringValue: 'EU' },
    },
  }));
}
```

```txt
Типы подписчиков SNS:
  SQS      → queue получает сообщение (most common, добавляет буфер + retry)
  Lambda   → вызывается напрямую (асинхронно, без буфера)
  HTTP/S   → POST на endpoint (webhooks)
  Email    → отправляется письмо (для алертов)
  SMS      → отправляется СМС (для критических алертов)
  Kinesis  → стриминг pipeline

SQS vs Lambda как subscriber:
  SQS:    буфер + retry + DLQ + batch processing → надёжнее
  Lambda: мгновенная обработка, нет буфера → если Lambda упала, retry ограничен
  Production: SNS → SQS → Lambda (двойная защита)
```

## Fan-Out Pattern — SNS + SQS

```typescript
// CDK: SNS Topic + fan-out в несколько SQS
import * as sns from 'aws-cdk-lib/aws-sns';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import { Duration } from 'aws-cdk-lib';

const orderTopic = new sns.Topic(this, 'OrderTopic', {
  topicName: 'order-events',
});

// Каждый сервис — своя SQS очередь (независимые retry, DLQ, масштабирование)
const billingDlq = new sqs.Queue(this, 'BillingDLQ');
const billingQueue = new sqs.Queue(this, 'BillingQueue', {
  deadLetterQueue: { queue: billingDlq, maxReceiveCount: 3 },
  visibilityTimeout: Duration.seconds(30),
});

const emailDlq = new sqs.Queue(this, 'EmailDLQ');
const emailQueue = new sqs.Queue(this, 'EmailQueue', {
  deadLetterQueue: { queue: emailDlq, maxReceiveCount: 3 },
});

const analyticsDlq = new sqs.Queue(this, 'AnalyticsDLQ');
const analyticsQueue = new sqs.Queue(this, 'AnalyticsQueue', {
  deadLetterQueue: { queue: analyticsDlq, maxReceiveCount: 5 },
});

// Подписка очередей на topic
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(billingQueue));
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(emailQueue));
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(analyticsQueue));
```

```txt
Flow Fan-Out Pattern:
  POST /orders
  → Order Service: save to DB
  → SNS PublishCommand (один вызов)
       ↓
       ├── SQS_Billing → Lambda_Billing (payment processing)
       ├── SQS_Email   → Lambda_Email (confirmation email)
       └── SQS_Analytics → Lambda_Analytics (metrics)

Преимущества:
  Order Service делает ОДИН вызов (SNS Publish)
  Каждый downstream сервис: независимый retry, DLQ, масштабирование
  Добавить новый сервис → подписать новую SQS → Order Service не трогать
```

## SNS Message Filtering — избирательная доставка

```typescript
// Проблема: в Topic приходят разные типы событий
// Без фильтрации: каждый subscriber получает ВСЁ → сам проверяет тип
// С фильтрацией: SNS доставляет subscriber только нужные сообщения

// CDK: подписка с фильтром по MessageAttribute
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(euBillingQueue, {
  filterPolicy: {
    region: sns.SubscriptionFilter.stringFilter({
      allowlist: ['EU', 'UK'],
    }),
    eventType: sns.SubscriptionFilter.stringFilter({
      allowlist: ['OrderCreated', 'OrderUpdated'],
    }),
  },
}));

// US billing queue получает только US события
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(usBillingQueue, {
  filterPolicy: {
    region: sns.SubscriptionFilter.stringFilter({
      allowlist: ['US', 'CA'],
    }),
  },
}));
```

## SNS vs SQS vs EventBridge

```txt
SQS (Simple Queue Service):
  Паттерн:    Point-to-Point (один consumer)
  Хранение:   сохраняет сообщения до 14 дней
  Retry:      Visibility Timeout + DLQ
  Ordering:   Standard (best-effort) / FIFO (strict)
  Когда:      задачи, которые должен выполнить один worker

SNS (Simple Notification Service):
  Паттерн:    Pub/Sub (много subscribers)
  Хранение:   не хранит (fire-and-forget, retry ограничен)
  Retry:      для HTTP: 3 попытки; для SQS/Lambda: надёжнее
  Filtering:  Message Filtering по атрибутам
  Когда:      fan-out, domain events, notifications

EventBridge:
  Паттерн:    Event Bus (routing по event patterns)
  Хранение:   не хранит
  Routing:    сложные rules по содержимому JSON
  Sources:    AWS сервисы, SaaS (Salesforce, Datadog), custom
  Когда:      сложная event routing логика, интеграция с AWS сервисами,
              cron jobs (Scheduled Rules), cross-account events

Частый вопрос: "Когда SNS, когда EventBridge?"
  SNS: простой fan-out по типу события, фильтрация по атрибутам
  EventBridge: routing по полям JSON тела, много rules, cron, SaaS интеграции
```

## Типичные ошибки на интервью

- **"SNS хранит сообщения как SQS"** — нет. SNS — fire-and-forget. Если subscriber недоступен в момент публикации — сообщение теряется (для HTTP endpoints — retry с backoff, для SQS — надёжно, так как SQS хранит). Именно поэтому SNS → SQS → Lambda предпочтительнее SNS → Lambda напрямую.

- **"SQS и SNS — взаимозаменяемы"** — разные паттерны. SQS = один consumer берёт сообщение из очереди (pull). SNS = push ко всем подписчикам. Для fan-out нужен SNS (или EventBridge). Для задачи "один worker обрабатывает" — SQS.

- **"SNS Fan-Out усложняет архитектуру без причины"** — без SNS, для уведомления 3 сервисов Order Service делает 3 HTTP вызова: жёсткая связанность, если один упал — нужна обработка в Order Service. С SNS: один вызов + каждый сервис независимо с retry. Добавить 4-й сервис = подписать его, без изменений в Order Service.

- **"Message Filtering в SNS работает по телу сообщения"** — нет. SNS Message Filtering работает только по Message Attributes (метаданные), не по телу JSON. Для фильтрации по содержимому тела → использовать EventBridge (поддерживает Content-based filtering по JSON полям).

- **"SNS FIFO и Standard — это как SQS FIFO"** — SNS тоже поддерживает FIFO Topic (только для SQS FIFO подписчиков). Но SNS FIFO строго ограничен по throughput. В большинстве fan-out сценариев стандартный SNS Topic достаточен, порядок обеспечивается на уровне отдельных SQS FIFO очередей.
