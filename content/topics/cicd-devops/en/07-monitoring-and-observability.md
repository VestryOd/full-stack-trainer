# Monitoring and Observability

## Monitoring vs Observability — the distinction

These two terms are often used interchangeably, but they describe different things:

**Monitoring** is the practice of collecting predefined signals from a system and alerting when those signals exceed thresholds. It answers: "Is something wrong?"

**Observability** is the property of a system that allows you to understand its internal state by examining its external outputs. It answers: "Why is something wrong?" — even for failure modes you didn't anticipate when you built the system.

```txt
Monitoring (known unknowns):
  "Alert me when error rate > 1%"
  — you already knew errors were worth watching

Observability (unknown unknowns):
  "Why is the checkout flow 3× slower only for users in Germany
   who use Safari on iOS after 18:00 on weekdays?"
  — you didn't predict this failure mode;
    observability lets you discover it from the data
```

A highly monitored system can still be poorly observable — if you only collect aggregate metrics, you can see *that* something is wrong but not *why*.

## The three pillars of observability

The three signals that together give you a complete picture of a distributed system's health are **logs**, **metrics**, and **traces**. Each answers a different question.

### Pillar 1: Logs

A **log** is a timestamped record of one discrete event in the system. Examples: a request arrived, an error occurred, a user logged in, a database query ran.

```txt
Logs answer: "What happened, exactly, at this specific moment?"
```

Example log output (structured JSON format — the industry standard):

```json
{
  "timestamp": "2025-03-15T14:32:01.234Z",
  "level": "error",
  "message": "Database query failed",
  "service": "user-service",
  "requestId": "req-abc123",
  "userId": "usr-456",
  "query": "SELECT * FROM users WHERE id = $1",
  "error": "connection timeout after 5000ms",
  "duration_ms": 5002
}
```

**Structured logging** (JSON) vs **unstructured logging** (plain text):

```ts
// ❌ Unstructured — human-readable but machine-unfriendly
console.log(`User ${userId} failed login attempt from IP ${ip}`);

// ✅ Structured — queryable, filterable, parseable by log aggregation tools
logger.warn('login_failed', {
  userId,
  ip,
  attempt: attemptCount,
  reason: 'invalid_password',
});
```

A log aggregation tool can filter and aggregate structured logs. Examples: Datadog, Grafana Loki, CloudWatch on AWS (Amazon Web Services), or the ELK Stack (Elasticsearch, Logstash, Kibana). You can ask it things like:

- "Show all errors for userId = usr-456 in the last hour"
- "Count login failures grouped by IP (Internet Protocol) address"
- "Alert when error count for service = payment-service > 50 in 5 minutes"

**Log levels** (from least to most severe):

- `DEBUG` — fine-grained diagnostic info. Turn it on only while debugging. Never run production at this level: too noisy, and it costs performance.
- `INFO` — normal, expected events: request received, user logged in, job completed. This is the default production level.
- `WARN` — something unexpected happened, but the system handled it. Examples: a retry that succeeded, a deprecated API call, a rate limit getting close. Investigate during a quiet period.
- `ERROR` — something failed and needs immediate attention: database unreachable, payment processing failed, unhandled exception.
- `FATAL` — the application cannot continue; the process is about to exit.

**Senior nuance #1 — what not to log:**

```ts
// ❌ Never log credentials or PII (Personally Identifiable Information —
//    data that can identify a specific person: name, email, phone, address)
logger.info('user login', { email, password });        // logs the password!
logger.info('payment', { cardNumber, cvv });           // PCI DSS violation

// ✅ Log identifiers, not sensitive data
logger.info('user login', { userId, email: maskEmail(email) });
logger.info('payment initiated', { userId, orderId, last4: card.last4 });
```

Logging credentials or PII breaks both security rules and the law. PII is personally identifiable information: a name, email, phone number or address. Several regimes require you to protect it:

- **GDPR** — the European Union's General Data Protection Regulation.
- **PCI DSS** — the Payment Card Industry Data Security Standard.
- **HIPAA** — the United States Health Insurance Portability and Accountability Act, for health data.

Many companies have been fined for logging emails or phone numbers.

### Pillar 2: Metrics

A **metric** is a numeric measurement of a system property, sampled over time. Metrics are aggregated — they tell you *how much* or *how fast*, not *what specifically happened*.

```txt
Metrics answer: "How is the system performing overall, over time?"
```

