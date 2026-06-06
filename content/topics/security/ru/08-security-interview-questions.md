<!-- verified: 2026-06-05, corrections: 0 -->
# Security Interview Questions (Fullstack / Senior)

---

# 1. Что такое Authentication?

Проверка личности пользователя.

---

Примеры:

```txt
Password

JWT

OAuth

SSO
```

---

# 2. Что такое Authorization?

Проверка прав пользователя.

---

Определяет:

```txt
что пользователь может делать
```

---

# 3. Чем Authentication отличается от Authorization?

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

# 4. Что такое RBAC?

Role Based Access Control.

---

Доступ определяется ролью.

---

Пример:

```txt
Admin

Manager

User
```

---

# 5. Что такое ABAC?

Attribute Based Access Control.

---

Доступ определяется атрибутами.

---

Например:

```txt
department

owner

country
```

---

# 6. Что такое JWT?

JSON Web Token.

---

Содержит:

```txt
Header

Payload

Signature
```

---

# 7. Зашифрован ли JWT?

Нет.

---

JWT подписан,
но не зашифрован.

---

# 8. Можно ли хранить пароль в JWT?

Нет.

---

JWT может прочитать любой.

---

# 9. Что такое Access Token?

Короткоживущий токен доступа.

---

Обычно:

```txt
5–30 минут
```

---

# 10. Что такое Refresh Token?

Долгоживущий токен
для получения нового Access Token.

---

# 11. Где хранить Access Token?

Лучший вариант:

```txt
Memory
```

---

Допустимый:

```txt
HttpOnly Cookie
```

---

# 12. Где хранить Refresh Token?

Чаще всего:

```txt
HttpOnly
Secure
SameSite Cookie
```

---

# 13. Почему localStorage опасен?

При XSS злоумышленник может прочитать токен.

---

# 14. Что такое XSS?

Cross Site Scripting.

---

Выполнение вредоносного JavaScript на сайте.

---

# 15. Какие типы XSS существуют?

```txt
Stored

Reflected

DOM
```

---

# 16. Что такое Stored XSS?

Скрипт сохраняется в БД.

---

Самый опасный вариант.

---

# 17. Что такое DOM XSS?

Уязвимость возникает на клиенте.

---

Часто через:

```js
innerHTML
```

---

# 18. Как защититься от XSS?

```txt
Escaping

React JSX

CSP

HttpOnly Cookies
```

---

# 19. Что такое CSP?

Content Security Policy.

---

Ограничивает выполнение скриптов.

---

# 20. Что такое CSRF?

Cross Site Request Forgery.

---

Заставляет браузер отправить запрос
от имени пользователя.

---

# 21. Почему JWT в Authorization Header снижает риск CSRF?

Браузер автоматически не добавляет:

```txt
Authorization Header
```

---

# 22. Как защититься от CSRF?

```txt
CSRF Token

SameSite Cookie

Authorization Header
```

---

# 23. Что такое SameSite Cookie?

Политика браузера,
контролирующая отправку cookie
между сайтами.

---

# 24. Что такое CORS?

Cross-Origin Resource Sharing.

---

Политика браузера
для междоменных запросов.

---

# 25. Защищает ли CORS сервер?

Нет.

---

Только браузер.

---

# 26. Что такое Preflight Request?

OPTIONS запрос,
который браузер отправляет заранее.

---

# 27. Что такое SQL Injection?

Влияние пользователя на SQL запрос.

---

# 28. Пример SQL Injection?

```sql
' OR 1=1 --
```

---

# 29. Как защититься от SQL Injection?

```txt
Parameterized Queries

ORM

Validation
```

---

# 30. Защищает ли Prisma от SQL Injection?

В большинстве случаев да.

---

Но не:

```txt
$queryRawUnsafe()
```

---

# 31. Что такое NoSQL Injection?

Аналог SQL Injection
для NoSQL баз данных.

---

# 32. Что такое Command Injection?

Влияние пользователя
на системные команды.

---

# 33. Что такое Input Validation?

Проверка корректности данных.

---

# 34. Что такое Sanitization?

Удаление опасного содержимого.

---

# 35. Чем Validation отличается от Sanitization?

Validation:

```txt
данные корректны?
```

---

Sanitization:

```txt
данные безопасны?
```

---

# 36. Почему нельзя доверять Frontend Validation?

