# SQS and Event-Driven Architecture

## What is SQS

SQS stands for:

```txt
Simple Queue Service
```

---

It is the AWS message queue.

---

# The Main Idea

Decouple services.

---

Without a queue:

```txt
API
 ↓
Email Service
```

---

If Email Service goes down:

```txt
the API suffers too
```

---

# Through a Queue

```txt
API
 ↓
SQS
 ↓
Email Service
```

---

The API completes successfully.

---

The message stays in the queue.

---

# Why Queues Are Needed

Very popular interview question.

---

For:

```txt
asynchronicity

buffering

resilience

scaling
```

---

# Producer

Sends messages.

---

For example:

```txt
Order Service
```

---

# Consumer

Reads messages.

---

For example:

```txt
Email Service
```

---

# Flow

```txt
Producer
 ↓
SQS
 ↓
Consumer
```

---

# Message

A message in the queue.

---

For example:

```json
{
 "userId": 123,
 "type": "WELCOME_EMAIL"
}
```

---

# Polling

Very popular interview question.

---

Consumer asks:

```txt
Are there messages?
```

---

If yes:

```txt
receives the message
```

---

# Visibility Timeout

Interviewers' favorite topic.

---

What happens.

---

Consumer received the message.

---

But hasn't processed it yet.

---

To prevent another consumer
from picking it up again:

```txt
the message is hidden
```

---

For the duration of:

```txt
Visibility Timeout
```

---

# Flow

```txt
Message
 ↓
Consumer
 ↓
Invisible
 ↓
Processing
```

---

# Delete Message

Very important.

---

After successful processing:

```txt
Consumer
 ↓
Delete Message
```

---

The message is deleted.

---

# What if Consumer Crashes

Very popular interview question.

---

The message wasn't deleted.

---

After the expiration of:

```txt
Visibility Timeout
```

---

The message reappears.

---

# At Least Once Delivery

A critically important topic.

---

SQS guarantees:

```txt
at least once
```

---

But may deliver:

```txt
multiple times
```

---

Therefore handlers must be:

```txt
idempotent
```

---

# Idempotency

Interviewers love asking this.

---

Operation:

```txt
1 call
or

10 calls
```

---

Must produce the same result.

---

# Standard Queue

Default.

---

Pros:

```txt
very high throughput
```

---

Cons:

```txt
possible duplicates

no strict ordering
```

---

# FIFO Queue

First In First Out.

---

Guarantees:

```txt
message ordering
```

---

And nearly eliminates duplicates.

---

Con:

```txt
lower throughput
```

---

# Dead Letter Queue

Very popular interview question.

---

Problem:

```txt
message keeps failing
```

---

Solution:

```txt
DLQ
```

---

After several attempts:

```txt
main queue
 ↓
DLQ
```

---

The message is moved.

---

# Lambda + SQS

A very popular architecture.

---

```txt
API
 ↓
SQS
 ↓
Lambda
```

---

Lambda automatically reads the queue.

---

# Event Driven Architecture

The main idea.

---

Instead of:

```txt
Service A
 ↓
Service B
 ↓
Service C
```

---

We get:

```txt
Service A
 ↓
Event
 ↓
Queue
 ↓
Consumers
```

---

Services don't know about each other.

---

# Real-World Example

Order creation.

---

```txt
Order Created
```

---

Event goes into the queue.

---

Then independently:

```txt
Email Service

Analytics Service

CRM Service

Billing Service
```

---

# When to Use SQS

Good fit:

```txt
Email

Reports

Notifications

Background Jobs

File Processing
```

---

# When Not a Good Fit

```txt
Realtime Chat

Realtime Gaming

Low Latency Systems
```

---

# Common Question

Why not call the service directly?

Answer:

A queue breaks the dependency between services and allows surviving temporary consumer failures.

---

# Common Question

What is Visibility Timeout?

Answer:

The period during which a received message is hidden from other consumers while the current consumer is processing it.

---

# Common Question

Why do you need a DLQ?

Answer:

To isolate messages that consistently fail during processing and cannot be successfully handled.

---

# Common Question

What is At Least Once Delivery?

Answer:

SQS guarantees delivery of a message at least once, so handlers must be idempotent.

---

# Interview Answer

SQS is the AWS message queue, used for asynchronous processing and building event-driven systems. It allows decoupling services, surviving temporary failures, and scaling load independently. Key concepts are Visibility Timeout, Dead Letter Queue, At Least Once Delivery, and Idempotency.
