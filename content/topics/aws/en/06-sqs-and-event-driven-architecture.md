# SQS and Event-Driven Architecture

## What is SQS and why queues exist

SQS (Simple Queue Service) is a managed AWS message queue. It decouples services: the producer sends a message and forgets about it; the consumer processes it independently.

```txt
Problem without a queue (tight coupling):
  API → Email Service (synchronous)
  If Email Service crashes → API also returns an error
  If Email Service is slow → API hangs waiting
  If load grows → both services become overloaded together

With SQS (loose coupling):
  API → SQS → Email Service
  API: sent the message, got 200 OK immediately
  Email Service crashes → message stays in the queue, automatic retry
  Email Service is slow → accumulates a backlog, processes at its own pace
  Load increases → scale consumers independently
```

## Visibility Timeout and at-least-once delivery

```txt
Message lifecycle in SQS:

1. Producer → SQS: SendMessage → message in queue (visible)
2. Consumer → SQS: ReceiveMessage → message becomes invisible
   (Visibility Timeout starts, default 30 sec)
3. Consumer processes the message...
4a. Success: Consumer → SQS: DeleteMessage → message deleted
4b. Consumer crashed / timeout expired → message becomes visible again
    → another consumer (or the same) will receive it again

Key point:
  SQS guarantees At-Least-Once Delivery (Standard Queue)
  A message can be delivered MORE than once
  → Handlers must be IDEMPOTENT
```

## Standard Queue vs FIFO Queue

```txt
Standard Queue:
  Throughput: unlimited (virtually unlimited TPS)
  Order:      Best-effort ordering (not guaranteed)
  Duplicates: possible (At-Least-Once Delivery)
  Use when:   most tasks: email, notifications, background jobs

FIFO Queue (.fifo suffix):
  Throughput: 3000 messages/sec with batching, 300 without
  Order:      strict (First-In-First-Out within a MessageGroupId)
  Duplicates: eliminated (Exactly-Once Processing, 5-minute dedup window)
  Use when:   financial transactions, ordering systems, state machines

  MessageGroupId: allows multiple "streams" inside one FIFO queue
  DeduplicationId: hash of message body or explicit ID for deduplication
```

## Dead Letter Queue (DLQ)

```txt
Problem: a message repeatedly fails processing
  → Consumer takes it → exception → Visibility Timeout expires
  → Becomes visible again → Consumer takes it again → exception...
  → Infinite loop, blocking the queue

DLQ solution:
  After N attempts (maxReceiveCount) → message moves to DLQ
  DLQ is a regular SQS queue, separate from the main one

What to do with DLQ messages:
  - CloudWatch alarm → team gets notified
  - Analyze messages: what went wrong?
  - Replay: after fixing the bug → move back to the main queue
```

## Lambda + SQS — event source mapping

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

```typescript
// Problem: SQS may deliver a message twice
// Without idempotency: user receives 2 welcome emails

// Bad: not idempotent
async function sendWelcomeEmail(userId: string): Promise<void> {
  await emailService.send(userId, 'welcome');
  // Called twice → two emails
}

// Good: idempotent via DB flag
async function sendWelcomeEmailIdempotent(userId: string, messageId: string): Promise<void> {
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

```txt
Traditional (synchronous / tight coupling):
  Order Service → HTTP → Payment Service → HTTP → Inventory → HTTP → Email
  Downside: one fails → the whole chain fails
  Downside: adding a new consumer requires changing Order Service

Event-Driven (asynchronous / loose coupling):
  Order Service → publish "OrderCreated" event → SQS/SNS/EventBridge
                                                     ↓
                                          Payment Lambda (subscribe)
                                          Inventory Lambda (subscribe)
                                          Email Lambda (subscribe)
                                          Analytics Lambda (subscribe)

Benefits:
  → Services are independent: one fails → the rest keep running
  → Add a new consumer → no changes to Order Service
  → Scale independently
  → Retry and DLQ are built in

Real-world flow example:
  POST /orders
  → Order Service saves to DB, publishes "OrderCreated" to SNS
  → SNS fan-out → SQS_Payment + SQS_Email + SQS_Analytics
  → Lambda_Payment processes payment (retry 3x, then DLQ)
  → Lambda_Email sends confirmation (idempotent)
  → Lambda_Analytics records metric (idempotent)
```

## Common interview mistakes

- **"SQS deletes a message as soon as it delivers it to the consumer"** — no. The message becomes invisible for the duration of the Visibility Timeout. Only an explicit `DeleteMessage` call (or successful processing in the Lambda event source mapping) deletes it. If the consumer crashes — the message becomes visible again.

- **"Standard Queue guarantees order; FIFO guarantees exactly-once"** — the opposite. Standard Queue: no order guarantee, duplicates possible. FIFO Queue: guarantees order and exactly-once (within a 5-minute deduplication window). But FIFO has limited throughput.

- **"Visibility Timeout should be set larger than the Lambda timeout"** — it should be set slightly larger so processing has time to complete. The core rule: `visibilityTimeout > Lambda timeout`. If Lambda timeout = 25s, visibilityTimeout = 30s — that's fine. If `<` — another consumer can pick up the message while the current one is still processing.

- **"DLQ is unnecessary if there's retry"** — retry without DLQ leads to an infinite loop for poison messages (messages with data that always cause an error). DLQ is isolation: broken messages are removed from the main flow without losing data.

- **"SQS can be used for pub/sub (one producer → many consumers)"** — SQS is point-to-point: exactly one consumer receives each message. For fan-out (one event → many consumers), use SNS or EventBridge: publish to an SNS topic → SNS fan-out → multiple SQS queues.
