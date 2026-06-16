<!-- verified: 2026-06-05, corrections: 0 -->
# SQS и Event-Driven Architecture

## Что такое SQS и зачем нужны очереди

SQS (Simple Queue Service) — managed очередь сообщений AWS. Разрывает зависимость между сервисами: producer отправляет сообщение и забывает о нём, consumer обрабатывает независимо.

```txt
Проблема без очереди (tight coupling):
  API → Email Service (синхронно)
  Если Email Service упал → API тоже возвращает ошибку
  Если Email Service медленный → API висит в ожидании
  Если нагрузка растёт → оба сервиса перегружаются вместе

С SQS (loose coupling):
  API → SQS → Email Service
  API: отправил сообщение, получил 200 OK сразу
  Email Service: упал → сообщение остаётся в очереди, retry автоматически
  Email Service медленный → накапливает бэклог, обрабатывает в своём темпе
  Нагрузка → масштабируем consumers независимо
```

## Visibility Timeout и механизм at-least-once delivery

```txt
Жизненный цикл сообщения в SQS:

1. Producer → SQS: SendMessage → сообщение в очереди (visible)
2. Consumer → SQS: ReceiveMessage → сообщение становится invisible
   (Visibility Timeout начинается, default 30 сек)
3. Consumer обрабатывает сообщение...
4a. Успех: Consumer → SQS: DeleteMessage → сообщение удалено
4b. Consumer упал / timeout истёк → сообщение снова visible
    → другой consumer (или тот же) получит его повторно

Важно:
  SQS гарантирует At-Least-Once Delivery (Standard Queue)
  Одно сообщение может быть доставлено БОЛЕЕ одного раза
  → Обработчики должны быть IDEMPOTENT
```

## Standard Queue vs FIFO Queue

```txt
Standard Queue:
  Throughput: неограниченный (virtually unlimited TPS)
  Порядок:    Best-effort ordering (не гарантируется)
  Дубликаты: возможны (At-Least-Once Delivery)
  Когда:     большинство задач: email, notifications, background jobs

FIFO Queue (.fifo suffix):
  Throughput: 3000 сообщений/сек с batching, 300 без
  Порядок:    строгий (First-In-First-Out в рамках MessageGroupId)
  Дубликаты: исключены (Exactly-Once Processing, 5-минутное окно дедупликации)
  Когда:     финансовые транзакции, ordering systems, состояния машин
  
  MessageGroupId: позволяет иметь несколько "потоков" внутри одной FIFO очереди
  DeduplicationId: hash тела сообщения или явный ID для дедупликации
```

## Dead Letter Queue (DLQ)

```txt
Проблема: сообщение постоянно падает при обработке
  → Consumer берёт → exception → Visibility Timeout истекает
  → Снова visible → Consumer берёт снова → exception...
  → Бесконечный цикл, блокирующий очередь

DLQ решение:
  После N попыток (maxReceiveCount) → сообщение переносится в DLQ
  DLQ — обычная SQS очередь, отдельная от основной

Что делать с сообщениями в DLQ:
  - Алерт в CloudWatch → команда получает уведомление
  - Анализ сообщений: что пошло не так?
  - Replay: после исправления бага → перенести обратно в основную очередь
```

## Lambda + SQS — event source mapping

```typescript
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
import { SQSEvent, SQSRecord, SQSBatchResponse } from 'aws-lambda';

const sqs = new SQSClient({ region: process.env.AWS_REGION });

// Producer: отправка сообщения в SQS
async function enqueueEmailJob(userId: string, templateId: string): Promise<void> {
  await sqs.send(new SendMessageCommand({
    QueueUrl: process.env.EMAIL_QUEUE_URL!,
    MessageBody: JSON.stringify({ userId, templateId, timestamp: Date.now() }),
    // Для FIFO очереди:
    // MessageGroupId: userId,         // все сообщения пользователя — один поток
    // MessageDeduplicationId: `${userId}-${templateId}-${Date.now()}`,
  }));
}

// Consumer Lambda: обрабатывает batch сообщений из SQS
export async function handler(event: SQSEvent): Promise<SQSBatchResponse> {
  const failures: string[] = [];

  for (const record of event.Records) {
    try {
      const body = JSON.parse(record.body) as { userId: string; templateId: string };
      await sendEmail(body.userId, body.templateId);
      // Успешно обработано → не нужно явно удалять
      // Lambda Event Source Mapping удаляет успешные автоматически
    } catch (err) {
      console.error(`Failed to process ${record.messageId}:`, err);
      failures.push(record.messageId); // помечаем как failed
    }
  }

  // SQS Batch Item Failures: только упавшие идут в retry / DLQ
  // Остальные из batch удаляются как успешные
  return {
    batchItemFailures: failures.map(id => ({ itemIdentifier: id })),
  };
}
```

