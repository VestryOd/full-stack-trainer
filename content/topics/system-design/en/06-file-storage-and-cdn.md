# File Storage and CDN

## A Very Popular Question

Design a file upload service.

---

Bad solution:

```txt
Frontend
 ↓
Backend
 ↓
File System
```

---

# Why It Is Bad

The backend becomes a bottleneck.

---

# Good Solution

```txt
Frontend
 ↓
Backend
 ↓
Pre-Signed URL

Frontend
 ↓
S3
```

---

# What Happens

The backend issues:

```txt
a temporary URL
```

---

The frontend uploads the file directly.

---

# Advantages

```txt
less load

better scaling

cheaper
```

---

# Where to Store Files

Usually:

```txt
S3

Google Cloud Storage

Azure Blob Storage
```

---

# Metadata

A very popular question.

---

The file itself:

```txt
S3
```

---

Information about the file:

```txt
PostgreSQL
```

---

# Schema

```txt
Files Table

id

userId

url

size

mimeType
```

---

# CDN

The next level.

---

Without CDN:

```txt
User Australia
 ↓
EU Server
```

---

High latency.

---

# With CDN

```txt
User
 ↓
CloudFront
 ↓
Nearest Edge
```

---

# Cache Hit

Content found at the Edge.

---

Very fast.

---

# Cache Miss

CloudFront goes to Origin.

---

# Origin

Usually:

```txt
S3

Backend

Load Balancer
```

---

# Image Processing

Interviewers love asking about this.

---

```txt
Upload
 ↓
S3
 ↓
Queue
 ↓
Worker
 ↓
Thumbnail
 ↓
S3
```

---

# Why a Queue

If simultaneously:

```txt
10000 photos
```

---

The system does not crash.

---

# Large Files

Another popular question.

---

Uses:

```txt
Multipart Upload
```

---

The file is split into parts.

---

# Common Question

Why can't you store files in PostgreSQL?

Answer:

The database grows quickly and starts to scale poorly.

---

# Common Question

What to store in the DB?

Answer:

File metadata, not the file itself.

---

# Common Question

Why is CDN needed?

Answer:

To reduce latency and load on the origin server.

---

# Interview Answer

Files are typically stored in an object store (such as S3) and their metadata is stored in a relational database. A CDN such as CloudFront is used to speed up delivery.
