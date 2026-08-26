# Deployment Strategies

## Why deployment strategy matters

Deploying new code to production is the riskiest moment in the software delivery lifecycle. If something goes wrong — a bug slipped through testing, a performance regression, a broken third-party integration — users are affected immediately. Deployment strategies are techniques for controlling *how* a new version of code replaces the old version, with the goals of:

1. **Minimizing downtime** — users experience the service as continuously available
2. **Limiting the blast radius** — the share of users a bad version can reach. If the new version has a bug, only a fraction of them see it before you catch it
3. **Enabling fast rollback** — if something is wrong, you can return to the previous state quickly

Each strategy makes different tradeoffs between complexity, resource cost, and risk.

## Zero-downtime deployment

**Zero-downtime deployment** is the overarching requirement that a deployment should not make the service unavailable to users — not even for a second. This sounds obvious, but it is non-trivial to achieve.

The naive approach — stop the old version, start the new version — creates a gap:

```txt
Naive (downtime) deployment:
  t=0s    Old version: running, serving traffic
  t=10s   STOP old version   ← users get "connection refused" or 503
  t=25s   START new version  ← 15 seconds of downtime
  t=30s   New version: running, serving traffic
```

All the strategies below are variations on how to eliminate that gap.

Zero-downtime deployment has a prerequisite: **your application must handle graceful shutdown.** The orchestrator sends a `SIGTERM` signal before it stops the process. On that signal the application must:

1. Stop accepting new connections
2. Finish processing in-flight requests
3. Close database connections cleanly
4. Exit with code 0

Without graceful shutdown, even the most sophisticated deployment strategy will drop requests at the moment a container is stopped.

## Rolling deployment

**Rolling deployment** (also called a *rolling update*) replaces old instances with new ones **incrementally**, while the service keeps running. It swaps one instance at a time, or a few at a time.

```txt
Service has 4 instances (pods/containers/VMs) of v1:
  [v1] [v1] [v1] [v1]   ← all serving traffic

Step 1: replace one instance
  [v2] [v1] [v1] [v1]   ← v2 starts, v1 is drained and stopped

Step 2: replace another
  [v2] [v2] [v1] [v1]

Step 3:
  [v2] [v2] [v2] [v1]

Step 4: complete
  [v2] [v2] [v2] [v2]   ← all instances running v2
```

**How a single instance is replaced (zero-downtime per instance):**

1. The new v2 instance starts and passes its health check.
2. The load balancer or proxy adds v2 to the routing pool.
3. The load balancer drains v1: no new requests go there, and it waits for the in-flight ones to finish. The drain timeout is typically 30–60 seconds.
4. The v1 instance is stopped once the drain completes.

**Advantages:**

- Simple to implement — built into Kubernetes, Amazon ECS (Elastic Container Service) and most platform-as-a-service (PaaS) providers.
- No extra infrastructure needed — it reuses the instances you already have.
- Low resource cost, compared to blue-green.

**Disadvantages:**

- During the rollout v1 and v2 run at once, so a request may hit either version. Inconsistent responses are possible.
- If v2 has a bug, some users see it and others do not. The share grows as the rollout progresses.
- Rollback means another rolling update in reverse, which is slow.
- Database migrations must stay compatible with both v1 and v2, since both run during the rollout.

Kubernetes rolling deployment configuration:

```yaml
# kubernetes deployment.yaml
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # allow at most 1 extra pod above desired count during update
      maxUnavailable: 0  # never go below desired count during update (zero-downtime)
  template:
    spec:
      containers:
        - name: app
          image: my-app:v2
          readinessProbe:         # pod is only added to load balancer AFTER this passes
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 5
```

The `readinessProbe` is what makes a rolling deployment zero-downtime. A pod receives traffic only after the probe passes. A buggy v2 that fails its health check therefore never sees real user traffic: the rollout stalls and alerts fire.

## Blue-green deployment

**Blue-green deployment** maintains **two identical production environments** — called "blue" and "green" — and switches traffic between them instantaneously.

```txt
Current state — "blue" is live:
  [blue:  v1 v1 v1 v1]  ←── 100% of user traffic
  [green: idle       ]      standing by (or absent)

Deploy v2 to green:
  [blue:  v1 v1 v1 v1]  ←── 100% of user traffic, still
  [green: v2 v2 v2 v2]      deployed and tested, no real traffic

Switch the load balancer (or DNS) over to green:
  [blue:  v1 v1 v1 v1]      now idle, kept for rollback
  [green: v2 v2 v2 v2]  ←── 100% of user traffic

If v2 has a bug, switch back — that takes seconds:
  [blue:  v1 v1 v1 v1]  ←── 100% of user traffic again
  [green: v2 v2 v2 v2]      idle again
```

The switch itself is a small change: a DNS (Domain Name System) record, a load balancer rule, or a reverse proxy config reload. Any of the three takes under a second.

**Advantages:**

- Instant rollback — switch the load balancer back, in seconds rather than minutes.
- No mixed-version traffic. At any point in time every user sees the same version.
- The full v2 environment can be tested in isolation before the switch — smoke tests, load tests, sign-off from QA (quality assurance).

