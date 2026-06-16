# Lifecycle Hooks and Customization

## All lifecycle events

Lifecycle Hooks are a mechanism for running code before/after data operations. Analogous to Prisma middleware or Mongoose pre/post hooks. Used for cross-cutting concerns tied to operations on a specific Content Type.

```typescript
// src/api/article/content-types/article/lifecycles.ts
export default {
  // ===== BEFORE HOOKS =====

  async beforeCreate(event) {
    const { data } = event.params;

    // Auto-generate slug from title
    if (data.title && !data.slug) {
      data.slug = data.title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '');
    }

    // Set publishedAt on creation
    // (if Draft & Publish is disabled)
    data.publishedAt = new Date();
  },

  async beforeUpdate(event) {
    const { data } = event.params;

    // Update slug if title changed
    if (data.title) {
      data.slug = data.title.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    }
  },

  async beforeDelete(event) {
    const { where } = event.params;

    // Check dependencies before deletion
    const commentsCount = await strapi.documents('api::comment.comment').count({
      filters: { article: where.id },
    });

    if (commentsCount > 0) {
      // Throw an error — deletion is blocked
      throw new Error(`Cannot delete article with ${commentsCount} comments`);
    }
  },

  // ===== AFTER HOOKS =====

  async afterCreate(event) {
    const { result } = event;

    // Send notification to editor
    await strapi.service('api::notification.notification').sendNewArticleNotification({
      articleId: result.documentId,
      title: result.title,
    });

    // Write to audit log
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

    // If article is published — invalidate cache
    if (result.publishedAt && !params.data?.publishedAt) {
      await strapi.service('api::cache.cache').invalidate(`article:${result.documentId}`);
    }
  },

  async afterDelete(event) {
    const { result } = event;
    strapi.log.info(`Article deleted: ${result.title} (${result.documentId})`);
  },

  // Read hooks (less commonly used)
  async afterFindMany(event) {
    const { result } = event;
    // result — array of found records
    // Can be transformed before returning
  },
};
```

## Bootstrap and Register — initialization at startup

```typescript
// src/index.ts — main Strapi customization file
export default {
  /**
   * register — called BEFORE plugins are loaded.
   * Register custom services, controllers, content types.
   */
  register({ strapi }) {
    // Register a custom middleware globally
    strapi.server.use(async (ctx, next) => {
      ctx.set('X-Custom-Header', 'value');
      await next();
    });
  },

  /**
   * bootstrap — called AFTER all plugins are loaded.
   * Initialize data, subscribe to events, register Cron Jobs.
   */
  async bootstrap({ strapi }) {
    // Subscribe to an event via EventHub
    strapi.eventHub.on('entry.create', async ({ model, entry }) => {
      strapi.log.info(`New entry created in ${model}: ${entry.id}`);
    });

    // Create default data if none exists
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

## Cron Jobs — periodic tasks

```typescript
// config/cron-tasks.ts
export default {
  // Every night at 02:00 — clean up old draft articles
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

  // Every hour — update statistics
  '0 * * * *': {
    task: async ({ strapi }) => {
      await strapi.service('api::stats.stats').updateHourlyStats();
    },
    enabled: process.env.NODE_ENV === 'production',
  },
};
```

## Webhooks — notifying external systems

```typescript
// Admin Panel → Settings → Webhooks → Add new webhook

// Strapi sends a POST request when an event occurs:
// {
//   "event": "entry.create",
//   "createdAt": "2024-01-15T10:00:00.000Z",
//   "model": "article",
//   "uid": "api::article.article",
//   "entry": { "id": 1, "title": "New Article", ... }
// }

// Custom Webhook via EventHub:
// src/index.ts bootstrap():
strapi.eventHub.on('entry.publish', async ({ model, entry }) => {
  if (model === 'article') {
    // Notify CDN about new content
    await fetch('https://cdn.example.com/purge', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${process.env.CDN_TOKEN}` },
      body: JSON.stringify({ path: `/articles/${entry.slug}` }),
    });
  }
});
```

## When to use Hook vs Service vs Bootstrap

```txt
Lifecycle Hook:
  ✓ Auto-generating values (slug, permalink)
  ✓ Audit / logging of model operations
  ✓ Synchronous validations at the data level
  ✓ Cache invalidation on update
  ✗ NOT complex business logic (hides logic)
  ✗ NOT external API calls (side effects should be explicit)

Service:
  ✓ Business logic (aggregation, calculations, rules)
  ✓ Working with multiple Content Types
  ✓ External API calls
  ✓ Reusable logic

Bootstrap:
  ✓ Initialization at startup (seed data, connections)
  ✓ Global event subscriptions
  ✓ Cron Job registration
  ✓ Middleware registration
```

## Common interview mistakes

- **"Lifecycle Hook is the best place for business logic"** — no. Hooks hide logic: a developer reads the Service and doesn't see that additional operations fire on save. Complex logic in a Hook = hard to test, hard to debug, unexpected side effects. Hooks for automatic data mutations, Services for business rules.

- **"afterCreate can't see the just-created record"** — it can. `event.result` in after hooks contains the result of the operation — the created record with all fields including the generated `id` and `documentId`. In before hooks, `event.result` is not available (the operation hasn't been executed yet).

- **"Cron Jobs run on all instances"** — this is a problem in multi-instance setups. If 3 Strapi instances are running (horizontal scaling), the cron will execute 3 times. Solution: distributed locking via Redis, or move the cron to a separate service/Lambda.

- **"Bootstrap is called on every request"** — no. Bootstrap is called once when the application starts. Register is also called once, before bootstrap. For per-request code — use middleware or lifecycle hooks.

- **"Strapi's EventHub and Node.js EventEmitter are the same thing"** — EventHub is built on top of Node.js EventEmitter but adds named Strapi events (entry.create, entry.update, entry.publish, etc.). EventHub is suitable for decoupled side effects, but does not guarantee delivery on failure — for reliable events you need a queue (BullMQ, RabbitMQ).
