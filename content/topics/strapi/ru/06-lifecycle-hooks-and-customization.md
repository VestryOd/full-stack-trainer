# Lifecycle Hooks и Customization

## Все lifecycle events

Lifecycle Hooks — механизм для выполнения кода до/после операций с данными. Аналог Prisma middleware или Mongoose pre/post hooks. Используются для cross-cutting задач привязанных к операциям с конкретным Content Type.

```typescript
// src/api/article/content-types/article/lifecycles.ts
export default {
  // ===== BEFORE HOOKS =====

  async beforeCreate(event) {
    const { data } = event.params;

    // Автогенерация slug из title
    if (data.title && !data.slug) {
      data.slug = data.title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '');
    }

    // Установить publishedAt при создании
    // (если Draft & Publish отключён)
    data.publishedAt = new Date();
  },

  async beforeUpdate(event) {
    const { data } = event.params;

    // Обновить slug если изменился title
    if (data.title) {
      data.slug = data.title.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    }

    // Добавить updatedBy
    // (Strapi делает это автоматически, но можно добавить кастомные поля)
  },

  async beforeDelete(event) {
    const { where } = event.params;

    // Проверить зависимости перед удалением
    const commentsCount = await strapi.documents('api::comment.comment').count({
      filters: { article: where.id },
    });

    if (commentsCount > 0) {
      // Бросить ошибку — удаление заблокировано
      throw new Error(`Cannot delete article with ${commentsCount} comments`);
    }
  },

  // ===== AFTER HOOKS =====

  async afterCreate(event) {
    const { result } = event;

    // Отправить уведомление редактору
    await strapi.service('api::notification.notification').sendNewArticleNotification({
      articleId: result.documentId,
      title: result.title,
    });

    // Записать в audit log
    await strapi.documents('api::audit-log.audit-log').create({
      data: {
        action: 'article_created',
        entityId: result.documentId,
        timestamp: new Date().toISOString(),
      },
    });
  },

  async afterUpdate(event) {
    const { result, params } = event;

    // Если статья опубликована — очистить кеш
    if (result.publishedAt && !params.data?.publishedAt) {
      // Инвалидировать Redis кеш для этой статьи
      await strapi.service('api::cache.cache').invalidate(`article:${result.documentId}`);
    }
  },

  async afterDelete(event) {
    const { result } = event;
    strapi.log.info(`Article deleted: ${result.title} (${result.documentId})`);
  },

  // Hooks для чтения (реже используются)
  async afterFindMany(event) {
    const { result } = event;
    // result — массив найденных записей
    // Можно трансформировать перед возвратом
  },
};
```

## Bootstrap и Register — инициализация на старте

```typescript
// src/index.ts — главный файл кастомизации Strapi
export default {
  /**
   * register — вызывается ПЕРЕД загрузкой плагинов.
   * Регистрация кастомных сервисов, контроллеров, content types.
   */
  register({ strapi }) {
    // Регистрация кастомного middleware глобально
    strapi.server.use(async (ctx, next) => {
      ctx.set('X-Custom-Header', 'value');
      await next();
    });
  },

  /**
   * bootstrap — вызывается ПОСЛЕ загрузки всех плагинов.
   * Инициализация данных, подписка на события, Cron Jobs.
   */
  async bootstrap({ strapi }) {
    // Подписаться на событие через EventHub
    strapi.eventHub.on('entry.create', async ({ model, entry }) => {
      strapi.log.info(`New entry created in ${model}: ${entry.id}`);
    });

    // Создать default данные если их нет
    const categoriesCount = await strapi.documents('api::category.category').count({});
    if (categoriesCount === 0) {
      await strapi.documents('api::category.category').create({
        data: { name: 'General', slug: 'general' },
      });
      strapi.log.info('Default category created');
    }
  },
};
```

## Cron Jobs — периодические задачи

