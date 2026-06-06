# ExecutionContext and Reflection

## The Most Underrated Topic in NestJS

Many people use:

```ts
@UseGuards()
@Roles()
@Auth()
```

---

But don't understand:

```txt
how this works under the hood
```

---

To understand it, you need to know:

```txt
ExecutionContext
Reflect Metadata
```

---

# What is ExecutionContext

ExecutionContext describes:

```txt
the context of the current request
```

---

Simplified:

```txt
who called
what was called
what arguments
which handler
which controller
```

---

# Where It Is Used

Practically everywhere.

---

For example:

```txt
Guards
Interceptors
Filters
Custom Decorators
```

---

# Example

```ts
canActivate(
  context: ExecutionContext
)
```

---

Every Guard receives:

```ts
ExecutionContext
```

---

# What You Can Get

Handler:

```ts
context.getHandler()
```

---

Controller:

```ts
context.getClass()
```

---

# HTTP Context

The most common use case.

---

```ts
const req =
  context
    .switchToHttp()
    .getRequest();
```

---

Now accessible:

```ts
req.user
req.headers
req.params
```

---

# Why switchToHttp()

A very popular interview question.

---

Nest supports:

```txt
HTTP
GraphQL
WebSockets
Microservices
```

---

Therefore the context is abstract.

---

You need to explicitly switch.

---

# Other Options

```ts
switchToWs()
```

---

```ts
switchToRpc()
```

---

# getHandler()

A very popular interview topic.

---

Returns:

```txt
the current method
```

---

For example:

```ts
@Get()
findUsers()
```

---

Will return:

```txt
findUsers
```

---

# getClass()

Returns:

```txt
the controller
```

---

For example:

```ts
UsersController
```

---

# What is Reflection

The next important topic.

---

Reflection allows:

```txt
reading metadata
at runtime
```

---

# Metadata

Additional data
that we attach to a class
or method.

---

Example:

```ts
@Roles('admin')
```

---

Somewhere we need to store:

```txt
admin
```

---

Metadata is used for this.

---

# Under the Hood

Example.

---

```ts
Reflect.defineMetadata(
  'roles',
  ['admin'],
  target
);
```

---

Later:

```ts
Reflect.getMetadata(
  'roles',
  target
);
```

---

# Why This Matters

Almost all of Nest is built around metadata.

---

For example:

```txt
@Controller
@Get
@Post
@Roles
@UseGuards
@Inject
```

---

All use metadata.

---

# Reflector

A special Nest service.

---

Used to read metadata.

---

```ts
constructor(
 private reflector: Reflector
) {}
```

---

Example:

```ts
const roles =
 this.reflector.get(
   'roles',
   context.getHandler()
 );
```

---

# Frequent Question

How does @Roles() work?

Answer:

The decorator saves the roles in metadata via Reflect Metadata. Then the Guard reads this metadata via the Reflector and makes the access decision.

---

# Interview Answer

ExecutionContext provides information about the current request and is used in Guards, Interceptors and Filters. Reflect Metadata allows storing additional data on classes and methods. Most NestJS decorators work through the metadata mechanism and are read at runtime via the Reflector service.
