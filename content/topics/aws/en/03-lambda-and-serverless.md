# Lambda and Serverless

## What is AWS Lambda and the Serverless model

Lambda is Function as a Service (FaaS): you upload code, and AWS (Amazon Web Services) handles infrastructure, scaling, and monitoring. "Serverless" doesn't mean no servers — they exist, but the developer doesn't manage them.

The difference is easiest to see as two checklists.

**Traditional EC2 (Elastic Compute Cloud)**

- Provision the virtual machine.
- Configure the operating system and the runtime.
- Deploy the application.
- Configure auto-scaling.
- Patch the operating system.
- Pay 24/7 for uptime.

**Lambda**

- Upload the code.
- Configure a trigger and a memory size.
- AWS handles everything else.

**Lambda pricing**

- $0.20 per 1 million requests.
- $0.0000166667 per gigabyte-second.
- Free Tier: 1 million requests a month plus 400k gigabyte-seconds, forever.

Take 100k requests a month at 128 megabytes (MB) of memory and 200 ms per call. The cost is about $0.00, because it fits inside the Free Tier. An EC2 `t3.micro` costs about $8 a month even at zero load.

## Execution Model — Lambda function lifecycle

Every invocation is either a cold start or a warm start, and the difference is four steps against one.

**Cold start — a new execution environment**

1. Download the deployment package: a zip archive or a container image.
2. Start the runtime sandbox for Node.js, Python or Java.
3. Run the init code outside the handler: imports, database connections.
4. Call `handler(event, context)`.

**Warm start — an existing execution environment**

1. Call `handler(event, context)`. That is the entire list.

After a call the container is "frozen" for roughly 5-15 minutes. The next invocation is a warm start if that container is still alive, and a cold start if it is not.

Concurrency is counted per invocation: each **concurrent** invocation gets a separate execution environment. 100 concurrent requests mean 100 containers, or 100 cold starts if they are the first ones. Lambda scales concurrency automatically up to the account limit, which is 1000 by default.

## Cold Start — causes, measurement, optimization

A cold start is the time Lambda spends building a fresh execution environment before your handler runs. Three things add up to it: runtime initialization time, package size, and the init code.

What that looks like per stack:

- Heavy — Java Spring, or NestJS: 2-5 seconds.
- Medium — Node.js with TypeORM and many imports: 500-1500 ms.
- Light — a Go or Rust binary: 50-100 ms.

**1. Minimize bundle size.** Use esbuild or tsup instead of webpack. Let tree shaking drop what you never import, and never pull in the whole SDK (software development kit) when one client is enough.

```typescript
// BAD: the entire SDK lands in the bundle
import AWS from 'aws-sdk';

// GOOD: only the client you actually call
import { S3Client } from '@aws-sdk/client-s3';
```

**2. Lazy initialization.** A database pool created at module level is rebuilt on every cold start, whether the call needs it or not. Create it on first use instead, and warm starts will reuse it.

```typescript
// BAD: connection created immediately on every cold start
const db = createPool({ ... }); // outside handler → always on cold start

// GOOD: create on first call, reuse on warm starts
let dbPool: Pool | null = null;
export async function handler(event: APIGatewayEvent) {
  if (!dbPool) dbPool = await createPool({ ... });
  // ...
}
```

**3. Provisioned Concurrency.** Lambda pre-warms N execution environments, so N concurrent callers see no cold start at all. You pay for those initialized environments continuously, which makes this worth it for latency-critical APIs with predictable traffic.

**4. Lambda SnapStart, Java only.** It restores a snapshot of an already-initialized execution environment in about 200 ms. Not available for Node.js or Python.

## Typical Lambda Handler in TypeScript

The handler below reads one item from DynamoDB. Two habits in it matter in every Lambda. Clients are created outside the handler, so warm starts reuse them. Every failure path returns a status code instead of throwing.

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

Triggers fall into three groups, and the group decides what happens when the call fails.

**Synchronous — Lambda waits and returns a response**

- API Gateway or a Function URL — an HTTP request and its response.
- ALB (Application Load Balancer) — Lambda acts as a backend.
- CloudFront Functions — processing at the edge.

**Asynchronous — Lambda receives the event, no response is expected**

