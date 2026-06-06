# Queries, Mutations, and Subscriptions

## Three Types of GraphQL Operations

GraphQL supports:

```txt
Query
Mutation
Subscription
```

---

# Query

Used for reading data.

---

REST equivalent:

```http
GET
```

---

Example:

```graphql
query {
  users {
    id
    name
  }
}
```

---

Response:

```json
{
  "data": {
    "users": [
      {
        "id": "1",
        "name": "Max"
      }
    ]
  }
}
```

---

# Query with Arguments

```graphql
query {
  user(id: 1) {
    name
  }
}
```

---

Schema:

```graphql
type Query {
  user(id: ID!): User
}
```

---

Resolver:

```ts
Query: {
  user: (_, args) => {
    return prisma.user.findUnique({
      where: {
        id: Number(args.id),
      },
    });
  },
}
```

---

# Aliases

A very useful feature.

---

You can call the same resolver multiple times.

---

```graphql
query {
  admin: user(id: 1) {
    name
  }

  manager: user(id: 2) {
    name
  }
}
```

---

Response:

```json
{
  "admin": {
    "name": "Max"
  },
  "manager": {
    "name": "John"
  }
}
```

---

# Fragments

Allow reusing a set of fields.

---

Without Fragment:

```graphql
user {
  id
  name
  email
}
```

---

```graphql
author {
  id
  name
  email
}
```

---

Repetition.

---

# With Fragment

```graphql
fragment UserFields on User {
  id
  name
  email
}
```

---

Usage:

```graphql
user {
  ...UserFields
}
```

---

# Variables

A very popular interview topic.

---

Bad:

```graphql
query {
  user(id: 1)
}
```

---

Better:

```graphql
query GetUser($id: ID!) {
  user(id: $id) {
    name
  }
}
```

---

Variables:

```json
{
  "id": 1
}
```

---

# Mutation

Used for modifying data.

---

Equivalent to:

```http
POST
PUT
PATCH
DELETE
```

---

Example:

```graphql
mutation {
  createUser(
    name: "Max"
  ) {
    id
    name
  }
}
```

---

Schema:

```graphql
type Mutation {
  createUser(
    name: String!
  ): User!
}
```

---

Resolver:

```ts
Mutation: {
  createUser: (_, args) => {
    return prisma.user.create({
      data: {
        name: args.name,
      },
    });
  },
}
```

---

# Input Types

A very important topic.

---

Bad:

```graphql
createUser(
  name: String
  email: String
  age: Int
)
```

---

Good:

```graphql
input CreateUserInput {
  name: String!
  email: String!
  age: Int
}
```

---

Mutation:

```graphql
createUser(
  input: CreateUserInput!
): User!
```

---

# Why Input Types Are Better

- easier to extend
- fewer arguments
- easier to validate

---

# Subscription

A very popular interview topic.

---

Subscriptions allow receiving data in realtime.

---

Example:

```graphql
subscription {
  messageAdded {
    id
    text
  }
}
```

---

When a new message appears:

```txt
the server pushes the event itself
```

---

# How It Differs from Query

Query:

```txt
request → response
```

---

Subscription:

```txt
request → persistent connection
```

---

# Usually Uses

```txt
WebSocket
```

---

# Use Cases

```txt
chat
notifications
stock exchange
games
online tracking
```

---

# NestJS Example

```ts
@Subscription(() => Message)
messageAdded() {
  return pubSub.asyncIterator([
    'MESSAGE_ADDED',
  ]);
}
```

---

# When Subscription Is Not Needed

Most CRUD systems work perfectly fine without it.

---

# Interview Question

When to use Query, Mutation, and Subscription?

Answer:

Query is used for reading data, Mutation for modifying data, and Subscription for receiving realtime updates over a persistent connection, typically WebSocket.