The four "golden signals", named in Google's SRE (Site Reliability Engineering) book:

1. **Latency** — how long requests take to process. Track p50, p95 and p99 percentiles; the average is usually misleading.
2. **Traffic** — how much demand the system is receiving: requests per second, messages per second, concurrent connections.
3. **Errors** — the rate of failed requests: 5xx responses over total responses, exception rate, timeout rate.
4. **Saturation** — how "full" the system is, how close to its capacity limit: processor, memory and disk usage, queue depth, database connection pool usage.

**Percentiles vs averages** — a critical distinction:

```txt
Imagine 100 requests: 99 take 10ms, 1 takes 10,000ms (10 seconds).
  Average latency:  ~110ms   ← looks fine
  p99 latency:    10,000ms   ← 1% wait 10 seconds — a crisis

The average masks outliers. Always monitor p95 and p99 for latency.
p99 = "99% of requests complete within this time"
      (the worst 1% are excluded — your most frustrated users)
```

Common metric types:

- **Counter** — a number that only goes up: total requests, total errors. Useful for computing rates, such as errors per second.
- **Gauge** — a value that can go up or down: current memory usage, queue depth, active connections.
- **Histogram** — distributes values into buckets, which is how latency percentiles are computed. How many requests took 0-10ms? 10-50ms? 50-200ms? More than 200ms?
- **Summary** — like a histogram, but percentiles are calculated on the client side. Less flexible for aggregation across many instances.

Example — instrumenting a Node.js Express app with Prometheus metrics (Prometheus is an open-source metrics collection and alerting system):

```ts
import { Registry, Counter, Histogram } from 'prom-client';

const registry = new Registry();

const httpRequestsTotal = new Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status_code'],
  registers: [registry],
});

const httpRequestDuration = new Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request duration in seconds',
  labelNames: ['method', 'route'],
  buckets: [0.01, 0.05, 0.1, 0.5, 1, 5],   // bucket boundaries in seconds
  registers: [registry],
});

// Middleware to instrument all requests
app.use((req, res, next) => {
  const end = httpRequestDuration.startTimer({ method: req.method, route: req.path });
  res.on('finish', () => {
    httpRequestsTotal.inc({
      method: req.method,
      route: req.path,
      status_code: res.statusCode,
    });
    end();   // records the duration
  });
  next();
});

// Expose metrics endpoint for Prometheus to scrape
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', registry.contentType);
  res.end(await registry.metrics());
});
```

### Pillar 3: Distributed Tracing

A **trace** follows one request as it travels through every service and component of a distributed system. It records how much time was spent at each step.

```txt
Traces answer: "What is the full journey of this specific request,
               and where exactly did it slow down or fail?"
```

In a monolithic application, a single stack trace tells you everything. In a microservices architecture, a single user-facing request might touch 8 services:

```txt
User request: "Load user dashboard"
  │
  ├── API Gateway (2ms)
  │   │
  │   ├── Auth Service — verify JWT (5ms)
  │   │
  │   ├── User Service — fetch user profile (8ms)
  │   │   └── PostgreSQL query (6ms)
  │   │
  │   └── Feed Service — fetch activity feed (230ms)  ← 🐌 SLOW
  │       ├── Redis cache check (1ms) — MISS
  │       └── PostgreSQL query (225ms)  ← THE BOTTLENECK
  │
  Total: 245ms
```

Without tracing, you see that the dashboard loads in 245ms — slow. With tracing, you can see immediately that the Feed Service's PostgreSQL query is responsible for 225ms (92%) of the total time.

**How tracing works:**

Each request is assigned a unique **trace ID** at the entry point (the API Gateway or first service). As the request passes through each service, it carries this ID in a header: `traceparent`, from the W3C (World Wide Web Consortium) Trace Context standard. Each service creates a **span** — a named, timed unit of work within the trace.

```txt
Trace ID: abc-123

  Span: "api-gateway"     [0ms ─────────────────────────── 245ms]
    Span: "auth-service"  [2ms ─────── 7ms]
    Span: "user-service"  [7ms ─────────── 15ms]
      Span: "db-query"    [9ms ──────── 15ms]
    Span: "feed-service"  [15ms ─────────────────────────── 245ms]
      Span: "redis-check" [15ms ── 16ms]
      Span: "db-query"    [16ms ─────────────────────────── 241ms]
```

