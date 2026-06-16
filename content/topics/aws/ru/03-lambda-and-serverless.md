<!-- verified: 2026-06-05, corrections: 0 -->
# Lambda и Serverless

## Что такое AWS Lambda и модель Serverless

Lambda — функция как сервис (FaaS): загружаешь код, AWS обеспечивает инфраструктуру, масштабирование, мониторинг. "Serverless" не означает отсутствие серверов — они существуют, но разработчик ими не управляет.

```txt
Традиционный EC2:                 Lambda:
  Provision VM                      Загрузить код
  Настроить OS + runtime            Настроить trigger + memory
  Деплоить приложение               Всё остальное — AWS
  Настраивать auto-scaling
  Патчить OS
  Платить 24/7 за uptime

Модель оплаты Lambda:
  $0.20 за 1 млн вызовов
  $0.0000166667 за GB-секунду
  Free Tier: 1M req/мес + 400k GB-сек навсегда

При 100k req/мес, 128MB, 200ms:
  Стоимость ≈ $0.00 (в рамках Free Tier)
EC2 t3.micro: ~$8/мес без нагрузки
```

## Execution Model — Lifecycle Lambda функции

```txt
Invocation → Cold или Warm Start:

Cold Start (новый execution environment):
  1. Скачать deployment package (ZIP/container image)
  2. Запустить runtime (Node.js/Python/Java sandbox)
  3. Выполнить init code (вне handler): импорты, DB connections
  4. Вызвать handler(event, context)

Warm Start (существующий execution environment):
  1. Вызвать handler(event, context)  ← только это

После вызова контейнер "заморожен" ~5-15 мин.
Следующий вызов: warm start если контейнер жив, cold start если нет.

Параллелизм: каждый КОНКУРЕНТНЫЙ вызов = отдельный execution environment.
  100 concurrent requests = 100 контейнеров (или cold starts если первые).
  Lambda автоматически масштабирует конкурентность до account limit (по умолчанию 1000).
```

## Cold Start — причины, измерение, оптимизация

```txt
Факторы влияющие на cold start latency:
  Тяжёлый: Java Spring + NestJS → 2-5 секунд
  Средний: Node.js с TypeORM + множеством импортов → 500-1500ms
  Лёгкий:  Go/Rust binary → 50-100ms
  Причина: время инициализации runtime + размер пакета + init code

Стратегии оптимизации:

1. Минимизация bundle size:
   esbuild или tsup вместо webpack → минимальный bundle
   Tree shaking: не импортировать весь aws-sdk, только нужное
   // ПЛОХО:
   import AWS from 'aws-sdk';
   // ХОРОШО:
   import { S3Client } from '@aws-sdk/client-s3';

2. Lazy initialization (defer DB connection):
   // ПЛОХО: DB connection создаётся при каждом cold start немедленно
   const db = createPool({ ... }); // вне handler → всегда при cold start

   // ХОРОШО: создать при первом вызове, переиспользовать при warm
   let dbPool: Pool | null = null;
   export async function handler(event: APIGatewayEvent) {
     if (!dbPool) dbPool = await createPool({ ... });
     // ...
   }

3. Provisioned Concurrency:
   Pre-warms N execution environments → нет cold starts для N concurrent.
   Стоимость: платишь за initialized envs постоянно.
   Подходит: latency-critical API с предсказуемым трафиком.

4. Lambda SnapStart (Java):
   Снапшот инициализированного execution environment → восстановление ~200ms.
   Не доступно для Node.js/Python.
```

## Типичный Lambda Handler с TypeScript

```typescript
import { APIGatewayProxyEvent, APIGatewayProxyResult, Context } from 'aws-lambda';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand } from '@aws-sdk/lib-dynamodb';

// Инициализация вне handler → переиспользуется при warm start
const ddbClient = new DynamoDBClient({ region: process.env.AWS_REGION });
const docClient = DynamoDBDocumentClient.from(ddbClient);

export async function handler(
  event: APIGatewayProxyEvent,
  context: Context
): Promise<APIGatewayProxyResult> {
  // context.getRemainingTimeInMillis() → осталось мс до timeout

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
    console.error('DynamoDB error:', err); // → CloudWatch Logs автоматически
    return { statusCode: 500, body: JSON.stringify({ error: 'Internal error' }) };
  }
}
```

## Triggers — чем запускается Lambda

