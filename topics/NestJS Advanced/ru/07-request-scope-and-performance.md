# Request Scope и Performance

## Самый популярный Senior вопрос

Что происходит если сделать:

```ts
@Injectable({
 scope: Scope.REQUEST
})
```

---

Большинство отвечает:

```txt
Создается новый объект на каждый запрос
```

---

Это правильно.

---

Но недостаточно.

---

# Напомним Scope

Nest поддерживает:

```txt
Singleton
Request
Transient
```

---

# Singleton

По умолчанию.

---

```ts
@Injectable()
export class UserService {}
```

---

Создается:

```txt
1 объект
на всё приложение
```

---

Схема:

```txt
Request 1
 ↓
UserService

Request 2
 ↓
тот же UserService
```

---

# Почему Singleton быстрый

Потому что:

```txt
объект создается один раз
```

---

Нет:

```txt
новых аллокаций памяти
лишнего GC
```

---

# Request Scope

```ts
@Injectable({
 scope: Scope.REQUEST
})
```

---

Создается:

```txt
новый экземпляр
на каждый запрос
```

---

Схема:

```txt
Request 1
 ↓
UserService #1

Request 2
 ↓
UserService #2

Request 3
 ↓
UserService #3
```

---

# Что происходит внутри

Очень популярный вопрос.

---

Nest создает:

```txt
новый dependency tree
```

---

Для каждого запроса.

---

# Пример

```txt
UserController
     ↓
UserService
     ↓
AuditService
     ↓
ConfigService
```

---

Если UserService стал Request Scope:

---

Очень важно:

```txt
AuditService
тоже становится
Request Scope
```

---

# Scope Propagation

Одна из самых важных тем.

---

Request Scope распространяется вверх.

---

Пример.

---

```txt
Controller
 ↓
Request Service
 ↓
Singleton Service
```

---

Nest не может смешать:

```txt
Request Instance
```

и

```txt
Singleton Instance
```

---

Поэтому создаст новый граф.

---

# Почему это дорого

На каждый запрос:

```txt
новые объекты

новые зависимости

новые ссылки

новый GC
```

---

# Что происходит при 1000 RPS

```txt
1000 запросов
```

---

Получаем:

```txt
тысячи объектов
каждую секунду
```

---

GC начинает работать чаще.

---

Растет latency.

---

# Когда Request Scope оправдан

Очень популярный вопрос.

---

Примеры:

```txt
Current User Context

Tenant Context

Correlation ID

Request Tracing
```

---

# Correlation ID

Очень частый кейс.

---

Каждому запросу:

```txt
Request-ID
```

---

Нужно передать через:

```txt
Controller
Service
Repository
```

---

Тогда Request Scope оправдан.

---

# Multi-Tenant

Еще один хороший пример.

---

```txt
Tenant A

Tenant B

Tenant C
```

---

На каждом запросе:

```txt
разная БД
разный контекст
```

---

# Когда НЕ нужен

Очень любят спрашивать.

---

Плохо:

```txt
UserService

ProductService

OrderService
```

---

Только потому что:

```txt
так удобнее
```

---

Это антипаттерн.

---

# AsyncLocalStorage

Очень современный вопрос.

---

Во многих случаях:

```txt
Request Scope
```

можно заменить на:

```txt
AsyncLocalStorage
```

---

Плюс:

```txt
без создания новых объектов
```

---

Производительность лучше.

---

# Transient Scope

Самый редкий.

---

```ts
Scope.TRANSIENT
```

---

Каждая инъекция:

```txt
новый объект
```

---

Даже внутри одного запроса.

---

# Пример

```txt
A -> Logger #1

B -> Logger #2

C -> Logger #3
```

---

# Когда используют

Редко.

---

Например:

```txt
builder objects

temporary helpers
```

---

# Частый вопрос

Какой Scope использовать по умолчанию?

Ответ:

```txt
Singleton
```

---

Практически всегда.

---

# Частый вопрос

Почему Request Scope может быть опасен?

Ответ:

Потому что Nest создает новый граф зависимостей для каждого запроса, что приводит к дополнительным аллокациям памяти и нагрузке на Garbage Collector.

---

# Interview Answer

Singleton является самым производительным Scope и используется по умолчанию. Request Scope создает новый экземпляр провайдера на каждый запрос и может значительно увеличивать потребление памяти и нагрузку на GC. Использовать его стоит только тогда, когда действительно нужен request-specific context, например tenant information или correlation id.