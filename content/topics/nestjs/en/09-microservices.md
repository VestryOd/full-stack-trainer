# NestJS Microservices

## What is a Microservice

A very popular interview question.

---

A microservice is an independent application
that performs a limited set of tasks.

---

Example.

---

Monolith:

```txt
Users
Orders
Payments
Notifications
```

---

In one application.

---

# Microservices

We split it up.

---

```txt
User Service

Order Service

Payment Service

Notification Service
```

---

Each service:

```txt
separate deploy

separate runtime

separate database (often)
```

---

# Why Microservices Appeared

A very popular interview question.

---

Reasons:

```txt
scaling

independent releases

team separation

fault tolerance
```

---

# Drawbacks

Even more popular.

---

There are:

```txt
network latency

distributed transactions

eventual consistency

monitoring

development complexity
```

---

# NestJS Microservices

Nest provides a separate layer.

---

Supported transports:

```txt
TCP

Redis

RabbitMQ

Kafka

NATS

gRPC
```

---

# The Main Idea

Instead of:

```http
GET /users/1
```

---

We get:

```txt
Message
```

---

between services.

---

# Message Pattern

The most important concept.

---

Analogous to:

```txt
Route
```

---

in HTTP.

---

Example.

---

```ts
@MessagePattern(
 'get-user'
)
```

---

A service subscribes.

---

```ts
@MessagePattern(
 'get-user'
)

getUser(id: string) {

 ...
}
```

---

# Request

The client sends:

```txt
get-user
```

---

Nest calls:

```txt
handler
```

---

# Event Pattern

The next topic.

---

```ts
@EventPattern(
 'user-created'
)
```

---

Used for events.

---

# Key Difference

Message Pattern:

```txt
Request / Response
```

---

There is a response.

---

# Event Pattern

```txt
Fire And Forget
```

---

No response.

---

# Example

Message Pattern:

```txt
give me the user
```

---

We wait for a response.

---

# Event Example

```txt
user was created
```

---

Nobody returns anything.

---

Just notifying the system.

---

# ClientProxy

A very popular interview topic.

---

Through it, a service
sends messages.

---

Example:

```ts
constructor(
 @Inject('USER_SERVICE')
 private client:
 ClientProxy
) {}
```

---

# Request / Response

```ts
this.client.send(
 'get-user',
 userId
);
```

---

We receive:

```txt
Observable
```

---

Very important.

---

Because under the hood:

```txt
network operation
```

---

# Event

```ts
this.client.emit(
 'user-created',
 payload
);
```

---

Nobody responds.

---

# send vs emit

A very popular interview question.

---

send:

```txt
Request/Response
```

---

emit:

```txt
Event
```

---

# Transport Layer

Nest hides the transport details.

---

The code is the same.

---

You can use:

```txt
TCP
Kafka
RabbitMQ
```

---

Only the config changes.

---

# TCP Transport

The simplest.

---

Usually used for:

```txt
local development

demo projects
```

---

# RabbitMQ

A very popular broker.

---

Pros:

```txt
queues

acknowledgement

retry

routing
```

---

# Kafka

A very popular Senior interview question.

---

Suitable for:

```txt
high throughput

event streaming

analytics
```

---

# gRPC

Very commonly used.

---

Pros:

```txt
faster than HTTP

protobuf

typing
```

---

# Event Driven Architecture

A very important topic.

---

Example.

---

```txt
Order Created
 ↓
Payment Service
 ↓
Notification Service
 ↓
Analytics Service
```

---

All receive the event.

---

Nobody depends directly.

---

# Saga Pattern

A very popular interview topic.

---

Problem:

```txt
distributed transaction
```

---

For example:

```txt
Order

Payment

Delivery
```

---

What if Payment failed?

---

You can't do:

```sql
ROLLBACK
```

across services.

---

Instead:

```txt
Compensating Actions
```

are used.

---

This is the Saga.

---

# When Microservices Are Justified

Suitable for:

```txt
large teams

complex domain

different load profiles
```

---

# When They Are Not Needed

A very popular interview question.

---

Bad for:

```txt
small CRUD projects
```

---

A monolith is simpler.

---

# Interview Answer

NestJS supports microservice architecture through various transport layers including TCP, RabbitMQ, Kafka, and gRPC. For Request/Response interaction, MessagePattern and ClientProxy.send() are used, and for event-driven architecture — EventPattern and ClientProxy.emit(). The main advantage is loose coupling of services and independent scaling.
