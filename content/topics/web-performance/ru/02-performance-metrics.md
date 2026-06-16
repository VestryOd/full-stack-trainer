<!-- verified: 2026-06-16, corrections: 0 -->
# Performance Metrics: TTFB, FCP, TTI, TBT

## Диагностические метрики vs. пользовательские метрики

Core Web Vitals (LCP, CLS, INP) отвечают на вопрос **"как ощущает страницу пользователь"**. TTFB, FCP, TTI и TBT — это **диагностические метрики**: они отвечают на вопрос **"почему"** LCP плохой, **"почему"** страница кажется медленной.

```txt
Типичный рабочий процесс оптимизации:

  Lighthouse → "LCP 5.2s — плохо"
                        ↓
  Смотрим диагностику:
    TTFB = 2.1s → сервер медленный
    FCP = 2.8s  → ждал TTFB + рендер-блокировка
    TBT = 850ms → тяжёлый JS после загрузки
    TTI = 6.3s  → страница не interactive из-за TBT
                        ↓
  Приоритет: сначала TTFB (самый дорогой),
  потом рендер-блокировка, потом JS-бандл

Без этих метрик вы знаете "что" плохо.
С ними — знаете "где копать".
```

## TTFB — Time to First Byte

### Что именно измеряется

TTFB — время от начала навигации (URL введён/клик по ссылке) до получения **первого байта тела HTTP-ответа** от сервера.

```txt
Что входит во время TTFB:

  [Redirect time]
  + [DNS lookup]
  + [TCP connection]
  + [TLS handshake]
  + [Request time]          ← время передачи запроса на сервер
  + [Server processing]     ← самая "управляемая" часть: рендер
  + [Response start]          страницы, запросы к БД, и т.д.
  ________________________
  = TTFB

  Разбивку можно посмотреть в:
  DevTools → Network → кликнуть на документ → вкладка Timing
```

```txt
✅ Хорошо:         < 800 мс
⚠️  Требует работы: 800 мс — 1800 мс
❌ Плохо:          > 1800 мс

Важный нюанс: Lighthouse измеряет TTFB для первого
HTML-документа. TTFB для API-запросов — отдельная история
(там нет redirect/DNS при keep-alive соединении).
```

### Главные причины плохого TTFB

```txt
1. Нет CDN → пользователь в Токио получает ответ от
   сервера в Вирджинии: ~150ms только на RTT (round-trip time)
   × 2-3 для TLS handshake = 300-450ms ещё до server processing

2. Server processing медленный:
   - ORM генерирует N+1 запросы к БД
   - Нет кэширования результатов (Redis/in-memory)
   - Cold start у serverless-функций (Lambda, Vercel Edge)

3. Редиректы: HTTP → HTTPS → www-версия → 3 дополнительных
   RTT до начала получения реального контента

4. Нет HTTP/2 → несколько параллельных ресурсов требуют
   отдельных TCP-соединений (head-of-line blocking)
```

### Оптимизация TTFB

```ts
// ❌ SSR без кэша — каждый запрос пересчитывает страницу
export async function getServerSideProps() {
  const posts = await db.post.findMany({ take: 10 });
  return { props: { posts } };
}

// ✅ stale-while-revalidate через заголовки —
// CDN отдаёт кэшированный ответ, фоном обновляет
export async function getServerSideProps({ res }) {
  res.setHeader(
    'Cache-Control',
    'public, s-maxage=60, stale-while-revalidate=600'
  );
  const posts = await db.post.findMany({ take: 10 });
  return { props: { posts } };
}
```

```ts
// ✅ Streaming SSR (React 18) — первый байт HTML приходит
// немедленно, контент стримится по мере готовности
// (Next.js App Router делает это автоматически)
import { Suspense } from 'react';

export default function Page() {
  return (
    <>
      <Header />           {/* отправляется немедленно */}
      <Suspense fallback={<Skeleton />}>
        <SlowComponent />  {/* стримится когда готов */}
      </Suspense>
    </>
  );
}
```

```ts
// ✅ Кэширование на уровне приложения (Redis)
import { Redis } from 'ioredis';

const redis = new Redis(process.env.REDIS_URL!);

async function getPageData(slug: string) {
  const cached = await redis.get(`page:${slug}`);
  if (cached) return JSON.parse(cached);

  const data = await db.page.findUnique({ where: { slug } });
  await redis.setex(`page:${slug}`, 300, JSON.stringify(data)); // 5 min TTL
  return data;
}
```

