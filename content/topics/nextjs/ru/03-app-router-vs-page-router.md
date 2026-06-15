<!-- verified: 2026-06-05, corrections: 0 -->
# App Router vs Pages Router

## Контекст

До Next.js 13 существовал только **Pages Router** — файловая структура `pages/`, где каждый файл = страница, а страница = React-компонент, рендерящийся как Server-side при первом запросе и далее гидратируемый как обычный Client Component. Next.js 13 представил **App Router** (директория `app/`), построенный вокруг React Server Components (RSC), вложенных layout'ов и streaming. С Next.js 13.4 App Router считается стабильным и рекомендуемым для новых проектов, но Pages Router официально поддерживается и используется в огромном количестве существующих кодовых баз — поэтому знание обоих важно не как "история", а как практический навык работы с legacy.

## Почему появился App Router

Pages Router хорошо решал задачи SSR/SSG/ISR, но имел структурные ограничения:

- **Нет вложенных layout'ов без costly re-render**: единственный layout-механизм — `_app.tsx`, общий для всего приложения. Чтобы дать разным секциям сайта разные layout'ы, приходилось вручную оборачивать страницы в компоненты-обёртки, и при навигации между страницами layout пересоздавался полностью (со сбросом состояния, например скролла или открытых модалок).
- **Нет встроенного Streaming**: вся страница рендерилась целиком на сервере и отправлялась одним блоком — медленный запрос к одной части страницы (например, к "Recommendations" блоку) блокировал отправку всего HTML.
- **Нет Server Components**: каждая страница, даже статическая по сути, гидратировалась как Client Component — весь JS, нужный для рендера, попадал в бандл клиента.
- **Data fetching через специальные функции** (`getServerSideProps`, `getStaticProps`) — эти функции жили *рядом* с компонентом, но не *внутри* него, и не поддерживали co-location данных на уровне вложенных компонентов: вся страница получала props одним большим объектом.

## Структура и роутинг

**Pages Router**:

```txt
pages/
 ├─ index.tsx          → /
 ├─ about.tsx           → /about
 ├─ users/
 │   ├─ index.tsx       → /users
 │   └─ [id].tsx        → /users/:id
 ├─ _app.tsx            → общий wrapper для всех страниц
 └─ _document.tsx       → кастомизация <html>/<head>
```

Каждый файл в `pages/` *напрямую* становится маршрутом — нельзя положить туда вспомогательный компонент без последствий (он станет страницей).

**App Router**:

```txt
app/
 ├─ layout.tsx           → Root Layout (обязателен)
 ├─ page.tsx              → /
 ├─ about/
 │   └─ page.tsx          → /about
 ├─ users/
 │   ├─ layout.tsx        → layout для всех /users/*
 │   ├─ page.tsx          → /users
 │   ├─ loading.tsx       → loading UI для /users
 │   ├─ error.tsx         → error boundary для /users
 │   └─ [id]/
 │       └─ page.tsx      → /users/:id
 └─ api/
     └─ health/
         └─ route.ts      → /api/health (Route Handler)
```

Маршрутом становится не любой файл, а файл с зарезервированным именем (`page.tsx`, `route.ts`, `layout.tsx` и т.д.) — это значит, что рядом с `page.tsx` можно свободно класть `components/`, `utils.ts`, `hooks.ts` без риска превратить их в случайные роуты. Это называют **colocation**.

## Главное отличие: модель компонентов по умолчанию

```txt
Pages Router:  Страница = Client Component
                (гидратируется целиком, getServerSideProps — отдельный server-only слой)

App Router:    Страница = Server Component по умолчанию
                ('use client' — явный opt-in для интерактивности)
```

Это меняет архитектурное мышление: в App Router вопрос не "как получить данные для страницы", а "какие части дерева *должны* быть интерактивными, и как минимизировать их количество". Подробнее — в статье про Server vs Client Components.

## Data Fetching

**Pages Router** — специальные экспортируемые функции, исполняемые Next.js до рендера компонента:

```ts
// pages/users/index.tsx
export async function getServerSideProps() {
  const users = await db.user.findMany();
  return { props: { users } }; // должно быть JSON-сериализуемо
}

export default function UsersPage({ users }: { users: User[] }) {
  return <UserList users={users} />;
}
```

**App Router** — `async/await` прямо в компоненте, co-located с разметкой:

```tsx
// app/users/page.tsx
export default async function UsersPage() {
  const users = await db.user.findMany();
  return <UserList users={users} />;
}
```

Ключевое следствие: в App Router *вложенные* Server Components могут независимо фетчить свои данные — нет необходимости тащить всё через props с верхнего уровня страницы. Next автоматически дедуплицирует одинаковые `fetch`-запросы в рамках одного рендера (request memoization).

## Layouts и сохранение состояния при навигации

В Pages Router общий UI (хедер, сайдбар) обычно жил в `_app.tsx` — единственном "layout" на всё приложение. Раздельные layout'ы для разных секций требовали ручных HOC/wrapper-компонентов, и при переходе между страницами **весь** layout (включая `_app`) ре-рендерился.

В App Router каждый сегмент маршрута может иметь свой `layout.tsx`, и они **вкладываются**:

```tsx
// app/layout.tsx — Root Layout, обязателен, содержит <html> и <body>
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <Header />
        {children}
      </body>
    </html>
  );
}

// app/dashboard/layout.tsx — вложенный layout только для /dashboard/*
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="dashboard-shell">
      <Sidebar />
      <main>{children}</main>
    </div>
  );
}
```

