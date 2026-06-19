# Monitoring and Observability

## Monitoring vs Observability — the distinction

These two terms are often used interchangeably, but they describe different things:

**Monitoring** is the practice of collecting predefined signals from a system and alerting when those signals exceed thresholds. It answers: "Is something wrong?"

**Observability** is the property of a system that allows you to understand its internal state by examining its external outputs. It answers: "Why is something wrong?" — even for failure modes you didn't anticipate when you built the system.

```txt
Monitoring (known unknowns):
  "Alert me when error rate > 1%" — you knew errors were a thing to watch

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

A **log** is a timestamped record of a discrete event that happened in the system — a request arrived, an error occurred, a user logged in, a database query ran.

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

With structured logs, your log aggregation tool (Datadog, Grafana Loki, AWS CloudWatch, ELK Stack — Elasticsearch + Logstash + Kibana) can let you filter and aggregate:
- "Show all errors for userId = usr-456 in the last hour"
- "Count login failures grouped by IP address"
- "Alert when error count for service = payment-service > 50 in 5 minutes"

**Log levels** (from least to most severe):

```txt
DEBUG   → fine-grained diagnostic info; enable only when debugging;
           never log in production at DEBUG level (too noisy, performance cost)

INFO    → normal, expected events (request received, user logged in,
           job completed); the default production log level

WARN    → something unexpected happened but the system handled it
           (retry succeeded after first attempt, deprecated API used,
           rate limit approaching); investigate during a quiet period

ERROR   → something failed that needs immediate attention
           (database unreachable, payment processing failed, unhandled exception)

FATAL   → the application cannot continue; process is about to exit
```

**Senior nuance #1 — what NOT to log:**

```ts
// ❌ Never log credentials or PII (Personally Identifiable Information —
//    data that can identify a specific person: name, email, phone, address)
logger.info('user login', { email, password });        // logs the password!
logger.info('payment', { cardNumber, cvv });           // PCI DSS violation

// ✅ Log identifiers, not sensitive data
logger.info('user login', { userId, email: maskEmail(email) });
logger.info('payment initiated', { userId, orderId, last4: card.last4 });
```

Logging PII or credentials is a security/compliance violation (GDPR, PCI DSS, HIPAA — different regulatory frameworks, all require protecting user data). Many companies have been fined for logging emails or phone numbers.

### Pillar 2: Metrics

A **metric** is a numeric measurement of a system property, sampled over time. Metrics are aggregated — they tell you *how much* or *how fast*, not *what specifically happened*.

```txt
Metrics answer: "How is the system performing overall, over time?"
```

The four "golden signals" (coined by Google's SRE — Site Reliability Engineering — book):

```txt
1. Latency  — how long requests take to process
              (p50, p95, p99 — percentiles; avg is usually misleading)

2. Traffic  — how much demand the system is receiving
              (requests per second, messages per second, concurrent connections)

3. Errors   — the rate of failed requests
              (5xx responses / total responses, exception rate, timeout rate)

4. Saturation — how "full" the system is; how close to its capacity limit
               (CPU %, memory %, disk %, queue depth, DB connection pool usage)
```

**Percentiles vs averages** — a critical distinction:

```txt
Imagine 100 requests, 99 take 10ms, 1 takes 10,000ms (10 seconds):
  Average latency:  ~110ms  ← looks fine
  p99 latency:    10,000ms  ← 1% of users wait 10 seconds — this is a crisis

Average masks outliers. Always monitor percentiles (p95, p99) for latency.
p99 = "99% of requests complete within this time"
      (the worst 1% are excluded — they are your most frustrated users)
```

Common metric types:

```txt
Counter    → monotonically increasing number (total requests, total errors)
             only goes up; useful for computing rates (errors/second)

Gauge      → a value that can go up or down (current memory usage, queue depth,
             number of active connections)

Histogram  → distributes values into buckets; used for latency percentiles
             (how many requests took 0-10ms? 10-50ms? 50-200ms? >200ms?)

Summary    → similar to histogram but calculates percentiles on the client side;
             less flexible for aggregation across multiple instances
```

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

A **trace** follows a single request as it travels through all the services and components of a distributed system, recording how much time was spent in each step.

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

Each request is assigned a unique **trace ID** at the entry point (the API Gateway or first service). As the request passes through each service, it carries this ID in a header (`traceparent` in the W3C Trace Context standard). Each service creates a **span** — a named, timed unit of work within the trace.

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

The OpenTelemetry (OTel) standard has become the industry standard for instrumentation. It is a vendor-neutral SDK that instruments your code once and exports traces (and metrics and logs) to any backend — Jaeger, Zipkin, Datadog, Honeycomb, etc.

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

```txt
Datadog APM     → SaaS; excellent auto-instrumentation; broad ecosystem;
                   expensive at scale; "Datadog APM" = their tracing product
                   (Datadog also does metrics and logs under the same platform)

