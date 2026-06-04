# S3 и CloudFront

## S3

Simple Storage Service.

---

Очень популярный вопрос.

---

S3 — объектное хранилище.

---

Важно:

```txt
НЕ файловая система
```

---

# Как хранятся данные

В виде:

```txt
Object
```

---

Каждый объект:

```txt
Key
Value
Metadata
```

---

Пример:

```txt
avatars/user1.jpg
```

---

# Bucket

Контейнер объектов.

---

Пример:

```txt
my-app-assets
```

---

Внутри:

```txt
images/
videos/
documents/
```

---

# Bucket ≠ Folder

Очень любят спрашивать.

---

В S3 нет настоящих папок.

---

Есть:

```txt
ключ объекта
```

---

Например:

```txt
images/logo.png
```

---

Папка:

```txt
images
```

фактически не существует.

---

# Почему S3 популярен

Практически бесконечное масштабирование.

---

AWS сам обеспечивает:

```txt
репликацию
отказоустойчивость
резервирование
```

---

# Частые кейсы

```txt
User Uploads

Images

Videos

Documents

Backups
```

---

# Pre-Signed URL

Очень популярный вопрос.

---

Проблема.

---

Не хотим:

```txt
Frontend
 ↓
Backend
 ↓
S3
```

---

Для каждого файла.

---

# Решение

Backend генерирует:

```txt
Pre-Signed URL
```

---

Frontend загружает файл:

```txt
напрямую в S3
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

Сервер не участвует.

---

# CloudFront

CDN AWS.

---

Content Delivery Network.

---

# Зачем нужен CDN

Без CDN:

```txt
Frankfurt
 ↓
Australia
```

---

Большая задержка.

---

# С CDN

```txt
User
 ↓
Nearest Edge Location
```

---

Контент ближе к пользователю.

---

# Edge Location

Сервер CloudFront.

---

Расположен по всему миру.

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

Первый запрос:

```txt
CloudFront → S3
```

---

Следующий:

```txt
CloudFront Cache
```

---

# Cache Hit

Контент найден в кеше.

---

Быстро.

---

# Cache Miss

Контент отсутствует.

---

CloudFront идет к Origin.

---

# Origin

Источник данных.

---

Например:

```txt
S3

ALB

EC2

API Gateway
```

---

# Invalidation

Очень популярный вопрос.

---

Проблема:

```txt
файл обновился
```

---

Но CDN хранит старую версию.

---

Решение:

```txt
CloudFront Invalidation
```

---

Либо:

```txt
Versioned Assets
```

---

Например:

```txt
app.v1.js
app.v2.js
```

---

# Почему часто используют S3 + CloudFront

Очень популярный вопрос.

---

Получаем:

```txt
дешевое хранение

масштабирование

CDN

отказоустойчивость
```

---

# Архитектура

```txt
Browser
 ↓
CloudFront
 ↓
S3
```

---

# Частый вопрос

Зачем CloudFront если есть S3?

Ответ:

S3 хранит данные, а CloudFront кеширует их на Edge Location и ускоряет доставку пользователям по всему миру.

---

# Частый вопрос

Что такое Pre-Signed URL?

Ответ:

Временная подписанная ссылка, позволяющая клиенту безопасно загружать или скачивать объект напрямую из S3 без передачи AWS credentials.

---

# Interview Answer

S3 является объектным хранилищем AWS и обычно используется для хранения файлов, изображений и документов. CloudFront представляет собой CDN, который кеширует контент на Edge Location и уменьшает задержки для пользователей. Часто эти сервисы используются вместе: S3 хранит данные, а CloudFront обеспечивает быструю доставку.