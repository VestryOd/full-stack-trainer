# AWS Fundamentals

## What is AWS

AWS (Amazon Web Services) —
Amazon's cloud platform.

---

Provides:

```txt
Compute
Storage
Networking
Databases
Messaging
Monitoring
Security
```

---

# The Main Idea of the Cloud

Instead of buying servers:

```txt
Buy a server
Configure a server
Maintain a server
Replace disks
Replace memory
```

---

We get:

```txt
resource rental
on demand
```

---

# Main Models

Very popular interview question.

---

# IaaS

Infrastructure as a Service.

---

AWS provides:

```txt
VM
Storage
Network
```

---

Example:

```txt
EC2
```

---

# PaaS

Platform as a Service.

---

AWS manages the infrastructure.

---

We write the code.

---

Examples:

```txt
Lambda
Elastic Beanstalk
```

---

# SaaS

Software as a Service.

---

A ready-made product.

---

Examples:

```txt
Gmail
Notion
Salesforce
```

---

# Region

Very popular interview question.

---

Region:

```txt
AWS geographical region
```

---

For example:

```txt
eu-central-1
Frankfurt

eu-west-1
Ireland
```

---

# Availability Zone

AZ.

---

Inside a region.

---

Example:

```txt
eu-central-1a
eu-central-1b
eu-central-1c
```

---

Separate data centers.

---

# Why AZ

For fault tolerance.

---

If one data center goes down:

```txt
the application continues to work
```

---

# Shared Responsibility Model

A very popular interview question.

---

AWS is responsible for:

```txt
Physical Security
Networking
Hardware
```

---

We are responsible for:

```txt
Application
Data
Users
Permissions
```

---

# Core Services

Compute:

```txt
EC2
Lambda
ECS
```

---

Storage:

```txt
S3
```

---

Database:

```txt
RDS
DynamoDB
```

---

Messaging:

```txt
SQS
SNS
```

---

Security:

```txt
IAM
Secrets Manager
```

---

# Infrastructure as Code

A very important topic.

---

Don't create resources manually.

---

We use:

```txt
CloudFormation
CDK
Terraform
```

---

# AWS CDK

Given your experience,
a very likely interview question.

---

CDK lets you describe infrastructure:

```ts
new Bucket(...)
new Function(...)
new Distribution(...)
```

---

In TypeScript.

---

Then it generates:

```txt
CloudFormation
```

---

# Common Question

What is an AWS Region?

Answer:

An independent geographical AWS region containing multiple Availability Zones.

---

# Common Question

What is an Availability Zone?

Answer:

An isolated data center within a region, used for fault tolerance.

---

# Interview Answer

AWS is a cloud platform providing compute resources, storage, databases, message queues, and security tools. The foundation of AWS architecture is Regions and Availability Zones, which ensure scalability and fault tolerance.