Потому что запрос можно отправить напрямую.

---

# 37. Что такое Mass Assignment?

Передача полей,
которые пользователь не должен менять.

---

# 38. Как защититься от Mass Assignment?

```txt
DTO

Whitelist

Field Mapping
```

---

# 39. Что такое HTTPS?

HTTP поверх TLS.

---

# 40. Что дает HTTPS?

```txt
шифрование

целостность

подлинность сервера
```

---

# 41. Что такое MITM?

Man In The Middle.

---

Перехват трафика между сторонами.

---

# 42. Что такое Password Hashing?

Хранение хеша вместо пароля.

---

# 43. Чем Hashing отличается от Encryption?

Hash:

```txt
необратим
```

---

Encryption:

```txt
обратима
```

---

# 44. Почему нельзя хранить пароли в открытом виде?

Утечка БД раскроет все пароли.

---

# 45. Почему SHA256 плохо подходит для паролей?

Слишком быстрый.

---

Легко брутфорсить.

---

# 46. Что такое bcrypt?

Алгоритм хеширования паролей.

---

Специально медленный.

---

# 47. Что такое Argon2?

Современный алгоритм хеширования паролей.

---

Считается лучшей практикой.

---

# 48. Что такое Salt?

Случайная строка,
добавляемая перед хешированием.

---

# 49. Зачем нужен Salt?

Защищает от:

```txt
Rainbow Tables
```

---

# 50. Что такое Rainbow Table?

Предвычисленная таблица:

```txt
password → hash
```

---

# 51. Что такое Secret?

Конфиденциальные данные приложения.

---

Например:

```txt
JWT Secret

DB Password

API Keys
```

---

# 52. Где хранить секреты?

Production:

```txt
AWS Secrets Manager

Vault

Parameter Store
```

---

# 53. Что такое Secret Rotation?

Периодическая смена секретов.

---

# 54. Что такое OWASP?

Open Worldwide Application Security Project.

---

# 55. Что такое OWASP Top 10?

Список самых опасных веб-уязвимостей.

---

# 56. Что такое Broken Access Control?

Неправильная проверка прав доступа.

---

# 57. Почему Broken Access Control опасен?

Позволяет получать доступ
к чужим данным.

---

# 58. Что такое Security Misconfiguration?

Ошибки настройки системы.

---

Пример:

```txt
открытый S3 Bucket
```

---

# 59. Что такое SSRF?

Server Side Request Forgery.

---

Заставляет сервер выполнять запросы
к внутренним ресурсам.

---

# 60. Почему SSRF опасен в AWS?

Можно получить доступ к:

```txt
Metadata Service

Internal APIs
```

---

# 61. Что такое Rate Limiting?

Ограничение количества запросов.

---

# 62. Зачем нужен Rate Limiting?

Защита от:

```txt
Brute Force

DDoS

Abuse
```

---

# 63. Как реализовать Rate Limiting?

Часто через:

```txt
Redis

INCR

TTL
```

---

# 64. Что такое Principle of Least Privilege?

Минимально необходимые права.

---

# 65. Что такое Defense in Depth?

Несколько уровней защиты.

---

Например:

```txt
HTTPS

JWT

RBAC

Validation

Rate Limiting
```

---

# 66. Что такое Security Headers?

Дополнительные HTTP заголовки защиты.

---

Примеры:

```txt
CSP

HSTS

X-Frame-Options
```

---

# 67. Что такое HSTS?

HTTP Strict Transport Security.

---

Заставляет браузер использовать HTTPS.

---

# 68. Что такое X-Frame-Options?

Защита от Clickjacking.

---

# 69. Что такое Clickjacking?

Обман пользователя через скрытые iframe.

---

# 70. Самый популярный Senior вопрос

Как бы вы защитили современное Next.js + NestJS приложение?

Ответ:

```txt
HTTPS

Access Token + Refresh Token

HttpOnly Cookies

RBAC

DTO Validation

Sanitization

Parameterized Queries

CSP

Rate Limiting

Secrets Manager

Password Hashing (Argon2/Bcrypt)
```

---

# 71. Самый сильный Senior ответ

Какие 3 самые опасные веб-уязвимости сегодня?

Ответ:

```txt
Broken Access Control

XSS

Injection
```

Потому что именно они чаще всего приводят к компрометации данных и захвату учетных записей пользователей.