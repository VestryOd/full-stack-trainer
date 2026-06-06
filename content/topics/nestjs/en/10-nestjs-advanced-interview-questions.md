# NestJS Advanced Interview Questions

---

# 1. What is NestJS?

A progressive Node.js framework
built on top of:

```txt
Express
or
Fastify
```

---

Uses:

```txt
Dependency Injection

Modules

Decorators
```

---

# 2. What happens inside NestFactory.create()?

1. Module scanning.
2. Building the Dependency Graph.
3. Registering Providers.
4. Creating Singleton objects.
5. Starting the HTTP Adapter.

---

# 3. What is Dependency Injection?

Passing dependencies from the outside through a container.

---

# 4. What is the DI Container?

A store of:

```txt
Token → Instance
```

---

# 5. What is a Provider?

Any object
that participates in Dependency Injection.

---

# 6. What is an Injection Token?

The key by which Nest looks up a dependency.

---

# 7. What types of Providers do you know?

```txt
useClass

useValue

useFactory

useExisting
```

---

# 8. When should useFactory be used?

When an object needs to be created dynamically.

---

For example:

```txt
Prisma

JWT

External SDK
```

---

# 9. What is a Dynamic Module?

A module
that creates its configuration at runtime.

---

# 10. What is forRoot()?

Registering global configuration.

---

# 11. What is forFeature()?

Local registration for a specific module.

---

# 12. What is ExecutionContext?

The context of the current request.

---

Allows getting:

```txt
Request

Handler

Controller
```

---

# 13. What is Reflect Metadata?

A mechanism for storing metadata on classes and methods.

---

# 14. What is Reflector?

A service for reading metadata.

---

# 15. How does @Roles() work?

Saves roles via metadata.

---

A Guard reads them via the Reflector.

---

# 16. What is a Custom Decorator?

A user-defined decorator
that adds metadata
or extracts data.

---

# 17. What is a Composite Decorator?

A combination of multiple decorators via:

```ts
applyDecorators()
```

---

# 18. What is Middleware?

Request processing before entering the Nest pipeline.

---

# 19. What is a Guard?

An authorization mechanism.

---

Decides:

```txt
can the request be executed
or not
```

---

# 20. What is a Pipe?

Transformation and validation of incoming data.

---

# 21. What is ValidationPipe?

Validates a DTO through:

```txt
class-validator
```

---

# 22. What does whitelist do?

Removes extra fields.

---

# 23. What is an Interceptor?

A mechanism for intercepting method execution.

---

Before and after the handler call.

---

# 24. What are Interceptors used for?

```txt
Logging

Caching

Metrics

Response Mapping
```

---

# 25. What is an Exception Filter?

Global error handling.

---

# 26. In what order do Middleware, Guard, Pipe and Interceptor execute?

```txt
Middleware
 ↓
Guard
 ↓
Interceptor(before)
 ↓
Pipe
 ↓
Controller
 ↓
Interceptor(after)
```

---

# 27. What is Scope?

The lifecycle of a Provider.

---

# 28. What Scopes exist?

```txt
Singleton

Request

Transient
```

---

# 29. What Scope is used by default?

```txt
Singleton
```

---

# 30. Why is Request Scope expensive?

It creates a new dependency graph for each request.

---

# 31. When should Request Scope be used?

```txt
Tenant Context

Correlation ID

Tracing
```

---

# 32. What is CQRS?

Separating read and write operations.

---

# 33. What is a Command?

A state-changing operation.

---

# 34. What is a Query?

A data reading operation.

---

# 35. What is an Event?

A fact that something happened.

---

# 36. What is CommandBus?

A bus for executing commands.

---

# 37. What is QueryBus?

A bus for executing queries.

---

# 38. What is EventBus?

A bus for publishing events.

---

# 39. When is CQRS justified?

Complex business logic.

---

# 40. When is CQRS excessive?

Plain CRUD.

---

# 41. What is a microservice?

An independent service
that performs a limited set of tasks.

---

# 42. What is ClientProxy?

A client for sending messages between services.

---

# 43. What does send() do?

Request/Response interaction.

---

# 44. What does emit() do?

Publishes an event without waiting for a response.

---

# 45. What is MessagePattern?

A request handler.

---

# 46. What is EventPattern?

An event handler.

---

# 47. What transports does Nest support?

```txt
TCP

Redis

RabbitMQ

Kafka

NATS

gRPC
```

---

# 48. When should RabbitMQ be used?

Task queues,
retry,
routing.

---

# 49. When should Kafka be used?

High-load event streaming.

---

# 50. The Most Popular Senior Question

What makes NestJS a powerful framework?

Answer:

Nest combines Dependency Injection, modular architecture, decorators, a middleware pipeline, CQRS, and microservice support into a single platform. This allows building both small APIs and complex distributed systems with good testability and loose coupling between components.
