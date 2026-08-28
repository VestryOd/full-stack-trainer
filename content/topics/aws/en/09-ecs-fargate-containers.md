# ECS, Fargate and Containers

## Docker and containers — the foundation

Docker closes the "works on my machine" gap by shipping the environment together with the code. Everything ECS (Elastic Container Service) runs is a container, so this is where the topic starts. Without Docker, the same app runs on two different stacks:

| | Dev | Prod |
|---|---|---|
| Node.js | 18 | 16 |
| OS (operating system) | Ubuntu 22.04 | CentOS 7 |
| libc | 2.35 | 2.17 |
| PostgreSQL | 15 | 13 |

Different layers mean different behavior, and bugs that only show up in prod.

A container is an isolated process with its own filesystem. The path is `Dockerfile → docker build → Image` (a layered filesystem), then `docker run → Container` (a running image).

**What gets packaged into the image:**

- Application code.
- Runtime — Node.js 20.x, the exact version.
- Dependencies (`node_modules`).
- System libraries, a specific version.
- An OS layer — a minimal Alpine or Debian.
- Config, the environment defaults.

**VM vs container:**

- A VM (virtual machine) carries a guest OS, a kernel and the app: gigabytes in size, minutes to start.
- A container carries the app and its libraries and shares the host kernel: megabytes in size, seconds to start.

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

ECS is a container orchestrator from AWS (Amazon Web Services). It manages launch, updates, scaling, monitoring, and networking. The alternative is Kubernetes, offered as EKS (Elastic Kubernetes Service), but ECS is simpler and better integrated with the AWS ecosystem.

Four levels, each one managing the level below it:

```txt
ECS hierarchy:
  Cluster (logical grouping of resources)
    ↳ Service (manages N copies of a Task Definition)
          ↳ Task (a running container or group of containers)
                ↳ Container (Docker container)
```

**A Task Definition is a JSON launch template.** It holds:

- The Docker image, given as an ECR (Elastic Container Registry) address.
- Processor (CPU) and memory allocation.
- Environment variables.
- Port mappings.
- Secrets, taken from Secrets Manager.
- Log configuration, CloudWatch Logs.
- Health check.

**A Service maintains the desired number of Tasks:**

- If a Task fails, the Service automatically starts a new one.
- Rolling deployment: new Tasks come up before old ones are removed.
- Blue/Green deployment: via CodeDeploy.

## ECR and deployment

Deployment is two steps: push a new image to the registry, then tell the Service to redeploy. The image tag is the commit hash, so every deploy is traceable to one commit.

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

Both run the same ECS Tasks. The question is who owns the servers underneath, and that decides both your operations work and your bill.

**ECS on EC2 (Elastic Compute Cloud)**

- You manage the EC2 instances: patching, capacity, AMI (Amazon Machine Image) updates.
- You pay for the EC2 instance continuously, whether a Task is running or not.
- Advantage: cheaper at high utilization, with EC2 Savings Plans.
- Use when: large steady-state workloads, special instance types such as a GPU (graphics card).

**ECS on Fargate (recommended)**

- AWS manages servers, capacity and patching.
- You pay only for processor and memory while a Task is running.
- Advantage: no operational overhead, and scale to zero for ECS Scheduled Tasks.
- Use when: most backend APIs, batch jobs, dev teams with no dedicated DevOps (development and operations) engineer.

**Fargate pricing:**

- $0.04048 per vCPU per hour.
- $0.004445 per GB (gigabyte) of memory per hour.
- Example: 0.5 vCPU + 1GB, one Task running 24/7 ≈ $18/month.
- Against ECS on EC2 t3.micro at $8.5/month — but that is the whole machine, used or not.

## CDK: Fargate Service + ALB

One CDK (Cloud Development Kit) construct, `ApplicationLoadBalancedFargateService`, creates the ALB (Application Load Balancer), the Fargate service and the wiring between them. The auto-scaling block after it keeps between 2 and 10 Tasks, targeting 70% processor utilization.

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
  desiredCount: 2,       // 2 tasks (for high availability)

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

Eleven rows, and the deciding ones are usually duration, cold start and the bill at zero traffic:

| | Lambda | ECS Fargate |
|---|---|---|
| Max duration | 15 min | Unlimited |
| Cold start | 50-3000ms | Minimal, 0 for an already-running task |
| Concurrency | 1000 by default | Determined by the number of Tasks |
| Memory | 128MB - 10GB | 8MB - 120GB per Task |
| Processor | Linear with memory | 0.25 - 16 vCPU |
| Persistent connections | No, ephemeral | Yes: WebSocket, SSE (server-sent events) |
| Stateful | No | Yes, in-memory cache |
| Cost pattern | Per invocation | Per running hour |
| Cost at zero traffic | $0.00 | Not $0 — Tasks keep running |
| Docker | Optional — a `.zip` archive | Required |

**Choose Lambda when:**

- The work is event-driven: triggers from S3 (Simple Storage Service), SQS (Simple Queue Service) or SNS (Simple Notification Service).
- Traffic is sporadic, so pay-per-use wins.
- You run background jobs or cron tasks.
- It is a simple HTTP API that answers in under 29 sec.

**Choose ECS Fargate when:**

- Long-running HTTP services (NestJS, Express).
- WebSocket servers.
- High-traffic APIs, over 1000 RPS (requests per second) continuously.
- Stateful workloads with an in-memory cache.
- Processes longer than 15 minutes.
- Complex monoliths with many dependencies.

## Common interview mistakes

- **"Container = VM"** — a container uses the host OS kernel, it does not run a separate OS. That's why: startup in seconds (not minutes), size in MBs (not GBs). Process + filesystem isolation, but a shared kernel. Windows containers are an exception (different mechanism).

- **"ECS and Fargate are the same thing"** — ECS is the orchestrator. Fargate is a launch type (a way to run tasks), as opposed to the EC2 launch type. ECS can run on EC2 (you manage the instances) or on Fargate (AWS manages the infrastructure).

- **"Fargate is more expensive than Lambda"** — it depends on traffic. Lambda: expensive for constant high load ($0.20/1M requests + compute). Fargate: fixed cost per hour. For >1M requests/day with longer-running tasks, Fargate can be cheaper.

- **"Auto Scaling in ECS reacts instantly"** — starting a new Fargate Task takes 30-60 seconds (pull image + start container). That's why Scale-Out Cooldown = 30s (aggressive), Scale-In Cooldown = 60s (conservative, to avoid killing too soon). For traffic spikes: keep `minCapacity` with a buffer.

- **"Lambda is better for NestJS"** — NestJS initialization (dependency injection, decorator scanning) takes 2-5 seconds on cold start. This is unacceptable on every Lambda invocation. NestJS on Fargate: process is always warm, no cold start problem. Lambda is better for simple functions; Fargate is better for frameworks with heavy initialization.
