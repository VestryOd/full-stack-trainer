# Web Performance — Interview Questions (Middle → Senior)

## How to use this cheat sheet

Each answer compresses the depth from the topic articles. Performance interviews at senior level always go one step deeper. Expect three questions after every answer: how would you measure that, what is the trade-off, and show me the DevTools workflow. Each group here ends with **"Typical follow-ups"**, showing where the conversation usually goes.

---

## Group 1: Core Web Vitals

**1. What are the three Core Web Vitals and what exactly does each measure?**

**LCP (Largest Contentful Paint):** the render time of the largest visible element in the viewport (usually a hero image or `<h1>`). Measures *loading performance*. Good: ≤ 2.5s.

**CLS (Cumulative Layout Shift):** the sum of all unexpected layout shifts during the page's lifetime, weighted by impact fraction × distance fraction. Measures *visual stability*. Good: ≤ 0.1.

**INP (Interaction to Next Paint):** how long the page takes to answer a user action. It is measured from the input — a click, a tap, a keypress — to the next frame painted. One page visit reports one value. For most pages that value is the slowest interaction of the visit. On pages with very many interactions, one highest interaction is ignored for every 50, so a single outlier cannot define the score.

INP replaced FID (First Input Delay) in March 2024 and measures *responsiveness*. Good: ≤ 200 ms. That threshold is judged at the 75th percentile of page loads in field data. It is not a percentile over the interactions inside one visit.

---

**2. Why did Google replace FID with INP, and what does INP reveal that FID didn't?**

FID measured only the *delay before the browser could start processing* the first interaction. Processing time and paint were left out. A handler that blocked the main thread for 800 ms after starting would report FID = 5 ms, and still feel completely unresponsive.

INP watches *all* interactions of the visit, not just the first one, and measures the *full duration* from input to next frame. It then reports the worst of them as the value for that visit. A page with slow `onClick` handlers on dynamically loaded content would score fine on FID but fail INP.

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

**Web fonts causing FOUT (flash of unstyled text) or FOIT (flash of invisible text):** the fallback font has different metrics. The text reflows the moment the custom font loads. Fix: `font-display: optional` (never reflows, may show fallback permanently) or `font-display: swap` + `size-adjust` / `ascent-override` to match fallback metrics.

---

**4. What is LCP and what are the four elements that can be the LCP element?**

LCP is the render timestamp of the largest *contentful* element visible in the viewport when the user first views the page. Four element types are eligible:

- `<img>`.
- `<image>` inside an SVG (scalable vector graphics) document.
- `<video>`, through its poster image.
- An element with a CSS `background-image`.

Text blocks such as `<p>` or `<h1>` can also be the LCP element if they are the largest. A background image set in CSS is eligible only if it is fetched from a URL, so gradients do not count.

---

**5. Walk through the complete LCP optimization checklist.**

LCP time = network latency + server TTFB (time to first byte) + resource load time + render time. Attack each part:

**1. Reduce TTFB:** put a CDN (content delivery network) in front, cache at the edge, keep the origin server fast. A TTFB above 600 ms is the primary cause of a slow LCP.

**2. Eliminate render-blocking resources:** move non-critical CSS to `<link media="print">` or async load; defer non-critical JS.

**3. Preload the LCP resource:**
```html
<link rel="preload" as="image" href="/hero.webp"
      imagesrcset="/hero-400.webp 400w, /hero-800.webp 800w"
      imagesizes="100vw">
```

**4. Use modern image formats:** WebP (the Web Picture format) is about 30% smaller than JPEG (Joint Photographic Experts Group) at the same visual quality. AVIF (a newer image format from the Alliance for Open Media) is about 50% smaller still.

**5. Do not lazy-load the LCP image:** `loading="lazy"` on the hero image delays LCP by the scroll-observation delay. Use `fetchpriority="high"` instead.

**6. Avoid client-side rendering for the LCP element:** if JavaScript injects the LCP element, the browser must download, parse and execute that JS first. Only then can it paint. Server-side rendering (SSR) or static site generation (SSG) puts the element straight into the initial HTML.

