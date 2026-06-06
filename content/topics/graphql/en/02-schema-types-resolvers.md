# Schema, Types, and Resolvers

## The Heart of GraphQL

GraphQL is built around a schema.

---

# What is a Schema

A schema describes:

```txt
what data is available
```

---

Example:

```graphql
type User {
  id: ID!
  name: String!
  email: String
}
```

---

It is the contract between server and client.

---

# Scalar Types

The built-in primitive types.

---

GraphQL provides:

```graphql
String
Int
Float
Boolean
ID
```

---

Example:

```graphql
type User {
  id: ID!
  age: Int
}
```

---

# Non Null

The symbol:

```graphql
!
```

---

Example:

```graphql
name: String!
```

---

Means:

```txt
the field will never be null
```

---

# Lists

Arrays.

---

```graphql
posts: [Post]
```

---

An array of Post.

---

# Combinations

A very popular interview question.

---

```graphql
posts: [Post!]!
```

---

Breakdown:

```txt
the field itself is required
each element in the array is required
```

---

# Object Types

A custom type.

---

```graphql
type User {
  id: ID!
  name: String!
}
```

---

# Relationships

GraphQL is great for describing relationships.

---

```graphql
type User {
  id: ID!
  posts: [Post!]!
}
```

---

```graphql
type Post {
  id: ID!
  title: String!
}
```

---

# Query Type

The entry point for reading data.

---

```graphql
type Query {
  user(id: ID!): User
}
```

---

Example query:

```graphql
query {
  user(id: 1) {
    name
  }
}
```

---

# Mutation Type

The entry point for modifying data.

---

```graphql
type Mutation {
  createUser(name: String!): User
}
```

---

# Resolver

The most important part.

---

Schema answers:

```txt
What exists?
```

---

Resolver answers:

```txt
How do you get the data?
```

---

Example:

```ts
const resolvers = {
  Query: {
    user: (_, args) => {
      return db.user.findById(args.id);
    },
  },
};
```

---

# Resolver Signature

A very popular interview question.

---

A resolver receives:

```ts
(parent, args, context, info)
```

---

# parent

The result of the previous resolver.

---

# args

The arguments from the GraphQL query.

---

Example:

```graphql
user(id: 1)
```

---

args:

```ts
{ id: 1 }
```

---

# context

Shared request-level data.

---

For example:

```ts
{
  user,
  prisma,
  dataloaders
}
```

---

Very commonly used for:

```txt
authorization
Prisma
DataLoader
```

---

# info

Information about the GraphQL query.

---

Rarely used.

---

# Nested Resolvers

Example:

```graphql
query {
  user(id: 1) {
    name
    posts {
      title
    }
  }
}
```

---

Execution order:

```txt
Query.user
↓
User.posts
```

---

Every field can potentially have its own resolver.

---

# Why This Matters

This is exactly where the:

```txt
N+1 Problem
```

appears.

---

Covered separately.

---

# Context

A very popular interview question.

---

In NestJS:

```ts
GraphQLModule.forRoot({
  context: ({ req }) => ({
    user: req.user,
  }),
});
```

---

Now any resolver can access:

```ts
context.user
```

---

# Interview Question

Why is GraphQL called strongly typed?

Answer:

Because the schema strictly describes all available types, fields, and arguments. The client knows the API structure before executing a query, and the server validates queries against the schema.
