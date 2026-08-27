<!-- verified: 2026-06-05, corrections: 0 -->
# Security: Вопросы для интервью

Вопросы сгруппированы тематически. Внутри каждой группы — полный senior-ответ + типичные follow-up вопросы.

---

## Группа 1: Основы безопасности

### Что такое CIA Triad и почему это важно?

CIA — это confidentiality, integrity, availability: конфиденциальность, целостность и доступность. Три фундаментальных свойства безопасности любой системы.

**Confidentiality** (конфиденциальность): данные доступны только авторизованным. Угрозы: перехват трафика, он же атака MITM (man-in-the-middle — «человек посередине»), SQL (Structured Query Language) Injection и утечка токенов. Меры: HTTPS (HTTP Secure — HTTP поверх шифрования), шифрование и RBAC (role-based access control — управление доступом на основе ролей).

**Integrity** (целостность): данные не могут быть изменены незаметно. Угрозы: CSRF (cross-site request forgery — подделка межсайтового запроса), которая выполняет действие от имени пользователя. Ещё SQL Injection, меняющий данные, и подмена payload у JWT (JSON Web Token) без валидной подписи. Меры: HMAC (hash-based message authentication code), digital signatures и сама подпись JWT.

**Availability** (доступность): система доступна для авторизованных пользователей. Угрозы: DDoS (distributed denial of service — распределённый отказ в обслуживании), regex DoS и resource exhaustion. Меры: Rate Limiting и Circuit Breaker.

**Типичные follow-up**

**Q: «Что нарушает DDoS?»**

A: Availability. DDoS исчерпывает ресурсы сервера, поэтому легитимные пользователи не могут получить доступ.

**Q: «Что нарушает перехват JWT?»**

A: Confidentiality. Злоумышленник получает доступ к данным, которые предназначались только авторизованному пользователю.

**Q: «Что нарушает CSRF?»**

A: Integrity. Действие выполняется от имени пользователя без его ведома, то есть данные изменены неавторизованно.

### Что такое Defense in Depth?

Принцип многоуровневой защиты: если один уровень пробит, следующий должен остановить атаку. Нельзя полагаться на единственную защиту.

Пример для API endpoint, по одному слою на шаг:

1. HTTPS — шифрование.
2. Rate Limiting — защита от brute force.
3. JWT Validation — аутентификация.
4. Role Check — авторизация.
5. Zod или ValidationPipe — валидация.
6. Parameterized Query — защита от injection.
7. Output Encoding — защита от XSS (cross-site scripting — межсайтовый скриптинг).
8. Security Headers — защита от clickjacking.

**Типичные follow-up**

**Q: «Что такое Security Through Obscurity? Это работает?»**

A: Попытка обезопасить систему скрытием информации — секретный URL, непубличная документация. Защитой это **не** является: злоумышленник находит endpoints через brute force, сканирование и source code.

Реальная защита — авторизация на endpoint, независимо от его «секретности». Принцип Kerckhoffs: система безопасна, если секрет — только ключ, а не алгоритм.

---

## Группа 2: JWT, Authentication и Tokens

### Опишите структуру JWT и что происходит если payload изменить

JWT — три base64url-encoded части: `header.payload.signature`.

- **Header**: алгоритм (`HS256`) и тип
- **Payload**: claims (sub, role, exp, iat, jti) — **не** зашифрован, любой может прочитать
- **Signature**: HMAC(header + payload, secret) — гарантирует целостность

Если payload изменить (например, `role: "user" → "admin"`): signature станет невалидной при верификации. Сервер должен отклонить токен с ошибкой. Исключение: атака `alg:none` — если библиотека принимает algorithm=none, подпись не проверяется. Защита: `jwt.verify(token, secret, { algorithms: ['HS256'] })` — явное указание.

**Типичные follow-up**

**Q: «Можно ли класть пароль в JWT?»**

