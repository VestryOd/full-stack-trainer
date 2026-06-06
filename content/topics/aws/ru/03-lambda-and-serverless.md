<!-- verified: 2026-06-05, corrections: 0 -->
# Lambda и Serverless

## Что такое AWS Lambda

Очень популярный вопрос.

---

Lambda — сервис выполнения кода
без управления серверами.

---

Загружаем:

```txt
код
```

---

AWS предоставляет:

```txt
серверы
масштабирование
мониторинг
инфраструктуру
```

---

# Традиционный подход

```txt
Application
 ↓
EC2
 ↓
Linux
 ↓
Monitoring
 ↓
Scaling
```

---

Мы отвечаем за всё.

---

# Lambda

```txt
Application
 ↓
Lambda
```

---

AWS отвечает за остальное.

---

# Почему называется Serverless

Очень любят спрашивать.

---

Серверы существуют.

---

Но:

```txt
разработчик ими не управляет
```

---

Отсюда:

```txt
Serverless
```

---

# Event Driven

Главная идея Lambda.

---

Lambda не работает постоянно.

---

Она запускается:

```txt
по событию
```

---

# Примеры событий

```txt
HTTP Request

S3 Upload

SQS Message

SNS Event

CloudWatch Event
```

---

# Пример

```txt
File Uploaded
 ↓
S3 Event
 ↓
Lambda
 ↓
Image Resize
```

---

# Lambda Handler

Node.js пример.

---

```ts
export const handler =
 async (event) => {

  return {
   statusCode: 200
  };
 };
```

---

# Event

Содержит данные события.

---

Например:

```txt
request
headers
query params
SQS message
```

---

Зависит от источника.

---

# Execution Environment

Очень популярный вопрос.

---

Lambda работает внутри:

```txt
изолированного runtime
```

---

AWS создает контейнер.

---

Запускает код.

---

Возвращает результат.

---

# Cold Start

Самый популярный вопрос по Lambda.

---

Что происходит.

---

Запрос пришел.

---

Но контейнера еще нет.

---

AWS должен:

```txt
создать runtime

загрузить код

инициализировать зависимости
```

---

Это занимает время.

---

Получаем:

```txt
Cold Start
```

---

# Cold Start Flow

```txt
Request
 ↓
Container Creation
 ↓
Initialization
 ↓
Handler Execution
```

---

# Warm Start

После первого вызова.

---

Контейнер уже существует.

---

Получаем:

```txt
Warm Start
```

---

Гораздо быстрее.

---

# Что влияет на Cold Start

Очень любят спрашивать.

---

Размер:

```txt
bundle
dependencies
runtime
```

---

Например:

```txt
NestJS
```

обычно стартует медленнее.

---

Чем:

```txt
простая Node Lambda
```

---

# Как уменьшить Cold Start

```txt
меньше bundle

tree shaking

esbuild

provisioned concurrency
```

---

# Stateless

Очень важная тема.

---

Lambda должна считаться:

```txt
stateless
```

---

Нельзя рассчитывать:

```txt
что контейнер сохранится
```

---

# Масштабирование

Очень сильная сторона Lambda.

---

```txt
1 запрос
```

---

Один контейнер.

---

```txt
1000 запросов
```

---

AWS может создать:

```txt
1000 контейнеров
```

---

Автоматически.

---

# Ограничения

Очень любят спрашивать.

---

Lambda не подходит для:

```txt
долгих соединений

WebSockets (частично)

очень долгих вычислений
```

---

# Стоимость

Очень популярный вопрос.

---

Платим за:

```txt
количество вызовов

время выполнения

память
```

---

Не платим за простой.

---

# Когда Lambda подходит

```txt
API

Background Jobs

File Processing

Automation

Event Processing
```

---

# Когда не подходит

```txt
High Throughput APIs

Long Running Processes

Heavy CPU Tasks
```

---

Тогда чаще используют:

```txt
ECS

Fargate

EC2
```

---

# Частый вопрос

Что такое Cold Start?

Ответ:

Задержка первого вызова Lambda, связанная с созданием нового runtime и инициализацией приложения.

---

# Частый вопрос

Почему Lambda считается Serverless?

Ответ:

Потому что разработчик не управляет серверами, масштабированием и инфраструктурой — этим занимается AWS.

---

# Interview Answer

AWS Lambda — это serverless compute сервис, который выполняет код в ответ на события. Lambda автоматически масштабируется, оплачивается по фактическому использованию и хорошо подходит для API, фоновых задач и обработки событий. Одной из основных особенностей является Cold Start — задержка при создании нового execution environment.