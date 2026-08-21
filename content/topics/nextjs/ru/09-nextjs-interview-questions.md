<!-- verified: 2026-06-05, corrections: 0 -->
# Next.js: вопросы для интервью (Middle → Senior)

Этот файл — быстрый Q&A-рекап. Подробные объяснения с кодом и нюансами — в предыдущих статьях этого раздела. Здесь акцент на точность формулировок и на senior-уточнения, которые часто проверяют как "добавочный вопрос" к базовому ответу.

---

## 1. Что такое Next.js?

Full-stack framework поверх React. Помимо UI (user interface, пользовательский интерфейс) он решает вопросы рендеринга, роутинга, data fetching и кеширования, а также даёт backend-слой: Route Handlers, Server Actions, Middleware. React — UI-библиотека, Next — фреймворк приложения, использующий React как движок рендеринга.

## 2. Какие проблемы React решает Next.js?

SEO (search engine optimization, поисковая оптимизация) и first paint страдают в чистом SPA (single-page application), потому что первый HTML пустой. Плюс нет единой модели data fetching, code splitting приходится делать руками, встроенного backend-слоя нет.

Senior-уточнение: современный React (Suspense, Server Components) сам по себе решает часть этих проблем. Но без фреймворка вокруг них — роутинг, сборка, деплой — эти примитивы малополезны.

## 3. Почему Next.js называют Fullstack Framework?

Потому что в одном проекте и одном деплое сочетаются UI-слой (Server и Client Components) и backend-слой (Route Handlers, Server Actions, Middleware). Для простых задач не нужно поднимать отдельный сервис на Express или Nest: BFF-агрегация (Backend For Frontend), формы, webhooks.

## 4. Чем React отличается от Next.js?

| | React | Next.js |
|---|---|---|
| Уровень | UI library | Application framework |
| Решает | Как описывать/обновлять UI | Где и когда исполняется код, роутинг, кеш |
| Backend | Нет | Route Handlers, Server Actions, Middleware |

## 5. Что такое Rendering?

Процесс превращения React-дерева в HTML. Модель задают два параметра. Первый — *где* это происходит: на сервере, на клиенте или при сборке, для раздачи через CDN (content delivery network, сеть доставки контента). Второй — *когда*: на каждый запрос, один раз при билде или периодически.

## 6. Что такое CSR?

Client Side Rendering — HTML создаётся в браузере после загрузки и выполнения JS. Плюс: дешёвый сервер, мгновенные переходы после загрузки. Минус: пустой первый HTML, request waterfalls в `useEffect`.

## 7. Что такое SSR?

Server Side Rendering — HTML создаётся на сервере на каждый запрос. В App Router это поведение по умолчанию для Server Component, который использует `cookies()`, `headers()` или `fetch` с `cache: 'no-store'`. Включить его явно можно через `export const dynamic = 'force-dynamic'`.

## 8. Что такое SSG?

Static Site Generation — HTML создаётся во время build, сервер на момент запроса не участвует в рендере вообще. В App Router — Server Component без динамических API, `fetch` с `cache: 'force-cache'` (поведение по умолчанию для fetch в Next.js ≤14).

## 9. Что такое ISR?

Incremental Static Regeneration — SSG, который "протухает" и пересобирается в фоне. Протухание задаётся либо по TTL (time to live, время жизни — параметр `revalidate`), либо по требованию, через `revalidateTag` или `revalidatePath`. Пользователь, чей запрос триггерит revalidation, получает **старую** версию (stale-while-revalidate), а не ждёт пересборки.

## 10-12. Когда использовать SSR / SSG / ISR?

```txt
SSR  → персонализированные данные, привязанные к сессии
        (личный кабинет, корзина с авторизацией)
SSG  → контент, который меняется редко
        (документация, лендинги, блог без частых правок)
ISR  → контент, который меняется, но не требует
        мгновенной свежести (каталоги, новости, CMS)
```

## 13. Что такое Hydration?

Процесс, при котором React сопоставляет уже существующий серверный HTML с виртуальным DOM (Document Object Model, дерево узлов страницы) и подключает обработчики событий, **без** пересоздания разметки с нуля. До hydration контент виден, но не интерактивен.

## 14-15. Hydration Mismatch и его причины

