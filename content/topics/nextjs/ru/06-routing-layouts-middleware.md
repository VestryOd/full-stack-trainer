<!-- verified: 2026-06-05, corrections: 1 -->
# Routing, Layouts и Middleware

## File-system routing: основы и нюансы типизации

В App Router маршрут определяется *папкой*, а не файлом — файл `page.tsx` внутри папки делает её доступной как маршрут. Это отличие важно: можно создать папку `app/blog/components/` с обычными компонентами, и она **не** станет маршрутом, потому что в ней нет `page.tsx`.

```txt
app/
 ├─ page.tsx              → /
 ├─ about/
 │   └─ page.tsx          → /about
 ├─ blog/
 │   ├─ page.tsx          → /blog
 │   └─ [id]/
 │       └─ page.tsx      → /blog/:id
```

### Dynamic Segments

```tsx
// app/blog/[id]/page.tsx
// Next.js 15: params и searchParams теперь Promise
export default async function BlogPost({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { id } = await params;
  const post = await getPost(id);
  return <Article post={post} />;
}
```

`id` (из `await params`) всегда `string` (или `string[]` для catch-all) — даже если по смыслу это число, Next не делает автоматического приведения типов. Частая ошибка — забыть `Number(params.id)`/`parseInt` перед использованием в запросе к БД, где ожидается числовой ID.

### Catch-all и Optional Catch-all

```txt
app/docs/[...slug]/page.tsx     → /docs/a, /docs/a/b, /docs/a/b/c
                                    НЕ матчит /docs (нужен хотя бы 1 сегмент)

app/docs/[[...slug]]/page.tsx   → /docs, /docs/a, /docs/a/b
                                    матчит И /docs (slug будет undefined)
```

```tsx
// app/docs/[...slug]/page.tsx
export default async function DocsPage({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params; // Next.js 15: params стал async
  // /docs/react/hooks/useEffect → slug = ['react', 'hooks', 'useEffect']
  const path = slug.join('/');
  return <DocContent path={path} />;
}
```

Типичное применение — CMS/docs-сайты, где дерево страниц произвольной глубины определяется внешним источником данных, а не файловой структурой.

### Route Groups — организация без влияния на URL

```txt
app/
 ├─ (marketing)/
 │   ├─ layout.tsx        → отдельный layout только для маркетинговых страниц
 │   ├─ page.tsx          → /
 │   └─ about/page.tsx    → /about
 ├─ (app)/
 │   ├─ layout.tsx        → отдельный layout для авторизованной части
 │   └─ dashboard/page.tsx → /dashboard
```

Папки в круглых скобках `(marketing)`, `(app)` — **не попадают в URL**. Это позволяет иметь несколько независимых Root-подобных layout'ов (например, один с публичным хедером, другой — с авторизованным сайдбаром) без вложенности друг в друга.

### Parallel Routes и Intercepting Routes (продвинутый уровень)

```txt
app/
 ├─ @modal/                  → "слот" — параллельный сегмент
 │   └─ (.)photo/[id]/page.tsx  → intercepting route
 ├─ photo/[id]/page.tsx
 └─ layout.tsx
```

`@modal` — именованный параллельный слот, рендерящийся независимо от основного контента через `layout.tsx`, который принимает его как отдельный проп:

```tsx
// app/layout.tsx
export default function Layout({
  children,
  modal,
}: {
  children: React.ReactNode;
  modal: React.ReactNode;
}) {
  return (
    <>
      {children}
      {modal}
    </>
  );
}
```

`(.)photo` — *intercepting route*: при клиентской навигации на `/photo/123` (например, по клику из ленты) открывается модалка с фото *поверх* текущей страницы, но при прямом заходе по URL (refresh, шаринг ссылки) или серверном переходе рендерится полноценная страница `/photo/[id]`. Это классический паттерн "Instagram-style" модалок для фотографий — на интервью senior-уровня его иногда спрашивают именно через формулировку "как сделать так, чтобы клик по фото открывал модалку, но прямая ссылка на фото открывала отдельную страницу".

## Layout, Template, Loading, Error, Not Found — файловые конвенции

```txt
app/dashboard/
 ├─ layout.tsx     → персистентный UI-каркас, НЕ перемонтируется при навигации внутри сегмента
 ├─ template.tsx   → как layout, но ПЕРЕМОНТИРУЕТСЯ на каждую навигацию
 ├─ loading.tsx    → автоматический <Suspense fallback>
 ├─ error.tsx      → автоматический Error Boundary (Client Component)
 ├─ not-found.tsx  → рендерится при вызове notFound() или несуществующем catch-all пути
 └─ page.tsx       → контент маршрута
```

### Layout vs Template — когда нужен именно Template

`layout.tsx` сохраняет состояние и DOM при навигации между дочерними маршрутами — это и есть основное преимущество App Router (сайдбар не "мигает", скролл не сбрасывается). Но иногда такое поведение **нежелательно**:

```tsx
// app/blog/[slug]/template.tsx
'use client';

import { useEffect } from 'react';

export default function Template({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // Должен срабатывать на КАЖДЫЙ переход между статьями,
    // даже если URL меняется в рамках одного сегмента
    analytics.trackPageView();
  }, []);

  return <>{children}</>;
}
```

Если бы это был `layout.tsx`, `useEffect` сработал бы только при первом монтировании сегмента, а не при каждом переходе между `/blog/post-1` и `/blog/post-2` (т.к. layout не размонтируется). `template.tsx` решает именно этот класс задач: per-navigation эффекты, CSS-анимации входа/выхода, сброс локального состояния формы между шагами визарда.

### Nested Layouts — что именно не перемонтируется

```txt
Root Layout
 └─ Dashboard Layout
     └─ Settings Page
```

