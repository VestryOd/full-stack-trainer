# Lifecycle Hooks and Customization

## All lifecycle events

A lifecycle hook is a function that Strapi runs automatically around a database operation on one Content Type. It runs either just before that operation or just after it. Nobody calls it by name. Putting it in the right file is what registers it.

That file is `lifecycles.ts`, and it sits next to the schema of the content type it serves. Each key of the exported object is the name of an event, and the names combine a prefix with an operation:

- `beforeCreate` and `afterCreate`, and the same pair for `Update` and `Delete`;
- `beforeFindOne`, `afterFindOne`, `beforeFindMany` and `afterFindMany` for reads;
- `beforeCount`, `afterCount` and the bulk `CreateMany`, `UpdateMany`, `DeleteMany` variants.

Every hook receives one `event` object. A before hook reads and changes `event.params`, which holds the `data` being written and the `where` of the query. An after hook also gets `event.result`, the record the operation produced. If you happen to know Prisma middleware or Mongoose pre and post hooks, this is the same idea.

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

The file `src/index.ts` is where you hook into the startup of the whole application rather than into one Content Type. It exports two functions, and what separates them is timing.

The function `register()` runs first, before Strapi has finished setting itself up and before plugins are loaded. Keep it lean, because most of the `strapi` object is not ready yet. It suits registering custom fields, extending content types programmatically, and adding a server-level middleware the way the example does.

The function `bootstrap()` runs after the application is set up but before the server starts accepting requests, so the whole `strapi` object is available. It is the place for seeding data that has to exist, subscribing to events, and registering cron jobs.

The example does two of those. It subscribes to `entry.create` through the EventHub, which is Strapi's internal event bus. It also creates a default category when none exists.

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

A cron job is a task Strapi runs on a schedule, with no HTTP request behind it. Clearing out stale records, recomputing statistics and sending digests are the usual cases.

Tasks are declared in `config/cron-tasks.ts` and switched on in `config/server.ts`. The `cron` setting there takes `enabled: true` together with the task object. Each entry pairs a schedule with a `task` function that receives `{ strapi }`, so whatever a service can reach is reachable here too.

The keys below are cron expressions, and the comment above each one says when it fires. The `options` object carries `tz`, the time zone the schedule is read in, named as in the standard time zone database. Strapi also documents a named form, where the key is the job name and the schedule moves into `options.rule`.

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

A webhook is an API call in reverse. Instead of a client asking Strapi for data, Strapi sends an HTTP POST to an address you registered whenever something happens to the content.

You add one in Admin Panel → Settings → Webhooks, give it a URL and tick the events it should react to. The choices include `entry.create`, `entry.update`, `entry.delete`, `entry.publish` and `entry.unpublish`, plus the media events. The request carries an `X-Strapi-Event` header naming the event and a JSON body with the event, the model and the entry itself. Private fields are left out of it.

The second half of the block does the same job from code. Subscribing to the EventHub inside `bootstrap()` delivers the event inside the process, which is what you want when the reaction is your own call. Here it purges a CDN (content delivery network) after publishing.

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

These three tools overlap, and choosing the wrong one is the usual source of behaviour nobody can find later. Two questions settle it: when should the code run, and how visible should it be?

A hook is invisible from outside. It fires on a data operation whether or not the caller expected it. That makes it right for small automatic touches, and wrong for business rules.

A service is called explicitly by name, so the logic stays where a reader goes looking for it. Bootstrap runs once at startup and takes everything that has to exist before the first request arrives. The block below sorts the concrete cases, and the ✗ lines matter as much as the ✓ ones.

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

- **"afterCreate can't see the just-created record"** — it can. The field `event.result` in after hooks contains the result of the operation. That is the created record with all its fields, including the generated `id` and `documentId`. In before hooks, `event.result` is not available (the operation hasn't been executed yet).

- **"Cron Jobs run on all instances"** — this is a problem in multi-instance setups. If 3 Strapi instances are running (horizontal scaling), the cron will execute 3 times. Solution: distributed locking via Redis, or move the cron to a separate service/Lambda.

- **"Bootstrap is called on every request"** — no. Bootstrap is called once when the application starts. Register is also called once, before bootstrap. For per-request code — use middleware or lifecycle hooks.

- **"Strapi's EventHub and Node.js EventEmitter are the same thing"** — EventHub is built on top of Node.js EventEmitter. It adds named Strapi events of its own: entry.create, entry.update, entry.publish and others. EventHub is suitable for decoupled side effects, but does not guarantee delivery on failure — for reliable events you need a queue (BullMQ, RabbitMQ).