```txt
Навигация /dashboard/settings → /dashboard/profile:

RootLayout       — НЕ ре-рендерится
DashboardLayout  — НЕ ре-рендерится (Sidebar не теряет состояние, скролл не сбрасывается)
page.tsx         — ре-рендерится
```

Это прямое следствие модели Server Components + React reconciliation на уровне дерева: при навигации Next запрашивает только изменившийся сегмент, а общие layout'ы остаются смонтированными.

## Loading UI и Error Handling — встроенные конвенции

В Pages Router состояния загрузки и ошибок реализовывались вручную (свой `if (loading) return <Spinner />`, свои error boundaries). App Router вводит файловые конвенции, которые Next автоматически оборачивает в `<Suspense>` и Error Boundary:

```txt
app/users/
 ├─ page.tsx     → основной контент
 ├─ loading.tsx  → автоматически оборачивает page.tsx в <Suspense fallback={<Loading />}>
 └─ error.tsx    → автоматически оборачивает page.tsx в Error Boundary
```

```tsx
// app/users/loading.tsx
export default function Loading() {
  return <Skeleton rows={5} />;
}

// app/users/error.tsx — обязательно Client Component
'use client';

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div>
      <p>Что-то пошло не так: {error.message}</p>
      <button onClick={() => reset()}>Повторить</button>
    </div>
  );
}
```

Важный нюанс: `error.tsx` ловит ошибки только в *своём сегменте и ниже* — ошибка в `layout.tsx` того же уровня будет поймана `error.tsx` родительского сегмента, а не текущего (layout рендерится "снаружи" своего error boundary).

## Streaming

Pages Router рендерит страницу целиком и отправляет один HTML-документ — медленный data fetch для любой части страницы задерживает TTFB всей страницы.

App Router поддерживает streaming "из коробки" через `<Suspense>`: сервер может отправить shell страницы немедленно, а медленные части — досылать отдельными чанками по мере готовности (используя HTTP chunked transfer encoding):

```tsx
// app/dashboard/page.tsx
import { Suspense } from 'react';

export default function DashboardPage() {
  return (
    <div>
      <Header /> {/* рендерится сразу */}
      <Suspense fallback={<RevenueSkeleton />}>
        <RevenueChart /> {/* медленный fetch — стримится отдельно */}
      </Suspense>
      <Suspense fallback={<OrdersSkeleton />}>
        <RecentOrders /> {/* свой независимый fetch */}
      </Suspense>
    </div>
  );
}
```

Пользователь видит `Header` и скелетоны мгновенно, а `RevenueChart`/`RecentOrders` "дорисовываются" по мере получения данных — без блокировки друг друга (параллельные, а не последовательные fetch).

## Метаданные и SEO

Pages Router: `_document.tsx` + ручная вставка `<Head>` через `next/head` на каждой странице.

App Router: декларативный Metadata API, статический или динамический:

```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from 'next';

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const post = await getPost(params.slug);
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: { images: [post.coverImage] },
  };
}
```

## Что осталось от Pages Router

Pages Router официально поддерживается, и оба router'а могут **сосуществовать в одном проекте** (Next будет приоритизировать `app/` при конфликте маршрутов) — это используется для постепенной миграции legacy-проектов. Большинство существующих кодовых баз на Next 12-14 до сих пор написаны на `pages/`, поэтому на практике вы скорее встретите Pages Router в реальном проекте, чем будете начинать с нуля на App Router.

## Сравнение

| | Pages Router | App Router |
|---|---|---|
| Директория | `pages/` | `app/` |
| Файл → роут | любой файл | только `page.tsx`/`route.ts` |
| Компонент по умолчанию | Client Component | Server Component |
| Data fetching | `getServerSideProps`/`getStaticProps` | `async/await` в компоненте |
| Layouts | `_app.tsx`, ручные wrapper'ы | вложенные `layout.tsx`, сохраняют состояние |
| Loading/Error | вручную | `loading.tsx`/`error.tsx` (конвенции) |
| Streaming | нет | да, через `<Suspense>` |
| Метаданные | `next/head` | Metadata API / `generateMetadata` |

## Типичные ошибки на интервью

- **"App Router — это просто новая папка вместо `pages/`"** — структура — лишь следствие, а не причина. Главное изменение — модель компонентов по умолчанию (Server Components) и встроенная поддержка streaming/nested layouts.

- **"getServerSideProps больше не существует в Next.js"** — существует, и прекрасно работает в Pages Router. Просто в App Router его заменяет `async`-компонент + `fetch`-опции.

- **Не могут объяснить, почему в Pages Router смена layout'а на каждой странице "дороже"** — потому что `_app.tsx` — единственный layout-уровень, и при отсутствии вложенных layout'ов общий UI либо ре-рендерится, либо требует кастомных решений (per-page layouts через `getLayout` — паттерн, который сообщество придумало само, не часть фреймворка).

- **Считают, что `error.tsx` ловит вообще все ошибки приложения** — он не перехватывает ошибки в `layout.tsx` своего же уровня и не заменяет глобальный `global-error.tsx` в корне `app/`.

- **"Server Components — это то же самое, что SSR в Pages Router"** — SSR в Pages Router всё равно гидратирует компонент на клиенте целиком (это Client Component, просто с серверным первым рендером). Server Component в App Router **вообще не попадает в клиентский JS-бандл** — это принципиально другая модель, а не просто "тот же SSR с новым названием".

- **Не знают, что оба router'а могут работать одновременно** — это ключевой факт для разговора про миграцию: переход с Pages на App Router делается incrementally, маршрут за маршрутом, а не "большим бангом".
