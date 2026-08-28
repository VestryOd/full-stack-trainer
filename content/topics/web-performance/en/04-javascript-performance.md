# JavaScript Performance

## Why JS is the most expensive resource type

A byte of JavaScript and a byte of an image of the same size cost the browser very different amounts:

```txt
200 KB image:
  Download → Decode → Paint     (all off the main thread)

200 KB JavaScript:
  Download → Parse → Compile → Execute
                ↑         ↑        ↑
           main thread, main thread, main thread
```

An image is handled off the main thread. JavaScript is not: parse, compile and execute all happen on it. **Execute alone can take hundreds of milliseconds, and the main thread is blocked for that whole time** — no response to clicks, no animations, nothing.

This leads to the key principle: **less JS = faster**, even when it's minified and compressed. Network size is not the only cost. Parse and compile take time even after caching (though V8 does cache bytecode).

## Long Tasks — what they are and why they matter

A Long Task is any task on the main thread lasting **more than 50ms**. Long Tasks are what TBT (Total Blocking Time) is made of. They are also what makes INP (Interaction to Next Paint) bad.

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

Where Long Tasks come from in real applications:

1. **Hydration of an SPA** (single-page application) built on React, Vue or Angular. The whole JS bundle is parsed and executed on first load, and on a weak Android device that alone can take 500ms or more.
2. **Heavy event handlers** — a click that synchronously filters or sorts a large array of data.
3. **Third-party scripts** — analytics, chat widgets, A/B testing. Often outside your control, but you can delay when they load.
4. **Large renders of the DOM** (Document Object Model — the tree of page elements). React re-renders a component with thousands of nodes, synchronously.
5. **`JSON.parse()` of a large payload** — a one-megabyte JSON takes roughly 50–100ms to parse on an average device.

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

`scheduler.yield()` splits a task over time, but the JS still runs on the main thread. Some work is bound by the CPU (the central processing unit), not by waiting for the network. That work needs a different tool. A **Web Worker** runs code in a separate operating-system thread, and the main thread stays completely free.

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

Code splitting breaks the bundle into parts that load on demand. It is the primary tool for reducing TTI (Time to Interactive) and TBT.

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

Tree shaking is a bundler mechanism (webpack, Rollup, esbuild) for removing unused code from the bundle. It only works with ES modules. ES is ECMAScript, the standard behind JavaScript, and its modules are the `import`/`export` syntax.

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

What to look for in the bundle map:

1. **Duplicates** — the same library included several times, from different versions in `node_modules` or from different entry points.
2. **Unexpectedly large dependencies.** Three of them show up again and again:
   - `moment.js` at 300KB — replace it with `date-fns`.
   - `lodash` at 70KB — replace it with `lodash-es` and let tree shaking work.
   - The full Ant Design at 1MB — import only the components you use.
3. **Code that should not be in the bundle at all.** Node.js-only modules such as `fs` and `path` leak into client code. So do test utilities, mock data and dev-only dependencies.

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

In the Chrome DevTools **Performance** panel:

1. Press record, interact with the page, then stop.
2. On the main thread track, red flags above tasks mark Long Tasks. Click a task and open `Bottom-up` to see who is responsible. `Script Evaluation` is JS parsing and compilation, and `Parse HTML` interrupted by `Compile Script` means a synchronous script.
3. Open the `Coverage` tab (⋮ → More tools → Coverage). After load it shows what share of the JS never ran. Red bars in a file mark code that did not run during load, and those files are good candidates for code splitting.
4. Application → Storage → Clear storage, then reload to check first-visit behaviour without the V8 cache.

In Lighthouse, "Reduce unused JavaScript" lists the specific files and how many bytes of each went unused. That is a direct signal to split the code or drop a dependency.

## Connection to other topics

- [Performance Metrics](./02-performance-metrics.md) — Long Tasks are what TBT measures, and code splitting directly reduces TTI.
- [Core Web Vitals](./01-core-web-vitals.md) — Long Tasks are the main enemy of INP, and the size of the hydration bundle affects LCP (Largest Contentful Paint).
- [Resource Loading](./03-resource-loading.md) — a dynamic `import()` plus `prefetch` gives route-based preloading.
- [Rendering Performance](./06-rendering-performance.md) — heavy DOM renders create Long Tasks, and React Concurrent Mode splits them automatically.

## Common interview traps

- **"Tree shaking works with any JS"** — only with ES modules. CommonJS (`require`) cannot be tree-shaken by definition because `require()` is a runtime call. If a library only ships CJS — the CommonJS format — tree shaking will not help.

- **"I split the task with setTimeout — it no longer blocks"** — total CPU load is unchanged. You've only allowed the event loop to process other tasks between chunks. If the task is genuinely heavy, the correct solution is a Web Worker, not setTimeout.

- **"Code splitting makes the site faster"** — imprecise. Code splitting reduces the JS that needs to be parsed on initial load. For a specific route that still loads and executes a lot of code, it doesn't help there. But the TTI of the first page improves.

- **"Barrel files are convenient and don't affect performance"** — they do. Webpack/bundlers may fail to tree-shake exports from a barrel if `sideEffects: false` isn't configured. The result: `import { one } from '@/utils'` pulls in all 120KB instead of the 1KB needed module.

- **"I added sideEffects: false and that's it"** — `sideEffects: false` promises the bundler that any unused module can be discarded. If a file has a real side effect — CSS injection, a window assignment, a polyfill — list it in the `sideEffects` array. Otherwise you break the app.

- **"A Web Worker will fix my performance problem"** — only for CPU-bound tasks. A Worker won't help if the problem is a heavy React tree render (that still happens on the main thread). For rendering, you need other techniques: virtualization, React.memo, useDeferredValue.

- **"I checked in DevTools on my MacBook — it's fast"** — performance on a top MacBook is 5–10× faster than an average Android. Lighthouse applies 4x CPU throttling to simulate a real device. Always verify on a real mobile device or with throttling enabled.
