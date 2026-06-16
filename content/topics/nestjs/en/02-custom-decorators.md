# Custom Decorators

## Types of decorators in NestJS

NestJS has four kinds of decorators: Parameter (extract data from the request), Method (attach metadata to a method), Class (attach metadata to a controller/provider), Property (rarely — for serialization/validation). The most useful for customization: Parameter and Composite (combined via `applyDecorators`).

```typescript
// 1. Parameter Decorator — createParamDecorator
// Get the current user from the request without @Req()
export const CurrentUser = createParamDecorator(
  (data: keyof User | undefined, ctx: ExecutionContext) => {
    const request = ctx.switchToHttp().getRequest();
    const user = request.user as User;

    // data — the decorator argument: @CurrentUser('id') → returns only user.id
    return data ? user?.[data] : user;
  },
);

// Usage:
@Get('profile')
getProfile(@CurrentUser() user: User) {
  return user; // the full user object
}

@Get('me')
getMe(@CurrentUser('id') userId: number) {
  return userId; // only user.id
}
```

## Metadata decorators — @Roles, @Public

```typescript
// Method/Class decorator via SetMetadata
export const ROLES_KEY = 'roles';
export const Roles = (...roles: Role[]) => SetMetadata(ROLES_KEY, roles);

export const IS_PUBLIC_KEY = 'isPublic';
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);

// Usage:
@Controller('admin')
@Roles(Role.ADMIN) // apply to the whole controller
export class AdminController {
  @Get('users')
  @Roles(Role.ADMIN, Role.SUPER_ADMIN) // override for this method
  getUsers() { ... }

  @Get('stats')
  @Public() // public route inside a protected controller
  getPublicStats() { ... }
}

// RolesGuard reads both decorators:
const roles = this.reflector.getAllAndOverride<Role[]>(ROLES_KEY, [
  context.getHandler(), // method takes priority
  context.getClass(),
]);
```

## Composite Decorators — applyDecorators

```typescript
// Instead of duplicating 4 decorators on every endpoint — one @Auth()
import { applyDecorators, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiUnauthorizedResponse } from '@nestjs/swagger';

export function Auth(...roles: Role[]) {
  return applyDecorators(
    SetMetadata(ROLES_KEY, roles),       // metadata for roles
    UseGuards(JwtAuthGuard, RolesGuard), // guards in the correct order
    ApiBearerAuth(),                      // Swagger documentation
    ApiUnauthorizedResponse({ description: 'Unauthorized' }),
  );
}

// Before:
@UseGuards(JwtAuthGuard, RolesGuard)
@SetMetadata('roles', [Role.ADMIN])
@ApiBearerAuth()
@ApiUnauthorizedResponse({ description: 'Unauthorized' })
@Get('users')
getUsers() { ... }

// After:
@Auth(Role.ADMIN)
@Get('users')
getUsers() { ... }
```

## Parameter Decorator with Pipe validation

```typescript
// createParamDecorator returns raw data — Pipes can be applied
export const ParsedBody = createParamDecorator(
  (key: string | undefined, ctx: ExecutionContext) => {
    const body = ctx.switchToHttp().getRequest().body;
    return key ? body?.[key] : body;
  },
);

// With a Pipe:
@Post()
create(@ParsedBody() body: unknown, @ParsedBody('email', new ParseUUIDPipe()) email: string) {
  // ParseUUIDPipe validates the email field (if it's a UUID)
}

// More realistic example — header with parsing:
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

## Class Decorator — custom @ApiController

```typescript
// Composite class decorator for Swagger + global prefix
import { Controller, applyDecorators } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';

export function ApiController(prefix: string, tag?: string) {
  return applyDecorators(
    Controller(prefix),
    ApiTags(tag ?? prefix),
  );
}

// Usage:
@ApiController('users', 'Users Management')
export class UsersController { ... }

// Equivalent to:
@Controller('users')
@ApiTags('Users Management')
export class UsersController { ... }
```

## Decorators and TypeScript — how they work

```typescript
// Decorators are just functions called when the class loads
// TypeScript compiles @Decorator into:
//   Decorator(target, propertyKey, descriptor)

// Method decorator (manual implementation):
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

// Usage:
@Log()
@Get(':id')
async findOne(@Param('id') id: string) {
  return this.usersService.findOne(+id);
}
// On every request: logs the call and the result
```

## Common interview mistakes

- **"createParamDecorator is just a replacement for @Req()"** — no. `createParamDecorator` lets you extract any data from the context (not just the HTTP request), accept an argument (like `@CurrentUser('id')`), and work with Pipes for validation/transformation. It's a full extension point, not just an alias.

- **"applyDecorators applies decorators bottom-up"** — no. `applyDecorators([A, B, C])` applies in order A → B → C (top-down, as written). This differs from stacking decorators with `@A @B @C`, where TypeScript applies right-to-left (C → B → A). With `applyDecorators`, the order is predictable.

- **"Decorators run on every request"** — no. Decorators execute ONCE when the module loads (at startup). The code inside the `createParamDecorator` factory function runs per request, but the decorator itself is registered only once.

- **"@Roles on the class and on the method are added together"** — depends on the Guard implementation. `reflector.getAllAndOverride` takes the method value if present, otherwise the class value (it does not merge). `reflector.getAllAndMerge` combines arrays from both. It's important to know which method your RolesGuard uses.

- **"Property decorators aren't needed in NestJS"** — they are used in class-validator (`@IsEmail()`, `@IsNotEmpty()`) and class-transformer (`@Expose()`, `@Transform()`). These libraries are deeply integrated into NestJS ValidationPipe. Property decorators store validation rules in metadata via `reflect-metadata`.