```typescript
// CDK: SQS + Lambda с DLQ
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import { Duration } from 'aws-cdk-lib';

const dlq = new sqs.Queue(this, 'EmailDLQ', {
  retentionPeriod: Duration.days(14), // хранить упавшие 14 дней
});

const emailQueue = new sqs.Queue(this, 'EmailQueue', {
  visibilityTimeout: Duration.seconds(30),
  deadLetterQueue: {
    queue: dlq,
    maxReceiveCount: 3, // после 3 попыток → DLQ
  },
});

const emailProcessor = new lambda.Function(this, 'EmailProcessor', {
  runtime: lambda.Runtime.NODEJS_20_X,
  handler: 'index.handler',
  code: lambda.Code.fromAsset('dist/email-processor'),
  timeout: Duration.seconds(25), // < visibilityTimeout!
});

emailProcessor.addEventSource(new lambdaEventSources.SqsEventSource(emailQueue, {
  batchSize: 10,                // обрабатывать до 10 сообщений за раз
  reportBatchItemFailures: true, // включает SQS Batch Item Failures
}));
```

## Idempotency — обязательное требование

```typescript
// Проблема: SQS может доставить сообщение дважды
// Без idempotency: пользователь получит 2 welcome email

// Плохо: не idempotent
async function sendWelcomeEmail(userId: string): Promise<void> {
  await emailService.send(userId, 'welcome');
  // Если вызвать дважды → два письма
}

// Хорошо: idempotent через БД-флаг
async function sendWelcomeEmailIdempotent(userId: string, messageId: string): Promise<void> {
  // Проверить не было ли уже обработано (используем SQS messageId как ключ)
  const alreadyProcessed = await db.processedMessages.findOne({ messageId });
  if (alreadyProcessed) {
    console.log(`Message ${messageId} already processed, skipping`);
    return;
  }

  await emailService.send(userId, 'welcome');
  
  // Сохранить факт обработки (атомарно или в транзакции с основной операцией)
  await db.processedMessages.insert({ messageId, processedAt: new Date() });
}

// В Lambda handler:
export async function handler(event: SQSEvent) {
  for (const record of event.Records) {
    const { userId } = JSON.parse(record.body);
    await sendWelcomeEmailIdempotent(userId, record.messageId);
  }
}
```

## Event-Driven Architecture

```txt
Традиционная (synchronous/tight coupling):
  Order Service → HTTP → Payment Service → HTTP → Inventory → HTTP → Email
  Минус: один упал → весь chain падает
  Минус: нельзя добавить новый consumer без изменения Order Service

Event-Driven (asynchronous/loose coupling):
  Order Service → publish "OrderCreated" event → SQS/SNS/EventBridge
                                                    ↓
                                         Payment Lambda (subscribe)
                                         Inventory Lambda (subscribe)
                                         Email Lambda (subscribe)
                                         Analytics Lambda (subscribe)

Преимущества:
  → Сервисы независимы: упал один → остальные работают
  → Добавить новый consumer → без изменения Order Service
  → Масштабируются независимо
  → Retry и DLQ встроены

Пример реального flow:
  POST /orders
  → Order Service сохраняет в БД, публикует "OrderCreated" в SNS
  → SNS fan-out → SQS_Payment + SQS_Email + SQS_Analytics
  → Lambda_Payment обрабатывает платёж (retry 3x, потом DLQ)
  → Lambda_Email отправляет подтверждение (idempotent)
  → Lambda_Analytics записывает метрику (idempotent)
```

## Типичные ошибки на интервью

- **"SQS удаляет сообщение сразу как отдаёт consumer"** — нет. Сообщение становится invisible на время Visibility Timeout. Только явный вызов `DeleteMessage` (или успешная обработка в Lambda event source mapping) удаляет сообщение. Если consumer упал — сообщение становится видимым снова.

- **"Standard Queue гарантирует порядок, FIFO гарантирует exactly-once"** — наоборот. Standard Queue: нет гарантии порядка, возможны дубликаты. FIFO Queue: гарантирует порядок и exactly-once (в 5-минутном окне дедупликации). Но FIFO имеет ограниченный throughput.

- **"Visibility Timeout нужно устанавливать больше таймаута Lambda"** — нужно устанавливать НЕМНОГО БОЛЬШЕ, чтобы успеть обработать. Но основное правило: `visibilityTimeout > Lambda timeout`. Если Lambda timeout = 25 сек, visibilityTimeout = 30 сек — это нормально. Если `<` — другой consumer может взять сообщение пока текущий ещё обрабатывает.

- **"DLQ не нужна, если есть retry"** — retry без DLQ приводит к бесконечному циклу для poison messages (сообщений с данными, которые всегда вызывают ошибку). DLQ — это изоляция: сломанные сообщения убираются из основного потока без потери данных.

- **"SQS можно использовать для pub/sub (один producer → много consumers)"** — SQS — это point-to-point: одно сообщение получает ровно один consumer. Для fan-out (один event → много consumers) нужен SNS или EventBridge: publish в SNS topic → SNS fan-out → несколько SQS очередей.