The OpenTelemetry (OTel) standard has become the industry standard for instrumentation. It is a vendor-neutral SDK (software development kit). Instrument your code once, and it exports traces — plus metrics and logs — to any backend: Jaeger, Zipkin, Datadog, Honeycomb.

```ts
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { HttpInstrumentation } from '@opentelemetry/instrumentation-http';
import { ExpressInstrumentation } from '@opentelemetry/instrumentation-express';
import { PgInstrumentation } from '@opentelemetry/instrumentation-pg';

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter({
    url: 'http://otel-collector:4318/v1/traces',
  }),
  instrumentations: [
    new HttpInstrumentation(),      // auto-instruments all HTTP requests/responses
    new ExpressInstrumentation(),   // auto-instruments Express routes and middleware
    new PgInstrumentation(),        // auto-instruments PostgreSQL queries
  ],
});

sdk.start();
```

With this setup, every HTTP request, Express route handler, and database query is automatically traced — zero manual instrumentation needed for the common cases.

## APM — Application Performance Monitoring

**APM** (Application Performance Monitoring) is a category of tools that combines metrics, traces, and sometimes logs into a unified view specifically focused on application-level performance.

APM tools typically provide:

- **Transaction tracing**: automatically trace every request through your app
- **Code-level performance profiling**: identify which line of code / which function call is slow
- **Error tracking**: group similar errors, show stack traces, count occurrences
- **Dependency mapping**: visualize which services call which other services
- **Alerting**: notify when performance degrades below a threshold

Popular APM tools:

- **Datadog APM** — SaaS (software as a service), excellent auto-instrumentation, broad ecosystem. Expensive at scale. "Datadog APM" is their tracing product; the same platform also does metrics and logs.
- **New Relic** — SaaS, one of the original APM tools. Good for traditional monoliths, newer features for microservices.
- **Sentry** — primarily error tracking, with performance monitoring added on top. Very popular in the frontend and fullstack world. An open-source self-hosted version exists.
- **Elastic APM** — part of the ELK Stack (Elasticsearch, Logstash, Kibana). Open-source, a good fit for teams already running Elasticsearch.
- **Grafana Stack** — the open-source option: Grafana for dashboards, Prometheus for metrics, Loki for logs, Tempo for traces. More setup work, but completely free.

The difference between an APM tool and the individual pillars:

| Tool type | What it does |
|---|---|
| Logging (Grafana Loki, CloudWatch Logs) | Stores and queries logs |
| Metrics (Prometheus, Datadog Metrics) | Stores and queries metrics |
| Tracing (Jaeger, Zipkin, Tempo) | Stores and queries traces |
| APM platform (Datadog, New Relic, Sentry) | Combines all three behind one interface focused on application health |

## Uptime monitoring

**Uptime monitoring** is the simplest form of monitoring. On a schedule, send a request to your service from outside, and alert if the answer is wrong.

```txt
Every minute, from servers in 5 regions:
  HTTP GET https://api.myapp.com/health
    → expect: HTTP 200 within 3 seconds
    → after 2 failures: alert via PagerDuty, Slack or email
```

This is "external" monitoring — it simulates what a real user experiences when they try to reach your service. It is distinct from "internal" monitoring (metrics from inside the application). An application can be healthy internally and still unreachable from outside. Causes: a changed firewall rule, DNS (Domain Name System) propagation, a misconfigured load balancer.

Popular uptime monitoring services:

- **Pingdom** — SaaS, monitoring from 100+ locations, alerts by text message and email.
- **UptimeRobot** — has a free tier with a 5-minute interval. Popular for side projects.
- **Checkly** — monitors with synthetic scripts, not just pings. It can replay a user flow: log in, add to cart, check out.
- **AWS CloudWatch** — built in if you are on AWS. It can create health checks by URL.
- **StatusPage.io** — not monitoring itself, but a public status page service — what you see at status.stripe.com or githubstatus.com.

## Health check endpoints

A **health check endpoint** is a dedicated API route that reports whether the service is healthy and ready to take traffic. It is not there for users but for the infrastructure: Kubernetes and the load balancer poll it.

```txt
GET /health
  → 200 OK
    {"status": "ok"}
  → 503 Service Unavailable
    {"status": "degraded", "reason": "database unreachable"}
```

There are two distinct types of health checks, and confusing them causes problems:

**Liveness probe** — "Is the process alive? Should it be restarted?"

A liveness check fails if the application process is in an unrecoverable state (deadlocked, out of memory, event loop blocked). The response to a failed liveness check is to **restart the container**.

