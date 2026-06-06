# N+1 Problem and DataLoader

## The Most Well-Known GraphQL Problem

If someone asked me:

```txt
What is the most popular senior-level GraphQL question?
```

I would answer:

```txt
N+1 Problem
```

---

# Why the Problem Occurs Specifically in GraphQL

Remember:

Every field can have its own resolver.

---

Example schema:

```graphql
type User {
  id: ID!
  name: String!
  posts: [Post!]!
}
```

---

Resolver:

```ts
User: {
  posts: (user) => {
    return prisma.post.findMany({
      where: {
        userId: user.id,
      },
    });
  },
}
```

---

# The Query

```graphql
query {
  users {
    id
    name
    posts {
      title
    }
  }
}
```

---

# What the Client Expects

```txt
Users + Posts
```

---

# What Actually Happens

Step 1

Fetch the users.

---

```sql
SELECT *
FROM users;
```

---

Let's say:

```txt
100 users
```

---

Step 2

For each user, the resolver is called:

```ts
User.posts
```

---

We get:

```sql
SELECT *
FROM posts
WHERE user_id = 1;

SELECT *
FROM posts
WHERE user_id = 2;

SELECT *
FROM posts
WHERE user_id = 3;
```

---

And so on for:

```txt
100 queries
```

---

Total:

```txt
1 + 100
```

---

This is called:

```txt
N+1 Problem
```

---

# Why This Is Bad

With:

```txt
1000 users
```

we get:

```txt
1001 SQL queries
```

---

The database starts to suffer.

---

# A Common Interview Question

What does N+1 look like?

---

Answer:

One query for the parent entities and a separate query for each related entity.

---

# The Naive Solution

Use include.

---

```ts
prisma.user.findMany({
  include: {
    posts: true,
  },
});
```

---

Sometimes this is sufficient.

---

But not always.

---

Especially with complex data graphs.

---

# The DataLoader Solution

Facebook created a special library:

```txt
DataLoader
```

---

The core idea:

```txt
Batching
+
Caching
```

---

# What DataLoader Does

Suppose the following arrive simultaneously:

```txt
user 1
user 2
user 3
user 4
```

---

Instead of:

```sql
4 separate queries
```

---

DataLoader batches them.

---

We get:

```sql
SELECT *
FROM users
WHERE id IN (1,2,3,4);
```

---

One query instead of four.

---

# DataLoader Example

Create the loader.

---

```ts
const userLoader =
  new DataLoader(
    async (ids) => {

      const users =
        await prisma.user.findMany({
          where: {
            id: {
              in: ids,
            },
          },
        });

      return ids.map(id =>
        users.find(u => u.id === id)
      );
    }
  );
```

---

# Why map() Is Needed

A very popular interview question.

---

DataLoader requires:

```txt
results in the same order
as the input keys
```

---

If input was:

```txt
[3,1,2]
```

---

Must return:

```txt
[user3,user1,user2]
```

---

# Usage

In a resolver:

```ts
User: {
  author: (post, _, ctx) => {
    return ctx.userLoader.load(
      post.userId
    );
  },
}
```

---

# What load() Does

```txt
does not execute the query immediately
```

---

It collects keys.

---

At the end of the current event loop tick:

```txt
executes the batch
```

---

# Caching

The second superpower of DataLoader.

---

If within one request:

```txt
user 1
```

is requested 20 times

---

DataLoader will execute:

```sql
one query
```

---

And then use the cache.

---

# A Very Important Rule

DataLoader is created:

```txt
per GraphQL request
```

---

NOT globally.

---

Why?

---

Otherwise:

```txt
stale data
memory leaks
security issues
```

---

# NestJS Example

Context:

```ts
GraphQLModule.forRoot({
  context: () => ({
    userLoader:
      createUserLoader(),
  }),
});
```

---

Now every request gets:

```txt
its own DataLoader
```

---

# DataLoader Does Not Replace JOIN

A very popular interview question.

---

DataLoader:

```txt
Batching Layer
```

---

JOIN:

```txt
SQL Operation
```

---

Sometimes JOIN is faster.

---

Sometimes DataLoader is more convenient.

---

It depends on the specific case.

---

# How to Detect N+1

Look at the SQL logs.

---

Instead of:

```txt
1-3 queries
```

you see:

```txt
100+
```

---

That's almost always N+1.

---

# Senior Interview Answer

The N+1 Problem occurs when GraphQL executes one query to fetch a list of entities and then a separate query for each related entity. DataLoader solves the problem through batching and request-scoped caching, combining many queries into a single SQL query using WHERE id IN (...) and reusing results within a single GraphQL request.
