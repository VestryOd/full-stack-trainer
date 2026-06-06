<!-- verified: 2026-06-05, corrections: 0 -->
# Security Fundamentals

## Самая важная тема

Большинство атак возникают не из-за сложных хакеров.

---

А из-за:

```txt
неправильной архитектуры
```

---

# Что такое Security

Защита:

```txt
данных

пользователей

системы
```

---

# CIA Triad

Очень любят спрашивать.

---

Три основных свойства безопасности.

---

# Confidentiality

Конфиденциальность.

---

Доступ только тем,
кому разрешено.

---

Примеры:

```txt
JWT

Passwords

Encryption

Roles
```

---

# Integrity

Целостность.

---

Данные не должны быть изменены
неавторизованным пользователем.

---

Пример:

```txt
цифровая подпись

JWT Signature
```

---

# Availability

Доступность.

---

Система должна работать.

---

Пример угроз:

```txt
DDoS

Server Crash

Resource Exhaustion
```

---

# Authentication

Кто ты?

---

Пример:

```txt
Login + Password

JWT

OAuth
```

---

# Authorization

Что тебе можно?

---

Пример:

```txt
Admin

User

Manager
```

---

# Пример

Пользователь вошел.

---

Authentication:

```txt
подтвердили личность
```

---

Authorization:

```txt
разрешили удалять пользователей
```

---

# Principle of Least Privilege

Очень популярный вопрос.

---

Пользователь должен иметь:

```txt
минимально необходимые права
```

---

Плохо:

```txt
admin всем
```

---

Хорошо:

```txt
только нужные permissions
```

---

# Attack Surface

Поверхность атаки.

---

Все точки входа:

```txt
API

Forms

Upload

Admin Panel

WebSockets
```

---

Чем больше поверхность:

```txt
тем больше рисков
```

---

# Defense in Depth

Очень популярная концепция.

---

Не полагаться на:

```txt
одну защиту
```

---

Пример:

```txt
JWT
+
Role Check
+
Validation
+
Rate Limiting
```

---

# Security Through Obscurity

Антипаттерн.

---

Плохо:

```txt
никто не узнает URL
```

---

Хорошо:

```txt
реальная авторизация
```

---

# HTTPS

Очень любят спрашивать.

---

HTTP:

```txt
трафик открыт
```

---

HTTPS:

```txt
TLS шифрование
```

---

# Что защищает HTTPS

```txt
Cookies

JWT

Passwords

Personal Data
```

---

# Частый вопрос

Что такое CIA?

Ответ:

Confidentiality, Integrity, Availability.

---

# Частый вопрос

Почему HTTPS обязателен?

Ответ:

Без HTTPS любой трафик может быть перехвачен и прочитан.

---

# Interview Answer

Основой информационной безопасности считается CIA Triad: Confidentiality, Integrity и Availability. Любая система должна обеспечивать конфиденциальность данных, защиту от несанкционированного изменения и доступность сервиса для пользователей.