# ECS, Fargate and Containers

## Docker and containers — the foundation

```txt
Problem without Docker ("works on my machine"):
  Dev:  Node.js 18, Ubuntu 22.04, libc 2.35, PostgreSQL 15
  Prod: Node.js 16, CentOS 7,  libc 2.17, PostgreSQL 13
  → different behavior, bugs in prod

Container = isolated process with its own filesystem:
  Dockerfile → docker build → Image (layered FS)
  docker run → Container (running Image)

What gets packaged:
  Application code
  Runtime (Node.js 20.x exact)
  Dependencies (node_modules)
  System libraries (specific version)
  OS layer (minimal Alpine/Debian)
  Config (env defaults)

VM vs Container:
  VM:        Guest OS + Kernel + App (GBs, minutes to start)
  Container: App + libs, shared Host Kernel (MBs, seconds to start)
```

```dockerfile
# Typical Dockerfile for NestJS
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS production
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package*.json ./
# Run as non-root (security)
USER node
EXPOSE 3000
CMD ["node", "dist/main.js"]
```

## ECS — Elastic Container Service

ECS is an AWS container orchestrator. It manages: launch, updates, scaling, monitoring, and networking. The alternative is Kubernetes (EKS), but ECS is simpler and better integrated with the AWS ecosystem.

```txt
ECS hierarchy:
  Cluster (logical grouping of resources)
    ↳ Service (manages N copies of a Task Definition)
          ↳ Task (a running container or group of containers)
                ↳ Container (Docker container)

Task Definition — a JSON launch template:
  Docker image (ECR URI)
  CPU + Memory allocation
  Environment variables
  Port mappings
  Secrets (from Secrets Manager)
  Log configuration (CloudWatch Logs)
  Health check

Service — maintains the desired number of Tasks:
  If a Task fails → Service automatically starts a new one
  Rolling deployment: new Tasks come up before old ones are removed
  Blue/Green deployment: via CodeDeploy
```

## ECR and deployment

```bash
# Typical CI/CD flow

# 1. Build and push to ECR (AWS Container Registry)
aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.eu-west-1.amazonaws.com

docker build -t my-api .
docker tag my-api:latest \
  123456789.dkr.ecr.eu-west-1.amazonaws.com/my-api:$GIT_SHA
docker push \
  123456789.dkr.ecr.eu-west-1.amazonaws.com/my-api:$GIT_SHA

# 2. Update ECS Service with the new image
aws ecs update-service \
  --cluster my-cluster \
  --service my-api-service \
  --force-new-deployment
```

## Fargate vs ECS on EC2

```txt
ECS on EC2:
  You manage: EC2 instances (patching, capacity, AMI updates)
  You pay for: EC2 instance continuously (whether a Task is running or not)
  Advantage: cheaper at high utilization (EC2 Savings Plans)
  Use when: large steady-state workloads, special instance types (GPU)

ECS on Fargate (recommended):
  AWS manages: servers, capacity, patching
  You pay for: only CPU+Memory while a Task is running
  Advantage: no operational overhead, scale to zero for ECS Scheduled Tasks
  Use when: most backend APIs, batch jobs, dev teams without dedicated DevOps

Fargate pricing:
  $0.04048/vCPU/hour
  $0.004445/GB memory/hour
  Example: 0.5 vCPU + 1GB, 1 Task 24/7 ≈ $18/month
  vs ECS on EC2 t3.micro ($8.5/month, but the whole machine regardless of usage)
```

## CDK: Fargate Service + ALB

```typescript
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as ecr from 'aws-cdk-lib/aws-ecr';

const cluster = new ecs.Cluster(this, 'Cluster', { vpc });

const repository = ecr.Repository.fromRepositoryName(this, 'Repo', 'my-api');

// ApplicationLoadBalancedFargateService — ALB + Fargate in one construct
const service = new ecsPatterns.ApplicationLoadBalancedFargateService(this, 'ApiService', {
  cluster,
  cpu: 512,              // 0.5 vCPU
  memoryLimitMiB: 1024,  // 1GB RAM
  desiredCount: 2,       // 2 tasks (for HA)

  taskImageOptions: {
    image: ecs.ContainerImage.fromEcrRepository(repository, 'latest'),
    containerPort: 3000,
    environment: {
      NODE_ENV: 'production',
      PORT: '3000',
    },
    secrets: {
      DATABASE_URL: ecs.Secret.fromSecretsManager(dbSecret, 'url'),
    },
  },

  // Health check grace period for ALB
  healthCheckGracePeriod: Duration.seconds(30),

  // Circuit breaker: rolls back the deployment if Tasks don't start
  circuitBreaker: { rollback: true },
});

// Auto Scaling by CPU
const scaling = service.service.autoScaleTaskCount({
  minCapacity: 2,
  maxCapacity: 10,
});

scaling.scaleOnCpuUtilization('CpuScaling', {
  targetUtilizationPercent: 70,
  scaleInCooldown: Duration.seconds(60),
  scaleOutCooldown: Duration.seconds(30),
});
```

## Lambda vs ECS Fargate — full matrix

```txt
                      Lambda              ECS Fargate
Max Duration:         15 min              Unlimited
Cold Start:           50-3000ms           Minimal (0 for already-running task)
Concurrent:           1000 (default)      Determined by number of Tasks
Memory:               128MB - 10GB        8MB - 120GB per Task
CPU:                  Linear with memory  0.25 - 16 vCPU
Persistent conn:      No (ephemeral)      Yes (WebSocket, SSE)
Stateful:             No                  Yes (in-memory cache)
Cost pattern:         Per invocation      Per running hour
Zero traffic cost:    $0.00               ≠ $0 (Tasks still running)
Docker:               Optional (ZIP)      Required

Choose Lambda:
  ✓ Event-driven (S3, SQS, SNS triggers)
  ✓ Sporadic traffic (pay-per-use)
  ✓ Background jobs, cron tasks
  ✓ Simple HTTP API (< 29 sec response)

Choose ECS Fargate:
  ✓ Long-running HTTP services (NestJS, Express)
  ✓ WebSocket servers
  ✓ High-traffic APIs (>1000 RPS continuously)
  ✓ Stateful workloads (in-memory cache)
  ✓ Processes > 15 minutes
  ✓ Complex monoliths with many dependencies
```

## Common interview mistakes

- **"Container = VM"** — a container uses the host OS kernel, it does not run a separate OS. That's why: startup in seconds (not minutes), size in MBs (not GBs). Process + filesystem isolation, but a shared kernel. Windows containers are an exception (different mechanism).

- **"ECS and Fargate are the same thing"** — ECS is the orchestrator. Fargate is a launch type (a way to run tasks), as opposed to the EC2 launch type. ECS can run on EC2 (you manage the instances) or on Fargate (AWS manages the infrastructure).

- **"Fargate is more expensive than Lambda"** — it depends on traffic. Lambda: expensive for constant high load ($0.20/1M requests + compute). Fargate: fixed cost per hour. For >1M requests/day with longer-running tasks, Fargate can be cheaper.

- **"Auto Scaling in ECS reacts instantly"** — starting a new Fargate Task takes 30-60 seconds (pull image + start container). That's why Scale-Out Cooldown = 30s (aggressive), Scale-In Cooldown = 60s (conservative, to avoid killing too soon). For traffic spikes: keep `minCapacity` with a buffer.

- **"Lambda is better for NestJS"** — NestJS initialization (DI, decorator scanning) takes 2-5 seconds on cold start. This is unacceptable on every Lambda invocation. NestJS on Fargate: process is always warm, no cold start problem. Lambda is better for simple functions; Fargate is better for frameworks with heavy initialization.
