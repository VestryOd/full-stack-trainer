<!-- verified: 2026-06-05, corrections: 0 -->
# Security: Вопросы для интервью

Вопросы сгруппированы тематически. Внутри каждой группы — полный senior-ответ + типичные follow-up вопросы.

---

## Группа 1: Основы безопасности

### Что такое CIA Triad и почему это важно?

CIA Triad — три фундаментальных свойства безопасности любой системы:

**Confidentiality** (конфиденциальность): данные доступны только авторизованным. Угрозы: перехват трафика (MITM), SQL Injection, утечка токенов. Меры: HTTPS, шифрование, RBAC.

**Integrity** (целостность): данные не могут быть изменены незаметно. Угрозы: CSRF (действие от имени пользователя), SQL Injection (изменение данных), tampering JWT без подписи. Меры: HMAC, digital signatures, JWT Signature.

**Availability** (доступность): система доступна для авторизованных пользователей. Угрозы: DDoS, regex DoS, resource exhaustion. Меры: Rate Limiting, Circuit Breaker.

```txt
Типичные follow-up:

Q: "Что нарушает DDoS?"
A: Availability. DDoS исчерпывает ресурсы сервера → легитимные
   пользователи не могут получить доступ.

Q: "Что нарушает перехват JWT?"
A: Confidentiality. Злоумышленник получает доступ к данным,
   которые предназначались только авторизованному пользователю.

Q: "Что нарушает CSRF?"
A: Integrity. Действие выполняется от имени пользователя без
   его ведома → данные изменены неавторизованно.
```

### Что такое Defense in Depth?

Принцип многоуровневой защиты: если один уровень пробит, следующий должен остановить атаку. Нельзя полагаться на единственную защиту.

Пример для API endpoint: HTTPS (шифрование) → Rate Limiting (brute force) → JWT Validation (аутентификация) → Role Check (авторизация) → Zod/ValidationPipe (валидация) → Parameterized Query (injection) → Output Encoding (XSS) → Security Headers (clickjacking).

```txt
Типичные follow-up:

Q: "Что такое Security Through Obscurity? Это работает?"
A: Попытка обезопасить систему скрытием информации (секретный URL,
   непубличная документация). НЕ является защитой: злоумышленник
   находит endpoints через brute force, сканирование, source code.
   Реальная защита: авторизация на endpoint, независимо от его
   "секретности". Принцип Kerckhoffs: система безопасна если
   секрет — только ключ, а не алгоритм.
```

---

## Группа 2: JWT, Authentication и Tokens

### Опишите структуру JWT и что происходит если payload изменить

JWT — три base64url-encoded части: `header.payload.signature`.

- **Header**: алгоритм (`HS256`) и тип
- **Payload**: claims (sub, role, exp, iat, jti) — НЕ зашифрован, любой может прочитать
- **Signature**: HMAC(header + payload, secret) — гарантирует целостность

Если payload изменить (например, `role: "user" → "admin"`): signature станет невалидной при верификации. Сервер должен отклонить токен с ошибкой. Исключение: атака `alg:none` — если библиотека принимает algorithm=none, подпись не проверяется. Защита: `jwt.verify(token, secret, { algorithms: ['HS256'] })` — явное указание.

```txt
Типичные follow-up:

Q: "Можно ли класть пароль в JWT?"
A: Нет. Payload только подписан, но не зашифрован. base64decode
   payload без ключа → любой видит содержимое.

Q: "Чем HS256 отличается от RS256?"
A: HS256 — симметричный (один secret для подписи и верификации).
   RS256 — асимметричный (private key подписывает, public key
   верифицирует). В microservices RS256 предпочтительнее: каждый
   сервис верифицирует через public key, не зная private key.
```

### Объясните схему Access Token + Refresh Token и проблему logout

**Зачем два токена**: один long-lived JWT при краже — катастрофа (30 дней). Два токена: Access (15 мин, stateless) + Refresh (30 дней, хранится в БД).

**Flow**: Login → AccessToken (в JSON response) + RefreshToken (HttpOnly Cookie). Через 15 мин: POST /auth/refresh → новый AccessToken. Logout: удалить RefreshToken из БД + clearCookie.

**JWT Logout Problem**: Access Token stateless — нельзя "отозвать" до истечения TTL. Решения: (1) короткий TTL (15 мин), (2) Redis blacklist по jti, (3) Refresh Token Rotation (каждый refresh → новый refresh token, старый аннулируется).

