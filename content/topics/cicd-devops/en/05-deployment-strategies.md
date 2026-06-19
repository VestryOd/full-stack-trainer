# Deployment Strategies

## Why deployment strategy matters

Deploying new code to production is the riskiest moment in the software delivery lifecycle. If something goes wrong — a bug slipped through testing, a performance regression, a broken third-party integration — users are affected immediately. Deployment strategies are techniques for controlling *how* a new version of code replaces the old version, with the goals of:

1. **Minimizing downtime** — users experience the service as continuously available
2. **Limiting blast radius** — if the new version has a bug, only a fraction of users are affected before you catch it
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

A prerequisite for zero-downtime deployment: **your application must handle graceful shutdown** — when it receives a `SIGTERM` signal (which the orchestrator sends before stopping the process), it must:
1. Stop accepting new connections
2. Finish processing in-flight requests
3. Close database connections cleanly
4. Exit with code 0

Without graceful shutdown, even the most sophisticated deployment strategy will drop requests at the moment a container is stopped.

## Rolling deployment

**Rolling deployment** (also called a *rolling update*) replaces instances of the old version with instances of the new version **incrementally** — one at a time, or a few at a time — while the service continues running.

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

```txt
1. New v2 instance starts and passes health check
2. Load balancer / proxy adds v2 to the routing pool
3. Load balancer drains v1 — stops sending new requests to it,
   waits for in-flight requests to finish (drain timeout: typically 30–60s)
4. v1 instance is stopped after drain completes
```

**Tradeoffs:**

```txt
Advantages:
  + Simple to implement — built into Kubernetes, ECS, most PaaS platforms
  + No extra infrastructure needed — uses existing instances
  + Low resource cost (compared to blue-green)

Disadvantages:
  - During the rollout, v1 and v2 run simultaneously
    → requests may be served by either version — inconsistency is possible
  - If v2 has a bug, some users see the bug while others don't
    (the percentage increases as the rollout progresses)
  - Rollback requires another rolling update in reverse (slow)
  - Database migrations must be backward-compatible with both v1 and v2
    (since both run at the same time during the rollout)
```

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

The `readinessProbe` is what makes rolling deployments zero-downtime: a pod only receives traffic after the probe passes, so a buggy v2 that fails the health check never receives real user traffic — the rollout stalls and alerts fire.

## Blue-green deployment

**Blue-green deployment** maintains **two identical production environments** — called "blue" and "green" — and switches traffic between them instantaneously.

```txt
Current state: "blue" is live (serving all traffic)
  [blue: v1, v1, v1, v1]  ←── 100% of user traffic
  [green: idle / v1]       ← standing by (or absent)

Deploy v2:
  [blue: v1, v1, v1, v1]  ← still live, still serving traffic
  [green: v2, v2, v2, v2] ← v2 is deployed and tested here (no real traffic yet)

Switch: update the load balancer / DNS to point to green
  [blue: v1, v1, v1, v1]  ← now idle (kept for rollback)
  [green: v2, v2, v2, v2] ←── 100% of user traffic

If v2 has a bug — rollback in seconds:
  [blue: v1, v1, v1, v1]  ←── switch back — 100% traffic back to v1 instantly
  [green: v2, v2, v2, v2] ← now idle again
```

The traffic switch can be a DNS change, a load balancer rule change, or a reverse proxy configuration reload — and it can happen in under a second.

**Tradeoffs:**

```txt
Advantages:
  + Instant rollback — just switch the load balancer back (seconds, not minutes)
  + Zero mixed-version traffic — at any point in time, all users see the same version
  + Full v2 environment can be tested in isolation before traffic switch
    (smoke tests, load tests, QA sign-off)

Disadvantages:
  - Double infrastructure cost — two full production environments must exist simultaneously
  - Database migrations: if v2 has schema changes, v1 must still work with the new schema
    during the pre-switch period (backward-compatible migrations required)
  - DNS-based switching has propagation delay (TTL) — not truly instant at the DNS level;
    use load balancer switching instead to avoid this
```

Blue-green with a reverse proxy (NGINX or similar):

```nginx
# Switch by updating the upstream and reloading NGINX (zero-downtime reload)
upstream app {
    server green:3000;   # was: server blue:3000;
}
```

Or with a cloud load balancer (AWS ALB target group switch, GCP Backend Service update):

```bash
# AWS: switch ALB listener rule to point to green target group
aws elbv2 modify-listener \
  --listener-arn arn:aws:elasticloadbalancing:... \
  --default-actions Type=forward,TargetGroupArn=<green-target-group-arn>
```

## Canary release

A **canary release** (named after "canary in a coal mine" — canaries were sent into mines to detect toxic gas before humans entered) sends a **small percentage of real user traffic** to the new version while the majority still hits the old version. The new version is observed for errors and performance regressions before traffic is gradually increased to 100%.

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

The key difference from rolling deployment: in a rolling update, you replace instances sequentially until all are updated — there is no concept of "send 5% to the new version." In a canary, you specifically control the *traffic split* (by weight in the load balancer, not by instance count).

**Where canary is implemented:**

