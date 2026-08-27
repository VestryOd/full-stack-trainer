# IAM and Security

## What is IAM

IAM (Identity and Access Management) is the authentication and authorization system of AWS (Amazon Web Services). It answers two questions: who are you (Identity) and what are you allowed to do (Access Management).

Four entities carry all of it:

- **User** — a human user, or a service account.
- **Group** — a group of users with shared permissions.
- **Role** — a set of permissions that an AWS service or a user can assume.
- **Policy** — a JSON document describing what is allowed and what is denied.

They stack in one direction. You attach a Policy to a User, a Group or a Role, and that Policy is what defines the permissions.

## Policy — structure and evaluation mechanism

A policy is a JSON document with a list of statements. The one below allows two S3 (Simple Storage Service) actions under a single prefix, and denies deletion outright.

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

**How a policy is evaluated**

1. Everything is denied by default. This is the implicit deny.
2. An explicit Allow permits the action.
3. An explicit Deny always overrides an Allow.

**Policy types**

- **Identity-based** — attached to a User, a Group or a Role.
- **Resource-based** — attached to the resource itself: an S3 Bucket Policy, a Lambda Resource Policy.
- **SCP (Service Control Policy)** — an organization-level policy that limits the entire AWS Organization.
- **Permission Boundary** — the maximum permissions a role is ever allowed to hold.

## IAM Role — why it's better than Access Keys

A Role beats Access Keys on one property: the credentials it hands out expire by themselves. The snippet puts the two side by side.

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

Those temporary credentials come from STS (Security Token Service) and have four fields:

- `AccessKeyId` — temporary, even though it looks like a regular one.
- `SecretAccessKey` — temporary.
- `SessionToken` — the field that confirms this is a temporary credential.
- `Expiration` — typically 1-12 hours.

Lambda obtains them with no code from you. The Lambda runtime calls the IMDS (instance metadata service) endpoint, IMDS calls STS, and the SDK (software development kit) picks the credentials up. No `AWS_ACCESS_KEY` or `AWS_SECRET` has to be stored anywhere in the code.

## Trust Policy — who can assume the role

A role carries two different policies, and confusing them is the classic mistake. The Trust Policy says who may assume the role; the permission policy says what the role may do afterwards.

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

The Trust Policy itself is a short JSON document:

```json
{
  "Principal": { "Service": "lambda.amazonaws.com" },
  "Action": "sts:AssumeRole",
  "Effect": "Allow"
}
```

The distinction worth memorizing:

| Policy | Question it answers |
|---|---|
| Trust Policy | Who can assume the role |
| Permission Policy | What the role can do |

## Principle of Least Privilege — in practice

Least privilege is about naming the exact resource, not the exact service. Below, an admin role that should never exist stands next to a role scoped to one bucket prefix, one table and one queue.

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

A resource-based policy hangs on the resource instead of the caller, and that is the only way to let another service reach it. Here CloudFront gets read access to a bucket, and API Gateway gets permission to invoke a Lambda.

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

Three patterns cover almost all day-to-day IAM work. CDK (Cloud Development Kit) grant methods replace hand-written policies. Conditions narrow a permission down to tags or time. AssumeRole opens a temporary door into another account.

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

- **"IAM User is better suited for services than Role"** — the opposite is true. Services such as Lambda, EC2 (Elastic Compute Cloud) and ECS (Elastic Container Service) should use IAM Roles. A User with Access Keys is a long-lived credential: if it leaks, you have to rotate it by hand. A Role issues temporary credentials automatically through STS.

- **"Resource `*` in a Policy is fine for a single action"** — no. `"Resource": "*"` means the action applies to **every** resource of that type in the account. For S3 that is all buckets, for DynamoDB all tables. Always name a concrete ARN (Amazon Resource Name).

- **"A Deny in one Policy can be overridden by an Allow in another"** — explicit Deny always wins. You cannot "re-allow" something explicitly denied by adding an Allow in another policy. Implicit deny (not mentioned) can be overridden by an Allow.

- **"Permission Boundary = maximum permissions on an Identity"** — correct, with one important nuance. Even when the Permission Boundary allows an action, an Identity Policy still has to allow it explicitly. A Permission Boundary only restricts; it never grants.

- **"An IAM Role can't be shared between accounts"** — it can, through a Cross-Account Role. The Trust Policy of a role in account A allows a Principal from account B to call `sts:AssumeRole`. Account B calls AssumeRole, receives temporary credentials, and works with resources in account A. This is the foundation of multi-account architectures.
