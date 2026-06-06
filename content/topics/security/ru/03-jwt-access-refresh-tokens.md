<!-- verified: 2026-06-05, corrections: 0 -->
# JWT, Access Token и Refresh Token

## Самая популярная тема Fullstack интервью

Почти гарантированно спрашивают.

---

# Что такое JWT

JSON Web Token.

---

Содержит:

```txt
Header

Payload

Signature
```

---

# Header

Например:

```json
{
 "alg":"HS256",
 "typ":"JWT"
}
```

---

# Payload

Содержит данные.

---

Например:

```json
{
 "userId":"123",
 "role":"admin"
}
```

---

# Очень важно

Payload:

```txt
не зашифрован
```

---

Только подписан.

---

Любой может его прочитать.

---

# Signature

Позволяет проверить:

```txt
токен не подменили
```

---

# Почему JWT популярен

Stateless.

---

Сервер не хранит сессии.

---

# Access Token

Короткоживущий токен.

---

Например:

```txt
15 минут
```

---

Используется в API запросах.

---

# Refresh Token

Долгоживущий токен.

---

Например:

```txt
30 дней
```

---

Используется для получения нового Access Token.

---

# Flow

```txt
Login
 ↓
Access Token
Refresh Token
```

---

Через 15 минут:

```txt
Access Token Expired
```

---

Используем:

```txt
Refresh Token
```

---

Получаем новый Access Token.

---

# Где хранить Access Token

Очень любят спрашивать.

---

Наиболее безопасно:

```txt
Memory
```

---

Допустимо:

```txt
HttpOnly Cookie
```

---

Плохо:

```txt
localStorage
```

---

Из-за XSS.

---

# Где хранить Refresh Token

Чаще всего:

```txt
HttpOnly Cookie
```

---

# Почему HttpOnly

JavaScript не может прочитать cookie.

---

Это уменьшает последствия XSS.

---

# JWT Logout Problem

Очень популярный Senior вопрос.

---

JWT stateless.

---

Если токен выдан:

```txt
он валиден
до истечения срока
```

---

Даже если пользователь нажал Logout.

---

# Решения

```txt
Short Access Token

Refresh Rotation

Blacklist
```

---

# Refresh Rotation

После обновления:

```txt
старый Refresh Token
аннулируется
```

---

# Частый вопрос

Можно ли хранить пароль в JWT?

Ответ:

Нет.

---

# Частый вопрос

Зашифрован ли JWT?

Ответ:

Нет.

---

Подписан, но не зашифрован.

---

# Частый вопрос

Почему localStorage опасен?

Ответ:

При XSS злоумышленник может прочитать токен.

---

# Interview Answer

JWT состоит из Header, Payload и Signature. Обычно используется схема Access Token + Refresh Token. Access Token имеет короткий срок жизни и используется для доступа к API, а Refresh Token позволяет получать новые Access Token без повторного логина.