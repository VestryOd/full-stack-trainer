<!-- verified: 2026-06-05, corrections: 1 -->
# Маршрутизация, файловые конвенции и middleware

## Файловая маршрутизация: основы и нюансы типизации

В App Router маршрут определяется *папкой*, а не файлом. Папка становится доступной как маршрут, когда внутри появляется файл `page.tsx`. Это отличие важно: можно создать папку `app/blog/components/` с обычными компонентами, и она **не** станет маршрутом, потому что в ней нет `page.tsx`.

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

`id` (из `await params`) всегда `string`, а для catch-all — `string[]`. Даже если по смыслу это число, Next не делает автоматического приведения типов. Частая ошибка — забыть `Number(params.id)` или `parseInt` перед использованием в запросе к БД (базе данных), где ожидается числовой ID.

### Catch-all и Optional Catch-all

```txt
app/docs/[...slug]/page.tsx
  → /docs/a, /docs/a/b, /docs/a/b/c
  → /docs НЕ матчится (нужен хотя бы 1 сегмент)

app/docs/[[...slug]]/page.tsx
  → /docs, /docs/a, /docs/a/b
  → /docs тоже матчится, slug будет undefined
```

```tsx
// app/docs/[...slug]/page.tsx
export default async function DocsPage({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const { slug } = await params; // Next.js 15: params стал async
  // /docs/react/hooks/useEffect → slug = ['react', 'hooks', 'useEffect']
  const path = slug.join('/');
  return <DocContent path={path} />;
}
```

Типичное применение — сайт документации на CMS (content management system, система управления контентом). Дерево страниц там может быть произвольной глубины, и его форму задаёт внешний источник данных, а не файловая структура.

### Route Groups — организация без влияния на URL

```txt
app/
 ├─ (marketing)/
 │   ├─ layout.tsx        → layout для маркетинга
 │   ├─ page.tsx          → /
 │   └─ about/page.tsx    → /about
 ├─ (app)/
 │   ├─ layout.tsx        → layout для закрытой части
 │   └─ dashboard/page.tsx → /dashboard
```

Папки в круглых скобках `(marketing)`, `(app)` — **не попадают в URL**. Это позволяет держать рядом несколько независимых Root-подобных layout'ов: один с публичным хедером, другой — с сайдбаром для авторизованных. Вкладывать их друг в друга не нужно.

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

`(.)photo` — это *intercepting route*. Клик по превью в ленте — клиентская навигация на `/photo/123`, и открывается модалка с фото *поверх* текущей страницы. А если зайти по тому же адресу напрямую (refresh, ссылка из мессенджера) или прийти серверным переходом, отрендерится полноценная страница `/photo/[id]`.

Это классический паттерн "Instagram-style" модалок для фотографий. На интервью senior-уровня его иногда спрашивают именно такой формулировкой. Как сделать, чтобы клик по фото открывал модалку, а прямая ссылка на то же фото — отдельную страницу?

## Layout, Template, Loading, Error, Not Found — файловые конвенции

```txt
app/dashboard/
 ├─ layout.tsx     → каркас; НЕ перемонтируется внутри сегмента
 ├─ template.tsx   → как layout, но ПЕРЕМОНТИРУЕТСЯ каждый раз
 ├─ loading.tsx    → автоматический <Suspense fallback>
 ├─ error.tsx      → Error Boundary (Client Component)
 ├─ not-found.tsx  → показывается на notFound() и промахе catch-all
 └─ page.tsx       → контент маршрута
```

### Layout vs Template — когда нужен именно Template

`layout.tsx` сохраняет состояние и DOM (Document Object Model — живое дерево узлов страницы в браузере) при навигации между дочерними маршрутами. Это и есть основное преимущество App Router: сайдбар не "мигает", скролл не сбрасывается. Но иногда такое поведение **нежелательно**:

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

Положите тот же код в `layout.tsx` — и `useEffect` сработает один раз, при первом монтировании сегмента. При переходе с `/blog/post-1` на `/blog/post-2` он больше не сработает: layout не размонтируется. Файл `template.tsx` решает именно этот класс задач. Три примера: эффекты на каждую навигацию, CSS-анимации входа и выхода, сброс локального состояния формы между шагами визарда.

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

