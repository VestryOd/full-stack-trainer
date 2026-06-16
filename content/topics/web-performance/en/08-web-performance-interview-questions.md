# Web Performance — Interview Questions (Middle → Senior)

## How to use this cheat sheet

Each answer compresses the depth from the topic articles. Performance interviews at senior level always go deeper: "how would you measure that?", "what's the trade-off?", "show me the DevTools workflow." Each group ends with **"Typical follow-ups"** showing where the conversation usually goes.

---

## Group 1: Core Web Vitals

**1. What are the three Core Web Vitals and what exactly does each measure?**

**LCP (Largest Contentful Paint):** the render time of the largest visible element in the viewport (usually a hero image or `<h1>`). Measures *loading performance*. Good: ≤ 2.5s.

**CLS (Cumulative Layout Shift):** the sum of all unexpected layout shifts during the page's lifetime, weighted by impact fraction × distance fraction. Measures *visual stability*. Good: ≤ 0.1.

**INP (Interaction to Next Paint):** the 75th percentile of all interaction latencies (click, tap, keypress) observed during the page visit — from user input to the next frame painted. Replaced FID in March 2024. Measures *responsiveness*. Good: ≤ 200ms.

---

**2. Why did Google replace FID with INP, and what does INP reveal that FID didn't?**

FID (First Input Delay) measured only the *delay before the browser could start processing* the first interaction — it excluded processing time and paint. A handler that blocked the main thread for 800ms after starting would show FID = 5ms but feel completely unresponsive. INP measures the *full duration* from input to next frame, across *all* interactions during the visit (taking the 75th percentile). A page with slow `onClick` handlers on dynamically loaded content would score fine on FID but fail INP.

---

**3. What causes CLS, and give three concrete fixes.**

CLS is caused by elements shifting after initial layout. Common causes and fixes:

**Images without dimensions:**
```html
<!-- ❌ browser doesn't know height → reflows when image loads -->
<img src="hero.jpg" alt="Hero">

<!-- ✅ reserve space with aspect-ratio or explicit dimensions -->
<img src="hero.jpg" alt="Hero" width="1200" height="600">
<!-- or CSS: aspect-ratio: 2/1 -->
```

**Late-injected content:** ads, cookie banners, and dynamic widgets inserted above existing content push it down. Fix: reserve space for them with min-height or skeleton placeholders.

**Web fonts causing FOUT/FOIT:** fallback font has different metrics, text reflows when custom font loads. Fix: `font-display: optional` (never reflows, may show fallback permanently) or `font-display: swap` + `size-adjust` / `ascent-override` to match fallback metrics.

---

**4. What is LCP and what are the four elements that can be the LCP element?**

LCP is the render timestamp of the largest *contentful* element visible in the viewport when the user first views the page. The four eligible element types: `<img>`, `<image>` inside SVG, `<video>` (poster image), and elements with a CSS background-image. Text blocks (`<p>`, `<h1>`, etc.) can also be LCP elements if they are the largest. Background images set via CSS are eligible only if they are fetched from a URL (not gradients).

---

**5. Walk through the complete LCP optimization checklist.**

LCP time = network latency + server TTFB + resource load time + render time. Attack each:

**1. Reduce TTFB:** CDN, edge caching, fast origin server. TTFB > 600ms is the primary culprit for slow LCP.

**2. Eliminate render-blocking resources:** move non-critical CSS to `<link media="print">` or async load; defer non-critical JS.

**3. Preload the LCP resource:**
```html
<link rel="preload" as="image" href="/hero.webp"
      imagesrcset="/hero-400.webp 400w, /hero-800.webp 800w"
      imagesizes="100vw">
```

**4. Use modern image formats:** WebP saves ~30%, AVIF ~50% vs JPEG at same quality.

**5. Do not lazy-load the LCP image:** `loading="lazy"` on the hero image delays LCP by the scroll-observation delay. Use `fetchpriority="high"` instead.

