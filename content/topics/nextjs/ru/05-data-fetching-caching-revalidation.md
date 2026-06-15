<!-- verified: 2026-06-05, corrections: 1 -->
# Data Fetching, Caching и Revalidation

## Четыре уровня кеширования в Next.js — must-know для senior

Один из самых частых senior-вопросов — "сколько уровней кеша есть в Next.js и в чём разница". Большинство кандидатов знают только про `fetch`-кеш, но в App Router их **четыре**, и они работают независимо:

```txt
1. Request Memoization  — дедупликация одинаковых fetch() в рамках ОДНОГО рендера
                           (живёт только пока рендерится дерево, потом сбрасывается)

2. Data Cache           — персистентный кеш результатов fetch() между запросами
                           и между деплоями (если используется persistent storage)

3. Full Route Cache     — кеш отрендеренного HTML + RSC payload для статических роутов,
                           создаётся во время build или при первом запросе

4. Router Cache         — клиентский кеш (in-memory, per-session) для навигации
                           между уже посещёнными маршрутами
```

Путаница на интервью почти всегда возникает из-за того, что кандидат отвечает только про Data Cache, когда вопрос на самом деле про Full Route Cache (или наоборот) — это разные слои с разными механизмами инвалидации.

## 1. Request Memoization

Если в рамках одного рендера дерева несколько компонентов независимо вызывают `fetch()` с одинаковыми URL и опциями, React/Next выполнит **один** реальный HTTP-запрос, а остальные вызовы получат тот же результат из памяти:

```tsx
// app/layout.tsx
async function getUser() {
  const res = await fetch('https://api.example.com/me');
  return res.json();
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const user = await getUser(); // запрос #1
  return <html><body><Header user={user} />{children}</body></html>;
}

// app/dashboard/page.tsx
async function getUser() {
  const res = await fetch('https://api.example.com/me');
  return res.json();
}

export default async function DashboardPage() {
  const user = await getUser(); // тот же URL — НЕ новый запрос, берётся из памяти
  return <Profile user={user} />;
}
```

Это работает только для `fetch` (и `React.cache`-обёрток для других источников данных, например прямых запросов к БД) и **только в пределах одного server-side рендера** — между разными запросами пользователей память не сохраняется. Это решает проблему "N компонентов — N одинаковых запросов", но не заменяет персистентный кеш.

## 2. Data Cache — кеш результатов fetch между запросами

Это то, что обычно подразумевают под "Next.js кеширует fetch". В отличие от Request Memoization, Data Cache **переживает отдельные запросы пользователей** (и в некоторых случаях — деплои, если настроено персистентное хранилище).

### Важное изменение в Next.js 15

```txt
Next.js 13/14: fetch() по умолчанию → cache: 'force-cache' (кешируется)
Next.js 15:    fetch() по умолчанию → cache: 'no-store'    (не кешируется)
```

Это одно из самых обсуждаемых breaking changes в истории Next.js — множество проектов, мигрировавших на v15, неожиданно получили SSR-поведение там, где раньше было SSG, потому что явно не указывали `cache`. На собеседовании важно не просто знать факт, а уметь объяснить мотивацию: команда Next посчитала, что "тихое" кеширование по умолчанию было source of truth для множества production-багов с устаревшими данными, и сделала поведение явным.

```ts
// SSG-подобное поведение: результат кешируется бессрочно (до явной инвалидации)
fetch('https://api.example.com/products', { cache: 'force-cache' });

// SSR-подобное поведение: новый запрос на каждый рендер
fetch('https://api.example.com/products', { cache: 'no-store' });

// ISR-подобное поведение: кеш на 60 секунд, потом фоновая регенерация
fetch('https://api.example.com/products', { next: { revalidate: 60 } });
```

### Кеширование источников данных, не использующих fetch

`fetch` — не единственный способ получать данные, и Data Cache "из коробки" работает только с ним. Для произвольных асинхронных функций (например, запросов через Prisma) используется `unstable_cache`:

```ts
import { unstable_cache } from 'next/cache';

export const getProducts = unstable_cache(
  async () => db.product.findMany(),
  ['products'],                 // key parts
  { revalidate: 60, tags: ['products'] },
);
```

## 3. Full Route Cache

Это кеш **результата рендера целого маршрута** — HTML и RSC payload, сгенерированные во время build (для статических маршрутов) или при первом запросе (для маршрутов, "догенерированных" по требованию). Это то, что физически лежит на CDN/edge и отдаётся без выполнения серверного кода.

Маршрут попадает в Full Route Cache, если он **полностью статический** — то есть не использует:

```txt
cookies()
headers()
searchParams (в Server Component)
fetch с cache: 'no-store'
export const dynamic = 'force-dynamic'
```

Использование любого из этого помечает маршрут как **dynamic**, и Full Route Cache для него не применяется — каждый запрос рендерится заново (хотя Data Cache внутри него может продолжать работать).

```tsx
// Этот сегмент НЕ попадёт в Full Route Cache,
// даже если все fetch внутри кешируются через Data Cache
export default async function Page() {
  const session = cookies().get('session'); // → dynamic rendering
  const products = await fetch(url, { cache: 'force-cache' }); // Data Cache всё ещё работает
  ...
}
```

## 4. Router Cache (Client-Side Router Cache)

Клиентский, in-memory кеш RSC payload для маршрутов, по которым пользователь уже переходил в текущей сессии. Он отвечает за то, что навигация "вперёд/назад" по уже посещённым страницам происходит мгновенно, без повторного запроса к серверу. Этот кеш живёт в памяти браузера и сбрасывается при полной перезагрузке страницы.

