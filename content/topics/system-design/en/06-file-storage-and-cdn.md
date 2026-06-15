# File Storage and CDN

## Why "files through the backend" is bad architecture

A naive file upload implementation:

```txt
Frontend → Backend → File System / S3
```

The problem isn't "load" in some abstract sense — it's concrete:

```txt
- The backend holds an HTTP connection open for the entire upload
  (for a 1 GB video, that could be minutes) — tying up a thread/worker
  that could be serving other requests
- The file passes through the backend's memory/disk twice:
  receive from the client → forward to S3
- The backend now has to scale for FILE UPLOAD traffic,
  even though its primary job is business logic
```

## Pre-Signed URLs — the right pattern

```txt
1. Frontend → Backend: "I want to upload report.pdf, 5MB, application/pdf"
2. The backend checks permissions, generates a pre-signed URL
   (a signed, time-limited URL with specific allowed parameters,
   e.g. valid for 15 minutes)
3. Backend → Frontend: returns the pre-signed URL
4. Frontend → S3: uploads the file DIRECTLY via this URL (a PUT request)
5. The backend learns the upload completed via either:
   - an S3 callback/webhook (S3 Event Notifications), or
   - an explicit "I uploaded it, here's its id" request from the frontend
```

```ts
// Backend: generating a pre-signed URL (AWS SDK v3)
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

async function createUploadUrl(userId: string, fileName: string, contentType: string) {
  const key = `uploads/${userId}/${crypto.randomUUID()}-${fileName}`;

  const command = new PutObjectCommand({
    Bucket: 'my-app-uploads',
    Key: key,
    ContentType: contentType, // constrains which Content-Type S3 will accept
  });

  const url = await getSignedUrl(s3Client, command, { expiresIn: 900 }); // 15 minutes
  return { uploadUrl: url, key };
}
```

Why this fixes the problem:

```txt
+ The backend no longer passes the file's bytes through itself —
  only request metadata (milliseconds of CPU instead of minutes of I/O)
+ S3 scales horizontally out of the box — the backend doesn't
  need to think about it
+ Cheaper — traffic goes directly to object storage,
  bypassing the backend's compute resources
```

Security nuance: a pre-signed URL should **constrain** the upload (`ContentType`, a maximum size via `Content-Length-Range` in the policy, a specific `key`) — otherwise a user who got a URL to upload their avatar could, in theory, upload an arbitrary file of arbitrary size to an arbitrary location in the bucket during the URL's TTL.

## Metadata: what goes in S3, what goes in the DB

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

Why not store files in the DB (BLOB columns): relational databases aren't physically designed to store large binary objects — it bloats DB size, slows down backups (backing up a DB with TBs of video takes hours), and works poorly with DB-level replication and caching. Object storage is designed exactly for this: cheap storage, built-in geo-distribution, direct serving via CDN.

The `status` field is an important detail that's often missed: after getting a pre-signed URL, the client might never actually upload the file (closed the tab) — the DB record needs to reflect this state so the user isn't shown "file uploaded" when it doesn't exist in S3. You also need periodic cleanup of "orphaned" records stuck in `uploading` that never transitioned to `ready`.

## CDN: like a cache, but for files, with privacy nuances

```txt
Without a CDN:
  User (Australia) → Origin (S3 bucket in eu-west-1)
  → latency determined by distance to Ireland

With a CDN:
  User (Australia) → CDN Edge (Sydney)
  → cache hit: served from the edge, minimal latency
  → cache miss: edge fetches from Origin, caches it, serves the user
```

### Public content vs private content

For public files (avatars, product images), it's simple: the CDN caches by URL, `Cache-Control` headers define the TTL.

For **private** content (a user's documents, paid video content), caching by URL doesn't work, because the URL shouldn't be accessible without authorization. Solutions:

```txt
- Signed CDN URLs (CloudFront Signed URLs/Cookies) — the CDN itself
  verifies a signature/expiry before serving cached content
- Caching at the CDN level still works (content is cached at the edge),
  but access is controlled by a time-limited signature,
  not by the URL's secrecy
```

### Cache invalidation for a CDN

```txt
Problem: a user updated their avatar, but the CDN keeps serving
the old version to everyone for the next 24 hours (the Cache-Control TTL)

Solutions:
  1. Versioned URLs: avatar-v2.jpg instead of avatar.jpg —
     a new URL = guaranteed cache miss = new content.
     This is the best approach — it requires NO explicit invalidation.
  2. Explicit invalidation API (CloudFront Invalidation) —
     an explicit "purge the cache for this path on all edge nodes"
     request — slower (minutes) and costs money if used frequently
```

Versioned URLs are almost always the better choice for user content: they turn the "when do we invalidate the cache" problem into "the cache lives forever, because the URL is unique per content version."

## Image/Video Processing Pipeline

```txt
1. Client → pre-signed URL → S3 (original)
2. S3 Event Notification → Queue (SQS/SNS)
3. A worker reads the event, downloads the original from S3
4. The worker generates derived versions:
   - thumbnails at various sizes
   - format conversion (HEIC → JPEG, video → multiple resolutions)
5. The worker uploads the results back to S3 (separate keys/bucket)
6. The worker updates the DB status (status: ready, adds derived URLs)
7. The frontend (via polling/WebSocket/SSE) learns processing is done
```

The queue here solves the same problem as in [Message Queues]: 10,000 simultaneous uploads don't become 10,000 parallel heavy video-processing jobs — they become 10,000 messages in a queue, processed at a steady rate by a worker pool. Without a queue, a sudden spike of uploads (e.g., after a viral post) would crash the processing service.

## Multipart Upload — for large files

```txt
A 5 GB file:
  - split into parts of 5-100 MB
  - each part uploaded via a separate PUT request
    (can be parallel, can be retried individually)
  - after all parts are uploaded, CompleteMultipartUpload assembles them into one object
```

Why: with a single-request upload, any network failure at 99% means retrying **the entire file from scratch**. Multipart lets you retry only the failed part, parallelize the upload (faster on fast connections), and support files beyond the single-PUT limit (5GB for a single S3 PUT).

## Upload security — a frequent follow-up

```txt
- Validate Content-Type on the backend when issuing the pre-signed URL —
  don't trust the file extension reported by the client
- Scan for viruses/malware AFTER upload, BEFORE the file becomes
  accessible to other users (status "scanning" → "ready")
- Enforce size limits via the pre-signed URL policy,
  not just client-side checks (the client can be bypassed)
- Isolate uploaded user content from
  executable code — a separate domain/bucket with no
  execution capability (avoid XSS via an uploaded "image.svg" with embedded JS)
```

## Common interview mistakes

- **Proposing "upload through the backend" as the final answer** — without mentioning pre-signed URLs, which is the expected "correct" solution for this topic.

- **Storing files as BLOBs in a relational DB** — without explaining why this scales poorly (DB size, backups, replication).

- **Not separating metadata from the file itself** — confusing "where the file is stored" with "where information about the file is stored."

- **CDN as "just a cache"** — without mentioning the difference between public and private content, and that private content needs signed URLs, not just the absence of a CDN.

- **Explicit cache-invalidation API as the only solution** — without mentioning versioned URLs, which elegantly avoid the invalidation problem altogether.

- **Not mentioning a queue for media processing** — synchronous thumbnail generation on upload means the user waits for video processing within an HTTP request.

- **Ignoring upload security** — a pre-signed URL with no size/type limits, no content scanning before content is made public.
