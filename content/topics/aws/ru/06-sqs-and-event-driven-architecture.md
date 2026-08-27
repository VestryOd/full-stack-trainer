<!-- verified: 2026-06-05, corrections: 0 -->
# SQS и Event-Driven Architecture

## Что такое SQS и зачем нужны очереди

SQS (Simple Queue Service) — управляемая очередь сообщений AWS (Amazon Web Services). Она разрывает зависимость между сервисами: отправитель кладёт сообщение и забывает о нём, получатель обрабатывает его независимо.

**Без очереди сервисы связаны жёстко.** API вызывает Email Service синхронно, и любой сбой одного становится сбоем другого:

- Если Email Service упал, API тоже возвращает ошибку.
- Если Email Service медленный, API висит в ожидании.
- Если нагрузка растёт, перегружаются оба сервиса сразу.

**С SQS между ними связь слабая.** API пишет в очередь, а Email Service читает из неё в своём темпе:

- API отправил сообщение и сразу получил `200 OK`.
- Если Email Service упал, сообщение остаётся в очереди и повторяется автоматически.
- Если Email Service медленный, копится бэклог, а он разбирает его в своём темпе.
- Если нагрузка растёт, получателей вы масштабируете отдельно.

## Visibility Timeout и механизм at-least-once delivery

Чтение сообщения не блокирует его и не удаляет. SQS всего лишь прячет его на время, и именно из этого решения растёт доставка «минимум один раз».

Жизненный цикл одного сообщения:

1. Отправитель вызывает `SendMessage`, и сообщение лежит в очереди видимым.
2. Получатель вызывает `ReceiveMessage`, и сообщение становится невидимым. Отсюда начинается Visibility Timeout, по умолчанию 30 секунд.
3. Получатель обрабатывает сообщение.
4. При успехе получатель вызывает `DeleteMessage`, и сообщение удаляется.
5. Если получатель упал или таймаут истёк раньше, сообщение снова становится видимым. Его получит другой получатель или тот же самый.

Главное: SQS гарантирует At-Least-Once Delivery на Standard Queue. Одно сообщение может быть доставлено **более** одного раза, поэтому обработчики обязаны быть **идемпотентными**.

## Standard Queue vs FIFO Queue

FIFO расшифровывается как first-in-first-out, и ровно эта гарантия порядка стоит вам пропускной способности. Два типа очередей меняют одно на другое.

**Standard Queue**

- Пропускная способность: неограниченная, практически любое число операций в секунду.
- Порядок: best-effort, не гарантируется.
- Дубликаты: возможны, потому что доставка идёт минимум один раз.
- Когда: большинство задач — письма, уведомления, фоновые задания.

**FIFO Queue (суффикс `.fifo`)**

- Пропускная способность: 3000 сообщений в секунду с батчингом, 300 без него.
- Порядок: строгий, first-in-first-out в рамках одного `MessageGroupId`.
- Дубликаты: исключены — exactly-once processing с пятиминутным окном дедупликации.
- Когда: финансовые транзакции, системы с гарантией порядка, конечные автоматы.

Управляют FIFO-очередью два идентификатора. `MessageGroupId` позволяет держать в одной очереди несколько независимых «потоков», и каждый сохраняет свой порядок. `DeduplicationId` — это хэш тела сообщения или явный id, который вы задаёте сами.

## Dead Letter Queue (DLQ)

DLQ — это место, куда уходят сообщения, которые уже никогда не обработаются. Без неё одно испорченное сообщение крутится вечно и держит всю очередь за собой.

**Проблема: сообщение постоянно падает при обработке**

1. Получатель берёт его и падает с исключением.
2. Visibility Timeout истекает, и сообщение снова становится видимым.
3. Его берёт другой получатель и снова падает.
4. Цикл бесконечный, и он блокирует очередь.

**Решение через DLQ**

После N попыток, которые считает `maxReceiveCount`, сообщение переносится в DLQ. DLQ — обычная очередь SQS, отдельная от основной.

**Что делать с тем, что там осело**

- Поднять алерт в CloudWatch, чтобы команда получила уведомление.
- Разобрать сообщения: что именно пошло не так?
- Переиграть их: после исправления бага перенести обратно в основную очередь.