```txt
DevTools-диагностика TTFB:

  Network tab → кликнуть на главный HTML-документ → Timing:
    "Waiting for server response" = server processing time
    "Initial connection" + "SSL" = сетевые задержки

  Если "Waiting" > 500ms — проблема на сервере
  Если "Initial connection" > 200ms — нет CDN или keep-alive
```

## FCP — First Contentful Paint

### Что именно измеряется

FCP фиксирует момент, когда браузер отрисовывает **любой** контент из DOM: текст, изображение, SVG, canvas (не белый экран).

```txt
FCP ≠ LCP:
  FCP — "хоть что-то появилось на экране"
  LCP — "самый важный контент отрисован"

  Пример: лоадер-спиннер может быть FCP,
  а реальный контент появится позже — это и будет LCP

  FCP полезен для диагностики: если FCP быстрый,
  но LCP медленный — проблема в загрузке конкретного
  LCP-ресурса (картинки/шрифта), а не в общей скорости
  отдачи HTML
```

```txt
✅ Хорошо:         < 1.8 сек
⚠️  Требует работы: 1.8 — 3.0 сек
❌ Плохо:          > 3.0 сек
```

### Что блокирует FCP — рендер-блокирующие ресурсы

Браузер **не рисует ничего** пока не загружены все CSS и синхронные JS-скрипты в `<head>`.

```html
<!-- ❌ Внешний CSS в <head> — блокирует рендер полностью
     пока не скачается (даже если стили только для футера) -->
<head>
  <link rel="stylesheet" href="https://cdn.example.com/styles.css" />
  <script src="/analytics.js"></script>  <!-- тоже блокирует -->
</head>
```

```html
<!-- ✅ Critical CSS inline + defer для остального -->
<head>
  <style>
    /* Только стили первого экрана — inline */
    header { background: #fff; }
    .hero { min-height: 100vh; }
  </style>

  <!-- defer: JS выполнится после парсинга HTML, не блокирует FCP -->
  <script defer src="/main.js"></script>

  <!-- async: независимый скрипт, не блокирует HTML-парсинг -->
  <script async src="/analytics.js"></script>

  <!-- Некритичный CSS — загружается асинхронно -->
  <link
    rel="preload"
    as="style"
    href="/non-critical.css"
    onload="this.rel='stylesheet'"
  />
</head>
```

```ts
// Измерение FCP в поле (реальные пользователи)
import { onFCP } from 'web-vitals';

onFCP((metric) => {
  // metric.value — в миллисекундах
  sendToAnalytics({ name: 'FCP', value: metric.value });
});
```

```txt
Ключевая диагностика FCP в Lighthouse:
  → "Eliminate render-blocking resources" — главный аудит
  → показывает конкретные URL и сколько ms они стоят
  → "Minify CSS" / "Remove unused CSS" — тоже влияет
     (большой CSS медленнее скачивается и парсится)
```

### FCP и Server-Side Rendering

```txt
FCP при разных стратегиях рендера:

  CSR (Create React App):
    TTFB → FCP: получили пустой HTML + bundle.js
    FCP → LCP: JS выполнился, React отрендерил DOM
    ↳ FCP = пустой экран или минимальный skeleton
      ДОЛГИЙ период между FCP и LCP

  SSR (Next.js getServerSideProps):
    TTFB → FCP: получили готовый HTML
    ↳ FCP уже показывает реальный контент
    ↳ Но TTFB может быть выше (server rendering)

  SSG (Static Site Generation):
    TTFB → FCP: HTML готов заранее, CDN отдаёт мгновенно
    ↳ Оптимальный TTFB И FCP
    ↳ Недостаток: нет персонализации без hydration
```

## TTI — Time to Interactive

### Что означает "интерактивный" технически

TTI — момент, после которого страница **надёжно реагирует на взаимодействия в пределах 50ms**. Алгоритм Lighthouse:

```txt
Алгоритм TTI (упрощённо):

  1. Найти FCP (начало поиска)
  2. Искать "тихое окно" длиной 5 секунд:
     - нет Long Tasks (задач > 50ms) на main thread
     - не более 2 параллельных сетевых запросов
  3. TTI = начало этого тихого окна
       (т.е. конец последней Long Task перед 5s-окном)

  FCP ←——————— TTI
       этот период = страница ВИДНА, но НЕ РЕАГИРУЕТ
       (клики буферизуются или игнорируются)
```