```ts
// Liveness: just confirm the process can respond
app.get('/health/live', (_req, res) => {
  res.status(200).json({ status: 'ok' });
});
```

**Readiness probe** — "Is the service ready to receive traffic?"

A readiness check fails when the application is running but not yet able to serve requests. It may still be warming up, or the database connection or the cache may not be ready. The response to a failed readiness check is to **remove the pod from the load balancer** — but not restart it.

```ts
// Readiness: check that all dependencies are reachable
app.get('/health/ready', async (_req, res) => {
  const checks = await Promise.allSettled([
    db.query('SELECT 1'),        // database reachable?
    redis.ping(),                // redis reachable?
  ]);

  const dbOk = checks[0].status === 'fulfilled';
  const redisOk = checks[1].status === 'fulfilled';

  if (dbOk && redisOk) {
    res.status(200).json({ status: 'ok', db: 'ok', redis: 'ok' });
  } else {
    res.status(503).json({
      status: 'degraded',
      db: dbOk ? 'ok' : 'unreachable',
      redis: redisOk ? 'ok' : 'unreachable',
    });
  }
});
```

Kubernetes uses both probes:

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 3000
  initialDelaySeconds: 10     # wait 10s before first check (app startup time)
  periodSeconds: 10
  failureThreshold: 3         # restart after 3 consecutive failures

readinessProbe:
  httpGet:
    path: /health/ready
    port: 3000
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 2         # remove from load balancer after 2 failures
```

### Senior nuance #2 — health check anti-patterns

```ts
// ❌ Anti-pattern 1: health check that can cause a cascade failure
// If your service has 50 pods, and each /health does a DB query,
// you're running 50 queries/minute just for health checks.
// Under high load, these can overwhelm the database.
app.get('/health', async (req, res) => {
  await db.query('SELECT COUNT(*) FROM users');   // full table scan — bad!
  res.json({ status: 'ok' });
});

// ✅ Use a cheap, targeted query
app.get('/health/ready', async (req, res) => {
  await db.query('SELECT 1');   // just checks connectivity, not data
  res.json({ status: 'ok' });
});

// ❌ Anti-pattern 2: liveness check that checks external dependencies
// If your database is down, a failing liveness probe restarts all pods.
// But restarting pods doesn't fix the database — you get a restart loop.
// Liveness should ONLY check if THIS PROCESS is alive.
app.get('/health/live', async (req, res) => {
  await db.query('SELECT 1');   // ← wrong for liveness
  res.json({ status: 'ok' });
});
```

## SLA, SLO, SLI — service level terminology

These three acronyms describe how reliability commitments are defined, measured and agreed. SLI is the service level indicator, SLO the service level objective, SLA the service level agreement. They are distinct layers:

| Acronym | What it is |
|---|---|
| SLI | What you measure |
| SLO | What you commit to internally |
| SLA | What you promise to customers, with consequences if you break it |

### SLI — Service Level Indicator

An **SLI** (Service Level Indicator) is a specific, quantifiable metric that represents how well the service is performing for users. It is the raw measurement.

Examples:

- **Availability** — successful requests divided by total requests, as a percentage.
- **Latency** — the share of requests completing in under 200ms.
- **Error rate** — the share of requests returning a 5xx status code.
- **Throughput** — transactions processed per second.

### SLO — Service Level Objective

An **SLO** (Service Level Objective) is an internal target for an SLI — the threshold below which you consider the service to be failing its users. It is a goal, not a promise to customers.

Examples:

- Availability at or above 99.9% over a rolling 30-day window.
- A p99 latency at or below 500ms for every API endpoint.
- An error rate under 0.1% in any 5-minute window.

**Error budget** is the idea that makes an SLO actionable. It is how much unreliability you are allowed before the SLO is violated.

```txt
SLO: 99.9% availability over 30 days
  30 days                = 43,200 minutes
  0.1% of 43,200 minutes = 43.2 minutes of downtime per month

