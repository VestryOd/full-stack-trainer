<!-- verified: 2026-06-05, corrections: 0 -->
# API Gateway

## Что такое API Gateway и зачем он нужен

Amazon API Gateway — это управляемый HTTP-шлюз от AWS (Amazon Web Services). Единая точка входа для HTTP-запросов к бэкенду: Lambda, ECS (Elastic Container Service) или обычный HTTP-сервис. Альтернатива — поднять nginx или Express на EC2 (Elastic Compute Cloud). Тогда сервер, масштабирование и сертификат SSL (Secure Sockets Layer) придётся вести самим.

Что API Gateway даёт из коробки:

- **Маршрутизация** — `GET /users` уходит в Lambda A, `POST /orders` в Lambda B.
- **Аутентификация** — JWT (JSON Web Token) Authorizer, Lambda Authorizer, IAM (Identity and Access Management), Cognito.
- **Ограничение частоты** — потолок запросов в секунду, лимит на всплеск и планы использования по ключу API.
- **Преобразование запроса и ответа** — mapping templates, только в REST (representational state transfer) API.
- **Кэширование** — кэш ответов с TTL (time to live) на границе сети, только в REST API.
- **Мониторинг** — метрики CloudWatch и трассировка X-Ray.
- **CORS** — заголовки cross-origin resource sharing настраиваются автоматически.
- **SSL** — терминация HTTPS (зашифрованный HTTP) и свой домен.

## REST API vs HTTP API vs WebSocket API

Под именем API Gateway живут три разных продукта. HTTP API — выбор по умолчанию сегодня. REST API остался ради возможностей, которых в HTTP API нет. WebSocket API — вообще другой протокол.

**REST API (v1, «Classic»)**

- Выпущен в 2015 году, богат возможностями.
- Особенности: mapping templates для запроса и ответа, кэширование, API Keys, Usage Plans, Resource Policies, edge-optimized endpoint.
- Стоимость: $3.50 за миллион вызовов API.
- Задержка: выше, около 5-10 мс накладных расходов.
- Когда: нужны API Keys вместе с Usage Plans, преобразование ответа или кэширование.

**HTTP API (v2, рекомендуемый)**

- Выпущен в 2019 году, упрощённый и более быстрый.
- Особенности: JWT Authorizer из коробки, `$connect` и `$disconnect`, интеграция Lambda proxy, авторизаторы OIDC (OpenID Connect) и OAuth 2.0.
- Стоимость: $1.00 за миллион вызовов API, примерно на 71% дешевле REST API.
- Задержка: примерно на 10-15 мс ниже, чем у REST API.
- Когда: большинство serverless HTTP API. Это рекомендация по умолчанию.
- Ограничения: нет кэширования ответов, нет Usage Plans, нет преобразования запроса.

**WebSocket API**

- Постоянные двусторонние соединения.
- Маршруты `$connect`, `$disconnect`, `$default`.
- Когда: чат в реальном времени, живые обновления, игры.

## Lambda Proxy Integration — как работает

При proxy-интеграции API Gateway ничего не преобразует. Он отдаёт Lambda весь запрос одним объектом события и возвращает наружу то, что Lambda вернула. Сниппет показывает, какие поля этого события вы реально читаете.

```typescript
// Что получает Lambda от API Gateway (HTTP API):
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

Встроенный авторизатор проверяет подпись и срок жизни токена до вызова Lambda, поэтому отклонённый запрос не стоит вам ни одного вызова. Вы задаёте издателя токена и ожидаемую аудиторию, кода авторизации писать не нужно.

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

const issuer = 'https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_XXXXX';

const jwtAuthorizer = new authorizers.HttpJwtAuthorizer('JwtAuth', issuer, {
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

Когда встроенной проверки мало, Lambda Authorizer выполняет ваш код и возвращает политику IAM, которая разрешает или запрещает вызов. Заодно он может передать данные в основную Lambda через объект контекста.

```typescript
// Lambda Authorizer: проверяет токен и возвращает IAM Policy
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

API Gateway ограничивает частоту на двух уровнях: аккаунт и отдельный маршрут. Упереться можно в любой, и в обоих случаях клиент получает 429, так что стратегия повторов нужна всегда.

**Лимиты по умолчанию (HTTP API)**

