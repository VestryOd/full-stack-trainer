# CQRS Pattern

## A Very Popular Senior Topic

What is:

```txt
CQRS
```

---

Stands for:

```txt
Command Query Responsibility Segregation
```

---

Separating:

```txt
Reads
```

and

```txt
Writes
```

---

# A Typical Service

For example:

```ts
class UserService {

 createUser()

 updateUser()

 deleteUser()

 getUser()

 getUsers()
}
```

---

Everything in one place.

---

# CQRS

We separate.

---

```txt
Commands
```

are responsible for:

```txt
changing state
```

---

```txt
Queries
```

are responsible for:

```txt
reading data
```

---

# Example

Command:

```txt
CreateUser
```

---

Query:

```txt
GetUser
```

---

Different objects.

---

# Why CQRS Appeared

A very popular interview question.

---

Reason:

```txt
reads and writes
often scale
differently
```

---

# Example

An online store.

---

Writes:

```txt
100 orders
```

---

Reads:

```txt
100000 views
```

---

Different load.

---

# Core Elements

In Nest CQRS uses:

```txt
Command

CommandHandler

Query

QueryHandler

Event

EventHandler
```

---

# Command

A command describes an action.

---

```ts
export class CreateUserCommand {

 constructor(
  public email: string
 ) {}
}
```

---

# Command Handler

Executes the action.

---

```ts
@CommandHandler(
 CreateUserCommand
)
export class
CreateUserHandler {

 async execute(
  command
 ) {}
}
```

---

# Execution

Via:

```ts
commandBus.execute(...)
```

---

Example:

```ts
await this.commandBus.execute(
 new CreateUserCommand(
  email
 )
);
```

---

# Query

Describes a data request.

---

```ts
export class GetUserQuery {

 constructor(
  public id: string
 ) {}
}
```

---

# Query Handler

```ts
@QueryHandler(
 GetUserQuery
)
```

---

Returns data.

---

# Execution

```ts
queryBus.execute(...)
```

---

# Event

A very popular topic.

---

After a user is created:

```txt
UserCreatedEvent
```

---

# Why

To avoid coupling code directly.

---

Instead of:

```txt
Create User
 ↓
Send Email
 ↓
Create Audit
 ↓
Update CRM
```

---

We get:

```txt
Create User
 ↓
Publish Event
```

---

And subscribers react on their own.

---

# Event Handler

```ts
@EventsHandler(
 UserCreatedEvent
)
```

---

Handles the event.

---

# Flow

```txt
Command
 ↓
Command Handler
 ↓
Database
 ↓
Event
 ↓
Event Handlers
```

---

# When CQRS Is Justified

A very popular interview question.

---

Suitable for:

```txt
complex domain

lots of business logic

event driven architecture

microservices
```

---

# When CQRS Is NOT Needed

Even more popular.

---

Bad for:

```txt
CRUD application
```

---

For example:

```txt
Admin Panel

Simple CMS

Internal Tool
```

---

It will only complicate the code.

---

# CQRS in Nest

Package:

```ts
@nestjs/cqrs
```

---

Modules:

```ts
CommandBus

QueryBus

EventBus
```

---

# Pros

```txt
separation of concerns

explicit business logic

scalability

event driven architecture
```

---

# Cons

A very popular interview topic.

---

```txt
many files

more boilerplate

harder to maintain
```

---

# Frequent Question

Is CQRS always necessary?

Answer:

No.

---

For most CRUD systems
a plain Service Layer is simpler.

---

# Frequent Question

How does a Command differ from a Query?

---

Command:

```txt
changes state
```

---

Query:

```txt
only reads
```

---

# Frequent Question

How are CQRS and Event Sourcing related?

---

CQRS:

```txt
can be used independently
```

---

Event Sourcing:

```txt
is often built on top of CQRS
```

---

But these are different patterns.

---

# Interview Answer

CQRS separates read and write operations into separate models. Commands are responsible for changing system state, Queries for retrieving data. In NestJS, CQRS is implemented via CommandBus, QueryBus, and EventBus. This approach is useful for complex domain systems but is often overkill for simple CRUD applications.
