# API Gateway

## Что такое API Gateway

Очень популярный вопрос.

---

API Gateway —
управляемый HTTP вход в систему.

---

Схема:

```txt
Browser
 ↓
API Gateway
 ↓
Lambda
```

---

# Зачем нужен

Можно вызвать Lambda напрямую.

---

Но API Gateway предоставляет:

```txt
Routing

Authentication

Rate Limiting

Caching

Monitoring
```

---

# Аналогия

API Gateway для микросервисов —
примерно как:

```txt
Nginx
```

---

Для обычного приложения.

---

# Основной Flow

```txt
Client
 ↓
API Gateway
 ↓
Lambda
 ↓
Response
```

---

# Endpoint

Например:

```http
GET /products
```

---

API Gateway получает запрос.

---

Передает его в Lambda.

---

Lambda возвращает ответ.

---

# Route Configuration

Пример:

```txt
GET /products

POST /products

DELETE /products
```

---

Каждый маршрут
может вызывать свою Lambda.

---

# Proxy Integration

Самый популярный режим.

---

API Gateway передает:

```txt
весь запрос
```

---

В Lambda.

---

Lambda получает:

```json
{
 headers,
 queryStringParameters,
 body
}
```

---

# Response

Lambda должна вернуть:

```ts
{
 statusCode: 200,
 body: ...
}
```

---

API Gateway превращает это:

```txt
в HTTP Response
```

---

# Authorization

Очень популярный вопрос.

---

API Gateway поддерживает:

```txt
JWT

IAM

Custom Authorizer

Cognito
```

---

# Lambda Authorizer

Часто спрашивают.

---

Схема:

```txt
Request
 ↓
Authorizer Lambda
 ↓
Allow / Deny
 ↓
Main Lambda
```

---

# Throttling

Очень важная тема.

---

Проблема:

```txt
100000 запросов
```

---

Могут перегрузить систему.

---

API Gateway позволяет:

```txt
ограничивать RPS
```

---

# Rate Limiting

Пример:

```txt
100 req/sec
```

---

Лишние запросы:

```txt
429 Too Many Requests
```

---

# Caching

API Gateway умеет кешировать ответы.

---

Например:

```txt
Product Catalog
```

---

Не всегда нужно вызывать Lambda.

---

# Monitoring

Интеграция с:

```txt
CloudWatch
```

---

Можно видеть:

```txt
Latency

Errors

Request Count
```

---

# REST API vs HTTP API

Очень любят спрашивать.

---

REST API:

```txt
старый вариант

больше возможностей

дороже
```

---

HTTP API:

```txt
быстрее

дешевле

проще
```

---

Сегодня часто выбирают:

```txt
HTTP API
```

---

# API Gateway + Lambda

Самая популярная AWS архитектура.

---

```txt
Frontend
 ↓
API Gateway
 ↓
Lambda
 ↓
Database
```

---

# Пример из Fullstack

```txt
Next.js
 ↓
API Gateway
 ↓
Lambda
 ↓
PostgreSQL
```

---

# Частый вопрос

Почему не вызывать Lambda напрямую?

Ответ:

API Gateway предоставляет маршрутизацию, авторизацию, rate limiting, кеширование и мониторинг.

---

# Частый вопрос

Что делает Lambda Authorizer?

Ответ:

Отдельная Lambda, которая проверяет права доступа и возвращает разрешение или запрет на выполнение запроса.

---

# Частый вопрос

Что такое Throttling?

Ответ:

Механизм ограничения количества запросов для защиты системы от перегрузки.

---

# Interview Answer

API Gateway является управляемым HTTP-шлюзом AWS и обычно используется перед Lambda. Он отвечает за маршрутизацию запросов, авторизацию, rate limiting, кеширование и мониторинг. В serverless архитектуре API Gateway часто выступает единой точкой входа для всех HTTP-запросов.