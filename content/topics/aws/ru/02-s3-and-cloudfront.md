<!-- verified: 2026-06-05, corrections: 0 -->
# S3 и CloudFront

## S3 — объектное хранилище, не файловая система

S3 (Simple Storage Service) — объектное хранилище: неограниченное масштабирование, 11 девяток durability (99.999999999%), данные реплицируются минимум в 3 AZ одного региона автоматически.

```txt
Ключевые отличия от файловой системы:
  - Нет иерархии папок: "папки" — это только префикс ключа объекта
  - Нет частичного обновления файла: только замена объекта целиком
  - Операции: PUT/GET/DELETE (нет append, seek, lock)
  - Доступ через HTTP API (или SDK), не через filesystem mount
    (EFS — если нужна файловая система для EC2)

Объект = ключ + данные + метаданные:
  Key:      "avatars/user-123/profile.jpg"  (путь — просто строка)
  Value:    байты файла (до 5TB на объект)
  Metadata: Content-Type, Cache-Control, кастомные x-amz-meta-*
```

## Storage Classes — выбор по паттерну доступа

```txt
Standard:
  Частый доступ (>1 раза/месяц). Latency мс.
  $0.023/GB/мес. Для активных данных приложения.

Intelligent-Tiering:
  Автоматически перемещает между Hot/Cold уровнями.
  Плюс $0.0025/1000 objects за мониторинг.
  Для данных с непредсказуемым паттерном доступа.

Standard-IA (Infrequent Access):
  Редкий доступ (<1 раза/мес), но нужна быстрая выдача.
  Дешевле хранение, дороже retrieval. Минимум 30 дней хранения.
  Для бэкапов, DR копий.

Glacier Instant Retrieval:
  Архив, доступ мс. Минимум 90 дней. Для quarterly backups.

Glacier Flexible Retrieval:
  Архив, доступ 1-12ч (expedited: $0.03/GB, standard: бесплатно).
  Минимум 90 дней.

Glacier Deep Archive:
  Архив 7-10+ лет, доступ 12-48ч. Самый дешёвый ($0.00099/GB/мес).
  Compliance данные, медицинские записи.

S3 Lifecycle Policy: автоматически переводить объекты между классами:
  30 дней → Standard-IA → 90 дней → Glacier → 365 дней → Deep Archive
```

## Безопасность S3 — три уровня управления доступом

```typescript
// 1. Block Public Access (обязательно для приватных bucket)
// В CDK:
const bucket = new s3.Bucket(this, 'AppBucket', {
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, // запретить любой публичный доступ
  encryption: s3.BucketEncryption.S3_MANAGED,        // SSE-S3 шифрование
  versioned: true,                                    // версионирование объектов
});

// 2. Bucket Policy — resource-based policy (JSON)
// Разрешить CloudFront читать из bucket:
const bucketPolicy = new s3.BucketPolicy(this, 'BucketPolicy', { bucket });
bucketPolicy.document.addStatements(
  new iam.PolicyStatement({
    actions: ['s3:GetObject'],
    resources: [bucket.arnForObjects('*')],
    principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
    conditions: {
      StringEquals: { 'AWS:SourceArn': distribution.distributionArn },
    },
  })
);

// 3. IAM Policy — identity-based (для пользователей/ролей)
// Lambda получает только нужные права:
bucket.grantRead(lambdaFunction);           // только GetObject, ListBucket
bucket.grantPut(lambdaFunction);            // только PutObject
bucket.grantReadWrite(lambdaFunction);      // GetObject + PutObject
// bucket.grantPublicAccess() — никогда для приватных данных!
```

## Pre-Signed URL — загрузка файлов напрямую в S3

Классический senior вопрос: как реализовать загрузку файлов без прокси через сервер?

```txt
Проблема без Pre-Signed URL:
  Client → Backend (10GB video) → S3
  Недостатки: трафик через ваш сервер (дорого, медленно), нагрузка на backend

Решение с Pre-Signed URL:
  1. Client → Backend: "хочу загрузить файл avatar.jpg"
  2. Backend → AWS SDK: сгенерировать pre-signed PUT URL
  3. Backend → Client: { url: "https://s3.amazonaws.com/...", fields: {...} }
  4. Client → S3: PUT напрямую (Backend не участвует!)
  5. S3 → Client: 200 OK
  6. Client → Backend: "загрузка завершена, ключ: avatars/user-123/avatar.jpg"
  7. Backend → DB: сохранить ключ в профиле пользователя
```

```typescript
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const s3 = new S3Client({ region: 'eu-west-1' });

// Генерация Pre-Signed URL для загрузки (PUT)
async function generateUploadUrl(userId: string, filename: string): Promise<string> {
  const key = `avatars/${userId}/${Date.now()}-${filename}`;

  const command = new PutObjectCommand({
    Bucket: process.env.BUCKET_NAME!,
    Key: key,
    ContentType: 'image/jpeg',
    // Ограничения через Content conditions в S3 bucket policy
    // или через Presigned POST (для ограничения размера)
  });

  const url = await getSignedUrl(s3, command, {
    expiresIn: 300, // 5 минут — достаточно для UI загрузки
  });

  return url; // клиент делает PUT на этот URL
}

// Генерация Pre-Signed URL для скачивания (GET) — приватные файлы
async function generateDownloadUrl(key: string): Promise<string> {
  const command = new GetObjectCommand({
    Bucket: process.env.BUCKET_NAME!,
    Key: key,
    ResponseContentDisposition: `attachment; filename="file.pdf"`,
  });
  return getSignedUrl(s3, command, { expiresIn: 3600 }); // 1 час
}
```