```txt
Synchronous (Lambda ждёт и возвращает ответ):
  API Gateway / Function URL → HTTP request/response
  ALB → Lambda как backend
  CloudFront Functions → edge processing

Asynchronous (Lambda получает событие, результат не ждут):
  S3 → "файл загружен" → Lambda (image resize)
  SNS → "пришло сообщение" → Lambda
  EventBridge → "scheduled cron" → Lambda
  Lambda retries при ошибке: 2 раза (с задержкой), потом Dead Letter Queue

Stream-based (Lambda polling источника):
  SQS → Lambda poll batch of messages (batch size 1-10000)
  Kinesis → Lambda poll records (при ошибке — bisect batch)
  DynamoDB Streams → Lambda реагирует на изменения в таблице
```

## Concurrency и Limits

```txt
Default Account Concurrent Executions: 1000 (по умолчанию, можно увеличить)
Burst limit: 500-3000/сек (зависит от региона)
Timeout: максимум 15 минут (900 сек)
Memory: 128MB – 10240MB (CPU масштабируется с памятью)
Deployment package: 50MB ZIP / 10GB container image
/tmp storage: 512MB – 10240MB (ephemeral, только в рамках invocation)
Payload (синхронный): 6MB request + 6MB response
Payload (асинхронный): 256KB

Reserved Concurrency: зарезервировать N concurrency для функции.
  Гарантирует: минимум N всегда доступны.
  Лимит: не более N (throttle при превышении → SQS/retry).

Throttling: при превышении concurrency → HTTP 429 (sync) или retry (async).
```

## Lambda + VPC — доступ к RDS/ElastiCache

```typescript
// Lambda в VPC для доступа к RDS в private subnet
const lambdaFn = new lambda.Function(this, 'ApiHandler', {
  runtime: lambda.Runtime.NODEJS_20_X,
  handler: 'index.handler',
  code: lambda.Code.fromAsset('dist'),
  vpc,
  vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
  securityGroups: [lambdaSecurityGroup],
  // Важно: Lambda в VPC → cold start +100-600ms (ENI provisioning)
  // Mitigation: использовать RDS Proxy (connection pooling)
});

// RDS Proxy: решает проблему "1000 Lambda * DB connection = pool exhaustion"
// Lambda → RDS Proxy (pooling) → RDS (реальных connections гораздо меньше)
```

**Важно**: Lambda в VPC не имеет internet доступа по умолчанию. Для доступа к AWS API (S3, DynamoDB): нужен NAT Gateway (дорого) или VPC Endpoints (дешевле).

## Когда Lambda, когда ECS/EC2

```txt
Lambda:
  ✓ Sporadic traffic (нет трафика → нет стоимости)
  ✓ Event processing (S3, SQS, SNS)
  ✓ Simple HTTP API с API Gateway
  ✓ Background jobs, scheduled tasks (cron)
  ✓ File processing (thumbnail generation)
  ✗ WebSocket постоянные соединения
  ✗ Долгие задачи >15 мин
  ✗ CPU-intensive (video encoding)
  ✗ Stateful сервисы

ECS/Fargate:
  ✓ Predictable, high-volume трафик
  ✓ WebSocket сервера
  ✓ Stateful сервисы
  ✓ Сложные NestJS монолиты
  ✓ Задачи без time limit
  ✗ Cold start нет (всегда running)
  ✗ Стоишь при zero трафике
```

## Типичные ошибки на интервью

- **"Lambda stateless — нельзя ничего хранить между вызовами"** — execution environment переиспользуется при warm start. Переменные вне handler (DB connections, cached data) сохраняются между вызовами ОДНОГО контейнера. Но нельзя рассчитывать что конкретный state будет на следующем вызове (может быть другой контейнер).

- **"Cold start можно устранить Provisioned Concurrency"** — можно уменьшить до нуля для N concurrent, но это стоит денег за постоянно "прогретые" среды. Для большинства API: оптимизировать bundle + lazy init + принять 200-500ms cold start.

- **"Lambda в VPC такая же быстрая как без VPC"** — Lambda в VPC добавляет ~100-600ms к cold start из-за ENI provisioning. AWS улучшил это (Hyperplane ENI), но overhead всё равно есть. Если возможно — использовать DynamoDB вместо RDS (нет VPC требования).

- **"Lambda масштабируется бесконечно"** — есть Account-level concurrent execution limit (по умолчанию 1000). При burst: 500-3000 новых containers/сек. При превышении → throttling (429). Limit можно повысить через request к AWS Support.

- **"Timeout Lambda — 5 минут"** — максимум 15 минут (900 секунд). По умолчанию 3 секунды. Нужно явно устанавливать timeout под задачу.
