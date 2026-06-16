# Lambda and Serverless

## What is AWS Lambda and the Serverless model

Lambda is Function as a Service (FaaS): you upload code, AWS handles infrastructure, scaling, and monitoring. "Serverless" doesn't mean no servers — they exist, but the developer doesn't manage them.

```txt
Traditional EC2:                  Lambda:
  Provision VM                      Upload code
  Configure OS + runtime            Configure trigger + memory
  Deploy application                AWS handles everything else
  Configure auto-scaling
  Patch OS
  Pay 24/7 for uptime

Lambda pricing:
  $0.20 per 1M requests
  $0.0000166667 per GB-second
  Free Tier: 1M req/mo + 400k GB-sec forever

At 100k req/mo, 128MB, 200ms:
  Cost ≈ $0.00 (within Free Tier)
EC2 t3.micro: ~$8/mo with zero load
```

## Execution Model — Lambda function lifecycle

```txt
Invocation → Cold or Warm Start:

Cold Start (new execution environment):
  1. Download deployment package (ZIP/container image)
  2. Start runtime (Node.js/Python/Java sandbox)
  3. Run init code (outside handler): imports, DB connections
  4. Call handler(event, context)

Warm Start (existing execution environment):
  1. Call handler(event, context)  ← only this

After a call the container is "frozen" for ~5-15 minutes.
Next invocation: warm start if container is alive, cold start if not.

Concurrency: each CONCURRENT invocation = separate execution environment.
  100 concurrent requests = 100 containers (or cold starts if the first).
  Lambda automatically scales concurrency up to the account limit (default 1000).
```

## Cold Start — causes, measurement, optimization

```txt
Factors affecting cold start latency:
  Heavy: Java Spring + NestJS → 2-5 seconds
  Medium: Node.js with TypeORM + many imports → 500-1500ms
  Light:  Go/Rust binary → 50-100ms
  Cause: runtime initialization time + package size + init code

Optimization strategies:

1. Minimize bundle size:
   esbuild or tsup instead of webpack → minimal bundle
   Tree shaking: don't import the entire aws-sdk, only what's needed
   // BAD:
   import AWS from 'aws-sdk';
   // GOOD:
   import { S3Client } from '@aws-sdk/client-s3';

2. Lazy initialization (defer DB connection):
   // BAD: DB connection created immediately on every cold start
   const db = createPool({ ... }); // outside handler → always on cold start

   // GOOD: create on first call, reuse on warm starts
   let dbPool: Pool | null = null;
   export async function handler(event: APIGatewayEvent) {
     if (!dbPool) dbPool = await createPool({ ... });
     // ...
   }

3. Provisioned Concurrency:
   Pre-warms N execution environments → no cold starts for N concurrent.
   Cost: you pay for initialized envs continuously.
   Good for: latency-critical APIs with predictable traffic.

4. Lambda SnapStart (Java):
   Snapshot of an initialized execution environment → ~200ms restore.
   Not available for Node.js/Python.
```

## Typical Lambda Handler in TypeScript

```typescript
import { APIGatewayProxyEvent, APIGatewayProxyResult, Context } from 'aws-lambda';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand } from '@aws-sdk/lib-dynamodb';

// Initialize outside handler → reused on warm starts
const ddbClient = new DynamoDBClient({ region: process.env.AWS_REGION });
const docClient = DynamoDBDocumentClient.from(ddbClient);

export async function handler(
  event: APIGatewayProxyEvent,
  context: Context
): Promise<APIGatewayProxyResult> {
  // context.getRemainingTimeInMillis() → ms remaining before timeout

  const userId = event.pathParameters?.userId;
  if (!userId) {
    return { statusCode: 400, body: JSON.stringify({ error: 'userId required' }) };
  }

  try {
    const result = await docClient.send(new GetCommand({
      TableName: process.env.TABLE_NAME!,
      Key: { pk: `USER#${userId}` },
    }));

    if (!result.Item) {
      return { statusCode: 404, body: JSON.stringify({ error: 'Not found' }) };
    }

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(result.Item),
    };
  } catch (err) {
    console.error('DynamoDB error:', err); // → CloudWatch Logs automatically
    return { statusCode: 500, body: JSON.stringify({ error: 'Internal error' }) };
  }
}
```

## Triggers — what invokes Lambda

```txt
Synchronous (Lambda waits and returns a response):
  API Gateway / Function URL → HTTP request/response
  ALB → Lambda as a backend
  CloudFront Functions → edge processing

