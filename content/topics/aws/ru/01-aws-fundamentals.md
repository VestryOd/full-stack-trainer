# AWS Fundamentals

## Что такое AWS

AWS (Amazon Web Services) —
облачная платформа Amazon.

---

Предоставляет:

```txt
Compute
Storage
Networking
Databases
Messaging
Monitoring
Security
```

---

# Главная идея облака

Вместо покупки серверов:

```txt
Купить сервер
Настроить сервер
Обслуживать сервер
Менять диски
Менять память
```

---

Получаем:

```txt
аренду ресурсов
по требованию
```

---

# Основные модели

Очень популярный вопрос.

---

# IaaS

Infrastructure as a Service.

---

AWS предоставляет:

```txt
VM
Storage
Network
```

---

Пример:

```txt
EC2
```

---

# PaaS

Platform as a Service.

---

AWS управляет инфраструктурой.

---

Мы пишем код.

---

Примеры:

```txt
Lambda
Elastic Beanstalk
```

---

# SaaS

Software as a Service.

---

Готовый продукт.

---

Примеры:

```txt
Gmail
Notion
Salesforce
```

---

# Region

Очень популярный вопрос.

---

Region:

```txt
географический регион AWS
```

---

Например:

```txt
eu-central-1
Frankfurt

eu-west-1
Ireland
```

---

# Availability Zone

AZ.

---

Внутри региона.

---

Пример:

```txt
eu-central-1a
eu-central-1b
eu-central-1c
```

---

Отдельные датацентры.

---

# Зачем AZ

Для отказоустойчивости.

---

Если один датацентр упал:

```txt
приложение продолжает работать
```

---

# Shared Responsibility Model

Очень любят спрашивать.

---

AWS отвечает за:

```txt
Physical Security
Networking
Hardware
```

---

Мы отвечаем за:

```txt
Application
Data
Users
Permissions
```

---

# Основные сервисы

Compute:

```txt
EC2
Lambda
ECS
```

---

Storage:

```txt
S3
```

---

Database:

```txt
RDS
DynamoDB
```

---

Messaging:

```txt
SQS
SNS
```

---

Security:

```txt
IAM
Secrets Manager
```

---

# Infrastructure as Code

Очень важная тема.

---

Не создавать ресурсы вручную.

---

Используем:

```txt
CloudFormation
CDK
Terraform
```

---

# AWS CDK

Судя по твоему опыту,
очень вероятный вопрос.

---

CDK позволяет описывать инфраструктуру:

```ts
new Bucket(...)
new Function(...)
new Distribution(...)
```

---

На TypeScript.

---

Затем генерируется:

```txt
CloudFormation
```

---

# Частый вопрос

Что такое AWS Region?

Ответ:

Независимый географический регион AWS, содержащий несколько Availability Zones.

---

# Частый вопрос

Что такое Availability Zone?

Ответ:

Изолированный датацентр внутри региона, используемый для отказоустойчивости.

---

# Interview Answer

AWS — это облачная платформа, предоставляющая вычислительные ресурсы, хранилища, базы данных, очереди сообщений и инструменты безопасности. Основой архитектуры AWS являются Regions и Availability Zones, обеспечивающие масштабируемость и отказоустойчивость.