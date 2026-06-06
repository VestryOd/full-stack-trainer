<!-- verified: 2026-06-05, corrections: 0 -->
# Custom Decorators

## Что такое декоратор

Декоратор — функция,
которая добавляет metadata
или изменяет поведение класса,
метода, параметра или свойства.

---

Примеры Nest:

```ts
@Controller()
@Get()
@Post()
@Inject()
```

---

Все они декораторы.

---

# Зачем нужны свои декораторы

Чтобы скрыть повторяющуюся логику.

---

Например:

```ts
req.user.id
```

встречается везде.

---

# Без декоратора

```ts
@Get()
profile(
 @Req() req
) {

 return req.user;
}
```

---

# Создаем User Decorator

```ts
export const User =
 createParamDecorator(
  (
   data,
   ctx: ExecutionContext
  ) => {

   const req =
    ctx
     .switchToHttp()
     .getRequest();

   return req.user;
  }
 );
```

---

# Использование

```ts
@Get()
profile(
 @User() user
) {

 return user;
}
```

---

Красиво и переиспользуемо.

---

# Что происходит под капотом

Nest вызывает:

```ts
ExecutionContext
```

---

Извлекает:

```ts
request.user
```

---

Передает значение параметру метода.

---

# Parameter Decorators

Самый популярный тип.

---

Примеры:

```ts
@Body()
@Param()
@Query()
@Headers()
```

---

Все работают одинаково.

---

# Method Decorators

Вешаются на метод.

---

Пример:

```ts
@Roles('admin')
```

---

Создание:

```ts
export const Roles =
 (...roles: string[]) =>
  SetMetadata(
   'roles',
   roles
  );
```

---

# Что делает SetMetadata

Под капотом:

```ts
Reflect.defineMetadata(...)
```

---

# Использование

```ts
@Roles('admin')
@Get()
users()
```

---

# Guard читает metadata

```ts
this.reflector.get(
 'roles',
 context.getHandler()
);
```

---

# Composite Decorators

Очень популярный Senior вопрос.

---

Можно объединять декораторы.

---

Пример:

```ts
@Auth()
```

---

Внутри:

```ts
UseGuards(...)
ApiBearerAuth()
Roles(...)
```

---

# Реализация

```ts
export function Auth() {

 return applyDecorators(
  UseGuards(AuthGuard),
  ApiBearerAuth()
 );
}
```

---

# Почему это удобно

Вместо:

```ts
@UseGuards(...)
@ApiBearerAuth()
@Roles(...)
```

---

Получаем:

```ts
@Auth()
```

---

# Class Decorators

Вешаются на класс.

---

Пример:

```ts
@Controller()
```

---

# Property Decorators

Используются редко.

---

Обычно:

```ts
Validation
Serialization
```

---

# Частый вопрос

Чем декоратор отличается от middleware?

---

Decorator:

```txt
добавляет metadata
```

---

Middleware:

```txt
обрабатывает запрос
```

---

# Частый вопрос

Как работает @Roles()?

Ответ:

@Roles использует SetMetadata и сохраняет список ролей в metadata метода. Затем Roles Guard читает эту metadata через Reflector и проверяет права пользователя.

---

# Interview Answer

Custom Decorators позволяют инкапсулировать повторяющуюся логику и работать с metadata NestJS. Они часто используются для извлечения данных из запроса, хранения ролей и создания композиции нескольких декораторов через applyDecorators.