Возникает, когда HTML, отрендеренный на сервере, не совпадает с тем, что React рендерит на клиенте при первом проходе. Причины: `Date.now()` или `Math.random()` напрямую в JSX (разметочный синтаксис React), доступ к `window` или `localStorage` во время рендера, невалидная вложенность HTML-тегов.

Решение — отложить вычисление до `useEffect`, а на сервере и при первом клиентском рендере отдавать `null` или placeholder. В редких точечных случаях — `suppressHydrationWarning`.

## 16-18. App Router, Pages Router и их главное отличие

App Router (`app/`) построен вокруг React Server Components, вложенных layout'ов с сохранением состояния при навигации и встроенного streaming. В Pages Router (`pages/`) каждый файл — это маршрут и Client Component, а данные приходят через `getServerSideProps` или `getStaticProps`.

**Главное отличие — не структура папок, а модель компонентов по умолчанию.** В App Router страница — это Server Component. В Pages Router — Client Component с серверным первым рендером.

## 19-21. Server Component, Client Component, как помечать

Server Component выполняется только на сервере, его код никогда не попадает в клиентский JS-бандл. Это поведение по умолчанию для всего в `app/`.

Client Component помечается директивой `'use client'`. Директива определяет границу *модуля*: всё, что импортируется из этого файла, и всё, что он сам импортирует, попадает в клиентский граф зависимостей.

## 22-23. Что можно/нельзя в Server Component

Нельзя: `useState`, `useEffect`, `useRef`, `window`/`document`, обработчики событий — у Server Component нет жизненного цикла в браузере. Можно: `fetch`, прямые запросы к БД (базе данных), `cookies()` и `headers()`, файловая система, env-переменные, "тяжёлые" серверные зависимости вроде markdown-парсеров.

## 24. Почему Server Components быстрее?

Четыре конкретных механизма. Первый: их код не попадает в клиентский бандл — 0 байт JS. Второй: нет hydration, а значит клиент не тратит CPU (процессорное время) на сопоставление DOM. Третий: прямой доступ к данным без лишнего round-trip "браузер → API". Четвёртый: тяжёлые зависимости вроде парсеров и форматтеров не "весят" на клиенте.

## 25. Чем SSR отличается от Server Components?

SSR — это *когда/где генерируется HTML* (может относиться и к Client Component с серверным первым рендером + последующей гидратацией). Server Components — это *исполняется ли код компонента в браузере вообще*. SSR-компонент в Pages Router всё равно гидратируется и отправляет JS клиенту; Server Component — никогда.

## 26-27. Data Fetching в App Router и отличие от browser fetch

`async/await` прямо в Server Component, рядом с разметкой. App Router `fetch` отличается от браузерного: он интегрирован с системой кеширования Next.js. Он поддерживает `cache`, `next.revalidate` и `next.tags`, а также участвует в Request Memoization — дедупликации одинаковых запросов в рамках одного рендера.

## 28-30. cache: 'force-cache', 'no-store', revalidate

С `force-cache` результат кешируется бессрочно, до явной инвалидации — поведение как у SSG. С `no-store` каждый рендер делает новый запрос — поведение как у SSR.

**Senior-нюанс**: в Next.js 13/14 по умолчанию стоит `force-cache`. В Next.js 15 умолчание сменили на `no-store` — одно из самых обсуждаемых breaking changes. А `revalidate: N` задаёт TTL в секундах и даёт ISR-подобное поведение. Записать можно как `next: { revalidate: 60 }` или `export const revalidate = 60`.

## 31-32. revalidatePath vs revalidateTag

`revalidatePath('/blog')` точечно сбрасывает кеш рендера конкретного маршрута (Full Route Cache). А `revalidateTag('posts')` сбрасывает Data Cache для *всех* `fetch` с этим тегом, независимо от маршрута. Это удобно, когда один ресурс используется на нескольких страницах.

## 33. generateStaticParams

Аналог `getStaticPaths` из Pages Router — возвращает массив параметров для статической генерации динамических маршрутов во время build. Для путей, не возвращённых отсюда, поведение контролируется `export const dynamicParams` (по умолчанию `true` → генерация по требованию при первом запросе, аналог `fallback: 'blocking'`).

## 34-36. cookies(), headers(), Dynamic Rendering

