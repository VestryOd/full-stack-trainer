<!-- verified: 2026-06-05, corrections: 0 -->
# SNS и Pub/Sub Architecture

## Что такое SNS и когда он нужен

SNS (Simple Notification Service) — управляемый сервис Pub/Sub от AWS (Amazon Web Services). Один издатель → один Topic → N подписчиков получают копию сообщения одновременно. В отличие от SQS (Simple Queue Service), который работает по схеме «точка-точка» (point-to-point), SNS реализует fan-out: одно событие, много получателей.

Разница видна сразу, как только появляется второй потребитель.

**SQS — точка-точка.** Поток такой: `Order Service → SQS → один потребитель`.

- Если потребитель медленный, сообщение ждёт в очереди.
- Три потребителя — это три разные очереди SQS и три отдельных вызова.

**SNS — Pub/Sub.** Поток такой: `Order Service → SNS Topic → копию получает каждый подписчик`.

- Добавить потребителя — одно действие: подписать его на Topic.
- Order Service не знает о существовании конкретных потребителей.

## Topic и подписчики — типы интеграций

Публикация — это один вызов `PublishCommand` в Topic ARN (Amazon Resource Name — уникальный идентификатор ресурса AWS). Атрибуты сообщения, которые вы прикрепляете здесь, — это то, по чему подписчики потом фильтруют.

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

Topic умеет доставлять в шесть типов подписчиков:

| Подписчик | Что он получает от Topic |
|---|---|
| SQS | Сообщение попадает в очередь. Самый частый вариант — добавляет буфер и повторы. |
| Lambda | Функция вызывается напрямую — асинхронно, без буфера. |
| HTTP/S | POST на endpoint (вебхуки). |
| Email | Отправляется письмо (для алертов). |
| SMS (Short Message Service) | Отправляется текстовое сообщение на телефон (для критических алертов). |
| Kinesis | Сообщение уходит в стриминговый конвейер (streaming pipeline). |

**SQS или Lambda как подписчик** — это главный выбор здесь:

- SQS: буфер, повторы, DLQ (dead-letter queue — очередь необработанных сообщений), пакетная обработка — надёжнее.
- Lambda: мгновенная обработка без буфера — если Lambda упала, повторы ограничены.
- Стандарт для production: SNS → SQS → Lambda, двойная защита.

## Fan-Out Pattern — SNS + SQS

Fan-out означает, что один вызов публикации доходит до каждого заинтересованного сервиса. Стек CDK (Cloud Development Kit) ниже даёт каждому потребителю свою очередь, поэтому повторы, DLQ и масштабирование независимы.

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
```

Из этой схемы следуют три вещи:

- Order Service делает ровно один вызов: одну публикацию в SNS.
- У каждого сервиса-потребителя свои повторы, DLQ и масштабирование.
- Добавить новый сервис — подписать новую очередь SQS, Order Service не трогаем.

## SNS Message Filtering — избирательная доставка

В один Topic приходят разные типы событий. Без фильтрации каждый подписчик получает их все и сам проверяет тип. С фильтром SNS доставляет подписчику только нужные сообщения.

```typescript
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

Все три переносят события между сервисами. Разница в том, кто получает сообщение, хранится ли оно и сколько маршрутизации вам достаётся.

**SQS (Simple Queue Service)**

- Паттерн: точка-точка, один потребитель.
- Хранение: сохраняет сообщения до 14 дней.
- Повторы: Visibility Timeout плюс DLQ.
- Порядок: Standard — по возможности, FIFO (first in, first out) — строгий.
- Когда: задачи, которые должен выполнить один worker.

**SNS**

- Паттерн: Pub/Sub, много подписчиков.
- Хранение: не хранит — fire-and-forget, повторы ограничены.
- Повторы: для HTTP 3 попытки; для SQS и Lambda надёжнее.
- Фильтрация: Message Filtering по атрибутам.
- Когда: fan-out, доменные события, уведомления.

**EventBridge**

- Паттерн: шина событий, маршрутизация по шаблонам событий.
- Хранение: не хранит.
- Маршрутизация: сложные правила по содержимому JSON.
- Источники: сервисы AWS, SaaS (Salesforce, Datadog), свои события.
- Когда: сложная логика маршрутизации, интеграция с сервисами AWS, задачи по расписанию (Scheduled Rules), события между аккаунтами.

Частый вопрос на собеседовании: «Когда SNS, а когда EventBridge?»

- SNS: простой fan-out по типу события, фильтрация по атрибутам.
- EventBridge: маршрутизация по полям тела JSON, много правил, cron, интеграции с SaaS.

## Типичные ошибки на интервью

- **"SNS хранит сообщения как SQS"** — нет. SNS — fire-and-forget. Если subscriber недоступен в момент публикации — сообщение теряется (для HTTP endpoints — retry с backoff, для SQS — надёжно, так как SQS хранит). Именно поэтому SNS → SQS → Lambda предпочтительнее SNS → Lambda напрямую.

- **"SQS и SNS — взаимозаменяемы"** — разные паттерны. SQS = один consumer берёт сообщение из очереди (pull). SNS = push ко всем подписчикам. Для fan-out нужен SNS (или EventBridge). Для задачи "один worker обрабатывает" — SQS.

- **"SNS Fan-Out усложняет архитектуру без причины"** — без SNS, для уведомления 3 сервисов Order Service делает 3 HTTP вызова: жёсткая связанность, если один упал — нужна обработка в Order Service. С SNS: один вызов + каждый сервис независимо с retry. Добавить 4-й сервис = подписать его, без изменений в Order Service.

- **"Message Filtering в SNS работает по телу сообщения"** — нет. SNS Message Filtering работает только по Message Attributes (метаданные), не по телу JSON. Для фильтрации по содержимому тела → использовать EventBridge (поддерживает Content-based filtering по JSON полям).

- **"SNS FIFO и Standard — это как SQS FIFO"** — SNS тоже поддерживает FIFO Topic (только для SQS FIFO подписчиков). Но SNS FIFO строго ограничен по throughput. В большинстве fan-out сценариев стандартный SNS Topic достаточен, порядок обеспечивается на уровне отдельных SQS FIFO очередей.
