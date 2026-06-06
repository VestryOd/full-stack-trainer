# Interceptors Deep Dive

## What is an Interceptor

An Interceptor is a mechanism
that allows intercepting
the execution of a method before and after its call.

---

Very important to understand:

```txt
Middleware runs
before Nest

Interceptor runs
inside Nest
```

---

# Where They Sit

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

# Interface

```ts
@Injectable()
export class LoggingInterceptor
 implements NestInterceptor {

 intercept(
  context: ExecutionContext,
  next: CallHandler
 ) {

 }
}
```

---

# What is CallHandler

A very popular interview question.

---

```ts
next.handle()
```

---

Represents:

```txt
the next step in the pipeline
```

---

Usually:

```txt
Controller Method
```

---

# The Simplest Example

```ts
intercept(
 context,
 next
) {

 console.log('before');

 return next.handle();
}
```

---

Flow:

```txt
before
 ↓
Controller
```

---

# After Execution

The Interceptor can process the response.

---

```ts
return next.handle().pipe(
 tap(() => {
  console.log('after');
 })
);
```

---

Flow:

```txt
before
 ↓
Controller
 ↓
after
```

---

# Why RxJS Is Used

A very popular interview question.

---

`next.handle()`

returns:

```ts
Observable
```

---

So we can use:

```txt
tap
map
catchError
switchMap
```

---

# Transform Response

The most common use case.

---

For example:

Controller returns:

```ts
{
 id: 1,
 name: 'John'
}
```

---

Interceptor:

```ts
return next.handle().pipe(

 map(data => ({
  success: true,
  data
 }))
);
```

---

Result:

```ts
{
 success: true,
 data: {...}
}
```

---

# Logging

A very popular use case.

---

```ts
const now = Date.now();

return next.handle().pipe(

 tap(() => {

  console.log(
   Date.now() - now
  );
 })
);
```

---

# Cache Interceptor

A built-in Nest example.

---

Checks:

```txt
is data in the cache
```

---

If yes:

```txt
the Controller is not called
```

---

# Exception Handling

Errors can be intercepted.

---

```ts
catchError(err => {

 throw new BadRequestException();
})
```

---

# ExecutionContext

Inside an Interceptor you can get:

```ts
const req =
 context
  .switchToHttp()
  .getRequest();
```

---

# Real Use Cases

```txt
Logging

Caching

Response Transformation

Metrics

Audit

Performance Monitoring
```

---

# How an Interceptor Differs from Middleware

A very popular interview question.

---

Middleware:

```txt
does not know
which handler is being called
```

---

Interceptor:

```txt
knows the
handler
controller
metadata
```

---

# How an Interceptor Differs from a Guard

Guard:

```txt
allow or deny
```

---

Interceptor:

```txt
modify execution
```

---

# How an Interceptor Differs from a Pipe

Pipe:

```txt
transforms incoming data
```

---

Interceptor:

```txt
can transform
both input
and output
```

---

# Frequent Question

Can method execution be stopped completely?

---

Yes.

---

For example:

```ts
return of(cachedData);
```

---

Then:

```txt
the Controller won't be called
```

---

# Interview Answer

An Interceptor allows intercepting the execution of a method before and after its call. It works via an RxJS Observable, has access to the ExecutionContext, and can be used for logging, caching, response transformation, and error handling. Unlike Middleware, it knows which controller and handler are executing.