## Revalidation: путь, тег и их различие

```ts
// app/api/revalidate/route.ts
import { revalidatePath, revalidateTag } from 'next/cache';

export async function POST(request: Request) {
  const { type, value } = await request.json();

  if (type === 'path') {
    revalidatePath('/blog'); // инвалидирует Full Route Cache для конкретного пути
  } else {
    revalidateTag('posts'); // инвалидирует ВСЕ fetch-вызовы с этим тегом,
                             // на любых маршрутах, где он использовался
  }

  return Response.json({ revalidated: true, now: Date.now() });
}
```

- `revalidatePath('/blog')` — точечно сбрасывает закешированный рендер конкретного маршрута (и опционально его дочерних сегментов).
- `revalidateTag('posts')` — сбрасывает Data Cache для *всех* `fetch`-вызовов, помеченных тегом `posts`, независимо от того, на каком маршруте они выполнялись. Это удобно, когда один и тот же ресурс используется на нескольких страницах (например, список постов на главной и на странице блога).

Типичный сценарий — webhook от CMS при публикации статьи:

```ts
// Контент-менеджер опубликовал статью в Strapi/Contentful
// → webhook вызывает /api/revalidate с тегом 'posts'
// → все страницы, чьи fetch были помечены tags: ['posts'], станут stale
// → следующий запрос к ним вызовет регенерацию в фоне (ISR-семантика)
```

## generateStaticParams — аналог getStaticPaths

```tsx
// app/blog/[slug]/page.tsx
export async function generateStaticParams() {
  const posts = await getAllPosts();
  return posts.map((post) => ({ slug: post.slug }));
}

export default async function BlogPost({ params }: { params: { slug: string } }) {
  const post = await getPost(params.slug);
  return <Article post={post} />;
}
```

Нюанс: для путей, не возвращённых из `generateStaticParams`, поведение зависит от `export const dynamicParams` (по умолчанию `true`) — Next сгенерирует страницу по требованию при первом запросе и закеширует результат (аналог `fallback: 'blocking'` из Pages Router). При `dynamicParams = false` запрос к несуществующему пути вернёт 404.

## Что делает маршрут "динамическим" — полный список триггеров

```txt
cookies(), headers()              — доступ к request-специфичным данным
searchParams в Server Component   — параметры запроса различаются между запросами
fetch(..., { cache: 'no-store' })
fetch(..., { next: { revalidate: 0 } })
export const dynamic = 'force-dynamic'
export const fetchCache = 'force-no-store'
```

Любой из этих признаков "поднимается" вверх по дереву layout'ов — если хотя бы один сегмент на маршруте динамический, весь маршрут рендерится динамически (статические части layout всё равно могут использовать собственный Data Cache).

## Practical пример: e-commerce страница товара

```tsx
// app/products/[id]/page.tsx

// Каталог большой — не генерируем все страницы при билде,
// но генерируем популярные заранее
export async function generateStaticParams() {
  const popular = await getPopularProductIds();
  return popular.map((id) => ({ id }));
}

export default async function ProductPage({ params }: { params: { id: string } }) {
  // Данные о товаре меняются нечасто — ISR с тегом для on-demand инвалидации
  const product = await fetch(`https://api.example.com/products/${params.id}`, {
    next: { revalidate: 3600, tags: [`product-${params.id}`] },
  }).then((r) => r.json());

  // Цена/наличие — почти real-time, отдельный динамический fetch
  const stock = await fetch(`https://api.example.com/stock/${params.id}`, {
    cache: 'no-store',
  }).then((r) => r.json());

  return <ProductView product={product} stock={stock} />;
}
```

Здесь сознательно скомбинированы три модели в рамках одной страницы: статически сгенерированные популярные товары (SSG), долгий ISR-кеш для редко меняющихся данных о товаре, и динамический fetch для остатков на складе. Это и есть тот "гранулярный" подход, который отличает App Router от модели "одна страница — одна стратегия рендеринга" в Pages Router.

## Типичные ошибки на интервью

- **"fetch в Next.js кешируется по умолчанию"** — верно для Next.js 13/14, неверно для Next.js 15 (default стал `no-store`). Хороший ответ показывает, что вы знаете *про какую версию* говорите и почему это изменилось.

- **Путают Data Cache и Full Route Cache** — например, говорят "я указал `revalidate: 60` для fetch, но страница всё равно рендерится динамически из-за `cookies()`". Это ожидаемо: Data Cache работает независимо от Full Route Cache, но `cookies()` делает маршрут dynamic на уровне Full Route Cache в любом случае.

- **"revalidateTag и revalidatePath — это одно и то же, просто разные аргументы"** — нет: `revalidatePath` целится в конкретный маршрут (и Full Route Cache для него), `revalidateTag` — в данные по всему приложению, независимо от того, на каких маршрутах они используются.

- **Не знают про Request Memoization** — и поэтому либо вручную "поднимают" фетч на верхний уровень и тащат данные через props (что убивает colocation), либо думают, что N вызовов одного и того же `fetch` в дереве — это N HTTP-запросов.

- **"unstable_cache — это нестабильная экспериментальная фича, которую нельзя использовать в проде"** — `unstable_` в названии исторически означает, что API может измениться в будущих версиях, а не что оно "сломано" или непригодно для прода. Это стандартный способ кешировать non-fetch источники данных.

- **Не могут назвать список того, что делает маршрут dynamic** — а это один из самых практических навыков: умение посмотреть на код и предсказать, попадёт ли страница в Full Route Cache или будет рендериться на каждый запрос.
