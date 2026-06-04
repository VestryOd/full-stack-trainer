# IAM и Security

## Что такое IAM

IAM расшифровывается как:

```txt
Identity and Access Management
```

---

Это система:

```txt
Authentication
Authorization
```

в AWS.

---

# Очень важно

Authentication:

```txt
Кто ты?
```

---

Authorization:

```txt
Что тебе можно?
```

---

IAM занимается обоими.

---

# Основная задача IAM

Определить:

```txt
Кто

Что

С чем

Может делать
```

---

# Основные сущности

```txt
User

Group

Role

Policy
```

---

# User

Физический пользователь.

---

Например:

```txt
Maxim
Alice
Admin
```

---

Пользователь получает:

```txt
Login
Password
Access Keys
```

---

# Group

Группа пользователей.

---

Например:

```txt
Developers

Admins

QA
```

---

Права назначаются группе.

---

# Policy

Самая важная сущность.

---

Policy определяет:

```txt
что разрешено
```

---

Пример:

```json
{
 "Effect": "Allow",
 "Action": "s3:GetObject",
 "Resource": "*"
}
```

---

Что означает:

```txt
можно читать объекты S3
```

---

# Action

Очень любят спрашивать.

---

Примеры:

```txt
s3:GetObject

s3:PutObject

lambda:InvokeFunction

dynamodb:GetItem
```

---

# Resource

К чему применяется право.

---

Например:

```txt
конкретный bucket

конкретная lambda
```

---

# Effect

```txt
Allow
```

или

```txt
Deny
```

---

# Principle of Least Privilege

Самый популярный вопрос.

---

Принцип:

```txt
минимально необходимые права
```

---

Плохо:

```txt
AdministratorAccess
```

---

Для всех.

---

Хорошо:

```txt
только нужные permissions
```

---

# Role

Очень важная тема.

---

Role — это набор прав,
который может временно принять сервис.

---

# Почему Role важнее User

Очень любят спрашивать.

---

Например:

```txt
Lambda
```

не является пользователем.

---

Но ей нужен доступ:

```txt
S3
DynamoDB
SQS
```

---

Используем:

```txt
IAM Role
```

---

# Lambda Role

Схема:

```txt
Lambda
 ↓
Assume Role
 ↓
S3 Access
```

---

Без Access Keys.

---

# Почему это безопаснее

Не нужно хранить:

```txt
AWS_ACCESS_KEY

AWS_SECRET_KEY
```

---

В коде.

---

# Temporary Credentials

Очень популярный вопрос.

---

Когда сервис принимает роль.

---

AWS выдает:

```txt
временные credentials
```

---

На ограниченное время.

---

# Trust Policy

Очень интересная тема.

---

Определяет:

```txt
кто может использовать роль
```

---

Например:

```txt
Lambda Service
```

---

Или:

```txt
EC2 Service
```

---

# Permission Policy

Определяет:

```txt
что можно делать
```

---

# Flow

```txt
Lambda
 ↓
Role
 ↓
Policy
 ↓
S3
```

---

# Secrets

Очень популярный вопрос.

---

Нельзя хранить:

```txt
passwords

tokens

api keys
```

---

В коде.

---

Используют:

```txt
Secrets Manager

Parameter Store
```

---

# Частый вопрос

Как Lambda получает доступ к S3?

Ответ:

Через IAM Role, назначенную функции Lambda. Роль содержит Policy с разрешением на доступ к нужному Bucket.

---

# Частый вопрос

Что такое IAM Role?

Ответ:

Набор разрешений, который может временно принять AWS сервис или пользователь.

---

# Частый вопрос

Почему IAM Role лучше Access Keys?

Ответ:

Не требует хранения секретов и использует временные credentials.

---

# Interview Answer

IAM отвечает за управление доступом в AWS. Основными сущностями являются Users, Roles и Policies. В production системах сервисы обычно используют IAM Roles вместо Access Keys, что позволяет безопасно получать временные разрешения на доступ к ресурсам AWS.