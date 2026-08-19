# File Storage and CDN

## Why "files through the backend" is bad architecture

Almost every system handles files with two components. Object storage such as S3 (Simple Storage Service) holds the bytes. A CDN (content delivery network) delivers them close to the user. A naive implementation uses neither properly, and routes every byte through your own backend:

```txt
Frontend → Backend → File System / S3
```

The problem isn't "load" in some abstract sense — it's concrete:

```txt
- The backend holds an HTTP connection open for the entire
  upload (for a 1 GB video, that could be minutes),
  blocking a thread or worker that could be
  serving other requests
- The file passes through the backend's memory/disk twice:
  receive from the client → forward to S3
- The backend now has to scale for file upload traffic,
  even though its primary job is business logic
```

## Pre-Signed URLs — the right pattern

```txt
1. Frontend → Backend: "I want to upload report.pdf,
   5MB, application/pdf"
2. The backend checks permissions, generates a
   pre-signed URL (a signed, time-limited URL with
   specific allowed parameters, e.g. valid for 15 minutes)
3. Backend → Frontend: returns the pre-signed URL
4. Frontend → S3: uploads the file straight to S3
   via this URL (a PUT request)
5. The backend learns the upload completed via either:
   - an S3 callback/webhook (S3 Event Notifications), or
   - an explicit "I uploaded it, here's its id"
     request from the frontend
```

```ts
// Backend: generating a pre-signed URL (AWS SDK v3)
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

async function createUploadUrl(
  userId: string,
  fileName: string,
  contentType: string,
) {
  const key = `uploads/${userId}/${crypto.randomUUID()}-${fileName}`;

  const command = new PutObjectCommand({
    Bucket: 'my-app-uploads',
    Key: key,
    ContentType: contentType, // constrains which Content-Type S3 accepts
  });

  // the URL is valid for 15 minutes
  const url = await getSignedUrl(s3Client, command, { expiresIn: 900 });
  return { uploadUrl: url, key };
}
```

Why this fixes the problem:

```txt
+ The backend no longer passes the file's bytes
  through itself — only request metadata
  (milliseconds of CPU instead of minutes of I/O)
+ S3 scales horizontally out of the box — the backend
  doesn't need to think about it
+ Cheaper — traffic goes directly to object storage,
  bypassing the backend's compute resources
```

Security nuance: a pre-signed URL should **constrain** the upload — the `ContentType`, a maximum size via `Content-Length-Range` in the policy, and a specific `key`.

Without those constraints, a user who got a URL to upload their avatar could in theory upload almost anything. Any file, of any size, to any location in the bucket. That stays possible for the whole TTL (time to live) of the URL.

## Metadata: what goes in S3, what goes in the database

```txt
S3 (object storage):
  - the file's bytes
  - the URL/key for access

PostgreSQL (metadata):
  - id, userId, originalFileName
  - s3Key, size, mimeType
  - status (uploading / processing / ready / failed)
  - createdAt, processedAt
```

Why not store files in the database, in BLOB (binary large object) columns? Relational databases aren't physically designed for large binary objects. It bloats database size and slows down backups — backing up a database with terabytes of video takes hours. It also works poorly with database-level replication and caching.

Object storage is designed exactly for this: cheap storage, built-in geo-distribution, direct serving via a CDN.

The `status` field is an important detail that's often missed. After getting a pre-signed URL, the client might never actually upload the file, for example because the tab was closed. The database record needs to reflect that state, so the user isn't shown "file uploaded" when nothing exists in S3. You also need periodic cleanup of "orphaned" records stuck in `uploading` that never moved to `ready`.

## CDN: like a cache, but for files, with privacy nuances

A CDN keeps copies of your files at edge locations around the world:

```txt
Without a CDN:
  User (Australia) → Origin (S3 bucket in eu-west-1)
  → latency determined by distance to Ireland

With a CDN:
  User (Australia) → CDN Edge (Sydney)
  → cache hit: served from the edge, minimal latency
  → cache miss: edge fetches from Origin,
    caches it, serves the user
```

### Public content vs private content

