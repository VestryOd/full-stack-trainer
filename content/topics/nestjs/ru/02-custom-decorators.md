# Custom Decorators

## Типы декораторов в NestJS

В NestJS четыре вида декораторов: Parameter (извлечь данные из запроса), Method (добавить metadata на метод), Class (добавить metadata на контроллер/провайдер), Property (редко — для сериализации/валидации). Самые полезные для кастомизации: Parameter и Composite (комбинированные через `applyDecorators`).

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

## Decorators для metadata — @Roles, @Public

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

## Composite Decorators — applyDecorators

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

## Parameter Decorator с Pipe валидацией

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
create(@ParsedBody() body: unknown, @ParsedBody('email', new ParseUUIDPipe()) email: string) {
  // ParseUUIDPipe валидирует email поле (если там UUID)
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

## Class Decorator — кастомный @ApiController

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

- **"createParamDecorator — это просто замена @Req()"** — нет. `createParamDecorator` позволяет извлекать любые данные из контекста (не только HTTP request), принимать аргумент (как `@CurrentUser('id')`), и работать с Pipes для валидации/трансформации. Это полноценная точка расширения, не просто alias.

- **"applyDecorators применяет декораторы снизу вверх"** — нет. `applyDecorators([A, B, C])` применяет в порядке A → B → C (сверху вниз, как написано). Это отличается от стекования декораторов через `@A @B @C`, где TypeScript применяет справа налево (C → B → A). В `applyDecorators` порядок предсказуем.

- **"Декораторы выполняются при каждом запросе"** — нет. Декораторы выполняются ОДИН РАЗ при загрузке модуля (startup). Код внутри `createParamDecorator` factory функции выполняется при каждом запросе, но сам декоратор зарегистрирован один раз.

- **"@Roles на классе и на методе складываются"** — зависит от реализации Guard. `reflector.getAllAndOverride` берёт method если есть, иначе class (не складывает). `reflector.getAllAndMerge` объединяет массивы из обоих. Важно знать какой метод использует твой RolesGuard.

- **"Property decorators в NestJS не нужны"** — используются в class-validator (`@IsEmail()`, `@IsNotEmpty()`) и class-transformer (`@Expose()`, `@Transform()`). Эти библиотеки глубоко интегрированы в NestJS ValidationPipe. Property decorators хранят validation rules в metadata через `reflect-metadata`.
