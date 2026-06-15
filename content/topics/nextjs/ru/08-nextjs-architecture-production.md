<!-- verified: 2026-06-05, corrections: 0 -->
# Production Architecture и Best Practices

## Уровень вопросов

Этот блок — про архитектурные решения, которые принимает не "разработчик фичи", а тот, кто отвечает за то, как приложение масштабируется, деплоится и эксплуатируется. Типичные формулировки: "как бы вы построили проект на Next.js", "где граница между Next и остальным backend", "что вы вынесете в Server Actions, а что в Route Handlers".

```txt
Browser
 ↓
CDN / Edge
 ↓
Next.js (rendering + BFF layer)
 ↓
Backend APIs / Microservices
 ↓
Database
```

## Вариант 1: Next как тонкий frontend-слой

```txt
Next.js (UI, SSR/SSG)
 ↓
NestJS API (бизнес-логика, авторизация, БД)
 ↓
PostgreSQL
```

Next отвечает только за рендеринг и UX, вся бизнес-логика — в отдельном backend-сервисе. Это понятная и распространённая схема, особенно когда backend уже существует и обслуживает несколько клиентов (web, mobile, partner API) — Next в этом случае просто один из консьюмеров API.

## Вариант 2: Next как BFF (Backend For Frontend)

```txt
Browser
 ↓
Next.js (агрегирует, трансформирует, кеширует)
 ↓
┌──────────────┬──────────────┬──────────────┐
User Service    Product Service   Order Service
 ↓
PostgreSQL / разные БД для разных сервисов
```

Next агрегирует данные из нескольких микросервисов и отдаёт фронтенду единый, заточенный под конкретный экран API (через Route Handlers или прямо через Server Components). Frontend не знает про внутреннюю топологию сервисов — вся сложность инкапсулирована в BFF.

**Где проходит граница BFF vs полноценный backend** — практический вопрос: BFF хорош для *агрегации и трансформации под UI* (объединить данные из 3 сервисов в один JSON для конкретного экрана, кеширование на уровне Next), но не должен превращаться в место, где живёт бизнес-логика с побочными эффектами на несколько доменов (например, "оформление заказа", которое должно атомарно списать остатки, создать платёж и отправить уведомление) — это ответственность доменных сервисов с собственными транзакционными гарантиями.

## Server Actions vs Route Handlers — когда что

Это один из самых частых "практических" вопросов на Next.js собеседованиях, и ответ "и то, и то — для бэкенда" — недостаточен.

```tsx
// Server Action — мутация, инициированная формой/UI текущего приложения
'use server';

import { revalidatePath } from 'next/cache';

export async function createComment(formData: FormData) {
  const text = formData.get('text');
  if (typeof text !== 'string' || text.trim().length === 0) {
    return { error: 'Comment cannot be empty' };
  }

  await db.comment.create({ data: { text, postId: formData.get('postId') as string } });
  revalidatePath('/posts'); // инвалидация кеша сразу после мутации
  return { success: true };
}
```

```tsx
// app/posts/[id]/page.tsx
import { createComment } from './actions';

export default function PostPage() {
  return (
    <form action={createComment}>
      <textarea name="text" />
      <button type="submit">Send</button>
    </form>
  );
}
```

```ts
// Route Handler — публичный API endpoint, вызываемый извне (не только из UI)
// app/api/webhooks/stripe/route.ts
export async function POST(request: Request) {
  const signature = request.headers.get('stripe-signature');
  const body = await request.text();

  const event = stripe.webhooks.constructEvent(body, signature!, process.env.STRIPE_WEBHOOK_SECRET!);
  // ... обработка события
  return new Response('ok', { status: 200 });
}
```

