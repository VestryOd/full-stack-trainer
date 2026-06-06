# API Gateway

## What is API Gateway

Very popular interview question.

---

API Gateway —
a managed HTTP entry point to the system.

---

Diagram:

```txt
Browser
 ↓
API Gateway
 ↓
Lambda
```

---

# Why You Need It

Lambda can be invoked directly.

---

But API Gateway provides:

```txt
Routing

Authentication

Rate Limiting

Caching

Monitoring
```

---

# Analogy

API Gateway for microservices —
roughly like:

```txt
Nginx
```

---

For a regular application.

---

# Main Flow

```txt
Client
 ↓
API Gateway
 ↓
Lambda
 ↓
Response
```

---

# Endpoint

For example:

```http
GET /products
```

---

API Gateway receives the request.

---

Passes it to Lambda.

---

Lambda returns the response.

---

# Route Configuration

Example:

```txt
GET /products

POST /products

DELETE /products
```

---

Each route
can invoke its own Lambda.

---

# Proxy Integration

The most popular mode.

---

API Gateway passes:

```txt
the entire request
```

---

To Lambda.

---

Lambda receives:

```json
{
 headers,
 queryStringParameters,
 body
}
```

---

# Response

Lambda must return:

```ts
{
 statusCode: 200,
 body: ...
}
```

---

API Gateway converts this:

```txt
into an HTTP Response
```

---

# Authorization

Very popular interview question.

---

API Gateway supports:

```txt
JWT

IAM

Custom Authorizer

Cognito
```

---

# Lambda Authorizer

Often asked.

---

Diagram:

```txt
Request
 ↓
Authorizer Lambda
 ↓
Allow / Deny
 ↓
Main Lambda
```

---

# Throttling

A very important topic.

---

Problem:

```txt
100000 requests
```

---

Can overload the system.

---

API Gateway allows:

```txt
limiting RPS
```

---

# Rate Limiting

Example:

```txt
100 req/sec
```

---

Excess requests:

```txt
429 Too Many Requests
```

---

# Caching

API Gateway can cache responses.

---

For example:

```txt
Product Catalog
```

---

Lambda doesn't always need to be invoked.

---

# Monitoring

Integration with:

```txt
CloudWatch
```

---

You can view:

```txt
Latency

Errors

Request Count
```

---

# REST API vs HTTP API

Interviewers love asking this.

---

REST API:

```txt
older option

more features

more expensive
```

---

HTTP API:

```txt
faster

cheaper

simpler
```

---

Today the common choice is:

```txt
HTTP API
```

---

# API Gateway + Lambda

The most popular AWS architecture.

---

```txt
Frontend
 ↓
API Gateway
 ↓
Lambda
 ↓
Database
```

---

# Fullstack Example

```txt
Next.js
 ↓
API Gateway
 ↓
Lambda
 ↓
PostgreSQL
```

---

# Common Question

Why not invoke Lambda directly?

Answer:

API Gateway provides routing, authorization, rate limiting, caching, and monitoring.

---

# Common Question

What does a Lambda Authorizer do?

Answer:

A separate Lambda that checks access rights and returns an allow or deny decision for the request.

---

# Common Question

What is Throttling?

Answer:

A mechanism for limiting the number of requests to protect the system from overload.

---

# Interview Answer

API Gateway is a managed AWS HTTP gateway and is commonly used in front of Lambda. It handles request routing, authorization, rate limiting, caching, and monitoring. In a serverless architecture, API Gateway typically serves as the single entry point for all HTTP requests.
