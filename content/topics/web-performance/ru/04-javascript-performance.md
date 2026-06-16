<!-- verified: 2026-06-16, corrections: 0 -->
# JavaScript Performance

## Почему JS — самый дорогой тип ресурса

Байт JavaScript и байт изображения одинакового размера стоят браузеру совершенно по-разному:

```txt
200 KB изображения:
  Скачать → Декодировать → Отрисовать
  Всё это происходит off-main-thread (в отдельных потоках)

200 KB JavaScript:
  Скачать → Parse → Compile → Execute
                ↑         ↑        ↑
           main thread, main thread, main thread

  Причём "Execute" может занимать сотни миллисекунд —
  и ВСЁ ЭТО ВРЕМЯ main thread заблокирован.
  Никакой реакции на клики. Никаких анимаций. Ничего.
```

Из этого следует ключевой принцип: **меньше JS = быстрее**, даже если он минифицирован и сжат. Размер по сети — не единственная стоимость. Parse и compile занимают время даже после кэша (хотя V8 кэширует байт-код).

## Long Tasks — что это и почему важно

Long Task — любая задача на main thread продолжительностью **более 50ms**. Именно из Long Tasks складывается TBT, и именно они вызывают плохой INP.

```ts
// Обнаружение Long Tasks в браузере (мониторинг в production)
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    console.warn('Long Task:', {
      duration: `${entry.duration.toFixed(0)}ms`,
      startTime: entry.startTime,
      // attribution доступен в Chrome: что именно вызвало задачу
      attribution: (entry as PerformanceLongTaskTiming).attribution,
    });
  }
});

observer.observe({ type: 'longtask', buffered: true });
```

```txt
Типичные источники Long Tasks в реальных приложениях:

  1. Hydration SPA (React/Vue/Angular) — парсинг + выполнение
     всего JS бандла при первой загрузке. На слабом Android
     может занимать 500ms+.

  2. Тяжёлые event handlers — синхронная обработка клика
     с фильтрацией/сортировкой большого массива данных.

  3. Сторонние скрипты — аналитика, чаты, A/B-тестирование.
     Часто вне вашего контроля, но можно отложить загрузку.

  4. Большие рендеры DOM — React перерисовывает компонент
     с тысячами узлов синхронно.

  5. JSON.parse() больших данных — 1MB JSON = ~50-100ms parse
     на среднем устройстве.
```

## Разбивка Long Tasks — техники yield

Если Long Task неизбежна, её можно разбить на части, давая браузеру "подышать" между ними.

```ts
// ❌ Монолитная обработка — блокирует main thread на весь цикл
function processOrders(orders: Order[]): Summary {
  return orders.reduce((acc, order) => {
    // тяжёлые вычисления для каждого заказа
    return computeOrderMetrics(acc, order);
  }, initialSummary);
}

// ✅ Разбивка через scheduler.yield() (Chrome 115+)
async function processOrdersAsync(orders: Order[]): Promise<Summary> {
  let summary = initialSummary;

  for (let i = 0; i < orders.length; i++) {
    summary = computeOrderMetrics(summary, orders[i]);

    // Каждые 100 элементов — yield обратно в event loop
    if (i % 100 === 0) {
      await scheduler.yield();
      // Браузер обрабатывает pending-клики, анимации, другие задачи.
      // Затем возвращается к продолжению цикла.
    }
  }

  return summary;
}
```

```ts
// Полифил для окружений без scheduler.yield()
const yieldToMain = (): Promise<void> => {
  // scheduler.yield() предпочтительнее: он восстанавливает
  // выполнение с тем же приоритетом что и прерванная задача.
  // setTimeout(0) ставит в очередь с более низким приоритетом.
  if ('scheduler' in window && 'yield' in scheduler) {
    return scheduler.yield();
  }
  return new Promise(resolve => setTimeout(resolve, 0));
};
```

```ts
// ✅ scheduler.postTask — явный контроль приоритета
// (Chrome 94+, Firefox экспериментально)
async function handleUserClick(data: InputData) {
  // user-visible: высокий приоритет, выполнится немедленно
  await scheduler.postTask(() => updateButtonState('loading'), {
    priority: 'user-visible',
  });

  // user-blocking: критичное обновление UI
  await scheduler.postTask(() => renderPreview(data), {
    priority: 'user-blocking',
  });

  // background: аналитика — не блокирует ничего важного
  scheduler.postTask(() => trackEvent('form_submit', data), {
    priority: 'background',
  });
}
```

## Web Workers — реальное решение для CPU-bound задач

