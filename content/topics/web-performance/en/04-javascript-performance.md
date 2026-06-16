# JavaScript Performance

## Why JS is the most expensive resource type

A byte of JavaScript and a byte of an image of the same size cost the browser very different amounts:

```txt
200 KB image:
  Download → Decode → Paint
  All of this happens off-main-thread (in separate threads)

200 KB JavaScript:
  Download → Parse → Compile → Execute
                ↑         ↑        ↑
           main thread, main thread, main thread

  And "Execute" can take hundreds of milliseconds —
  the main thread is blocked FOR ALL OF THAT TIME.
  No response to clicks. No animations. Nothing.
```

This leads to the key principle: **less JS = faster**, even when it's minified and compressed. Network size is not the only cost. Parse and compile take time even after caching (though V8 does cache bytecode).

## Long Tasks — what they are and why they matter

A Long Task is any task on the main thread lasting **more than 50ms**. Long Tasks are what TBT is made of, and they're what causes poor INP.

```ts
// Detecting Long Tasks in the browser (production monitoring)
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    console.warn('Long Task:', {
      duration: `${entry.duration.toFixed(0)}ms`,
      startTime: entry.startTime,
      // attribution is available in Chrome: what caused the task
      attribution: (entry as PerformanceLongTaskTiming).attribution,
    });
  }
});

observer.observe({ type: 'longtask', buffered: true });
```

```txt
Common sources of Long Tasks in real applications:

  1. SPA hydration (React/Vue/Angular) — parsing + executing
     the entire JS bundle on first load. On a weak Android
     device this can take 500ms+.

  2. Heavy event handlers — synchronously processing a click
     with filtering/sorting a large array of data.

  3. Third-party scripts — analytics, chats, A/B testing.
     Often outside your control, but you can delay their loading.

  4. Large DOM renders — React re-renders a component with
     thousands of nodes synchronously.

  5. JSON.parse() of large payloads — a 1MB JSON ≈ 50–100ms
     parse time on an average device.
```

## Breaking up Long Tasks — yield techniques

When a Long Task is unavoidable, you can split it into parts, letting the browser "breathe" between them.

```ts
// ❌ Monolithic processing — blocks the main thread for the entire loop
function processOrders(orders: Order[]): Summary {
  return orders.reduce((acc, order) => {
    // expensive computation per order
    return computeOrderMetrics(acc, order);
  }, initialSummary);
}

// ✅ Chunked processing via scheduler.yield() (Chrome 115+)
async function processOrdersAsync(orders: Order[]): Promise<Summary> {
  let summary = initialSummary;

  for (let i = 0; i < orders.length; i++) {
    summary = computeOrderMetrics(summary, orders[i]);

    // Every 100 items — yield back to the event loop
    if (i % 100 === 0) {
      await scheduler.yield();
      // The browser processes pending clicks, animations, other tasks.
      // Then resumes from here.
    }
  }

  return summary;
}
```

```ts
// Polyfill for environments without scheduler.yield()
const yieldToMain = (): Promise<void> => {
  // scheduler.yield() is preferred: it resumes execution
  // at the same priority as the interrupted task.
  // setTimeout(0) queues at a lower priority.
  if ('scheduler' in window && 'yield' in scheduler) {
    return scheduler.yield();
  }
  return new Promise(resolve => setTimeout(resolve, 0));
};
```

```ts
// ✅ scheduler.postTask — explicit priority control
// (Chrome 94+, Firefox experimental)
async function handleUserClick(data: InputData) {
  // user-visible: high priority, runs immediately
  await scheduler.postTask(() => updateButtonState('loading'), {
    priority: 'user-visible',
  });

  // user-blocking: critical UI update
  await scheduler.postTask(() => renderPreview(data), {
    priority: 'user-blocking',
  });

  // background: analytics — doesn't block anything important
  scheduler.postTask(() => trackEvent('form_submit', data), {
    priority: 'background',
  });
}
```

## Web Workers — the real solution for CPU-bound work

`scheduler.yield()` splits a task over time, but JS still runs on the main thread. A **Web Worker** runs code in a separate OS thread — the main thread stays completely free.

```ts
// worker.ts — runs in a separate thread
self.onmessage = (event: MessageEvent<number[]>) => {
  const data = event.data;

  // As much heavy computation as needed — main thread untouched
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
// main.ts — hand the task off to the Worker
function runInWorker(data: number[]): Promise<number[]> {
  return new Promise((resolve, reject) => {
    // In production: reuse the worker instead of creating one each time
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

// Main thread is not blocked — UI responds to clicks
const button = document.querySelector('button')!;
button.addEventListener('click', async () => {
  button.disabled = true;
  const result = await runInWorker(largeDataset);
  renderResults(result);
  button.disabled = false;
});
```