**Disadvantages:**

- Double infrastructure cost: two full production environments have to exist at the same time.
- Database migrations get harder. If v2 changes the schema, v1 must keep working with it until the switch, so migrations have to be backward-compatible.
- Switching by DNS is not instant: a record carries a propagation delay set by its TTL (time to live). Switch at the load balancer instead.

Blue-green with a reverse proxy (nginx or similar):

```nginx
# Switch by updating the upstream and reloading nginx (zero-downtime reload)
upstream app {
    server green:3000;   # was: server blue:3000;
}
```

Or with a cloud load balancer. On AWS (Amazon Web Services) you repoint the listener of an Application Load Balancer. On Google Cloud you update the Backend Service instead:

```bash
# AWS: switch the load balancer listener rule to the green target group
aws elbv2 modify-listener \
  --listener-arn arn:aws:elasticloadbalancing:... \
  --default-actions Type=forward,TargetGroupArn=<green-target-group-arn>
```

## Canary release

A **canary release** sends a **small percentage of real user traffic** to the new version, while the majority still hits the old one. You watch the new version for errors and performance regressions, then raise its share step by step up to 100%. The name comes from the canary in a coal mine: miners sent the bird in first to detect toxic gas.

```txt
Phase 1: 5% canary
  [v2] ←── 5% of traffic (the "canary")
  [v1] [v1] [v1] [v1] ←── 95% of traffic

  Monitor: error rate, latency, business metrics
  If all looks good → increase

Phase 2: 20% canary
  [v2] [v2] ←── 20% of traffic
  [v1] [v1] [v1] [v1] ←── 80% of traffic

Phase 3: 50%
  ...

Phase 4: 100% (rollout complete)
  [v2] [v2] [v2] [v2] ←── 100% of traffic
  (v1 retired)
```

The key difference from a rolling deployment is what you control. A rolling update replaces instances one by one until every instance is new. You cannot say "send 5% of the traffic to v2" here — the split is only a side effect of how far the rollout got. A canary controls the *traffic split* directly, by weight in the load balancer rather than by instance count.

**Where canary is implemented:**

- **Load balancer weighted routing** — weighted target groups on an AWS Application Load Balancer, `weight` in nginx, Kubernetes Gateway API
- **Service mesh** (Istio, Linkerd) — fine-grained traffic control at the network layer without touching the application
- **Platform-level** — Vercel (traffic splitting), AWS CodeDeploy with canary configuration

```yaml
# Kubernetes Gateway API weighted traffic split (v1.0 of Gateway API)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
spec:
  rules:
    - backendRefs:
        - name: app-v1
          port: 3000
          weight: 95
        - name: app-v2
          port: 3000
          weight: 5      # 5% canary
```

**Advantages:**

- Real user traffic tests the new version and catches bugs that staging missed.
- Small blast radius: a bug in v2 initially reaches only 5% of users.
- A gradual rollout gives time to spot performance regressions that appear only under real load.

**Disadvantages:**

- Both versions run at the same time, with the same database-migration constraints as a rolling update.
- You need a load balancer that supports weighted routing.
- Observability has to be set up per version, not just per service.
- Canary analysis — deciding when it is safe to raise the share — is either automated (Argo Rollouts, Flagger) or manual. Manual analysis is error-prone under time pressure.

## Feature flags

A **feature flag** is a switch in the application code that turns a feature on or off at runtime, without deploying new code. It is also called a *feature toggle* or a *feature switch*.

**Feature flags are not a deployment strategy.** They are a code-level technique that complements deployment strategies. The distinction:

| Mechanism | What it controls |
|---|---|
| Deployment strategy | *How* new code reaches the production environment: rolling, blue-green or canary. |
| Feature flag | *Whether* a feature in already-deployed code is active for a given user. The code is in production either way; the flag controls visibility. |

Basic implementation:

```ts
// Feature flag checked at runtime
const ENABLE_NEW_CHECKOUT = process.env.ENABLE_NEW_CHECKOUT === 'true';

app.get('/checkout', (req, res) => {
  if (ENABLE_NEW_CHECKOUT) {
    return newCheckoutHandler(req, res);
  }
  return legacyCheckoutHandler(req, res);
});
```

**Why feature flags fit CI/CD (continuous integration and continuous delivery):**

```txt
Without feature flags:
  Feature branch → PR → merge when done → deploy → feature is live
  Problem: large long-lived feature branches → integration hell

With feature flags:
  Feature code merged to main behind a flag (flag = off)
  → deploys happen normally, flag-gated code is inert
  → QA/testing on production with flag = on for internal users only
  → gradual rollout: enable for 1% → 10% → 50% → 100%
  → instant rollback: flip the flag off (no new deploy needed)
```

**Feature flag services** (more powerful than environment variables):

