# AWS: Cloud Platform Fundamentals

## What is AWS and why cloud?

AWS (Amazon Web Services) is the largest cloud platform: over 200 services, >32% of the cloud market (2024). The idea: instead of buying, configuring, and maintaining physical servers — rent compute resources on demand and pay only for what you use.

**Key benefits for developers**:

- **No capital expenditure.** CAPEX (capital expenditure) is money paid up front for hardware you own; OPEX (operational expenditure) is a monthly bill for capacity you used. The cloud turns the first into the second.
- **Instant scaling**, vertical (a bigger machine) and horizontal (more machines).
- **Global infrastructure**: 33 regions and 105 availability zones (AZ) as of 2024.
- **Managed services** — you never patch the operating system (OS) for RDS (Relational Database Service), Lambda or S3 (Simple Storage Service).

## Cloud service models (IaaS / PaaS / SaaS)

Infrastructure as a Service (IaaS) hands you raw machines. Platform as a Service (PaaS) hands you a managed runtime. Software as a Service (SaaS) hands you a finished product. The difference is how much of the stack you still run yourself.

**IaaS — Infrastructure as a Service**

- AWS provides: virtual machines, networking, block storage.
- You manage: the operating system, the runtime, the application, the data.
- Example: EC2 (Elastic Compute Cloud) — you launch a Linux server, and install Node.js and nginx yourself.
- When: you need full control over the environment, or you are moving a legacy app.

**PaaS — Platform as a Service**

- AWS manages: the operating system, the runtime, scaling.
- You manage: code and data.
- Examples: Lambda (just code) and Elastic Beanstalk (deploy a Docker or Node app).
- When: you want to focus on business logic, not on infrastructure.

**SaaS — Software as a Service**

- A ready-made product out of the box.
- Examples: AWS WorkMail, Gmail, Notion.
- When: you consume the product rather than build on it.

The Shared Responsibility Model splits along the same line:

| Model | AWS is responsible for | You are responsible for |
|---|---|---|
| IaaS | Physical security and hardware | Every layer of software above the hypervisor |
| PaaS | Operating system, runtime, patches | Code, data, configuration |
| SaaS | Everything | Only your own user data |

## Global infrastructure: Region, AZ, Edge Location

Three nested layers. A region gives you geography, an availability zone gives you fault isolation inside it, and an edge location gives you low latency on cached files.

**Region** — an independent geographic cluster of data centers: `eu-west-1` (Ireland), `us-east-1` (Virginia), `ap-southeast-1` (Singapore). A failure in one region does not affect another. Four things decide which one you pick:

- Proximity to users — this is where latency comes from.
- Compliance: GDPR (General Data Protection Regulation) keeps personal data of European Union residents in an EU region.
- Available services — not all services exist in all regions.
- Cost, which differs between regions for the same resource.

**Availability Zone (AZ)** — an isolated data center, or a group of them, inside one region: `eu-west-1a`, `eu-west-1b`, `eu-west-1c`. Zones are wired by private fiber with under 1 ms latency, faster than the public internet. Deploy into 2+ zones and you get high availability (HA): if `eu-west-1a` fails, traffic moves to `eu-west-1b` automatically.

**Edge Location**, also called a CloudFront PoP (point of presence) — one of 250+ caching points of the CDN (content delivery network) worldwide. Closer to the user than any region, so static assets arrive faster. Used by CloudFront, Route53 and AWS Shield.

Architectural rule: static assets go to S3 behind CloudFront, the application runs in 2+ availability zones of one region. Disaster Recovery means a replica in another region — an RDS Multi-Region Read Replica, or S3 Cross-Region Replication.

## Shared Responsibility Model — who is responsible for what

Critically important in interviews, because candidates often confuse the two sides: AWS secures the cloud, you secure what you put into it.

**AWS secures the cloud itself** (in AWS wording, "security of the cloud"):

- Physical data center security: guards, cameras, access control.
- Hardware: servers, networking, storage.
- The AWS global network — fiber and backbone.
- The hypervisor that runs EC2 virtual machines.
- The operating system and its patches inside managed services: RDS, Lambda, and ECS (Elastic Container Service) Fargate.

**You secure what you run in the cloud** ("security in the cloud"):

- IAM (Identity and Access Management): users, roles, policies, least privilege.
- Data: encryption at rest and in transit, plus backups.
- Configuration: security groups, network access control lists (NACL), public versus private subnets.
- The application: your code, your dependencies, input validation.
- The operating system on your own EC2 instances. Your OS means your patches — AWS does not update the Linux kernel on EC2 for you.
- S3 bucket policies. Block public access.

## Key services — an ecosystem map

AWS has over 200 services. The two dozen below are the ones you meet on a web project, grouped by the job they do. A typical Node.js application needs only a handful: object storage, a managed database, a function runtime, a queue, a CDN and IAM roles. The rest are listed so you recognize the name when it comes up.