## Lambda + SQS — event source mapping

Event source mapping заставляет Lambda опрашивать очередь за вас, поэтому цикла `ReceiveMessage` в вашем коде нет. Первый сниппет — отправитель и получатель, второй связывает очередь, DLQ и функцию в CDK (Cloud Development Kit).

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

Раз SQS может доставить одно сообщение дважды, неидемпотентный обработчик отправит два приветственных письма. Лечится это так: запоминаем `messageId` всего обработанного и пропускаем повторы.

```typescript
// Проблема: SQS может доставить сообщение дважды
// Без idempotency: пользователь получит 2 welcome email

// Плохо: не idempotent
async function sendWelcomeEmail(userId: string): Promise<void> {
  await emailService.send(userId, 'welcome');
  // Если вызвать дважды → два письма
}

// Хорошо: idempotent через БД-флаг
async function sendWelcomeEmailIdempotent(
  userId: string,
  messageId: string,
): Promise<void> {
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

Разница между двумя стилями в том, кто про кого обязан знать. В синхронной цепочке каждый сервис знает следующего по имени. В событийной версии издатель не знает своих подписчиков вообще.

**Традиционная: синхронная, жёсткая связь**

`Order Service → HTTP → Payment Service → HTTP → Inventory → HTTP → Email`

- Один сервис упал — падает вся цепочка.
- Нового получателя не добавить без изменения Order Service.

**Событийная: асинхронная, слабая связь**

Order Service публикует событие `OrderCreated` в SQS, SNS (Simple Notification Service) или EventBridge, а независимые потребители на него подписываются:

- Payment Lambda.
- Inventory Lambda.
- Email Lambda.
- Analytics Lambda.

Что это даёт:

- Сервисы независимы: один упал, остальные работают.
- Новый получатель добавляется без изменений в Order Service.
- Каждый масштабируется отдельно.
- Повторы и DLQ встроены.

**Реальный поток от начала до конца**

1. Приходит `POST /orders`.
2. Order Service сохраняет заказ в базу и публикует `OrderCreated` в SNS.
3. SNS раздаёт событие в `SQS_Payment`, `SQS_Email` и `SQS_Analytics`.
4. `Lambda_Payment` проводит платёж, повторяя 3 раза, а потом уходит в DLQ.
5. `Lambda_Email` отправляет подтверждение, идемпотентно.
6. `Lambda_Analytics` записывает метрику, идемпотентно.

## Типичные ошибки на интервью

- **«SQS удаляет сообщение сразу, как отдал его получателю»** — нет. Сообщение становится невидимым на время Visibility Timeout. Удаляет его только явный вызов `DeleteMessage` или успешная обработка в Lambda event source mapping. Если получатель упал, сообщение снова становится видимым.

- **«Standard Queue гарантирует порядок, FIFO гарантирует exactly-once»** — всё наоборот. Standard Queue не гарантирует порядок, и дубликаты в ней возможны. FIFO Queue гарантирует и порядок, и exactly-once в пятиминутном окне дедупликации. Зато пропускная способность у FIFO ограничена.

- **«Visibility Timeout нужно устанавливать больше таймаута Lambda»** — да, но **немного** больше, чтобы обработка успела завершиться. Основное правило: `visibilityTimeout > Lambda timeout`. Если таймаут Lambda 25 секунд, а visibilityTimeout 30 секунд — это нормально. Если наоборот, другой получатель заберёт сообщение, пока текущий ещё его обрабатывает.

- **«DLQ не нужна, если есть retry»** — повторы без DLQ приводят к бесконечному циклу на «ядовитых» сообщениях (poison messages), то есть на данных, которые всегда вызывают ошибку. DLQ — это изоляция: сломанные сообщения уходят из основного потока, и при этом не теряются.

- **«SQS можно использовать для pub/sub, один отправитель на много получателей»** — SQS работает точка-точка: каждое сообщение получает ровно один потребитель. Для веерной рассылки, когда одно событие уходит многим, нужен SNS или EventBridge. Схема такая: публикация в топик SNS, оттуда веерная рассылка в несколько очередей SQS.