```ts
// ✅ Comlink — wrapper for ergonomic Worker usage
// (eliminates postMessage/onmessage boilerplate)
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
// Looks like a normal async call, works via a Worker
```

## Code Splitting — load only what's needed

Code splitting breaks the bundle into parts loaded on demand. It's the primary tool for reducing TTI and TBT.

### Route-based splitting (automatic in Next.js)

```ts
// Next.js App Router: each route segment is a separate chunk.
// /dashboard code doesn't end up in the home page bundle.

// app/page.tsx             → chunk: main
// app/dashboard/page.tsx   → chunk: dashboard (loads on navigation)
// app/admin/page.tsx       → chunk: admin

// Pages Router — same via getStaticProps/getServerSideProps:
// pages/index.tsx          → chunk: index
// pages/checkout.tsx       → chunk: checkout
```

### Component-based splitting — React.lazy

```ts
// ❌ Importing the component into the main bundle
import { HeavyChart } from './HeavyChart'; // recharts + d3 = ~200KB

// ✅ Dynamic import — component loads only when needed (on mount)
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
// ✅ Conditional lazy loading — only for specific users
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
// ✅ Preload on hover — component loads before the user clicks
// (they have ~100–200ms between hover and click)
const preloadChart = () => import('./HeavyChart');

function DashboardLink() {
  return (
    <button
      onMouseEnter={preloadChart}
      onFocus={preloadChart}
      onClick={() => setShowChart(true)}
    >
      Show chart
    </button>
  );
}
```

### Dynamic import for libraries

```ts
// ❌ Top-level import of the entire library
import { format, parseISO, differenceInDays } from 'date-fns';

// ✅ Dynamic import only when needed
async function formatDate(dateStr: string): Promise<string> {
  const { format, parseISO } = await import('date-fns');
  return format(parseISO(dateStr), 'dd MMM yyyy');
}

// ✅ Or named imports from the ES-module version
// (date-fns supports tree shaking with named imports)
import { format } from 'date-fns/format';
import { parseISO } from 'date-fns/parseISO';
```

## Tree Shaking — eliminating dead code

Tree shaking is a bundler mechanism (webpack, Rollup, esbuild) for removing unused code from the bundle. It only works with ES modules (`import`/`export`).

### Why tree shaking often doesn't work

```ts
// ❌ CommonJS — tree shaking is IMPOSSIBLE
// Webpack can't statically determine what's being used because
// require() is a runtime function call
const utils = require('./utils');
const result = utils[dynamicKey](); // what's used? unknown

// ✅ ES Modules — tree shaking works
// Static analysis: only 'formatPrice' is imported
import { formatPrice } from './utils';
```

```ts
// ❌ Barrel files kill tree shaking
// utils/index.ts — re-exports everything
export * from './formatters';   // 50KB
export * from './validators';   // 30KB
export * from './transformers'; // 40KB

// Importing from a barrel:
import { formatPrice } from '@/utils';
// Webpack may include ALL 120KB in the bundle
// because side effects are unknown

// ✅ Direct import — only the needed module
import { formatPrice } from '@/utils/formatters';
```

```json
// package.json — explicitly declare files have no side effects.
// This signals webpack/Rollup: unused exports from these files
// can safely be removed.
{
  "sideEffects": false
}

// Or granularly — only specific files have side effects
{
  "sideEffects": [
    "*.css",
    "./src/polyfills.js",
    "./src/setup.js"
  ]
}
```

### Side effects — why this matters

```ts
// Example of a side effect in a module — code runs on import,
// not just exporting values
// analytics.ts
window.__analytics = { version: '1.0' }; // ← side effect!
export function track(event: string) { ... }

// If package.json says sideEffects: false, and track() is unused,
// the bundler removes this module INCLUDING the window.__analytics
// assignment. This is CORRECT only if the side effect isn't needed.
// If it is needed — list the file in sideEffects[].
```

```ts
// ❌ Common mistake with lodash
import _ from 'lodash'; // entire library = ~72KB gzip

// ✅ Named import from lodash-es
import { debounce, throttle } from 'lodash-es';
// Tree shaking removes everything except debounce and throttle

// ✅ Or path import (works with CommonJS lodash too)
import debounce from 'lodash/debounce';
import throttle from 'lodash/throttle';
```

## Bundle analysis — finding what takes up space

```bash
# Next.js — built-in analyzer
npm install @next/bundle-analyzer

# next.config.ts
import withBundleAnalyzer from '@next/bundle-analyzer';

export default withBundleAnalyzer({
  enabled: process.env.ANALYZE === 'true',
})({
  // ... rest of config
});

# Run
ANALYZE=true npm run build
# Opens an interactive bundle map in the browser
```

