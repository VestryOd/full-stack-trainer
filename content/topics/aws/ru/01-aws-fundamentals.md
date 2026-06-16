<!-- verified: 2026-06-05, corrections: 0 -->
# AWS: Основы облачной платформы

## Что такое AWS и зачем облако

AWS (Amazon Web Services) — крупнейшая облачная платформа: более 200 сервисов, >32% рынка облака (2024). Идея: вместо покупки, настройки и обслуживания физических серверов — аренда вычислительных ресурсов по требованию с оплатой за фактическое использование.

**Ключевые преимущества для разработчика**:
- Нет капитальных затрат (CAPEX → OPEX)
- Мгновенное масштабирование (vertical и horizontal)
- Глобальная инфраструктура (33 региона, 105 AZ на 2024)
- Managed services: не нужно управлять OS/патчами для RDS, Lambda, S3

## Модели облачных сервисов (IaaS / PaaS / SaaS)

```txt
IaaS (Infrastructure as a Service):
  AWS предоставляет: виртуальные машины, сеть, диски
  Вы управляете: OS, runtime, приложением, данными
  Пример: EC2 (запускаете Linux-сервер, сами ставите Node.js, nginx)
  Когда: нужен полный контроль над окружением, legacy приложение

PaaS (Platform as a Service):
  AWS управляет: OS, runtime, scaling
  Вы управляете: кодом и данными
  Примеры: Lambda (только код), Elastic Beanstalk (деплой Docker/Node)
  Когда: хотите сфокусироваться на бизнес-логике, не на инфраструктуре

SaaS (Software as a Service):
  Готовый продукт "из коробки"
  Примеры: AWS WorkMail, Gmail, Notion
  Когда: потребляете продукт, не строите на нём

Shared Responsibility разделена по модели:
  IaaS: AWS = физ. безопасность + hardware; Вы = всё ПО выше
  PaaS: AWS = OS + runtime + патчи; Вы = код + данные + конфигурация
  SaaS: AWS = всё; Вы = только данные пользователей
```

## Глобальная инфраструктура: Region, AZ, Edge Location

```txt
Region (Регион):
  Независимый географический кластер датацентров.
  Примеры: eu-west-1 (Ирландия), us-east-1 (Вирджиния), ap-southeast-1 (Сингапур)
  Изоляция: сбой одного региона не затрагивает другой.
  Как выбирать: близость к пользователям (latency), compliance (GDPR → EU),
  наличие нужных сервисов (не все сервисы в всех регионах), стоимость.

Availability Zone (AZ):
  Изолированный датацентр (или группа) внутри региона.
  Связаны low-latency (<1ms) private fiber — быстрее internet.
  Пример: eu-west-1a, eu-west-1b, eu-west-1c
  Принцип: деплоить приложение в 2+ AZ → отказоустойчивость.
  Если eu-west-1a упал: трафик автоматически идёт на eu-west-1b.

Edge Location (CloudFront PoP):
  Точки присутствия для кэширования CDN-контента (250+ по миру).
  Ближе к пользователю чем region → меньше latency для статики.
  Используются CloudFront, Route53, AWS Shield.
```

```txt
Архитектурное правило: статические ресурсы — S3 + CloudFront (Edge).
Приложение — в 2+ AZ в одном регионе. Disaster Recovery — replica в
другом регионе (RDS Multi-Region Read Replica, S3 Cross-Region Replication).
```

## Shared Responsibility Model — кто за что отвечает

Принципиально важна на интервью: кандидаты часто смешивают ответственность AWS и свою.

```txt
AWS отвечает за ("Security OF the Cloud"):
  ✓ Физическая безопасность датацентров (охрана, камеры, доступ)
  ✓ Hardware (серверы, сети, хранилища)
  ✓ Глобальная сеть AWS (fibre, backbone)
  ✓ Гипервизор (для EC2)
  ✓ Managed service OS и патчи (RDS, Lambda, ECS Fargate)

Вы отвечаете за ("Security IN the Cloud"):
  ✓ IAM: пользователи, роли, политики (least privilege)
  ✓ Данные: шифрование at-rest и in-transit, backup
  ✓ Конфигурация: security groups, NACL, public vs private subnet
  ✓ Приложение: код, зависимости, валидация входящих данных
  ✓ EC2 OS: ваша OS → ваши патчи (AWS не обновляет ядро Linux на EC2)
  ✓ S3: политики bucket (public access block!)
```

## Ключевые сервисы — карта экосистемы

