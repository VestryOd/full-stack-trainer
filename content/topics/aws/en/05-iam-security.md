# IAM and Security

## What is IAM

IAM (Identity and Access Management) is AWS's authentication and authorization system. It answers two questions: who are you (Identity) and what are you allowed to do (Access Management).

```txt
Core IAM entities:
  User   — human user or service account
  Group  — group of users with shared permissions
  Role   — a set of permissions that an AWS service or user can assume
  Policy — a JSON document describing what is allowed/denied

Hierarchy:
  User / Group / Role → attach → Policy → defines permissions
```

## Policy — structure and evaluation mechanism

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
  1. Default: everything is DENY (implicit deny)
  2. If there is an explicit Allow → permitted
  3. If there is an explicit Deny → always overrides Allow

Policy types:
  Identity-based:  attached to User/Group/Role
  Resource-based:  attached to the resource (S3 Bucket Policy, Lambda Resource Policy)
  SCP (Org-level): limits the entire AWS Organization
  Permission Boundary: maximum allowed permissions for a role
```

## IAM Role — why it's better than Access Keys

```typescript
// Bad: hardcoded Access Keys in code or env files
// Problem: if .env leaks → full access with no expiry
const s3 = new S3Client({
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID!,       // long-lived
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!, // credential
  },
});

// Good: Lambda with IAM Role — credentials automatically from environment
// Lambda runtime provides temporary credentials via IMDS
const s3 = new S3Client({ region: process.env.AWS_REGION });
// SDK automatically picks up: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
// AWS_SESSION_TOKEN from env vars that Lambda Runtime sets
```

```txt
Temporary credentials (STS — Security Token Service):
  AccessKeyId:     temporary (looks like a regular one)
  SecretAccessKey: temporary
  SessionToken:    confirms this is a temporary credential
  Expiration:      typically 1-12 hours

Lambda gets temporary credentials automatically:
  Lambda Runtime → IMDS endpoint → STS → credentials → SDK
  No need to store AWS_ACCESS_KEY/SECRET anywhere in code
```

## Trust Policy — who can assume the role

```typescript
// CDK: creating an IAM Role for Lambda with Trust Policy
import * as iam from 'aws-cdk-lib/aws-iam';

const lambdaRole = new iam.Role(this, 'LambdaRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'), // Trust Policy
  managedPolicies: [
    iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
  ],
});

// Add only necessary permissions (Least Privilege):
lambdaRole.addToPolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['s3:GetObject', 's3:PutObject'],
  resources: [`arn:aws:s3:::${bucket.bucketName}/uploads/*`], // specific prefix
}));

lambdaRole.addToPolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem'],
  resources: [table.tableArn], // specific table, not '*'
}));

// Trust Policy for cross-account assume role:
const crossAccountRole = new iam.Role(this, 'CrossAccountRole', {
  assumedBy: new iam.AccountPrincipal('123456789012'), // different AWS account
});
```

```txt
Trust Policy structure (JSON):
{
  "Principal": { "Service": "lambda.amazonaws.com" },
  "Action": "sts:AssumeRole",
  "Effect": "Allow"
}

Distinction:
  Trust Policy      → who can assume the role (Who)
  Permission Policy → what the role can do (What)
```

## Principle of Least Privilege — in practice

```typescript
// Bad: AdministratorAccess for Lambda
// If Lambda is compromised → full access to the entire account
const badRole = new iam.Role(this, 'BadRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
  managedPolicies: [
    iam.ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess'), // never!
  ],
});

// Good: minimal permissions with specific resource ARNs
const goodRole = new iam.Role(this, 'GoodRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
});

// Read-only from a specific bucket + prefix
bucket.grantRead(handler, 'avatars/*');

// Write-only to a specific table
table.grantWriteData(handler);

// Send-only to a specific SQS queue
queue.grantSendMessages(handler);
```

## Resource-based Policy — direct resource access

```typescript
// S3 Bucket Policy: allow CloudFront to read objects
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

// Lambda Resource Policy: allow API Gateway to invoke Lambda
// Created automatically by CDK on addRoutes/addMethod
// But manually it looks like:
new lambda.CfnPermission(this, 'ApiGwPermission', {
  action: 'lambda:InvokeFunction',
  functionName: handler.functionName,
  principal: 'apigateway.amazonaws.com',
  sourceArn: `arn:aws:execute-api:${this.region}:${this.account}:${api.apiId}/*`,
});
```

## IAM in development — practical patterns

```typescript
// 1. CDK Grants — ready-made Least Privilege methods
bucket.grantRead(lambdaFn);           // s3:GetObject, s3:ListBucket
bucket.grantPut(lambdaFn);            // s3:PutObject
table.grantReadWriteData(lambdaFn);   // DynamoDB CRUD without Delete/DropTable
queue.grantConsumeMessages(lambdaFn); // sqs:ReceiveMessage, sqs:DeleteMessage
topic.grantPublish(lambdaFn);         // sns:Publish

// 2. IAM Conditions — restrict by tags, IP, time
const tagConditionPolicy = new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['ec2:StopInstances'],
  resources: ['*'],
  conditions: {
    StringEquals: {
      'ec2:ResourceTag/Environment': 'dev', // only dev instances
    },
  },
});

// 3. STS AssumeRole — temporary cross-account access
import { STSClient, AssumeRoleCommand } from '@aws-sdk/client-sts';

async function assumeRole(roleArn: string) {
  const sts = new STSClient({});
  const { Credentials } = await sts.send(new AssumeRoleCommand({
    RoleArn: roleArn,
    RoleSessionName: 'my-app-session',
    DurationSeconds: 3600, // 1 hour
  }));
  return Credentials; // AccessKeyId, SecretAccessKey, SessionToken
}
```

## Common interview mistakes

- **"IAM User is better suited for services than Role"** — the opposite: services (Lambda, EC2, ECS) should use IAM Roles. A User with Access Keys is a long-lived credential: if it leaks, you must manually rotate it. A Role issues temporary credentials automatically via STS.

- **"Resource `*` in a Policy is fine for a single action"** — no. `"Resource": "*"` means the action applies to ALL resources of that type in the account. For S3, that's all buckets; for DynamoDB — all tables. Always specify a concrete ARN.

- **"A Deny in one Policy can be overridden by an Allow in another"** — explicit Deny always wins. You cannot "re-allow" something explicitly denied by adding an Allow in another policy. Implicit deny (not mentioned) can be overridden by an Allow.

- **"Permission Boundary = maximum permissions on an Identity"** — correct, but with an important nuance: even if the Permission Boundary allows an action, there must also be an Identity Policy that explicitly allows it. Permission Boundary only restricts, it does not grant.

- **"An IAM Role can't be shared between accounts"** — it can, via Cross-Account Role: the Trust Policy of a role in account A allows a Principal from account B to call `sts:AssumeRole`. Account B calls AssumeRole → gets temporary credentials → works with resources in account A. This is the foundation of multi-account architectures.