При переходе `/dashboard/settings/profile` → `/dashboard/settings/billing`:

```txt
Root Layout      — не перемонтируется
Dashboard Layout — не перемонтируется
Settings Layout  — не перемонтируется (если есть)
page.tsx         — заменяется новым содержимым
```

Next запрашивает с сервера только RSC payload для изменившегося сегмента — общие layout'ы остаются смонтированными React-деревом, поэтому состояние (открытое меню, позиция скролла внутри сайдбара) не теряется.

## Middleware

### Где выполняется и зачем это важно

Middleware — это код, выполняющийся **до** того, как запрос достигнет роутинга Next.js, на **Edge Runtime** (V8 isolates, а не полноценный Node.js). Это даёт низкую латентность (middleware может выполняться географически близко к пользователю), но накладывает ограничения:

```txt
Недоступно в middleware:
  fs, net, child_process, любые Node-специфичные нативные модули
  Полноценные ORM (Prisma Client в стандартной конфигурации не работает на Edge)

Доступно:
  Web-стандартные API: fetch, Request, Response, URL, crypto (Web Crypto)
  Next-специфичные обёртки: NextRequest, NextResponse
```

### Базовый пример с matcher

```ts
// middleware.ts — обязательно в корне проекта (или src/)
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('session')?.value;

  if (!token) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('from', request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/settings/:path*'],
};
```

`matcher` — это не просто "оптимизация", это необходимость: без него middleware выполняется **для каждого запроса**, включая статические ассеты (`/_next/static/...`), что добавляет латентность ко всему приложению без надобности.

### Redirect vs Rewrite — разница, которую путают чаще всего

```ts
// Redirect — браузер получает 307/308, URL в адресной строке МЕНЯЕТСЯ
return NextResponse.redirect(new URL('/login', request.url));

// Rewrite — запрос обрабатывается другим путём "под капотом",
// URL в адресной строке пользователя ОСТАЁТСЯ прежним
return NextResponse.rewrite(new URL('/internal/maintenance-page', request.url));
```

Практический пример rewrite — A/B тестирование без изменения URL:

```ts
export function middleware(request: NextRequest) {
  const bucket = request.cookies.get('ab-bucket')?.value ?? (Math.random() < 0.5 ? 'a' : 'b');

  const response = bucket === 'b'
    ? NextResponse.rewrite(new URL('/home-variant-b', request.url))
    : NextResponse.next();

  response.cookies.set('ab-bucket', bucket, { maxAge: 60 * 60 * 24 * 30 });
  return response;
}
```

Пользователь видит `/` в адресной строке в обоих случаях, но Next отдаёт содержимое разных страниц в зависимости от куки — это и есть rewrite в действии.

### Geo и Localization

```ts
export function middleware(request: NextRequest) {
  const country = request.geo?.country ?? 'US'; // доступно на Vercel; в self-hosted нужен свой источник
  const locale = country === 'DE' ? 'de' : country === 'FR' ? 'fr' : 'en';

  if (!request.nextUrl.pathname.startsWith(`/${locale}`)) {
    return NextResponse.redirect(new URL(`/${locale}${request.nextUrl.pathname}`, request.url));
  }
  return NextResponse.next();
}
```

### Когда middleware — не лучший выбор

```txt
Хорошо подходит:
  - аутентификация/авторизация на уровне роутинга (проверка наличия токена)
  - редиректы и rewrites
  - модификация заголовков/cookies для всех запросов
  - geo/locale-based routing, A/B bucket assignment

Плохо подходит:
  - проверка токена с походом в БД на каждый запрос (Edge Runtime + латентность БД
    на КАЖДЫЙ запрос, включая статику, если matcher настроен широко)
  - сложная бизнес-логика — её место в Route Handlers/Server Actions,
    где доступен полноценный Node.js runtime
```

Частый антипаттерн — валидация JWT с проверкой в БД (например, проверка "не отозван ли токен") прямо в middleware. Технически возможно через `fetch` к внешнему сервису, но добавляет сетевой round-trip к *каждому* защищённому запросу. Более тяжёлая авторизационная логика обычно переносится в сами Route Handlers/Server Actions, а middleware ограничивается дешёвой проверкой (например, валидностью JWT-подписи без похода в БД).

## Типичные ошибки на интервью

- **"params.id — это число, если в URL цифры"** — нет, `params` всегда строки (или массивы строк для catch-all), приведение типов — ответственность разработчика.

- **Путают `[...slug]` и `[[...slug]]`** — первый не матчит родительский путь без сегментов (`/docs` даст 404), второй матчит, и `slug` будет `undefined`.

- **"Route Groups влияют на URL"** — нет, `(marketing)`/`(app)` существуют только для организации файлов и разных layout'ов, в URL они не отображаются.

- **"layout.tsx и template.tsx — это одно и то же, просто синонимы"** — `layout` сохраняет state и DOM между навигациями внутри сегмента, `template` пересоздаётся при каждой навигации. Разница критична для `useEffect`-based аналитики или анимаций входа/выхода.

- **"Middleware может делать всё, что Route Handler"** — нет, Edge Runtime не даёт доступа к Node API и большинству ORM. Незнание этого — частая причина "у меня в middleware падает Prisma".

- **Забывают про `matcher`** — без него middleware гоняется на каждый запрос, включая `/_next/static/*`, `/favicon.ico` и т.д., что измеримо увеличивает латентность.

- **"Redirect и Rewrite — это синонимы для 'перенаправить пользователя'"** — Redirect меняет URL в браузере (видимо пользователю и поисковикам), Rewrite — нет. Для SEO это принципиально разные инструменты (redirect передаёт сигнал "контент переехал", rewrite — "это тот же ресурс, просто внутренняя реализация другая").
