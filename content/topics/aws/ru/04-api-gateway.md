<!-- verified: 2026-06-05, corrections: 0 -->
# API Gateway

## Что такое API Gateway и зачем он нужен

Amazon API Gateway — managed HTTP-шлюз: единая точка входа для HTTP-запросов к backend (Lambda, ECS, HTTP-сервисы). Альтернатива: запускать nginx/Express на EC2 — но тогда нужно управлять сервером, scaling, SSL.

```txt
Что даёт API Gateway:
  Routing       → GET /users → Lambda A, POST /orders → Lambda B
  Authentication → JWT Authorizer, Lambda Authorizer, IAM, Cognito
  Rate Limiting → X req/сек, burst limit, usage plans per API key
  Request/Response Transformation → mapping templates (REST API)
  Caching       → TTL-кэш ответов на Edge (только REST API)
  Monitoring    → CloudWatch метрики, X-Ray трacing
  CORS          → настройка CORS headers автоматически
  SSL           → HTTPS termination + custom domain
```

## REST API vs HTTP API vs WebSocket API

```txt
REST API (v1 — "Classic"):
  Выпущен: 2015. Feature-rich.
  Особенности: Request/Response mapping templates, caching, API Keys,
  Usage Plans, Resource Policies, edge-optimized endpoint
  Стоимость: $3.50/million API calls
  Latency: выше (~5-10ms overhead)
  Когда: нужны API Keys + Usage Plans, Response mapping, Caching

HTTP API (v2 — рекомендуется):
  Выпущен: 2019. Упрощённый и более быстрый.
  Особенности: JWT Authorizer out-of-the-box, $connect/$disconnect,
  Lambda proxy integration, OIDC/OAuth 2.0 authorizers
  Стоимость: $1.00/million API calls (~71% дешевле REST API)
  Latency: ~10-15ms ниже чем REST API
  Когда: большинство serverless HTTP API (рекомендуется по умолчанию)
  Ограничения: нет response caching, нет Usage Plans, нет request transformation

WebSocket API:
  Persistent bidirectional connections
  $connect, $disconnect, $default routes
  Когда: real-time чат, live updates, gaming
```

## Lambda Proxy Integration — как работает

```typescript
// Что получает Lambda от API Gateway (HTTP API):
import { APIGatewayProxyEventV2, APIGatewayProxyResultV2 } from 'aws-lambda';

export async function handler(event: APIGatewayProxyEventV2): Promise<APIGatewayProxyResultV2> {
  console.log({
    method: event.requestContext.http.method,  // "GET"
    path: event.rawPath,                        // "/users/123"
    pathParams: event.pathParameters,           // { userId: "123" }
    queryParams: event.queryStringParameters,   // { filter: "active" }
    headers: event.headers,                     // { authorization: "Bearer ..." }
    body: event.body,                           // JSON string или undefined
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

## Authorization — JWT и Lambda Authorizer

### JWT Authorizer (HTTP API) — встроенный

```typescript
// CDK: настройка JWT Authorizer (HTTP API v2)
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
  authorizer: jwtAuthorizer, // JWT проверяется до вызова Lambda
});
```

### Lambda Authorizer — кастомная логика авторизации

```typescript
// Lambda Authorizer: проверяет токен и возвращает IAM Policy
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
          Resource: event.methodArn, // или '*' для всех routes
        }],
      },
      context: { userId: decoded.sub, role: decoded.role }, // передаётся в main Lambda
    };
  } catch {
    throw new Error('Unauthorized'); // API Gateway вернёт 401
  }
}

// В main Lambda доступ к context из authorizer:
// event.requestContext.authorizer.lambda.userId
// event.requestContext.authorizer.lambda.role
```

## Throttling и Rate Limiting

```txt
Default Limits (HTTP API):
  Account-level burst: 5000 req/сек (soft limit, можно повысить)
  Steady state: 10000 req/сек per account
  Per route throttling: настраивается отдельно

При превышении:
  → 429 Too Many Requests
  → Клиент должен реализовать exponential backoff

Usage Plans (только REST API):
  Привязка API Keys к лимитам: 1000 req/день, 100 req/сек burst
  Для монетизации API или партнёров с разными тарифами
```

## Staging и Custom Domain

```typescript
// CDK: кастомный домен для HTTP API
import * as apigwv2 from 'aws-cdk-lib/aws-apigatewayv2';

const domainName = new apigwv2.DomainName(this, 'ApiDomain', {
  domainName: 'api.myapp.com',
  certificate: acmCertificate, // ACM в том же регионе (для HTTP API — не us-east-1!)
});

const httpApi = new apigwv2.HttpApi(this, 'HttpApi', {
  defaultDomainMapping: {
    domainName,
    mappingKey: 'v1', // → api.myapp.com/v1
  },
});
```

```txt
Stage переменные:
  /dev  → Lambda alias: dev
  /prod → Lambda alias: prod
  Позволяет использовать один API ID с разными stage → разные Lambda
```

## Сравнение: API Gateway vs ALB vs CloudFront

```txt
API Gateway HTTP API:
  ✓ JWT Authorizer out-of-the-box
  ✓ Serverless — нет постоянных ресурсов
  ✓ Per-route authorization
  ✓ WebSocket API вариант
  ✗ Payload limit: 10MB
  ✗ Timeout: max 29 секунд (Lambda timeout)
  ✗ Нет sticky sessions
  Когда: Lambda backend, serverless API

ALB (Application Load Balancer):
  ✓ HTTP/2, WebSockets
  ✓ Health checks
  ✓ Path-based routing для ECS/EC2/Lambda
  ✓ Payload >10MB
  ✗ Нет built-in JWT authorizer (нужен Cognito или custom)
  Когда: ECS/EC2 backend, high-throughput, need HTTP/2

CloudFront + Lambda@Edge:
  ✓ Глобальное edge distribution
  ✓ Caching ответов API
  ✓ DDoS protection (AWS Shield)
  ✗ Сложнее настроить
  Когда: глобальные API с частью static + API mix
```

## Типичные ошибки на интервью

- **"API Gateway = только для Lambda"** — API Gateway поддерживает интеграцию с HTTP backends (URL), AWS сервисами напрямую (DynamoDB, S3 через mapping templates в REST API), ALB, и другими. Lambda — наиболее частый, но не единственный вариант.

- **"REST API и HTTP API — одно и то же, просто разные версии"** — принципиально разные продукты. HTTP API быстрее, дешевле, имеет встроенный JWT authorizer. REST API поддерживает кэширование, API Keys, Usage Plans, request/response transformation. Для нового проекта: HTTP API.

- **"Lambda Authorizer вызывается при каждом запросе"** — результат Lambda Authorizer кэшируется (TTL по умолчанию 300 секунд). Это значит: при изменении роли пользователя — до 5 минут старый кэшированный Allow/Deny действует. Настраивается через `authorizerResultTtlInSeconds`.

- **"API Gateway timeout = Lambda timeout"** — API Gateway имеет собственный максимальный timeout: 29 секунд для синхронных интеграций. Если Lambda timeout = 5 мин — API Gateway всё равно ответит ошибкой через 29 сек.

- **"Для WebSocket нужен отдельный сервер"** — API Gateway WebSocket API поддерживает persistent bidirectional connections без постоянного сервера. `$connect`, `$disconnect`, `$default` routes на Lambda. Но Lambda в WebSocket не может инициировать отправку — нужен Management API callback.
