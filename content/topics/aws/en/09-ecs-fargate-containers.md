# ECS, Fargate and Containers

## Why Containers Are Needed

Very popular interview question.

---

The problem.

---

The application works on the developer's machine.

---

But doesn't work on the server.

---

Reasons:

```txt
different Node version

different libraries

different Linux

different environment
```

---

# Docker

Solves the problem.

---

A container contains:

```txt
Application

Runtime

Dependencies

Configuration
```

---

We get:

```txt
the same environment
everywhere
```

---

# Container

Interviewers love asking this.

---

A container is:

```txt
an isolated process
```

---

Important.

---

A container is:

```txt
NOT a virtual machine
```

---

# VM vs Container

VM:

```txt
OS
+
Kernel
+
Application
```

---

Container:

```txt
Application
+
Dependencies
```

---

Uses:

```txt
shared kernel
```

---

That's why containers are lighter.

---

# ECS

Elastic Container Service.

---

AWS container orchestrator.

---

Manages:

```txt
starting

updating

scaling

monitoring
```

---

Containers.

---

# ECS Cluster

A group of resources.

---

Inside:

```txt
Services

Tasks
```

---

# Task

Very popular interview question.

---

Task:

```txt
a running container
```

---

Roughly:

```txt
Docker Container
```

---

In ECS.

---

# Task Definition

A launch template.

---

Contains:

```txt
image

cpu

memory

env variables

ports
```

---

# Service

Manages the number of tasks.

---

For example:

```txt
3 containers
```

---

If one goes down:

```txt
ECS creates a new one
```

---

# ECS on EC2

The older approach.

---

We manage:

```txt
virtual machines
```

ourselves.

---

Diagram:

```txt
ECS
 ↓
EC2
 ↓
Containers
```

---

# Drawback

We need to manage:

```txt
EC2

updates

scaling
```

---

# Fargate

Very popular interview question.

---

AWS serverless containers.

---

Diagram:

```txt
ECS
 ↓
Fargate
 ↓
Containers
```

---

Without EC2.

---

# What AWS Does

Manages:

```txt
servers

capacity

patching

scaling
```

---

# What We Do

Only:

```txt
deploy container
```

---

# Why Fargate is Popular

We get:

```txt
containers

without managing servers
```

---

# ECS vs Fargate

Interviewers love asking this.

---

ECS + EC2:

```txt
cheaper

more control
```

---

Fargate:

```txt
simpler

less DevOps
```

---

# Lambda vs Fargate

The most popular question.

---

Lambda:

```txt
short tasks

event driven

serverless
```

---

Fargate:

```txt
long-lived applications

REST API

WebSocket

Background Workers
```

---

# When Lambda is a Bad Choice

For example:

```txt
NestJS API

long connections

very high load
```

---

Often better:

```txt
ECS/Fargate
```

---

# When Lambda is a Good Choice

```txt
File Processing

Notifications

Cron Jobs

Small APIs
```

---

# Load Balancer

A very important topic.

---

ECS is often placed behind:

```txt
ALB
```

---

Application Load Balancer.

---

Flow:

```txt
User
 ↓
ALB
 ↓
Task 1

Task 2

Task 3
```

---

# Auto Scaling

Interviewers love asking this.

---

For example:

```txt
CPU > 70%
```

---

ECS launches:

```txt
new containers
```

---

# Deployment

Typically:

```txt
Docker Build
 ↓
ECR
 ↓
ECS Deploy
```

---

# ECR

Elastic Container Registry.

---

AWS Docker Registry.

---

Stores:

```txt
Docker Images
```

---

# Common Question

What is ECS?

Answer:

The AWS container orchestration service.

---

# Common Question

What is Fargate?

Answer:

A serverless mode for running containers without managing EC2.

---

# Common Question

When to choose Lambda vs Fargate?

Answer:

Lambda is suitable for event-driven short tasks. Fargate is better for long-lived APIs and containerized applications.

---

# Interview Answer

ECS is the AWS container orchestration service. Fargate allows running containers without managing servers, providing a serverless model for Docker applications. For most modern backend APIs built with NestJS or Express, ECS Fargate is commonly used together with an Application Load Balancer.
