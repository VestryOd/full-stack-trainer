# SQS and Event-Driven Architecture

## What is SQS and why queues exist

SQS (Simple Queue Service) is the managed message queue of AWS (Amazon Web Services). It decouples services: the producer sends a message and forgets about it; the consumer processes it independently.

**Without a queue the two services are tightly coupled.** The API calls the Email Service synchronously, and every failure of one becomes a failure of the other:

- If the Email Service crashes, the API returns an error too.
- If the Email Service is slow, the API hangs waiting for it.
- If load grows, both services get overloaded together.

**With SQS between them the coupling is loose.** The API writes to the queue and the Email Service reads from it at its own speed:

- The API sends the message and gets `200 OK` immediately.
- If the Email Service crashes, the message stays in the queue and is retried automatically.
- If the Email Service is slow, a backlog accumulates and it processes at its own pace.
- If load grows, you scale the consumers independently.

## Visibility Timeout and at-least-once delivery

Reading a message neither locks it nor deletes it. SQS only hides it for a while, and that single design choice is what makes at-least-once delivery unavoidable.

The lifecycle of one message:

1. The producer calls `SendMessage`, and the message sits in the queue, visible.
2. A consumer calls `ReceiveMessage`, and the message becomes invisible. The Visibility Timeout starts here, 30 seconds by default.
3. The consumer processes the message.
4. On success the consumer calls `DeleteMessage`, and the message is deleted.
5. If the consumer crashes, or the timeout expires first, the message becomes visible again. Another consumer, or the same one, will receive it again.

Key point: SQS guarantees At-Least-Once Delivery on a Standard Queue. One message can be delivered **more** than once, so handlers must be **idempotent**.

## Standard Queue vs FIFO Queue

FIFO stands for first-in-first-out, and that ordering guarantee is exactly what costs you throughput. The two queue types trade one against the other.

**Standard Queue**

- Throughput: unlimited, or virtually unlimited transactions per second.
- Order: best-effort ordering, not guaranteed.
- Duplicates: possible, because delivery is at-least-once.
- Use for most tasks: email, notifications, background jobs.

**FIFO Queue (the `.fifo` suffix)**

- Throughput: 3000 messages per second with batching, 300 without.
- Order: strict, first-in-first-out within one `MessageGroupId`.
- Duplicates: eliminated — exactly-once processing, with a 5-minute deduplication window.
- Use for financial transactions, ordering systems, state machines.

Two identifiers steer a FIFO queue. `MessageGroupId` lets several independent "streams" live inside one queue, each keeping its own order. `DeduplicationId` is a hash of the message body, or an explicit id you supply for deduplication.

## Dead Letter Queue (DLQ)

A DLQ is where messages go when they will never succeed. Without one, a single bad message loops forever and blocks everything behind it.

**The problem: a message that repeatedly fails processing**

1. A consumer takes it and throws an exception.
2. The Visibility Timeout expires and the message becomes visible again.
3. Another consumer takes it and throws again.
4. The loop is infinite, and it blocks the queue.

**The DLQ solution**

After N attempts, counted by `maxReceiveCount`, the message is moved to the DLQ. The DLQ is an ordinary SQS queue, separate from the main one.

**What to do with the messages that land there**

- Raise a CloudWatch alarm, so the team gets notified.
- Analyze the messages: what went wrong?
- Replay them — after the bug is fixed, move them back to the main queue.

## Lambda + SQS — event source mapping

Event source mapping makes Lambda poll the queue for you, so no `ReceiveMessage` loop appears in your code. The first snippet is the producer and the consumer; the second wires a queue, a DLQ and the function together in CDK (Cloud Development Kit).

```typescript
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
import { SQSEvent, SQSBatchResponse } from 'aws-lambda';

const sqs = new SQSClient({ region: process.env.AWS_REGION });

// Producer: send message to SQS
async function enqueueEmailJob(userId: string, templateId: string): Promise<void> {
  await sqs.send(new SendMessageCommand({
    QueueUrl: process.env.EMAIL_QUEUE_URL!,
    MessageBody: JSON.stringify({ userId, templateId, timestamp: Date.now() }),
    // For FIFO queue:
    // MessageGroupId: userId,         // all messages from user → one stream
    // MessageDeduplicationId: `${userId}-${templateId}-${Date.now()}`,
  }));
}

// Consumer Lambda: processes a batch of SQS messages
export async function handler(event: SQSEvent): Promise<SQSBatchResponse> {
  const failures: string[] = [];

  for (const record of event.Records) {
    try {
      const body = JSON.parse(record.body) as { userId: string; templateId: string };
      await sendEmail(body.userId, body.templateId);
      // Successfully processed → no need to explicitly delete
      // Lambda Event Source Mapping deletes successful items automatically
    } catch (err) {
      console.error(`Failed to process ${record.messageId}:`, err);
      failures.push(record.messageId); // mark as failed
    }
  }

  // SQS Batch Item Failures: only failed items go to retry / DLQ
  // The rest of the batch is deleted as successful
  return {
    batchItemFailures: failures.map(id => ({ itemIdentifier: id })),
  };
}
```