```typescript
// config/cron-tasks.ts
export default {
  // Каждую ночь в 02:00 — очистить старые draft статьи
  '0 2 * * *': {
    task: async ({ strapi }) => {
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

      const oldDrafts = await strapi.documents('api::article.article').findMany({
        filters: {
          publishedAt: { $null: true },
          createdAt: { $lt: thirtyDaysAgo.toISOString() },
        },
      });

      for (const draft of oldDrafts) {
        await strapi.documents('api::article.article').delete({
          documentId: draft.documentId,
        });
      }

      strapi.log.info(`Cleaned up ${oldDrafts.length} stale drafts`);
    },
    options: { tz: 'Europe/Berlin' },
  },

  // Каждый час — обновить статистику
  '0 * * * *': {
    task: async ({ strapi }) => {
      await strapi.service('api::stats.stats').updateHourlyStats();
    },
    enabled: process.env.NODE_ENV === 'production',
  },
};
```

## Webhooks — уведомление внешних систем

```typescript
// Admin Panel → Settings → Webhooks → Add new webhook

// Strapi отправит POST запрос при событии:
// {
//   "event": "entry.create",
//   "createdAt": "2024-01-15T10:00:00.000Z",
//   "model": "article",
//   "uid": "api::article.article",
//   "entry": { "id": 1, "title": "New Article", ... }
// }

// Кастомный Webhook через EventHub:
// src/index.ts bootstrap():
strapi.eventHub.on('entry.publish', async ({ model, entry }) => {
  if (model === 'article') {
    // Уведомить CDN о новом контенте
    await fetch('https://cdn.example.com/purge', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${process.env.CDN_TOKEN}` },
      body: JSON.stringify({ path: `/articles/${entry.slug}` }),
    });
  }
});
```

## Когда Hook, когда Service, когда Bootstrap

```txt
Lifecycle Hook:
  ✓ Автогенерация значений (slug, permalink)
  ✓ Аудит / логирование операций с моделью
  ✓ Синхронные валидации на уровне данных
  ✓ Очистка кеша при обновлении
  ✗ НЕ сложная бизнес-логика (прячет логику)
  ✗ НЕ вызовы внешних API (side effects должны быть явными)

Service:
  ✓ Бизнес-логика (агрегация, расчёты, правила)
  ✓ Взаимодействие с несколькими Content Types
  ✓ Вызовы внешних API
  ✓ Переиспользуемая логика

Bootstrap:
  ✓ Инициализация при старте (seed data, connections)
  ✓ Глобальные подписки на события
  ✓ Cron Jobs регистрация
  ✓ Middleware регистрация
```

## Типичные ошибки на интервью

- **"Lifecycle Hook — лучшее место для бизнес-логики"** — нет. Hooks скрывают логику: разработчик читает Service и не видит что при сохранении срабатывают дополнительные операции. Сложная логика в Hook = трудно тестировать, трудно отлаживать, неожиданные side effects. Hooks для автоматических мутаций данных, Service для бизнес-правил.

- **"afterCreate не видит только что созданную запись"** — видит. `event.result` в after hooks содержит результат операции — созданную запись со всеми полями включая сгенерированный `id` и `documentId`. В before hooks `event.result` недоступен (операция ещё не выполнена).

- **"Cron Jobs запускаются на всех инстансах"** — проблема в multi-instance. Если запущено 3 инстанса Strapi (horizontal scaling), cron выполнится 3 раза. Решение: distributed locking через Redis или вынести cron в отдельный сервис/Lambda.

- **"Bootstrap вызывается каждый раз при запросе"** — нет. Bootstrap вызывается один раз при старте приложения. Register — тоже один раз, до bootstrap. Для кода выполняемого per-request — middleware или lifecycle hooks.

- **"EventHub в Strapi и Node.js EventEmitter — одно и то же"** — EventHub построен поверх Node.js EventEmitter, но добавляет именованные события Strapi (entry.create, entry.update, entry.publish, etc.). EventHub хорошо подходит для decoupled side effects, но не гарантирует доставку при сбоях — для надёжных событий нужна очередь (BullMQ, RabbitMQ).
