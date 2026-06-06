# RDS vs DynamoDB

## Very Popular AWS Question

What to choose:

```txt
RDS

or

DynamoDB
```

---

The question actually means:

```txt
SQL

or

NoSQL
```

---

# What is RDS

RDS:

```txt
Relational Database Service
```

---

A managed relational database.

---

Supports:

```txt
PostgreSQL

MySQL

MariaDB

SQL Server
```

---

# What We Get

AWS manages:

```txt
backup

replication

patching

monitoring
```

---

We work with it like a regular database.

---

# What is DynamoDB

AWS NoSQL database.

---

Model:

```txt
Key-Value

Document
```

---

No:

```txt
JOIN

Foreign Key

Relations
```

---

# The Main Difference

RDS:

```txt
tables are related
```

---

DynamoDB:

```txt
denormalization
```

---

# RDS Example

```sql
Users

Orders

Products
```

---

Related via:

```sql
JOIN
```

---

# DynamoDB Example

We often store:

```json
{
 userId: 1,
 orders: [...]
}
```

---

In a single object.

---

# Schema

Very popular interview question.

---

RDS:

```txt
strict schema
```

---

DynamoDB:

```txt
flexible schema
```

---

# JOIN

Interviewers' favorite question.

---

RDS:

```sql
JOIN
```

---

Exists.

---

DynamoDB:

```txt
no JOIN
```

---

Data must be designed differently.

---

# Transactions

RDS:

```txt
full ACID
```

---

DynamoDB:

```txt
limited transactions
```

---

Supported,
but used less often.

---

# Scaling

A very important topic.

---

RDS:

```txt
harder to scale
```

---

Especially writes.

---

# DynamoDB

Built for:

```txt
horizontal scaling
```

---

Can handle:

```txt
millions of requests
```

---

# Performance

Very popular interview question.

---

DynamoDB:

```txt
single-digit millisecond
```

---

Practically always.

---

Because:

```txt
no JOIN

no complex queries
```

---

# Query Flexibility

RDS:

```txt
very flexible queries
```

---

For example:

```sql
JOIN
GROUP BY
WINDOW FUNCTIONS
```

---

# DynamoDB

Limited queries.

---

Model:

```txt
Query by Key
```

---

# Partition Key

The most important DynamoDB topic.

---

Each record has:

```txt
Partition Key
```

---

It determines:

```txt
where the data is stored
```

---

# Sort Key

Optional.

---

Allows storing:

```txt
multiple records
within a partition
```

---

# Secondary Indexes

Like indexes in SQL.

---

Allow querying:

```txt
not only by Primary Key
```

---

# When to Use RDS

Good fit:

```txt
CRM

ERP

E-commerce

Financial Systems

Complex Relations
```

---

# When to Use DynamoDB

Good fit:

```txt
High Throughput

Gaming

IoT

Session Storage

Event Storage
```

---

# Typical Fullstack Project

Interviewers love asking this.

---

```txt
Next.js

NestJS

PostgreSQL
```

---

Almost always:

```txt
RDS
```

---

# When DynamoDB is Justified

For example:

```txt
millions of events

logging

telemetry

real-time systems
```

---

# Common Question

Why is DynamoDB so fast?

Answer:

Because it is optimized for key-based access, doesn't support JOIN, and distributes data across partitions.

---

# Common Question

Why do many applications use PostgreSQL instead of DynamoDB?

Answer:

Because most business applications work with relations between entities and require flexible SQL queries.

---

# Common Question

Which is harder to design?

Answer:

DynamoDB.

---

Because you first need to think through query patterns and only then design the data structure.

---

# Interview Answer

RDS is a managed relational database and is well-suited for systems with complex relations and SQL queries. DynamoDB is a highly scalable NoSQL database optimized for key-based access. The choice between them depends on the nature of the data, scaling requirements, and query patterns.