- **Load balancer weighted routing** — AWS ALB weighted target groups, NGINX `weight`, Kubernetes Gateway API
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

**Tradeoffs:**

```txt
Advantages:
  + Real user traffic tests the new version — catches bugs that staging missed
  + Small blast radius — a bug in v2 initially affects only 5% of users
  + Gradual rollout gives time to detect performance regressions that only
    appear under real-world load

Disadvantages:
  - Both versions run simultaneously (same database migration constraints as rolling)
  - Requires a load balancer that supports weighted routing
  - More complex observability setup — you need to track metrics per version,
    not just per service
  - Canary analysis (deciding when it's safe to increase traffic) can be automated
    (Argo Rollouts, Flagger) or manual — manual is error-prone under time pressure
```

## Feature flags

A **feature flag** (also called a *feature toggle* or *feature switch*) is a mechanism in the application code that enables or disables a feature at runtime — without deploying new code.

**Feature flags are NOT a deployment strategy.** They are a code-level technique that complements deployment strategies. The distinction:

```txt
Deployment strategy  = controls HOW new code reaches the production environment
                       (rolling / blue-green / canary)

Feature flag         = controls WHETHER a feature in already-deployed code
                       is active for a given user
                       (the code is already in production — the flag controls visibility)
```

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

**Why feature flags are powerful in combination with CI/CD:**

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

```txt
Canary release:  traffic split at the infrastructure level (load balancer)
                 → different *servers* handle the requests
                 → both v1 code and v2 code are deployed

Feature flag:    traffic split at the application level (inside the code)
                 → the *same server* handles the request, but executes
                   different code paths based on the flag value
                 → only one version of code is deployed
```

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
# (using Argo Rollouts CRD)
kubectl argo rollouts set weight my-app 0
# Or simply abort the rollout
kubectl argo rollouts abort my-app
```

### Database migrations and rollback

The hardest part of rollback is often the database. If v2 ran a migration that added a column and populated it, rolling back to v1 means v1 might not know about that column — or worse, v2 deleted a column that v1 depends on.

The safe pattern is the **expand-contract migration** (also called the *parallel-change pattern*):

```txt
Phase 1 — EXPAND (deploy v2a):
  v2a adds the new column as nullable (backward-compatible)
  v1 and v2a run simultaneously — v1 ignores the new column, v2a writes to it

Phase 2 — MIGRATE:
  Backfill data in the new column for existing rows
  Run in the background, not as part of the deploy

Phase 3 — CONTRACT (deploy v2b):
  v2b makes the column NOT NULL (now safe — all rows have data)
  Remove old column references from the code
  Old v1 code is no longer in production

Phase 4 — CLEANUP (deploy v3):
  Drop the old column once v2b has been stable for some time
```

This means: **never drop a column in the same migration that adds its replacement**. Never make a column NOT NULL in the first migration. Always deploy in multiple phases so that rollback at any phase is safe.

## Which strategy to use

```txt
Project type / constraint         → Recommended strategy
───────────────────────────────────────────────────────────────────
Simple app, small team,           Rolling update
limited infrastructure

Zero tolerance for mixed-version  Blue-green
states, instant rollback required,
can afford 2x infra cost

High traffic, want to validate    Canary release
new version on real traffic
before full rollout

Code ready but feature not ready  Feature flag
for all users, or need gradual
user rollout without re-deploying
```

In practice, most mature pipelines combine strategies: rolling or blue-green for infrastructure-level deployment, feature flags for application-level control, and canary for high-risk releases.

## Common interview traps

- **Confusing canary release with feature flags** — this is extremely common and specifically tested in interviews. Canary = infrastructure-level traffic split between two deployed versions. Feature flag = application-level code branch within a single deployed version. They can be used together, but they are not the same thing.

- **"Blue-green is just deploying twice"** — the point of blue-green is that the old version keeps running until the switch, making rollback instantaneous. If you tear down blue after deploying green, you have lost the key advantage.

- **Forgetting about database migrations in rolling deployments** — when v1 and v2 run simultaneously, both hit the same database. If v2's migration drops a column that v1 reads, v1 breaks. All migrations during a rolling update must be backward-compatible (additive only in the same deploy wave; deletions in a later wave after v1 is gone).

- **Treating `maxUnavailable: 1` and `maxSurge: 0` as zero-downtime** — with these settings, Kubernetes will stop one old pod before starting a new one, meaning capacity temporarily drops. For zero-downtime, use `maxUnavailable: 0` (never go below desired count) and `maxSurge: 1` (temporarily run one extra pod).

- **"Rollback is just redeploying the old Docker image"** — true for stateless code, but if the database schema changed in the "forward" direction and the old code doesn't understand the new schema, redeploying old code will break the app. Rollback must be planned as part of the migration strategy.

- **Claiming zero-downtime without addressing graceful shutdown** — zero-downtime deployment at the infrastructure level is defeated if the application doesn't handle `SIGTERM` gracefully. The platform waits to drain connections — but if the app exits immediately on `SIGTERM`, in-flight requests are dropped. The application code must cooperate.