---

## Typical follow-ups (Group 1)

**"How do you measure Core Web Vitals in production, not just in DevTools?"**

Use field data, which means measurements taken from real users. Three sources are common:

- The Chrome User Experience Report (CrUX) through PageSpeed Insights.
- The Core Web Vitals report in Search Console.
- The `web-vitals` JS library, sending values to your own analytics.

Lab data from Lighthouse and DevTools is synthetic. It does not capture real user conditions: slow Android devices, 3G networks, background tabs. Field data is what Google uses for ranking.

**"A page passes Lighthouse but fails Core Web Vitals in Search Console — why?"**

Lighthouse is lab data measured on one simulated device. CrUX is field data from real Chrome users, reported at the 75th percentile. Real users have slower devices, cache misses, background tabs, and extensions.

There is also a difference in scope. Lighthouse measures a fresh cold load, while the field report includes soft navigations and repeat visits.

**"What is TTFB and how does it relate to LCP?"**

TTFB (Time to First Byte) is the time from the request to the first byte of the response. It is a sub-metric of LCP, because a slow server delays everything downstream. A TTFB above 600 ms will almost certainly push LCP past 2.5 s, even with perfect frontend optimization.

---

## Group 2: Resource Loading

**6. What is the critical rendering path and which resources block it?**

The critical rendering path is the sequence of steps the browser must complete before the first pixel is painted:

```txt
DNS → TCP → TLS → HTTP request → HTML parse →
DOM construction → CSSOM construction →
Render Tree → Layout → Paint
```

**Render-blocking resources** are three:

- CSS files in `<head>`. The browser will not paint until the CSSOM is built.
- Synchronous `<script>` tags without `defer` or `async`. They pause HTML parsing.
- `@import` inside CSS, which creates additional sequential fetches.

Images, fonts, and async scripts do not block the initial render.

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

The rule of thumb:

