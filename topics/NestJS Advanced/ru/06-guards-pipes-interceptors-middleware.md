# Guards vs Pipes vs Interceptors vs Middleware

## Самый популярный вопрос по NestJS

Почти гарантированно спрашивают:

```txt
Чем отличаются:
Middleware
Guard
Pipe
Interceptor
```

---

# Главное правило

Каждый механизм решает свою задачу.

---

# Middleware

Отвечает за:

```txt
Request Processing
```

---

Примеры:

```txt
Logging

CORS

Headers

Cookies

Request ID
```

---

# Middleware ничего не знает

Не знает:

```txt
Controller
Handler
Metadata
```

---

Работает на уровне:

```txt
HTTP Layer
```

---

# Guard

Отвечает за:

```txt
Authorization
```

---

Вопрос:

```txt
Разрешить запрос?
```

---

или

```txt
Запретить запрос?
```

---

# Пример

```ts
canActivate() {

 return true;
}
```

---

# Типичный кейс

```txt
JWT

Roles

Permissions
```

---

# Pipe

Отвечает за:

```txt
Transformation
Validation
```

---

Вопрос:

```txt
Корректны ли входные данные?
```

---

# Пример

```ts
ParseIntPipe
```

---

```ts
@Get(':id')
find(
 @Param(
  'id',
  ParseIntPipe
 )
 id: number
)
```

---

Pipe превращает:

```txt
"123"
```

в

```txt
123
```

---

# ValidationPipe

Самый популярный Pipe.

---

Использует:

```txt
class-validator
class-transformer
```

---

Пример:

```ts
@Post()
create(
 @Body()
 dto: CreateUserDto
)
```

---

Проверяет:

```txt
email
required fields
types
```

---

# Санитизация

Очень популярный вопрос.

---

```ts
whitelist: true
```

---

Удаляет:

```txt
лишние поля
```

---

Пример:

```json
{
 "email": "...",
 "role": "admin"
}
```

---

Если role нет в DTO:

```txt
будет удалено
```

---

# Interceptor

Отвечает за:

```txt
Cross Cutting Concerns
```

---

Например:

```txt
Logging

Caching

Metrics

Response Mapping
```

---

# Сравнение

Middleware:

```txt
до Nest
```

---

Guard:

```txt
доступ
```

---

Pipe:

```txt
валидация
```

---

Interceptor:

```txt
обертка над выполнением
```

---

# Порядок выполнения

Очень популярный вопрос.

---

Полный Flow.

---

```txt
Request
 ↓
Middleware
 ↓
Guard
 ↓
Interceptor (before)
 ↓
Pipe
 ↓
Controller
 ↓
Service
 ↓
Interceptor (after)
 ↓
Response
```

---

# Почему Pipe после Guard

Очень любят спрашивать.

---

Потому что:

```txt
не нужно валидировать данные
если пользователь всё равно
не имеет доступа
```

---

# Почему Interceptor оборачивает Controller

Потому что:

```txt
может измерять время
логировать
изменять ответ
```

---

# Реальный пример

---

Middleware:

```txt
Request ID
```

---

Guard:

```txt
JWT
```

---

Pipe:

```txt
Validation
```

---

Interceptor:

```txt
Logging
```

---

Controller:

```txt
Business Logic
```

---

# Частый вопрос

Где реализовывать Roles?

---

Правильный ответ:

```txt
Guard
```

---

Не Middleware.

---

# Частый вопрос

Где реализовывать Validation?

---

```txt
Pipe
```

---

Не Guard.

---

# Частый вопрос

Где реализовывать Logging?

---

```txt
Interceptor
```

---

или

```txt
Middleware
```

---

Зависит от задачи.

---

# Частый вопрос

Что выбрать для проверки JWT?

---

Чаще всего:

```txt
Guard
```

---

# Частый вопрос

Что выбрать для преобразования ответа API?

---

```txt
Interceptor
```

---

# Частый вопрос

Что выбрать для удаления лишних полей?

---

```txt
ValidationPipe
```

---

# Interview Answer

Middleware работает на уровне HTTP и используется для общей обработки запросов. Guards отвечают за авторизацию и принимают решение о доступе. Pipes валидируют и трансформируют входящие данные. Interceptors оборачивают выполнение метода и используются для логирования, кеширования, обработки ошибок и трансформации ответов. Порядок выполнения: Middleware → Guard → Interceptor(before) → Pipe → Controller → Interceptor(after).