# Performance Metrics: TTFB, FCP, TTI, TBT

## Diagnostic metrics vs. user-experience metrics

Core Web Vitals (LCP, CLS, INP) answer the question **"how does the page feel to the user?"** TTFB, FCP, TTI, and TBT are **diagnostic metrics**: they answer **"why"** LCP is bad, **"why"** the page feels slow.

```txt
Typical optimization workflow:

  Lighthouse → "LCP 5.2s — poor"
                        ↓
  Look at diagnostics:
    TTFB = 2.1s → slow server
    FCP = 2.8s  → waiting on TTFB + render-blocking resources
    TBT = 850ms → heavy JS after load
    TTI = 6.3s  → page not interactive because of TBT
                        ↓
  Priority: fix TTFB first (most expensive),
  then render-blocking, then JS bundle

Without these metrics you know *what* is slow.
With them — you know *where to dig*.
```

## TTFB — Time to First Byte

### What exactly is measured

TTFB is the time from the start of navigation (URL entered / link clicked) to receiving the **first byte of the HTTP response body** from the server.

```txt
What goes into TTFB:

  [Redirect time]
  + [DNS lookup]
  + [TCP connection]
  + [TLS handshake]
  + [Request time]          ← time for the request to reach the server
  + [Server processing]     ← the most "controllable" part: page
  + [Response start]          rendering, DB queries, etc.
  ________________________
  = TTFB

  Breakdown visible in:
  DevTools → Network → click the document → Timing tab
```

```txt
✅ Good:              < 800 ms
⚠️  Needs improvement: 800 ms — 1800 ms
❌ Poor:              > 1800 ms

Important nuance: Lighthouse measures TTFB for the first
HTML document. TTFB for API requests is a separate story
(no redirect/DNS overhead on a keep-alive connection).
```

### Main causes of poor TTFB

```txt
1. No CDN → a user in Tokyo gets a response from a server
   in Virginia: ~150ms just for RTT × 2–3 for TLS handshake
   = 300–450ms before any server processing

2. Slow server processing:
   - ORM generates N+1 queries to the DB
   - No result caching (Redis / in-memory)
   - Cold starts on serverless functions (Lambda, Vercel Edge)

3. Redirects: HTTP → HTTPS → www → 3 additional RTTs
   before the browser receives real content

4. No HTTP/2 → multiple parallel resources each need
   their own TCP connection (head-of-line blocking)
```

### Optimizing TTFB

```ts
// ❌ SSR without caching — every request re-renders the page
export async function getServerSideProps() {
  const posts = await db.post.findMany({ take: 10 });
  return { props: { posts } };
}

// ✅ stale-while-revalidate via headers —
// CDN serves cached response, revalidates in the background
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
// ✅ Streaming SSR (React 18) — first byte of HTML arrives
// immediately, content streams as it becomes ready
// (Next.js App Router does this automatically)
import { Suspense } from 'react';

export default function Page() {
  return (
    <>
      <Header />           {/* sent immediately */}
      <Suspense fallback={<Skeleton />}>
        <SlowComponent />  {/* streams when ready */}
      </Suspense>
    </>
  );
}
```

```ts
// ✅ Application-level caching (Redis)
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
DevTools diagnosis for TTFB:

  Network tab → click the main HTML document → Timing:
    "Waiting for server response" = server processing time
    "Initial connection" + "SSL" = network overhead

  If "Waiting" > 500ms — the problem is server-side
  If "Initial connection" > 200ms — no CDN or keep-alive
```

## FCP — First Contentful Paint

### What exactly is measured

FCP records the moment when the browser renders **any** content from the DOM: text, an image, SVG, canvas — anything that isn't a blank white screen.

```txt
FCP ≠ LCP:
  FCP — "something, anything appeared on screen"
  LCP — "the most important content has rendered"

  Example: a loading spinner can be the FCP,
  while the actual content appears later — that will be the LCP.

  FCP is useful for diagnosis: if FCP is fast but LCP is slow,
  the problem is with loading the specific LCP resource
  (image/font), not with the overall HTML delivery speed.
```

```txt
✅ Good:              < 1.8 s
⚠️  Needs improvement: 1.8 — 3.0 s
❌ Poor:              > 3.0 s
```

### What blocks FCP — render-blocking resources

The browser **paints nothing** until all CSS and synchronous `<script>` tags in `<head>` have loaded and been processed.

```html
<!-- ❌ External CSS in <head> — completely blocks rendering
     until downloaded (even if those styles are footer-only) -->
<head>
  <link rel="stylesheet" href="https://cdn.example.com/styles.css" />
  <script src="/analytics.js"></script>  <!-- also blocks -->
</head>
```