- `defer` for scripts that need the DOM (Document Object Model, the browser's live tree of page nodes).
- `async` for independent scripts such as analytics and ads, where order does not matter.
- `type="module"` for ESM (ECMAScript modules) bundles, which are deferred automatically.

---

**8. What does `rel="preload"` do and when should you use it vs `rel="prefetch"`?**

The `preload` hint tells the browser: you will need this resource soon, start fetching it now, at high priority. Use it for resources the browser discovers late in the page load. Typical cases are a hero image referenced from CSS, a font used in above-fold content, and a critical script. Preload does not execute the resource — it only fetches and caches it.

The `prefetch` hint tells the browser something weaker: the user might navigate to a page that needs this. It is a low-priority background fetch, stored in the HTTP cache, and it is meant for next-page navigation resources.

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

Four fixes, in the order you usually reach for them:

- Resource hints (`preconnect`, `preload`) to start the fetches earlier.
- Colocating the API calls on the server, the backend-for-frontend (BFF) pattern.
- HTTP/2 or HTTP/3 multiplexing, so several requests share one connection.
- Inlining the critical CSS, which removes a separate CSS fetch from the critical path.

---

**10. What is HTTP/2 multiplexing and what performance problem does it solve?**

HTTP/1.1 allows only one active request per TCP (transmission control protocol) connection. Browsers compensate by opening six connections per domain, but each one pays the cost of TCP slow start. HTTP/2 sends multiple streams over a single connection at the same time, with no head-of-line blocking at the HTTP layer.

Two older habits lose their point because of that. Domain sharding — splitting resources across `static1.cdn.com` and `static2.cdn.com` just to open more connections — becomes an anti-pattern. Bundling everything into one giant file becomes less necessary, because many small files are fine on HTTP/2.

HTTP/3 goes further and removes head-of-line blocking at the connection level too. It does so by running over QUIC, a transport built on top of UDP (user datagram protocol) instead of TCP.

---

## Typical follow-ups (Group 2)

**"When does preloading a font hurt performance?"**

There are two cases. The first is placement. If the font is not used above the fold, `preload` competes for bandwidth with the LCP resources: the hero image and the critical CSS. The second case is size. A variable font file can weigh 500 kilobytes or more, and preloading all of it for a handful of characters wastes that bandwidth.

Better: preload only the subset used above the fold, and cut the file down with a subsetting tool such as `pyftsubset` or Fonttools.

**"What is the priority order of resource hints?"**

The order is `preconnect`, then `preload`, then `prefetch`, then `dns-prefetch`. Note that `preconnect` opens the whole TCP and TLS (transport layer security) connection, not just the DNS (domain name system) lookup. Use it for two or three critical origins only, because each kept-alive connection consumes browser resources.

**"Lighthouse says 'eliminate render-blocking resources', but the CSS is already in `<head>`. What do you do?"**

Split the CSS. Extract the above-the-fold styles and inline them in a `<style>` tag inside `<head>`. Load the rest with `<link media="print">`, which the browser fetches without blocking, then switch it to `media="all"` in the `onload` handler.

The other option is a CSS-in-JS solution that extracts the critical CSS per component automatically. Next.js does this out of the box.

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

Four points to take from the diagram:

- JS blocks DOM construction the moment the parser meets it, unless the tag carries `defer` or `async`.
- CSS blocks rendering, because the CSSOM must be built before the Render Tree.
- Layout and Paint are expensive. Avoid triggering them inside loops.
- Composite is the cheapest stage. Only properties living on GPU (graphics processing unit) layers, `transform` and `opacity`, can animate without Layout and Paint.

---

**12. What is layout thrashing and how do you fix it?**

Layout thrashing is also called forced synchronous layout. Reading a layout property such as `offsetHeight` or `getBoundingClientRect()` forces the browser to flush pending style changes. It must then recalculate layout synchronously, before the next frame. Writing a style afterwards forces yet another layout on the next read. In a loop this costs N layout recalculations per frame instead of one.

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

Rule: animate `transform: translateX()` instead of `left`, `transform: scaleX()` instead of `width`. The GPU handles `transform` and `opacity` natively, while Layout and Paint run on the CPU (central processing unit).

---

**14. What is `requestAnimationFrame` and when should you use it over `setTimeout`?**

The `requestAnimationFrame(cb)` call schedules `cb` to run once before the browser's next repaint. It is synchronized to the display refresh rate, usually 60 frames per second, or about every 16.7 ms. Three benefits follow from that:

- It never runs while the tab is hidden, which saves battery and processor time.
- It is synchronized to the display, so there is no tearing and no wasted frame.
- The browser can combine it with other visual work in the same frame.

`setTimeout(fn, 0)` can fire at any time — it may split across frames (visual stutter) or run during a layout phase. Use `requestAnimationFrame` for: all visual animations, DOM batch writes after reading layout properties, scroll-based updates. Use `setTimeout` for non-visual deferred work.

---

**15. What is the `will-change` property and what are the risks of overusing it?**

The `will-change` property hints to the browser that an element is about to be animated. The browser then promotes that element to its own compositor layer *before* the animation starts, so promotion does not cost anything mid-animation. For animations triggered on hover or from JS, this removes the jank of the first frame.

Risk: each composited layer consumes GPU memory. Using `will-change: transform` on hundreds of elements simultaneously can exhaust GPU memory, causing the browser to de-promote layers — worse than not using it at all. Apply it only to elements that will *actually* animate, and remove it after the animation ends:

```ts
el.addEventListener('mouseenter', () => { el.style.willChange = 'transform'; });
el.addEventListener('animationend', () => { el.style.willChange = 'auto'; });
```

---

## Typical follow-ups (Group 3)

**"What is paint flashing in DevTools and how do you enable it?"**

Open DevTools, go to the Rendering panel, and tick the 'Paint flashing' checkbox. Areas that are repainted in each frame flash green. This is how you find components that repaint on scroll, and for a smooth scroll that count should be zero.

If the whole page flashes on scroll, something is forcing a global repaint. Usually it is a fixed-position element with a `box-shadow`, or an animation that was never composited.

**"What is a stacking context and why does it matter for performance?"**

A stacking context is a 3D space in which `z-index` compositing happens. It is created by `position` together with `z-index`, by `opacity` below 1, and by `transform`, `will-change` or `filter`.

Each stacking context is painted as a single unit. Too many nested contexts prevent the browser from optimizing layer merging. Unexpected contexts also explain the classic puzzle: why does this element appear above everything else?

**"When does a CSS animation outperform a JS animation?"**

CSS animations on compositor-only properties (`transform`, `opacity`) run on the compositor thread. A blocked JS thread — a long task — does not drop their frames. JS animations driven by `requestAnimationFrame` run on the main thread, so a long task drops both the animation and the frame.

For fire-and-forget animations on `transform` or `opacity`, CSS is safer. For complex physics or interactive animations, use JS with `requestAnimationFrame`.

---

## Group 4: Caching Strategies

**16. Explain the difference between `Cache-Control: max-age`, `no-cache`, and `no-store`.**

**`max-age=N`:** cache the response for N seconds. Browser serves from cache without hitting the server. Used for versioned static assets (`bundle.abc123.js`).

**`no-cache`:** *always* revalidate with the server before using the cached copy. The browser sends a conditional request (`If-None-Match` / `If-Modified-Since`). The server can respond 304 Not Modified (no body sent) — fast, but still a round trip. Despite the name, `no-cache` *does* cache.

**`no-store`:** never store the response in any cache. Every request fetches fresh from the server. Used for sensitive data (banking session pages, personal health data).

| Kind of response | `Cache-Control` value |
|---|---|
| Static asset with a content hash | `max-age=31536000, immutable` |
| HTML page (must always revalidate) | `no-cache` |
| Sensitive data | `no-store` |
| API response cached for a minute | `max-age=60, s-maxage=300` |

---

**17. What is ETags and how does cache revalidation work?**

An ETag is a server-generated token, normally a hash of the content. The flow has four steps:

1. On the first request the server sends `ETag: "abc123"` in the response.
2. The browser stores the response together with its ETag.
3. On the next request, once `max-age` has expired, the browser sends `If-None-Match: "abc123"`.
4. The server compares that ETag with the current content. If nothing changed it answers `304 Not Modified` with no body, which saves bandwidth. If the content changed it answers `200` with the new content and a new ETag.

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

```txt
Cache-Control: max-age=60, stale-while-revalidate=3600
```

That header means three things. Serve from cache for the first 60 seconds, while the response is still fresh. After those 60 seconds, serve the stale copy and revalidate in the background. After 3660 seconds in total, revalidation becomes synchronous.

**Appropriate:** content that changes but not critically — blog posts, product listings, dashboard data. Small staleness is acceptable.

**Inappropriate:** user-specific real-time data (account balance, cart state), form submissions, authentication state. Serving stale personal data to the wrong session is a bug or security issue.

---

## Typical follow-ups (Group 4)

**"What is the difference between the browser cache and the Service Worker cache?"**

The browser cache, also called the HTTP cache, is automatic. It is controlled by `Cache-Control` headers and managed by the browser. You cannot programmatically decide to serve a stale copy when the network fails.

The Service Worker cache, reached through the Cache API, is programmatic and fully under your control. You decide exactly what to cache, when to update it, and what to serve when the user is offline. A Service Worker can also intercept requests the HTTP cache would never see, such as cross-origin failures and timeout fallbacks.

**"A user is not seeing their latest data after a deploy, without a hard refresh. Why?"**

A stale cache entry with a long `max-age` is still serving the old asset. Three solutions:

- Content-based hashing in filenames. The URL changes on deploy, so the stale entry is never requested again.
- For HTML: `max-age=0` or `no-cache`, so the entry point always revalidates.
- A Service Worker that calls `skipWaiting()` and `clients.claim()` to activate immediately on update.

**"What is the difference between a CDN cache and a browser cache?"**

The browser cache is per-user and lives on their device. The CDN cache is shared across users and lives on the edge server. `Cache-Control` governs both, but `s-maxage` overrides `max-age` for the CDN only. The `Vary` header tells the CDN to keep separate cache entries per header value, for example `Vary: Accept-Encoding`.

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

Tree shaking is the bundler's elimination of unused exports from ECMAScript modules. It relies on static analysis of `import`/`export` statements — the bundler can determine at build time which exports are never imported.

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

**"You added `React.lazy()` everywhere and INP got worse. Why?"**

Lazy loading triggers a network request, then a parse, then an execute, on the first navigation to that route. If the user clicks a button that triggers a lazy load, the click handler sits blocked waiting for the bundle, and INP goes up.

The fix is to prefetch the likely next routes while the browser is idle, with `import(/* webpackPrefetch: true */ './Page')`. Then the bundle is already in cache by the time the user navigates.

**"What is the scheduler API and how does it improve INP?"**

The `scheduler.postTask()` call lets you schedule work at an explicit priority. There are three: `user-blocking` for input handling, `user-visible` for rendering, and `background` for analytics and other non-critical work.

Work can yield to higher-priority tasks mid-execution. That breaks long tasks into smaller chunks without manually inserting `setTimeout(0)` yields. It is available in Chrome 94 and later, and can be polyfilled with `MessageChannel`.

**"How do you identify what is causing a long task?"**

Record the interaction in the DevTools Performance panel, find the long task (the red triangle), expand its call stack, and identify the hot function.

The other route is the LoAF (Long Animation Frame) API, available from Chrome 116. It reports not just the duration but the full attribution: which scripts contributed, and which event handlers ran.

---

## Group 6: Profiling and Measurement

**24. Describe your DevTools workflow for diagnosing a slow page interaction.**

Step-by-step:

1. **Open DevTools → Performance panel.** Set CPU throttle to 4x or 6x (simulates a mid-range Android).

2. **Click "Record", perform the interaction** (the button click, the dropdown open, etc.), stop recording.

3. **Find the interaction in the timeline.** Look for a red rectangle (long task) or check the "Interactions" track. The bar shows start-to-paint duration.

4. **Expand the call stack** under the long task. The widest bar at the bottom is the actual bottleneck — a React re-render, a sort, a deep clone, a synchronous XHR (XMLHttpRequest) call.

5. **Check "Layout" and "Paint" events.** If layout takes >20ms, find what triggered it (style recalculation → layout shift → forced synchronous layout).

6. **Use the "Bottom-Up" tab** to sort by total time — surfaces the actual hot function, not the initiator.

7. **Fix, re-record, compare.** Measure before and after to verify the fix actually helped.

---

**25. What is the `web-vitals` library and how do you use it to send Core Web Vitals to analytics?**

The `web-vitals` library is Google's official JS library. It measures the Core Web Vitals with the same logic Chrome uses for CrUX. It reports field data (real user measurements), not synthetic lab data.

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

**"What is the difference between lab data and field data?"**

Lab data comes from a synthetic, controlled environment: Lighthouse, WebPageTest, DevTools. It is fast to run, reproducible, and useful during development. It does not reflect real user conditions such as device spread, network variance, cold versus warm cache, and browser extensions.

Field data comes from real users, through CrUX or the `web-vitals` library. It reflects the actual experience. It is slower to collect and not reproducible, but it is what Google ranks on and what users feel.

The senior answer is to collect both: lab data to find issues, field data to confirm impact and verify fixes.

**"How do you measure performance in continuous integration so regressions are caught?"**

Run Lighthouse CI, the continuous integration runner for Lighthouse, on every pull request with `lhci autorun`. Set budget thresholds: LCP under 2.5 s, bundle size under 200 kilobytes. Fail the pull request when a threshold is exceeded. Use a fixed test URL and a warm server to reduce variance.

Add the `bundlesize` or `size-limit` package as well, to catch JS size regressions independently of Lighthouse.

**"A React app has an INP of 800 ms. What is your first hypothesis?"**

A heavy re-render on interaction. React re-renders a large subtree on a state change, and the time between input and next paint includes all of that work.

To diagnose it, open the React DevTools Profiler, record the interaction, and find the components that rendered unnecessarily. The usual fixes are `React.memo`, `useMemo` and `useCallback` on stable references, or moving state down to leaf components to shrink the re-render scope.
