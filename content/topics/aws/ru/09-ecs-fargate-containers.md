# ECS, Fargate и Containers

## Зачем вообще нужны контейнеры

Очень популярный вопрос.

---

Проблема.

---

Приложение работает у разработчика.

---

Но не работает на сервере.

---

Причины:

```txt
другая версия Node

другие библиотеки

другой Linux

другое окружение
```

---

# Docker

Решает проблему.

---

Контейнер содержит:

```txt
Application

Runtime

Dependencies

Configuration
```

---

Получаем:

```txt
одинаковое окружение
везде
```

---

# Container

Очень любят спрашивать.

---

Контейнер:

```txt
изолированный процесс
```

---

Важно.

---

Контейнер:

```txt
НЕ виртуальная машина
```

---

# VM vs Container

VM:

```txt
OS
+
Kernel
+
Application
```

---

Container:

```txt
Application
+
Dependencies
```

---

Использует:

```txt
общий kernel
```

---

Поэтому контейнеры легче.

---

# ECS

Elastic Container Service.

---

Оркестратор контейнеров AWS.

---

Управляет:

```txt
запуском

обновлением

масштабированием

мониторингом
```

---

Контейнеров.

---

# ECS Cluster

Группа ресурсов.

---

Внутри:

```txt
Services

Tasks
```

---

# Task

Очень популярный вопрос.

---

Task:

```txt
запущенный контейнер
```

---

Условно:

```txt
Docker Container
```

---

В ECS.

---

# Task Definition

Шаблон запуска.

---

Содержит:

```txt
image

cpu

memory

env variables

ports
```

---

# Service

Управляет количеством задач.

---

Например:

```txt
3 контейнера
```

---

Если один упал:

```txt
ECS создаст новый
```

---

# ECS на EC2

Старый подход.

---

Мы сами управляем:

```txt
виртуальными машинами
```

---

Схема:

```txt
ECS
 ↓
EC2
 ↓
Containers
```

---

# Недостаток

Нужно управлять:

```txt
EC2

обновлениями

масштабированием
```

---

# Fargate

Очень популярный вопрос.

---

Serverless контейнеры AWS.

---

Схема:

```txt
ECS
 ↓
Fargate
 ↓
Containers
```

---

Без EC2.

---

# Что делает AWS

Управляет:

```txt
servers

capacity

patching

scaling
```

---

# Что делаем мы

Только:

```txt
deploy container
```

---

# Почему Fargate популярен

Получаем:

```txt
контейнеры

без управления серверами
```

---

# ECS vs Fargate

Очень любят спрашивать.

---

ECS + EC2:

```txt
дешевле

больше контроля
```

---

Fargate:

```txt
проще

меньше DevOps
```

---

# Lambda vs Fargate

Самый популярный вопрос.

---

Lambda:

```txt
короткие задачи

event driven

serverless
```

---

Fargate:

```txt
долгоживущие приложения

REST API

WebSocket

Background Workers
```

---

# Когда Lambda плохой выбор

Например:

```txt
NestJS API

долгие соединения

очень высокая нагрузка
```

---

Часто лучше:

```txt
ECS/Fargate
```

---

# Когда Lambda хороший выбор

```txt
File Processing

Notifications

Cron Jobs

Small APIs
```

---

# Load Balancer

Очень важная тема.

---

Перед ECS часто ставят:

```txt
ALB
```

---

Application Load Balancer.

---

Flow:

```txt
User
 ↓
ALB
 ↓
Task 1

Task 2

Task 3
```

---

# Auto Scaling

Очень любят спрашивать.

---

Например:

```txt
CPU > 70%
```

---

ECS запускает:

```txt
новые контейнеры
```

---

# Deployment

Обычно:

```txt
Docker Build
 ↓
ECR
 ↓
ECS Deploy
```

---

# ECR

Elastic Container Registry.

---

Docker Registry AWS.

---

Хранит:

```txt
Docker Images
```

---

# Частый вопрос

Что такое ECS?

Ответ:

Сервис оркестрации контейнеров AWS.

---

# Частый вопрос

Что такое Fargate?

Ответ:

Serverless режим запуска контейнеров без управления EC2.

---

# Частый вопрос

Когда выбрать Lambda, а когда Fargate?

Ответ:

Lambda подходит для событийных коротких задач. Fargate лучше для долгоживущих API и контейнерных приложений.

---

# Interview Answer

ECS является сервисом оркестрации контейнеров AWS. Fargate позволяет запускать контейнеры без управления серверами, предоставляя serverless модель для Docker-приложений. Для большинства современных backend API на NestJS или Express часто используют ECS Fargate вместе с Application Load Balancer.