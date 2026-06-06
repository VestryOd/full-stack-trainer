# Custom Decorators

## What is a Decorator

A decorator is a function
that adds metadata
or changes the behavior of a class,
method, parameter, or property.

---

Nest examples:

```ts
@Controller()
@Get()
@Post()
@Inject()
```

---

These are all decorators.

---

# Why Custom Decorators Are Needed

To hide repetitive logic.

---

For example:

```ts
req.user.id
```

appears everywhere.

---

# Without a Decorator

```ts
@Get()
profile(
 @Req() req
) {

 return req.user;
}
```

---

# Creating a User Decorator

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

# Usage

```ts
@Get()
profile(
 @User() user
) {

 return user;
}
```

---

Clean and reusable.

---

# What Happens Under the Hood

Nest calls:

```ts
ExecutionContext
```

---

Extracts:

```ts
request.user
```

---

Passes the value to the method parameter.

---

# Parameter Decorators

The most popular type.

---

Examples:

```ts
@Body()
@Param()
@Query()
@Headers()
```

---

All work the same way.

---

# Method Decorators

Attached to a method.

---

Example:

```ts
@Roles('admin')
```

---

Creating:

```ts
export const Roles =
 (...roles: string[]) =>
  SetMetadata(
   'roles',
   roles
  );
```

---

# What SetMetadata Does

Under the hood:

```ts
Reflect.defineMetadata(...)
```

---

# Usage

```ts
@Roles('admin')
@Get()
users()
```

---

# Guard Reads Metadata

```ts
this.reflector.get(
 'roles',
 context.getHandler()
);
```

---

# Composite Decorators

A very popular Senior interview question.

---

Decorators can be combined.

---

Example:

```ts
@Auth()
```

---

Internally:

```ts
UseGuards(...)
ApiBearerAuth()
Roles(...)
```

---

# Implementation

```ts
export function Auth() {

 return applyDecorators(
  UseGuards(AuthGuard),
  ApiBearerAuth()
 );
}
```

---

# Why This Is Convenient

Instead of:

```ts
@UseGuards(...)
@ApiBearerAuth()
@Roles(...)
```

---

We get:

```ts
@Auth()
```

---

# Class Decorators

Attached to a class.

---

Example:

```ts
@Controller()
```

---

# Property Decorators

Rarely used.

---

Typically for:

```ts
Validation
Serialization
```

---

# Frequent Question

How does a decorator differ from middleware?

---

Decorator:

```txt
adds metadata
```

---

Middleware:

```txt
processes the request
```

---

# Frequent Question

How does @Roles() work?

Answer:

@Roles uses SetMetadata and stores the list of roles in the method's metadata. Then the Roles Guard reads this metadata via the Reflector and checks the user's permissions.

---

# Interview Answer

Custom Decorators allow encapsulating repetitive logic and working with NestJS metadata. They are commonly used to extract data from the request, store roles, and create compositions of multiple decorators via applyDecorators.