`cookies()` и `headers()` дают доступ к данным конкретного запроса на сервере и **помечают маршрут как dynamic**. Маршрут выпадает из Full Route Cache и рендерится на каждый запрос.

Dynamic Rendering — общий термин для этого поведения. Другие триггеры: `searchParams` в Server Component, `fetch` с `cache: 'no-store'` или `revalidate: 0`, а также `export const dynamic = 'force-dynamic'`.

## 37. Request Memoization

Если несколько компонентов в рамках *одного* рендера вызывают `fetch` с одинаковыми URL и опциями, выполняется один реальный HTTP-запрос. Остальные берут результат из памяти. Работает это только в пределах одного серверного рендера — persistent-кешем между запросами разных пользователей занимается Data Cache.

## 38-40. Layout, Nested Layout, почему Layout лучше обычной обёртки

`layout.tsx` — персистентный UI-каркас для сегмента маршрута и его потомков. Он **не размонтируется** при навигации между дочерними маршрутами, поэтому состояние живёт: открытое меню, скролл сайдбара. Layout'ы вкладываются: `Root Layout → Dashboard Layout → Page`.

Ручной компонент-обёртка в Pages Router так не умеет. Next запрашивает с сервера только RSC payload (React Server Components payload) изменившегося сегмента, а общие layout'ы остаются смонтированными.

## 41-43. loading.tsx, error.tsx, not-found.tsx

`loading.tsx` автоматически оборачивает `page.tsx` в `<Suspense fallback={...}>`. Файл `error.tsx` обязательно должен быть Client Component; это Error Boundary для сегмента и **его потомков**. Он не покрывает `layout.tsx` своего же уровня — тот ловит `error.tsx` родителя. А `not-found.tsx` рендерится при вызове `notFound()` или промахе catch-all маршрута.

## 44-46. Middleware: что, где, для чего

Код, выполняющийся **до** маршрутизации, на Edge Runtime (V8 isolates, без Node API). Файл `middleware.ts` в корне проекта. Применения: auth-редиректы, rewrites, geo/locale routing, A/B bucket assignment, модификация заголовков/cookies. Не подходит для тяжёлой бизнес-логики и операций с БД на каждый запрос — это задача Route Handlers/Server Actions с Node runtime.

## 47. Redirect vs Rewrite

Redirect (`NextResponse.redirect`) — браузер получает 307/308, URL в адресной строке **меняется**, видимо пользователю и поисковикам. Rewrite (`NextResponse.rewrite`) — запрос обслуживается другим путём "под капотом", URL **не меняется**. Для SEO это разные сигналы: redirect = "контент переехал", rewrite = "тот же ресурс, другая реализация".

## 48-53. Metadata API, OpenGraph, robots.txt, sitemap.xml

Metadata API — декларативный экспорт `metadata` или `generateMetadata` из `layout.tsx` и `page.tsx`. Метаданные **наследуются и сливаются** по дереву layout'ов, а `title.template` задаёт форму дочерних title.

OpenGraph отвечает за превью ссылок в соцсетях и мессенджерах. Файлы `app/robots.ts` и `app/sitemap.ts` — типизированные файловые конвенции (`MetadataRoute.Robots`, `MetadataRoute.Sitemap`). Для очень больших каталогов `generateSitemaps` отдаёт несколько файлов.

## 54-55. next/image, next/font

`next/image` генерирует `srcset` и конвертирует картинки в современные форматы: WebP (формат Google, файлы заметно меньше) и AVIF (новее, ещё меньше). Всё, что вне первого экрана, грузится лениво. Явные `width` и `height` — или `fill` с позиционированным родителем — резервируют место и снижают CLS (Cumulative Layout Shift). Проп `priority` повышает приоритет загрузки для LCP-элемента (Largest Contentful Paint).

`next/font` скачивает шрифт **на этапе сборки**, отдаёт его сам как статический ассет и подгоняет fallback-метрики. Это убирает запрос к Google Fonts в рантайме и снижает CLS при подмене шрифта.

## 56. Core Web Vitals

LCP (Largest Contentful Paint) улучшают SSR/SSG, `next/image priority` и `next/font`. CLS (Cumulative Layout Shift) улучшают явные размеры изображений и шрифтов. INP (Interaction to Next Paint) улучшает меньший объём клиентского JS за счёт Server Components.