Asynchronous (Lambda receives event, no response expected):
  S3 → "file uploaded" → Lambda (image resize)
  SNS → "message received" → Lambda
  EventBridge → "scheduled cron" → Lambda
  Lambda retries on error: 2 times (with backoff), then Dead Letter Queue

Stream-based (Lambda polls the source):
  SQS → Lambda polls batch of messages (batch size 1-10000)
  Kinesis → Lambda polls records (on error — bisects batch)
  DynamoDB Streams → Lambda reacts to table changes
```

## Concurrency and Limits

```txt
Default Account Concurrent Executions: 1000 (can be raised)
Burst limit: 500-3000/sec (region-dependent)
Timeout: maximum 15 minutes (900 sec)
Memory: 128MB – 10240MB (CPU scales with memory)
Deployment package: 50MB ZIP / 10GB container image
/tmp storage: 512MB – 10240MB (ephemeral, within invocation only)
Payload (synchronous): 6MB request + 6MB response
Payload (asynchronous): 256KB

Reserved Concurrency: reserve N concurrency for a function.
  Guarantees: at least N always available.
  Caps: no more than N (throttle on overflow → SQS/retry).

Throttling: exceeding concurrency → HTTP 429 (sync) or retry (async).
```

## Lambda + VPC — access to RDS/ElastiCache

```typescript
// Lambda in a VPC for access to RDS in a private subnet
const lambdaFn = new lambda.Function(this, 'ApiHandler', {
  runtime: lambda.Runtime.NODEJS_20_X,
  handler: 'index.handler',
  code: lambda.Code.fromAsset('dist'),
  vpc,
  vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
  securityGroups: [lambdaSecurityGroup],
  // Note: Lambda in VPC → cold start +100-600ms (ENI provisioning)
  // Mitigation: use RDS Proxy (connection pooling)
});

// RDS Proxy: solves "1000 Lambda * DB connection = pool exhaustion"
// Lambda → RDS Proxy (pooling) → RDS (far fewer real connections)
```

**Important**: Lambda in a VPC has no internet access by default. To access AWS APIs (S3, DynamoDB): you need a NAT Gateway (expensive) or VPC Endpoints (cheaper).

## Lambda vs ECS/EC2

```txt
Lambda:
  ✓ Sporadic traffic (no traffic → no cost)
  ✓ Event processing (S3, SQS, SNS)
  ✓ Simple HTTP API with API Gateway
  ✓ Background jobs, scheduled tasks (cron)
  ✓ File processing (thumbnail generation)
  ✗ Persistent WebSocket connections
  ✗ Tasks longer than 15 min
  ✗ CPU-intensive tasks (video encoding)
  ✗ Stateful services

ECS/Fargate:
  ✓ Predictable, high-volume traffic
  ✓ WebSocket servers
  ✓ Stateful services
  ✓ Complex NestJS monoliths
  ✓ Tasks with no time limit
  ✗ No cold start (always running)
  ✗ Costs money at zero traffic
```

## Common interview mistakes

- **"Lambda is stateless — nothing can be stored between calls"** — the execution environment is reused on warm starts. Variables outside the handler (DB connections, cached data) persist between calls ON THE SAME CONTAINER. But you can't rely on specific state being present on the next call (it might be a different container).

- **"Cold starts can be eliminated with Provisioned Concurrency"** — you can reduce them to zero for N concurrent, but this costs money for constantly "warmed" environments. For most APIs: optimize the bundle + lazy init + accept 200-500ms cold starts.

- **"Lambda in a VPC is just as fast as outside a VPC"** — Lambda in a VPC adds ~100-600ms to cold start due to ENI provisioning. AWS improved this (Hyperplane ENI), but overhead still exists. When possible, use DynamoDB instead of RDS (no VPC requirement).

- **"Lambda scales infinitely"** — there's an account-level concurrent execution limit (default 1000). On burst: 500-3000 new containers/sec. On overflow → throttling (429). The limit can be raised via AWS Support request.

- **"Lambda timeout is 5 minutes"** — the maximum is 15 minutes (900 seconds). The default is 3 seconds. Always set an explicit timeout appropriate for the task.