```txt
✅ Хорошо:         < 3.8 сек
⚠️  Требует работы: 3.8 — 7.3 сек
❌ Плохо:          > 7.3 сек

Критическое отличие TTI от FCP:
  Пользователь ВИДИТ контент (FCP), тапает кнопку —
  ничего не происходит, потому что JS ещё выполняется
  (TTI ещё не достигнут). Это один из самых раздражающих
  паттернов в мобильном вебе.
```

### Что увеличивает разрыв FCP → TTI

```ts
// ❌ Монолитный bundle — весь код приложения в одном файле
// Даже неиспользуемые на текущей странице части
// парсятся и компилируются браузером
import { CheckoutModule } from './checkout';   // не нужен на главной
import { AdminPanel } from './admin';          // не нужен большинству
import { ReportGenerator } from './reports';   // тяжёлый, нужен редко

// ✅ Dynamic import — код загружается только когда нужен
const CheckoutModule = lazy(() => import('./checkout'));
const AdminPanel = lazy(() =>
  import('./admin').then(m => ({ default: m.AdminPanel }))
);

// При клике на кнопку — загружается только тогда
async function handleCheckoutClick() {
  const { startCheckout } = await import('./checkout');
  startCheckout();
}
```

```txt
Практическое правило для TTI:
  Суммарный JS, который парсится/выполняется до TTI,
  должен быть минимальным.

  На мобильных устройствах парсинг JS примерно в 3-4 раза
  медленнее, чем на desktop (слабее CPU):
  - 100 KB JS на MacBook Pro = ~50ms
  - 100 KB JS на средний Android = ~150-200ms
  → Это напрямую удлиняет Long Tasks и сдвигает TTI
```

## TBT — Total Blocking Time

### Формула и смысл

TBT — лабораторная метрика (измеряется в Lighthouse, не в реальном поле), которая суммирует **"избыточное" время** всех Long Tasks между FCP и TTI:

```txt
Long Task = любая задача на main thread > 50ms

TBT = сумма (длительность каждой Long Task - 50ms)
      для всех Long Tasks между FCP и TTI

Пример:
  Long Task 1: 250ms → вклад = 250 - 50 = 200ms
  Long Task 2: 90ms  → вклад = 90  - 50 = 40ms
  Long Task 3: 180ms → вклад = 180 - 50 = 130ms
  ————————————————————————————————————————
  TBT = 370ms

Почему именно 50ms? Это порог, при котором
взаимодействие ощущается немедленным (<100ms).
Первые 50ms Long Task "не считаются" — это нормально.
Всё что сверх — реальная блокировка.
```

```txt
✅ Хорошо:         < 200 мс
⚠️  Требует работы: 200 — 600 мс
❌ Плохо:          > 600 мс
```

### TBT как прокси для INP в лаборатории

```txt
Отношение TBT и INP:

  INP — FIELD метрика (реальные пользователи)
  TBT — LAB метрика (Lighthouse, воспроизводимо)

  Корреляция высокая, но не 1:1:
    TBT показывает ПОТЕНЦИАЛ для плохого INP
    (если много Long Tasks — взаимодействие, попавшее
    на такую задачу, получит плохой INP)

  Практически:
    TBT > 600ms → очень вероятен INP > 500ms
    TBT < 200ms → скорее всего INP < 200ms
    Но INP может быть плохим при хорошем TBT,
    если конкретный обработчик события тяжёлый
    (TBT это страница в целом, INP — конкретные клики)
```

### Диагностика TBT — где искать Long Tasks

```txt
Chrome DevTools → Performance → запись загрузки страницы:

  Главный тред (Main):
    Красные прямоугольники над задачами = Long Tasks
    Кликнуть → Bottom-up / Call Tree → увидеть что именно
    занимало время

  Типичные виновники:
    - Парсинг и компиляция JS (Script Evaluation)
    - Hydration React/Vue/Angular
    - Сторонние скрипты (чаты, аналитика, A/B-тесты)
    - Большие операции с DOM (рендер длинных списков)
```

```ts
// Программное обнаружение Long Tasks в браузере
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.duration > 50) {
      console.warn(`Long Task: ${entry.duration.toFixed(0)}ms`, entry);
      sendToAnalytics({
        name: 'long_task',
        duration: entry.duration,
        startTime: entry.startTime,
      });
    }
  }
});

observer.observe({ type: 'longtask', buffered: true });
```

