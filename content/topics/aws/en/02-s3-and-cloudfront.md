# S3 and CloudFront

## S3 — object storage, not a filesystem

S3 (Simple Storage Service) is object storage: unlimited scaling, 11 nines durability (99.999999999%), data is automatically replicated across at least 3 AZs within a region.

```txt
Key differences from a filesystem:
  - No folder hierarchy: "folders" are just a prefix in the object key
  - No partial file updates: replace the entire object
  - Operations: PUT/GET/DELETE (no append, seek, lock)
  - Access via HTTP API (or SDK), not filesystem mount
    (EFS — if you need a filesystem for EC2)

Object = key + data + metadata:
  Key:      "avatars/user-123/profile.jpg"  (path is just a string)
  Value:    file bytes (up to 5TB per object)
  Metadata: Content-Type, Cache-Control, custom x-amz-meta-*
```

## Storage Classes — choosing by access pattern

```txt
Standard:
  Frequent access (>1x/month). Millisecond latency.
  $0.023/GB/month. For active application data.

Intelligent-Tiering:
  Automatically moves between Hot/Cold tiers.
  Plus $0.0025/1000 objects for monitoring.
  For data with unpredictable access patterns.

Standard-IA (Infrequent Access):
  Rare access (<1x/month), but fast retrieval needed.
  Cheaper storage, more expensive retrieval. 30-day minimum.
  For backups, DR copies.

Glacier Instant Retrieval:
  Archive, millisecond access. 90-day minimum. For quarterly backups.

Glacier Flexible Retrieval:
  Archive, 1-12h access (expedited: $0.03/GB, standard: free).
  90-day minimum.

Glacier Deep Archive:
  7-10+ year archive, 12-48h access. Cheapest ($0.00099/GB/month).
  Compliance data, medical records.

S3 Lifecycle Policy: automatically transition objects between classes:
  30 days → Standard-IA → 90 days → Glacier → 365 days → Deep Archive
```

## S3 security — three access control layers

```typescript
// 1. Block Public Access (mandatory for private buckets)
// In CDK:
const bucket = new s3.Bucket(this, 'AppBucket', {
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, // block all public access
  encryption: s3.BucketEncryption.S3_MANAGED,        // SSE-S3 encryption
  versioned: true,                                    // object versioning
});

// 2. Bucket Policy — resource-based policy (JSON)
// Allow CloudFront to read from the bucket:
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

// 3. IAM Policy — identity-based (for users/roles)
// Lambda gets only the permissions it needs:
bucket.grantRead(lambdaFunction);           // only GetObject, ListBucket
bucket.grantPut(lambdaFunction);            // only PutObject
bucket.grantReadWrite(lambdaFunction);      // GetObject + PutObject
// bucket.grantPublicAccess() — never for private data!
```

## Pre-Signed URL — uploading files directly to S3

A classic senior question: how to implement file uploads without proxying through your server?

```txt
Problem without Pre-Signed URL:
  Client → Backend (10GB video) → S3
  Downsides: traffic through your server (expensive, slow), backend load

Solution with Pre-Signed URL:
  1. Client → Backend: "I want to upload avatar.jpg"
  2. Backend → AWS SDK: generate pre-signed PUT URL
  3. Backend → Client: { url: "https://s3.amazonaws.com/...", fields: {...} }
  4. Client → S3: PUT directly (Backend is not involved!)
  5. S3 → Client: 200 OK
  6. Client → Backend: "upload done, key: avatars/user-123/avatar.jpg"
  7. Backend → DB: save the key to the user's profile
```

```typescript
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const s3 = new S3Client({ region: 'eu-west-1' });

// Generate a Pre-Signed URL for upload (PUT)
async function generateUploadUrl(userId: string, filename: string): Promise<string> {
  const key = `avatars/${userId}/${Date.now()}-${filename}`;

  const command = new PutObjectCommand({
    Bucket: process.env.BUCKET_NAME!,
    Key: key,
    ContentType: 'image/jpeg',
  });

  const url = await getSignedUrl(s3, command, {
    expiresIn: 300, // 5 minutes — enough for a UI upload
  });

  return url; // client does PUT to this URL
}

// Generate a Pre-Signed URL for download (GET) — private files
async function generateDownloadUrl(key: string): Promise<string> {
  const command = new GetObjectCommand({
    Bucket: process.env.BUCKET_NAME!,
    Key: key,
    ResponseContentDisposition: `attachment; filename="file.pdf"`,
  });
  return getSignedUrl(s3, command, { expiresIn: 3600 }); // 1 hour
}
```

