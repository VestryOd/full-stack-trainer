# SNS and Pub/Sub Architecture

## What is SNS

SNS stands for:

```txt
Simple Notification Service
```

---

It is the AWS Pub/Sub service.

---

# The Main Idea

SQS:

```txt
One message
 ↓
One Consumer
```

---

SNS:

```txt
One event
 ↓
Many subscribers
```

---

# Queue vs Pub/Sub

Very popular interview question.

---

SQS:

```txt
Producer
 ↓
Queue
 ↓
Consumer
```

---

A message is typically processed
by one recipient.

---

# SNS

```txt
Producer
 ↓
Topic
 ↓
Subscriber A

Subscriber B

Subscriber C
```

---

All subscribers receive the same event.

---

# Topic

The most important SNS entity.

---

Topic is an event publication channel.

---

For example:

```txt
user-created
```

---

# Publish

Sending an event.

---

```txt
User Service
 ↓
SNS Topic
```

---

# Subscribe

Subscribing to a Topic.

---

```txt
Email Service

Analytics Service

CRM Service
```

---

All receive the same event.

---

# Flow

```txt
User Created
 ↓
SNS Topic
 ↓
Email

Analytics

CRM
```

---

# Why SNS is Needed

Interviewers love asking this.

---

Without SNS:

```txt
User Service
 ↓
Email

 ↓
Analytics

 ↓
CRM
```

---

Tight coupling.

---

With SNS:

```txt
User Service
```

---

Doesn't know at all
who is listening to events.

---

# Types of Subscribers

SNS can send events to:

```txt
SQS

Lambda

HTTP

Email

SMS
```

---

# SNS → Lambda

A very popular architecture.

---

```txt
SNS Topic
 ↓
Lambda A

Lambda B

Lambda C
```

---

# SNS → SQS

Even more popular.

---

```txt
SNS
 ↓
SQS A

SQS B

SQS C
```

---

Each system gets its own queue.

---

# Fan-Out Pattern

The most popular SNS topic.

---

One event:

```txt
Order Created
```

---

Is sent to:

```txt
Billing

Email

Analytics

CRM
```

---

This is called:

```txt
Fan-Out
```

---

# SQS vs SNS

Interviewers love asking this.

---

SQS:

```txt
Queue
```

---

SNS:

```txt
Pub/Sub
```

---

SQS:

```txt
1 Consumer
```

---

SNS:

```txt
Many Consumers
```

---

# SNS + SQS

The most popular AWS architecture.

---

```txt
Order Service
 ↓
SNS
 ↓
SQS Billing

SQS Email

SQS Analytics
```

---

Advantages:

```txt
scaling

retries

buffering

loose coupling
```

---

# Delivery Guarantees

SNS also uses:

```txt
At Least Once Delivery
```

---

Therefore subscribers must be:

```txt
idempotent
```

---

# When to Use SNS

Good fit:

```txt
Domain Events

Notifications

Fan-Out

Event Driven Architecture
```

---

# When Not to Use

If you need:

```txt
a single recipient
```

---

Then it's better to use:

```txt
SQS
```

---

# Common Question

How does SNS differ from SQS?

Answer:

SQS is designed for queues and processing messages by a single consumer. SNS implements the Pub/Sub model, where one event is delivered to multiple subscribers.

---

# Common Question

What is the Fan-Out Pattern?

Answer:

An architectural pattern where a single event is published to SNS and automatically delivered to multiple independent systems.

---

# Interview Answer

SNS is the AWS Pub/Sub service used for publishing events to multiple subscribers. The central element is the Topic, to which events are published. SNS is often used together with SQS to build scalable event-driven systems.
