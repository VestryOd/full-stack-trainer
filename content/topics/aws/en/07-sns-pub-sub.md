# SNS and Pub/Sub Architecture

## What is SNS and when to use it

SNS (Simple Notification Service) is a managed AWS Pub/Sub service. One publisher → one Topic → N subscribers all receive a copy of the message simultaneously. Unlike SQS (point-to-point), SNS implements fan-out: one event, many recipients.

```txt
SQS (Point-to-Point):
  Order Service → SQS → one Consumer
  If Consumer is slow → message waits in the queue
  If 3 Consumers are needed → 3 separate SQS queues → 3 separate calls

SNS (Pub/Sub):
  Order Service → SNS Topic → all subscribers receive a copy
  Add a new consumer → just subscribe it to the Topic
  Order Service has no knowledge of who the consumers are
```

## Topic and subscribers — integration types

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

```txt
SNS subscriber types:
  SQS      → queue receives the message (most common, adds buffer + retry)
  Lambda   → invoked directly (async, no buffer)
  HTTP/S   → POST to an endpoint (webhooks)
  Email    → email is sent (for alerts)
  SMS      → SMS is sent (for critical alerts)
  Kinesis  → streaming pipeline

SQS vs Lambda as subscriber:
  SQS:    buffer + retry + DLQ + batch processing → more reliable
  Lambda: instant processing, no buffer → if Lambda fails, retry is limited
  Production: SNS → SQS → Lambda (double protection)
```

## Fan-Out Pattern — SNS + SQS

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

Benefits:
  Order Service makes ONE call (SNS Publish)
  Each downstream service: independent retry, DLQ, scaling
  Add a new service → subscribe a new SQS → Order Service unchanged
```

## SNS Message Filtering — selective delivery

```typescript
// Problem: different event types are published to the Topic
// Without filtering: every subscriber receives EVERYTHING → checks the type itself
// With filtering: SNS delivers only the relevant messages to each subscriber

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

```txt
SQS (Simple Queue Service):
  Pattern:   Point-to-Point (one consumer)
  Storage:   stores messages up to 14 days
  Retry:     Visibility Timeout + DLQ
  Ordering:  Standard (best-effort) / FIFO (strict)
  Use when:  tasks that should be processed by a single worker

SNS (Simple Notification Service):
  Pattern:   Pub/Sub (many subscribers)
  Storage:   no storage (fire-and-forget, retry is limited)
  Retry:     for HTTP: 3 attempts; for SQS/Lambda: reliable
  Filtering: Message Filtering by attributes
  Use when:  fan-out, domain events, notifications

EventBridge:
  Pattern:   Event Bus (routing by event patterns)
  Storage:   no storage
  Routing:   complex rules on JSON content
  Sources:   AWS services, SaaS (Salesforce, Datadog), custom
  Use when:  complex event routing logic, AWS service integration,
             cron jobs (Scheduled Rules), cross-account events

Common question: "When SNS, when EventBridge?"
  SNS: simple fan-out by event type, filtering by attributes
  EventBridge: routing by JSON body fields, many rules, cron, SaaS integrations
```

## Common interview mistakes

- **"SNS stores messages like SQS does"** — no. SNS is fire-and-forget. If a subscriber is unavailable at publish time — the message is lost (for HTTP endpoints: retry with backoff; for SQS: reliable, since SQS stores). That's exactly why SNS → SQS → Lambda is preferred over SNS → Lambda directly.

- **"SQS and SNS are interchangeable"** — they implement different patterns. SQS = one consumer pulls a message from the queue. SNS = push to all subscribers. Fan-out requires SNS (or EventBridge). For "one worker processes it" — SQS.

- **"SNS Fan-Out adds unnecessary complexity"** — without SNS, to notify 3 services the Order Service makes 3 HTTP calls: tight coupling, if one fails the Order Service must handle it. With SNS: one call + each service retries independently. Adding a 4th service = subscribe it, no changes to the Order Service.

- **"SNS Message Filtering works on the message body"** — no. SNS Message Filtering works only on Message Attributes (metadata), not on the JSON body. For filtering by body content → use EventBridge (supports content-based filtering on JSON fields).

- **"SNS FIFO is the same as SQS FIFO"** — SNS also supports a FIFO Topic (only for SQS FIFO subscribers). But SNS FIFO is strictly limited in throughput. For most fan-out scenarios, a standard SNS Topic is sufficient; ordering is ensured at the level of individual SQS FIFO queues.