- Всплеск на уровне аккаунта: 5000 запросов в секунду. Лимит мягкий, его можно поднять.
- Установившийся режим: 10000 запросов в секунду на аккаунт.
- Ограничение на маршрут: настраивается отдельно.

При превышении лимита вызывающий получает `429 Too Many Requests`, и клиент обязан реализовать экспоненциальную задержку между повторами.

**Usage Plans (только REST API)** привязывают API Keys к лимитам: 1000 запросов в день, 100 запросов в секунду на всплеске. Они существуют ради монетизации API или ради партнёров с разными тарифами.

## Staging и Custom Domain

Свой домен отвязывает публичный адрес от сгенерированного имени хоста API Gateway. Стейдж позволяет одному API отдавать `/dev` и `/prod` из одного развёртывания.

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

**Переменные стейджа** направляют стейдж на разные алиасы Lambda:

- `/dev` идёт на алиас Lambda `dev`.
- `/prod` идёт на алиас Lambda `prod`.

Поэтому один и тот же API id может обслуживать несколько стейджей, и каждый вызовет свою Lambda.

## Сравнение: API Gateway vs ALB vs CloudFront

Все трое могут стоять перед бэкендом, и выбор определяет сам бэкенд. API Gateway — для Lambda. ALB (Application Load Balancer) — для долгоживущих контейнеров и инстансов. CloudFront — для контента, который надо кэшировать поближе к пользователю.

**API Gateway HTTP API**

- ✓ JWT Authorizer из коробки.
- ✓ Serverless — нет постоянных ресурсов, за которые вы платите.
- ✓ Авторизация на уровне маршрута.
- ✓ Есть вариант WebSocket API.
- ✗ Предел полезной нагрузки: 10 мегабайт (MB).
- ✗ Таймаут: максимум 29 секунд, и это же обрезает реальный таймаут Lambda.
- ✗ Нет sticky sessions.
- Когда: бэкенд на Lambda, serverless API.

**ALB**

- ✓ HTTP/2 и WebSocket.
- ✓ Проверки здоровья.
- ✓ Маршрутизация по пути на ECS, EC2 или Lambda.
- ✓ Полезная нагрузка больше 10 MB.
- ✗ Нет встроенного JWT authorizer: добавляете Cognito или свой.
- Когда: бэкенд на ECS или EC2, высокая пропускная способность, нужен HTTP/2.

**CloudFront + Lambda@Edge**

- ✓ Глобальная раздача с границы сети.
- ✓ Кэширование ответов API.
- ✓ Защита от DDoS, распределённого отказа в обслуживании, через AWS Shield.
- ✗ Сложнее настроить.
- Когда: глобальные API, где статика смешана с вызовами API.

## Типичные ошибки на интервью

- **«API Gateway = только для Lambda»** — он умеет интегрироваться и с обычными HTTP-бэкендами по URL, и с ALB, и напрямую с сервисами AWS. До DynamoDB и S3 (Simple Storage Service) можно дотянуться через mapping templates в REST API. Lambda — самая частая цель, но не единственная.

- **«REST API и HTTP API — одно и то же, просто разные версии»** — это принципиально разные продукты. HTTP API быстрее, дешевле и имеет встроенный JWT authorizer. REST API поддерживает кэширование, API Keys, Usage Plans, преобразование запроса и ответа. Для нового проекта берите HTTP API.

- **«Lambda Authorizer вызывается при каждом запросе»** — результат кэшируется, TTL по умолчанию 300 секунд. Если роль пользователя изменилась, старый закэшированный Allow или Deny действует ещё до 5 минут. Окно настраивается через `authorizerResultTtlInSeconds`.

- **«Таймаут API Gateway равен таймауту Lambda»** — у API Gateway свой максимум: 29 секунд для синхронных интеграций. Поставьте Lambda таймаут в 5 минут, и API Gateway всё равно ответит ошибкой через 29 секунд.

- **«Для WebSocket нужен отдельный сервер»** — API Gateway WebSocket API держит постоянные двусторонние соединения и без него. Маршруты `$connect`, `$disconnect` и `$default` работают на Lambda. Но Lambda за WebSocket не может начать отправку сама: ей нужно позвонить обратно через Management API.
