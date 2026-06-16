# ExecutionContext и Reflection

## Что такое ExecutionContext

`ExecutionContext` — абстракция над текущим входящим запросом, доступная в Guards, Interceptors и Exception Filters. Абстракция нужна потому что NestJS работает с несколькими транспортами: HTTP, WebSocket, gRPC, Microservice RPC. Один и тот же Guard должен работать независимо от транспорта.

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
  context.switchToHttp()  → { getRequest(), getResponse(), getNext() }
  context.switchToWs()    → { getClient(), getData() }
  context.switchToRpc()   → { getContext(), getData() }

Почему нельзя сразу context.getRequest():
  ExecutionContext не знает на каком транспорте ты работаешь.
  switchToHttp() явно заявляет "я знаю что это HTTP запрос".
  На WebSocket транспорте switchToHttp().getRequest() вернёт undefined.
```

## Reflect Metadata — как декораторы хранят данные

Reflect Metadata — стандарт для хранения метаданных на классах и методах во время выполнения. Библиотека `reflect-metadata` (polyfill для Reflect API) используется NestJS повсеместно.

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

## getType() для multi-transport Guards

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

- **"ExecutionContext — это просто request объект"** — нет. ExecutionContext — обёртка над контекстом выполнения, не над запросом. `getRequest()` — это один из методов только HTTP-контекста. ExecutionContext также даёт доступ к handler и controller (для metadata чтения), и работает для WebSocket и RPC.

- **"Reflector.get() и getAllAndOverride() — одно и то же"** — нет. `get(key, handler)` читает metadata только с handler. `getAllAndOverride(key, [handler, class])` — читает сначала с handler, если нет — с class. Для `@Roles` на уровне контроллера + override на уровне метода: `getAllAndOverride` нужен обязательно.

- **"Reflect.defineMetadata вызывается при каждом запросе"** — нет. Декораторы выполняются ОДИН РАЗ при старте приложения (при загрузке модуля). Metadata записывается в память раз и навсегда. `Reflect.getMetadata` в Guard при каждом запросе только читает — это O(1) lookup.

- **"@SetMetadata можно использовать с любым типом данных"** — да, но стандарт: использовать константу для ключа (`export const ROLES_KEY = 'roles'`) во избежание typo в строках. TypeScript дженерик `reflector.getAllAndOverride<string[]>` гарантирует тип возвращаемого значения.

- **"getHandler() возвращает имя метода"** — нет. Возвращает функцию-reference (`Function`), не строку. `context.getHandler().name` — даст строку с именем. Используется как ключ для `Reflect.getMetadata` потому что metadata привязана к объекту функции.
