<!-- verified: 2026-06-05, corrections: 0 -->
# ECS, Fargate и Containers

## Docker и контейнеры — фундамент

Docker закрывает разрыв «works on my machine»: окружение едет вместе с кодом. Всё, что запускает ECS (Elastic Container Service), — это контейнеры, поэтому топик начинается отсюда. Без Docker одно и то же приложение работает на двух разных стеках:

| | Dev | Prod |
|---|---|---|
| Node.js | 18 | 16 |
| OS (операционная система) | Ubuntu 22.04 | CentOS 7 |
| libc | 2.35 | 2.17 |
| PostgreSQL | 15 | 13 |

Разные слои — приложение ведёт себя иначе, и появляются баги, которые видны только в prod.

Контейнер — изолированный процесс с собственной файловой системой. Путь такой: `Dockerfile → docker build → Image` (слоёная файловая система), затем `docker run → Container` (запущенный образ).

**Что упаковывается в образ:**

- Код приложения.
- Runtime — Node.js 20.x, точная версия.
- Зависимости (`node_modules`).
- Системные библиотеки, конкретная версия.
- Слой OS — минимальный Alpine или Debian.
- Конфигурация, значения переменных окружения по умолчанию.

**VM против контейнера:**

- VM (virtual machine — виртуальная машина) несёт гостевую OS, ядро и приложение: гигабайты размера, минуты на старт.
- Контейнер несёт приложение и библиотеки, а ядро использует хостовое: мегабайты размера, секунды на старт.

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

ECS — оркестратор контейнеров от AWS (Amazon Web Services). Управляет запуском, обновлением, масштабированием, мониторингом и сетью. Альтернатива — Kubernetes в виде EKS (Elastic Kubernetes Service), но ECS проще и лучше интегрирован с экосистемой AWS.

Четыре уровня, и каждый управляет уровнем ниже:

```txt
Иерархия ECS:
  Cluster (логическая группа ресурсов)
    ↳ Service (управляет N копий Task Definition)
          ↳ Task (запущенный контейнер или группа)
                ↳ Container (Docker container)
```

**Task Definition — это JSON-шаблон запуска.** В нём лежат:

- Образ Docker, заданный адресом в ECR (Elastic Container Registry).
- Выделение процессора (CPU) и памяти.
- Переменные окружения.
- Маппинг портов.
- Секреты, взятые из Secrets Manager.
- Конфигурация логов, CloudWatch Logs.
- Health check.

**Service поддерживает заданное количество Tasks:**

- Если Task упал, Service автоматически запускает новый.
- Rolling deployment: новые Tasks поднимаются до удаления старых.
- Blue/Green deployment: через CodeDeploy.

## ECR и деплой

Деплой — это два шага: отправить новый образ в реестр, потом сказать Service переразвернуться. Тег образа — это хеш коммита, поэтому каждый деплой прослеживается до одного коммита.

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

Оба варианта запускают одни и те же Tasks. Вопрос в том, кто владеет серверами под ними, и от этого зависят и работа по эксплуатации, и счёт.

**ECS on EC2 (Elastic Compute Cloud)**

- Вы управляете инстансами EC2: патчинг, ёмкость, обновления AMI (Amazon Machine Image).
- Вы платите за инстанс EC2 непрерывно, работает Task или нет.
- Преимущество: дешевле при высокой утилизации, с EC2 Savings Plans.
- Когда: большие стабильные нагрузки, особые типы инстансов вроде GPU (видеокарта).

**ECS on Fargate (рекомендуется)**

- AWS управляет серверами, ёмкостью и патчингом.
- Вы платите только за процессор и память, пока Task работает.
- Преимущество: нет операционной нагрузки, а для ECS Scheduled Tasks возможно масштабирование до нуля.
- Когда: большинство бэкенд-API, пакетные задачи, команды без выделенного инженера DevOps (development and operations).

**Сколько стоит Fargate:**

