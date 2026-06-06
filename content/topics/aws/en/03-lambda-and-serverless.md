# Lambda and Serverless

## What is AWS Lambda

Very popular interview question.

---

Lambda is a service for running code
without managing servers.

---

We upload:

```txt
code
```

---

AWS provides:

```txt
servers
scaling
monitoring
infrastructure
```

---

# Traditional Approach

```txt
Application
 ↓
EC2
 ↓
Linux
 ↓
Monitoring
 ↓
Scaling
```

---

We are responsible for everything.

---

# Lambda

```txt
Application
 ↓
Lambda
```

---

AWS is responsible for the rest.

---

# Why It's Called Serverless

Interviewers love asking this.

---

Servers do exist.

---

But:

```txt
the developer doesn't manage them
```

---

Hence:

```txt
Serverless
```

---

# Event Driven

The main idea behind Lambda.

---

Lambda doesn't run continuously.

---

It is triggered:

```txt
by an event
```

---

# Examples of Events

```txt
HTTP Request

S3 Upload

SQS Message

SNS Event

CloudWatch Event
```

---

# Example

```txt
File Uploaded
 ↓
S3 Event
 ↓
Lambda
 ↓
Image Resize
```

---

# Lambda Handler

Node.js example.

---

```ts
export const handler =
 async (event) => {

  return {
   statusCode: 200
  };
 };
```

---

# Event

Contains event data.

---

For example:

```txt
request
headers
query params
SQS message
```

---

Depends on the source.

---

# Execution Environment

Very popular interview question.

---

Lambda runs inside:

```txt
an isolated runtime
```

---

AWS creates a container.

---

Runs the code.

---

Returns the result.

---

# Cold Start

The most popular Lambda question.

---

What happens.

---

A request arrives.

---

But there is no container yet.

---

AWS must:

```txt
create a runtime

load the code

initialize dependencies
```

---

This takes time.

---

We get:

```txt
Cold Start
```

---

# Cold Start Flow

```txt
Request
 ↓
Container Creation
 ↓
Initialization
 ↓
Handler Execution
```

---

# Warm Start

After the first invocation.

---

The container already exists.

---

We get:

```txt
Warm Start
```

---

Much faster.

---

# What Affects Cold Start

Interviewers love asking this.

---

Size of:

```txt
bundle
dependencies
runtime
```

---

For example:

```txt
NestJS
```

usually starts slower.

---

Than:

```txt
simple Node Lambda
```

---

# How to Reduce Cold Start

```txt
smaller bundle

tree shaking

esbuild

provisioned concurrency
```

---

# Stateless

A very important topic.

---

Lambda should be treated as:

```txt
stateless
```

---

You cannot rely on:

```txt
the container persisting
```

---

# Scaling

A very strong feature of Lambda.

---

```txt
1 request
```

---

One container.

---

```txt
1000 requests
```

---

AWS can create:

```txt
1000 containers
```

---

Automatically.

---

# Limitations

Interviewers love asking this.

---

Lambda is not suitable for:

```txt
long-lived connections

WebSockets (partially)

very long computations
```

---

# Cost

Very popular interview question.

---

We pay for:

```txt
number of invocations

execution time

memory
```

---

We don't pay for idle time.

---

# When Lambda is a Good Fit

```txt
API

Background Jobs

File Processing

Automation

Event Processing
```

---

# When It's Not a Good Fit

```txt
High Throughput APIs

Long Running Processes

Heavy CPU Tasks
```

---

Then the common choice is:

```txt
ECS

Fargate

EC2
```

---

# Common Question

What is a Cold Start?

Answer:

The latency of the first Lambda invocation, caused by the creation of a new runtime and application initialization.

---

# Common Question

Why is Lambda considered Serverless?

Answer:

Because the developer doesn't manage servers, scaling, or infrastructure — AWS handles all of that.

---

# Interview Answer

AWS Lambda is a serverless compute service that executes code in response to events. Lambda scales automatically, is billed based on actual usage, and is well-suited for APIs, background tasks, and event processing. One of its key characteristics is the Cold Start — the delay when a new execution environment is created.
