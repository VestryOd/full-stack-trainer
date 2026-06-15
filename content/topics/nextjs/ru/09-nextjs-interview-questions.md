<!-- verified: 2026-06-05, corrections: 0 -->
# Next.js Interview Questions (Middle → Senior)

Этот файл — быстрый Q&A-рекап. Подробные объяснения с кодом и нюансами — в предыдущих статьях этого раздела; здесь акцент на точность формулировок и senior-уточнения, которые часто проверяют именно как "добавочный вопрос" к базовому ответу.

---

## 1. Что такое Next.js?

Full-stack framework поверх React, который решает (помимо UI) вопросы рендеринга, роутинга, data fetching, кеширования и предоставляет backend-слой (Route Handlers, Server Actions, Middleware). React — UI library, Next — application framework, использующий React как rendering engine.

## 2. Какие проблемы React решает Next.js?

SEO и first paint (пустой HTML в SPA), отсутствие единой модели data fetching, ручной code splitting, отсутствие встроенного backend-слоя. Senior-уточнение: современный React (Suspense, Server Components) сам по себе решает часть этих проблем — но без framework вокруг них (роутинг, build pipeline, deployment) эти примитивы малополезны.

## 3. Почему Next.js называют Fullstack Framework?

Потому что в одном проекте и одном деплое сочетаются UI-слой (Server/Client Components) и backend-слой (Route Handlers, Server Actions, Middleware) — без необходимости поднимать отдельный Express/Nest сервис для простых задач (BFF-агрегация, формы, webhooks).

## 4. Чем React отличается от Next.js?

| | React | Next.js |
|---|---|---|
| Уровень | UI library | Application framework |
| Решает | Как описывать/обновлять UI | Где и когда исполняется код, роутинг, кеш |
| Backend | Нет | Route Handlers, Server Actions, Middleware |

## 5. Что такое Rendering?

Процесс превращения React-дерева в HTML. Ключевые параметры модели: *где* (сервер/клиент/build-time CDN) и *когда* (на каждый запрос/один раз при билде/периодически).

## 6. Что такое CSR?

Client Side Rendering — HTML создаётся в браузере после загрузки и выполнения JS. Плюс: дешёвый сервер, мгновенные переходы после загрузки. Минус: пустой первый HTML, request waterfalls в `useEffect`.

## 7. Что такое SSR?

Server Side Rendering — HTML создаётся на сервере на каждый запрос. В App Router — поведение по умолчанию для Server Component, использующего `cookies()`/`headers()`/`fetch` с `cache: 'no-store'`, либо явно через `export const dynamic = 'force-dynamic'`.

## 8. Что такое SSG?

Static Site Generation — HTML создаётся во время build, сервер на момент запроса не участвует в рендере вообще. В App Router — Server Component без динамических API, `fetch` с `cache: 'force-cache'` (поведение по умолчанию для fetch в Next.js ≤14).

## 9. Что такое ISR?

Incremental Static Regeneration — SSG, который "протухает" по TTL (`revalidate`) или по требованию (`revalidateTag`/`revalidatePath`) и пересобирается в фоне. Пользователь, чей запрос триггерит revalidation, получает **старую** версию (stale-while-revalidate), а не ждёт пересборки.

## 10-12. Когда использовать SSR / SSG / ISR?

```txt
SSR  → персонализированные/привязанные к сессии данные (личный кабинет, корзина с auth)
SSG  → контент, который меняется редко (документация, лендинги, блог без частых правок)
ISR  → контент, который меняется, но не требует мгновенной свежести
        (каталоги, новости, CMS-страницы)
```

## 13. Что такое Hydration?

Процесс, при котором React сопоставляет уже существующий серверный HTML с виртуальным DOM и подключает обработчики событий, **без** пересоздания разметки с нуля. До hydration контент виден, но не интерактивен.

## 14-15. Hydration Mismatch и его причины