**Presigned POST** (alternative to PUT): allows restricting maximum file size (via `$content-length-range` condition) and Content-Type. Preferred for browser uploads.

## CloudFront — CDN and global caching

CloudFront is a Content Delivery Network: content is cached at 250+ Edge Locations worldwide. A request from Sydney to S3 in us-east-1 (~200ms) vs a Sydney Edge Location (~5ms).

```txt
How caching works:
  1. Request → nearest Edge Location
  2. Cache HIT: response is served immediately from edge cache
  3. Cache MISS: EdgeLocation → Origin (S3/ALB/EC2/API GW) → cached

TTL is controlled by:
  - Cache-Control header from Origin (max-age=86400)
  - CloudFront Behavior settings (min/max/default TTL)
  - Default: 24 hours
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
    // API requests — don't cache
    '/api/*': {
      origin: new origins.HttpOrigin('api.myapp.com'),
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
    },
  },
  // Custom domain + SSL
  domainNames: ['myapp.com', 'www.myapp.com'],
  certificate: acmCertificate, // ACM Certificate in us-east-1 (required!)
});
```

## Cache Invalidation — clearing stale cache

```typescript
import { CloudFrontClient, CreateInvalidationCommand } from '@aws-sdk/client-cloudfront';

const cf = new CloudFrontClient({ region: 'us-east-1' });

// Invalidate specific paths after a deploy
async function invalidateCache(distributionId: string, paths: string[]): Promise<void> {
  await cf.send(new CreateInvalidationCommand({
    DistributionId: distributionId,
    InvalidationBatch: {
      CallerReference: Date.now().toString(),
      Paths: {
        Quantity: paths.length,
        Items: paths, // ['/*'] — everything, or ['/index.html', '/app.js']
      },
    },
  }));
}

// Called after frontend deploy:
await invalidateCache(process.env.CF_DISTRIBUTION_ID!, ['/*']);
```

**Best practice**: instead of invalidation, use **content hashing** in filenames:
```txt
app.abc123.js   (hash of content)
app.def456.js   (new version with a different hash)
```
Browser/CDN caches these forever (`max-age=31536000, immutable`). Only `index.html` is invalidated on deploy (it contains the link to the new hash).

## SPA deployment on S3 + CloudFront

```txt
Architecture:
  Next.js (static export) / React (CRA/Vite) → `npm run build`
  dist/               → S3 bucket
  CloudFront          → serves from S3, edge caching
  Route53             → DNS → CloudFront distribution

CloudFront settings for SPA:
  Default Root Object: index.html
  Error pages: 404 → /index.html (200) — for client-side routing

SPA routing problem:
  /dashboard → CloudFront → S3 looks for a "dashboard" object → 403/404
  Solution: Custom Error Response 403/404 → /index.html (status 200)
  React Router/Next.js Router handles the path on the client.
```

## Common interview mistakes

- **"S3 is a filesystem"** — S3 is object storage. No real folders (only prefixes), no partial updates, no append operations. For a shared filesystem between EC2 — EFS. For block storage (EC2 disk) — EBS.

- **"Pre-Signed URL is needed to hide AWS credentials"** — the main purpose is to avoid proxying files through the backend. Credentials are never given to the client. The URL contains a server-signed signature valid for a limited time.

- **"CloudFront is only needed for video"** — CloudFront accelerates any content, including JS/CSS/HTML. For SPA deployment, S3+CloudFront is essential: the S3 endpoint is slower (no edge caching), and there's no HTTPS for a custom domain without CloudFront.

- **"Cache Invalidation `/*` is the right way to update the cache"** — it works, but it's not optimal. Invalidating `/*` costs money (>1000 invalidations/month are paid), and takes time (~1-5 min). The right approach: content-hashed filenames + only invalidate `index.html`.

- **"A CloudFront SSL certificate can be created in any region"** — for CloudFront, an ACM certificate MUST be in the `us-east-1` region (CloudFront, being a global service, only reads certificates from there). A common mistake: create a certificate in eu-west-1 → CloudFront doesn't see it.
