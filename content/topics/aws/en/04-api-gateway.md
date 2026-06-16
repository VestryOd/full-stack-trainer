# API Gateway

## What is API Gateway and why you need it

Amazon API Gateway is a managed HTTP gateway: a single entry point for HTTP requests to a backend (Lambda, ECS, HTTP services). Alternative: running nginx/Express on EC2 — but then you manage the server, scaling, SSL yourself.

```txt
What API Gateway provides:
  Routing       → GET /users → Lambda A, POST /orders → Lambda B
  Authentication → JWT Authorizer, Lambda Authorizer, IAM, Cognito
  Rate Limiting → X req/sec, burst limit, usage plans per API key
  Request/Response Transformation → mapping templates (REST API)
  Caching       → TTL-cache of responses at Edge (REST API only)
  Monitoring    → CloudWatch metrics, X-Ray tracing
  CORS          → automatic CORS headers configuration
  SSL           → HTTPS termination + custom domain
```

## REST API vs HTTP API vs WebSocket API

```txt
REST API (v1 — "Classic"):
  Released: 2015. Feature-rich.
  Features: Request/Response mapping templates, caching, API Keys,
  Usage Plans, Resource Policies, edge-optimized endpoint
  Cost: $3.50/million API calls
  Latency: higher (~5-10ms overhead)
  Use when: need API Keys + Usage Plans, Response mapping, Caching

HTTP API (v2 — recommended):
  Released: 2019. Simplified and faster.
  Features: JWT Authorizer out-of-the-box, $connect/$disconnect,
  Lambda proxy integration, OIDC/OAuth 2.0 authorizers
  Cost: $1.00/million API calls (~71% cheaper than REST API)
  Latency: ~10-15ms lower than REST API
  Use when: most serverless HTTP APIs (recommended by default)
  Limitations: no response caching, no Usage Plans, no request transformation

WebSocket API:
  Persistent bidirectional connections
  $connect, $disconnect, $default routes
  Use when: real-time chat, live updates, gaming
```

## Lambda Proxy Integration — how it works

```typescript
// What Lambda receives from API Gateway (HTTP API):
import { APIGatewayProxyEventV2, APIGatewayProxyResultV2 } from 'aws-lambda';

export async function handler(event: APIGatewayProxyEventV2): Promise<APIGatewayProxyResultV2> {
  console.log({
    method: event.requestContext.http.method,  // "GET"
    path: event.rawPath,                        // "/users/123"
    pathParams: event.pathParameters,           // { userId: "123" }
    queryParams: event.queryStringParameters,   // { filter: "active" }
    headers: event.headers,                     // { authorization: "Bearer ..." }
    body: event.body,                           // JSON string or undefined
    isBase64: event.isBase64Encoded,
  });

  const userId = event.pathParameters?.userId;

  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': 'https://myapp.com',
    },
    body: JSON.stringify({ userId, status: 'active' }),
  };
}
```

## Authorization — JWT and Lambda Authorizer

### JWT Authorizer (HTTP API) — built-in

```typescript
// CDK: JWT Authorizer setup (HTTP API v2)
import * as apigwv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as authorizers from 'aws-cdk-lib/aws-apigatewayv2-authorizers';
import * as integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';

const httpApi = new apigwv2.HttpApi(this, 'HttpApi', {
  corsPreflight: {
    allowOrigins: ['https://myapp.com'],
    allowMethods: [apigwv2.CorsHttpMethod.GET, apigwv2.CorsHttpMethod.POST],
    allowHeaders: ['Content-Type', 'Authorization'],
  },
});

const jwtAuthorizer = new authorizers.HttpJwtAuthorizer('JwtAuth', 'https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_XXXXX', {
  jwtAudience: ['my-app-client-id'],
  identitySource: '$request.header.Authorization',
});

httpApi.addRoutes({
  path: '/users/{userId}',
  methods: [apigwv2.HttpMethod.GET],
  integration: new integrations.HttpLambdaIntegration('GetUser', getUserFn),
  authorizer: jwtAuthorizer, // JWT is verified before Lambda is invoked
});
```

### Lambda Authorizer — custom authorization logic

