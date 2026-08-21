<!-- verified: 2026-06-05, corrections: 0 -->
# App Router против Pages Router

## Коротко

В Next.js два роутера, и на практике нужны оба. **App Router** — то, на чём пишут новый код. **Pages Router** — то, на чём написано большинство существующих проектов.

Ключевое различие — модель компонентов по умолчанию. В App Router страница это Server Component, в Pages Router — Client Component.

До Next.js 13 существовал только **Pages Router**. Его правило простое: в структуре `pages/` каждый файл — страница, а страница — React-компонент. Этот компонент рендерится на сервере при первом запросе, а дальше гидратируется как обычный Client Component.

Next.js 13 представил **App Router** (директория `app/`), построенный вокруг React Server Components (RSC), вложенных layout'ов и streaming. С Next.js 13.4 он считается стабильным и рекомендуемым для новых проектов. Pages Router по-прежнему официально поддерживается и живёт в огромном количестве кодовых баз, так что знание обоих — практический навык, а не история.

## Почему появился App Router

Pages Router хорошо решал задачи серверного рендеринга (SSR), статической генерации (SSG) и инкрементальной регенерации (ISR), но структурные ограничения у него были:

- **Нет вложенных layout'ов без лишних ре-рендеров**: единственный layout-механизм — `_app.tsx`, общий для всего приложения. Чтобы дать разным секциям сайта разные layout'ы, страницы приходилось вручную оборачивать в компоненты-обёртки. А при навигации между страницами layout пересоздавался полностью — со сбросом состояния, например скролла или открытых модалок.
- **Нет встроенного Streaming**: вся страница рендерилась целиком на сервере и отправлялась одним блоком — медленный запрос к одной части страницы (например, к "Recommendations" блоку) блокировал отправку всего HTML.
- **Нет Server Components**: каждая страница, даже статическая по сути, гидратировалась как Client Component — весь JS, нужный для рендера, попадал в бандл клиента.
- **Data fetching через специальные функции** (`getServerSideProps`, `getStaticProps`) — эти функции жили *рядом* с компонентом, но не *внутри* него. Co-location данных на уровне вложенных компонентов не поддерживалась: вся страница получала props одним большим объектом.

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

Маршрутом становится не любой файл, а файл с зарезервированным именем: `page.tsx`, `route.ts`, `layout.tsx` и ещё несколько. Поэтому рядом с `page.tsx` можно свободно класть `components/`, `utils.ts`, `hooks.ts` — они не превратятся в случайные роуты. Это называют **colocation**.

## Главное отличие: модель компонентов по умолчанию

```txt
Pages Router:  Страница = Client Component
                (гидратируется целиком; getServerSideProps —
                 отдельный server-only слой)

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

В Pages Router общий UI (хедер, сайдбар) обычно жил в `_app.tsx` — единственном "layout" на всё приложение. Раздельные layout'ы для разных секций требовали компонентов-обёрток, написанных руками, — часто это был компонент высшего порядка (HOC). А при переходе между страницами ре-рендерился **весь** layout, включая `_app`.

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
DashboardLayout  — НЕ ре-рендерится
                   (Sidebar не теряет состояние, скролл не сброшен)
page.tsx         — ре-рендерится
```

Это прямое следствие модели Server Components + React reconciliation на уровне дерева: при навигации Next запрашивает только изменившийся сегмент, а общие layout'ы остаются смонтированными.

## Loading UI и Error Handling — встроенные конвенции

В Pages Router состояния загрузки и ошибок реализовывались вручную (свой `if (loading) return <Spinner />`, свои error boundaries). App Router вводит файловые конвенции, которые Next автоматически оборачивает в `<Suspense>` и Error Boundary:

```txt
app/users/
 ├─ page.tsx     → основной контент
 ├─ loading.tsx  → оборачивает page.tsx в
 │                 <Suspense fallback={<Loading />}>
 └─ error.tsx    → оборачивает page.tsx в Error Boundary
```

```tsx
// app/users/loading.tsx
export default function Loading() {
  return <Skeleton rows={5} />;
}

// app/users/error.tsx — обязательно Client Component
'use client';

export default function Error({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <div>
      <p>Что-то пошло не так: {error.message}</p>
      <button onClick={() => retry()}>Повторить</button>
    </div>
  );
}
```

Проп `retry` стал стабильным в Next.js 16.3: он заново запрашивает данные и перерендеривает сегмент. В старом коде и в проектах на Next.js 15 вместо него `reset`. Тот только сбрасывает состояние ошибки и перерендеривает детей, без повторного запроса.

Важный нюанс: `error.tsx` ловит ошибки только в *своём сегменте и ниже*. Ошибку в `layout.tsx` того же уровня поймает `error.tsx` родительского сегмента, а не текущего. Причина: layout рендерится "снаружи" своего error boundary.

## Streaming

Pages Router рендерит страницу целиком и отправляет один HTML-документ. Медленный data fetch для любой части страницы задерживает TTFB (time to first byte) всей страницы.

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

## Метаданные и поисковая оптимизация (SEO)

Pages Router: `_document.tsx` + ручная вставка `<Head>` через `next/head` на каждой странице.

App Router: декларативный Metadata API, статический или динамический:

```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from 'next';

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params; // Next.js 15: params стал async
  const post = await getPost(slug);
  return {
    title: post.title,
    description: post.excerpt,
    openGraph: { images: [post.coverImage] },
  };
}
```

## Что осталось от Pages Router

Pages Router официально поддерживается, и оба router'а могут **сосуществовать в одном проекте** (при конфликте маршрутов Next приоритизирует `app/`) — это используется для постепенной миграции legacy-проектов.

Большинство существующих кодовых баз на Next 12-14 до сих пор написаны на `pages/`. На практике вы скорее встретите Pages Router в реальном проекте, чем будете начинать с нуля на App Router.

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

- **Не могут объяснить, почему в Pages Router смена layout'а на каждой странице "дороже"** — `_app.tsx` там единственный layout-уровень. Без вложенных layout'ов общий UI либо ре-рендерится, либо требует кастомного обходного пути. Обычно это per-page layouts через `getLayout` — паттерн, который сообщество придумало само, а не часть фреймворка.

- **Считают, что `error.tsx` ловит вообще все ошибки приложения** — он не перехватывает ошибки в `layout.tsx` своего же уровня и не заменяет глобальный `global-error.tsx` в корне `app/`.

- **"Server Components — это то же самое, что SSR в Pages Router"** — SSR в Pages Router всё равно гидратирует компонент на клиенте целиком. Это Client Component, просто с серверным первым рендером. Server Component в App Router **вообще не попадает в клиентский JS-бандл**. Это принципиально другая модель, а не "тот же SSR с новым названием".

- **Не знают, что оба router'а могут работать одновременно** — это ключевой факт для разговора про миграцию. Переход с Pages на App Router делается инкрементально, маршрут за маршрутом, а не "большим бангом".