## 57-58. Streaming и Suspense

Streaming — отправка HTML частями (chunked transfer encoding) по мере готовности данных, вместо рендера всей страницы целиком перед отправкой. `<Suspense fallback={...}>` оборачивает медленную часть дерева. Пользователь видит shell и fallback немедленно, а контент "дорисовывается" по готовности. Для SEO стриминг прозрачен: поисковый робот получает финальный HTML после завершения стрима.

## 59-60. Server Actions: что и когда

Функции с директивой `'use server'`, вызываемые из форм/UI-кода как мутации (`<form action={myAction}>`), без отдельного API-эндпоинта. Подходят для CRUD-мутаций (create, read, update, delete), форм, optimistic UI (`useOptimistic`). **Не** подходят для публичного API — у них нет стабильного версионируемого контракта и они не предназначены для внешних потребителей.

## 61. Когда лучше Route Handlers (API Routes)?

Когда для внешних потребителей нужен явный контракт REST (representational state transfer). Типичные вызывающие: webhooks от платёжных систем или CMS (content management system, система управления контентом), мобильное приложение, сторонние интеграции, OAuth callbacks.

## 62-63. Edge Runtime и его ограничения

Выполнение на V8 isolates близко к пользователю — низкая латентность, минимальный/нулевой cold start. Ограничения: нет `fs`/`net`/`child_process`/нативных модулей, доступны только Web-стандартные API (`fetch`, `crypto`, Streams). Стандартный Prisma + `pg`-драйвер не работает на Edge без адаптера — частая причина "работает локально, падает в проде на Edge".

## 64. Что такое BFF?

Backend For Frontend — Next агрегирует и трансформирует данные из нескольких микросервисов в единый, заточенный под конкретный экран API. Frontend не знает про внутреннюю топологию сервисов. Граница: BFF — для агрегации/трансформации под UI, а не для бизнес-логики с побочными эффектами на несколько доменов (это ответственность доменных сервисов).

## 65-66. Как бы вы построили e-commerce / CMS-проект?

E-commerce — это комбинация моделей, по одной на экран. Главная и категории → SSG/ISR. Страница товара → ISR плюс on-demand revalidation по webhook. Корзина → CSR. Checkout → Server Actions плюс Route Handler для платёжного webhook. Личный кабинет → SSR.

CMS-проект — Next плюс Strapi или Contentful, ISR с `revalidateTag`, инвалидация по webhook при публикации контента.

## 67. Как объяснить архитектуру современного Next.js?

Построен вокруг App Router и React Server Components: рендеринг, data fetching и кеширование выбираются гранулярно на уровне route segment, а не всего приложения. Большая часть логики выполняется на сервере по умолчанию, Client Components — осознанный opt-in только там, где нужна интерактивность (формы, обработчики событий, browser API).

## 68. Самый популярный senior-вопрос: какую модель рендеринга выбрать?

Единственно правильной модели нет. Продакшен-приложение комбинирует SSG, ISR, SSR, Server и Client Components *по экранам*, в зависимости от требований к SEO, производительности, свежести данных и стоимости вычислений. Сильный ответ — это таблица "тип страницы → стратегия", а не одно слово.

## Типичные ошибки на интервью

- **Путают SSR и Server Components** (см. вопрос 25) — самая частая ошибка во всём разделе.

- **Отвечают на "fetch кешируется по умолчанию" без указания версии Next** — в 13/14 да (`force-cache`), в 15 нет (`no-store`). Незнание этого breaking change — красный флаг для роли, требующей актуальных знаний.

- **Путают revalidatePath и revalidateTag** — первый целится в маршрут (Full Route Cache), второй — в данные по всему приложению (Data Cache), независимо от маршрута.

- **Считают, что middleware может всё то же, что Route Handler** — Edge Runtime не даёт Node API и большинства ORM (object-relational mapper, библиотека доступа к базе).

- **Дают однословный ответ на "как кешировать/строить приложение"** — сильный ответ показывает композицию решений, по одному на экран. Единая стратегия на всё приложение таким ответом не является.

- **Не знают, что ошибки Server Components не видны в браузере** — критично для разговора про наблюдаемость и сбор ошибок в продакшене.
