# Providers, Scopes and DI Container

## The Most Important Idea in NestJS

Practically all of Nest is built around:

```txt
Dependency Injection
```

---

# What is a Dependency

Example.

---

```ts
class UserService {

  constructor(
    private db: DatabaseService
  ) {}
}
```

---

Here:

```txt
DatabaseService
```

is a dependency.

---

# Without DI

We create it manually.

---

```ts
const db =
 new DatabaseService();

const service =
 new UserService(db);
```

---

Drawbacks:

```txt
tight coupling
hard to test
hard to swap implementations
```

---

# With DI

```ts
constructor(
 private db: DatabaseService
) {}
```

---

Nest will create the object itself.

---

# What is the DI Container

The most popular topic.

---

Simplified:

```txt
Map<Token, Instance>
```

---

For example:

```txt
UserService
 ↓
instance

DatabaseService
 ↓
instance
```

---

At application startup, Nest builds:

```txt
Dependency Graph
```

---

# Dependency Graph

Example.

---

```txt
UserController
      ↓
UserService
      ↓
DatabaseService
```

---

Nest analyzes:

```txt
constructor()
```

---

And determines:

```txt
who needs to be created first
```

---

# What Happens at Startup

Step 1

Scanning:

```txt
Modules
Providers
Controllers
```

---

Step 2

Creating the Dependency Graph.

---

Step 3

Creating instances.

---

Step 4

Saving to the Container.

---

# Provider

A very popular interview question.

---

A Provider is any object
that can participate in DI.

---

For example:

```ts
@Injectable()
export class UserService {}
```

---

This is a Provider.

---

# Provider Token

The most underrated topic.

---

Under the hood, Nest doesn't look for a class.

---

It looks for a:

```txt
Token
```

---

Usually the token is the class itself.

---

For example:

```ts
UserService
```

---

Effectively:

```txt
Token → Instance
```

---

# Simplified Diagram

```txt
UserService
 ↓
new UserService()
```

---

Stored in the container.

---

# Injection

```ts
constructor(
 private userService:
 UserService
)
```

---

Nest looks for:

```txt
Token = UserService
```

---

Finds the instance.

---

Passes it to the constructor.

---

# Custom Token

A very popular interview topic.

---

You can use a string.

---

```ts
{
 provide: 'API_URL',
 useValue: 'https://...'
}
```

---

Injection:

```ts
@Inject('API_URL')
private url: string
```

---

# useClass

The simplest option.

---

```ts
{
 provide: UserRepository,
 useClass: PrismaRepository
}
```

---

Which means:

```txt
when UserRepository is requested
create PrismaRepository
```

---

# useValue

A ready-made value.

---

```ts
{
 provide: 'CONFIG',
 useValue: {
  port: 3000
 }
}
```

---

Often used for:

```txt
config
constants
mocks
```

---

# useFactory

A very popular interview question.

---

Allows creating an object dynamically.

---

```ts
{
 provide: DatabaseClient,

 useFactory: () => {

  return new PrismaClient();
 }
}
```

---

# useFactory with Dependencies

```ts
{
 provide: ApiClient,

 inject: [ConfigService],

 useFactory: (config) => {

  return new ApiClient(
   config.get('url')
  );
 }
}
```

---

Very commonly used.

---

# useExisting

Less popular.

---

```ts
{
 provide: UserRepo,
 useExisting:
 PrismaRepo
}
```

---

Both tokens will point
to the same object.

---

# Scopes

A very popular Senior interview question.

---

# Singleton

The default.

---

Created:

```txt
one instance
for the entire application
```

---

```ts
@Injectable()
export class UserService {}
```

---

Singleton.

---

# Request Scope

```ts
@Injectable({
 scope: Scope.REQUEST
})
```

---

A new instance is created:

```txt
for each request
```

---

# Example

```txt
Request 1
 ↓
UserService #1

Request 2
 ↓
UserService #2
```

---

# Transient Scope

The rarest.

---

```ts
Scope.TRANSIENT
```

---

A new instance for:

```txt
each injection
```

---

# When Request Scope Is Justified

For example:

```txt
Tenant Context
Current User Context
Correlation ID
Request Tracing
```

---

# Why Request Scope Is Dangerous

A very popular interview question.

---

Because:

```txt
thousands of objects are created
```

---

Higher load on the GC.

---

Therefore:

```txt
Singleton
```

is preferred.

---

# Frequent Question

Why does DI make code better?

---

Answer:

It allows inverting dependencies, reduces coupling between components, simplifies testing and swapping implementations.

---

# Interview Answer

NestJS uses a Dependency Injection Container that stores objects by tokens and automatically resolves dependencies through constructors. Providers are the core elements of the container and can be created via useClass, useValue, useFactory, and useExisting. By default, all providers are Singletons, but Request and Transient Scopes are also supported.
