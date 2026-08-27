# S3 and CloudFront

## S3 — object storage, not a filesystem

S3 (Simple Storage Service) is the object storage of AWS (Amazon Web Services). It scales without a limit and gives 11 nines of durability (99.999999999%). Data is replicated automatically across at least 3 availability zones within a region.

Four differences from a filesystem drive every design decision around S3:

- No folder hierarchy. A "folder" is only a prefix inside the object key.
- No partial file updates. You replace the entire object.
- Three operations: PUT, GET, DELETE. There is no append, no seek, no lock.
- Access over an HTTP API or an SDK (software development kit), never a mounted filesystem. If you do need a filesystem for EC2 (Elastic Compute Cloud), that is EFS (Elastic File System).

An object is a key plus data plus metadata:

- **Key** — `avatars/user-123/profile.jpg`. The path is just a string, not a directory tree.
- **Value** — the file bytes, up to 5 terabytes per object.
- **Metadata** — `Content-Type`, `Cache-Control`, and custom `x-amz-meta-*` entries.

## Storage Classes — choosing by access pattern

S3 charges less for storage the longer you are willing to wait to read it back. Picking a class is a bet on how often the object will actually be read.

- **Standard** — frequent access, more than once a month, millisecond latency. $0.023 per gigabyte per month. For active application data.
- **Intelligent-Tiering** — moves objects between hot and cold tiers on its own. Adds $0.0025 per 1000 objects for the monitoring. For data with unpredictable access patterns.
- **Standard-IA (Infrequent Access)** — rare access, less than once a month, but retrieval still has to be fast. Cheaper storage, more expensive retrieval, 30-day minimum. For backups and disaster recovery (DR) copies.
- **Glacier Instant Retrieval** — archive with millisecond access, 90-day minimum. For quarterly backups.
- **Glacier Flexible Retrieval** — archive with 1-12 hour access, 90-day minimum. Expedited retrieval costs $0.03 per gigabyte, standard retrieval is free.
- **Glacier Deep Archive** — archive for 7-10+ years, 12-48 hour access, cheapest of all at $0.00099 per gigabyte per month. For compliance data and medical records.

An S3 Lifecycle Policy moves objects between classes on a schedule, so nobody has to remember to do it:

`Standard` → 30 days → `Standard-IA` → 90 days → `Glacier` → 365 days → `Deep Archive`

## S3 security — three access control layers

Three layers decide who may read a bucket, and the snippet sets them up in the right order. First the account-level public-access switch, then the policy on the bucket, then the policy on whoever is asking.

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

Without a pre-signed URL every byte travels client → backend → S3. A 10-gigabyte video crosses your server on the way: traffic you pay for, latency you add, and load your backend never needed.

With a pre-signed URL the file goes straight to S3 and your backend only hands out permission:

1. Client to backend: "I want to upload `avatar.jpg`".
2. Backend asks the AWS SDK to generate a pre-signed PUT URL.
3. Backend returns it: `{ url: "https://s3.amazonaws.com/...", fields: {...} }`.
4. Client sends PUT directly to S3. The backend is not involved.
5. S3 answers the client with `200 OK`.
6. Client tells the backend: "upload done, key `avatars/user-123/avatar.jpg`".
7. Backend saves that key to the user profile in the database.

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
    // Size limits go through content conditions in the S3 bucket policy,
    // or through Presigned POST
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

Caching has only three states, and just one of them is fast:

1. The request reaches the nearest edge location.
2. Cache hit — the response is served immediately from the edge cache.
3. Cache miss — the edge location goes to the origin and caches the answer on the way back. An origin can be S3, an ALB (Application Load Balancer), EC2 or API Gateway.

Three things control the TTL (time to live) of a cached object:

- The `Cache-Control` header sent by the origin, for example `max-age=86400`.
- The min, max and default TTL in the CloudFront behavior settings.
- The default of 24 hours, when nothing else says otherwise.

The distribution below serves the bucket through an OAC (origin access control), so the bucket stays private and only CloudFront is allowed to read it.

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

Invalidation tells CloudFront to forget a path before its TTL runs out. You need it after a deploy that changed the content of a file without changing its name.

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

A single-page application (SPA) is a folder of static files, so it needs no server: S3 stores it and CloudFront serves it. The one thing that breaks is client-side routing, and the fix is a single setting.

**Architecture**

- Next.js (static export) or React built with CRA (Create React App) or Vite — `npm run build`.
- `dist/` goes into an S3 bucket.
- CloudFront serves from that bucket, with edge caching.
- Route53 points DNS (domain name system) at the CloudFront distribution.

**CloudFront settings**

- Default Root Object: `index.html`.
- Error pages: 404 → `/index.html` with status 200, which is what makes client-side routing work.

**The routing problem**

A request for `/dashboard` reaches CloudFront, CloudFront asks S3 for an object named `dashboard`, and S3 answers 403 or 404. The fix is a Custom Error Response mapping 403 and 404 to `/index.html` with status 200. React Router or the Next.js router then resolves the path on the client.

## Common interview mistakes

- **"S3 is a filesystem"** — S3 is object storage. No real folders (only prefixes), no partial updates, no append operations. For a filesystem shared between EC2 instances, use EFS. For block storage, the disk of one EC2 instance, use EBS (Elastic Block Store).

- **"Pre-Signed URL is needed to hide AWS credentials"** — the main purpose is to avoid proxying files through the backend. Credentials are never given to the client. The URL contains a server-signed signature valid for a limited time.

- **"CloudFront is only needed for video"** — CloudFront accelerates any content, including JS, CSS and HTML. For a single-page application, S3 + CloudFront is essential. The raw S3 endpoint is slower, because it has no edge caching, and it cannot give you HTTPS (encrypted HTTP) on a custom domain.

- **"Cache Invalidation `/*` is the right way to update the cache"** — it works, but it's not optimal. Invalidating `/*` costs money (>1000 invalidations/month are paid), and takes time (~1-5 min). The right approach: content-hashed filenames + only invalidate `index.html`.

- **"A CloudFront SSL certificate can be created in any region"** — no. The SSL (Secure Sockets Layer) certificate for CloudFront **must** sit in `us-east-1`, and it is issued by ACM (AWS Certificate Manager). CloudFront is a global service and reads certificates only from that one region. The common mistake is creating the certificate in `eu-west-1`, after which CloudFront never sees it.