**6. Avoid client-side rendering for the LCP element:** if the LCP element is injected by JavaScript, the browser must download, parse, and execute JS before painting it. SSR or SSG puts the element in initial HTML.

---

## Typical follow-ups (Group 1)

```txt
"How do you measure CWV in production, not just in DevTools?" →
  field data: Chrome UX Report (CrUX) via PageSpeed Insights,
  Search Console CWV report, or the web-vitals JS library sending
  to your own analytics. Lab data (Lighthouse, DevTools) is synthetic
  and doesn't capture real user conditions (slow Android devices,
  3G, background tabs). Field data is what Google uses for ranking.

"A page passes Lighthouse but fails CWV in Search Console — why?" →
  Lighthouse is lab data on a simulated device. CrUX is field data
  from real Chrome users at the 75th percentile. Real users have
  slower devices, cache misses, background tabs, and extensions.
  Also: Lighthouse measures a fresh cold load; CWV includes
  soft navigations and repeat visits.

"What is TTFB and how does it relate to LCP?" →
  TTFB (Time to First Byte) is the time from request to first byte
  of the response. It is a sub-metric of LCP — a slow server
  delays everything downstream. A TTFB > 600ms will almost certainly
  push LCP past 2.5s even with perfect frontend optimization.
```

---

## Group 2: Resource Loading

**6. What is the critical rendering path and which resources block it?**

The critical rendering path is the sequence of steps the browser must complete before the first pixel is painted: DNS → TCP → TLS → HTTP request → HTML parse → DOM construction → CSSOM construction → Render Tree → Layout → Paint.

