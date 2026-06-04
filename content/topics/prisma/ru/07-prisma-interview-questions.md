# Prisma Interview Questions

---

# 1. Что такое Prisma?

Prisma — TypeScript-first ORM toolkit, который генерирует типизированный клиент на основе schema.prisma.

---

# 2. Что такое schema.prisma?

Центральный файл Prisma.

Описывает:

- datasource
- generator
- models
- relations

---

# 3. Что является source of truth?

Ответ:

```txt
schema.prisma
```

---

# 4. Что такое Prisma Client?

Сгенерированный TypeScript API для работы с базой данных.

---

# 5. Что делает Prisma Migrate?

Генерирует SQL миграции из изменений схемы.

---

# 6. Чем migrate dev отличается от migrate deploy?

migrate dev:

```txt
локальная разработка
```

---

migrate deploy:

```txt
production
CI/CD
```

---

# 7. Что такое db push?

Обновляет структуру БД без создания миграций.

---

# 8. Почему db push не используют в production?

Потому что нет истории изменений.

---

# 9. Какие отношения поддерживает Prisma?

- One-To-One
- One-To-Many
- Many-To-Many

---

# 10. Что делает include?

Подгружает связанные сущности.

---

# 11. Что делает select?

Ограничивает возвращаемые поля.

---

# 12. Что лучше использовать для performance?

Обычно:

```txt
select
```

---

а не огромные include.

---

# 13. Что такое connect?

Связывает существующую запись.

---

# 14. Что такое connectOrCreate?

Если запись существует:

```txt
connect
```

Если нет:

```txt
create
```

---

# 15. Что такое nested writes?

Создание/обновление связанных сущностей одним запросом.

---

# 16. Как работают транзакции в Prisma?

Через:

```ts
$transaction()
```

---

Под капотом используются транзакции базы данных.

---

# 17. Защищает ли Prisma от race conditions?

Нет.

---

Race conditions решаются через:

- транзакции
- locks
- constraints

на уровне БД.

---

# 18. Что такое N+1 Problem?

Один запрос на список объектов
и N дополнительных запросов
для связанных данных.

---

# 19. Как бороться с N+1?

- include
- batching
- DataLoader
- правильный GraphQL design

---

# 20. Почему знание PostgreSQL всё еще важно?

Потому что Prisma генерирует SQL.

Проблемы производительности
обычно находятся на уровне базы данных.

---

# 21. Когда использовать Raw SQL?

- сложные аналитические запросы
- оконные функции
- специфичные возможности PostgreSQL

---

# 22. Чем Prisma отличается от TypeORM?

Prisma:

```txt
schema-first
generated client
strong typing
```

---

TypeORM:

```txt
decorators
entities
runtime metadata
```

---

# 23. Что такое Shadow Database?

Временная БД,
которую Prisma использует
для проверки миграций.

---

# 24. Что такое createMany?

Массовая вставка записей.

Быстрее цикла из create().

---

# 25. Что бы вы оптимизировали первым делом в медленном Prisma запросе?

Ответ:

1. EXPLAIN ANALYZE
2. Индексы
3. include/select
4. Pagination
5. N+1
6. Raw SQL при необходимости