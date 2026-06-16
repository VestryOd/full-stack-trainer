# AWS: Cloud Platform Fundamentals

## What is AWS and why cloud?

AWS (Amazon Web Services) is the largest cloud platform: over 200 services, >32% of the cloud market (2024). The idea: instead of buying, configuring, and maintaining physical servers — rent compute resources on demand and pay only for what you use.

**Key benefits for developers**:
- No capital expenditure (CAPEX → OPEX)
- Instant scaling (vertical and horizontal)
- Global infrastructure (33 regions, 105 AZs as of 2024)
- Managed services: no need to manage OS/patches for RDS, Lambda, S3

## Cloud service models (IaaS / PaaS / SaaS)

```txt
IaaS (Infrastructure as a Service):
  AWS provides: VMs, networking, block storage
  You manage: OS, runtime, application, data
  Example: EC2 (you launch a Linux server, install Node.js and nginx yourself)
  When: you need full control over the environment, legacy app

PaaS (Platform as a Service):
  AWS manages: OS, runtime, scaling
  You manage: code and data
  Examples: Lambda (just code), Elastic Beanstalk (deploy Docker/Node)
  When: you want to focus on business logic, not infrastructure

SaaS (Software as a Service):
  A ready-made product out of the box
  Examples: AWS WorkMail, Gmail, Notion
  When: you consume the product, not build on it

Shared Responsibility splits by model:
  IaaS: AWS = physical security + hardware; You = all software above
  PaaS: AWS = OS + runtime + patches; You = code + data + config
  SaaS: AWS = everything; You = only user data
```

## Global infrastructure: Region, AZ, Edge Location

```txt
Region:
  An independent geographic cluster of data centers.
  Examples: eu-west-1 (Ireland), us-east-1 (Virginia), ap-southeast-1 (Singapore)
  Isolation: a failure in one region doesn't affect another.
  How to choose: proximity to users (latency), compliance (GDPR → EU),
  available services (not all services in all regions), cost.

Availability Zone (AZ):
  An isolated data center (or group) within a region.
  Connected by low-latency (<1ms) private fiber — faster than the internet.
  Example: eu-west-1a, eu-west-1b, eu-west-1c
  Principle: deploy the application in 2+ AZs → high availability.
  If eu-west-1a fails: traffic automatically routes to eu-west-1b.

Edge Location (CloudFront PoP):
  Points of presence for CDN content caching (250+ worldwide).
  Closer to users than a region → lower latency for static assets.
  Used by CloudFront, Route53, AWS Shield.
```

```txt
Architectural rule: static assets → S3 + CloudFront (Edge).
Application → 2+ AZs in one region. Disaster Recovery → replica in
another region (RDS Multi-Region Read Replica, S3 Cross-Region Replication).
```

## Shared Responsibility Model — who is responsible for what

Critically important in interviews: candidates often confuse AWS responsibility and their own.

```txt
AWS is responsible for ("Security OF the Cloud"):
  ✓ Physical data center security (guards, cameras, access control)
  ✓ Hardware (servers, networking, storage)
  ✓ AWS global network (fiber, backbone)
  ✓ Hypervisor (for EC2)
  ✓ Managed service OS and patches (RDS, Lambda, ECS Fargate)

You are responsible for ("Security IN the Cloud"):
  ✓ IAM: users, roles, policies (least privilege)
  ✓ Data: encryption at rest and in transit, backups
  ✓ Configuration: security groups, NACLs, public vs private subnet
  ✓ Application: code, dependencies, input validation
  ✓ EC2 OS: your OS → your patches (AWS does not update Linux kernel on EC2)
  ✓ S3: bucket policies (block public access!)
```

## Key services — an ecosystem map

