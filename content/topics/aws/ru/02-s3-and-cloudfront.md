<!-- verified: 2026-06-05, corrections: 0 -->
# S3 и CloudFront

## S3 — объектное хранилище, не файловая система

S3 (Simple Storage Service) — объектное хранилище AWS (Amazon Web Services). Оно масштабируется без предела и даёт 11 девяток надёжности хранения, durability (99.999999999%). Данные автоматически реплицируются минимум в 3 зоны доступности одного региона.

Четыре отличия от файловой системы определяют всё, что вы будете строить вокруг S3:

- Нет иерархии папок. «Папка» — это только префикс внутри ключа объекта.
- Нет частичного обновления файла. Объект заменяется целиком.
- Три операции: PUT, GET, DELETE. Нет ни append, ни seek, ни блокировок.
- Доступ идёт через HTTP API или SDK (software development kit), а не через примонтированную файловую систему. Если файловая система нужна именно для EC2 (Elastic Compute Cloud) — это EFS (Elastic File System).

Объект — это ключ плюс данные плюс метаданные:

- **Ключ** — `avatars/user-123/profile.jpg`. Путь здесь просто строка, а не дерево каталогов.
- **Значение** — байты файла, до 5 терабайт на объект.
- **Метаданные** — `Content-Type`, `Cache-Control` и произвольные `x-amz-meta-*`.

## Storage Classes — выбор по паттерну доступа

Чем дольше вы готовы ждать чтения, тем дешевле S3 берёт за хранение. Выбор класса — это ставка на то, как часто объект реально будут читать.

- **Standard** — частый доступ, чаще раза в месяц, задержка в миллисекундах. $0.023 за гигабайт в месяц. Для активных данных приложения.
- **Intelligent-Tiering** — сам перекладывает объекты между горячим и холодным уровнями. Добавляет $0.0025 за 1000 объектов за мониторинг. Для данных с непредсказуемым паттерном доступа.
- **Standard-IA (Infrequent Access)** — редкий доступ, реже раза в месяц, но выдача всё равно нужна быстрая. Хранение дешевле, выдача дороже, минимум 30 дней хранения. Для резервных копий и копий на случай аварии, disaster recovery (DR).
- **Glacier Instant Retrieval** — архив с доступом за миллисекунды, минимум 90 дней. Для квартальных бэкапов.
- **Glacier Flexible Retrieval** — архив с доступом за 1-12 часов, минимум 90 дней. Ускоренная выдача стоит $0.03 за гигабайт, обычная бесплатна.
- **Glacier Deep Archive** — архив на 7-10+ лет, доступ 12-48 часов, самый дешёвый из всех: $0.00099 за гигабайт в месяц. Для данных под регуляторные требования и медицинских записей.

S3 Lifecycle Policy переводит объекты между классами по расписанию, чтобы об этом никто не вспоминал руками:

`Standard` → 30 дней → `Standard-IA` → 90 дней → `Glacier` → 365 дней → `Deep Archive`

## Безопасность S3 — три уровня управления доступом

Кто может читать бакет, решают три уровня, и сниппет ставит их в правильном порядке. Сначала переключатель публичного доступа на уровне аккаунта, затем политика на самом бакете, затем политика на том, кто спрашивает.

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

Без pre-signed URL каждый байт идёт по маршруту клиент → бэкенд → S3. Видео на 10 гигабайт проходит через ваш сервер: это оплаченный трафик, добавленная задержка и нагрузка, которая бэкенду не нужна.

С pre-signed URL файл уходит прямо в S3, а бэкенд только выдаёт разрешение:

1. Клиент бэкенду: «хочу загрузить файл `avatar.jpg`».
2. Бэкенд просит AWS SDK сгенерировать pre-signed PUT URL.
3. Бэкенд возвращает его клиенту: `{ url: "https://s3.amazonaws.com/...", fields: {...} }`.
4. Клиент шлёт PUT напрямую в S3. Бэкенд в этом уже не участвует.
5. S3 отвечает клиенту `200 OK`.
6. Клиент сообщает бэкенду: «загрузка завершена, ключ `avatars/user-123/avatar.jpg`».
7. Бэкенд сохраняет этот ключ в профиле пользователя в базе данных.

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
    // Ограничения размера — через content conditions в bucket policy S3
    // или через Presigned POST
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

**Presigned POST** (альтернатива PUT): позволяет ограничить максимальный размер файла (условие `$content-length-range`) и `Content-Type`. Предпочтительнее для загрузки из браузера.