**Render-blocking resources:** CSS files in `<head>` (the browser won't paint until CSSOM is built), synchronous `<script>` tags without `defer` or `async` (pause HTML parsing), and `@import` in CSS (creates additional sequential fetches). Images, fonts, and async scripts do not block the initial render.

---

**7. `defer` vs `async` vs module scripts — how do they differ?**

```html
<!-- async: download in parallel, execute immediately when ready
     (pauses HTML parsing). No guaranteed execution order. -->
<script async src="analytics.js"></script>

<!-- defer: download in parallel, execute AFTER HTML is fully parsed,
     IN ORDER. Safe for scripts that depend on the DOM. -->
<script defer src="app.js"></script>

<!-- type="module": always deferred by default. Executes after
     HTML parsed, supports import/export, strict mode, own scope. -->
<script type="module" src="main.js"></script>
```

Rule: `defer` for scripts that need the DOM; `async` for independent scripts (analytics, ads) where order doesn't matter; `type="module"` for ESM bundles — they are deferred automatically.

---

**8. What does `rel="preload"` do and when should you use it vs `rel="prefetch"`?**

`preload`: tells the browser "you will need this resource soon — start fetching it now, at high priority." Used for resources the browser discovers late in the page load (hero image in CSS, font used in above-fold content, critical script). Does not execute the resource — just fetches and caches.

`prefetch`: tells the browser "the user might navigate to a page that needs this." Low-priority background fetch, stored in the HTTP cache. Used for next-page navigation resources.

```html
<!-- preload: fetch NOW, high priority, for current page -->
<link rel="preload" as="font" href="/fonts/inter.woff2" crossorigin>
<link rel="preload" as="image" href="/hero.webp">

<!-- prefetch: fetch SOON, low priority, for next navigation -->
<link rel="prefetch" href="/checkout.js">
```

Misusing `preload` for non-critical resources wastes bandwidth and competes with critical resources. The browser will also warn: "preload was found but not used within 3s."

---

**9. What is a connection waterfall and how do you diagnose it in DevTools?**

A connection waterfall is a chain of sequential network requests where each request depends on the previous one completing before it can even begin. Classic example: HTML → JS bundle → API call → another API call. In DevTools Network panel, look for long horizontal bars with a staircase shape — each request starts only after the previous one's response.

Fixes: (1) resource hints (`preconnect`, `preload`) to start fetches earlier; (2) colocating API calls on the server (BFF pattern); (3) HTTP/2 or HTTP/3 multiplexing — multiple requests on one connection; (4) inlining critical CSS to avoid a separate CSS fetch on the critical path.

---

**10. What is HTTP/2 multiplexing and what performance problem does it solve?**

HTTP/1.1 allows only one active request per TCP connection. Browsers compensate by opening 6 connections per domain — but each has TCP slow-start overhead. HTTP/2 sends multiple streams over a single connection simultaneously with no head-of-line blocking at the HTTP layer. This makes: domain sharding anti-pattern (splitting resources across `static1.cdn.com`, `static2.cdn.com` to open more connections), and bundling everything into one giant file less necessary — many small files is fine on HTTP/2. HTTP/3 adds connection-level HOL blocking fix via QUIC (UDP-based).

---

## Typical follow-ups (Group 2)

```txt
"When does preloading a font HURT performance?" →
  If the font is not used above the fold, preload competes with
  LCP resources (hero image, critical CSS) for bandwidth. If the
  font file is large (variable fonts can be 500KB+), preloading
  the full file for a few characters wastes bandwidth.
  Better: preload only the subset used above the fold,
  use font subsetting tools (pyftsubset, Fonttools).

"What is resource hints priority order?" →
  preconnect > preload > prefetch > dns-prefetch.
  preconnect opens the TCP+TLS connection (not just DNS).
  Only use preconnect for 2-3 critical origins — each kept-alive
  connection consumes browser resources.

"Lighthouse says 'eliminate render-blocking resources.' The
CSS is already in <head> — what do you do?" →
  Split CSS: extract above-the-fold styles and inline them in
  <style> in <head>. Load the rest with <link media="print">
  which the browser fetches non-blocking, then switch to media="all"
  via JS onload. Or use a CSS-in-JS solution that extracts
  critical CSS per component automatically (Next.js does this).
```

---

## Group 3: Rendering Pipeline

**11. Describe the browser rendering pipeline from HTML bytes to pixels.**

```txt
Bytes → Characters → Tokens → Nodes → DOM
                                           ↘
CSS Bytes → Characters → Tokens → Nodes → CSSOM
                                           ↙
                              Render Tree (only visible nodes)
                                    ↓
                                 Layout (geometry — x, y, width, height)
                                    ↓
                                  Paint (fill pixels into layers)
                                    ↓
                               Composite (GPU merges layers → screen)
```

Key points: (1) JS blocks DOM construction when encountered (unless `defer`/`async`); (2) CSS blocks rendering (CSSOM must be built before Render Tree); (3) Layout and Paint are expensive — avoid triggering them in loops; (4) Composite is cheapest — only properties on GPU layers (`transform`, `opacity`) can animate without Layout/Paint.

---

**12. What is layout thrashing and how do you fix it?**

Layout thrashing (forced synchronous layout): reading a layout property (`offsetHeight`, `getBoundingClientRect()`) forces the browser to flush pending style changes and recalculate layout synchronously — before the next frame. Then writing a style forces another layout on the next read. In a loop, this causes N layout recalculations per frame instead of one.

```ts
// ❌ Layout thrashing — read forces layout, write invalidates it, loop repeats
elements.forEach(el => {
  const height = el.offsetHeight;    // forces layout flush
  el.style.height = height * 2 + 'px'; // invalidates layout
});

// ✅ Batch reads first, then batch writes
const heights = elements.map(el => el.offsetHeight); // one layout flush
elements.forEach((el, i) => {
  el.style.height = heights[i] * 2 + 'px';           // batch writes
});
// Or use requestAnimationFrame to batch in the next frame
```

---

**13. Which CSS properties are cheap to animate and which are expensive?**

**Cheap (compositor-only, no Layout or Paint):**
- `transform` (translate, rotate, scale)
- `opacity`
- `filter` (on composited layers)
- `will-change: transform` (promotes element to its own layer)

**Expensive (triggers Layout → Paint → Composite):**
- `width`, `height`, `margin`, `padding`, `top`, `left` — trigger Layout
- `background-color`, `color`, `border-color`, `box-shadow` — trigger Paint

Rule: animate `transform: translateX()` instead of `left`, `transform: scaleX()` instead of `width`. The GPU handles transform/opacity natively; Layout and Paint run on the CPU.

---

**14. What is `requestAnimationFrame` and when should you use it over `setTimeout`?**

`requestAnimationFrame(cb)` schedules `cb` to run once before the browser's next repaint, synchronized to the display refresh rate (usually 60fps = ~16.7ms). Benefits: (1) never runs when the tab is hidden — saves CPU/battery; (2) synchronized to the display — no tearing or wasted frames; (3) the browser can combine it with other visual work in the same frame.

`setTimeout(fn, 0)` can fire at any time — it may split across frames (visual stutter) or run during a layout phase. Use `requestAnimationFrame` for: all visual animations, DOM batch writes after reading layout properties, scroll-based updates. Use `setTimeout` for non-visual deferred work.

---

**15. What is the `will-change` property and what are the risks of overusing it?**

`will-change` hints to the browser that an element will be animated, prompting it to promote the element to its own compositor layer *before* the animation starts (avoiding the cost of promotion during animation). For animations triggered on hover or via JS, this removes the jank of the first frame.

Risk: each composited layer consumes GPU memory. Using `will-change: transform` on hundreds of elements simultaneously can exhaust GPU memory, causing the browser to de-promote layers — worse than not using it at all. Apply it only to elements that will *actually* animate, and remove it after the animation ends:

```ts
el.addEventListener('mouseenter', () => { el.style.willChange = 'transform'; });
el.addEventListener('animationend', () => { el.style.willChange = 'auto'; });
```

---

## Typical follow-ups (Group 3)

```txt
"What is paint flashing in DevTools and how do you enable it?" →
  DevTools → Rendering panel → 'Paint flashing' checkbox. Areas
  that are repainted in each frame flash green. Useful for
  identifying components that repaint on scroll (should be zero
  for a smooth scroll experience). If the entire page flashes on
  scroll, something is causing a global repaint — often a fixed-
  position element with a box-shadow or non-composited animation.

"What is stacking context and why does it matter for performance?" →
  A stacking context is a 3D space for z-index compositing.
  Created by: position + z-index, opacity < 1, transform,
  will-change, filter. Each stacking context is painted as a
  unit. Too many nested stacking contexts prevent the browser
  from optimizing layer merging. Unexpected stacking contexts
  explain "why does this element appear above everything else?"

"When does CSS animation outperform JS animation?" →
  CSS animations on compositor-only properties (transform, opacity)
  run on the compositor thread — the JS thread being blocked
  (long task) doesn't drop their frames. JS animations via
  requestAnimationFrame run on the main thread — a long task
  drops both the animation and the frame. For fire-and-forget
  animations on transform/opacity: CSS is safer. For complex
  physics or interactive animations: JS + requestAnimationFrame.
```

---

## Group 4: Caching Strategies

**16. Explain the difference between `Cache-Control: max-age`, `no-cache`, and `no-store`.**

**`max-age=N`:** cache the response for N seconds. Browser serves from cache without hitting the server. Used for versioned static assets (`bundle.abc123.js`).

**`no-cache`:** *always* revalidate with the server before using the cached copy. The browser sends a conditional request (`If-None-Match` / `If-Modified-Since`). The server can respond 304 Not Modified (no body sent) — fast, but still a round trip. Despite the name, `no-cache` *does* cache.

**`no-store`:** never store the response in any cache. Every request fetches fresh from the server. Used for sensitive data (banking session pages, personal health data).

```txt
Static assets with content hash:  Cache-Control: max-age=31536000, immutable
HTML pages (must always revalidate): Cache-Control: no-cache
Sensitive data:                     Cache-Control: no-store
API responses (cache 1 min):       Cache-Control: max-age=60, s-maxage=300
```

---

**17. What is ETags and how does cache revalidation work?**

ETag is a server-generated token (hash of the content). Flow: (1) first request — server sends `ETag: "abc123"` in response; (2) browser stores the response with its ETag; (3) next request (after max-age expires) — browser sends `If-None-Match: "abc123"`; (4) server compares ETag with current content: if unchanged → `304 Not Modified` (no body, saves bandwidth); if changed → `200` with new content and new ETag.

`Last-Modified` / `If-Modified-Since` is the older alternative using timestamps instead of content hashes. ETags are more reliable (timestamp precision, clock drift on multi-server setups).

---

**18. What is a Service Worker and how does it enable offline-first experiences?**

A Service Worker is a JavaScript file that runs in a background thread (separate from the page), intercepting network requests via the `fetch` event. It can: cache responses in the Cache API, serve cached content when offline, implement stale-while-revalidate strategies, and push notifications.

```ts
// service-worker.ts
const CACHE_NAME = 'v1';
const PRECACHE = ['/shell.html', '/app.js', '/styles.css'];

self.addEventListener('install', (event: ExtendableEvent) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE))
  );
});

self.addEventListener('fetch', (event: FetchEvent) => {
  event.respondWith(
    caches.match(event.request).then(cached => {
      // Stale-while-revalidate: serve cache immediately, update in background
      const networkFetch = fetch(event.request).then(response => {
        caches.open(CACHE_NAME).then(c => c.put(event.request, response.clone()));
        return response;
      });
      return cached ?? networkFetch;
    })
  );
});
```

---

**19. What is stale-while-revalidate and when is it appropriate vs inappropriate?**

Stale-while-revalidate (SWR): serve the cached (stale) response immediately, while fetching a fresh version in the background for the next request. Zero-latency for the user; always eventually consistent.

```
Cache-Control: max-age=60, stale-while-revalidate=3600
```
Means: serve from cache for 60s (fresh); after 60s serve stale and revalidate in background; after 3660s must revalidate synchronously.

**Appropriate:** content that changes but not critically — blog posts, product listings, dashboard data. Small staleness is acceptable.

**Inappropriate:** user-specific real-time data (account balance, cart state), form submissions, authentication state. Serving stale personal data to the wrong session is a bug or security issue.

---

## Typical follow-ups (Group 4)

```txt
"What is the difference between the browser cache and the Service Worker cache?" →
  Browser cache (HTTP cache): automatic, controlled by Cache-Control
  headers, managed by the browser. You can't programmatically decide
  to serve stale on network failure.
  Service Worker cache (Cache API): programmatic, fully in your control.
  You decide exactly what to cache, when to update, and what to serve
  when offline. Service Worker can intercept requests the HTTP cache
  would never see (cross-origin failures, timeout fallbacks).

"A user reports they're not seeing their latest data after you
deployed. No hard refresh. Why?" →
  A stale cache entry with a long max-age is serving the old asset.
  Solutions: (1) content-based hashing in filenames — the URL changes
  on deploy, busting the cache; (2) for HTML: max-age=0 or no-cache
  so the entry point always revalidates; (3) Service Worker with
  skipWaiting() + clients.claim() to activate immediately on update.

"What is CDN cache vs browser cache?" →
  Browser cache: per-user, on their device. Cache-Control governs both.
  CDN cache: shared across users, on the edge server. s-maxage overrides
  max-age for CDN only. Vary: header tells the CDN to maintain separate
  cache entries per header value (e.g., Vary: Accept-Encoding).
```

---

## Group 5: JavaScript Performance

**20. What is a long task and how does it affect INP?**

A long task is any JavaScript execution on the main thread that takes more than 50ms. During a long task, the browser cannot process user input — clicks and key presses are queued. When the long task finishes, the browser processes the input (possibly many at once) and paints the next frame. INP measures this delay. A 200ms long task after a button click = an INP of ~200ms.

DevTools diagnosis: Performance panel → Long Tasks are shown as red triangles. `PerformanceObserver` for programmatic monitoring:

```ts
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.duration > 50) {
      console.warn('Long task:', entry.duration, entry.attribution);
    }
  }
});
observer.observe({ type: 'longtask', buffered: true });
```

---

**21. What is code splitting and how does it reduce initial load time?**

Code splitting delays loading JavaScript that is not needed for the initial view. Without splitting, the browser downloads, parses, and executes the entire bundle before the page is interactive — even code for routes the user hasn't visited.

```tsx
// Without code splitting: CheckoutPage.js included in main bundle
import CheckoutPage from './CheckoutPage';

// With React.lazy + Suspense: CheckoutPage loaded only when navigated to
const CheckoutPage = React.lazy(() => import('./CheckoutPage'));

function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/checkout" element={<CheckoutPage />} />
      </Routes>
    </Suspense>
  );
}
```

Next.js does route-based code splitting automatically. The impact: reducing the initial JS bundle from 500KB to 150KB can cut Time to Interactive by 2-3 seconds on a slow device.

---

**22. What is tree shaking and what prevents it from working?**

Tree shaking is the bundler's elimination of unused exports from ES modules. It relies on static analysis of `import`/`export` statements — the bundler can determine at build time which exports are never imported.

**What prevents tree shaking:**
1. CommonJS (`require`) — dynamic, can't be statically analyzed
2. Side-effectful imports: `import 'polyfill'` — bundler can't know if it's safe to remove
3. Missing `"sideEffects": false` in `package.json` — bundler assumes all files have side effects
4. Re-exporting everything: `export * from './utils'` — prevents individual tree shaking
5. Dynamic imports with variable paths: `import(variable)` — bundler can't know which modules are used

---

**23. What is the difference between `debounce` and `throttle` and when to use each?**

**Debounce:** delays execution until N milliseconds after the *last* call. The function only fires after the user has *stopped* triggering events.

**Throttle:** guarantees the function fires at most once per N milliseconds, regardless of how many times it's called.

```ts
// Debounce: search input — wait until user stops typing
const debouncedSearch = debounce((query: string) => {
  fetchResults(query);
}, 300); // fires 300ms after last keystroke

// Throttle: scroll handler — cap updates at 60fps
const throttledScroll = throttle(() => {
  updateScrollProgress();
}, 16); // fires at most once per 16ms (~60fps)
```

Rule: **debounce** for expensive operations triggered by the *end* of user activity (search, form validation, resize). **Throttle** for operations that should keep running *during* user activity but not overwhelm the browser (scroll progress, mouse position tracking, canvas drawing).

---

## Typical follow-ups (Group 5)

```txt
"You added React.lazy() everywhere and INP got worse. Why?" →
  Lazy loading triggers a network request + parse + execute on
  first navigation to that route. If the user clicks a button
  that triggers a lazy load, the click handler is blocked
  waiting for the bundle — high INP. Fix: prefetch likely-next
  routes on idle (import(/* webpackPrefetch: true */ './Page'))
  so the bundle is in cache before the user navigates.

"What is the scheduler API and how does it improve INP?" →
  scheduler.postTask() lets you schedule work at priorities:
  'user-blocking' (input handling), 'user-visible' (rendering),
  'background' (analytics, non-critical). Work can yield to higher-
  priority tasks mid-execution. This breaks long tasks into smaller
  chunks without manually inserting setTimeout(0) yields.
  Available in Chrome 94+; polyfillable via MessageChannel.

"How do you identify what's causing a long task?" →
  DevTools Performance panel: record interaction → find long task
  (red triangle) → expand call stack → identify the hot function.
  Or use the LoAF (Long Animation Frame) API (Chrome 116+):
  it reports not just duration but the full attribution — which
  scripts contributed, which event handlers ran.
```

---

## Group 6: Profiling and Measurement

**24. Describe your DevTools workflow for diagnosing a slow page interaction.**

Step-by-step:

1. **Open DevTools → Performance panel.** Set CPU throttle to 4x or 6x (simulates a mid-range Android).

2. **Click "Record", perform the interaction** (the button click, the dropdown open, etc.), stop recording.

3. **Find the interaction in the timeline.** Look for a red rectangle (long task) or check the "Interactions" track. The bar shows start-to-paint duration.

4. **Expand the call stack** under the long task. The widest bar at the bottom is the actual bottleneck — a React re-render, a sort, a deep clone, a synchronous XHR.

5. **Check "Layout" and "Paint" events.** If layout takes >20ms, find what triggered it (style recalculation → layout shift → forced synchronous layout).

6. **Use the "Bottom-Up" tab** to sort by total time — surfaces the actual hot function, not the initiator.

7. **Fix, re-record, compare.** Measure before and after to verify the fix actually helped.

---

**25. What is the `web-vitals` library and how do you use it to send CWV to analytics?**

The `web-vitals` library is Google's official JS library that measures CWV with the same logic Chrome uses for CrUX. It reports field data (real user measurements), not synthetic lab data.

```ts
import { onCLS, onINP, onLCP, onFCP, onTTFB } from 'web-vitals';

function sendToAnalytics({ name, value, rating, id }: Metric) {
  // rating: 'good' | 'needs-improvement' | 'poor'
  navigator.sendBeacon('/analytics', JSON.stringify({
    metric: name,
    value: Math.round(name === 'CLS' ? value * 1000 : value),
    rating,
    id,   // unique per page visit, for deduplication
    url: location.href,
    userAgent: navigator.userAgent,
  }));
}

onCLS(sendToAnalytics);
onINP(sendToAnalytics);
onLCP(sendToAnalytics);
onFCP(sendToAnalytics);
onTTFB(sendToAnalytics);
```

Key detail: `onCLS` and `onINP` report the *final* value at page unload (or when the page goes to background). Call them once per page visit — they accumulate. Use `id` to deduplicate if the same visit sends multiple reports.

---

## Typical follow-ups (Group 6)

```txt
"What is the difference between lab data and field data?" →
  Lab data: synthetic, controlled environment — Lighthouse, WebPageTest,
  DevTools. Fast to run, reproducible, useful for development.
  Does not reflect real user conditions (device spread, network variance,
  cold vs warm cache, extensions). Field data: from real users — CrUX,
  web-vitals library. Reflects actual experience. Slower to collect,
  not reproducible, but what Google uses for ranking and what users feel.
  Senior answer: always collect both; use lab to find issues, field to
  confirm impact and verify fixes.

"How do you measure performance in CI/CD so regressions are caught?" →
  Run Lighthouse CI on every PR: lhci autorun. Set budget thresholds
  (LCP < 2.5s, bundle size < 200KB). Fail the PR if thresholds are
  exceeded. Use a fixed test URL and warm server to reduce variance.
  Also: bundlesize or size-limit packages to catch JS size regressions
  independent of Lighthouse.

"A React app's INP is 800ms. What is your first hypothesis?" →
  Heavy re-render on interaction. React re-renders a large subtree
  on state change — the time between input and next paint includes
  all that re-render work. Diagnosis: React DevTools Profiler →
  record the interaction → find components that rendered unnecessarily.
  Fix: React.memo, useMemo, useCallback on stable references,
  or move state down to leaf components to reduce re-render scope.
```