A: Нет. Payload только подписан, но не зашифрован. Любой может сделать base64decode payload без ключа и увидеть содержимое.

**Q: «Чем HS256 отличается от RS256?»**

A: HS256 — симметричный: один secret и для подписи, и для верификации. RS256 — асимметричный: private key подписывает, public key верифицирует. В microservices RS256 предпочтительнее, потому что каждый сервис верифицирует через public key, не зная private key.

### Объясните схему Access Token + Refresh Token и проблему logout

**Зачем два токена**: один long-lived JWT при краже — катастрофа, потому что он действует 30 дней. Два токена делят этот риск: Access (15 мин, stateless) плюс Refresh (30 дней, хранится в базе данных).

**Flow**: Login → AccessToken (в JSON response) + RefreshToken (HttpOnly Cookie). Через 15 мин: POST /auth/refresh → новый AccessToken. Logout: удалить RefreshToken из базы данных + clearCookie.

**JWT Logout Problem**: Access Token stateless, поэтому его нельзя «отозвать» до истечения TTL (time to live — время жизни). Три решения:

1. Короткий TTL, 15 мин.
2. Redis blacklist по `jti`.
3. Refresh Token Rotation: каждый refresh выдаёт новый refresh token, а старый аннулируется.

**Типичные follow-up**

**Q: «Где безопасно хранить Access Token?»**

A: Memory (JS variable) защищён от XSS, но теряется при refresh страницы. HttpOnly Cookie защищён от XSS, но несёт риск CSRF, поэтому нужен `sameSite=strict`. localStorage — **небезопасно**: XSS может украсть.

**Q: «Как обнаружить кражу Refresh Token?»**

A: Refresh Token Rotation. При каждом refresh выдаётся новый refresh token, а старый удаляется из базы данных. Если злоумышленник использует украденный токен, это попытка reuse уже использованного токена. Она поднимает alert и отзывает **все** refresh tokens пользователя.

**Q: «Что такое OAuth 2.0 и чем он отличается от аутентификации?»**

A: OAuth 2.0 — протокол делегированной **авторизации**, то есть доступа к ресурсам. Для аутентификации нужен OpenID Connect — слой поверх OAuth 2.0, который добавляет `id_token` с identity-данными. «Войти через Google» — это OpenID Connect, а не чистый OAuth 2.0.

---

## Группа 3: XSS, CSRF и CORS

Три темы на стороне браузера, которые легко перепутать: XSS, CSRF и CORS (cross-origin resource sharing — совместное использование ресурсов между источниками).

### Объясните XSS, CSRF и чем они отличаются

**XSS** (Cross-Site Scripting): злоумышленник внедряет JavaScript в страницы, браузер жертвы выполняет его в контексте вашего сайта. Три типа: Stored (в базе данных), Reflected (в URL) и DOM-based — он живёт в Document Object Model, объектной модели документа на клиенте. Результат: кража токенов из localStorage/cookie, keylogger, действия от имени пользователя.

**CSRF** (Cross-Site Request Forgery): браузер жертвы (уже аутентифицированный) отправляет запрос к вашему сайту с evil.com. Браузер автоматически прикладывает cookie для вашего домена. Сервер не отличает от легитимного запроса.

**Ключевое отличие**: XSS — код выполняется с вашего origin. CSRF — запрос отправляется с чужого origin.

**Типичные follow-up**

**Q: «Почему JWT в заголовке Authorization защищает от CSRF?»**

A: Браузер автоматически отправляет cookie для домена, но **не** добавляет кастомные заголовки вроде Authorization на кросс-доменные запросы. Страница на evil.com не может получить JWT из памяти или из localStorage из-за same-origin policy, поэтому и заголовок поставить не может.

**Q: «Защищает ли HttpOnly Cookie от XSS?»**

A: Частично. HttpOnly делает cookie недоступным для чтения из JS. Но XSS всё равно может отправлять запросы с вашего origin через fetch или XMLHttpRequest, и cookie прикладывается автоматически. XSS плюс сессионная аутентификация дают action hijacking. Полная защита — HttpOnly плюс CSP (Content Security Policy), который ограничивает то, что может сделать внедрённый скрипт.

