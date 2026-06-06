# AWS Interview Questions (Fullstack / Senior)

---

# 1. What is AWS?

AWS (Amazon Web Services) is Amazon's cloud platform providing services for computing, data storage, networking, security, message queuing, and databases.

---

# 2. What is Cloud Computing?

A model for delivering computing resources over the internet on demand.

---

# 3. What is a Region?

An AWS geographical region.

Example:

```txt
eu-central-1
us-east-1
```

---

# 4. What is an Availability Zone?

An isolated data center within an AWS region.

---

# 5. Why are Availability Zones needed?

For fault tolerance.

If one data center becomes unavailable, the application continues to run in other AZs.

---

# 6. What is the Shared Responsibility Model?

AWS is responsible for:

```txt
Infrastructure
Networking
Hardware
```

---

The customer is responsible for:

```txt
Application
Users
Permissions
Data
```

---

# 7. What is Infrastructure as Code?

Describing infrastructure as code.

Examples:

```txt
CloudFormation
CDK
Terraform
```

---

# 8. What is AWS CDK?

An AWS framework for describing infrastructure in TypeScript, Python, Java, and other languages.

---

# 9. What is S3?

AWS object storage.

Used for:

```txt
Images
Files
Backups
Documents
```

---

# 10. What is a Bucket?

A container for objects in S3.

---

# 11. Are there folders in S3?

No.

Folders are just part of the object key.

---

# 12. What is a Pre-Signed URL?

A temporary signed link for directly uploading or downloading an object from S3.

---

# 13. Why use Pre-Signed URLs?

To avoid proxying large files through the backend.

---

# 14. What is CloudFront?

AWS CDN.

Caches content closer to users.

---

# 15. What is a CDN?

Content Delivery Network.

A network of servers for accelerated content delivery.

---

# 16. What is an Edge Location?

A CloudFront server located near the user.

---

# 17. How does CloudFront differ from S3?

S3 stores data.

CloudFront accelerates its delivery.

---

# 18. What is a Cache Hit?

Content found in the CloudFront cache.

---

# 19. What is a Cache Miss?

Content not found in the cache and requested from the Origin.

---

# 20. What is Lambda?

AWS Serverless Compute Service.

Executes code in response to an event.

---

# 21. Why is Lambda called Serverless?

Because the developer doesn't manage servers.

---

# 22. What is Event-Driven Architecture?

An architecture where execution is initiated by events.

---

# 23. What events can trigger Lambda?

```txt
API Gateway
S3
SQS
SNS
CloudWatch
```

---

# 24. What is a Cold Start?

The time it takes to create a new execution environment for Lambda.

---

# 25. What is a Warm Start?

A repeated invocation of an already existing Lambda container.

---

# 26. How to reduce Cold Start?

```txt
smaller bundle

fewer dependencies

Provisioned Concurrency
```

---

# 27. What is API Gateway?

An AWS HTTP gateway for routing requests to Lambda and other services.

---

# 28. Why is API Gateway needed?

Provides:

```txt
Routing
Auth
Caching
Monitoring
Rate Limiting
```

---

# 29. What is a Lambda Authorizer?

A Lambda function that performs authorization before the main endpoint is invoked.

---

# 30. What is Throttling?

Limiting the number of requests.

---

# 31. What is IAM?

Identity and Access Management.

The AWS access control system.

---

# 32. What is an IAM Policy?

A set of permissions.

---

# 33. What is an IAM Role?

A set of permissions that a service or user can temporarily use.

---

# 34. What is Least Privilege?

The principle of minimum necessary permissions.

---

# 35. Why are IAM Roles better than Access Keys?

No need to store secrets in code.

Temporary credentials are used.

---

# 36. How does Lambda get access to S3?

Via IAM Role.

---

# 37. What is Secrets Manager?

A service for securely storing secrets.

---

# 38. What is SQS?

AWS message queue.

---

# 39. Why are queues needed?

For:

```txt
asynchronicity

buffering

retries

scaling
```

---

# 40. What is a Producer?

A message sender.

---

# 41. What is a Consumer?

A message receiver.

---

# 42. What is Visibility Timeout?

The time during which a message is hidden after being received by a consumer.

---

# 43. What is a Dead Letter Queue?

A queue for messages that could not be processed.

---

# 44. What is At Least Once Delivery?

A guarantee that a message is delivered at least once.

---

# 45. What is Idempotency?

An operation that produces the same result regardless of how many times it is called.

---

# 46. What is SNS?

AWS Pub/Sub service.

---

# 47. What is a Topic?

An event publication channel in SNS.

---

# 48. How does SNS differ from SQS?

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

# 49. What is the Fan-Out Pattern?

Broadcasting a single event to multiple subscribers.

---

# 50. What is RDS?

A managed relational database AWS service.

---

# 51. Which databases does RDS support?

```txt
PostgreSQL
MySQL
MariaDB
SQL Server
```

---

# 52. What is DynamoDB?

A highly scalable AWS NoSQL database.

---

# 53. Main difference between PostgreSQL and DynamoDB?

PostgreSQL:

```txt
Relations
JOIN
SQL
```

---

DynamoDB:

```txt
Key-Value
Document
```

---

# 54. Why is DynamoDB fast?

Optimized for key-based access and horizontal scaling.

---

# 55. What is a Partition Key?

The key that determines where data is stored in DynamoDB.

---

# 56. What is ECS?

AWS container orchestration service.

---

# 57. What is Fargate?

Serverless container execution without managing EC2.

---

# 58. What is ECR?

AWS Docker Registry.

---

# 59. What is a Task in ECS?

A running container.

---

# 60. What is a Service in ECS?

A component that maintains the required number of containers.

---

# 61. How does ECS differ from Fargate?

ECS can use EC2.

Fargate is fully managed by AWS.

---

# 62. When to choose Lambda?

Good fit for:

```txt
Events
Cron Jobs
File Processing
Small APIs
```

---

# 63. When to choose ECS/Fargate?

Good fit for:

```txt
NestJS APIs
Long Running Services
WebSockets
Microservices
```

---

# 64. What is ALB?

Application Load Balancer.

Distributes traffic across containers and services.

---

# 65. How would you build file upload?

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

# 66. How would you build thumbnail generation?

```txt
Upload
 ↓
S3
 ↓
Lambda
 ↓
Thumbnail
```

---

# 67. How would you build email processing?

```txt
API
 ↓
SQS
 ↓
Worker
 ↓
Email Provider
```

---

# 68. How would you build an online store?

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
```

---

# 69. How would you build a CMS?

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

# 70. Most Popular Senior Question

When to choose Lambda vs ECS/Fargate?

Answer:

Lambda is suitable for short event-driven tasks and irregular workloads. ECS/Fargate is better suited for long-lived APIs, containerized applications, WebSocket connections, and services with steady load.

---

# 71. The Strongest Architectural Answer

How to choose an AWS service?

Answer:

You can't choose a service based on "always use Lambda" or "always use ECS". The choice depends on the nature of the workload, latency requirements, cost, fault tolerance, execution time, and the operational complexity of the system.