`scheduler.yield()` делит задачу во времени, но JS всё равно выполняется на main thread. **Web Worker** выполняет код в отдельном потоке ОС — main thread остаётся полностью свободным.

```ts
// worker.ts — выполняется в отдельном потоке
self.onmessage = (event: MessageEvent<number[]>) => {
  const data = event.data;

  // Сколько угодно тяжёлых вычислений — main thread не затронут
  const result = data
    .filter(n => isPrime(n))
    .map(n => n * n);

  self.postMessage(result);
};

function isPrime(n: number): boolean {
  if (n < 2) return false;
  for (let i = 2; i <= Math.sqrt(n); i++) {
    if (n % i === 0) return false;
  }
  return true;
}
```

```ts
// main.ts — отправляем задачу в Worker
function runInWorker(data: number[]): Promise<number[]> {
  return new Promise((resolve, reject) => {
    // В продакшене переиспользовать worker, а не создавать каждый раз
    const worker = new Worker(new URL('./worker.ts', import.meta.url), {
      type: 'module',
    });

    worker.onmessage = (e: MessageEvent<number[]>) => {
      resolve(e.data);
      worker.terminate();
    };
    worker.onerror = reject;
    worker.postMessage(data);
  });
}

// Main thread не заблокирован — UI отвечает на клики
const button = document.querySelector('button')!;
button.addEventListener('click', async () => {
  button.disabled = true;
  const result = await runInWorker(largeDataset);
  renderResults(result);
  button.disabled = false;
});
```

```ts
// ✅ Comlink — обёртка для удобной работы с Workers
// (устраняет boilerplate postMessage/onmessage)
import * as Comlink from 'comlink';

// worker.ts
const api = {
  processData(data: number[]): number[] {
    return data.filter(isPrime).map(n => n * n);
  },
};
Comlink.expose(api);

// main.ts
const worker = new Worker(new URL('./worker.ts', import.meta.url));
const api = Comlink.wrap<typeof import('./worker')['default']>(worker);
const result = await api.processData(largeDataset);
// Выглядит как обычный async вызов, работает через Worker
```

## Code Splitting — загружаем только нужное

Code splitting — разбивка бандла на части, загружаемые по требованию. Главный инструмент снижения TTI и TBT.

### Route-based splitting (автоматически в Next.js)

```ts
// Next.js App Router: каждый route segment — отдельный чанк.
// Код /dashboard не попадает в бандл главной страницы.

// app/page.tsx        → chunk: main
// app/dashboard/page.tsx → chunk: dashboard (загружается при навигации)
// app/admin/page.tsx  → chunk: admin

// Pages Router — то же самое через getStaticProps/getServerSideProps:
// pages/index.tsx     → chunk: index
// pages/checkout.tsx  → chunk: checkout
```

### Component-based splitting — React.lazy

```ts
// ❌ Импорт компонента в основной бандл
import { HeavyChart } from './HeavyChart'; // recharts + d3 = ~200KB

// ✅ Динамический импорт — компонент загружается только
// когда он нужен (при монтировании)
import { lazy, Suspense } from 'react';

const HeavyChart = lazy(() => import('./HeavyChart'));

function Dashboard() {
  return (
    <Suspense fallback={<ChartSkeleton />}>
      <HeavyChart data={data} />
    </Suspense>
  );
}
```

```ts
// ✅ Условный lazy loading — только для определённых пользователей
const AdminPanel = lazy(() => import('./AdminPanel'));

function App({ user }: { user: User }) {
  return (
    <div>
      <MainContent />
      {user.isAdmin && (
        <Suspense fallback={<Skeleton />}>
          <AdminPanel />
        </Suspense>
      )}
    </div>
  );
}
```

```ts
// ✅ Preload при наведении — компонент грузится до того,
// как пользователь кликнул (у него есть ~100-200ms)
const preloadChart = () => import('./HeavyChart');

function DashboardLink() {
  return (
    <button
      onMouseEnter={preloadChart}
      onFocus={preloadChart}
      onClick={() => setShowChart(true)}
    >
      Показать график
    </button>
  );
}
```

### Dynamic import для библиотек

```ts
// ❌ Импорт всей библиотеки в топ-уровне
import { format, parseISO, differenceInDays } from 'date-fns';

// ✅ Динамический импорт только при необходимости
async function formatDate(dateStr: string): Promise<string> {
  const { format, parseISO } = await import('date-fns');
  return format(parseISO(dateStr), 'dd MMM yyyy');
}

// ✅ Или именованные импорты из ES-модульной версии
// (date-fns поддерживает tree shaking при именованном импорте)
import { format } from 'date-fns/format';
import { parseISO } from 'date-fns/parseISO';
```

