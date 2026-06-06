# Request Scope and Performance

## The Most Popular Senior Interview Question

What happens if you do:

```ts
@Injectable({
 scope: Scope.REQUEST
})
```

---

Most people answer:

```txt
A new object is created for each request
```

---

That's correct.

---

But not enough.

---

# Scope Recap

Nest supports:

```txt
Singleton
Request
Transient
```

---

# Singleton

The default.

---

```ts
@Injectable()
export class UserService {}
```

---

Created:

```txt
1 object
for the entire application
```

---

Diagram:

```txt
Request 1
 ↓
UserService

Request 2
 ↓
same UserService
```

---

# Why Singleton Is Fast

Because:

```txt
the object is created only once
```

---

No:

```txt
new memory allocations
extra GC
```

---

# Request Scope

```ts
@Injectable({
 scope: Scope.REQUEST
})
```

---

Created:

```txt
a new instance
for each request
```

---

Diagram:

```txt
Request 1
 ↓
UserService #1

Request 2
 ↓
UserService #2

Request 3
 ↓
UserService #3
```

---

# What Happens Internally

A very popular interview question.

---

Nest creates:

```txt
a new dependency tree
```

---

For each request.

---

# Example

```txt
UserController
     ↓
UserService
     ↓
AuditService
     ↓
ConfigService
```

---

If UserService becomes Request Scope:

---

Very important:

```txt
AuditService
also becomes
Request Scope
```

---

# Scope Propagation

One of the most important topics.

---

Request Scope propagates upward.

---

Example.

---

```txt
Controller
 ↓
Request Service
 ↓
Singleton Service
```

---

Nest cannot mix:

```txt
Request Instance
```

and

```txt
Singleton Instance
```

---

So it will create a new graph.

---

# Why This Is Expensive

On each request:

```txt
new objects

new dependencies

new references

new GC
```

---

# What Happens at 1000 RPS

```txt
1000 requests
```

---

We get:

```txt
thousands of objects
every second
```

---

GC starts working more often.

---

Latency grows.

---

# When Request Scope Is Justified

A very popular interview question.

---

Examples:

```txt
Current User Context

Tenant Context

Correlation ID

Request Tracing
```

---

# Correlation ID

A very common use case.

---

Each request gets a:

```txt
Request-ID
```

---

It needs to be passed through:

```txt
Controller
Service
Repository
```

---

Then Request Scope is justified.

---

# Multi-Tenant

Another good example.

---

```txt
Tenant A

Tenant B

Tenant C
```

---

On each request:

```txt
different database
different context
```

---

# When It Is NOT Needed

A very popular interview topic.

---

Bad:

```txt
UserService

ProductService

OrderService
```

---

Just because:

```txt
it's more convenient
```

---

This is an anti-pattern.

---

# AsyncLocalStorage

A very modern interview question.

---

In many cases:

```txt
Request Scope
```

can be replaced with:

```txt
AsyncLocalStorage
```

---

Advantage:

```txt
no new objects created
```

---

Better performance.

---

# Transient Scope

The rarest.

---

```ts
Scope.TRANSIENT
```

---

Each injection:

```txt
new object
```

---

Even within the same request.

---

# Example

```txt
A -> Logger #1

B -> Logger #2

C -> Logger #3
```

---

# When Used

Rarely.

---

For example:

```txt
builder objects

temporary helpers
```

---

# Frequent Question

What Scope should be used by default?

Answer:

```txt
Singleton
```

---

Almost always.

---

# Frequent Question

Why can Request Scope be dangerous?

Answer:

Because Nest creates a new dependency graph for each request, leading to additional memory allocations and load on the Garbage Collector.

---

# Interview Answer

Singleton is the most performant Scope and is used by default. Request Scope creates a new provider instance for each request and can significantly increase memory consumption and GC load. It should only be used when a request-specific context is genuinely needed, such as tenant information or correlation id.