For public files (avatars, product images) it's simple: the CDN caches by URL, and `Cache-Control` headers define the TTL.

For **private** content (a user's documents, paid video), caching by URL doesn't work, because the URL shouldn't be accessible without authorization. Two things make it work:

- **Signed CDN URLs** (CloudFront Signed URLs or Cookies) — the CDN itself verifies a signature and expiry before serving cached content.
- Caching at the CDN level still works, because the content is cached at the edge. Access is controlled by a time-limited signature rather than by the URL's secrecy.

### Cache invalidation for a CDN

The problem: a user updated their avatar, but the CDN keeps serving the old version to everyone for the next 24 hours — the `Cache-Control` TTL. There are two solutions:

1. **Versioned URLs**: `avatar-v2.jpg` instead of `avatar.jpg`. A new URL means a guaranteed cache miss, which means new content. This is the best approach, because it requires no explicit invalidation at all.
2. **An explicit invalidation API** (CloudFront Invalidation) — an explicit "purge the cache for this path on all edge nodes" request. Slower (minutes), and it costs money if used frequently.

Versioned URLs are almost always the better choice for user content. They turn the question "when do we invalidate the cache" into "the cache lives forever, because the URL is unique per content version."

## Image/Video Processing Pipeline

```txt
1. Client → pre-signed URL → S3 (original)
2. S3 Event Notification → Queue
3. A worker reads the event, downloads the original from S3
4. The worker generates derived versions:
   - thumbnails at various sizes
   - format conversion (HEIC → JPEG,
     video → multiple resolutions)
5. The worker uploads the results back to S3
   (separate keys/bucket)
6. The worker updates the database status
   (status: ready, adds derived URLs)
7. The frontend learns processing is done, via polling,
   WebSocket or server-sent events
```

The queue here solves the same problem as in the Message Queues article. In the Amazon stack that queue is SQS (Simple Queue Service) or SNS (Simple Notification Service).

10,000 simultaneous uploads don't become 10,000 parallel heavy video-processing jobs. They become 10,000 messages in a queue, processed at a steady rate by a worker pool. Without a queue, a sudden spike of uploads — after a viral post, say — would crash the processing service.

## Multipart Upload — for large files

```txt
A 5 GB file:
  - split into parts of 5-100 MB
  - each part uploaded via a separate PUT request
    (can be parallel, can be retried individually)
  - after all parts are uploaded,
    CompleteMultipartUpload assembles them
    into one object
```

Why: with a single-request upload, any network failure at 99% means retrying **the entire file from scratch**. Multipart lets you retry only the failed part. It also lets you parallelize the upload, which is faster on fast connections. And it supports files beyond the single-PUT limit — 5GB for a single S3 PUT.

## Upload security — a frequent follow-up

- Validate `Content-Type` on the backend when issuing the pre-signed URL. Don't trust the file extension reported by the client.
- Scan for viruses and malware **after** upload but **before** the file becomes accessible to other users: status "scanning" → "ready".
- Enforce size limits via the pre-signed URL policy, not just client-side checks. The client can be bypassed.
- Isolate uploaded user content from executable code — a separate domain or bucket with no execution capability. This avoids XSS (cross-site scripting) via an uploaded "image.svg" with JS embedded in it.

## Common interview mistakes

- **Proposing "upload through the backend" as the final answer**, without mentioning pre-signed URLs. That is the expected "correct" solution for this topic.

- **Storing files as BLOBs in a relational database**, without explaining why this scales poorly: database size, backups, replication.

- **Not separating metadata from the file itself** — confusing "where the file is stored" with "where information about the file is stored."

- **CDN as "just a cache".** That misses the difference between public and private content, and misses that private content needs signed URLs rather than no CDN at all.

- **An explicit cache-invalidation API as the only solution**, without mentioning versioned URLs, which avoid the invalidation problem altogether.

- **Not mentioning a queue for media processing.** Synchronous thumbnail generation on upload means the user waits for video processing inside an HTTP request.

- **Ignoring upload security** — a pre-signed URL with no size or type limits, and no content scanning before content is made public.