**Presigned POST** (альтернатива PUT): позволяет ограничить максимальный размер файла ($x-amz-meta condition), Content-Type. Предпочтительнее для загрузки из браузера.

## CloudFront — CDN и глобальное кэширование

CloudFront — Content Delivery Network: контент кэшируется в 250+ Edge Locations по всему миру. Запрос из Сиднея к S3 в us-east-1 (~200ms) vs Edge Location в Сиднее (~5ms).

```txt
Как работает кэширование:
  1. Запрос → ближайший Edge Location
  2. Cache HIT: ответ отдаётся немедленно из edge cache
  3. Cache MISS: EdgeLocation → Origin (S3/ALB/EC2/API GW) → кэшируется
  
TTL управляется:
  - Cache-Control header из Origin (max-age=86400)
  - CloudFront Behavior настройки (min/max/default TTL)
  - По умолчанию: 24 часа
```

```typescript
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';

const distribution = new cloudfront.Distribution(this, 'Distribution', {
  defaultBehavior: {
    origin: new origins.S3BucketOrigin(bucket, {
      originAccessControl: new cloudfront.S3OriginAccessControl(this, 'OAC'),
    }),
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
  },
  additionalBehaviors: {
    // API запросы — не кэшировать
    '/api/*': {
      origin: new origins.HttpOrigin('api.myapp.com'),
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
    },
  },
  // Custom domain + SSL
  domainNames: ['myapp.com', 'www.myapp.com'],
  certificate: acmCertificate, // ACM Certificate в us-east-1 (обязательно!)
});
```

## Cache Invalidation — инвалидация устаревшего кэша

```typescript
import { CloudFrontClient, CreateInvalidationCommand } from '@aws-sdk/client-cloudfront';

const cf = new CloudFrontClient({ region: 'us-east-1' });

// Инвалидация конкретных путей после деплоя
async function invalidateCache(distributionId: string, paths: string[]): Promise<void> {
  await cf.send(new CreateInvalidationCommand({
    DistributionId: distributionId,
    InvalidationBatch: {
      CallerReference: Date.now().toString(),
      Paths: {
        Quantity: paths.length,
        Items: paths, // ['/*'] — всё, или ['/index.html', '/app.js']
      },
    },
  }));
}

// Вызов после деплоя фронтенда:
await invalidateCache(process.env.CF_DISTRIBUTION_ID!, ['/*']);
```

**Лучшая практика**: вместо инвалидации использовать **content hashing** в именах файлов:
```txt
app.abc123.js   (хэш от содержимого)
app.def456.js   (новая версия с другим хэшем)
```
Браузер/CDN кэшируют навсегда (`max-age=31536000, immutable`). Только `index.html` инвалидируется при деплое (он содержит ссылку на новый хэш).

## SPA деплой на S3 + CloudFront

```txt
Архитектура:
  Next.js (static export) / React (CRA/Vite) → `npm run build`
  dist/               → S3 bucket
  CloudFront          → раздаёт из S3, edge caching
  Route53             → DNS → CloudFront distribution

Настройки CloudFront для SPA:
  Default Root Object: index.html
  Error pages: 404 → /index.html (200) — для client-side routing

Проблема с SPA routing:
  /dashboard → CloudFront → S3 ищет "dashboard" объект → 403/404
  Решение: Custom Error Response 403/404 → /index.html (status 200)
  React Router/Next.js Router обработает путь на клиенте.
```

## Типичные ошибки на интервью

- **"S3 — это файловая система"** — S3 объектное хранилище. Нет настоящих папок (только префиксы), нет частичного обновления, нет append операций. Для файловой системы (shared между EC2) — EFS. Для блочного хранилища (диск EC2) — EBS.

- **"Pre-Signed URL нужен чтобы скрыть AWS credentials"** — главная цель: избежать проксирования файлов через backend. Credentials никогда не отдаются клиенту. URL содержит подпись сервера, действительную ограниченное время.

- **"CloudFront обязателен только для видео"** — CloudFront ускоряет любой контент, включая JS/CSS/HTML. Для SPA деплоя S3+CloudFront обязателен: S3 endpoint медленнее (нет edge caching), нет HTTPS для custom domain без CloudFront.

- **"Cache Invalidation `/*` — правильный способ обновить кэш"** — рабочий, но не оптимальный. Инвалидация `/*` стоит денег (>1000 invalidations/мес платные), займёт время (~1-5 мин). Правильный подход: content-hashed filenames + инвалидировать только `index.html`.

- **"CloudFront SSL сертификат можно создать в любом регионе"** — для CloudFront ACM сертификат ОБЯЗАТЕЛЬНО должен быть в регионе `us-east-1` (глобальный сервис CloudFront читает сертификаты только оттуда). Распространённая ошибка: создать сертификат в eu-west-1 → CloudFront не видит его.