**Compute — where your code runs**

- **EC2** (Elastic Compute Cloud) — virtual machines (IaaS), full control.
- **Lambda** — functions as a service, event-driven, serverless.
- **ECS / Fargate** — Docker containers. ECS is the orchestrator, Fargate is the serverless compute under it.
- **EKS** (Elastic Kubernetes Service) — managed Kubernetes.

**Storage — where bytes live**

- **S3** — object storage, infinite scale, 11 nines of durability.
- **EBS** (Elastic Block Store) — block storage: a disk for one EC2 instance, like an SSD (solid-state drive) in a server.
- **EFS** (Elastic File System) — managed NFS (network file system), shared between EC2 instances.

**Databases**

- **RDS** — managed PostgreSQL, MySQL or Aurora for OLTP (online transaction processing).
- **Aurora** — AWS-optimized PostgreSQL and MySQL, 5x faster.
- **DynamoDB** — NoSQL (non-relational) key-value store, single-digit millisecond latency, infinite scale.
- **ElastiCache** — managed Redis or Memcached.

**Messaging**

- **SQS** (Simple Queue Service) — a queue for async decoupling, at-least-once delivery.
- **SNS** (Simple Notification Service) — publish/subscribe fan-out: one message, many subscribers.
- **EventBridge** — an event bus with rule-based routing and integrations.

**Networking**

- **VPC** (Virtual Private Cloud) — your isolated network inside AWS.
- **ALB / NLB** — load balancers. ALB (Application Load Balancer) routes HTTP requests, NLB (Network Load Balancer) routes raw connections (TCP).
- **Route53** — DNS (domain name system), health checks, routing policies.
- **CloudFront** — the CDN: edge caching plus a WAF (web application firewall).

**Security**

- **IAM** — roles and policies: who is allowed to do what.
- **Secrets Manager** — secure storage and rotation of secrets.
- **KMS** (Key Management Service) — encryption key management.
- **WAF** — request filtering with OWASP (Open Web Application Security Project) rule sets.
- **GuardDuty** — threat detection driven by machine learning.

**Infrastructure as code**

- **CloudFormation** — native AWS infrastructure as code (IaC): templates in YAML (a plain-text config format) or JSON.
- **CDK** (Cloud Development Kit) — TypeScript or Python compiled to CloudFormation, and the recommended path.
- **Terraform** — multi-cloud IaC from HashiCorp, popular in enterprise.

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

**CDK advantages over raw CloudFormation:**

- Type safety — the TypeScript compiler validates the stack before you deploy it.
- Higher-level abstractions from the Construct library.
- Code reuse: loops, conditionals and classes instead of copy-pasted templates.
- Testability with jest and CDK assertions.

## Pricing model — Pay-as-you-go

AWS bills by consumption: per hour or second for machines, per request for functions and storage operations.

**Core principles**

- You pay only for what you use — EC2 is billed per hour or per second.
- The more you use, the lower the unit price (volume discounts).
- Reserved Instances: an upfront 1-3 year commitment gives up to 72% discount.
- Spot Instances: unused EC2 capacity, up to 90% cheaper, but it can be interrupted.

**Free Tier**

- EC2: 750 hours a month of `t2.micro`, for 12 months.
- S3: 5 gigabytes of storage, 20k GET, 2k PUT, for 12 months.
- Lambda: 1M requests a month plus 400k gigabyte-seconds, forever.
- RDS: 750 hours a month of `db.t2.micro`, for 12 months.

**Typical costs for a small SaaS, per month**

- S3 + CloudFront: $1-5.
- Lambda at 1M requests: free, or about $0.20.
- RDS `t3.micro`: about $13.
- ALB: about $16 base, plus a per-request charge.

## Common interview mistakes

- **"AWS is responsible for the security of data in S3"** — no. The bucket policy, the public access settings and the encryption are all the user's responsibility. AWS only guarantees the physical integrity of the hardware. S3 public bucket incidents (data leaks) are 100% user misconfiguration.

- **"A Region is a single data center"** — a region consists of multiple availability zones (minimum 3), and each zone is an isolated data center. A single EC2 in one zone is a single point of failure. High availability requires 2+ zones.

- **"Lambda and EC2 are competitors — pick one"** — they complement each other. Lambda suits event-driven, short-lived tasks, irregular traffic and teams with no servers to operate. EC2 suits long-running processes, WebSocket connections, specific operating system or memory requirements, and steady predictable traffic.

- **"Infrastructure as code can be set up later; start in the console"** — anti-pattern. Resources created through the console are not reproducible and not versioned, and they lead to "snowflake servers". Write infrastructure as code from day one, with CDK or Terraform.

- **"Edge Location = AZ"** — these are different things. An availability zone is a data center in a region for compute and storage. An edge location is a CloudFront point of presence for caching. There are edge locations in cities with no region at all (250+ versus ~33 regions).
