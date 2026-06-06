# AWS Architecture Patterns

## The Most Important AWS File

On Senior interviews, they rarely ask:

```txt
what is S3
```

---

More often they ask:

```txt
how would you build the system
```

---

# Pattern 1

Static Website

---

Diagram:

```txt
User
 ↓
CloudFront
 ↓
S3
```

---

Used for:

```txt
Landing Pages

Documentation

Static Sites
```

---

# Pattern 2

Next.js Production

---

Very popular interview question.

---

```txt
User
 ↓
CloudFront
 ↓
Next.js
 ↓
API
 ↓
PostgreSQL
```

---

# Pattern 3

Next.js + Strapi

---

For CMS projects.

---

```txt
User
 ↓
CloudFront
 ↓
Next.js
 ↓
Strapi
 ↓
PostgreSQL
```

---

Pages:

```txt
ISR
```

---

After publishing:

```txt
revalidateTag()
```

---

# Pattern 4

Serverless API

---

The most popular AWS pattern.

---

```txt
Client
 ↓
API Gateway
 ↓
Lambda
 ↓
DynamoDB
```

---

Pros:

```txt
simplicity

scaling

low cost
```

---

# Pattern 5

File Upload

---

Interviewers love asking this.

---

```txt
Frontend
 ↓
Backend
 ↓
Pre-Signed URL

Frontend
 ↓
S3
```

---

# Why This Way

Backend doesn't participate
in the file transfer.

---

# Pattern 6

Image Processing

---

```txt
Upload
 ↓
S3
 ↓
Lambda
 ↓
Thumbnail
 ↓
S3
```

---

A very common task.

---

# Pattern 7

Queue Based Processing

---

```txt
API
 ↓
SQS
 ↓
Workers
```

---

Advantages:

```txt
offloading the API

retries

scaling
```

---

# Pattern 8

SNS + SQS Fan-Out

---

Senior interviewers love this.

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

One event:

```txt
many subscribers
```

---

# Pattern 9

Microservices

---

```txt
ALB
 ↓
ECS

 ↓
User Service

 ↓
Order Service

 ↓
Payment Service
```

---

# Pattern 10

Event Driven Architecture

---

```txt
Order Created
 ↓
SNS
 ↓
Consumers
```

---

Services are connected
through events.

---

# Monolith vs Microservices

Very popular interview question.

---

Monolith:

```txt
simpler

cheaper

faster development
```

---

Microservices:

```txt
scaling

independent releases

harder to maintain
```

---

# Lambda vs ECS

Another popular question.

---

Lambda:

```txt
event driven
```

---

ECS:

```txt
always running
```

---

# PostgreSQL vs DynamoDB

Interviewers love asking this.

---

Most business systems:

```txt
PostgreSQL
```

---

High Throughput:

```txt
DynamoDB
```

---

# Common Question

How would you build an online store?

Answer:

```txt
Next.js
 ↓
CloudFront
 ↓
NestJS
 ↓
PostgreSQL

Uploads → S3

Notifications → SQS

Emails → Workers
```

---

# Common Question

How would you build a CMS?

Answer:

```txt
Next.js
 ↓
Strapi
 ↓
PostgreSQL

Images → S3

CDN → CloudFront
```

---

# Common Question

How would you build an image processing system?

Answer:

```txt
Upload
 ↓
S3
 ↓
Event
 ↓
SQS
 ↓
Lambda Workers
 ↓
Thumbnail
```

---

# The Strongest Senior Answer

Which AWS service to choose?

Answer:

There is no universal service. The choice depends on performance requirements, cost, fault tolerance, latency, and the nature of the workload. A good architect selects services for each specific scenario rather than applying the same stack to every problem.