## CloudFront — CDN и глобальное кэширование

CloudFront — это Content Delivery Network: контент кэшируется в 250+ пограничных точках по всему миру. Запрос из Сиднея к S3 в us-east-1 идёт около 200 мс, а к пограничной точке в самом Сиднее — около 5 мс.

У кэширования всего три состояния, и быстрое из них только одно:

1. Запрос приходит в ближайшую пограничную точку.
2. Попадание в кэш — ответ сразу отдаётся из кэша на границе сети.
3. Промах — пограничная точка идёт к источнику и кэширует ответ по дороге назад. Источником может быть S3, ALB (Application Load Balancer), EC2 или API Gateway.

Время жизни объекта в кэше, TTL (time to live), задают три вещи:

- Заголовок `Cache-Control` от источника, например `max-age=86400`.
- Значения min, max и default для TTL в настройках CloudFront Behavior.
- Значение по умолчанию — 24 часа, если больше ничего не сказано.

Дистрибуция ниже раздаёт бакет через OAC (origin access control), поэтому сам бакет остаётся приватным и читать его может только CloudFront.

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

Инвалидация говорит CloudFront забыть путь раньше, чем истечёт его TTL. Она нужна после деплоя, который поменял содержимое файла, не поменяв его имя.

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

**Лучшая практика**: вместо инвалидации использовать **хэш содержимого** (content hashing) в именах файлов:
```txt
app.abc123.js   (хэш от содержимого)
app.def456.js   (новая версия с другим хэшем)
```
Браузер/CDN кэшируют навсегда (`max-age=31536000, immutable`). Только `index.html` инвалидируется при деплое (он содержит ссылку на новый хэш).

## SPA деплой на S3 + CloudFront

Одностраничное приложение (SPA) — это папка статических файлов, поэтому сервер ему не нужен: S3 хранит, CloudFront раздаёт. Ломается ровно одно — маршрутизация на клиенте, и чинится она одной настройкой.

**Архитектура**

- Next.js (статический экспорт) или React, собранный через CRA (Create React App) либо Vite — `npm run build`.
- Папка `dist/` уезжает в S3-бакет.
- CloudFront раздаёт из этого бакета с кэшем на границе сети.
- Route53 направляет DNS (domain name system) на дистрибуцию CloudFront.

**Настройки CloudFront**

- Default Root Object: `index.html`.
- Страницы ошибок: 404 → `/index.html` со статусом 200 — именно это заставляет работать маршрутизацию на клиенте.

**Проблема с маршрутизацией**

Запрос на `/dashboard` приходит в CloudFront, CloudFront просит у S3 объект с именем `dashboard`, и S3 отвечает 403 или 404. Лечится это Custom Error Response, который отображает 403 и 404 на `/index.html` со статусом 200. Дальше путь разбирает React Router или роутер Next.js уже на клиенте.

## Типичные ошибки на интервью

- **«S3 — это файловая система»** — S3 объектное хранилище. Нет настоящих папок (только префиксы), нет частичного обновления, нет операций append. Для файловой системы, общей для нескольких EC2, есть EFS. Для блочного хранилища, диска одной EC2, есть EBS (Elastic Block Store).

- **«Pre-Signed URL нужен, чтобы скрыть ключи доступа AWS»** — главная цель другая: не прогонять файлы через бэкенд. Ключи доступа клиенту не отдаются никогда. URL содержит подпись сервера, действительную ограниченное время.

- **«CloudFront обязателен только для видео»** — CloudFront ускоряет любой контент, включая JS, CSS и HTML. Для одностраничного приложения связка S3 + CloudFront обязательна. Голая точка входа S3 медленнее, потому что у неё нет кэша на границе сети, и она не даёт HTTPS (зашифрованный HTTP) на своём домене.

- **«Cache Invalidation `/*` — правильный способ обновить кэш»** — рабочий, но не оптимальный. Инвалидация `/*` стоит денег: больше 1000 инвалидаций в месяц уже платные. И она занимает время, примерно 1-5 минут. Правильный подход — хэш содержимого в имени файла плюс инвалидация только `index.html`.

- **«SSL-сертификат для CloudFront можно создать в любом регионе»** — нет. SSL-сертификат (Secure Sockets Layer) для CloudFront **обязан** лежать в `us-east-1`, и выпускает его ACM (AWS Certificate Manager). CloudFront — глобальный сервис и читает сертификаты только из этого региона. Распространённая ошибка — создать сертификат в `eu-west-1`, после чего CloudFront его просто не видит.
