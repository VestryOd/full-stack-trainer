# ExecutionContext и рефлексия

## Что такое ExecutionContext

`ExecutionContext` — обёртка над текущим входящим запросом. Её получают три механизма Nest, которые встраиваются в обработку запроса:

- **Guard** — решает, пустить запрос к обработчику или отклонить.
- **Interceptor** — оборачивает вызов обработчика и может изменить ответ.
- **Exception Filter** — превращает выброшенное исключение в ответ клиенту.

Обёртка нужна потому, что NestJS работает с несколькими транспортами. Транспорт — это канал, по которому пришёл запрос: HTTP, WebSocket, gRPC или RPC-сообщение микросервиса. RPC (remote procedure call) — вызов метода на другом сервисе по сети.

Один и тот же Guard должен работать на любом транспорте. Поэтому он получает не сырой `req`, а `ExecutionContext`.

```typescript
import { CanActivate, ExecutionContext, Injectable } from '@nestjs/common';

@Injectable()
export class AuthGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    // context.getType() → 'http' | 'ws' | 'rpc'
    const type = context.getType();

    // context.getHandler() → метод контроллера (например: getUser)
    const handler = context.getHandler();

    // context.getClass() → класс контроллера (например: UsersController)
    const controllerClass = context.getClass();

    // switchToHttp() → только для HTTP транспорта
    const request = context.switchToHttp().getRequest<Request>();
    const response = context.switchToHttp().getResponse<Response>();

    return true;
  }
}
```

```txt
Методы switchTo*():
  switchToHttp() → { getRequest(), getResponse(), getNext() }
  switchToWs()   → { getClient(), getData() }
  switchToRpc()  → { getContext(), getData() }

Почему нельзя сразу context.getRequest():
  ExecutionContext не знает, на каком транспорте вы работаете.
  switchToHttp() явно заявляет: "это HTTP-запрос".
  На WebSocket switchToHttp().getRequest() вернёт undefined.
```

## Reflect Metadata — как декораторы хранят данные

Reflect Metadata — стандарт для хранения метаданных на классах и методах во время выполнения. Метаданные здесь — это данные о коде: например, список ролей, который декоратор `@Roles('admin')` привязывает к методу.

NestJS использует для этого библиотеку `reflect-metadata`. Она polyfill, то есть реализация стандарта для движков, где его ещё нет. Декоратор пишет метаданные, а Guard читает их через `Reflector`.

```typescript
import 'reflect-metadata'; // должен быть первым импортом в main.ts

// Декоратор @Roles сохраняет роли в metadata метода/класса
export const ROLES_KEY = 'roles';

export const Roles = (...roles: string[]) =>
  SetMetadata(ROLES_KEY, roles);
// SetMetadata под капотом делает:
// Reflect.defineMetadata(ROLES_KEY, roles, target, propertyKey)

// Guard читает metadata через Reflector
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    // getAllAndOverride: метод-уровень приоритетнее класс-уровня
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [
      context.getHandler(), // сначала проверить на методе
      context.getClass(),   // потом на классе
    ]);

    if (!requiredRoles) return true; // нет ограничений → пропустить

    const { user } = context.switchToHttp().getRequest();
    return requiredRoles.some(role => user?.roles?.includes(role));
  }
}
```

## Прямая работа с Reflect API

`SetMetadata` — тонкая обёртка над `Reflect.defineMetadata`, и то же самое можно написать руками. Пример ниже показывает четыре способа работать с одними и теми же метаданными. Это встроенный хелпер, ручной декоратор, чтение через `Reflector` и чтение напрямую через `Reflect`.

```typescript
// SetMetadata — встроенный хелпер NestJS (рекомендуется)
export const Public = () => SetMetadata('isPublic', true);

// Эквивалент вручную:
export function PublicManual(): MethodDecorator {
  return (target, propertyKey) => {
    Reflect.defineMetadata('isPublic', true, target, propertyKey);
  };
}

// Чтение через reflector (в Guard):
const isPublic = this.reflector.getAllAndOverride<boolean>('isPublic', [
  context.getHandler(),
  context.getClass(),
]);

// Прямое чтение через Reflect (без Reflector):
const roles = Reflect.getMetadata('roles', context.getHandler());

// reflector.get vs reflector.getAllAndOverride:
// .get(key, target) — читает только с указанного target
// .getAllAndOverride(key, [method, class]) — читает сначала с method, потом с class
// .getAllAndMerge(key, [method, class]) — объединяет массивы с обоих (для union ролей)
```

