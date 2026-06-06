<!-- verified: 2026-06-05, corrections: 0 -->
# File Storage и CDN

## Очень популярный вопрос

Спроектируйте загрузку файлов.

---

Плохое решение:

```txt
Frontend
 ↓
Backend
 ↓
File System
```

---

# Почему плохо

Backend становится узким местом.

---

# Хорошее решение

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

# Что происходит

Backend выдает:

```txt
временную ссылку
```

---

Frontend загружает файл напрямую.

---

# Преимущества

```txt
меньше нагрузка

лучше масштабирование

дешевле
```

---

# Где хранить файлы

Обычно:

```txt
S3

Google Cloud Storage

Azure Blob Storage
```

---

# Метаданные

Очень популярный вопрос.

---

Сам файл:

```txt
S3
```

---

Информация о файле:

```txt
PostgreSQL
```

---

# Схема

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

Следующий уровень.

---

Без CDN:

```txt
User Australia
 ↓
EU Server
```

---

Большая задержка.

---

# С CDN

```txt
User
 ↓
CloudFront
 ↓
Nearest Edge
```

---

# Cache Hit

Контент найден на Edge.

---

Очень быстро.

---

# Cache Miss

CloudFront идет в Origin.

---

# Origin

Обычно:

```txt
S3

Backend

Load Balancer
```

---

# Image Processing

Очень любят спрашивать.

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

# Почему очередь

Если одновременно:

```txt
10000 фото
```

---

Система не падает.

---

# Large Files

Еще популярный вопрос.

---

Используют:

```txt
Multipart Upload
```

---

Файл разбивается на части.

---

# Частый вопрос

Почему нельзя хранить файлы в PostgreSQL?

Ответ:

База данных быстро разрастается и начинает плохо масштабироваться.

---

# Частый вопрос

Что хранить в БД?

Ответ:

Метаданные файла, а не сам файл.

---

# Частый вопрос

Зачем нужен CDN?

Ответ:

Для уменьшения latency и нагрузки на origin сервер.

---

# Interview Answer

Файлы обычно хранятся в объектном хранилище (например S3), а их метаданные — в реляционной базе данных. Для ускорения доставки используется CDN, например CloudFront.