# S3 and CloudFront

## S3

Simple Storage Service.

---

Very popular interview question.

---

S3 is an object storage.

---

Important:

```txt
NOT a file system
```

---

# How Data is Stored

As:

```txt
Object
```

---

Each object has:

```txt
Key
Value
Metadata
```

---

Example:

```txt
avatars/user1.jpg
```

---

# Bucket

A container for objects.

---

Example:

```txt
my-app-assets
```

---

Inside:

```txt
images/
videos/
documents/
```

---

# Bucket ≠ Folder

Interviewers love asking this.

---

S3 has no real folders.

---

There is:

```txt
object key
```

---

For example:

```txt
images/logo.png
```

---

The folder:

```txt
images
```

doesn't actually exist.

---

# Why S3 is Popular

Practically infinite scaling.

---

AWS handles:

```txt
replication
fault tolerance
redundancy
```

---

# Common Use Cases

```txt
User Uploads

Images

Videos

Documents

Backups
```

---

# Pre-Signed URL

Very popular interview question.

---

The problem.

---

We don't want:

```txt
Frontend
 ↓
Backend
 ↓
S3
```

---

For every file.

---

# Solution

Backend generates:

```txt
Pre-Signed URL
```

---

Frontend uploads the file:

```txt
directly to S3
```

---

# Flow

```txt
Frontend
 ↓
API
 ↓
PreSigned URL

Frontend
 ↓
S3 Upload
```

---

The server is not involved.

---

# CloudFront

AWS CDN.

---

Content Delivery Network.

---

# Why You Need a CDN

Without CDN:

```txt
Frankfurt
 ↓
Australia
```

---

High latency.

---

# With CDN

```txt
User
 ↓
Nearest Edge Location
```

---

Content is closer to the user.

---

# Edge Location

A CloudFront server.

---

Located worldwide.

---

# Flow

```txt
Browser
 ↓
CloudFront
 ↓
S3
```

---

First request:

```txt
CloudFront → S3
```

---

Subsequent requests:

```txt
CloudFront Cache
```

---

# Cache Hit

Content found in cache.

---

Fast.

---

# Cache Miss

Content not found.

---

CloudFront goes to the Origin.

---

# Origin

The data source.

---

For example:

```txt
S3

ALB

EC2

API Gateway
```

---

# Invalidation

Very popular interview question.

---

Problem:

```txt
file was updated
```

---

But CDN still holds the old version.

---

Solution:

```txt
CloudFront Invalidation
```

---

Or:

```txt
Versioned Assets
```

---

For example:

```txt
app.v1.js
app.v2.js
```

---

# Why S3 + CloudFront is Commonly Used

Very popular interview question.

---

We get:

```txt
cheap storage

scalability

CDN

fault tolerance
```

---

# Architecture

```txt
Browser
 ↓
CloudFront
 ↓
S3
```

---

# Common Question

Why use CloudFront if S3 already exists?

Answer:

S3 stores data, while CloudFront caches it at Edge Locations and speeds up delivery to users worldwide.

---

# Common Question

What is a Pre-Signed URL?

Answer:

A temporary signed link that allows a client to safely upload or download an object directly from S3 without passing AWS credentials.

---

# Interview Answer

S3 is AWS's object storage and is commonly used for storing files, images, and documents. CloudFront is a CDN that caches content at Edge Locations and reduces latency for users. These services are often used together: S3 stores the data and CloudFront ensures fast delivery.