| | Server Actions | Route Handlers |
|---|---|---|
| Кто вызывает | Формы и UI-код этого же приложения | Любой клиент: webhook, mobile-приложение, сторонний сервис |
| Контракт | Неявный (привязан к конкретной форме/функции) | Явный REST/JSON-контракт, версионируемый |
| Типичные кейсы | CRUD-мутации, формы, optimistic UI с `useOptimistic` | Webhooks, публичный API, интеграции, OAuth callbacks |
| Кеш-инвалидация | `revalidatePath`/`revalidateTag` прямо в действии | Обычно тоже, но часто как отдельный `/api/revalidate` |

Антипаттерн — городить публичный API через Server Actions (они создают неявные, "магические" endpoint'ы под капотом, не предназначенные для внешних потребителей и без версионирования) или, наоборот, делать Route Handler для каждой формы в UI, теряя преимущества прогрессивного улучшения (`<form action={...}>` работает даже без JS).

## Edge Runtime vs Node.js Runtime

```ts
// app/api/heavy/route.ts
export const runtime = 'nodejs'; // по умолчанию для Route Handlers

// app/api/light/route.ts
export const runtime = 'edge'; // выполняется на Edge (V8 isolates)
```

| | Node.js Runtime | Edge Runtime |
|---|---|---|
| Доступные API | Полный Node.js (`fs`, `net`, нативные модули) | Web-стандартные API (fetch, crypto, Streams) |
| Холодный старт | Выше | Минимальный/отсутствует |
| География | Один регион (или несколько, в зависимости от хостинга) | Близко к пользователю, множество edge-локаций |
| ORM (Prisma и т.п.) | Работает "из коробки" | Требует Edge-совместимого драйвера/адаптера |
| Размер бандла | Без жёстких лимитов | Лимиты на размер (обычно ~1-4 МБ в зависимости от провайдера) |

Практическое правило: всё, что обращается к традиционной реляционной БД через стандартный TCP-driver (Prisma с `pg`), — Node runtime. Edge подходит для лёгких, латентность-критичных операций: geo-based логики, простых проверок токенов, прокси-запросов к внешним API.

## Caching Strategy — не "одна модель", а карта по экранам

Production-приложение почти никогда не использует одну модель рендеринга. Хороший ответ на "как вы будете кешировать e-commerce" — это таблица, а не одно слово:

```txt
Homepage              → SSG + revalidate (раз в час, контент почти статичен)
Категории товаров      → ISR, revalidateTag('category-X') при изменении ассортимента
Страница товара        → ISR + on-demand revalidation (webhook от CMS/PIM при изменении цены)
Поиск/фильтры          → SSR или CSR (комбинации параметров непредсказуемы — кешировать невыгодно)
Корзина                → CSR (state привязан к сессии/cookie конкретного пользователя)
Checkout                → Server Actions / Route Handler с server runtime (платежи, побочные эффекты)
Личный кабинет          → SSR (cookies() → dynamic) или CSR с client-side data fetching
Admin-панель            → CSR, часто за отдельным auth-слоем, SEO не нужен
```

## Environment Variables — граница безопасности

```bash
# .env
DATABASE_URL=postgres://...          # доступен ТОЛЬКО на сервере
STRIPE_SECRET_KEY=sk_live_...         # доступен ТОЛЬКО на сервере
NEXT_PUBLIC_API_URL=https://api...    # попадает в клиентский бандл
```

```ts
// ❌ Опасно — секрет случайно используется в коде, который может попасть в Client Component
export function getApiKey() {
  return process.env.STRIPE_SECRET_KEY; // если этот модуль импортирован в 'use client' файл —
}                                        // переменная может быть инлайнена в бандл при сборке

// ✅ Защита через server-only
import 'server-only';
export function getApiKey() {
  return process.env.STRIPE_SECRET_KEY;
}
```

Правило `NEXT_PUBLIC_*` — это не "удобный префикс", это **инлайнинг значения переменной в JS-бандл во время сборки**. Из этого следует нетривиальное практическое следствие: смена значения `NEXT_PUBLIC_*` переменной требует **пересборки** приложения — простого изменения переменной окружения в runtime-конфигурации контейнера/хостинга недостаточно, старое значение останется "зашитым" в уже собранный бандл.

## Monitoring и Observability

```txt
Error tracking:       Sentry, Bugsnag — особенно важно ловить ошибки
                        и в Server Components, и в Client Components отдельно
Performance:          Vercel Analytics / Core Web Vitals, Datadog RUM
Server-side метрики:  логирование Route Handlers, Server Actions,
                        latency запросов к БД/внешним API
```

Нюанс specific для App Router: ошибка в Server Component происходит на сервере и **не появляется в browser console** — без серверного error tracking (Sentry с серверным SDK) такие ошибки можно полностью пропустить, видя только generic "Something went wrong" из `error.tsx`.

## Deployment

```txt
Vercel       — "родная" платформа, нулевая конфигурация для ISR/Edge/Streaming,
                но vendor lock-in для специфичных фич (например, on-demand ISR
                может работать иначе на других платформах)
Self-hosted  — `next start` после `next build`, либо Docker + Node.js сервер;
                для ISR/ревалидации нужна персистентная файловая система
                или внешнее хранилище кеша
Static export — `output: 'export'`, превращает приложение в чистую статику
                (без Server Components с динамикой, без Route Handlers,
                без Image Optimization API) — подходит для простых сайтов
                без серверной части, деплоится на любой статический хостинг
```

## Сквозной пример: e-commerce

```txt
Homepage, категории        → SSG/ISR, CDN
Карточка товара             → ISR + revalidateTag по webhook от PIM
Поиск                       → SSR (Route Handler проксирует в Elasticsearch)
Корзина                      → CSR + localStorage/cookie, синхронизация через Server Action
Checkout                     → Server Actions (создание заказа) +
                                Route Handler (webhook от платёжного провайдера)
Личный кабинет, заказы       → SSR (cookies() для сессии)
Admin                         → CSR, отдельный auth, runtime: 'nodejs' для всех API
```

## Самый сильный senior-ответ

На вопрос "что самое важное в production Next.js приложении" слабый ответ — перечислить фичи (SSR/ISR/Server Actions). Сильный ответ — что не существует единой "правильной" модели: production-приложение — это *композиция* решений по рендерингу, кешированию и runtime, принимаемых **для каждого экрана отдельно**, на основе требований к SEO, свежести данных, латентности и стоимости вычислений. Архитектор отвечает не за "выбор Next.js фичи", а за то, чтобы эта композиция была явной, документированной и не превращалась в случайный набор `cache: 'no-store'`, расставленных по мере появления багов с устаревшими данными.

## Типичные ошибки на интервью

- **"Next.js заменяет backend полностью"** — в большинстве production-архитектур Next — это слой рендеринга и BFF, а не источник истины для бизнес-логики и данных.

- **"Server Actions — это просто новый способ писать API"** — у них другая модель вызова (привязаны к конкретным формам/компонентам, не имеют стабильного публичного контракта) и другие случаи использования, чем у Route Handlers.

- **Не знают, что Edge Runtime ограничивает выбор ORM/драйверов БД** — стандартный Prisma + `pg` не работает на Edge без адаптера; это частая причина "runtime ошибок в проде, которых не было локально".

- **"NEXT_PUBLIC_ переменные можно менять в runtime без пересборки"** — нет, они инлайнятся в бандл на этапе `next build`. Изменение требует ребилда.

- **Дают один ответ на "как кешировать сайт", не различая разные экраны** — сильный ответ — это таблица "тип страницы → стратегия", а не единое решение для всего приложения.

- **Не упоминают, что ошибки Server Components не видны в браузере** — критично для построения observability: без серверного error tracking часть продакшен-багов будет полностью невидима для команды.

- **"Static export (`output: 'export'`) поддерживает все фичи App Router"** — нет, он исключает Server Actions, Route Handlers с динамикой, Image Optimization API и любую серверную динамику — фактически это режим "только статика".
