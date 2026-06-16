<!-- verified: 2026-06-05, corrections: 0 -->
# ECS, Fargate и Containers

## Docker и контейнеры — фундамент

```txt
Проблема без Docker ("works on my machine"):
  Dev: Node.js 18, Ubuntu 22.04, libc 2.35, PostgreSQL 15
  Prod: Node.js 16, CentOS 7, libc 2.17, PostgreSQL 13
  → приложение ведёт себя иначе, баги в prod

Контейнер = изолированный процесс с собственной файловой системой:
  Dockerfile → docker build → Image (слоёная ФС)
  docker run → Container (запущенный Image)
  
  Что упаковывается:
    Application code
    Runtime (Node.js 20.x exact)
    Dependencies (node_modules)
    System libraries (конкретная версия)
    OS layer (минимальный Alpine/Debian)
    Config (env defaults)

VM vs Container:
  VM:        Guest OS + Kernel + App (GB, минуты старта)
  Container: App + libs, shared Host Kernel (MB, секунды старта)
```

```dockerfile
# Типичный Dockerfile для NestJS
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
# Запускаем не как root (безопасность)
USER node
EXPOSE 3000
CMD ["node", "dist/main.js"]
```

## ECS — Elastic Container Service

ECS — оркестратор контейнеров AWS. Управляет: запуск, обновление, масштабирование, мониторинг, networking. Альтернатива — Kubernetes (EKS), но ECS проще и лучше интегрирован с AWS-экосистемой.

```txt
Иерархия ECS:
  Cluster (логическая группа ресурсов)
    ↳ Service (управляет N копий Task Definition)
          ↳ Task (запущенный контейнер или группа)
                ↳ Container (Docker container)

Task Definition — JSON-шаблон запуска:
  Docker image (ECR URI)
  CPU + Memory allocation
  Environment variables
  Port mappings
  Secrets (из Secrets Manager)
  Log configuration (CloudWatch Logs)
  Health check

Service — поддерживает заданное количество Tasks:
  Если Task упал → Service автоматически запускает новый
  Rolling deployment: новые Tasks поднимаются до удаления старых
  Blue/Green deployment: через CodeDeploy
```

## ECR и деплой

```bash
# Типичный CI/CD flow

# 1. Сборка и push в ECR (AWS Container Registry)
aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.eu-west-1.amazonaws.com

docker build -t my-api .
docker tag my-api:latest \
  123456789.dkr.ecr.eu-west-1.amazonaws.com/my-api:$GIT_SHA
docker push \
  123456789.dkr.ecr.eu-west-1.amazonaws.com/my-api:$GIT_SHA

# 2. Обновление ECS Service новым image
aws ecs update-service \
  --cluster my-cluster \
  --service my-api-service \
  --force-new-deployment
```

## Fargate vs ECS on EC2

```txt
ECS on EC2:
  Ты управляешь: EC2 instances (patching, capacity, AMI updates)
  Ты платишь: за EC2 instance непрерывно (работает ли Task или нет)
  Преимущество: дешевле при высокой утилизации (EC2 Savings Plans)
  Когда: большие стабильные нагрузки, специфичные instance types (GPU)

ECS on Fargate (рекомендуется):
  AWS управляет: серверами, capacity, patching
  Ты платишь: только за CPU+Memory пока Task работает
  Преимущество: нет операционной нагрузки, scale до нуля в ECS Scheduled Tasks
  Когда: большинство backend API, batch jobs, dev teams без DevOps

Fargate pricing:
  $0.04048/vCPU/hour
  $0.004445/GB memory/hour
  Пример: 0.5 vCPU + 1GB, 1 Task 24/7 ≈ $18/мес
  vs ECS on EC2 t3.micro ($8.5/мес, но вся машина целиком)
```

## CDK: Fargate Service + ALB

```typescript
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as ecr from 'aws-cdk-lib/aws-ecr';

const cluster = new ecs.Cluster(this, 'Cluster', { vpc });

const repository = ecr.Repository.fromRepositoryName(this, 'Repo', 'my-api');

// ApplicationLoadBalancedFargateService — ALB + Fargate в одном конструкте
const service = new ecsPatterns.ApplicationLoadBalancedFargateService(this, 'ApiService', {
  cluster,
  cpu: 512,         // 0.5 vCPU
  memoryLimitMiB: 1024,  // 1GB RAM
  desiredCount: 2,  // 2 задачи (для HA)

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

  // Health check для ALB
  healthCheckGracePeriod: Duration.seconds(30),

  // Circuit breaker: откат деплоя если задачи не поднимаются
  circuitBreaker: { rollback: true },
});

// Auto Scaling по CPU
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

## Lambda vs ECS Fargate — полная матрица

```txt
                      Lambda              ECS Fargate
Max Duration:         15 min              Unlimited
Cold Start:           50-3000ms           Минимальный (0 для running task)
Concurrent:           1000 (по умолч.)    Определяется кол-вом Tasks
Memory:               128MB - 10GB        8MB - 120GB per Task
CPU:                  Linear с memory     0.25 - 16 vCPU
Persistent conn:      Нет (ephemeral)     Да (WebSocket, SSE)
Stateful:             Нет                 Да (in-memory cache)
Cost pattern:         Per invocation      Per running hour
Zero traffic cost:    $0.00               ≠ $0 (Tasks running)
Docker:               Опционально (ZIP)   Обязательно

Lambda выбирай:
  ✓ Event-driven (S3, SQS, SNS triggers)
  ✓ Sporadic traffic (pay-per-use)
  ✓ Background jobs, cron tasks
  ✓ Simple HTTP API (< 29 sec response)

ECS Fargate выбирай:
  ✓ Long-running HTTP services (NestJS, Express)
  ✓ WebSocket сервера
  ✓ High-traffic APIs (>1000 RPS постоянно)
  ✓ Stateful workloads (in-memory cache)
  ✓ Процессы > 15 минут
  ✓ Сложные монолиты с многими зависимостями
```

## Типичные ошибки на интервью

- **"Container = VM"** — контейнер использует ядро host OS, не запускает отдельную OS. Поэтому: запуск за секунды (не минуты), размер MB (не GB). Изоляция процесса + файловой системы, но общий kernel. Windows контейнеры — исключение (другой механизм).

- **"ECS и Fargate — это одно и то же"** — ECS — оркестратор. Fargate — launch type (способ запуска), альтернатива EC2 launch type. ECS может работать и на EC2 (ты управляешь инстансами), и на Fargate (AWS управляет).

- **"Fargate дороже чем Lambda"** — зависит от трафика. Lambda: дорого при постоянной высокой нагрузке ($0.20/1M requests + compute). Fargate: фиксированная стоимость per hour. При >1M requests/day с длинными задачами Fargate может быть дешевле.

- **"Auto Scaling в ECS реагирует мгновенно"** — запуск нового Fargate Task занимает 30-60 секунд (pull image + start container). Поэтому Scale-Out Cooldown = 30s (агрессивно), Scale-In Cooldown = 60s (консервативно чтобы не убить слишком рано). Для spike трафика: держать `minCapacity` с запасом.

- **"Для NestJS лучше Lambda"** — NestJS инициализация (DI, decorators scan) = 2-5 секунд cold start. При каждой Lambda invocation с cold start это неприемлемо. NestJS на Fargate: процесс всегда warm, нет cold start проблемы. Lambda лучше для простых функций, Fargate — для фреймворков с тяжёлой инициализацией.
