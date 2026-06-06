# PostgreSQL Fundamentals

## What is PostgreSQL

PostgreSQL is an open-source object-relational database management system (RDBMS).

The main purpose of PostgreSQL:

- store data
- ensure data integrity
- execute queries efficiently
- support concurrent access by many users

PostgreSQL is considered one of the most reliable and feature-rich SQL databases.

---

# PostgreSQL Architecture

Simplified:

Client
↓
PostgreSQL Server
↓
Storage Engine
↓
Disk

When an application sends SQL:

```sql
SELECT * FROM users;
```

the following happens:

1. PostgreSQL receives the query.
2. Parser checks the syntax.
3. Planner builds the execution plan.
4. Executor runs the plan.
5. Data is returned to the client.

---

# Core Entities

## Database

A logical container for data.

For example:

```sql
CREATE DATABASE interview_db;
```

---

## Schema

A group of objects within a database.

Default:

```sql
public
```

For example:

```txt
database
 ├── public.users
 ├── public.posts
 └── public.comments
```

---

## Table

A table stores rows of data.

Example:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    name TEXT
);
```

---

## Row

An individual record.

```txt
id=1
email=max@test.com
name=Max
```

---

## Column

An individual field in a table.

```txt
id
email
name
```

---

# Data Types

Most common:

## Numbers

```sql
INTEGER
BIGINT
NUMERIC
DECIMAL
```

---

## Strings

```sql
TEXT
VARCHAR
CHAR
```

---

## Date and Time

```sql
DATE
TIMESTAMP
TIMESTAMPTZ
```

---

## Boolean

```sql
BOOLEAN
```

---

## JSON

```sql
JSON
JSONB
```

---

# Constraints

Constraints guarantee data correctness.

## NOT NULL

```sql
email TEXT NOT NULL
```

---

## UNIQUE

```sql
email TEXT UNIQUE
```

---

## PRIMARY KEY

```sql
id SERIAL PRIMARY KEY
```

Guarantees:

- uniqueness
- no NULL values

---

## FOREIGN KEY

```sql
user_id INTEGER REFERENCES users(id)
```

Enforces referential integrity.

---

# Relationships

## One-To-One

```txt
User
 ↓
Profile
```

---

## One-To-Many

```txt
User
 ↓
Posts
```

---

## Many-To-Many

```txt
Users
 ↕
Roles
```

Usually through a join table.

---

# JOIN

Allows combining data from multiple tables.

## INNER JOIN

Returns only matching records.

```sql
SELECT *
FROM users
INNER JOIN posts
ON posts.user_id = users.id;
```

---

## LEFT JOIN

Returns all rows from the left table.

```sql
SELECT *
FROM users
LEFT JOIN posts
ON posts.user_id = users.id;
```

---

# Normalization

The goal of normalization:

- eliminate data duplication
- ensure integrity

Bad:

```txt
posts
 ├── author_name
 ├── author_email
```

Better:

```txt
posts.user_id
 ↓
users.id
```

---

# Denormalization

Sometimes data is intentionally duplicated for performance.

Example:

```txt
orders.total_price
```

instead of recalculating via JOIN every time.

---

# JSONB

One of PostgreSQL's strongest features.

Example:

```sql
CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    config JSONB
);
```

Can store:

```json
{
  "theme": "dark",
  "language": "en"
}
```

JSONB can also be indexed.
