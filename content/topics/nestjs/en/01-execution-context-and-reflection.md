# ExecutionContext and Reflection

## What is ExecutionContext

`ExecutionContext` is a wrapper around the current incoming request. Three Nest mechanisms that plug into request handling receive it:

- **Guard** — decides whether the request reaches the handler or is rejected.
- **Interceptor** — wraps the handler call and can change the response.
- **Exception Filter** — turns a thrown exception into a response for the client.

The wrapper exists because NestJS works with several transports. A transport is the channel a request arrives on: HTTP, WebSocket, gRPC, or a microservice RPC message. RPC (remote procedure call) means calling a method on another service over the network.

The same Guard has to work on any transport. That is why it receives an `ExecutionContext` and not a raw `req`.

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
  switchToHttp() → { getRequest(), getResponse(), getNext() }
  switchToWs()   → { getClient(), getData() }
  switchToRpc()  → { getContext(), getData() }

Why you can't just call context.getRequest():
  ExecutionContext doesn't know which transport you're on.
  switchToHttp() states explicitly: "this is an HTTP request".
  On WebSocket, switchToHttp().getRequest() returns undefined.
```

## Reflect Metadata — how decorators store data

Reflect Metadata is a standard for storing metadata on classes and methods at runtime. Metadata here means data about your code: for example, the list of roles that `@Roles('admin')` attaches to a method.

NestJS uses the `reflect-metadata` library for this. It is a polyfill, that is, an implementation of the standard for engines that do not have it yet. The decorator writes the metadata, and a Guard reads it through `Reflector`.

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

`SetMetadata` is a thin wrapper over `Reflect.defineMetadata`, and you can write the same thing by hand. The example below shows four ways to work with the same metadata. They are the built-in helper, a manual decorator, reading through `Reflector`, and reading straight from `Reflect`.

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

JWT (JSON Web Token) is a signed token that the client sends in the `Authorization` header. A practical approach is to check the token on every route, and mark the rare exceptions with a `@Public()` decorator.

Then you cannot forget to protect a route: everything is closed by default, and a public route is visible in the code.

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

## getType() — one Guard for several transports

`context.getType()` returns `'http' | 'ws' | 'rpc'` and tells you which transport the request came in on. The Guard looks at that value and picks the matching `switchTo*()`.

Without this check a universal Guard breaks on the first non-HTTP request: `switchToHttp().getRequest()` returns `undefined` instead of an error.

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

- **"ExecutionContext is just the request object"** — no. It wraps the execution context, not the request. `getRequest()` belongs to the HTTP-specific sub-context only. Besides the request, `ExecutionContext` gives you the handler and the controller class so you can read metadata, and it works for WebSocket and RPC.

- **"Reflector.get() and getAllAndOverride() are the same thing"** — no. The call `get(key, handler)` reads metadata only from the handler. The call `getAllAndOverride(key, [handler, class])` reads the handler first, and falls back to the class only if the handler has nothing. For `@Roles` on the controller with an override on the method, you need `getAllAndOverride`.

- **"Reflect.defineMetadata is called on every request"** — no. Decorators run **once** at application startup, when the module loads. Metadata is written to memory once and for all. `Reflect.getMetadata` in a Guard only reads on each request, and that read is an O(1) lookup.

- **"@SetMetadata can be used with any data type"** — yes, with one caveat. Keep the key in a constant: `export const ROLES_KEY = 'roles'`. Then a typo in a string cannot turn into a Guard that silently does nothing. The generic `reflector.getAllAndOverride<string[]>` fixes the return type.

- **"getHandler() returns the method name"** — no. It returns a function reference (`Function`), not a string. You get the name from `context.getHandler().name`. The function itself is used as the key for `Reflect.getMetadata`, because metadata is attached to the function object.
