# Кастомные декораторы

## Типы декораторов в NestJS

В NestJS четыре вида декораторов, и различаются они тем, к чему декоратор прикрепляется:

- **Parameter** — стоит у аргумента метода и извлекает данные из запроса.
- **Method** — добавляет метаданные на метод контроллера.
- **Class** — добавляет метаданные на класс: контроллер или провайдер.
- **Property** — стоит у поля класса. Нужен редко, в основном для сериализации и валидации.

Есть и пятый вариант, собранный из остальных: Composite — несколько декораторов, склеенных вместе через `applyDecorators`. Для кастомизации чаще всего пишут Parameter и Composite, поэтому статья идёт по ним подробно.

```typescript
// 1. Parameter Decorator — createParamDecorator
// Получить текущего пользователя из request без @Req()
export const CurrentUser = createParamDecorator(
  (data: keyof User | undefined, ctx: ExecutionContext) => {
    const request = ctx.switchToHttp().getRequest();
    const user = request.user as User;

    // data — аргумент декоратора: @CurrentUser('id') → вернёт только user.id
    return data ? user?.[data] : user;
  },
);

// Использование:
@Get('profile')
getProfile(@CurrentUser() user: User) {
  return user; // весь объект user
}

@Get('me')
getMe(@CurrentUser('id') userId: number) {
  return userId; // только user.id
}
```

## Декораторы метаданных — @Roles и @Public

Такой декоратор ничего не проверяет сам. Он только помечает метод или контроллер, а решение принимает Guard, который эту метку читает.

Метку создаёт хелпер `SetMetadata(ключ, значение)`. Ключ выносят в константу, чтобы декоратор и Guard не разошлись из-за опечатки в строке.

```typescript
// Method/Class decorator через SetMetadata
export const ROLES_KEY = 'roles';
export const Roles = (...roles: Role[]) => SetMetadata(ROLES_KEY, roles);

export const IS_PUBLIC_KEY = 'isPublic';
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);

// Использование:
@Controller('admin')
@Roles(Role.ADMIN) // применить ко всему контроллеру
export class AdminController {
  @Get('users')
  @Roles(Role.ADMIN, Role.SUPER_ADMIN) // переопределить для метода
  getUsers() { ... }

  @Get('stats')
  @Public() // публичный маршрут внутри защищённого контроллера
  getPublicStats() { ... }
}

// RolesGuard читает оба декоратора:
const roles = this.reflector.getAllAndOverride<Role[]>(ROLES_KEY, [
  context.getHandler(), // метод приоритетнее
  context.getClass(),
]);
```

## Составные декораторы — applyDecorators

`applyDecorators` склеивает несколько декораторов в один. Это лечит частую боль: у каждого защищённого эндпоинта стоят одни и те же четыре строки, и одну из них однажды забывают написать.

Собрав их в `@Auth(Role.ADMIN)`, вы получаете одну точку правки: добавили в набор новый декоратор — он появился на всех эндпоинтах сразу.

```typescript
// Вместо дублирования 4 декораторов на каждом endpoint — один @Auth()
import { applyDecorators, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiUnauthorizedResponse } from '@nestjs/swagger';

export function Auth(...roles: Role[]) {
  return applyDecorators(
    SetMetadata(ROLES_KEY, roles),      // metadata для ролей
    UseGuards(JwtAuthGuard, RolesGuard), // guards в правильном порядке
    ApiBearerAuth(),                     // Swagger документация
    ApiUnauthorizedResponse({ description: 'Unauthorized' }),
  );
}

// До:
@UseGuards(JwtAuthGuard, RolesGuard)
@SetMetadata('roles', [Role.ADMIN])
@ApiBearerAuth()
@ApiUnauthorizedResponse({ description: 'Unauthorized' })
@Get('users')
getUsers() { ... }

// После:
@Auth(Role.ADMIN)
@Get('users')
getUsers() { ... }
```

## Parameter-декоратор вместе с Pipe

`createParamDecorator` возвращает сырое значение, поэтому проверять его должен Pipe. Pipe в NestJS — это шаг, который валидирует или преобразует входные данные перед тем, как они попадут в аргумент метода.

Pipe передают вторым аргументом декоратора, ровно как встроенным `@Param` и `@Body`. Например, `ParseUUIDPipe` требует, чтобы значение было UUID (universally unique identifier) — идентификатором вида `550e8400-e29b-41d4-a716-446655440000`.