```txt
Compute:
  EC2         — Virtual Machines (IaaS), полный контроль
  Lambda      — Functions as a Service, event-driven, serverless
  ECS/Fargate — Docker контейнеры (ECS = оркестратор, Fargate = serverless compute)
  EKS         — Managed Kubernetes

Storage:
  S3          — Object storage, infinite scale, 11 девяток durability
  EBS         — Block storage (диск для EC2, как SSD в сервере)
  EFS         — Managed NFS (shared filesystem между EC2)

Database:
  RDS         — Managed PostgreSQL/MySQL/Aurora (OLTP)
  Aurora      — AWS-оптимизированный PostgreSQL/MySQL, 5x быстрее
  DynamoDB    — NoSQL key-value, single-digit ms latency, infinite scale
  ElastiCache — Managed Redis/Memcached

Messaging:
  SQS         — Queue (async decoupling, at-least-once delivery)
  SNS         — Pub/Sub fan-out (один message → много подписчиков)
  EventBridge — Event bus (routing по правилам, интеграции)

Networking:
  VPC         — Virtual Private Cloud (изолированная сеть)
  ALB/NLB     — Load Balancers (HTTP/TCP)
  Route53     — DNS + health checks + routing policies
  CloudFront  — CDN + edge caching + WAF

Security:
  IAM         — Identity and Access Management (роли, политики)
  Secrets Manager — безопасное хранение и ротация секретов
  KMS         — управление ключами шифрования
  WAF         — Web Application Firewall (OWASP rules)
  GuardDuty   — threat detection (ML-based)

IaC:
  CloudFormation — native AWS IaC (YAML/JSON templates)
  CDK            — TypeScript/Python → CloudFormation (рекомендуется)
  Terraform      — multi-cloud IaC (HashiCorp, популярен в enterprise)
```

## AWS CDK — Infrastructure as Code на TypeScript

CDK (Cloud Development Kit) позволяет описывать AWS инфраструктуру на TypeScript, Python, Java. CDK → синтез → CloudFormation → деплой.

```typescript
import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';

export class MyAppStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 bucket для хранения файлов
    const bucket = new s3.Bucket(this, 'AppBucket', {
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN, // не удалять при cdk destroy
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // Lambda function
    const handler = new lambda.Function(this, 'AppHandler', {
      runtime: lambda.Runtime.NODEJS_20_X,
      code: lambda.Code.fromAsset('dist/lambda'),
      handler: 'index.handler',
      environment: {
        BUCKET_NAME: bucket.bucketName,
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
    });

    // Дать Lambda право читать из bucket (least privilege)
    bucket.grantRead(handler);

    // API Gateway → Lambda
    new apigateway.LambdaRestApi(this, 'AppApi', {
      handler,
      proxy: true,
    });
  }
}
```

```bash
# CDK workflow
npx cdk synth    # сгенерировать CloudFormation template (проверить)
npx cdk diff     # показать изменения перед деплоем
npx cdk deploy   # задеплоить изменения
npx cdk destroy  # удалить stack (осторожно: RETAIN resources остаются)
```

**Преимущества CDK над raw CloudFormation**: типизация (TypeScript compiler проверяет), абстракции (Construct library), переиспользование кода (циклы, условия, классы), тестирование (jest + CDK assertions).

## Модель ценообразования — Pay-as-you-go

```txt
Основные принципы:
  - Платишь только за использование (EC2: по часам/секундам)
  - Чем больше используешь → дешевле per unit (volume discounts)
  - Reserved Instances: предоплата на 1-3 года → до 72% скидки
  - Spot Instances: незадействованные EC2 → до 90% дешевле, но могут прерваться

Бесплатный уровень (Free Tier):
  EC2: 750 ч/мес t2.micro (12 мес)
  S3: 5GB storage, 20k GET, 2k PUT (12 мес)
  Lambda: 1 млн вызовов/мес + 400k GB-сек (навсегда)
  RDS: 750 ч/мес db.t2.micro (12 мес)

Типичные затраты для small SaaS:
  S3 + CloudFront: $1-5/мес
  Lambda (1M req/мес): бесплатно или ~$0.20
  RDS t3.micro: ~$13/мес
  ALB: ~$16/мес (base) + per-request
```

## Типичные ошибки на интервью

- **"AWS отвечает за безопасность данных в S3"** — нет. S3 bucket policy, публичный доступ, шифрование — ответственность пользователя. AWS лишь обеспечивает физическую сохранность hardware. Инциденты с публичными S3 bucket (утечки данных) — 100% ошибка конфигурации пользователя.

- **"Регион = один датацентр"** — регион состоит из нескольких AZ (минимум 3), каждая AZ — отдельный изолированный датацентр. Одиночный EC2 в одной AZ = single point of failure. Для HA нужно 2+ AZ.

- **"Lambda и EC2 — конкуренты, нужно выбрать одно"** — они дополняют друг друга. Lambda: event-driven, короткие задачи, sporadic трафик, нет DevOps. EC2: длительные процессы, WebSocket, специфические требования к OS/RAM, predictable трафик.

- **"IaC можно настроить потом, сначала в консоли"** — антипаттерн. Ресурсы созданные через консоль не воспроизводимы, не версионируются, приводят к "snowflake servers". Infrastructure as Code с первого дня: CDK/Terraform.

- **"Edge Location = AZ"** — это разные вещи. AZ — датацентр в регионе для compute/storage. Edge Location — CloudFront точка присутствия для кэширования/CDN. Edge Location есть в городах где нет региона (больше 250 vs ~33 регионов).
