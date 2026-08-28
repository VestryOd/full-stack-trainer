<!-- verified: 2026-06-05, corrections: 0 -->
# IAM и Security

## Что такое IAM

IAM (Identity and Access Management) — система аутентификации и авторизации в AWS (Amazon Web Services). Она отвечает на два вопроса: кто вы (Identity) и что вам можно (Access Management).

Всё держится на четырёх сущностях:

- **User** — живой пользователь или сервисный аккаунт.
- **Group** — группа пользователей с общими правами.
- **Role** — набор прав, которые может принять сервис AWS или пользователь.
- **Policy** — JSON-документ, описывающий, что разрешено, а что запрещено.

Складываются они в одну сторону. Вы прикрепляете Policy к User, Group или Role, и именно Policy определяет права.

## Policy — структура и порядок вычисления

Политика — это JSON-документ со списком утверждений. Та, что ниже, разрешает два действия с S3 (Simple Storage Service) внутри одного префикса и наотрез запрещает удаление.

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

**Как политика вычисляется**

1. По умолчанию запрещено всё. Это неявный запрет, implicit deny.
2. Явный Allow разрешает действие.
3. Явный Deny всегда перекрывает Allow.

**Типы политик**

- **Identity-based** — прикрепляется к User, Group или Role.
- **Resource-based** — прикрепляется к самому ресурсу: S3 Bucket Policy, Lambda Resource Policy.
- **SCP (Service Control Policy)** — политика уровня организации, ограничивает всю AWS Organization.
- **Permission Boundary** — максимальные права, которые роль вообще может получить.

## IAM Role — почему лучше Access Keys

Role выигрывает у Access Keys одним свойством: выданные ею ключи протухают сами. Сниппет ставит два подхода рядом.

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

Эти временные ключи выдаёт STS (Security Token Service), и у них четыре поля:

- `AccessKeyId` — временный, хотя выглядит как обычный.
- `SecretAccessKey` — временный.
- `SessionToken` — поле, которое и подтверждает временность ключа.
- `Expiration` — обычно 1-12 часов.

Lambda получает их без единой строки вашего кода. Среда выполнения Lambda обращается к точке IMDS (instance metadata service), IMDS идёт в STS, а SDK (software development kit) забирает результат. Никакие `AWS_ACCESS_KEY` и `AWS_SECRET` хранить в коде не нужно.

## Trust Policy — кто может принять роль

У роли две разные политики, и путают их постоянно. Trust Policy говорит, кто может принять роль; политика прав говорит, что роль потом может делать.

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

Сама Trust Policy — короткий JSON-документ:

```json
{
  "Principal": { "Service": "lambda.amazonaws.com" },
  "Action": "sts:AssumeRole",
  "Effect": "Allow"
}
```

Разницу стоит запомнить:

| Политика | На какой вопрос отвечает |
|---|---|
| Trust Policy | Кто может принять роль |
| Permission Policy | Что роль может делать |

## Principle of Least Privilege — практика

Наименьшие привилегии — это про то, чтобы называть конкретный ресурс, а не конкретный сервис. Ниже рядом стоят админская роль, которой не должно существовать, и роль, суженная до одного префикса, одной таблицы и одной очереди.

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

Ресурсная политика висит на самом ресурсе, а не на вызывающем, и это единственный способ пустить к нему другой сервис. Здесь CloudFront получает право читать бакет, а API Gateway — право вызывать Lambda.

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

Три приёма закрывают почти всю ежедневную работу с IAM. Методы grant из CDK (Cloud Development Kit) заменяют политики, написанные руками. Условия сужают право до тегов или времени. AssumeRole открывает временную дверь в другой аккаунт.

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

- **«IAM User лучше подходит для сервисов, чем Role»** — всё наоборот. Сервисы вроде Lambda, EC2 (Elastic Compute Cloud) и ECS (Elastic Container Service) должны использовать IAM Role. User с Access Keys — это долгоживущий ключ: если он утечёт, ротировать придётся руками. Role выдаёт временные ключи автоматически через STS.

- **«Resource `*` в Policy — это нормально для одного действия»** — нет. `"Resource": "*"` означает, что действие применимо к **каждому** ресурсу этого типа в аккаунте. Для S3 это все бакеты, для DynamoDB — все таблицы. Всегда указывайте конкретный ARN (Amazon Resource Name).

- **«Deny в одной Policy можно перекрыть Allow в другой»** — явный Deny всегда побеждает. Нельзя «разрешить обратно» то, что явно запрещено, добавив Allow в другую политику. А вот неявный запрет, когда ресурс нигде не упомянут, перекрыть через Allow можно.

- **«Permission Boundary = максимальные права на Identity»** — верно, но с важным нюансом. Даже когда Permission Boundary разрешает действие, нужна ещё Identity Policy, которая разрешает его явно. Permission Boundary только ограничивает и никогда ничего не выдаёт.

- **«IAM-ролью нельзя поделиться между аккаунтами»** — можно, через Cross-Account Role. Trust Policy роли в аккаунте A разрешает Principal из аккаунта B вызвать `sts:AssumeRole`. Аккаунт B вызывает AssumeRole, получает временные ключи и работает с ресурсами аккаунта A. На этом стоят все многоаккаунтные архитектуры.