**Q: «Что такое CORS и защищает ли он сервер?»**

A: CORS — политика браузера, контролирующая кросс-доменные запросы через fetch и XHR (XMLHttpRequest). Сервер она **не** защищает: curl, Postman и любой бэкенд полностью обходят CORS. Защищает только браузерный контекст пользователя. Сервер защищают аутентификация и авторизация.

**Q: «Когда браузер отправляет Preflight OPTIONS?»**

A: Перед «non-simple» запросом: метод DELETE, PUT или PATCH, заголовок Authorization или `Content-Type: application/json`, либо любой кастомный заголовок. Preflight спрашивает сервер, разрешён ли этот запрос, до отправки основного.

---

## Группа 4: Injection и Input Validation

### Что такое SQL Injection и как защититься?

SQL Injection: пользовательский ввод конкатенируется в SQL → злоумышленник изменяет логику запроса. Пример: `email = "' OR '1'='1' --"` → обход аутентификации. UNION attack → утечка всей таблицы. При правах DROP → удаление данных.

Единственная правильная защита: **parameterized queries**, где данные никогда не становятся частью SQL-текста. ORM (object-relational mapper — объектно-реляционное отображение), например Prisma или TypeORM, параметризует автоматически для стандартных методов, но `$queryRawUnsafe` и `query()` с конкатенацией уязвимы.

**Типичные follow-up**

**Q: «Что такое Command Injection?»**

A: Аналог SQL Injection для shell-команд. Если ввод пользователя передаётся в `exec()`, злоумышленник вставляет `; rm -rf /`. Защита: `execFile()` вместо `exec()`, потому что он не интерпретирует metacharacters, или отказ от shell полностью.

**Q: «Что такое Mass Assignment?»**

A: Клиент передаёт поля, которые не должен менять, например `role:'admin'`, а сервер слепо применяет `req.body` к модели. Защита: явный whitelist через DTO (data transfer object — объект передачи данных) или Zod schema, принимать только объявленные поля.

**Q: «Чем Validation отличается от Sanitization?»**

A: Validation спрашивает, корректны ли данные, и отклоняет неправильные с кодом 400. Sanitization спрашивает, безопасны ли данные, и трансформирует их для контекста. Для SQL — только parameterized queries, не ручное экранирование. Для HTML — DOMPurify, когда рендерить HTML действительно нужно. Оба нужны в разных контекстах.

---

## Группа 5: Пароли и Секреты

### Как правильно хранить пароли и почему нельзя шифровать?

**Нельзя шифровать**: шифрование обратимо. При утечке ключа → все пароли раскрыты. Для проверки пароля при логине шифрование не нужно — достаточно сравнить хеши.

**Нельзя SHA-256**: семейство Secure Hash Algorithm разработано ради скорости. GPU (graphics processing unit — графический процессор) вычисляет 23 млрд SHA-256/сек, поэтому перебор словаря из 10 млн паролей занимает ~0.01 сек.

**bcrypt**: специально медленный (cost=12 → ~400ms), встраивает соль в хеш автоматически, adaptive (при росте мощности CPU — повышать cost). CPU здесь — центральный процессор.

**Argon2id**: победитель Password Hashing Competition. Memory-hard: требует 64MB RAM (random access memory — оперативная память), поэтому GPU-атаки нивелированы. Рекомендован для новых проектов.

**Типичные follow-up**

**Q: «Что такое Rainbow Table и как bcrypt защищает?»**

A: Rainbow Table — предвычисленная таблица `{password → hash}`. Поскольку bcrypt даёт каждому паролю уникальную соль, одинаковые пароли дают разные хеши и таблица бесполезна. Злоумышленнику пришлось бы строить отдельную таблицу под каждое значение salt, а это нереально.

