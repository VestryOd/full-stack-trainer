# Notification System Design

## Problem Statement

Design a notification system.

---

Examples:

```txt
Email

Push Notifications

SMS

In-App Notifications
```

---

# Requirements

A user created an order.

---

We need to send:

```txt
Email

Push

Internal Notification
```

---

# Beginner's Mistake

Doing this:

```txt
Order Service
 ↓
Email Service
 ↓
Push Service
 ↓
SMS Service
```

---

# Why It Is Bad

If the Email Service goes down:

```txt
Order Service goes down
```

---

# The Right Approach

Via events.

---

```txt
Order Service
 ↓
Event
 ↓
Notification System
```

---

# Event Driven Architecture

After the order we publish:

```txt
Order Created
```

---

# Fan Out

A very popular question.

---

One event.

---

Many handlers.

---

```txt
Order Created
 ↓
Email

Push

Analytics

CRM
```

---

# Notification Service

```txt
API
 ↓
Queue
 ↓
Workers
```

---

# Why a Queue Is Required

Interviewers love asking about this.

---

A user created:

```txt
10000 orders
```

---

The email service is slow.

---

The queue smooths the load.

---

# Typical Diagram

```txt
Producer
 ↓
SQS
 ↓
Notification Workers
```

---

# Notification Table

```sql
notifications

id

user_id

type

status

created_at
```

---

# Statuses

```txt
Pending

Sent

Failed
```

---

# Retry

A very important topic.

---

The email service is unavailable.

---

We retry after:

```txt
1 min

5 min

15 min
```

---

# Dead Letter Queue

After several failures.

---

```txt
Main Queue
 ↓
DLQ
```

---

# Otherwise

The message will keep failing forever.

---

# User Preferences

Interviewers love asking about this.

---

The user can disable:

```txt
Emails

SMS

Push
```

---

Table:

```sql
notification_preferences
```

---

# Push Notifications

Usually:

```txt
Firebase Cloud Messaging

Apple Push Notification Service
```

---

# Email

Usually:

```txt
SES

SendGrid

Mailgun
```

---

# SMS

Usually:

```txt
Twilio
```

---

# In-App Notifications

Stored in the DB.

---

For example:

```txt
Your order has been shipped
```

---

# Realtime Notifications

If the user is online.

---

```txt
Notification Service
 ↓
WebSocket
 ↓
Client
```

---

# If the User Is Offline

Interviewers love asking about this.

---

We write to:

```txt
Database
```

---

Then show:

```txt
Unread Notifications
```

---

# Scaling

Very straightforward.

---

Add more:

```txt
Workers
```

---

The number of workers scales independently.

---

# Final Architecture

```txt
Order Service
 ↓
SNS
 ↓
SQS
 ↓
Notification Workers
```

---

Then:

```txt
Email

Push

SMS
```

---

Store in:

```txt
PostgreSQL
```

---

Cache in:

```txt
Redis
```

---

# Common Question

Why send notifications via a queue?

Answer:

To avoid blocking the main business process.

---

# Common Question

Why is DLQ needed?

Answer:

To isolate messages that keep failing.

---

# Common Question

Why does Event Driven Architecture fit well?

Answer:

Because the order creation service knows nothing about notification delivery methods.

---

# Common Question

How to add a new notification channel?

Answer:

Add a new consumer for the event without changing existing services.

---

# Interview Answer

A modern notification system is built on Event Driven Architecture. The business service publishes events that go into a queue, and separate workers are responsible for delivering Email, Push, SMS, and in-app notifications. This approach ensures loose coupling, reliability, and independent scaling of components.
