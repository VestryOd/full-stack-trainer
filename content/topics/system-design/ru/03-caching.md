# Caching

## Зачем нужен Cache

Самый популярный System Design вопрос.

---

Без кеша:

```txt
Client
 ↓
API
 ↓
Database
```

---

Каждый запрос идет в БД.

---

# Проблема

Представим:

```txt
10000 запросов/сек
```

---

На главную страницу.

---

Все идут в PostgreSQL.

---

Получаем:

```txt
узкое место
```

---

# Решение

Добавляем Cache Layer.

---

```txt
Client
 ↓
API
 ↓
Redis
 ↓
Database
```

---

# Cache Hit

Данные найдены в кеше.

---

```txt
Redis
 ↓
Response
```

---

БД не участвует.

---

# Cache Miss

Данных нет.

---

```txt
Redis
 ↓
Database
 ↓
Redis
 ↓
Response
```

---

# Что обычно кешируют

```txt
Profiles

Products

Catalogs

Settings

Popular Posts
```

---

# Что обычно НЕ кешируют

```txt
Bank Balances

Payments

Critical Transactions
```

---

# Cache Aside

Самый популярный паттерн.

---

Flow:

```txt
Read Redis

Miss

Read DB

Write Redis
```

---

# Write Through

При записи обновляем:

```txt
Database
+
Cache
```

---

# Cache Invalidation

Самая сложная проблема кеширования.

---

Пользователь изменил данные.

---

Redis хранит старые данные.

---

# Решение

После UPDATE:

```txt
DEL cache_key
```

---

или:

```txt
SET new value
```

---

# TTL

Time To Live.

---

Например:

```txt
5 минут
```

---

После чего запись удаляется.

---

# Cache Stampede

Очень популярный вопрос.

---

Проблема:

```txt
TTL истек

10000 запросов
```

---

Все идут в БД.

---

# Решение

```txt
Mutex

Random TTL

Warm Cache
```

---

# Multi-Level Cache

Продвинутый уровень.

---

```txt
Browser Cache

CDN Cache

Redis Cache

Database
```

---

# Частый вопрос

Когда Redis помогает больше всего?

Ответ:

Когда чтений намного больше, чем записей.

---

# Interview Answer

Кеширование уменьшает нагрузку на базу данных и снижает latency. Наиболее популярным паттерном является Cache Aside с использованием Redis и TTL.