```typescript
// CDK: SQS + Lambda with DLQ
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import { Duration } from 'aws-cdk-lib';

const dlq = new sqs.Queue(this, 'EmailDLQ', {
  retentionPeriod: Duration.days(14), // keep failed messages for 14 days
});

const emailQueue = new sqs.Queue(this, 'EmailQueue', {
  visibilityTimeout: Duration.seconds(30),
  deadLetterQueue: {
    queue: dlq,
    maxReceiveCount: 3, // after 3 attempts → DLQ
  },
});

const emailProcessor = new lambda.Function(this, 'EmailProcessor', {
  runtime: lambda.Runtime.NODEJS_20_X,
  handler: 'index.handler',
  code: lambda.Code.fromAsset('dist/email-processor'),
  timeout: Duration.seconds(25), // < visibilityTimeout!
});

emailProcessor.addEventSource(new lambdaEventSources.SqsEventSource(emailQueue, {
  batchSize: 10,                 // process up to 10 messages at a time
  reportBatchItemFailures: true,  // enables SQS Batch Item Failures
}));
```

## Idempotency — a mandatory requirement

Because SQS can deliver the same message twice, a handler that is not idempotent sends two welcome emails. The fix is to record the `messageId` of everything already processed and skip the repeats.

```typescript
// Problem: SQS may deliver a message twice
// Without idempotency: user receives 2 welcome emails

// Bad: not idempotent
async function sendWelcomeEmail(userId: string): Promise<void> {
  await emailService.send(userId, 'welcome');
  // Called twice → two emails
}

// Good: idempotent via DB flag
async function sendWelcomeEmailIdempotent(
  userId: string,
  messageId: string,
): Promise<void> {
  // Check if already processed (use SQS messageId as the key)
  const alreadyProcessed = await db.processedMessages.findOne({ messageId });
  if (alreadyProcessed) {
    console.log(`Message ${messageId} already processed, skipping`);
    return;
  }

  await emailService.send(userId, 'welcome');

  // Save proof of processing (atomically or in a transaction with the main operation)
  await db.processedMessages.insert({ messageId, processedAt: new Date() });
}

// In the Lambda handler:
export async function handler(event: SQSEvent) {
  for (const record of event.Records) {
    const { userId } = JSON.parse(record.body);
    await sendWelcomeEmailIdempotent(userId, record.messageId);
  }
}
```

## Event-Driven Architecture

The difference between the two styles is who has to know about whom. In a synchronous chain every service knows its successor by name. In the event-driven version the publisher knows none of its subscribers.

**Traditional: synchronous, tight coupling**

`Order Service → HTTP → Payment Service → HTTP → Inventory → HTTP → Email`

- One service fails and the whole chain fails.
- Adding a new consumer requires changing Order Service.

**Event-driven: asynchronous, loose coupling**

Order Service publishes an `OrderCreated` event to SQS, SNS (Simple Notification Service) or EventBridge, and independent consumers subscribe to it:

- Payment Lambda.
- Inventory Lambda.
- Email Lambda.
- Analytics Lambda.

What that buys you:

- Services are independent: one fails, the rest keep running.
- A new consumer is added with no changes to Order Service.
- Each consumer scales independently.
- Retry and DLQ are built in.

**A real-world flow, end to end**

1. `POST /orders` arrives.
2. Order Service saves the order to the database and publishes `OrderCreated` to SNS.
3. SNS fans out to `SQS_Payment`, `SQS_Email` and `SQS_Analytics`.
4. `Lambda_Payment` processes the payment, retrying 3 times and then falling through to the DLQ.
5. `Lambda_Email` sends the confirmation, idempotently.
6. `Lambda_Analytics` records a metric, idempotently.

## Common interview mistakes

- **"SQS deletes a message as soon as it delivers it to the consumer"** — no. The message becomes invisible for the duration of the Visibility Timeout. Only an explicit `DeleteMessage` call (or successful processing in the Lambda event source mapping) deletes it. If the consumer crashes — the message becomes visible again.

- **"Standard Queue guarantees order; FIFO guarantees exactly-once"** — the opposite. Standard Queue: no order guarantee, duplicates possible. FIFO Queue: guarantees order and exactly-once (within a 5-minute deduplication window). But FIFO has limited throughput.

- **"Visibility Timeout should be set larger than the Lambda timeout"** — it should be set slightly larger so processing has time to complete. The core rule: `visibilityTimeout > Lambda timeout`. If Lambda timeout = 25s, visibilityTimeout = 30s — that's fine. If `<` — another consumer can pick up the message while the current one is still processing.

- **"DLQ is unnecessary if there's retry"** — retry without DLQ leads to an infinite loop for poison messages (messages with data that always cause an error). DLQ is isolation: broken messages are removed from the main flow without losing data.

- **"SQS can be used for pub/sub (one producer → many consumers)"** — SQS is point-to-point: exactly one consumer receives each message. For fan-out (one event → many consumers), use SNS or EventBridge: publish to an SNS topic → SNS fan-out → multiple SQS queues.