**Q: «Где хранить секреты приложения в production?»**

A: AWS (Amazon Web Services) Secrets Manager или Parameter Store, HashiCorp Vault, GCP (Google Cloud Platform) Secret Manager. Преимущества: audit log, ротация без деплоя, управление доступом на основе IAM (identity and access management) и автоматическая ротация паролей RDS (Relational Database Service) в AWS. Для development — `.env` в `.gitignore`.

**Q: «Что такое Secret Rotation и как сделать без downtime?»**

A: Периодическая смена секретов, чтобы уменьшить ущерб при компрометации. Без downtime это четыре шага:

1. Выпустить `new_secret`.
2. Поддержать оба ключа: сначала пробуем новый, для JWT откатываемся на старый.
3. Дождаться, пока истекут токены, подписанные старым ключом.
4. Удалить `old_secret`.

Endpoint JWKS (JSON Web Key Set) публикует public keys автоматически, поэтому ротация не требует деплоя потребителей.

---

## Группа 6: OWASP и Безопасная Архитектура

OWASP (Open Worldwide Application Security Project) публикует Top 10 — список самых критичных уязвимостей веб-приложений.

### Назовите топ-3 уязвимости из OWASP Top 10 и объясните их

**A01 — Broken Access Control** (#1 с 2021): отсутствие проверки прав на ресурс. IDOR (insecure direct object reference — небезопасная прямая ссылка на объект): пользователь меняет `/orders/123` на `/orders/124` и видит чужой заказ. Защита: ownership check на уровне каждого запроса, deny by default.

**A03 — Injection**: SQL, Command и NoSQL (нереляционная база данных) injection. Защита: parameterized queries, execFile вместо exec, Zod validation.

**A10 — Server-Side Request Forgery (SSRF)**: сервер делает HTTP-запрос по URL, указанному злоумышленником. В AWS: `http://169.254.169.254/latest/meta-data/` → IAM credentials. Защита: allowlist hostname плюс защита от DNS (domain name system) rebinding. Эта проверка убеждается, что адрес IP (internet protocol), полученный при резолве имени, не попадает в private range.

**Типичные follow-up**

**Q: «Как бы вы защитили fullstack приложение (Next.js + NestJS)?»**

A: Слоями.

1. HTTPS + HSTS (HTTP Strict Transport Security) на транспорте.
2. Helmet.js security headers: CSP, X-Frame-Options и остальные.
3. Rate Limiting против brute force и DoS.
4. Access Token (JWT на 15 мин) + Refresh Token (HttpOnly Cookie, rotation).
5. ValidationPipe с `whitelist=true` против Mass Assignment и невалидного ввода.
6. Parameterized queries или Prisma против SQL Injection.
7. Zod или class-validator на каждый endpoint для input validation.
8. Role + ownership check против Broken Access Control.
9. Argon2 или bcrypt для паролей.
10. AWS Secrets Manager для секретов.
11. SSRF protection для любых URL-fetch операций.
12. Audit logging для auth events + 403 patterns.

**Q: «Что такое SSRF в контексте AWS и почему это критично?»**

A: Instance Metadata Service отвечает на `GET 169.254.169.254/latest/meta-data/iam/security-credentials/role-name` временными AWS credentials. С этими credentials злоумышленник добирается до S3 (Amazon Simple Storage Service), RDS и других сервисов по IAM. Защита: IMDSv2, который требует токен запроса, allowlist URLs и блокировка `169.254.169.254` на уровне security group.

**Q: «Что такое Rate Limiting и как реализовать через Redis?»**

A: Ограничение количества запросов за период для защиты от brute force и DoS. Redis: `INCR key`, поставить TTL при первом `INCR`, и если count больше лимита — отклонить с кодом 429. Библиотека express-rate-limit поддерживает Redis store. Продвинутый вариант: rate limit по (userId + endpoint) отдельно от (IP) и sliding window вместо fixed window.