Next запрашивает с сервера только одно: RSC payload (React Server Components payload — сериализованное описание изменившегося сегмента). Общие layout'ы остаются смонтированными в React-дереве, поэтому их состояние живёт дальше: открытое меню, позиция скролла внутри сайдбара.

## Middleware

### Где выполняется и зачем это важно

Middleware — это код, выполняющийся **до** того, как запрос достигнет роутинга Next.js, на **Edge Runtime** (V8 isolates, а не полноценный Node.js). Это даёт низкую латентность (middleware может выполняться географически близко к пользователю), но накладывает ограничения:

```txt
Недоступно в middleware:
  fs, net, child_process, любые Node-специфичные нативные модули
  Полноценные ORM (стандартный Prisma Client не работает на Edge)

Доступно:
  Web-стандартные API: fetch, Request, Response, URL, Web Crypto
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

`matcher` — это не "оптимизация", это необходимость. Без него middleware выполняется **для каждого запроса**, включая статические ассеты вроде `/_next/static/...`. Латентность добавляется ко всему приложению без всякой пользы.

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
  const existing = request.cookies.get('ab-bucket')?.value;
  const bucket = existing ?? (Math.random() < 0.5 ? 'a' : 'b');

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
  // request.geo заполняется на Vercel; в self-hosted нужен свой источник
  const country = request.geo?.country ?? 'US';
  const locale = country === 'DE' ? 'de' : country === 'FR' ? 'fr' : 'en';

  if (!request.nextUrl.pathname.startsWith(`/${locale}`)) {
    const target = new URL(`/${locale}${request.nextUrl.pathname}`, request.url);
    return NextResponse.redirect(target);
  }
  return NextResponse.next();
}
```

### Когда middleware — не лучший выбор

```txt
Хорошо подходит:
  - проверка наличия токена на уровне роутинга
  - редиректы и rewrites
  - модификация заголовков/cookies для всех запросов
  - geo/locale-роутинг, раздача A/B-бакетов

Плохо подходит:
  - проверка токена с походом в БД на каждый запрос
    (Edge Runtime плюс латентность БД на КАЖДЫЙ запрос,
    включая статику, если matcher настроен широко)
  - сложная бизнес-логика — её место в Route Handlers
    и Server Actions, где есть полноценный Node.js runtime
```

Частый антипаттерн — валидация JWT (JSON Web Token) прямо в middleware с проверкой в БД, например "не отозван ли токен". Технически это возможно через `fetch` к внешнему сервису. Но так к *каждому* защищённому запросу добавляется сетевой round-trip.

Более тяжёлую авторизационную логику обычно переносят в сами Route Handlers и Server Actions. Middleware тогда ограничивается дешёвой проверкой — например, валидностью JWT-подписи без похода в БД.

## Типичные ошибки на интервью

- **"params.id — это число, если в URL цифры"** — нет. Значения `params` всегда строки, а для catch-all — массивы строк. Приведение типов — ответственность разработчика.

- **Путают `[...slug]` и `[[...slug]]`** — первому нужен хотя бы один сегмент, поэтому `/docs` даст 404. Второй матчит и `/docs`, только `slug` там будет `undefined`.

- **"Route Groups влияют на URL"** — нет, `(marketing)`/`(app)` существуют только для организации файлов и разных layout'ов, в URL они не отображаются.

- **"layout.tsx и template.tsx — это одно и то же, просто синонимы"** — `layout` сохраняет состояние и DOM между навигациями внутри сегмента, `template` пересоздаётся при каждой навигации. Разница критична для `useEffect`-based аналитики или анимаций входа/выхода.

- **"Middleware может делать всё, что Route Handler"** — нет. Edge Runtime не даёт доступа к Node API и к большинству ORM (object-relational mapper, библиотека доступа к базе). Незнание этого — частая причина "у меня в middleware падает Prisma".

- **Забывают про `matcher`** — без него middleware гоняется на каждый запрос, включая `/_next/static/*`, `/favicon.ico` и т.д., что измеримо увеличивает латентность.

- **"Redirect и Rewrite — это синонимы для 'перенаправить пользователя'"** — нет. Redirect меняет URL в браузере, и это видят и пользователь, и поисковик. Rewrite URL не меняет. Для SEO (search engine optimization, поисковая оптимизация) это принципиально разные инструменты: redirect говорит "контент переехал", rewrite — "тот же ресурс, другая внутренняя реализация".