## Tree Shaking — убираем мёртвый код

Tree shaking — механизм сборщиков (webpack, Rollup, esbuild) для удаления неиспользуемого кода из бандла. Работает только с ES-модулями (`import`/`export`).

### Почему tree shaking часто не работает

```ts
// ❌ CommonJS — tree shaking НЕВОЗМОЖЕН
// Webpack не может статически определить, что именно используется,
// потому что require() — это вызов функции в рантайме
const utils = require('./utils');
const result = utils[dynamicKey](); // что используется — неизвестно

// ✅ ES Modules — tree shaking работает
// Статический анализ: импортируется только 'formatPrice'
import { formatPrice } from './utils';
```

```ts
// ❌ Barrel-файлы ("бочки") убивают tree shaking
// utils/index.ts — реэкспортирует всё подряд
export * from './formatters';   // 50KB
export * from './validators';   // 30KB
export * from './transformers'; // 40KB

// Импорт из barrel:
import { formatPrice } from '@/utils';
// Webpack может включить ВСЕ 120KB в бандл,
// потому что side effects неизвестны

// ✅ Прямой импорт — только нужный модуль
import { formatPrice } from '@/utils/formatters';
```

```json
// package.json — явно указываем что файлы без side effects
// Это сигнал webpack/Rollup: неиспользуемые экспорты
// из этих файлов можно безопасно удалить
{
  "sideEffects": false
}

// Или точечно — только определённые файлы имеют side effects
{
  "sideEffects": [
    "*.css",
    "./src/polyfills.js",
    "./src/setup.js"
  ]
}
```

### Side effects — почему это важно

```ts
// Пример side effect в модуле — код выполняется при импорте,
// не только экспортирует значения
// analytics.ts
window.__analytics = { version: '1.0' }; // ← side effect!
export function track(event: string) { ... }

// Если в package.json sideEffects: false, и track() не используется,
// сборщик удалит этот модуль ВМЕСТЕ с присваиванием window.__analytics.
// Это ПРАВИЛЬНО только если side effect действительно не нужен.
// Если нужен — укажите файл в sideEffects[].
```

```ts
// ❌ Популярная ошибка с lodash
import _ from 'lodash'; // вся библиотека = ~72KB gzip

// ✅ Именованный импорт из lodash-es
import { debounce, throttle } from 'lodash-es';
// Tree shaking уберёт всё кроме debounce и throttle

// ✅ Или точечный импорт (работает и с CommonJS lodash)
import debounce from 'lodash/debounce';
import throttle from 'lodash/throttle';
```

## Анализ бандла — найти что занимает место

```bash
# Next.js — встроенный анализатор
npm install @next/bundle-analyzer

# next.config.ts
import withBundleAnalyzer from '@next/bundle-analyzer';

export default withBundleAnalyzer({
  enabled: process.env.ANALYZE === 'true',
})({
  // ... остальной конфиг
});

# Запуск
ANALYZE=true npm run build
# Откроет интерактивную карту бандла в браузере
```

```bash
# Vite — rollup-plugin-visualizer
npm install rollup-plugin-visualizer -D

# vite.config.ts
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    visualizer({
      open: true,        // открыть в браузере после сборки
      gzipSize: true,    // показывать размер после gzip
      brotliSize: true,  // и после brotli
    }),
  ],
});
```

```txt
Что искать в карте бандла:

  1. Дубликаты — одна библиотека включена несколько раз
     (разные версии в node_modules, разные точки входа)

  2. Неожиданно большие зависимости:
     moment.js (300KB) → заменить на date-fns
     lodash (70KB) → заменить на lodash-es с tree shaking
     full Ant Design (1MB) → использовать только нужные компоненты

  3. Код, не нужный в бандле:
     Node.js-only модули (fs, path) попали в клиентский код
     Тестовые утилиты, mock-данные
     Dev-only зависимости
```

## Bundle optimization — стратегии чанков

```ts
// vite.config.ts — разбивка на смысловые чанки
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // vendor: всё из node_modules — кэшируется отдельно
          // (меняется реже, чем код приложения)
          if (id.includes('node_modules')) {
            // Крупные библиотеки — в отдельные чанки
            if (id.includes('react') || id.includes('react-dom')) {
              return 'vendor-react';
            }
            if (id.includes('recharts') || id.includes('d3')) {
              return 'vendor-charts'; // загружается только на странице с графиками
            }
            return 'vendor'; // остальные npm пакеты
          }
        },
      },
    },
  },
});
```