```typescript
// Lambda Authorizer: validates the token and returns an IAM Policy
import { APIGatewayRequestAuthorizerEvent, APIGatewayAuthorizerResult } from 'aws-lambda';
import jwt from 'jsonwebtoken';

export async function handler(event: APIGatewayRequestAuthorizerEvent): Promise<APIGatewayAuthorizerResult> {
  const token = event.headers?.authorization?.replace('Bearer ', '');

  try {
    const decoded = jwt.verify(token!, process.env.JWT_SECRET!) as { sub: string; role: string };

    return {
      principalId: decoded.sub,
      policyDocument: {
        Version: '2012-10-17',
        Statement: [{
          Action: 'execute-api:Invoke',
          Effect: 'Allow',
          Resource: event.methodArn, // or '*' for all routes
        }],
      },
      context: { userId: decoded.sub, role: decoded.role }, // passed to the main Lambda
    };
  } catch {
    throw new Error('Unauthorized'); // API Gateway returns 401
  }
}

// In main Lambda, access context from authorizer:
// event.requestContext.authorizer.lambda.userId
// event.requestContext.authorizer.lambda.role
```

## Throttling and Rate Limiting

```txt
Default Limits (HTTP API):
  Account-level burst: 5000 req/sec (soft limit, can be raised)
  Steady state: 10000 req/sec per account
  Per route throttling: configurable individually

On exceeding limits:
  → 429 Too Many Requests
  → Client must implement exponential backoff

Usage Plans (REST API only):
  Bind API Keys to limits: 1000 req/day, 100 req/sec burst
  For API monetization or partners with different tiers
```

## Staging and Custom Domain

```typescript
// CDK: custom domain for HTTP API
import * as apigwv2 from 'aws-cdk-lib/aws-apigatewayv2';

const domainName = new apigwv2.DomainName(this, 'ApiDomain', {
  domainName: 'api.myapp.com',
  certificate: acmCertificate, // ACM in the same region (for HTTP API — not us-east-1!)
});

const httpApi = new apigwv2.HttpApi(this, 'HttpApi', {
  defaultDomainMapping: {
    domainName,
    mappingKey: 'v1', // → api.myapp.com/v1
  },
});
```

```txt
Stage variables:
  /dev  → Lambda alias: dev
  /prod → Lambda alias: prod
  Allows using one API ID with different stages → different Lambdas
```

## Comparison: API Gateway vs ALB vs CloudFront

```txt
API Gateway HTTP API:
  ✓ JWT Authorizer out-of-the-box
  ✓ Serverless — no persistent resources
  ✓ Per-route authorization
  ✓ WebSocket API option
  ✗ Payload limit: 10MB
  ✗ Timeout: max 29 seconds (Lambda timeout)
  ✗ No sticky sessions
  Use when: Lambda backend, serverless API

ALB (Application Load Balancer):
  ✓ HTTP/2, WebSockets
  ✓ Health checks
  ✓ Path-based routing for ECS/EC2/Lambda
  ✓ Payload >10MB
  ✗ No built-in JWT authorizer (Cognito or custom required)
  Use when: ECS/EC2 backend, high-throughput, need HTTP/2

CloudFront + Lambda@Edge:
  ✓ Global edge distribution
  ✓ Caching of API responses
  ✓ DDoS protection (AWS Shield)
  ✗ More complex to configure
  Use when: global APIs with static + API mix
```

## Common interview mistakes

- **"API Gateway is only for Lambda"** — API Gateway supports integration with HTTP backends (URL), AWS services directly (DynamoDB, S3 via mapping templates in REST API), ALB, and others. Lambda is the most common, but not the only option.

- **"REST API and HTTP API are the same thing, just different versions"** — they are fundamentally different products. HTTP API is faster, cheaper, has a built-in JWT authorizer. REST API supports caching, API Keys, Usage Plans, request/response transformation. For new projects: HTTP API.

- **"Lambda Authorizer is called on every request"** — the Lambda Authorizer result is cached (default TTL: 300 seconds). This means: if a user's role changes — the old cached Allow/Deny remains active for up to 5 minutes. Configurable via `authorizerResultTtlInSeconds`.

- **"API Gateway timeout = Lambda timeout"** — API Gateway has its own maximum timeout: 29 seconds for synchronous integrations. If Lambda timeout = 5 min — API Gateway will still return an error after 29 seconds.

- **"WebSocket requires a dedicated server"** — API Gateway WebSocket API supports persistent bidirectional connections without a dedicated server. `$connect`, `$disconnect`, `$default` routes on Lambda. But Lambda in WebSocket cannot initiate sends — a Management API callback is required.