## Полный паттерн: JWT Auth Guard с @Public()

JWT (JSON Web Token) — подписанный токен, который клиент присылает в заголовке `Authorization`. Рабочий приём — проверять токен сразу на всех маршрутах, а редкие исключения помечать декоратором `@Public()`.

Тогда забыть про защиту нельзя: по умолчанию закрыто всё, а публичный маршрут виден в коде явно.

```typescript
// public.decorator.ts
export const IS_PUBLIC_KEY = 'isPublic';
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);

// jwt-auth.guard.ts
@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  constructor(private reflector: Reflector) {
    super();
  }

  canActivate(context: ExecutionContext): boolean | Promise<boolean> {
    // Проверить @Public() на методе ИЛИ контроллере
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) return true; // пропустить без JWT проверки

    return super.canActivate(context); // стандартная JWT валидация
  }
}

// app.module.ts — применить глобально
providers: [
  { provide: APP_GUARD, useClass: JwtAuthGuard }, // все эндпоинты защищены по умолчанию
],

// auth.controller.ts — публичные маршруты
@Public()
@Post('login')
login(@Body() dto: LoginDto) { ... }

// users.controller.ts — защищённые маршруты
@Get('profile')  // защищён JwtAuthGuard автоматически
getProfile(@Request() req) { return req.user; }
```

## getType() — один Guard для нескольких транспортов

`context.getType()` возвращает `'http' | 'ws' | 'rpc'` и говорит, каким транспортом пришёл запрос. Guard смотрит на это значение и выбирает подходящий `switchTo*()`.

Без такой проверки универсальный Guard сломается на первом же не-HTTP запросе: `switchToHttp().getRequest()` вернёт `undefined`, а не ошибку.

```typescript
@Injectable()
export class UniversalGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const type = context.getType<'http' | 'ws' | 'rpc'>();

    if (type === 'http') {
      const req = context.switchToHttp().getRequest();
      return this.validateHttpRequest(req);
    }

    if (type === 'ws') {
      const data = context.switchToWs().getData();
      return this.validateWsMessage(data);
    }

    if (type === 'rpc') {
      const rpcContext = context.switchToRpc().getContext();
      return this.validateRpcCall(rpcContext);
    }

    return false;
  }
}
```

## Типичные ошибки на интервью

- **"ExecutionContext — это просто request объект"** — нет. Это обёртка над контекстом выполнения, а не над запросом. `getRequest()` — метод только HTTP-контекста. Кроме запроса `ExecutionContext` даёт обработчик и класс контроллера, чтобы прочитать метаданные, и работает для WebSocket и RPC.

- **"Reflector.get() и getAllAndOverride() — одно и то же"** — нет. Вызов `get(key, handler)` читает метаданные только с обработчика. Вызов `getAllAndOverride(key, [handler, class])` смотрит сначала обработчик, и только если там пусто — класс. Для `@Roles` на контроллере с переопределением на методе нужен именно `getAllAndOverride`.

- **"Reflect.defineMetadata вызывается при каждом запросе"** — нет. Декораторы выполняются **один раз** при старте приложения, когда загружается модуль. Метаданные записываются в память раз и навсегда. `Reflect.getMetadata` в Guard при каждом запросе только читает, и это поиск за O(1).

- **"@SetMetadata можно использовать с любым типом данных"** — да, но с оговоркой. Ключ принято выносить в константу (`export const ROLES_KEY = 'roles'`), чтобы опечатка в строке не превратилась в тихо неработающий Guard. Дженерик `reflector.getAllAndOverride<string[]>` задаёт тип возвращаемого значения.

- **"getHandler() возвращает имя метода"** — нет. Он возвращает ссылку на функцию (`Function`), а не строку. Имя достаётся через `context.getHandler().name`. Саму функцию используют как ключ для `Reflect.getMetadata`, потому что метаданные привязаны к объекту функции.
