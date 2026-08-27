# SNS and Pub/Sub Architecture

## What is SNS and when to use it

SNS (Simple Notification Service) is a managed Pub/Sub service from AWS (Amazon Web Services). One publisher → one Topic → N subscribers all receive a copy of the message simultaneously. Unlike SQS (Simple Queue Service), which is point-to-point, SNS implements fan-out: one event, many recipients.

The difference shows up as soon as a second consumer appears.

**SQS — point-to-point.** The flow is `Order Service → SQS → one consumer`.

- If the consumer is slow, the message waits in the queue.
- Three consumers mean three separate SQS queues and three separate calls.

**SNS — Pub/Sub.** The flow is `Order Service → SNS Topic → every subscriber gets a copy`.

- Adding a consumer is one action: subscribe it to the Topic.
- Order Service has no knowledge of who the consumers are.

## Topic and subscribers — integration types

Publishing is a single `PublishCommand` against the Topic ARN (Amazon Resource Name). The message attributes you attach here are what subscribers can filter on later.

```typescript
import { SNSClient, PublishCommand } from '@aws-sdk/client-sns';

const sns = new SNSClient({ region: process.env.AWS_REGION });

// Publisher: publish an event
async function publishOrderCreated(order: Order): Promise<void> {
  await sns.send(new PublishCommand({
    TopicArn: process.env.ORDER_TOPIC_ARN!,
    Message: JSON.stringify({
      orderId: order.id,
      userId: order.userId,
      total: order.total,
      items: order.items,
    }),
    Subject: 'OrderCreated', // useful for email subscribers
    MessageAttributes: {     // for SNS Message Filtering
      eventType: { DataType: 'String', StringValue: 'OrderCreated' },
      region: { DataType: 'String', StringValue: 'EU' },
    },
  }));
}
```

A Topic can push to six kinds of subscriber:

| Subscriber | What the Topic delivers to it |
|---|---|
| SQS | Queue receives the message. Most common — adds a buffer and retry. |
| Lambda | Invoked directly — async, no buffer. |
| HTTP/S | A POST to an endpoint (webhooks). |
| Email | An email is sent (for alerts). |
| SMS (Short Message Service) | A text message is sent (for critical alerts). |
| Kinesis | Message goes into a streaming pipeline. |

**SQS or Lambda as the subscriber** is the choice that matters most:

- SQS: buffer, retry, DLQ (dead-letter queue) and batch processing — more reliable.
- Lambda: instant processing, no buffer — if Lambda fails, retry is limited.
- Production default: SNS → SQS → Lambda, double protection.

## Fan-Out Pattern — SNS + SQS

Fan-out means one publish call reaches every interested service. The CDK (Cloud Development Kit) stack below gives each consumer its own queue, so retry, DLQ and scaling stay independent.

```typescript
// CDK: SNS Topic + fan-out to multiple SQS queues
import * as sns from 'aws-cdk-lib/aws-sns';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import { Duration } from 'aws-cdk-lib';

const orderTopic = new sns.Topic(this, 'OrderTopic', {
  topicName: 'order-events',
});

// Each service gets its own SQS queue (independent retry, DLQ, scaling)
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

// Subscribe queues to the topic
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(billingQueue));
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(emailQueue));
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(analyticsQueue));
```

```txt
Fan-Out Pattern flow:
  POST /orders
  → Order Service: save to DB
  → SNS PublishCommand (one call)
       ↓
       ├── SQS_Billing   → Lambda_Billing (payment processing)
       ├── SQS_Email     → Lambda_Email (confirmation email)
       └── SQS_Analytics → Lambda_Analytics (metrics)
```

Three things follow from that shape:

- Order Service makes exactly one call: a single SNS publish.
- Each downstream service: independent retry, DLQ, scaling.
- Adding a new service means subscribing a new SQS queue — Order Service unchanged.

## SNS Message Filtering — selective delivery

Different event types are published to the same Topic. Without filtering, every subscriber receives all of them and has to check the type itself. With a filter policy, SNS delivers only the relevant messages to each subscriber.

```typescript
// CDK: subscription with a filter on MessageAttribute
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

// US billing queue receives only US events
orderTopic.addSubscription(new snsSubscriptions.SqsSubscription(usBillingQueue, {
  filterPolicy: {
    region: sns.SubscriptionFilter.stringFilter({
      allowlist: ['US', 'CA'],
    }),
  },
}));
```

## SNS vs SQS vs EventBridge

All three move events between services. They differ in who receives a message, whether it is stored, and how much routing you get.

**SQS (Simple Queue Service)**

- Pattern: point-to-point, one consumer.
- Storage: stores messages up to 14 days.
- Retry: Visibility Timeout plus DLQ.
- Ordering: Standard is best-effort, FIFO (first in, first out) is strict.
- Use when: tasks that should be processed by a single worker.

**SNS**

- Pattern: Pub/Sub, many subscribers.
- Storage: none — fire-and-forget, and retry is limited.
- Retry: for HTTP, 3 attempts; for SQS and Lambda, reliable.
- Filtering: Message Filtering by attributes.
- Use when: fan-out, domain events, notifications.

**EventBridge**

- Pattern: event bus, routing by event patterns.
- Storage: none.
- Routing: complex rules on JSON content.
- Sources: AWS services, SaaS (Salesforce, Datadog), custom.
- Use when: complex event routing logic, AWS service integration, cron jobs (Scheduled Rules), cross-account events.

A common interview question is "when SNS, when EventBridge?"

- SNS: simple fan-out by event type, filtering by attributes.
- EventBridge: routing by JSON body fields, many rules, cron, SaaS integrations.

## Common interview mistakes

- **"SNS stores messages like SQS does"** — no. SNS is fire-and-forget. If a subscriber is unavailable at publish time — the message is lost (for HTTP endpoints: retry with backoff; for SQS: reliable, since SQS stores). That's exactly why SNS → SQS → Lambda is preferred over SNS → Lambda directly.

- **"SQS and SNS are interchangeable"** — they implement different patterns. SQS = one consumer pulls a message from the queue. SNS = push to all subscribers. Fan-out requires SNS (or EventBridge). For "one worker processes it" — SQS.

- **"SNS Fan-Out adds unnecessary complexity"** — without SNS, notifying 3 services means 3 HTTP calls from the Order Service. That is tight coupling: if one call fails, the Order Service must handle it. With SNS it is one call, and each service retries independently. Adding a 4th service = subscribe it, no changes to the Order Service.

- **"SNS Message Filtering works on the message body"** — no. SNS Message Filtering works only on Message Attributes (metadata), not on the JSON body. For filtering by body content → use EventBridge (supports content-based filtering on JSON fields).

- **"SNS FIFO is the same as SQS FIFO"** — SNS also supports a FIFO Topic (only for SQS FIFO subscribers). But SNS FIFO is strictly limited in throughput. For most fan-out scenarios, a standard SNS Topic is sufficient; ordering is ensured at the level of individual SQS FIFO queues.