```txt
Типичные follow-up:

Q: "Где безопасно хранить Access Token?"
A: Memory (JS variable) — защищён от XSS, теряется при refresh страницы.
   HttpOnly Cookie — защищён от XSS, CSRF риск (нужен sameSite=strict).
   localStorage — НЕБЕЗОПАСНО: XSS может украсть.

Q: "Как обнаружить кражу Refresh Token?"
A: Refresh Token Rotation: при каждом refresh выдаётся новый refresh
   token, старый удаляется из БД. Если злоумышленник использует украденный
   токен → попытка reuse уже использованного токена → alert + revoke
   ВСЕХ refresh tokens пользователя.

Q: "Что такое OAuth 2.0 и чем он отличается от аутентификации?"
A: OAuth 2.0 — протокол делегированной АВТОРИЗАЦИИ (доступ к ресурсам).
   Для аутентификации нужен OpenID Connect (слой поверх OAuth 2.0,
   добавляет id_token с identity данными). "Войти через Google" =
   OpenID Connect, не чистый OAuth 2.0.
```

---

## Группа 3: XSS, CSRF и CORS

### Объясните XSS, CSRF и чем они отличаются

**XSS** (Cross-Site Scripting): злоумышленник внедряет JavaScript в страницы, браузер жертвы выполняет его в контексте вашего сайта. Три типа: Stored (в БД), Reflected (в URL), DOM-based (в client JS). Результат: кража токенов из localStorage/cookie, keylogger, действия от имени пользователя.

**CSRF** (Cross-Site Request Forgery): браузер жертвы (уже аутентифицированный) отправляет запрос к вашему сайту с evil.com. Браузер автоматически прикладывает cookie для вашего домена. Сервер не отличает от легитимного запроса.

**Ключевое отличие**: XSS — код выполняется с вашего origin. CSRF — запрос отправляется с чужого origin.

```txt
Типичные follow-up:

Q: "Почему JWT в Authorization header защищает от CSRF?"
A: Браузер автоматически отправляет cookie для домена, но НЕ
   добавляет кастомные заголовки (Authorization) на кросс-доменные
   запросы. Evil.com не может получить JWT из memory/localStorage
   (same-origin policy) → не может поставить заголовок.

Q: "Защищает ли HttpOnly Cookie от XSS?"
A: Частично. HttpOnly делает cookie недоступным для JS.read.
   Но XSS всё равно может отправлять запросы с вашего origin
   (fetch, XMLHttpRequest) → cookie автоматически прикладывается.
   XSS + сессионная аутентификация → action hijacking.
   Полная защита: HttpOnly + CSP (предотвращает XSS).

Q: "Что такое CORS и защищает ли он сервер?"
A: CORS — политика браузера, контролирующая кросс-доменные запросы
   fetch/XHR. НЕ защищает сервер: curl/Postman/backend полностью
   обходят CORS. Защищает только браузерный контекст пользователя.
   Сервер защищают аутентификация и авторизация.

Q: "Когда браузер отправляет Preflight OPTIONS?"
A: Перед "non-simple" запросом: метод DELETE/PUT/PATCH, или
   заголовок Authorization/Content-Type: application/json, или
   любой кастомный заголовок. Preflight спрашивает сервер
   "разрешён ли этот запрос?" до отправки основного.
```

---

## Группа 4: Injection и Input Validation

### Что такое SQL Injection и как защититься?

SQL Injection: пользовательский ввод конкатенируется в SQL → злоумышленник изменяет логику запроса. Пример: `email = "' OR '1'='1' --"` → обход аутентификации. UNION attack → утечка всей таблицы. При правах DROP → удаление данных.

Единственная правильная защита: **parameterized queries** (данные никогда не становятся частью SQL-текста). ORM (Prisma, TypeORM) параметризует автоматически для стандартных методов, но `$queryRawUnsafe` / `query()` с конкатенацией — уязвимы.

```txt
Типичные follow-up:

Q: "Что такое Command Injection?"
A: Аналог SQL Injection для shell команд. Если ввод пользователя
   передаётся в exec() → злоумышленник вставляет ; rm -rf /
   Защита: execFile() вместо exec() (не интерпретирует metacharacters),
   или избегать shell полностью.

Q: "Что такое Mass Assignment?"
A: Клиент передаёт поля которые не должен менять (например role:'admin')
   и сервер слепо применяет req.body к модели. Защита: явный whitelist
   через DTO/Zod schema — принимать только объявленные поля.

Q: "Чем Validation отличается от Sanitization?"
A: Validation: данные корректны? (reject неправильные — 400).
   Sanitization: данные безопасны? (трансформировать для контекста).
   Для SQL — только parameterized queries, не ручное экранирование.
   Для HTML — DOMPurify при необходимости рендерить HTML.
   Оба нужны в разных контекстах.
```