Error budget = 43.2 minutes / month
```

Suppose you have already used 40 minutes this month. Only 3.2 minutes are left, so you freeze risky deploys until the new month and put engineering effort into reliability instead. If the budget is consistently unused, you can move faster: deploy more often, take more risks.

The error budget idea comes from Google's SRE book. It bridges the gap between product teams, who want to move fast, and ops teams, who want stability. It quantifies how much risk the system can afford, in units everyone understands.

### SLA — Service Level Agreement

An **SLA** (Service Level Agreement) is a contractual commitment between a service provider and a customer. It defines the expected level of service, and the consequences if that level is not met: credits, refunds, the right to terminate.

Examples:

- **AWS S3 (Simple Storage Service)** — 99.9% monthly uptime. Below 99% the customer gets a 10% service credit; below 95%, a 25% credit.
- **Stripe** — 99.99% API uptime. Downtime is compensated with service credits, not cash refunds. Read the fine print.
- **A typical enterprise SaaS contract** — 99.9% uptime. Below that, a pro-rated refund; below 95%, the customer may terminate.

The relationship between the three:

```txt
SLI (measurement) → SLO (internal target) → SLA (external promise)
```

An SLO is **stricter** than an SLA. If your SLA promises 99.9%, your internal SLO might be 99.95%. The gap between them is your safety margin. Drift toward the SLO, and you catch and fix it before you breach the SLA and pay for it.

**Nines of availability** — a common shorthand:

| Shorthand | Availability | Downtime per year |
|---|---|---|
| Two nines | 99% | 3.65 days (87.6 hours) |
| Three nines | 99.9% | 8.76 hours |
| Four nines | 99.99% | 52.6 minutes |
| Five nines | 99.999% | 5.26 minutes |

Five nines is extremely hard to reach, even for the largest companies. Most SaaS products target three or four nines. Four nines usually requires multi-region redundancy, zero-downtime deployments, automated failover and extensive runbooks.

## Putting it together: a practical observability setup

For a Node.js + PostgreSQL application deployed on AWS:

- **Logs.** The application writes structured JSON to stdout; it goes to CloudWatch Logs, Datadog or Loki. Retention: 30 days for INFO, 90 days for ERROR. Alert via PagerDuty on more than 10 ERROR logs in 5 minutes.
- **Metrics.** The Prometheus client library exposes a `/metrics` endpoint; Prometheus scrapes it every 15 seconds. Grafana dashboards show request rate, p95 and p99 latency, error rate and database pool size. Alert to Slack when p99 latency exceeds 1s for 5 minutes, to PagerDuty when the error rate exceeds 1% for 2 minutes.
- **Traces.** The OpenTelemetry SDK exports to Jaeger, Tempo or Datadog APM. Sample rate: 100% in staging, 10% in production; full sampling is expensive. Use traces to debug slow requests and understand cross-service dependencies.
- **Uptime monitoring.** UptimeRobot or Checkly pings `/health/live` every 60 seconds from 3 regions. Alert by text message and Slack after 2 consecutive failures.
- **Health checks.** Kubernetes liveness on `/health/live`, which only checks that the process responds. Kubernetes readiness on `/health/ready`, which checks database and Redis connectivity.

## Common interview traps

- **"Monitoring and observability are the same thing"** — monitoring is the practice of watching predefined metrics. Observability is a property of the system that lets you discover unknown failure modes. A system can be heavily monitored but poorly observable.

- **"We log everything with console.log"** — signals an unfamiliarity with production logging. The problems: `console.log` is synchronous and briefly blocks the event loop. It produces unstructured strings. It cannot be filtered by level. It carries no metadata — no service name, request ID or user ID. Use a structured logger: winston, pino.

- **Not knowing the difference between liveness and readiness probes** — a very common interview question. Confusing them causes real operational damage. A liveness probe that checks external dependencies will restart every pod when the database goes down. A readiness probe would just take those pods out of the load balancer.

- **"Our SLA is 99.99%"** — interviewers will ask: "What's your error budget? How do you track it?" If you can't answer, it signals you don't actually operate at that level. Know the number of minutes of allowed downtime that corresponds to your SLA.

- **Confusing SLI, SLO, and SLA** — a very common interview confusion, especially on senior/staff roles. Remember: SLI = measurement, SLO = internal target, SLA = customer contract. SLO is stricter than SLA to provide a safety buffer.

- **"We use average latency as our metric"** — the average masks outliers. A p99 latency of 3 seconds means 1% of your users wait 3 seconds. The average may still look like 200ms, because 99% of requests are fast. Always monitor percentiles.

- **"We have a /health endpoint that just returns 200"** — fine for uptime monitoring, but not sufficient for Kubernetes liveness/readiness. A process can return 200 while being in a degraded state (database unreachable but returning cached data). The readiness probe should actually test dependency connectivity.