Возникает, когда HTML, отрендеренный на сервере, не совпадает с тем, что React рендерит на клиенте при первом проходе. Причины: `Date.now()`/`Math.random()` напрямую в JSX, доступ к `window`/`localStorage` во время рендера, невалидная вложенность HTML-тегов. Решение — отложить вычисление до `useEffect` (рендерить `null`/placeholder на сервере и при первом клиентском рендере) или, в редких точечных случаях, `suppressHydrationWarning`.

## 16-18. App Router, Pages Router и их главное отличие

App Router (`app/`) построен вокруг React Server Components, вложенных layout'ов с сохранением состояния при навигации и встроенного streaming. Pages Router (`pages/`) — каждый файл = маршрут = Client Component, данные через `getServerSideProps`/`getStaticProps`. **Главное отличие — не структура папок, а модель компонентов по умолчанию**: в App Router страница — Server Component, в Pages Router — Client Component с серверным первым рендером.

## 19-21. Server Component, Client Component, как помечать

Server Component — выполняется только на сервере, его код никогда не попадает в клиентский JS-бандл (по умолчанию для всего в `app/`). Client Component — помечается директивой `'use client'`, которая определяет границу *модуля*: всё, что импортируется из этого файла (и что он сам импортирует), попадает в клиентский граф зависимостей.

## 22-23. Что можно/нельзя в Server Component

Нельзя: `useState`, `useEffect`, `useRef`, `window`/`document`, обработчики событий — у Server Component нет жизненного цикла в браузере. Можно: `fetch`, прямые запросы к БД, `cookies()`/`headers()`, файловая система, env-переменные, "тяжёлые" серверные зависимости (markdown-парсеры и т.п.).

## 24. Почему Server Components быстрее?

Четыре конкретных механизма: (1) их код не попадает в клиентский бандл — 0 байт JS; (2) нет hydration — нет затрат CPU клиента на сопоставление DOM; (3) прямой доступ к данным без лишнего HTTP round-trip "браузер → API"; (4) тяжёлые зависимости (парсеры, форматтеры) не "весят" на клиенте.

## 25. Чем SSR отличается от Server Components?

SSR — это *когда/где генерируется HTML* (может относиться и к Client Component с серверным первым рендером + последующей гидратацией). Server Components — это *исполняется ли код компонента в браузере вообще*. SSR-компонент в Pages Router всё равно гидратируется и отправляет JS клиенту; Server Component — никогда.

## 26-27. Data Fetching в App Router и отличие от browser fetch

`async/await` прямо в Server Component, co-located с разметкой. В отличие от browser `fetch`, App Router fetch интегрирован с системой кеширования Next.js: поддерживает `cache`, `next.revalidate`, `next.tags`, и участвует в Request Memoization (дедупликация одинаковых запросов в рамках одного рендера).

## 28-30. cache: 'force-cache', 'no-store', revalidate

`force-cache` — кеширует результат бессрочно (до явной инвалидации), SSG-подобное поведение. `no-store` — новый запрос на каждый рендер, SSR-подобное поведение. **Senior-нюанс**: в Next.js 13/14 `force-cache` — поведение по умолчанию, в Next.js 15 default изменён на `no-store` — одно из самых обсуждаемых breaking changes. `revalidate: N` — TTL в секундах для ISR-подобного поведения (`next: { revalidate: 60 }` или `export const revalidate = 60`).

## 31-32. revalidatePath vs revalidateTag

`revalidatePath('/blog')` — точечно сбрасывает кеш рендера конкретного маршрута (Full Route Cache). `revalidateTag('posts')` — сбрасывает Data Cache для *всех* `fetch`, помеченных этим тегом, независимо от маршрута — удобно, когда один ресурс используется на нескольких страницах.

## 33. generateStaticParams

Аналог `getStaticPaths` из Pages Router — возвращает массив параметров для статической генерации динамических маршрутов во время build. Для путей, не возвращённых отсюда, поведение контролируется `export const dynamicParams` (по умолчанию `true` → генерация по требованию при первом запросе, аналог `fallback: 'blocking'`).

## 34-36. cookies(), headers(), Dynamic Rendering