```ts
// next.config.ts — кастомные chunk стратегии
export default {
  webpack(config) {
    config.optimization.splitChunks = {
      chunks: 'all',
      cacheGroups: {
        // Выделить React в отдельный долгоживущий чанк
        react: {
          name: 'vendor-react',
          test: /[\\/]node_modules[\\/](react|react-dom)[\\/]/,
          priority: 20,
        },
        // Общие компоненты, используемые на 3+ страницах
        commons: {
          name: 'commons',
          minChunks: 3,
          priority: 10,
        },
      },
    };
    return config;
  },
};
```

## Performance Budget — ограничения как дисциплина

```ts
// Автоматический контроль размера бандла через bundlesize
// package.json
{
  "bundlesize": [
    { "path": ".next/static/chunks/main-*.js", "maxSize": "80 kB" },
    { "path": ".next/static/chunks/pages/index-*.js", "maxSize": "50 kB" }
  ]
}
```

```yaml
# .github/workflows/bundle-check.yml
name: Bundle Size Check
on: [pull_request]
jobs:
  bundle:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build
      - uses: actions/github-script@v7
        with:
          script: |
            const { execSync } = require('child_process');
            const size = execSync('du -sh .next/static').toString();
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              body: `Bundle size: ${size}`
            });
```

## DevTools-воркфлоу для JS-производительности

```txt
Chrome DevTools → Performance panel:

  1. ⏺ Record → взаимодействие → Stop
  2. Main thread track:
     - Красные флажки над задачами = Long Tasks
     - Нажать на задачу → Bottom-up: кто виноват?
     - "Script Evaluation" → парсинг/компиляция JS
     - "Parse HTML" прерывается на "Compile Script" → синхронный скрипт

  3. Coverage tab (DevTools → ⋮ → More tools → Coverage):
     - После загрузки: сколько % JS не выполнилось?
     - Красные полосы в файлах = код не запускался при загрузке
     - Хорошие кандидаты для code splitting

  4. Application → Storage → Clear storage → проверить
     поведение при первом посещении (без кэша V8)

Lighthouse → "Reduce unused JavaScript":
  → Показывает конкретные файлы и сколько байт неиспользовано
  → Прямой сигнал для code splitting или удаления зависимости
```

## Связь с другими темами

```txt
[Performance Metrics]     — Long Tasks = TBT; code splitting
                            напрямую снижает TTI
[Core Web Vitals]         — Long Tasks = главный враг INP;
                            hydration бандла влияет на LCP
[Resource Loading]        — dynamic import() + prefetch =
                            предзагрузка следующего роута
[Rendering Performance]   — Heavy рендер DOM создаёт
                            Long Tasks; React Concurrent
                            разбивает их автоматически
```

## Типичные ошибки на интервью

- **"Tree shaking работает с любым JS"** — только с ES-модулями. CommonJS (`require`) tree shaking невозможен по определению, потому что `require()` — рантайм-вызов. Если библиотека публикует только CJS — tree shaking не поможет.

- **"Я разбил задачу через setTimeout — теперь она не блокирует"** — суммарная нагрузка на CPU не изменилась. Вы лишь позволили event loop обрабатывать другие задачи между частями. Если задача действительно тяжёлая — правильное решение Web Worker, а не setTimeout.

- **"Code splitting ускоряет сайт"** — неточно. Code splitting снижает количество JS, которое нужно распарсить при начальной загрузке. Для конкретного маршрута, где всё равно грузится и выполняется много кода, это не помогает. Зато TTI первой страницы улучшается.

- **"Barrel-файлы удобны и не влияют на производительность"** — влияют. Webpack/bundler может не tree shaking'ить экспорты из barrel если не настроен `sideEffects: false`. В итоге `import { one } from '@/utils'` тянет все 120KB вместо 1KB нужного модуля.

- **"Добавил sideEffects: false и всё"** — sideEffects: false обещает бандлеру, что любой неиспользуемый модуль можно выбросить. Если в каком-то файле есть реальный side effect (CSS injection, window-присваивание, полифил) — его нужно явно исключить в массиве `sideEffects`, иначе поломаете приложение.

- **"Web Worker решит проблему производительности"** — только для CPU-bound задач. Worker не поможет если проблема в тяжёлом рендере React-дерева (это всё равно происходит на main thread). Для рендера нужны другие техники: виртуализация, React.memo, useDeferredValue.

- **"Проверил в DevTools на своём MacBook — всё быстро"** — performance на топовом MacBook в 5–10× быстрее среднего Android. Lighthouse применяет 4x CPU throttling для симуляции реального устройства. Всегда проверяйте на реальном мобильном или с throttling.
