<!-- verified: 2026-06-05, corrections: 0 -->
# Основы Next.js

## Что такое Next.js

Next.js — это full-stack framework поверх React. Ключевое слово здесь именно *framework*, а не *library*. React даёт вам строительные блоки: компоненты, хуки, реконсиляцию виртуального DOM (Document Object Model — дерево узлов страницы в браузере). Но он принципиально не отвечает на главные вопросы. Где хранить роуты? Когда и где запрашивать данные? Рендерить страницу на сервере или в браузере?

Next берёт эти решения на себя и навязывает (в хорошем смысле) свою структуру проекта.

Важно понимать разницу:

```txt
React  → UI library: компоненты, хуки, state, virtual DOM
Next.js → Application framework: routing, rendering, data fetching,
          caching, bundling, optimizations, backend-слой
```

Next.js не заменяет React. Он использует React как rendering engine и достраивает вокруг него инфраструктуру. Без фреймворка её собирают руками: React Router, конфиг Webpack, свой сервер рендеринга, свой слой данных, свой кеш.

## Зачем понадобился Next.js: проблемы классического SPA

SPA (single-page application) — это приложение, где сервер отдаёт одну почти пустую HTML-страницу, а всё остальное дорисовывает JS в браузере.

### Проблема 1 — поисковая оптимизация (SEO) и first paint

Классический SPA на Create React App или Vite отдаёт браузеру почти пустой HTML:

```html
<!DOCTYPE html>
<html>
  <body>
    <div id="root"></div>
    <script src="/bundle.js"></script>
  </body>
</html>
```

До 2018-2019 годов поисковые роботы плохо исполняли JS, поэтому такая страница индексировалась как пустая. Сейчас Googlebot умеет рендерить JS (через headless Chromium), но:

- рендеринг происходит асинхронно и может занимать дни — это влияет на скорость индексации новых страниц;
- бюджет рендеринга (crawl budget) ограничен — большие SPA индексируются медленнее и не полностью;
- другие боты (соцсети для OpenGraph-превью, некоторые поисковики) до сих пор не выполняют JS вообще.

Это решают серверный рендеринг (SSR — server-side rendering, HTML собирается на сервере на каждый запрос) и статическая генерация (SSG — static site generation, HTML собирается один раз при сборке). И браузер, и поисковый робот сразу получают готовый HTML с контентом.

### Проблема 2 — стоимость первой загрузки

Путь до интерактивной страницы принято мерить тремя метриками:

- **TTFB** (time to first byte) — когда пришёл первый байт ответа;
- **FCP** (first contentful paint) — когда пользователь увидел на экране хоть что-то;
- **TTI** (time to interactive) — когда страница начала реагировать на клики.

В чистом SPA пользователь проходит длинную последовательность:

```txt
HTML (почти пустой)
  ↓
скачивание JS-бандла
  ↓
парсинг и выполнение бандла, React mount
  ↓
запросы к API (часто после mount, не до)
  ↓
ре-рендер с данными
```

Каждый шаг добавляет латентность, и они в основном *последовательные*. На медленных сетях (3G, мобильный интернет в регионах) это превращается в секунды белого экрана. Next.js за счёт SSR/SSG отдаёт HTML с данными сразу, а гидратация (hydration) "оживляет" уже отрисованную разметку — пользователь видит контент раньше, чем приложение становится интерактивным.

### Проблема 3 — где и когда фетчить данные

В классическом React — до Suspense и React Server Components (RSC) — фетчинг данных был набором соглашений, которые каждая команда придумывала сама. Типичные варианты: `useEffect` + `useState`, кастомные хуки, react-query и SWR (stale-while-revalidate), Redux-thunk-и.

Next.js даёт единую модель. Данные запрашиваются прямо в серверных компонентах через `async`/`await`. Не нужны ни клиентский `useEffect`, ни водопады запросов (request waterfalls), ни лишний JS на клиенте только ради логики фетчинга.

```tsx
// app/products/page.tsx — Server Component, выполняется на сервере
export default async function ProductsPage() {
  const products = await fetch('https://api.example.com/products', {
    cache: 'no-store', // или revalidate, см. статью про data fetching
  }).then((res) => res.json());

  return (
    <ul>
      {products.map((p: { id: string; name: string }) => (
        <li key={p.id}>{p.name}</li>
      ))}
    </ul>
  );
}
```

Здесь нет `useEffect`, нет состояния загрузки на клиенте, нет лишнего JS, который нужно было бы скачивать только для того, чтобы дёрнуть API.

## Next.js как "opinionated framework"

На собеседованиях часто спрашивают, что значит "opinionated". Это означает, что framework делает архитектурные решения за вас и ожидает, что вы будете следовать его соглашениям, а не изобретать свои:

- **Routing** — файловая структура `app/` *является* роутингом (file-system based routing). Нет отдельного конфига маршрутов.
- **Rendering model** — по умолчанию все компоненты в `app/` — Server Components; клиентский код — это осознанный opt-in через `'use client'`.
- **Data fetching** — `fetch` с расширенным API (`cache`, `next.revalidate`, `next.tags`) встроен в платформу, а не приходит из библиотеки.
- **Bundling/Code splitting** — автоматическая разбивка по маршрутам, без ручной настройки `React.lazy` на каждый роут.