- S3 (Simple Storage Service): "file uploaded" invokes a Lambda, for example to resize an image.
- SNS (Simple Notification Service): "message received" invokes a Lambda.
- EventBridge: a scheduled cron rule invokes a Lambda.
- On error Lambda retries 2 times with backoff, and then sends the event to a Dead Letter Queue (DLQ).

**Stream-based — Lambda polls the source**

- SQS (Simple Queue Service): Lambda polls a batch of messages, batch size 1-10000.
- Kinesis: Lambda polls records, and on error it bisects the batch.
- DynamoDB Streams: Lambda reacts to table changes.

## Concurrency and Limits

Each number below is a hard boundary, and production hits them earlier than people expect.

- Concurrent executions per account: 1000 by default, and it can be raised.
- Burst limit: 500-3000 per second, depending on the region.
- Timeout: maximum 15 minutes, which is 900 seconds.
- Memory: 128 MB to 10240 MB. The processor share scales with the memory you ask for.
- Deployment package: 50 MB as a zip archive, or 10 gigabytes as a container image.
- `/tmp` storage: 512 MB to 10240 MB, ephemeral and valid within one invocation only.
- Synchronous payload: 6 MB request plus 6 MB response.
- Asynchronous payload: 256 kilobytes.

**Reserved Concurrency** reserves N concurrency for one function. It guarantees that at least N is always available to that function, and it also caps it at N. Anything over the cap is throttled and has to be retried, usually through SQS.

Throttling is what exceeding concurrency looks like: HTTP 429 for synchronous calls, a retry for asynchronous ones.

## Lambda + VPC — access to RDS/ElastiCache

A Lambda placed inside a VPC (Virtual Private Cloud) can reach an RDS (Relational Database Service) instance sitting in a private subnet. The price is a slower cold start, and the snippet marks both that cost and the mitigation.

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

**Important**: Lambda in a VPC has no internet access by default. To reach AWS APIs such as S3 or DynamoDB you need one of two things. A NAT (network address translation) Gateway is expensive; VPC Endpoints are cheaper.

## Lambda vs ECS/EC2

Neither one wins in general. Lambda wins when traffic is irregular and each unit of work is short. ECS (Elastic Container Service) on Fargate wins when the process has to stay alive.

**Lambda**

- ✓ Irregular traffic — no traffic means no cost.
- ✓ Event processing from S3, SQS, SNS.
- ✓ A simple HTTP API with API Gateway.
- ✓ Background jobs and scheduled tasks (cron).
- ✓ File processing, such as thumbnail generation.
- ✗ Persistent WebSocket connections.
- ✗ Tasks longer than 15 minutes.
- ✗ Processor-heavy tasks, such as video encoding.
- ✗ Stateful services.

**ECS / Fargate**

- ✓ Predictable, high-volume traffic.
- ✓ WebSocket servers.
- ✓ Stateful services.
- ✓ Complex NestJS monoliths.
- ✓ Tasks with no time limit.
- ✓ No cold start, because the process is always running.
- ✗ You pay even at zero traffic.

## Common interview mistakes

- **"Lambda is stateless — nothing can be stored between calls"** — the execution environment is reused on warm starts. Variables outside the handler, such as database connections and cached data, persist between calls **on that same container**. But you can't rely on specific state being present on the next call, because it might be a different container.

- **"Cold starts can be eliminated with Provisioned Concurrency"** — you can reduce them to zero for N concurrent, but this costs money for constantly "warmed" environments. For most APIs: optimize the bundle + lazy init + accept 200-500ms cold starts.

- **"Lambda in a VPC is just as fast as outside a VPC"** — it is not. Lambda in a VPC adds roughly 100-600 ms to cold start, because it has to provision an ENI (elastic network interface). AWS improved this with Hyperplane ENI, but the overhead still exists. When possible, use DynamoDB instead of RDS, since it needs no VPC.

- **"Lambda scales infinitely"** — there's an account-level concurrent execution limit (default 1000). On burst: 500-3000 new containers/sec. On overflow → throttling (429). The limit can be raised via AWS Support request.

- **"Lambda timeout is 5 minutes"** — the maximum is 15 minutes (900 seconds). The default is 3 seconds. Always set an explicit timeout appropriate for the task.