```txt
Compute:
  EC2         — Virtual Machines (IaaS), full control
  Lambda      — Functions as a Service, event-driven, serverless
  ECS/Fargate — Docker containers (ECS = orchestrator, Fargate = serverless compute)
  EKS         — Managed Kubernetes

Storage:
  S3          — Object storage, infinite scale, 11 nines durability
  EBS         — Block storage (disk for EC2, like an SSD in a server)
  EFS         — Managed NFS (shared filesystem between EC2 instances)

Database:
  RDS         — Managed PostgreSQL/MySQL/Aurora (OLTP)
  Aurora      — AWS-optimized PostgreSQL/MySQL, 5x faster
  DynamoDB    — NoSQL key-value, single-digit ms latency, infinite scale
  ElastiCache — Managed Redis/Memcached

Messaging:
  SQS         — Queue (async decoupling, at-least-once delivery)
  SNS         — Pub/Sub fan-out (one message → many subscribers)
  EventBridge — Event bus (rule-based routing, integrations)

Networking:
  VPC         — Virtual Private Cloud (isolated network)
  ALB/NLB     — Load Balancers (HTTP/TCP)
  Route53     — DNS + health checks + routing policies
  CloudFront  — CDN + edge caching + WAF

Security:
  IAM         — Identity and Access Management (roles, policies)
  Secrets Manager — secure storage and rotation of secrets
  KMS         — encryption key management
  WAF         — Web Application Firewall (OWASP rules)
  GuardDuty   — threat detection (ML-based)

IaC:
  CloudFormation — native AWS IaC (YAML/JSON templates)
  CDK            — TypeScript/Python → CloudFormation (recommended)
  Terraform      — multi-cloud IaC (HashiCorp, popular in enterprise)
```

## AWS CDK — Infrastructure as Code in TypeScript

CDK (Cloud Development Kit) lets you describe AWS infrastructure in TypeScript, Python, or Java. CDK → synth → CloudFormation → deploy.

```typescript
import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';

export class MyAppStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 bucket for file storage
    const bucket = new s3.Bucket(this, 'AppBucket', {
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.RETAIN, // don't delete on cdk destroy
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

    // Grant Lambda read access to the bucket (least privilege)
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
npx cdk synth    # generate CloudFormation template (review it)
npx cdk diff     # show changes before deploying
npx cdk deploy   # deploy changes
npx cdk destroy  # delete the stack (caution: RETAIN resources remain)
```

**CDK advantages over raw CloudFormation**: type safety (TypeScript compiler validates), higher-level abstractions (Construct library), code reuse (loops, conditionals, classes), testability (jest + CDK assertions).

## Pricing model — Pay-as-you-go

```txt
Core principles:
  - Pay only for what you use (EC2: billed per hour/second)
  - Higher usage → lower unit cost (volume discounts)
  - Reserved Instances: upfront 1-3 year commitment → up to 72% discount
  - Spot Instances: unused EC2 capacity → up to 90% cheaper, but can be interrupted

Free Tier:
  EC2: 750 hrs/mo t2.micro (12 months)
  S3: 5GB storage, 20k GET, 2k PUT (12 months)
  Lambda: 1M requests/mo + 400k GB-sec (forever)
  RDS: 750 hrs/mo db.t2.micro (12 months)

Typical costs for a small SaaS:
  S3 + CloudFront: $1-5/mo
  Lambda (1M req/mo): free or ~$0.20
  RDS t3.micro: ~$13/mo
  ALB: ~$16/mo (base) + per-request
```

## Common interview mistakes

- **"AWS is responsible for the security of data in S3"** — no. S3 bucket policy, public access settings, encryption — all the user's responsibility. AWS only guarantees the physical integrity of the hardware. S3 public bucket incidents (data leaks) are 100% user misconfiguration.

- **"A Region is a single data center"** — a region consists of multiple AZs (minimum 3), and each AZ is an isolated data center. A single EC2 in one AZ = single point of failure. HA requires 2+ AZs.

- **"Lambda and EC2 are competitors — pick one"** — they complement each other. Lambda: event-driven, short-lived tasks, sporadic traffic, no DevOps overhead. EC2: long-running processes, WebSocket, specific OS/RAM requirements, predictable traffic.

- **"IaC can be set up later; start in the console"** — anti-pattern. Resources created through the console aren't reproducible, aren't versioned, and lead to "snowflake servers." Infrastructure as Code from day one: CDK/Terraform.

- **"Edge Location = AZ"** — these are different things. AZ is a data center in a region for compute/storage. Edge Location is a CloudFront point of presence for caching/CDN. There are Edge Locations in cities with no region (250+ vs ~33 regions).
