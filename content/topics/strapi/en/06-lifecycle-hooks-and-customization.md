# Lifecycle Hooks and Customization

## The Main Idea

Sometimes code needs to run:

```txt
before creating a record
after creating a record
before deleting a record
after updating a record
```

---

For this, there are:

```txt
Lifecycle Hooks
```

---

# Analogy

Very similar to:

```txt
Prisma Middleware
Entity Listeners
ORM Hooks
```

---

# Example

An article is being created.

---

We need to automatically:

```txt
generate a slug
```

---

Before saving.

---

We use:

```txt
beforeCreate
```

---

# Main Hooks

A very popular interview topic.

---

Before an operation:

```txt
beforeCreate
beforeUpdate
beforeDelete
beforeFindMany
beforeFindOne
```

---

After an operation:

```txt
afterCreate
afterUpdate
afterDelete
afterFindMany
afterFindOne
```

---

# beforeCreate

Example.

---

```js
beforeCreate(event) {

  const { data } = event.params;

  data.slug =
    slugify(data.title);
}
```

---

Now the slug is created automatically.

---

# afterCreate

Example.

---

A user was created.

---

We need to send an email.

---

```js
afterCreate(event) {

  sendWelcomeEmail(
    event.result.email
  );
}
```

---

# What the event Contains

A very popular interview question.

---

Usually:

```txt
params
result
state
```

---

# params

Request data.

---

For example:

```txt
data
where
populate
```

---

# result

The result of the operation.

---

Available in after hooks.

---

# Example

```js
event.result.id
```

---

# When to Use Hooks

Suitable for:

```txt
slug generation
audit logs
notifications
validation
sync with external systems
```

---

# When NOT to Use Hooks

A very important question.

---

Bad for:

```txt
complex business logic
```

---

Why?

---

The logic becomes hidden.

---

Harder to maintain.

---

Better to use:

```txt
Service Layer
```

---

# Customizing the Controller

A very popular use case.

---

For example:

Standard CRUD is not enough.

---

We create:

```txt
custom endpoint
```

---

Example:

```http
GET /articles/popular
```

---

And a custom controller.

---

# Customizing the Service

The most common place for logic.

---

Example:

```js
async getPopularArticles() {

  return await strapi
    .documents(...)
    .findMany(...);
}
```

---

# Cron Jobs

Many people forget about this.

---

Strapi supports:

```txt
scheduled jobs
```

---

For example:

Every night:

```txt
clear cache
update statistics
send reports
```

---

# Plugins

A very important topic.

---

Strapi is built on plugins.

---

Built-in:

```txt
Users & Permissions
Upload
GraphQL
i18n
```

---

# You Can Write Your Own

For example:

```txt
CRM Integration
ERP Integration
Analytics
Custom Dashboard
```

---

# Upload Plugin

Very commonly used.

---

Supports:

```txt
Local Storage
AWS S3
Cloudinary
Azure Blob
```

---

# Extending the Content API

You can override:

```txt
Routes
Controllers
Services
Policies
```

---

Effectively turning Strapi
into a full-featured backend.

---

# Frequent Question

Where should business logic be written?

---

Correct answer:

```txt
Services
```

---

NOT:

```txt
Lifecycle Hooks
```

---

NOT:

```txt
Controllers
```

---

# Frequent Question

When should a Lifecycle Hook be used?

---

When you need to perform an additional action
tied to a model event.

---

For example:

```txt
slug generation
logging
notifications
```

---

# Interview Answer

Lifecycle Hooks allow you to execute code before and after data operations such as creating, updating, and deleting records. They are useful for slug generation, auditing, and notifications. Core business logic should reside in the Service Layer, not in Hooks. Strapi also supports custom Controllers, Services, Cron Jobs, and custom Plugins, making it a full-featured backend framework on top of a CMS.