`cookies()`/`headers()` дают доступ к request-специфичным данным на сервере и **помечают маршрут как dynamic** — он выпадает из Full Route Cache и рендерится на каждый запрос. Dynamic Rendering — общий термин для этого поведения; полный список триггеров включает также `searchParams` в Server Component, `fetch` с `cache: 'no-store'`/`revalidate: 0`, и `export const dynamic = 'force-dynamic'`.

## 37. Request Memoization

Если несколько компонентов в рамках *одного* рендера вызывают `fetch` с одинаковыми URL/опциями, выполняется один реальный HTTP-запрос, остальные берут результат из памяти. Работает только в пределах одного server-side рендера — не персистентный кеш между запросами разных пользователей (это задача Data Cache).

## 38-40. Layout, Nested Layout, почему Layout лучше обычной обёртки

`layout.tsx` — персистентный UI-каркас для сегмента маршрута и его потомков, **не размонтируется** при навигации между дочерними маршрутами — сохраняется состояние (открытое меню, скролл сайдбара). Layout'ы вкладываются: `Root Layout → Dashboard Layout → Page`. В отличие от ручного компонента-обёртки в Pages Router, Next запрашивает с сервера только RSC payload изменившегося сегмента, а общие layout'ы остаются смонтированными.

## 41-43. loading.tsx, error.tsx, not-found.tsx

`loading.tsx` автоматически оборачивает `page.tsx` в `<Suspense fallback={...}>`. `error.tsx` (обязательно Client Component) — Error Boundary для сегмента и **его потомков**, но не для `layout.tsx` своего же уровня (его ловит `error.tsx` родителя). `not-found.tsx` рендерится при вызове `notFound()` или несовпадении catch-all маршрута.

## 44-46. Middleware: что, где, для чего

Код, выполняющийся **до** маршрутизации, на Edge Runtime (V8 isolates, без Node API). Файл `middleware.ts` в корне проекта. Применения: auth-редиректы, rewrites, geo/locale routing, A/B bucket assignment, модификация заголовков/cookies. Не подходит для тяжёлой бизнес-логики и операций с БД на каждый запрос — это задача Route Handlers/Server Actions с Node runtime.

## 47. Redirect vs Rewrite

Redirect (`NextResponse.redirect`) — браузер получает 307/308, URL в адресной строке **меняется**, видимо пользователю и поисковикам. Rewrite (`NextResponse.rewrite`) — запрос обслуживается другим путём "под капотом", URL **не меняется**. Для SEO это разные сигналы: redirect = "контент переехал", rewrite = "тот же ресурс, другая реализация".

## 48-53. Metadata API, OpenGraph, robots.txt, sitemap.xml

Metadata API — декларативный экспорт `metadata`/`generateMetadata` из `layout.tsx`/`page.tsx`, метаданные **наследуются и сливаются** по дереву layout'ов (`title.template` для дочерних title). OpenGraph — превью ссылок в соцсетях/мессенджерах. `app/robots.ts`/`app/sitemap.ts` — типизированные файловые конвенции (`MetadataRoute.Robots`/`MetadataRoute.Sitemap`); для очень больших каталогов — `generateSitemaps` для нескольких файлов.

## 54-55. next/image, next/font

`next/image` генерирует `srcset`, конвертирует в WebP/AVIF, лениво грузит вне viewport; явные `width`/`height` (или `fill` с позиционированным родителем) резервируют место — снижают CLS; `priority` повышает fetch-приоритет для LCP-элементов. `next/font` скачивает шрифт **на этапе сборки**, self-host'ит как статический ассет, подгоняет fallback-метрики — устраняет runtime-запрос к Google Fonts и снижает CLS при свапе шрифта.

## 56. Core Web Vitals

LCP (Largest Contentful Paint, улучшается SSR/SSG + `next/image priority` + `next/font`), CLS (Cumulative Layout Shift, улучшается явными размерами изображений/шрифтов), INP (Interaction to Next Paint, улучшается меньшим объёмом клиентского JS за счёт Server Components).

