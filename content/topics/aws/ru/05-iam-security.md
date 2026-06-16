<!-- verified: 2026-06-05, corrections: 0 -->
# IAM и Security

## Что такое IAM

IAM (Identity and Access Management) — система аутентификации и авторизации в AWS. Отвечает на два вопроса: кто ты (Identity) и что тебе можно (Access Management).

```txt
Основные сущности IAM:
  User   — физический пользователь (human or service account)
  Group  — группа пользователей с общими правами
  Role   — набор прав, которые может принять AWS-сервис или пользователь
  Policy — JSON-документ, описывающий что разрешено/запрещено

Иерархия:
  User / Group / Role → attach → Policy → defines permissions
```

## Policy — структура и механизм evaluation

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::my-bucket/*",
      "Condition": {
        "StringEquals": {
          "s3:prefix": ["uploads/"]
        }
      }
    },
    {
      "Effect": "Deny",
      "Action": "s3:DeleteObject",
      "Resource": "*"
    }
  ]
}
```

```txt
Policy Evaluation Logic:
  1. Default: всё DENY (implicit deny)
  2. Если есть явный Allow → разрешено
  3. Если есть явный Deny → всегда перекрывает Allow

Типы политик:
  Identity-based:  прикрепляется к User/Group/Role
  Resource-based:  прикрепляется к ресурсу (S3 Bucket Policy, Lambda Resource Policy)
  SCP (Org-level): ограничивает всю AWS Organization
  Permission Boundary: максимально допустимые права для роли
```

## IAM Role — почему лучше Access Keys

```typescript
// Плохо: hardcoded Access Keys в коде или env файлах
// Проблема: если утечёт .env → полный доступ на неограниченное время
const s3 = new S3Client({
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID!,      // долгоживущий
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!, // credential
  },
});

// Хорошо: Lambda с IAM Role — credentials автоматически из environment
// Lambda runtime предоставляет временные credentials через IMDS
const s3 = new S3Client({ region: process.env.AWS_REGION });
// SDK автоматически подхватывает: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
// AWS_SESSION_TOKEN из переменных среды, которые Lambda Runtime устанавливает
```

```txt
Временные credentials (STS — Security Token Service):
  AccessKeyId:     временный (как у постоянного)
  SecretAccessKey: временный
  SessionToken:    подтверждает что это временный
  Expiration:      обычно 1-12 часов

Lambda получает временные credentials автоматически:
  Lambda Runtime → IMDS endpoint → STS → credentials → SDK
  Не нужно хранить AWS_ACCESS_KEY/SECRET нигде в коде
```

## Trust Policy — кто может принять роль

```typescript
// CDK: создание IAM Role для Lambda с Trust Policy
import * as iam from 'aws-cdk-lib/aws-iam';

const lambdaRole = new iam.Role(this, 'LambdaRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'), // Trust Policy
  managedPolicies: [
    iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
  ],
});

// Добавить только нужные права (Least Privilege):
lambdaRole.addToPolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['s3:GetObject', 's3:PutObject'],
  resources: [`arn:aws:s3:::${bucket.bucketName}/uploads/*`], // конкретный prefix
}));

lambdaRole.addToPolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem'],
  resources: [table.tableArn], // конкретная таблица, не '*'
}));

// Trust Policy для cross-account assume role:
const crossAccountRole = new iam.Role(this, 'CrossAccountRole', {
  assumedBy: new iam.AccountPrincipal('123456789012'), // другой AWS account
});
```

```txt
Trust Policy структура (JSON):
{
  "Principal": { "Service": "lambda.amazonaws.com" },
  "Action": "sts:AssumeRole",
  "Effect": "Allow"
}

Разница:
  Trust Policy  → кто может принять роль (Who)
  Permission Policy → что роль может делать (What)
```

## Principle of Least Privilege — практика

```typescript
// Плохо: AdministratorAccess для Lambda
// Если Lambda скомпрометирована → полный доступ ко всему account
const badRole = new iam.Role(this, 'BadRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
  managedPolicies: [
    iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess'), // никогда!
  ],
});

// Хорошо: минимальные права с конкретными resource ARN
const goodRole = new iam.Role(this, 'GoodRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
});

// Только чтение из конкретного bucket + prefix
bucket.grantRead(handler, 'avatars/*');

// Только запись в конкретную таблицу
table.grantWriteData(handler);

// Только отправка в конкретную SQS очередь
queue.grantSendMessages(handler);
```

## Resource-based Policy — доступ к ресурсу напрямую

```typescript
// S3 Bucket Policy: разрешить CloudFront читать объекты
const bucketPolicy = new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
  actions: ['s3:GetObject'],
  resources: [bucket.arnForObjects('*')],
  conditions: {
    StringEquals: {
      'AWS:SourceArn': distribution.distributionArn,
    },
  },
});

// Lambda Resource Policy: разрешить API Gateway вызывать Lambda
// Создаётся автоматически CDK при addRoutes/addMethod
// Но вручную выглядит так:
new lambda.CfnPermission(this, 'ApiGwPermission', {
  action: 'lambda:InvokeFunction',
  functionName: handler.functionName,
  principal: 'apigateway.amazonaws.com',
  sourceArn: `arn:aws:execute-api:${this.region}:${this.account}:${api.apiId}/*`,
});
```

## IAM в разработке — практические паттерны

```typescript
// 1. CDK Grants — готовые методы для Least Privilege
bucket.grantRead(lambdaFn);          // s3:GetObject, s3:ListBucket
bucket.grantPut(lambdaFn);           // s3:PutObject
table.grantReadWriteData(lambdaFn);  // DynamoDB CRUD без Delete и DropTable
queue.grantConsumeMessages(lambdaFn); // sqs:ReceiveMessage, sqs:DeleteMessage
topic.grantPublish(lambdaFn);        // sns:Publish

// 2. IAM Conditions — ограничение по тегам, IP, время
const tagConditionPolicy = new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['ec2:StopInstances'],
  resources: ['*'],
  conditions: {
    StringEquals: {
      'ec2:ResourceTag/Environment': 'dev', // только dev instances
    },
  },
});

// 3. STS AssumeRole — временный cross-account доступ
import { STSClient, AssumeRoleCommand } from '@aws-sdk/client-sts';

async function assumeRole(roleArn: string) {
  const sts = new STSClient({});
  const { Credentials } = await sts.send(new AssumeRoleCommand({
    RoleArn: roleArn,
    RoleSessionName: 'my-app-session',
    DurationSeconds: 3600, // 1 час
  }));
  return Credentials; // AccessKeyId, SecretAccessKey, SessionToken
}
```

## Типичные ошибки на интервью

- **"IAM User лучше подходит для сервисов, чем Role"** — наоборот: сервисы (Lambda, EC2, ECS) должны использовать IAM Role. User с Access Keys — долгоживущий credential: если утечёт, нужно вручную ротировать. Role выдаёт временные credentials автоматически через STS.

- **"Resource `*` в Policy — это нормально для одного действия"** — нет. `"Resource": "*"` означает, что действие применимо ко ВСЕМ ресурсам типа в аккаунте. Для S3 это все buckets, для DynamoDB — все таблицы. Всегда указывать конкретный ARN.

- **"Deny в одной Policy можно перекрыть Allow в другой"** — явный Deny всегда побеждает. Нельзя "разрешить обратно" то, что явно запрещено, добавив Allow в другую политику. Implicit deny (ничего не упомянуто) можно перекрыть Allow.

- **"Permission Boundary = максимальные права на Identity"** — правильно, но важный нюанс: даже если Permission Boundary разрешает действие, нужна ещё Identity Policy, которая явно разрешает его. Permission Boundary только ограничивает, не предоставляет.

- **"IAM ролью нельзя поделиться между аккаунтами"** — можно через Cross-Account Role: Trust Policy роли в account A разрешает Principal из account B сделать `sts:AssumeRole`. Account B делает AssumeRole → получает временные credentials → работает с ресурсами account A. Основа для multi-account архитектур.