New Relic       → SaaS; one of the original APM tools; good for traditional
                   monoliths; newer features for microservices

Sentry          → primarily error tracking, but also adds performance monitoring;
                   very popular in the frontend/fullstack world;
                   open-source self-hostable version available

Elastic APM     → part of the ELK Stack (Elasticsearch, Logstash, Kibana);
                   open-source; good for teams already using Elasticsearch

Grafana Stack   → open-source; Grafana (dashboards) + Prometheus (metrics) +
(OSS option)      Loki (logs) + Tempo (traces); more setup work but fully free
```

The difference between an APM tool and the individual pillars:

```txt
Logging tool (Grafana Loki, CloudWatch Logs)  → stores and queries logs
Metrics tool (Prometheus, Datadog Metrics)     → stores and queries metrics
Tracing tool (Jaeger, Zipkin, Tempo)           → stores and queries traces
APM platform (Datadog, New Relic, Sentry)      → combines all three with a UI
                                                  focused on application health
```

## Uptime monitoring

**Uptime monitoring** is the simplest form of monitoring: periodically send a request to your service from an external location and alert if it doesn't respond correctly.

```txt
Every 1 minute, from servers in 5 regions:
  HTTP GET https://api.myapp.com/health
    → expect: HTTP 200 within 3 seconds
    → if fails 2 consecutive times: alert via PagerDuty / Slack / email
```

This is "external" monitoring — it simulates what a real user experiences when they try to reach your service. It is distinct from "internal" monitoring (metrics from inside the application). An application can be running and reporting healthy internally while being unreachable externally (firewall rule changed, DNS propagation issue, load balancer misconfiguration).

Popular uptime monitoring services:

```txt
Pingdom         → SaaS; monitoring from 100+ locations; SMS + email alerts
UptimeRobot     → free tier available (5-minute interval); popular for side projects
Checkly         → monitors via synthetic scripts (not just pings — can simulate
                   a user flow: login → add to cart → checkout)
AWS CloudWatch  → built-in if you're on AWS; can create URL health checks
StatusPage.io   → not monitoring itself, but a public status page service
                   (what you see at status.stripe.com, githubstatus.com)
```

## Health check endpoints

A **health check endpoint** is a dedicated API route in your application that reports whether the service is healthy and ready to accept traffic. It is not a user-facing feature — it is infrastructure plumbing.

```txt
GET /health  →  200 OK  {"status": "ok"}
              or
              503 Service Unavailable  {"status": "degraded", "reason": "database unreachable"}
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

A readiness check fails if the application is running but not yet ready to serve requests (still warming up, database connection not yet established, cache not populated). The response to a failed readiness check is to **remove the pod from the load balancer** — but not restart it.

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

These three acronyms describe how reliability commitments are defined, measured, and agreed upon. They are distinct layers:

```txt
SLI → what you measure
SLO → what you commit to internally
SLA → what you promise to customers (with consequences if broken)
```

### SLI — Service Level Indicator

An **SLI** (Service Level Indicator) is a specific, quantifiable metric that represents how well the service is performing for users. It is the raw measurement.

```txt
Examples of SLIs:
  - Availability SLI:  (number of successful requests) / (total requests) × 100%
  - Latency SLI:       percentage of requests completing in < 200ms
  - Error rate SLI:    percentage of requests returning a 5xx status code
  - Throughput SLI:    number of transactions processed per second
```

### SLO — Service Level Objective

An **SLO** (Service Level Objective) is an internal target for an SLI — the threshold below which you consider the service to be failing its users. It is a goal, not a promise to customers.

```txt
Examples of SLOs:
  - "Availability ≥ 99.9% over a rolling 30-day window"
  - "p99 latency ≤ 500ms for all API endpoints"
  - "Error rate < 0.1% over any 5-minute window"
```

**Error budget** — the concept that makes SLOs actionable: the amount of unreliability you are allowed before your SLO is violated.

```txt
SLO: 99.9% availability over 30 days
  30 days = 43,200 minutes
  0.1% of 43,200 minutes = 43.2 minutes of allowed downtime per month

Error budget = 43.2 minutes / month

If you've used 40 minutes already this month → only 3.2 minutes of error budget left
→ freeze risky deploys until the new month begins
→ focus engineering effort on reliability improvements

If error budget is consistently unused → you can afford to move faster,
deploy more often, take more risks
```