```html
<!-- ✅ Critical CSS inline + defer for the rest -->
<head>
  <style>
    /* Only above-the-fold styles — inlined */
    header { background: #fff; }
    .hero { min-height: 100vh; }
  </style>

  <!-- defer: JS runs after HTML parsing, doesn't block FCP -->
  <script defer src="/main.js"></script>

  <!-- async: independent script, doesn't block HTML parsing -->
  <script async src="/analytics.js"></script>

  <!-- Non-critical CSS — loaded asynchronously -->
  <link
    rel="preload"
    as="style"
    href="/non-critical.css"
    onload="this.rel='stylesheet'"
  />
</head>
```

```ts
// Measuring FCP in the field (real users)
import { onFCP } from 'web-vitals';

onFCP((metric) => {
  // metric.value in milliseconds
  sendToAnalytics({ name: 'FCP', value: metric.value });
});
```

```txt
Key FCP diagnostics in Lighthouse:
  → "Eliminate render-blocking resources" — the main audit
  → shows specific URLs and how many ms each costs
  → "Minify CSS" / "Remove unused CSS" — also relevant
     (large CSS downloads and parses more slowly)
```

### FCP and Server-Side Rendering

```txt
FCP across different rendering strategies:

  CSR (Create React App):
    TTFB → FCP: received empty HTML + bundle.js
    FCP → LCP: JS executed, React rendered the DOM
    ↳ FCP = blank screen or minimal skeleton
      LONG gap between FCP and LCP

  SSR (Next.js getServerSideProps):
    TTFB → FCP: received ready-to-render HTML
    ↳ FCP already shows real content
    ↳ But TTFB may be higher (server rendering cost)

  SSG (Static Site Generation):
    TTFB → FCP: HTML pre-built, CDN serves it instantly
    ↳ Optimal TTFB AND FCP
    ↳ Trade-off: no personalization without hydration
```

## TTI — Time to Interactive

### What "interactive" means technically

TTI is the point after which the page **reliably responds to interactions within 50ms**. Lighthouse's algorithm:

```txt
TTI algorithm (simplified):

  1. Find FCP (start of search)
  2. Search for a "quiet window" 5 seconds long:
     - no Long Tasks (tasks > 50ms) on the main thread
     - no more than 2 in-flight network requests
  3. TTI = the beginning of that quiet window
       (i.e. the end of the last Long Task before the 5s window)

  FCP ←——————— TTI
       this period = page is VISIBLE but NOT RESPONSIVE
       (clicks are buffered or ignored)
```

```txt
✅ Good:              < 3.8 s
⚠️  Needs improvement: 3.8 — 7.3 s
❌ Poor:              > 7.3 s

Critical distinction TTI vs FCP:
  The user SEES content (FCP), taps a button —
  nothing happens, because JS is still executing
  (TTI hasn't been reached yet). This is one of the most
  frustrating patterns in mobile web.
```

### What widens the FCP → TTI gap

```ts
// ❌ Monolithic bundle — all application code in one file.
// Even code unused on the current page is parsed
// and compiled by the browser.
import { CheckoutModule } from './checkout';   // not needed on home page
import { AdminPanel } from './admin';          // not needed by most users
import { ReportGenerator } from './reports';   // heavy, rarely used

// ✅ Dynamic import — code loads only when needed
const CheckoutModule = lazy(() => import('./checkout'));
const AdminPanel = lazy(() =>
  import('./admin').then(m => ({ default: m.AdminPanel }))
);

// On button click — loads only then
async function handleCheckoutClick() {
  const { startCheckout } = await import('./checkout');
  startCheckout();
}
```

```txt
Practical rule for TTI:
  Total JS parsed/executed before TTI must be minimal.

  On mobile devices, JS parsing is roughly 3–4× slower
  than desktop (weaker CPU):
  - 100 KB JS on a MacBook Pro = ~50ms
  - 100 KB JS on a mid-range Android = ~150–200ms
  → This directly lengthens Long Tasks and pushes TTI out
```

## TBT — Total Blocking Time

### The formula and what it means

TBT is a lab metric (measured in Lighthouse, not in real-user field data) that sums the **"excess" time** of all Long Tasks between FCP and TTI:

```txt
Long Task = any task on the main thread lasting > 50ms

TBT = sum of (Long Task duration − 50ms)
      for every Long Task between FCP and TTI

Example:
  Long Task 1: 250ms → contribution = 250 − 50 = 200ms
  Long Task 2: 90ms  → contribution =  90 − 50 =  40ms
  Long Task 3: 180ms → contribution = 180 − 50 = 130ms
  ——————————————————————————————————————————————————————
  TBT = 370ms

Why 50ms? That's the threshold at which an interaction
feels immediate (<100ms). The first 50ms of a Long Task
"don't count" — that's acceptable. Everything beyond
is real blocking time.
```

```txt
✅ Good:              < 200 ms
⚠️  Needs improvement: 200 — 600 ms
❌ Poor:              > 600 ms
```

### TBT as a lab proxy for INP

