<!-- verified: 2026-06-05, corrections: 0 -->
# Redis Data Structures

## Самая недооцененная тема Redis

Многие думают:

```txt
Redis = Key Value
```

---

Это не совсем так.

---

Redis поддерживает несколько структур данных.

---

# String

Самая популярная.

---

Пример:

```bash
SET user:1 "John"
```

---

Получение:

```bash
GET user:1
```

---

Используется для:

```txt
Cache

JSON

Tokens

Sessions
```

---

# Counter

Очень популярный кейс.

---

```bash
INCR page_views
```

---

Redis атомарно увеличит счетчик.

---

# Почему это удобно

Не нужен:

```txt
SELECT

UPDATE
```

---

Из БД.

---

# Hash

Очень популярная структура.

---

Похожа на объект.

---

Пример:

```bash
HSET user:1
 name John
 age 30
```

---

Получение:

```bash
HGET user:1 name
```

---

# Когда использовать

```txt
User Profile

Settings

Metadata
```

---

# List

Список элементов.

---

Пример:

```bash
LPUSH queue task1
```

---

Получение:

```bash
RPOP queue
```

---

Очень похоже на очередь.

---

# Queue

Популярный кейс.

---

```txt
Producer
 ↓
Redis List
 ↓
Consumer
```

---

# Set

Множество уникальных значений.

---

Пример:

```bash
SADD tags redis
SADD tags node
```

---

Повтор:

```bash
SADD tags redis
```

---

Не добавится.

---

# Когда использовать

```txt
Tags

Followers

Permissions
```

---

# Sorted Set

Самый любимый вопрос интервьюеров.

---

Каждый элемент имеет:

```txt
Score
```

---

Пример:

```bash
ZADD leaderboard
 100 user1
 200 user2
```

---

Получение рейтинга:

```bash
ZRANGE
```

---

# Где используют

```txt
Leaderboards

Ratings

Top Users

Game Scores
```

---

# Bitmap

Редко спрашивают.

---

Используется для:

```txt
Flags

Feature Tracking

Analytics
```

---

# HyperLogLog

Очень редкая тема.

---

Позволяет считать:

```txt
уникальных пользователей
```

---

С минимальной памятью.

---

# Stream

Современная структура.

---

Похожа на:

```txt
Kafka Lite
```

---

Используется для:

```txt
Event Processing

Messaging
```

---

# Частый вопрос

Какая структура используется для Leaderboard?

Ответ:

Sorted Set.

---

# Частый вопрос

Как хранить пользователя?

Ответ:

Чаще всего Hash.

---

# Частый вопрос

Как реализовать счетчик просмотров?

Ответ:

String + INCR.

---

# Частый вопрос

Как реализовать очередь?

Ответ:

List или Streams.

---

# Частый вопрос

Чем Set отличается от Sorted Set?

Ответ:

Set хранит только уникальные значения, а Sorted Set дополнительно хранит score и поддерживает сортировку.

---

# Interview Answer

Хотя Redis часто воспринимается как key-value хранилище, на самом деле он предоставляет множество специализированных структур данных: Strings, Hashes, Lists, Sets, Sorted Sets, Streams и другие. Выбор структуры зависит от характера данных и операций, которые необходимо выполнять.