```typescript
// createParamDecorator возвращает сырые данные — Pipes можно навесить
export const ParsedBody = createParamDecorator(
  (key: string | undefined, ctx: ExecutionContext) => {
    const body = ctx.switchToHttp().getRequest().body;
    return key ? body?.[key] : body;
  },
);

// С Pipe:
@Post()
create(
  @ParsedBody() body: unknown,
  @ParsedBody('userId', new ParseUUIDPipe()) userId: string,
) {
  // ParseUUIDPipe проверит, что body.userId — валидный UUID
}

// Более реалистичный пример — заголовок с парсингом:
export const ClientVersion = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): string | undefined => {
    const req = ctx.switchToHttp().getRequest();
    return req.headers['x-client-version'];
  },
);

@Get()
getData(@ClientVersion() version: string) {
  console.log('Client version:', version);
}
```

## Class-декоратор — свой @ApiController

Class-декоратор навешивают на класс целиком, и `applyDecorators` работает с ним так же, как с методами. Типичный случай — контроллер, у которого всегда есть и путь, и тег для Swagger.

`@ApiController('users', 'Users Management')` ставит оба сразу и заодно задаёт правило: имя тега по умолчанию равно префиксу пути.

```typescript
// Composite class decorator для Swagger + global prefix
import { Controller, applyDecorators } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';

export function ApiController(prefix: string, tag?: string) {
  return applyDecorators(
    Controller(prefix),
    ApiTags(tag ?? prefix),
  );
}

// Использование:
@ApiController('users', 'Users Management')
export class UsersController { ... }

// Эквивалент:
@Controller('users')
@ApiTags('Users Management')
export class UsersController { ... }
```

## Декораторы и TypeScript — как они работают

Декоратор — это обычная функция, которую TypeScript вызывает один раз, когда загружается класс. Ей передают сам класс или его метод, и она может дописать метаданные или подменить метод.

Пример ниже подменяет: `Log()` забирает исходную функцию из `descriptor.value`, оборачивает её в свою и возвращает изменённый дескриптор.

```typescript
// Декораторы — это просто функции, вызываемые при загрузке класса
// TypeScript компилирует @Decorator в:
//   Decorator(target, propertyKey, descriptor)

// Method decorator (ручная реализация):
export function Log(): MethodDecorator {
  return (target, propertyKey, descriptor: PropertyDescriptor) => {
    const originalMethod = descriptor.value;

    descriptor.value = async function (...args: unknown[]) {
      console.log(`[${String(propertyKey)}] called with:`, args);
      const result = await originalMethod.apply(this, args);
      console.log(`[${String(propertyKey)}] returned:`, result);
      return result;
    };

    return descriptor;
  };
}

// Использование:
@Log()
@Get(':id')
async findOne(@Param('id') id: string) {
  return this.usersService.findOne(+id);
}
// При каждом запросе: логирует вызов и результат
```

## Типичные ошибки на интервью

- **"createParamDecorator — это просто замена @Req()"** — нет. Он извлекает любые данные из контекста, не только из HTTP-запроса. Он принимает аргумент, как `@CurrentUser('id')`. И он работает с Pipes, то есть значение можно проверить и преобразовать. Это полноценная точка расширения, а не псевдоним для `@Req()`.

- **"applyDecorators применяет декораторы снизу вверх"** — нет. `applyDecorators(A, B, C)` применяет их в порядке A → B → C, то есть как написано. Стек `@A @B @C` ведёт себя иначе: TypeScript применяет его справа налево, C → B → A. В `applyDecorators` порядок предсказуемый.

- **"Декораторы выполняются при каждом запросе"** — нет. Сам декоратор выполняется **один раз** при загрузке модуля, то есть на старте. При каждом запросе выполняется другое: функция внутри `createParamDecorator`, которая достаёт значение из контекста.

- **"@Roles на классе и на методе складываются"** — зависит от реализации Guard. Метод `reflector.getAllAndOverride` берёт значение с метода, если оно есть, иначе с класса, и ничего не складывает. Метод `reflector.getAllAndMerge` объединяет массивы с обоих. Важно знать, какой из двух вызывает ваш RolesGuard.

- **"Property decorators в NestJS не нужны"** — нужны. На них построены class-validator (`@IsEmail()`, `@IsNotEmpty()`) и class-transformer (`@Expose()`, `@Transform()`), а обе библиотеки встроены в ValidationPipe. Правила валидации эти декораторы хранят в метаданных через `reflect-metadata`.