```txt
The TBT ↔ INP relationship:

  INP — FIELD metric (real users)
  TBT — LAB metric (Lighthouse, reproducible)

  The correlation is high, but not 1:1:
    TBT shows the POTENTIAL for a bad INP
    (if there are many Long Tasks, an interaction
    that lands on one will produce a poor INP)

  In practice:
    TBT > 600ms → INP > 500ms is very likely
    TBT < 200ms → INP < 200ms is likely
    But INP can be poor with a good TBT if a specific
    event handler is heavy (TBT is page-wide;
    INP is about specific interactions)
```

### Diagnosing TBT — where to find Long Tasks

```txt
Chrome DevTools → Performance → record page load:

  Main thread track:
    Red rectangles above tasks = Long Tasks
    Click → Bottom-up / Call Tree → see what's taking time

  Typical culprits:
    - JS parsing and compilation (Script Evaluation)
    - React/Vue/Angular hydration
    - Third-party scripts (chat widgets, analytics, A/B tests)
    - Large DOM operations (rendering long lists)
```

```ts
// Detecting Long Tasks programmatically in the browser
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
// ✅ Breaking up heavy initialization to reduce TBT on load
async function initApp() {
  await initRouter();
  await scheduler.yield(); // give the browser a chance to handle events

  await initStore();
  await scheduler.yield();

  await initThirdPartyAnalytics(); // heaviest — deferred to last
}
```

## How the metrics connect — the causality chain

```txt
Navigation starts
        ↓
[TTFB] — server responds
        ↓ HTML received
[FCP]  — browser paints first content
   ↑         ↑
   │         └─ blocked by: render-blocking CSS/JS
   └─────────── depends on: TTFB + network latency
        ↓
[LCP]  — main content painted ← user-facing CWV
   ↑
   └─── depends on: FCP + LCP resource download
        ↓ JS bundles execute, page hydrates
[TBT]  — sum of main thread blocking (lab only)
        ↓
[TTI]  — page is fully interactive
   ↑
   └─── depends on: Long Tasks after FCP

[INP]  — responsiveness of specific interactions ← CWV
   ↑
   └─── correlates with TBT, but measured in real field data
```

## DevTools workflow for diagnosis

```txt
Step 1: Lighthouse audit (tab or CLI)
  → gives all four metrics + CWV
  → points to specific problems (audit items)
  → run in incognito mode (no extensions!)

Step 2: Performance panel for TTFB and Long Tasks
  DevTools → Performance → ⏺ (Ctrl+Shift+E to reload with recording)
  → Timings track: FCP, LCP, TBT markers
  → Network track: any early render-blocker?
  → Main track: where are the Long Tasks?

Step 3: Network tab for TTFB
  Hover over the waterfall bar for the document → Timing breakdown
  "Waiting for server response" = real server time
  Compare to CDN node TTFB: if close to the user and still slow
  → it's the server, not the network

Step 4: Coverage tab
  DevTools → ⋮ → More tools → Coverage → ⏺ → reload
  → shows % of unused JS/CSS during load
  → red bars = code that loaded but wasn't needed
```

## Connection to other topics

```txt
[Core Web Vitals]         — LCP, CLS, INP are user-facing metrics;
                            TTFB/FCP/TBT/TTI are the tools
                            for diagnosing why they're poor
[Resource Loading]        — preload/prefetch and render-blocking
                            directly affect FCP
[JavaScript Performance]  — code splitting reduces TTI and TBT;
                            Long Tasks are the foundation of TBT
[Caching Strategies]      — browser cache and CDN cut TTFB
```

## Common interview traps

- **"TTFB is page load time"** — no. TTFB ends at the first byte of the response. Loading all resources is the Load Event — a completely different metric.

- **"FCP and LCP are the same thing"** — FCP records any first content (including a spinner); LCP records the largest meaningful element. A page can have an excellent FCP and a poor LCP.

- **"TTI is when the page has loaded"** — TTI is defined by a 5-second quiet window free of Long Tasks, not by the Load event. A page can be "loaded" (all resources downloaded) while TTI hasn't been reached because JS is still executing.

- **"TBT can be measured in real-user field data"** — no. TBT is a lab metric (Lighthouse). In the field, INP is used. Confusing them signals shallow knowledge.

- **Not knowing the thresholds** — interviews often ask "what counts as good TTFB?" TTFB: <800ms; FCP: <1.8s; TTI: <3.8s; TBT: <200ms. Memorizing exact numbers matters less than knowing the order of magnitude.

- **"I added defer to all scripts — FCP is good now"** — `defer` helps FCP, but if the CSS itself is large or unoptimized, FCP will still be slow. You need to look at the whole picture: TTFB → render-blocking → critical CSS size.

- **Ignoring the mobile/desktop difference** — Lighthouse by default simulates a mobile device (4x CPU slowdown, slow network). TTI and TBT on mobile can be 3–5× worse than on desktop. Saying "our TTI is good" without specifying the device is an incomplete answer.
