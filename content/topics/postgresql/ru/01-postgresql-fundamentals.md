# PostgreSQL Fundamentals

## Что такое PostgreSQL

PostgreSQL — это open-source объектно-реляционная система управления базами данных (RDBMS).

Главная задача PostgreSQL:

- хранить данные
- обеспечивать их целостность
- эффективно выполнять запросы
- поддерживать конкурентную работу множества пользователей

PostgreSQL считается одной из самых надежных и функционально богатых SQL баз данных.

---

# Архитектура PostgreSQL

Упрощенно:

Client
↓
PostgreSQL Server
↓
Storage Engine
↓
Disk

Когда приложение отправляет SQL:

```sql
SELECT * FROM users;
```

происходит следующее:

1. PostgreSQL принимает запрос.
2. Парсер проверяет синтаксис.
3. Planner строит план выполнения.
4. Executor выполняет план.
5. Данные возвращаются клиенту.

---

# Основные сущности

## Database

Логический контейнер данных.

Например:

```sql
CREATE DATABASE interview_db;
```

---

## Schema

Группа объектов внутри базы.

По умолчанию:

```sql
public
```

Например:

```txt
database
 ├── public.users
 ├── public.posts
 └── public.comments
```

---

## Table

Таблица хранит строки данных.

Пример:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    name TEXT
);
```

---

## Row

Отдельная запись.

```txt
id=1
email=max@test.com
name=Max
```

---

## Column

Отдельное поле таблицы.

```txt
id
email
name
```

---

# Типы данных

Наиболее популярные:

## Числа

```sql
INTEGER
BIGINT
NUMERIC
DECIMAL
```

---

## Строки

```sql
TEXT
VARCHAR
CHAR
```

---

## Дата и время

```sql
DATE
TIMESTAMP
TIMESTAMPTZ
```

---

## Логический тип

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

Ограничения гарантируют корректность данных.

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

Гарантирует:

- уникальность
- отсутствие NULL

---

## FOREIGN KEY

```sql
user_id INTEGER REFERENCES users(id)
```

Обеспечивает ссылочную целостность.

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

Обычно через промежуточную таблицу.

---

# JOIN

Позволяет объединять данные из нескольких таблиц.

## INNER JOIN

Возвращает только совпавшие записи.

```sql
SELECT *
FROM users
INNER JOIN posts
ON posts.user_id = users.id;
```

---

## LEFT JOIN

Возвращает все строки из левой таблицы.

```sql
SELECT *
FROM users
LEFT JOIN posts
ON posts.user_id = users.id;
```

---

# Нормализация

Цель нормализации:

- убрать дублирование данных
- обеспечить целостность

Плохо:

```txt
posts
 ├── author_name
 ├── author_email
```

Лучше:

```txt
posts.user_id
 ↓
users.id
```

---

# Денормализация

Иногда данные специально дублируют ради производительности.

Пример:

```txt
orders.total_price
```

вместо пересчета через JOIN каждый раз.

---

# JSONB

Одна из сильнейших сторон PostgreSQL.

Пример:

```sql
CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    config JSONB
);
```

Можно хранить:

```json
{
  "theme": "dark",
  "language": "en"
}
```

При этом JSONB можно индексировать.