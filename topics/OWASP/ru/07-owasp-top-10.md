# OWASP Top 10

## Что такое OWASP

OWASP:

```txt
Open Worldwide
Application Security Project
```

---

Самая известная организация
по безопасности веб-приложений.

---

# OWASP Top 10

Список самых распространенных
и опасных уязвимостей.

---

На интервью редко требуют
знать весь список наизусть.

---

Но нужно понимать основные пункты.

---

# A01

Broken Access Control

---

Самая опасная категория.

---

# Пример

Пользователь:

```http
GET /users/123
```

---

Меняет:

```http
GET /users/124
```

---

И получает чужие данные.

---

# Причина

Нет проверки прав доступа.

---

# Защита

```txt
RBAC

ABAC

Ownership Checks
```

---

# A02

Cryptographic Failures

---

Ошибки шифрования.

---

Примеры:

```txt
HTTP вместо HTTPS

слабые алгоритмы

пароли без bcrypt
```

---

# A03

Injection

---

Очень популярный вопрос.

---

Примеры:

```txt
SQL Injection

NoSQL Injection

Command Injection
```

---

# Защита

```txt
ORM

Parameterized Queries

Validation
```

---

# A04

Insecure Design

---

Уязвимость архитектуры.

---

Пример:

```txt
нет Rate Limiting

нет MFA

нет блокировки аккаунта
```

---

# A05

Security Misconfiguration

---

Ошибки настройки.

---

Примеры:

```txt
открытый S3 Bucket

debug mode

лишние права
```

---

# A06

Vulnerable Components

---

Уязвимые зависимости.

---

Пример:

```txt
npm package
с известной CVE
```

---

# Защита

```txt
npm audit

Dependabot

регулярные обновления
```

---

# A07

Identification and Authentication Failures

---

Ошибки аутентификации.

---

Примеры:

```txt
слабые пароли

нет MFA

небезопасные JWT
```

---

# A08

Software and Data Integrity Failures

---

Нарушение целостности.

---

Пример:

```txt
загрузка неподписанных пакетов
```

---

# A09

Security Logging and Monitoring Failures

---

Нет логирования.

---

Нет мониторинга.

---

Атака произошла.

---

Никто не заметил.

---

# A10

Server Side Request Forgery

---

SSRF.

---

Очень любят спрашивать.

---

# Идея

Сервер заставляют выполнить запрос.

---

Пример:

```http
POST /fetch-image
```

---

Пользователь передает:

```txt
http://localhost:5432
```

---

Или:

```txt
http://169.254.169.254
```

---

Сервер сам идет по адресу.

---

# Почему это опасно

Можно получить доступ:

```txt
к внутренним сервисам

metadata AWS

закрытым API
```

---

# Защита

```txt
Allow List

URL Validation

Network Restrictions
```

---

# Что реально спрашивают на интервью

Чаще всего:

```txt
Broken Access Control

XSS

CSRF

SQL Injection

JWT Security

Password Storage

SSRF
```

---

# Частый вопрос

Какая категория сейчас самая опасная?

Ответ:

Broken Access Control.

---

# Частый вопрос

Что такое SSRF?

Ответ:

Уязвимость, позволяющая злоумышленнику заставить сервер выполнять запросы к внутренним или защищенным ресурсам.

---

# Частый вопрос

Что такое Security Misconfiguration?

Ответ:

Ошибки конфигурации инфраструктуры или приложения, которые приводят к появлению уязвимостей.

---

# Interview Answer

OWASP Top 10 представляет собой список наиболее критичных уязвимостей веб-приложений. Наиболее важными для Fullstack разработчика являются Broken Access Control, Injection, Authentication Failures, Security Misconfiguration и SSRF.