```ts
// Using a feature flag service (LaunchDarkly, GrowthBook, Unleash, etc.)
const variation = await flagClient.variation('new-checkout', user, false);

if (variation) {
  return newCheckoutHandler(req, res);
}
return legacyCheckoutHandler(req, res);
```

These services allow:
- **User targeting** — enable for specific users, groups, or percentage
- **Gradual rollout** — start at 1%, increase over time
- **Kill switch** — disable instantly across all users without a deploy
- **A/B testing** — measure business impact of the new feature before full rollout

**The critical difference with canary release:**

| | Canary release | Feature flag |
|---|---|---|
| Where the split happens | Infrastructure, in the load balancer | Application, inside the code |
| Who serves the request | Different servers | The same server, on a different code path |
| What is deployed | Both the v1 code and the v2 code | One version of the code |

## Rollback strategies

No deployment strategy eliminates the possibility of something going wrong. Every deployment plan must include a rollback path.

### Rollback in rolling deployment

Rolling rollback = another rolling update, but deploying the previous image tag:

```bash
# Kubernetes: roll back to previous deployment
kubectl rollout undo deployment/my-app

# Or to a specific revision
kubectl rollout undo deployment/my-app --to-revision=3

# Check rollout status
kubectl rollout status deployment/my-app
```

Downside: rollback takes as long as the original rollout. If a full rollout takes 5 minutes, so does the rollback.

### Rollback in blue-green deployment

```bash
# Switch load balancer back to blue (the previous version that's still running)
# This takes seconds — blue was never torn down
aws elbv2 modify-listener --default-actions Type=forward,TargetGroupArn=<blue-arn>
```

This is why blue-green's double infrastructure cost is often worth it: rollback is instantaneous.

### Rollback in canary release

```yaml
# Set canary weight to 0 — all traffic back to stable
# (using the Argo Rollouts CRD — CustomResourceDefinition)
kubectl argo rollouts set weight my-app 0
# Or simply abort the rollout
kubectl argo rollouts abort my-app
```

### Database migrations and rollback

The hardest part of rollback is often the database. Say v2 ran a migration that added a column and filled it in. Rolling back to v1 leaves v1 unaware of that column. Worse, v2 may have deleted a column that v1 still depends on.

The safe pattern is the **expand-contract migration**, also called the *parallel-change pattern*. It runs in four phases:

1. **Expand** — deploy `v2a`, which adds the new column as nullable. The change stays backward-compatible. Now v1 and `v2a` run side by side: v1 ignores the new column, `v2a` writes to it.
2. **Migrate** — backfill the new column for the existing rows. Run this in the background, not as part of the deploy.
3. **Contract** — deploy `v2b`. Every row now has data, so `v2b` can make the column `NOT NULL` and drop the old column references from the code. The old v1 code is out of production by then.
4. **Cleanup** — deploy v3, dropping the old column once `v2b` has been stable for some time.

This means: **never drop a column in the same migration that adds its replacement**. Never make a column `NOT NULL` in the first migration. Always deploy in multiple phases, so that a rollback at any phase is safe.

## Which strategy to use

| Project type or constraint | Recommended strategy |
|---|---|
| Simple app, small team, limited infrastructure | Rolling update |
| No mixed-version states allowed, instant rollback required, 2× infrastructure affordable | Blue-green |
| High traffic, and you want to validate the new version on real traffic first | Canary release |
| Code is ready but the feature is not, or you need a gradual user rollout without re-deploying | Feature flag |

In practice, most mature pipelines combine strategies: rolling or blue-green for infrastructure-level deployment, feature flags for application-level control, and canary for high-risk releases.

## Common interview traps

- **Confusing canary release with feature flags** — this is extremely common and specifically tested in interviews. Canary = infrastructure-level traffic split between two deployed versions. Feature flag = application-level code branch within a single deployed version. They can be used together, but they are not the same thing.

- **"Blue-green is just deploying twice"** — the point of blue-green is that the old version keeps running until the switch, making rollback instantaneous. If you tear down blue after deploying green, you have lost the key advantage.

- **Forgetting about database migrations in rolling deployments** — when v1 and v2 run simultaneously, both hit the same database. If v2's migration drops a column that v1 reads, v1 breaks. All migrations during a rolling update must be backward-compatible (additive only in the same deploy wave; deletions in a later wave after v1 is gone).

- **Treating `maxUnavailable: 1` and `maxSurge: 0` as zero-downtime** — with these settings Kubernetes stops one old pod before it starts a new one. Capacity temporarily drops. For zero-downtime use `maxUnavailable: 0` (never go below the desired count) and `maxSurge: 1` (temporarily run one extra pod).

- **"Rollback is just redeploying the old Docker image"** — true for stateless code. But if the database schema has moved forward and the old code does not understand it, redeploying the old code breaks the app. Rollback must be planned as part of the migration strategy.

- **Claiming zero-downtime without addressing graceful shutdown** — zero-downtime deployment at the infrastructure level is defeated if the application doesn't handle `SIGTERM` gracefully. The platform waits to drain connections — but if the app exits immediately on `SIGTERM`, in-flight requests are dropped. The application code must cooperate.