```ts
// ✅ Разбивка тяжёлой инициализации на микрозадачи
// чтобы снизить TBT при загрузке

async function initApp() {
  await initRouter();
  await scheduler.yield(); // даём браузеру шанс обработать события

  await initStore();
  await scheduler.yield();

  await initThirdPartyAnalytics(); // самое тяжёлое — в конце
}
```

## Как метрики связаны между собой — цепочка причинности

```txt
Навигация начинается
        ↓
[TTFB] — сервер отвечает
        ↓ HTML получен
[FCP]  — браузер отрисовал первый контент
   ↑         ↑
   │         └─ блокируют: рендер-блокирующий CSS/JS
   └─────────── зависит от: TTFB + сетевые задержки
        ↓
[LCP]  — главный контент отрисован ← пользовательская CWV
   ↑
   └─── зависит от: FCP + загрузка LCP-ресурса
        ↓ JS-бандлы выполняются, страница hydrates
[TBT]  — сумма блокировок main thread (лаборатория)
        ↓
[TTI]  — страница полностью интерактивна
   ↑
   └─── зависит от: Long Tasks после FCP

[INP]  — отзывчивость конкретных взаимодействий ← CWV
   ↑
   └─── коррелирует с TBT, но измеряется в реальном поле
```

## DevTools-воркфлоу для диагностики

```txt
Шаг 1: Lighthouse audit (вкладка или CLI)
  → даёт все четыре метрики + CWV
  → указывает на конкретные проблемы (аудиты)
  → запускать в режиме инкогнито (без расширений!)

Шаг 2: Performance panel для TTFB и Long Tasks
  DevTools → Performance → ⏺ (с Ctrl+Shift+E для reload)
  → трек Timings: FCP, LCP, TBT-маркеры
  → трек Network: ранний блокировщик рендера?
  → трек Main: где Long Tasks?

Шаг 3: Network tab для TTFB
  Hover на waterfall-баре документа → Timing breakdown
  "Waiting for server response" = реальный server time
  Сравниваем с TTFB у CDN-ноды: если близко к пользователю
  и всё равно медленно → сервер, не сеть

Шаг 4: Coverage tab
  DevTools → ⋮ → More tools → Coverage → ⏺ → reload
  → показывает % неиспользуемого JS/CSS при загрузке
  → красные полосы = код, который грузится, но не нужен
```

## Связь с другими темами

```txt
[Core Web Vitals]         — LCP, CLS, INP — пользовательские
                            метрики, для диагностики которых
                            нужны TTFB/FCP/TBT/TTI
[Resource Loading]        — preload/prefetch и render-blocking
                            напрямую влияют на FCP
[JavaScript Performance]  — code splitting снижает TTI и TBT;
                            Long Tasks — основа TBT
[Caching Strategies]      — браузерный кэш и CDN
                            сокращают TTFB
```

## Типичные ошибки на интервью

- **"TTFB — это время загрузки страницы"** — нет. TTFB заканчивается на первом байте ответа. Загрузка всех ресурсов — это Load Event, совершенно другая метрика.

- **"FCP и LCP — это одно и то же"** — FCP фиксирует любой первый контент (включая лоадер), LCP фиксирует самый большой значимый элемент. Страница может иметь отличный FCP и плохой LCP.

- **"TTI — это когда страница загружена"** — TTI определяется наличием 5-секундного "тихого окна" без Long Tasks, а не Load-событием. Страница может быть "загружена" (все ресурсы скачаны), но TTI ещё не достигнут, потому что JS продолжает выполняться.

- **"TBT можно измерить в реальном поле"** — нет. TBT — лабораторная метрика (Lighthouse). В поле используется INP. Путать их — признак поверхностного знания.

- **Не знать пороги** — на интервью часто спрашивают "что считается хорошим TTFB". TTFB: <800ms; FCP: <1.8s; TTI: <3.8s; TBT: <200ms. Не обязательно знать наизусть, но порядок цифр важен.

- **"Добавил defer на все скрипты — FCP стал хороший"** — `defer` помогает FCP, но если сам CSS большой или не оптимизирован, FCP всё равно будет медленным. Нужно смотреть в комплексе: TTFB → рендер-блокировка → размер критического CSS.

- **Игнорировать разницу mobile/desktop** — Lighthouse по умолчанию симулирует мобильное устройство (4x CPU slowdown, медленная сеть). TTI и TBT на мобильном могут быть в 3-5 раз хуже, чем на desktop. Говорить "у нас TTI хороший" без уточнения устройства — неполный ответ.
