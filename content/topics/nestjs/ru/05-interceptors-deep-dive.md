<!-- verified: 2026-06-05, corrections: 0 -->
# Interceptors Deep Dive

## Что такое Interceptor

Interceptor — механизм,
который позволяет перехватывать
выполнение метода до и после его вызова.

---

Очень важно понимать:

```txt
Middleware работает
до Nest

Interceptor работает
внутри Nest
```

---

# Где находятся

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

# Интерфейс

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

# Что такое CallHandler

Очень популярный вопрос.

---

```ts
next.handle()
```

---

Представляет:

```txt
следующий шаг пайплайна
```

---

Обычно:

```txt
Controller Method
```

---

# Самый простой пример

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

# После выполнения

Interceptor может обрабатывать ответ.

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

# Почему используется RxJS

Очень популярный вопрос.

---

`next.handle()`

возвращает:

```ts
Observable
```

---

Поэтому можем:

```txt
tap
map
catchError
switchMap
```

---

# Transform Response

Самый частый кейс.

---

Например:

Контроллер:

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

Результат:

```ts
{
 success: true,
 data: {...}
}
```

---

# Logging

Очень популярный кейс.

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

Встроенный пример Nest.

---

Проверяет:

```txt
есть данные в кеше
```

---

Если есть:

```txt
Controller не вызывается
```

---

# Exception Handling

Можно перехватывать ошибки.

---

```ts
catchError(err => {

 throw new BadRequestException();
})
```

---

# ExecutionContext

Внутри Interceptor можно получить:

```ts
const req =
 context
  .switchToHttp()
  .getRequest();
```

---

# Реальные кейсы

```txt
Logging

Caching

Response Transformation

Metrics

Audit

Performance Monitoring
```

---

# Чем Interceptor отличается от Middleware

Очень популярный вопрос.

---

Middleware:

```txt
не знает
какой handler вызывается
```

---

Interceptor:

```txt
знает
handler
controller
metadata
```

---

# Чем Interceptor отличается от Guard

Guard:

```txt
разрешить или запретить
```

---

Interceptor:

```txt
изменить выполнение
```

---

# Чем Interceptor отличается от Pipe

Pipe:

```txt
изменяет входящие данные
```

---

Interceptor:

```txt
может изменять
и вход
и выход
```

---

# Частый вопрос

Можно ли полностью остановить выполнение метода?

---

Да.

---

Например:

```ts
return of(cachedData);
```

---

Тогда:

```txt
Controller не вызовется
```

---

# Interview Answer

Interceptor позволяет перехватывать выполнение метода до и после его вызова. Он работает через RxJS Observable, имеет доступ к ExecutionContext и может использоваться для логирования, кеширования, трансформации ответов и обработки ошибок. В отличие от Middleware он знает, какой контроллер и handler выполняются.