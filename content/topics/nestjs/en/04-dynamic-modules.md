# Dynamic Modules

## A Very Popular Senior Interview Question

A regular Module:

```ts
@Module({
 providers: [...]
})
```

---

Is static.

---

The configuration is known in advance.

---

But what if you need:

```txt
configuration
from environment
from runtime
from an external API
```

---

Solution:

```txt
Dynamic Module
```

---

# What is a Dynamic Module

A module
that can generate
its configuration dynamically.

---

# The Most Well-Known Example

```ts
ConfigModule.forRoot()
```

---

You have certainly used it.

---

```ts
ConfigModule.forRoot({
 isGlobal: true
})
```

---

This is a Dynamic Module.

---

# Why

Because:

```txt
@Module(...)
```

is generated at runtime.

---

# Structure

```ts
static forRoot()
: DynamicModule
```

---

Example.

---

```ts
@Module({})
export class DatabaseModule {

 static forRoot(
  options
 ): DynamicModule {

  return {

   module:
    DatabaseModule,

   providers: [...]
  };
 }
}
```

---

# Usage

```ts
DatabaseModule.forRoot({
 host: 'localhost'
})
```

---

# What It Returns

Very important.

---

DynamicModule:

```ts
{
 module,
 providers,
 exports,
 imports
}
```

---

Effectively:

```txt
we are dynamically creating @Module
```

---

# Why This Is Needed

Allows:

```txt
passing settings
when importing the module
```

---

# Real Example

```ts
JwtModule.register({
 secret: '123'
})
```

---

This is a Dynamic Module.

---

# register()

A very common pattern.

---

```ts
Module.register()
```

---

Used when:

```txt
the config is known immediately
```

---

# registerAsync()

Even more popular.

---

```ts
JwtModule.registerAsync(...)
```

---

Used when:

```txt
you need to wait for dependencies
```

---

For example:

```txt
ConfigService
Vault
AWS Secrets
```

---

# Example

```ts
JwtModule.registerAsync({

 inject: [ConfigService],

 useFactory: (config) => ({

  secret:
   config.get('JWT_SECRET')

 })
})
```

---

# Why registerAsync Is Important

At startup:

```txt
ConfigService is already created
```

---

And we can use it.

---

# Global Dynamic Module

A very popular interview question.

---

You can make it:

```ts
@Global()
```

---

Then:

```txt
no need to import it
in every module
```

---

# forFeature()

Another popular pattern.

---

For example:

```ts
TypeOrmModule.forFeature(...)
```

---

Used for:

```txt
local registration of
repository
entity
feature providers
```

---

# Difference

forRoot:

```txt
once
for the entire application
```

---

forFeature:

```txt
for a specific module
```

---

# Frequent Question

Why is a Dynamic Module better than a regular Module?

---

Answer:

It allows passing configuration at import time and creating providers dynamically.

---

# Frequent Question

What built-in Dynamic Modules do you know?

---

For example:

```txt
ConfigModule.forRoot()
JwtModule.register()
TypeOrmModule.forRoot()
GraphQLModule.forRoot()
```

---

# Frequent Question

When should registerAsync be used?

---

When the configuration depends on other providers.

---

For example:

```txt
ConfigService
Secrets Manager
Vault
```

---

# Interview Answer

A Dynamic Module is a module that is created dynamically at runtime and can accept configuration through methods like forRoot, register, or registerAsync. This mechanism is actively used in built-in NestJS modules such as ConfigModule, JwtModule, and GraphQLModule.
