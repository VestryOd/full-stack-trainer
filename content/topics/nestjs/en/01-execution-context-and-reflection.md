# ExecutionContext and Reflection

## What is ExecutionContext

`ExecutionContext` is an abstraction over the current incoming request, available in Guards, Interceptors, and Exception Filters. The abstraction is necessary because NestJS works with multiple transports: HTTP, WebSocket, gRPC, and Microservice RPC. The same Guard must work regardless of the transport.

```typescript
import { CanActivate, ExecutionContext, Injectable } from '@nestjs/common';

@Injectable()
export class AuthGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    // context.getType() → 'http' | 'ws' | 'rpc'
    const type = context.getType();

    // context.getHandler() → the controller method (e.g. getUser)
    const handler = context.getHandler();

    // context.getClass() → the controller class (e.g. UsersController)
    const controllerClass = context.getClass();

    // switchToHttp() → only for the HTTP transport
    const request = context.switchToHttp().getRequest<Request>();
    const response = context.switchToHttp().getResponse<Response>();

    return true;
  }
}
```

```txt
switchTo*() methods:
  context.switchToHttp()  → { getRequest(), getResponse(), getNext() }
  context.switchToWs()    → { getClient(), getData() }
  context.switchToRpc()   → { getContext(), getData() }

Why you can't just call context.getRequest():
  ExecutionContext doesn't know which transport you're on.
  switchToHttp() explicitly states "I know this is an HTTP request."
  On a WebSocket transport, switchToHttp().getRequest() returns undefined.
```

## Reflect Metadata — how decorators store data

Reflect Metadata is a standard for storing metadata on classes and methods at runtime. The `reflect-metadata` library (a polyfill for the Reflect API) is used throughout NestJS.

```typescript
import 'reflect-metadata'; // must be the first import in main.ts

// The @Roles decorator stores roles in metadata on the method/class
export const ROLES_KEY = 'roles';

export const Roles = (...roles: string[]) =>
  SetMetadata(ROLES_KEY, roles);
// SetMetadata under the hood does:
// Reflect.defineMetadata(ROLES_KEY, roles, target, propertyKey)

// A Guard reads metadata via Reflector
@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    // getAllAndOverride: method-level takes priority over class-level
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [
      context.getHandler(), // check on the method first
      context.getClass(),   // then on the class
    ]);

    if (!requiredRoles) return true; // no restriction → allow through

    const { user } = context.switchToHttp().getRequest();
    return requiredRoles.some(role => user?.roles?.includes(role));
  }
}
```

## Working directly with the Reflect API

```typescript
// SetMetadata — NestJS built-in helper (recommended)
export const Public = () => SetMetadata('isPublic', true);

// Manual equivalent:
export function PublicManual(): MethodDecorator {
  return (target, propertyKey) => {
    Reflect.defineMetadata('isPublic', true, target, propertyKey);
  };
}

// Reading via reflector (in a Guard):
const isPublic = this.reflector.getAllAndOverride<boolean>('isPublic', [
  context.getHandler(),
  context.getClass(),
]);

// Reading directly via Reflect (without Reflector):
const roles = Reflect.getMetadata('roles', context.getHandler());

// reflector.get vs reflector.getAllAndOverride:
// .get(key, target) — reads only from the given target
// .getAllAndOverride(key, [method, class]) — reads from method first, then class
// .getAllAndMerge(key, [method, class]) — merges arrays from both (for union roles)
```

## Complete pattern: JWT Auth Guard with @Public()

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
    // Check @Public() on the method OR the controller
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) return true; // skip JWT validation

    return super.canActivate(context); // standard JWT validation
  }
}

// app.module.ts — apply globally
providers: [
  { provide: APP_GUARD, useClass: JwtAuthGuard }, // all endpoints protected by default
],

// auth.controller.ts — public routes
@Public()
@Post('login')
login(@Body() dto: LoginDto) { ... }

// users.controller.ts — protected routes
@Get('profile')  // protected by JwtAuthGuard automatically
getProfile(@Request() req) { return req.user; }
```

## getType() for multi-transport Guards

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

## Common interview mistakes

- **"ExecutionContext is just the request object"** — no. ExecutionContext is a wrapper around the execution context, not the request. `getRequest()` is only one method of the HTTP-specific sub-context. ExecutionContext also gives access to the handler and controller (for metadata reading), and works for WebSocket and RPC.

- **"Reflector.get() and getAllAndOverride() are the same thing"** — no. `get(key, handler)` reads metadata only from the handler. `getAllAndOverride(key, [handler, class])` reads from the handler first; if not found, from the class. For `@Roles` on the controller level with an override on the method level: `getAllAndOverride` is mandatory.

- **"Reflect.defineMetadata is called on every request"** — no. Decorators execute ONCE at application startup (when the module loads). Metadata is written to memory once and for all. `Reflect.getMetadata` in a Guard reads on every request — but it's an O(1) lookup.

- **"@SetMetadata can be used with any data type"** — yes, but the convention is to use a constant for the key (`export const ROLES_KEY = 'roles'`) to avoid typos in strings. The TypeScript generic `reflector.getAllAndOverride<string[]>` ensures the return type.

- **"getHandler() returns the method name"** — no. It returns a function reference (`Function`), not a string. `context.getHandler().name` gives the string name. It's used as the key for `Reflect.getMetadata` because metadata is attached to the function object itself.
