# GraphQL Interview Questions

---

# 1. What is GraphQL?

GraphQL is a query language for APIs and a runtime for executing them.

---

# 2. Why was GraphQL created?

To solve the problems of:

- Overfetching
- Underfetching

in REST APIs.

---

# 3. How does GraphQL differ from REST?

REST:

```txt
the server defines the response
```

GraphQL:

```txt
the client defines the response
```

---

# 4. What is a Schema?

The API contract.

Describes types, fields, and operations.

---

# 5. What is a Resolver?

A function that fetches data for a schema field.

---

# 6. What does a Resolver receive?

```ts
(parent, args, context, info)
```

---

# 7. What is a Query?

A data-reading operation.

---

# 8. What is a Mutation?

A data-modification operation.

---

# 9. What is a Subscription?

A realtime operation, typically running over WebSocket.

---

# 10. What is an Input Type?

A type for passing complex data into a Mutation.

---

# 11. What is a Fragment?

A reusable set of fields.

---

# 12. What are Variables?

A way to pass query parameters separately from the query document.

---

# 13. What is Introspection?

GraphQL's ability to describe its own schema.

---

# 14. Why is GraphQL called strongly typed?

Because the schema strictly describes all data types.

---

# 15. What is the N+1 Problem?

One query for a list of entities and a separate query for each related entity.

---

# 16. How do you solve N+1?

DataLoader.

---

# 17. What does DataLoader do?

- Batching
- Request-scoped caching

---

# 18. Why is DataLoader created per request?

To avoid:

- memory leaks
- stale data
- security issues

---

# 19. What is Query Complexity?

An estimate of the cost of a GraphQL query.

---

# 20. What is Depth Limiting?

Restricting the maximum nesting depth of a query.

---

# 21. Why is Pagination needed?

To avoid loading huge volumes of data.

---

# 22. Why is Cursor Pagination better than Offset?

It scales better on large tables.

---

# 23. Why is GraphQL caching harder?

Because all requests go through a single endpoint.

---

# 24. What are Persisted Queries?

Pre-registered queries identified by hash.

---

# 25. What is Apollo Federation?

A mechanism for combining multiple GraphQL services into a unified schema.

---

# 26. What is a Gateway?

A service that combines multiple GraphQL APIs.

---

# 27. What is BFF?

Backend For Frontend.

A dedicated API layer optimized for the frontend.

---

# 28. When is GraphQL better than REST?

- complex frontend
- mobile apps
- lots of related data

---

# 29. When is REST better than GraphQL?

- simple CRUD systems
- public APIs
- high cacheability

---

# 30. The Most Popular Senior Question

How would you scale a large GraphQL API?

Answer:

I would use DataLoader to solve N+1, pagination to limit data volume, query complexity and depth limiting to protect against heavy queries, persisted queries for caching, and Apollo Federation to split the schema across microservices.