The error budget concept, from Google's SRE book, bridges the gap between product teams (who want to move fast) and ops teams (who want stability): it quantifies how much risk the system can afford, in units everyone understands.

### SLA — Service Level Agreement

An **SLA** (Service Level Agreement) is a contractual commitment between a service provider and a customer that defines the expected level of service and the consequences (credits, refunds, termination rights) if that level is not met.

```txt
Examples of SLAs:
  AWS S3 SLA:  99.9% monthly uptime; if uptime < 99%, customer gets 10% service credit
               if uptime < 95%, customer gets 25% service credit

  Stripe SLA:  99.99% API uptime; downtime is credited as service credits
               (not actual money refunds — read the fine print)

  Enterprise SaaS SLA: 99.9% uptime; < 99.9% → customer gets pro-rated refund;
                       < 95% → customer has right to terminate contract
```

The relationship between the three:

```txt
SLI (measurement) → SLO (internal target) → SLA (external commitment)

SLO is STRICTER than SLA:
  If your SLA promises 99.9%, your internal SLO might be 99.95%.
  The gap between SLO and SLA is your "safety margin" —
  if you're falling toward your SLO, you catch and fix it
  before you breach your SLA and face financial consequences.
```

**Nines of availability** — a common shorthand:

```txt
"Two nines"   = 99%    = 3.65 days of downtime/year   (87.6 hours)
"Three nines" = 99.9%  = 8.76 hours of downtime/year
"Four nines"  = 99.99% = 52.6 minutes of downtime/year
"Five nines"  = 99.999%= 5.26 minutes of downtime/year

Note: "five nines" is extremely difficult to achieve even for the largest
companies. Most SaaS products target "three nines" or "four nines."
Achieving "four nines" typically requires: multi-region redundancy,
zero-downtime deployments, automated failover, extensive runbooks.
```

## Putting it together: a practical observability setup

For a Node.js + PostgreSQL application deployed on AWS:

```txt
Logs:
  Application → structured JSON to stdout → CloudWatch Logs (or Datadog/Loki)
  Retention: 30 days for INFO, 90 days for ERROR
  Alerts: > 10 ERROR logs in 5 minutes → PagerDuty alert

Metrics:
  Application → Prometheus client library → /metrics endpoint
  Prometheus scrapes /metrics every 15 seconds
  Grafana dashboards: request rate, p95/p99 latency, error rate, DB pool size
  Alerts: p99 latency > 1s for 5 minutes → Slack alert
          error rate > 1% for 2 minutes → PagerDuty alert

Traces:
  Application → OpenTelemetry SDK → Jaeger / Tempo / Datadog APM
  Sample rate: 100% in staging, 10% in production (full sampling is expensive)
  Use for: debugging slow requests, understanding cross-service dependencies

Uptime monitoring:
  UptimeRobot / Checkly pings /health/live every 60 seconds from 3 regions
  Alert if 2 consecutive failures: SMS + Slack

Health checks:
  Kubernetes liveness: /health/live (just process responsiveness)
  Kubernetes readiness: /health/ready (checks DB + Redis connectivity)
```

## Common interview traps

- **"Monitoring and observability are the same thing"** — monitoring is a practice of watching predefined metrics; observability is a property of the system that allows discovery of unknown failure modes. A system can be heavily monitored but poorly observable.

- **"We log everything with console.log"** — signals an unfamiliarity with production logging. The problems: console.log is synchronous (blocks the event loop briefly); it produces unstructured strings; it cannot be configured for level filtering; it doesn't include metadata (service name, request ID, user ID). Use a structured logger (winston, pino).

- **Not knowing the difference between liveness and readiness probes** — a very common interview question. Confusing them leads to real operational problems: a readiness probe checking external dependencies that causes pod restarts when the database is down (instead of just removing the pod from the load balancer).

- **"Our SLA is 99.99%"** — interviewers will ask: "What's your error budget? How do you track it?" If you can't answer, it signals you don't actually operate at that level. Know the number of minutes of allowed downtime that corresponds to your SLA.

- **Confusing SLI, SLO, and SLA** — a very common interview confusion, especially on senior/staff roles. Remember: SLI = measurement, SLO = internal target, SLA = customer contract. SLO is stricter than SLA to provide a safety buffer.

- **"We use average latency as our metric"** — average masks outliers. p99 latency of 3 seconds means 1% of your users wait 3 seconds, but the average might look like 200ms because 99% of requests are fast. Always monitor percentiles.

- **"We have a /health endpoint that just returns 200"** — fine for uptime monitoring, but not sufficient for Kubernetes liveness/readiness. A process can return 200 while being in a degraded state (database unreachable but returning cached data). The readiness probe should actually test dependency connectivity.
