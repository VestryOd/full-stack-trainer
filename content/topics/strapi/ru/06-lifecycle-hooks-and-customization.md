# Lifecycle Hooks и Customization

## Главная идея

Иногда нужно выполнить код:

```txt
до создания записи
после создания записи
до удаления записи
после обновления записи
```

---

Для этого существуют:

```txt
Lifecycle Hooks
```

---

# Аналогия

Очень похоже на:

```txt
Prisma Middleware
Entity Listeners
ORM Hooks
```

---

# Пример

Создается статья.

---

Нужно автоматически:

```txt
сгенерировать slug
```

---

До сохранения.

---

Используем:

```txt
beforeCreate
```

---

# Основные Hooks

Очень любят спрашивать.

---

До операции:

```txt
beforeCreate
beforeUpdate
beforeDelete
beforeFindMany
beforeFindOne
```

---

После операции:

```txt
afterCreate
afterUpdate
afterDelete
afterFindMany
afterFindOne
```

---

# beforeCreate

Пример.

---

```js
beforeCreate(event) {

  const { data } = event.params;

  data.slug =
    slugify(data.title);
}
```

---

Теперь slug создается автоматически.

---

# afterCreate

Пример.

---

Создали пользователя.

---

Нужно отправить письмо.

---

```js
afterCreate(event) {

  sendWelcomeEmail(
    event.result.email
  );
}
```

---

# Что содержит event

Очень популярный вопрос.

---

Обычно:

```txt
params
result
state
```

---

# params

Данные запроса.

---

Например:

```txt
data
where
populate
```

---

# result

Результат операции.

---

Доступен в after hooks.

---

# Пример

```js
event.result.id
```

---

# Когда использовать Hooks

Подходит для:

```txt
slug generation
audit logs
notifications
validation
sync with external systems
```

---

# Когда НЕ использовать Hooks

Очень важный вопрос.

---

Плохо:

```txt
сложная бизнес-логика
```

---

Почему?

---

Логика становится скрытой.

---

Труднее поддерживать.

---

Лучше:

```txt
Service Layer
```

---

# Кастомизация Controller

Очень популярный кейс.

---

Например:

Стандартного CRUD недостаточно.

---

Создаем:

```txt
custom endpoint
```

---

Пример:

```http
GET /articles/popular
```

---

И собственный controller.

---

# Кастомизация Service

Самое частое место для логики.

---

Пример:

```js
async getPopularArticles() {

  return await strapi
    .documents(...)
    .findMany(...);
}
```

---

# Cron Jobs

Многие забывают.

---

Strapi поддерживает:

```txt
scheduled jobs
```

---

Например:

Каждую ночь:

```txt
очистить кеш
обновить статистику
отправить отчеты
```

---

# Plugins

Очень важная тема.

---

Strapi построен на плагинах.

---

Встроенные:

```txt
Users & Permissions
Upload
GraphQL
i18n
```

---

# Можно писать свои

Например:

```txt
CRM Integration
ERP Integration
Analytics
Custom Dashboard
```

---

# Upload Plugin

Очень часто используется.

---

Поддерживает:

```txt
Local Storage
AWS S3
Cloudinary
Azure Blob
```

---

# Extending Content API

Можно переопределять:

```txt
Routes
Controllers
Services
Policies
```

---

Фактически превращая Strapi
в полноценный backend.

---

# Частый вопрос

Где писать бизнес-логику?

---

Правильный ответ:

```txt
Services
```

---

НЕ:

```txt
Lifecycle Hooks
```

---

НЕ:

```txt
Controllers
```

---

# Частый вопрос

Когда использовать Lifecycle Hook?

---

Когда нужно выполнить дополнительное действие,
привязанное к событию модели.

---

Например:

```txt
создание slug
логирование
уведомление
```

---

# Interview Answer

Lifecycle Hooks позволяют выполнять код до и после операций с данными, таких как создание, обновление и удаление записей. Они полезны для генерации slug, аудита и уведомлений. Основная бизнес-логика должна находиться в Service Layer, а не в Hooks. Strapi также поддерживает кастомные Controllers, Services, Cron Jobs и собственные Plugins, что делает его полноценным backend framework поверх CMS.