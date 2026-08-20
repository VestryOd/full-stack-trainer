# Custom Decorators

## Types of decorators in NestJS

NestJS has four kinds of decorators, and what separates them is what the decorator attaches to:

- **Parameter** — sits on a method argument and extracts data from the request.
- **Method** — attaches metadata to a controller method.
- **Class** — attaches metadata to a class: a controller or a provider.
- **Property** — sits on a class field. Rarely needed, mostly for serialization and validation.

There is a fifth option built out of the others: Composite — several decorators glued together with `applyDecorators`. For customization you mostly write Parameter and Composite decorators, so this article covers those two in detail.

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

## Metadata decorators — @Roles and @Public

A metadata decorator checks nothing by itself. It only marks a method or a controller, and the decision is made by a Guard that reads the mark.

The mark is created by the `SetMetadata(key, value)` helper. Keep the key in a constant, so the decorator and the Guard cannot drift apart because of a typo in a string.

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

## Composite decorators — applyDecorators

`applyDecorators` glues several decorators into one. That fixes a common pain: every protected endpoint carries the same four lines, and one day one of those lines is missing.

Pack them into `@Auth(Role.ADMIN)` and you get a single place to edit. Add a decorator to the set, and it appears on every endpoint at once.

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

## Parameter decorators together with a Pipe

`createParamDecorator` returns a raw value, so checking it is a Pipe's job. A Pipe in NestJS is the step that validates or converts incoming data before it reaches the method argument.

You pass the Pipe as the decorator's second argument, exactly as with the built-in `@Param` and `@Body`. For example, `ParseUUIDPipe` requires the value to be a UUID (universally unique identifier) — an id shaped like `550e8400-e29b-41d4-a716-446655440000`.

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
create(
  @ParsedBody() body: unknown,
  @ParsedBody('userId', new ParseUUIDPipe()) userId: string,
) {
  // ParseUUIDPipe checks that body.userId is a valid UUID
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

## Class decorators — your own @ApiController

A class decorator is attached to the whole class, and `applyDecorators` works there just as it does on methods. The typical case is a controller that always needs both a route prefix and a Swagger tag.

`@ApiController('users', 'Users Management')` sets both at once, and it also fixes a rule: by default the tag name equals the route prefix.

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

A decorator is an ordinary function that TypeScript calls once, when the class loads. It receives the class or one of its methods, and it can either write metadata or replace the method.

The example below replaces one: `Log()` takes the original function out of `descriptor.value`, wraps it in its own function, and returns the changed descriptor.

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

- **"createParamDecorator is just a replacement for @Req()"** — no. It extracts any data from the context, not only from the HTTP request. It accepts an argument, as in `@CurrentUser('id')`. And it works with Pipes, so the value can be validated and converted. It is a real extension point, not an alias for `@Req()`.

- **"applyDecorators applies decorators bottom-up"** — no. `applyDecorators(A, B, C)` applies them in the order A → B → C, as written. A stack of `@A @B @C` behaves differently: TypeScript applies it right to left, C → B → A. With `applyDecorators` the order is predictable.

- **"Decorators run on every request"** — no. The decorator itself runs **once** when the module loads, at startup. What runs per request is something else: the function inside `createParamDecorator` that pulls the value out of the context.

- **"@Roles on the class and on the method are added together"** — it depends on the Guard. The `reflector.getAllAndOverride` call takes the method value if there is one, otherwise the class value, and merges nothing. The `reflector.getAllAndMerge` call combines the arrays from both. You need to know which of the two your RolesGuard uses.

- **"Property decorators aren't needed in NestJS"** — they are. Both class-validator (`@IsEmail()`, `@IsNotEmpty()`) and class-transformer (`@Expose()`, `@Transform()`) are built on them. Both libraries are wired into ValidationPipe. These decorators store validation rules in metadata via `reflect-metadata`.