- $0.04048 за vCPU в час.
- $0.004445 за GB (гигабайт) памяти в час.
- Пример: 0.5 vCPU + 1GB, один Task 24/7 ≈ $18/мес.
- Против ECS on EC2 t3.micro за $8.5/мес — но это вся машина целиком, используете вы её или нет.

## CDK: Fargate Service + ALB

Один конструкт CDK (Cloud Development Kit), `ApplicationLoadBalancedFargateService`, создаёт сразу ALB (Application Load Balancer), сервис Fargate и связку между ними. Блок авто-масштабирования ниже держит от 2 до 10 Tasks, целясь в 70% загрузки процессора.

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
  desiredCount: 2,  // 2 задачи (для высокой доступности)

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

Одиннадцать строк, и решают обычно длительность, холодный старт и счёт при нулевом трафике:

| | Lambda | ECS Fargate |
|---|---|---|
| Максимальная длительность | 15 мин | Не ограничена |
| Холодный старт | 50-3000ms | Минимальный, 0 для уже запущенной задачи |
| Параллелизм | 1000 по умолчанию | Определяется количеством Tasks |
| Память | 128MB - 10GB | 8MB - 120GB на Task |
| Процессор | Линейно от памяти | 0.25 - 16 vCPU |
| Постоянные соединения | Нет, эфемерные | Да: WebSocket, SSE (server-sent events) |
| Состояние | Нет | Да, кеш в памяти |
| Модель оплаты | За вызов | За час работы |
| Стоимость при нулевом трафике | $0.00 | Не $0 — Tasks продолжают работать |
| Docker | Опционально — архив `.zip` | Обязательно |

**Выбирайте Lambda, когда:**

- Работа событийная: триггеры от S3 (Simple Storage Service), SQS (Simple Queue Service) или SNS (Simple Notification Service).
- Трафик нерегулярный, и оплата по факту выгоднее.
- Это фоновые задачи или задачи по расписанию.
- Это простой HTTP API с ответом меньше 29 сек.

**Выбирайте ECS Fargate, когда:**

- Долгоживущие HTTP-сервисы (NestJS, Express).
- Серверы WebSocket.
- Высоконагруженные API, больше 1000 RPS (запросов в секунду) постоянно.
- Нагрузки с состоянием, с кешем в памяти.
- Процессы длиннее 15 минут.
- Сложные монолиты с большим количеством зависимостей.

## Типичные ошибки на интервью

- **"Container = VM"** — контейнер использует ядро host OS, не запускает отдельную OS. Поэтому: запуск за секунды (не минуты), размер MB (не GB). Изоляция процесса + файловой системы, но общий kernel. Windows контейнеры — исключение (другой механизм).

- **"ECS и Fargate — это одно и то же"** — ECS — оркестратор. Fargate — launch type (способ запуска), альтернатива EC2 launch type. ECS может работать и на EC2 (инстансами управляете вы), и на Fargate (ими управляет AWS).

- **"Fargate дороже чем Lambda"** — зависит от трафика. Lambda: дорого при постоянной высокой нагрузке ($0.20/1M requests + compute). Fargate: фиксированная стоимость per hour. При >1M requests/day с длинными задачами Fargate может быть дешевле.

- **"Auto Scaling в ECS реагирует мгновенно"** — запуск нового Fargate Task занимает 30-60 секунд (pull image + start container). Поэтому Scale-Out Cooldown = 30s (агрессивно), Scale-In Cooldown = 60s (консервативно чтобы не убить слишком рано). Для всплесков трафика держите `minCapacity` с запасом.

- **"Для NestJS лучше Lambda"** — инициализация NestJS (внедрение зависимостей, сканирование декораторов) занимает 2-5 секунд на холодном старте. На каждом холодном старте Lambda это неприемлемо. NestJS на Fargate: процесс всегда warm, нет cold start проблемы. Lambda лучше для простых функций, Fargate — для фреймворков с тяжёлой инициализацией.
