# Guards vs Pipes vs Interceptors vs Middleware

## The Most Popular NestJS Interview Question

Almost guaranteed to be asked:

```txt
What is the difference between:
Middleware
Guard
Pipe
Interceptor
```

---

# The Main Rule

Each mechanism solves its own task.

---

# Middleware

Responsible for:

```txt
Request Processing
```

---

Examples:

```txt
Logging

CORS

Headers

Cookies

Request ID
```

---

# Middleware Knows Nothing

Does not know about:

```txt
Controller
Handler
Metadata
```

---

Operates at the:

```txt
HTTP Layer
```

---

# Guard

Responsible for:

```txt
Authorization
```

---

Question:

```txt
Allow the request?
```

---

or

```txt
Deny the request?
```

---

# Example

```ts
canActivate() {

 return true;
}
```

---

# Typical Use Cases

```txt
JWT

Roles

Permissions
```

---

# Pipe

Responsible for:

```txt
Transformation
Validation
```

---

Question:

```txt
Are the input data correct?
```

---

# Example

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

The Pipe transforms:

```txt
"123"
```

into

```txt
123
```

---

# ValidationPipe

The most popular Pipe.

---

Uses:

```txt
class-validator
class-transformer
```

---

Example:

```ts
@Post()
create(
 @Body()
 dto: CreateUserDto
)
```

---

Validates:

```txt
email
required fields
types
```

---

# Sanitization

A very popular interview question.

---

```ts
whitelist: true
```

---

Removes:

```txt
extra fields
```

---

Example:

```json
{
 "email": "...",
 "role": "admin"
}
```

---

If role is not in the DTO:

```txt
it will be removed
```

---

# Interceptor

Responsible for:

```txt
Cross Cutting Concerns
```

---

For example:

```txt
Logging

Caching

Metrics

Response Mapping
```

---

# Comparison

Middleware:

```txt
before Nest
```

---

Guard:

```txt
access
```

---

Pipe:

```txt
validation
```

---

Interceptor:

```txt
wrapper around execution
```

---

# Execution Order

A very popular interview question.

---

Full Flow.

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

# Why Pipe Comes After Guard

A very popular interview topic.

---

Because:

```txt
no need to validate data
if the user doesn't have access
anyway
```

---

# Why Interceptor Wraps the Controller

Because it:

```txt
can measure time
log
modify the response
```

---

# Real Example

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

# Frequent Question

Where should Roles be implemented?

---

Correct answer:

```txt
Guard
```

---

Not Middleware.

---

# Frequent Question

Where should Validation be implemented?

---

```txt
Pipe
```

---

Not Guard.

---

# Frequent Question

Where should Logging be implemented?

---

```txt
Interceptor
```

---

or

```txt
Middleware
```

---

Depends on the task.

---

# Frequent Question

What to choose for JWT verification?

---

Most often:

```txt
Guard
```

---

# Frequent Question

What to choose for transforming the API response?

---

```txt
Interceptor
```

---

# Frequent Question

What to choose for removing extra fields?

---

```txt
ValidationPipe
```

---

# Interview Answer

Middleware operates at the HTTP level and is used for general request processing. Guards handle authorization and make the access decision. Pipes validate and transform incoming data. Interceptors wrap method execution and are used for logging, caching, error handling, and response transformation. Execution order: Middleware → Guard → Interceptor(before) → Pipe → Controller → Interceptor(after).