## 57-58. Streaming и Suspense

Streaming — отправка HTML частями (chunked transfer encoding) по мере готовности данных, вместо рендера всей страницы целиком перед отправкой. `<Suspense fallback={...}>` оборачивает медленную часть дерева — пользователь видит shell и fallback немедленно, а контент "дорисовывается" по готовности. Для SEO прозрачно — крауlер получает финальный HTML после завершения стрима.

## 59-60. Server Actions: что и когда

Функции с директивой `'use server'`, вызываемые из форм/UI-кода как мутации (`<form action={myAction}>`), без отдельного API-эндпоинта. Подходят для CRUD-мутаций, форм, optimistic UI (`useOptimistic`). **Не** подходят для публичного API — у них нет стабильного версионируемого контракта и они не предназначены для внешних потребителей.

## 61. Когда лучше Route Handlers (API Routes)?

Когда нужен явный REST/JSON-контракт для внешних потребителей: webhooks (платёжные системы, CMS), мобильное приложение, сторонние интеграции, OAuth callbacks.

## 62-63. Edge Runtime и его ограничения

Выполнение на V8 isolates близко к пользователю — низкая латентность, минимальный/нулевой cold start. Ограничения: нет `fs`/`net`/`child_process`/нативных модулей, доступны только Web-стандартные API (`fetch`, `crypto`, Streams). Стандартный Prisma + `pg`-драйвер не работает на Edge без адаптера — частая причина "работает локально, падает в проде на Edge".

## 64. Что такое BFF?

Backend For Frontend — Next агрегирует и трансформирует данные из нескольких микросервисов в единый, заточенный под конкретный экран API. Frontend не знает про внутреннюю топологию сервисов. Граница: BFF — для агрегации/трансформации под UI, а не для бизнес-логики с побочными эффектами на несколько доменов (это ответственность доменных сервисов).

## 65-66. Как бы вы построили e-commerce / CMS-проект?

E-commerce — комбинация моделей по экранам: Homepage/категории → SSG/ISR, страница товара → ISR + on-demand revalidation по webhook, корзина → CSR, checkout → Server Actions + Route Handler для платёжного webhook, личный кабинет → SSR. CMS-проект — Next + Strapi/Contentful + ISR с `revalidateTag`, инвалидация по webhook при публикации контента.

## 67. Как объяснить архитектуру современного Next.js?

Построен вокруг App Router и React Server Components: рендеринг, data fetching и кеширование выбираются гранулярно на уровне route segment, а не всего приложения. Большая часть логики выполняется на сервере по умолчанию, Client Components — осознанный opt-in только там, где нужна интерактивность (формы, обработчики событий, browser API).

## 68. Самый популярный senior-вопрос: какую модель рендеринга выбрать?

Нет единственно правильной модели — production-приложение комбинирует SSG, ISR, SSR, Server и Client Components *по экранам*, в зависимости от требований к SEO, производительности, свежести данных и стоимости вычислений. Сильный ответ — это таблица "тип страницы → стратегия", а не одно слово.

## Типичные ошибки на интервью

- **Путают SSR и Server Components** (см. вопрос 25) — самая частая ошибка во всём разделе.

- **Отвечают на "fetch кешируется по умолчанию" без указания версии Next** — в 13/14 да (`force-cache`), в 15 нет (`no-store`). Незнание этого breaking change — красный флаг для роли, требующей актуальных знаний.

- **Путают revalidatePath и revalidateTag** — первый целится в маршрут (Full Route Cache), второй — в данные по всему приложению (Data Cache), независимо от маршрута.

- **Считают, что middleware может всё то же, что Route Handler** — Edge Runtime не даёт Node API и большинства ORM.

- **Дают однословный ответ на "как кешировать/строить приложение"** — сильный ответ для senior всегда показывает композицию решений по экранам, а не единую стратегию.

- **Не знают, что ошибки Server Components не видны в браузере** — критично для обсуждения observability и error tracking в production.