Плюс такого подхода — меньше "бойлерплейта" и архитектурных дискуссий внутри команды. Минус — выход за рамки этих соглашений (например, нестандартный SSR-сервер или кастомный кеш-слой) даётся сложнее, чем в "неопиньонированном" стеке (Vite + React Router + ваш выбор всего остального).

## Next.js — fullstack framework

Next.js одновременно содержит:

```txt
Frontend:  React Server/Client Components, Layouts, Streaming UI
Backend:   Route Handlers (app/api/**/route.ts), Server Actions,
           Middleware
```

Это позволяет держать BFF-слой (Backend For Frontend) и UI (пользовательский интерфейс) в одном репозитории и одном деплое. Отдельный сервис на Express или Nest только для агрегации данных под конкретный экран не нужен. Пример Route Handler — полноценный backend-эндпоинт:

```ts
// app/api/users/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const userId = request.nextUrl.searchParams.get('id');
  const user = await db.user.findUnique({ where: { id: userId ?? '' } });

  if (!user) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }
  return NextResponse.json(user);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const created = await db.user.create({ data: body });
  return NextResponse.json(created, { status: 201 });
}
```

И Middleware — код, выполняемый *до* того, как запрос дойдёт до страницы или Route Handler, на Edge Runtime:

```ts
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('session')?.value;

  if (!token && request.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.redirect(new URL('/login', request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*'],
};
```

Типичные применения middleware: аутентификация/редиректы, geo-based routing, A/B-тестирование (выбор варианта до рендера), модификация заголовков/cookies. Важный нюанс: middleware исполняется на Edge Runtime, поэтому Node.js-специфичные API (`fs`, `net`, нативные модули) там недоступны. Плюс каждый вызов добавляет латентность ко *всем* подходящим под matcher запросам, так что middleware стоит держать максимально лёгким.

## Code splitting и оптимизации "из коробки"

В классическом SPA приложение часто отдаётся одним большим JS-бандлом (или требует ручной настройки `React.lazy`/`Suspense` для каждого маршрута). Next.js по умолчанию делает per-route code splitting: пользователь, открывший `/checkout`, не скачивает JS, нужный только для `/admin`.

Дополнительно framework предоставляет компоненты-обёртки над браузерными примитивами, которые сами решают проблемы производительности:

```tsx
import Image from 'next/image';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], display: 'swap' });

export default function Hero() {
  return (
    <div className={inter.className}>
      <Image
        src="/hero.jpg"
        alt="Hero banner"
        width={1200}
        height={600}
        priority // отключает lazy-loading для above-the-fold изображений
      />
    </div>
  );
}
```

`next/image` делает сразу несколько вещей. Он генерирует `srcset`, конвертирует картинку в современные форматы (`.webp`, `.avif`) и лениво загружает всё, что за пределами viewport. Ещё он резервирует место под картинку, а это убирает сдвиг вёрстки — метрику CLS (cumulative layout shift) из Core Web Vitals.

`next/font` скачивает шрифты на этапе сборки и отдаёт их как статические файлы проекта. Запрос к Google Fonts в рантайме исчезает, а вместе с ним — вспышка невидимого текста (FOIT) и вспышка нестилизованного текста (FOUT).

## React vs Next.js — как объяснить разницу на собеседовании

Частый вопрос, и плохой ответ — "Next — это React с роутингом". Более точная формулировка:

| | React | Next.js |
|---|---|---|
| Уровень | UI library | Application framework |
| Что решает | Как описывать и обновлять UI | Где и когда исполняется код, как маршрутизировать, кешировать, отдавать данные |
| Rendering | Только client-side (по умолчанию) | клиентский (CSR), серверный (SSR), статический (SSG), инкрементальный (ISR), streaming — гранулярно по сегментам |
| Backend | Отсутствует | Route Handlers, Server Actions, Middleware |

Next.js использует React *как* rendering engine — он не подменяет реконсиляцию, хуки или модель компонентов, а оборачивает их в инфраструктуру жизненного цикла запроса.

## Типичные ошибки на интервью

- **"Next.js — это библиотека для роутинга в React"** — упускает суть. Next — это application framework, который решает рендеринг, data fetching, кеширование, бэкенд-слой, а не только маршрутизацию.

- **"SSR решает проблему SEO раз и навсегда"** — современные поисковики и так умеют рендерить JS. Реальная ценность SSR/SSG — это производительность (TTFB/FCP) и предсказуемость индексации, а не только "видимость для робота".

- **Путают SSG и SSR** — говорят "страница рендерится на сервере" про обе модели, не различая *когда*: во время билда (SSG) или на каждый запрос (SSR). Это разные модели с разными trade-off'ами по стоимости и свежести данных — подробнее в статье про rendering models.

- **"Middleware — это просто способ редиректить"** — middleware исполняется на Edge Runtime для *каждого* подходящего запроса, без доступа к Node.js API. Незнание этого ограничения — частая причина "почему у меня в middleware не работает Prisma/fs".

- **Не могут объяснить, почему Next называют fullstack** — ответ не "потому что есть API Routes". Дело в том, что одно приложение и один деплой соединяют UI-слой (Server и Client Components) с backend-слоем (Route Handlers, Server Actions, Middleware). Именно это упрощает архитектуру BFF.

- **Считают `next/image` и `next/font` "просто синтаксическим сахаром"** — на самом деле это оптимизации на этапе сборки и в рантайме: генерация `srcset`, конвертация форматов, инлайнинг шрифтов. В vanilla React всё это настраивают вручную, сторонними инструментами.