---

## Группа 5: Пароли и Секреты

### Как правильно хранить пароли и почему нельзя шифровать?

**Нельзя шифровать**: шифрование обратимо. При утечке ключа → все пароли раскрыты. Для проверки пароля при логине шифрование не нужно — достаточно сравнить хеши.

**Нельзя SHA-256**: разработан для скорости. GPU вычисляет 23 млрд SHA-256/сек → brute force словаря 10 млн паролей за ~0.01 сек.

**bcrypt**: специально медленный (cost=12 → ~400ms), встраивает соль в хеш автоматически, adaptive (при росте мощности CPU — повышать cost).

**Argon2id**: победитель Password Hashing Competition. Memory-hard (64MB RAM) → GPU атаки нивелированы. Рекомендован для новых проектов.

```txt
Типичные follow-up:

Q: "Что такое Rainbow Table и как bcrypt защищает?"
A: Rainbow Table — предвычисленная таблица {password → hash}.
   bcrypt: уникальная соль per-password → одинаковые пароли дают
   разные хеши → таблица бесполезна (нужно строить отдельную
   таблицу для каждого возможного salt значения — нереально).

Q: "Где хранить секреты приложения в production?"
A: AWS Secrets Manager / Parameter Store, HashiCorp Vault,
   GCP Secret Manager. Преимущества: audit log, ротация без деплоя,
   IAM-based access control, автоматическая ротация RDS паролей (AWS).
   Development: .env в .gitignore.

Q: "Что такое Secret Rotation и как сделать без downtime?"
A: Периодическая смена секретов для минимизации exposure при компрометации.
   Без downtime: (1) выпустить new_secret, (2) поддержать оба ключа
   (try new → fallback old для JWT), (3) дождаться истечения токенов
   со старым ключом, (4) удалить old_secret.
   JWKS endpoint: автоматическая публикация public keys → rotation
   без деплоя потребителей.
```

---

## Группа 6: OWASP и Безопасная Архитектура

### Назовите топ-3 уязвимости из OWASP Top 10 и объясните их

**A01 Broken Access Control** (#1 с 2021): отсутствие проверки прав на ресурс. IDOR: пользователь меняет `/orders/123` на `/orders/124` → видит чужой заказ. Защита: ownership check на уровне каждого запроса, deny by default.

**A03 Injection**: SQL, Command, NoSQL injection. Защита: parameterized queries, execFile вместо exec, Zod validation.

**A10 SSRF**: сервер делает HTTP-запрос по URL указанному злоумышленником. В AWS: `http://169.254.169.254/latest/meta-data/` → IAM credentials. Защита: allowlist hostname + DNS rebinding protection (проверить что resolved IP не private range).

```txt
Типичные follow-up:

Q: "Как бы вы защитили fullstack приложение (Next.js + NestJS)?"
A: Слоями:
   1. HTTPS + HSTS (transport)
   2. Helmet.js security headers (CSP, X-Frame-Options, ...)
   3. Rate Limiting (brute force / DoS)
   4. Access Token (15мин JWT) + Refresh Token (HttpOnly Cookie, rotation)
   5. ValidationPipe whitelist=true (Mass Assignment, invalid input)
   6. Parameterized queries / Prisma (SQL Injection)
   7. Zod/class-validator на каждый endpoint (input validation)
   8. Role + ownership check (Broken Access Control)
   9. Argon2/bcrypt для паролей
   10. AWS Secrets Manager для секретов
   11. SSRF protection для любых URL-fetch операций
   12. Audit logging для auth events + 403 patterns

Q: "Что такое SSRF в контексте AWS и почему это критично?"
A: Instance Metadata Service: GET 169.254.169.254/latest/meta-data/
   iam/security-credentials/role-name → временные AWS credentials.
   С этими credentials → доступ к S3, RDS, другим сервисам по IAM.
   Защита: IMDSv2 (требует токен запроса), allowlist URLs,
   блокировка 169.254.169.254 на уровне security group.

Q: "Что такое Rate Limiting и как реализовать через Redis?"
A: Ограничение кол-ва запросов за период для защиты от brute force/DoS.
   Redis: INCR key → TTL установить при первом INCR → если count > limit →
   отклонить с 429. Библиотека express-rate-limit поддерживает Redis store.
   Продвинутый: rate limit по (userId + endpoint) отдельно от (IP),
   sliding window вместо fixed window.
```
