# Message Queues and Event Driven Architecture

## Why Queues Are So Popular

Interviewers love asking about this.

---

Without a queue:

```txt
API
 ↓
Email Service
```

---

If the Email Service goes down:

```txt
API goes down
```

---

# Through a Queue

```txt
API
 ↓
Queue
 ↓
Worker
```

---

The API completes successfully.

---

The message remains.

---

# Main Advantages

```txt
Asynchrony

Buffering

Retries

Scaling
```

---

# Producer

Creates a message.

---

# Consumer

Processes a message.

---

# Queue

Intermediate storage.

---

# Example

```txt
Order Created
 ↓
SQS
 ↓
Email Worker
```

---

# Why This Is Better

Creating an order:

```txt
fast
```

---

Email:

```txt
asynchronous
```

---

# Event Driven Architecture

The next level.

---

A service publishes an event.

---

For example:

```txt
User Created
```

---

# Fan Out

```txt
User Service
 ↓
Event
 ↓
Email

Analytics

CRM
```

---

# Pub/Sub

Many subscribers.

---

Each receives the event.

---

# At Least Once Delivery

A very popular question.

---

A message may arrive:

```txt
multiple times
```

---

# Therefore

The consumer must be:

```txt
idempotent
```

---

# Dead Letter Queue

Messages that keep failing.

---

```txt
Main Queue
 ↓
DLQ
```

---

# When to Use a Queue

Suitable for:

```txt
Emails

Notifications

Reports

Video Processing
```

---

# When Not to Use

```txt
Realtime Chat

Realtime Gaming
```

---

# Interview Answer

Queues allow decoupling task creation from processing. They improve system reliability, allow surviving temporary failures, and allow scaling load independently.
