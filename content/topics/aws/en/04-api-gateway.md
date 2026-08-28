# API Gateway

## What is API Gateway and why you need it

Amazon API Gateway is the managed HTTP gateway of AWS (Amazon Web Services). It is a single entry point for HTTP requests to a backend: Lambda, ECS (Elastic Container Service), or a plain HTTP service. The alternative is running nginx or Express on EC2 (Elastic Compute Cloud). Then the server, the scaling and the SSL (Secure Sockets Layer) certificate are yours to manage.

What API Gateway provides out of the box:

- **Routing** — `GET /users` to Lambda A, `POST /orders` to Lambda B.
- **Authentication** — JWT (JSON Web Token) Authorizer, Lambda Authorizer, IAM (Identity and Access Management), Cognito.
- **Rate limiting** — a request-per-second ceiling, a burst limit, and usage plans per API key.
- **Request and response transformation** — mapping templates, in the REST (representational state transfer) API only.
- **Caching** — a TTL (time to live) cache of responses at the edge, in the REST API only.
- **Monitoring** — CloudWatch metrics and X-Ray tracing.
- **CORS** — cross-origin resource sharing headers configured automatically.
- **SSL** — HTTPS (encrypted HTTP) termination and a custom domain.

## REST API vs HTTP API vs WebSocket API

Three different products share the name API Gateway. HTTP API is the default choice today. REST API survives for the features HTTP API dropped. WebSocket API is a different protocol altogether.

**REST API (v1, "Classic")**

- Released in 2015, feature-rich.
- Features: request and response mapping templates, caching, API Keys, Usage Plans, Resource Policies, an edge-optimized endpoint.
- Cost: $3.50 per million API calls.
- Latency: higher, roughly 5-10 ms of overhead.
- Use when you need API Keys with Usage Plans, response mapping, or caching.

**HTTP API (v2, recommended)**

- Released in 2019, simplified and faster.
- Features: a JWT Authorizer out of the box, `$connect` and `$disconnect`, Lambda proxy integration, OIDC (OpenID Connect) and OAuth 2.0 authorizers.
- Cost: $1.00 per million API calls, about 71% cheaper than REST API.
- Latency: roughly 10-15 ms lower than REST API.
- Use for most serverless HTTP APIs. This is the default recommendation.
- Limitations: no response caching, no Usage Plans, no request transformation.

**WebSocket API**

- Persistent bidirectional connections.
- Routes `$connect`, `$disconnect`, `$default`.
- Use for real-time chat, live updates, gaming.

## Lambda Proxy Integration — how it works

With proxy integration API Gateway transforms nothing. It hands the whole request to Lambda as one event object and returns whatever Lambda gives back. The snippet shows which fields of that event you actually read.

```typescript
// What Lambda receives from API Gateway (HTTP API):
import { APIGatewayProxyEventV2, APIGatewayProxyResultV2 } from 'aws-lambda';

export async function handler(
  event: APIGatewayProxyEventV2
): Promise<APIGatewayProxyResultV2> {
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

The built-in authorizer checks the token signature and expiry before Lambda is invoked, so a rejected request never costs you an invocation. You give it the token issuer and the expected audience, and there is no authorization code to write.

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

const issuer = 'https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_XXXXX';

const jwtAuthorizer = new authorizers.HttpJwtAuthorizer('JwtAuth', issuer, {
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

When the built-in check is not enough, a Lambda Authorizer runs your own code and returns an IAM policy that allows or denies the call. It can also pass data down to the main Lambda through a context object.

```typescript
// Lambda Authorizer: validates the token and returns an IAM Policy
import { APIGatewayRequestAuthorizerEvent, APIGatewayAuthorizerResult } from 'aws-lambda';
import jwt from 'jsonwebtoken';

export async function handler(
  event: APIGatewayRequestAuthorizerEvent
): Promise<APIGatewayAuthorizerResult> {
  const token = event.headers?.authorization?.replace('Bearer ', '');

  try {
    type Claims = { sub: string; role: string };
    const decoded = jwt.verify(token!, process.env.JWT_SECRET!) as Claims;

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

API Gateway throttles on two levels, the account and the individual route. Hitting either one returns a 429 to the caller, so the client needs a retry strategy in both cases.

**Default limits (HTTP API)**

- Account-level burst: 5000 requests per second. This is a soft limit and can be raised.
- Steady state: 10000 requests per second per account.
- Per-route throttling: configurable individually.

On exceeding a limit the caller gets `429 Too Many Requests`, and the client has to implement exponential backoff.

**Usage Plans (REST API only)** bind API Keys to limits: 1000 requests a day, 100 requests per second of burst. They exist for API monetization, or for partners on different tiers.

## Staging and Custom Domain

A custom domain detaches your public address from the generated API Gateway hostname. A stage lets one API serve `/dev` and `/prod` from the same deployment.

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

**Stage variables** point a stage at a different Lambda alias:

- `/dev` goes to the Lambda alias `dev`.
- `/prod` goes to the Lambda alias `prod`.

One API id can therefore serve several stages, and each stage can call a different Lambda.

## Comparison: API Gateway vs ALB vs CloudFront

All three can sit in front of your backend, and the backend decides which one you pick. API Gateway is for Lambda. An ALB (Application Load Balancer) is for long-lived containers and instances. CloudFront is for content that should be cached near the user.

**API Gateway HTTP API**

- ✓ JWT Authorizer out of the box.
- ✓ Serverless — no persistent resources to pay for.
- ✓ Per-route authorization.
- ✓ WebSocket API option.
- ✗ Payload limit: 10 megabytes (MB).
- ✗ Timeout: 29 seconds maximum, which caps the effective Lambda timeout too.
- ✗ No sticky sessions.
- Use when the backend is Lambda and the API is serverless.

**ALB**

- ✓ HTTP/2 and WebSockets.
- ✓ Health checks.
- ✓ Path-based routing to ECS, EC2 or Lambda.
- ✓ Payload over 10 MB.
- ✗ No built-in JWT authorizer; you add Cognito or your own.
- Use when the backend is ECS or EC2, throughput is high, or you need HTTP/2.

**CloudFront + Lambda@Edge**

- ✓ Global edge distribution.
- ✓ Caching of API responses.
- ✓ DDoS protection, distributed denial of service, through AWS Shield.
- ✗ More complex to configure.
- Use for global APIs that mix static content with API calls.

## Common interview mistakes

- **"API Gateway is only for Lambda"** — it also integrates with plain HTTP backends by URL, with an ALB, and with AWS services directly. DynamoDB and S3 (Simple Storage Service) are reachable through mapping templates in the REST API. Lambda is the most common target, not the only one.

- **"REST API and HTTP API are the same thing, just different versions"** — they are fundamentally different products. HTTP API is faster, cheaper, and has a built-in JWT authorizer. REST API supports caching, API Keys, Usage Plans, and request and response transformation. For new projects, pick HTTP API.

- **"Lambda Authorizer is called on every request"** — the result is cached, with a default TTL of 300 seconds. If a user's role changes, the old cached Allow or Deny stays active for up to 5 minutes. The window is configurable through `authorizerResultTtlInSeconds`.

- **"API Gateway timeout = Lambda timeout"** — API Gateway has its own maximum of 29 seconds for synchronous integrations. Set the Lambda timeout to 5 minutes and API Gateway will still return an error after 29 seconds.

- **"WebSocket requires a dedicated server"** — API Gateway WebSocket API holds persistent bidirectional connections without one. The `$connect`, `$disconnect` and `$default` routes run on Lambda. But a Lambda behind WebSocket cannot start a send on its own: it has to call back through the Management API.
