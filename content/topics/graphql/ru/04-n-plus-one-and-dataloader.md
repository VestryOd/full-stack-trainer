# N+1 Problem и DataLoader

## Самая известная проблема GraphQL

Если бы меня спросили:

```txt
Какой самый популярный senior вопрос по GraphQL?
```

Я бы ответил:

```txt
N+1 Problem
```

---

# Почему проблема возникает именно в GraphQL

Помним:

Каждое поле может иметь свой resolver.

---

Пример схемы:

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

# Запрос

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

# Что ожидает клиент

```txt
Users + Posts
```

---

# Что происходит на самом деле

Шаг 1

Получаем пользователей.

---

```sql
SELECT *
FROM users;
```

---

Допустим:

```txt
100 пользователей
```

---

Шаг 2

Для каждого пользователя вызывается:

```ts
User.posts
```

---

Получаем:

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

И так:

```txt
100 запросов
```

---

Итого:

```txt
1 + 100
```

---

Это и называется:

```txt
N+1 Problem
```

---

# Почему это плохо

При:

```txt
1000 пользователей
```

получим:

```txt
1001 SQL запрос
```

---

База данных начинает страдать.

---

# На интервью любят спрашивать

Как выглядит N+1?

---

Ответ:

Один запрос на родительские сущности и отдельный запрос на каждую связанную сущность.

---

# Наивное решение

Использовать include.

---

```ts
prisma.user.findMany({
  include: {
    posts: true,
  },
});
```

---

Иногда этого достаточно.

---

Но не всегда.

---

Особенно при сложных графах данных.

---

# Решение DataLoader

Facebook создал специальную библиотеку:

```txt
DataLoader
```

---

Главная идея:

```txt
Batching
+
Caching
```

---

# Что делает DataLoader

Допустим одновременно пришли:

```txt
user 1
user 2
user 3
user 4
```

---

Вместо:

```sql
4 отдельных запроса
```

---

DataLoader объединяет их.

---

Получаем:

```sql
SELECT *
FROM users
WHERE id IN (1,2,3,4);
```

---

Один запрос вместо четырех.

---

# DataLoader Example

Создаем loader.

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

# Почему нужен map()

Очень популярный вопрос.

---

DataLoader требует:

```txt
результат в том же порядке
что и входные ключи
```

---

Если получили:

```txt
[3,1,2]
```

---

Нужно вернуть:

```txt
[user3,user1,user2]
```

---

# Использование

В resolver:

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

# Что делает load()

```txt
не выполняет запрос сразу
```

---

Он собирает ключи.

---

И в конце текущего event loop tick:

```txt
выполняет batching
```

---

# Caching

Вторая суперсила DataLoader.

---

Если в рамках одного запроса:

```txt
user 1
```

запросили 20 раз

---

DataLoader выполнит:

```sql
один запрос
```

---

Дальше будет использовать кэш.

---

# Очень важное правило

DataLoader создается:

```txt
на каждый GraphQL запрос
```

---

НЕ глобально.

---

Почему?

---

Иначе:

```txt
устаревшие данные
утечки памяти
проблемы безопасности
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

Теперь каждый запрос получает:

```txt
свой DataLoader
```

---

# DataLoader не заменяет JOIN

Очень популярный вопрос.

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

Иногда JOIN быстрее.

---

Иногда DataLoader удобнее.

---

Нужно смотреть конкретный кейс.

---

# Как понять что есть N+1

Смотришь логи SQL.

---

Вместо:

```txt
1-3 запроса
```

видишь:

```txt
100+
```

---

Почти всегда это N+1.

---

# Senior Interview Answer

N+1 Problem возникает, когда GraphQL выполняет один запрос для получения списка сущностей и затем отдельный запрос для каждой связанной сущности. DataLoader решает проблему через batching и request-scoped caching, объединяя множество запросов в один SQL запрос вида WHERE id IN (...) и переиспользуя результаты в рамках одного GraphQL запроса.