```bash
# Vite — rollup-plugin-visualizer
npm install rollup-plugin-visualizer -D

# vite.config.ts
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    visualizer({
      open: true,        // open in browser after build
      gzipSize: true,    // show gzip size
      brotliSize: true,  // and brotli size
    }),
  ],
});
```

```txt
What to look for in the bundle map:

  1. Duplicates — the same library included multiple times
     (different versions in node_modules, different entry points)

  2. Unexpectedly large dependencies:
     moment.js (300KB) → replace with date-fns
     lodash (70KB) → replace with lodash-es + tree shaking
     full Ant Design (1MB) → use only needed components

  3. Code that shouldn't be in the bundle:
     Node.js-only modules (fs, path) leaked into client code
     Test utilities, mock data
     Dev-only dependencies
```

## Bundle optimization — chunk strategies

```ts
// vite.config.ts — split into semantic chunks
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // vendor: everything from node_modules — cached separately
          // (changes less often than application code)
          if (id.includes('node_modules')) {
            // Large libraries get their own chunks
            if (id.includes('react') || id.includes('react-dom')) {
              return 'vendor-react';
            }
            if (id.includes('recharts') || id.includes('d3')) {
              return 'vendor-charts'; // only loads on chart pages
            }
            return 'vendor'; // remaining npm packages
          }
        },
      },
    },
  },
});
```

```ts
// next.config.ts — custom chunk strategies
export default {
  webpack(config) {
    config.optimization.splitChunks = {
      chunks: 'all',
      cacheGroups: {
        // Isolate React in a long-lived chunk
        react: {
          name: 'vendor-react',
          test: /[\\/]node_modules[\\/](react|react-dom)[\\/]/,
          priority: 20,
        },
        // Shared components used on 3+ pages
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

## Performance Budget — constraints as discipline

```ts
// Automated bundle size enforcement via bundlesize
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

## DevTools workflow for JS performance

```txt
Chrome DevTools → Performance panel:

  1. ⏺ Record → interact with the page → Stop
  2. Main thread track:
     - Red flags above tasks = Long Tasks
     - Click a task → Bottom-up: who's responsible?
     - "Script Evaluation" → JS parsing/compilation
     - "Parse HTML" interrupted by "Compile Script" → sync script

  3. Coverage tab (DevTools → ⋮ → More tools → Coverage):
     - After load: what % of JS was never executed?
     - Red bars in files = code that didn't run during load
     - Good candidates for code splitting

  4. Application → Storage → Clear storage → check
     first-visit behavior (no V8 cache)

Lighthouse → "Reduce unused JavaScript":
  → Shows specific files and how many bytes are unused
  → A direct signal for code splitting or removing a dependency
```

## Connection to other topics

```txt
[Performance Metrics]     — Long Tasks = TBT; code splitting
                            directly reduces TTI
[Core Web Vitals]         — Long Tasks are the main enemy of INP;
                            hydration bundle size affects LCP
[Resource Loading]        — dynamic import() + prefetch =
                            route-based preloading
[Rendering Performance]   — Heavy DOM renders create Long Tasks;
                            React Concurrent Mode splits them
                            automatically
```

## Common interview traps

- **"Tree shaking works with any JS"** — only with ES modules. CommonJS (`require`) cannot be tree-shaken by definition because `require()` is a runtime call. If a library only ships CJS, tree shaking won't help.

- **"I split the task with setTimeout — it no longer blocks"** — total CPU load is unchanged. You've only allowed the event loop to process other tasks between chunks. If the task is genuinely heavy, the correct solution is a Web Worker, not setTimeout.

- **"Code splitting makes the site faster"** — imprecise. Code splitting reduces the JS that needs to be parsed on initial load. For a specific route that still loads and executes a lot of code, it doesn't help there. But the TTI of the first page improves.

- **"Barrel files are convenient and don't affect performance"** — they do. Webpack/bundlers may fail to tree-shake exports from a barrel if `sideEffects: false` isn't configured. The result: `import { one } from '@/utils'` pulls in all 120KB instead of the 1KB needed module.

- **"I added sideEffects: false and that's it"** — `sideEffects: false` promises the bundler that any unused module can be discarded. If a file has a real side effect (CSS injection, window assignment, polyfill) — it must be explicitly listed in the `sideEffects` array, otherwise you'll break the app.

- **"A Web Worker will fix my performance problem"** — only for CPU-bound tasks. A Worker won't help if the problem is a heavy React tree render (that still happens on the main thread). For rendering, you need other techniques: virtualization, React.memo, useDeferredValue.

- **"I checked in DevTools on my MacBook — it's fast"** — performance on a top MacBook is 5–10× faster than an average Android. Lighthouse applies 4x CPU throttling to simulate a real device. Always verify on a real mobile device or with throttling enabled.
