# Performance Metrics: TTFB, FCP, TTI, TBT

## Diagnostic metrics vs. user-experience metrics

This article is about the four **diagnostic metrics**. TTFB (time to first byte) and FCP (first contentful paint) describe how fast something appears. TTI (time to interactive) and TBT (total blocking time) describe how long the page stays unresponsive.

Core Web Vitals answer a different question: how does the page feel to the user? Those three are LCP (largest contentful paint), CLS (cumulative layout shift) and INP (interaction to next paint). The diagnostic four answer the follow-up: *why* does it feel that way. Core Web Vitals tell you the page is slow; TTFB, FCP, TTI and TBT tell you where to dig.

A typical optimization session looks like this. Lighthouse reports an LCP of 5.2 seconds and calls it poor, so you open the diagnostics:

- **TTFB = 2.1 s** — the server is slow.
- **FCP = 2.8 s** — waiting on TTFB plus render-blocking resources.
- **TBT = 850 ms** — heavy JS after load.
- **TTI = 6.3 s** — the page isn't interactive because of TBT.

The order of work follows from those numbers. Fix TTFB first, because it is the most expensive. Then the render-blocking resources, then the JS bundle.

## TTFB — Time to First Byte

### What exactly is measured

TTFB is the time from the start of navigation to the **first byte of the HTTP response body** arriving from the server. Navigation starts when the user enters a URL or clicks a link. That time is a sum of six parts:

- redirect time;
- the DNS (domain name system) lookup;
- opening the TCP (transmission control protocol) connection;
- the TLS (transport layer security) handshake;
- request time, that is how long the request takes to reach the server;
- server processing plus response start — the most "controllable" part, which covers page rendering, database queries and the rest.

The same breakdown is visible in DevTools: Network → click the document → Timing tab.

| Rating | TTFB |
|---|---|
| ✅ Good | under 800 ms |
| ⚠️ Needs improvement | 800 ms — 1800 ms |
| ❌ Poor | over 1800 ms |

One nuance matters here. Lighthouse measures TTFB for the first HTML document. TTFB for API requests is a separate story, because a keep-alive connection carries no redirect or DNS overhead.

### Main causes of poor TTFB

1. **No CDN (content delivery network).** A user in Tokyo gets the response from a server in Virginia. That is about 150 ms of round-trip time alone, times two or three for the TLS handshake — 300–450 ms before any server processing.
2. **Slow server processing.** Common shapes: an ORM (object-relational mapper) generating N+1 queries to the database. No caching of results in Redis or in memory. Cold starts on serverless functions such as Lambda or Vercel Edge.
3. **Redirects.** The chain `HTTP → HTTPS → www` costs three extra round trips before the browser receives real content.
4. **No HTTP/2.** Several parallel resources each need their own TCP connection, and head-of-line blocking sets in.

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

**Diagnosing TTFB in DevTools.** Open the Network tab, click the main HTML document, then go to Timing. The row `Waiting for server response` is the server processing time, while `Initial connection` plus `SSL` is the network overhead. If the waiting row is over 500 ms, the problem is server-side. If the initial connection is over 200 ms, there is no CDN and no keep-alive.

## FCP — First Contentful Paint

### What exactly is measured

FCP records the moment when the browser renders **any** content from the DOM (document object model). Text, an image, an SVG (scalable vector graphics) drawing, a canvas — anything that isn't a blank white screen counts.

FCP is not LCP. FCP means that something, anything, appeared on screen; LCP means that the most important content has rendered. A loading spinner can be the FCP, while the actual content appears later and becomes the LCP.

That gap is what makes FCP useful for diagnosis. If FCP is fast but LCP is slow, the problem is the specific LCP resource: an image or a font. The overall speed of HTML delivery is fine.

| Rating | FCP |
|---|---|
| ✅ Good | under 1.8 s |
| ⚠️ Needs improvement | 1.8 — 3.0 s |
| ❌ Poor | over 3.0 s |

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

Key FCP diagnostics in Lighthouse:

- **Eliminate render-blocking resources** — the main audit. It lists the specific addresses and how many milliseconds each one costs.
- **Minify CSS** and **Remove unused CSS** — also relevant, because a large stylesheet downloads and parses more slowly.

### FCP and Server-Side Rendering

**CSR (client-side rendering), as in Create React App.** Between TTFB and FCP the browser receives an empty HTML document plus `bundle.js`. Between FCP and LCP the JS executes and React renders the DOM. So the FCP is a blank screen or a minimal skeleton, and the gap between FCP and LCP is **long**.

**SSR (server-side rendering), as in `getServerSideProps`.** Between TTFB and FCP the browser receives ready-to-render HTML, so the FCP already shows real content. The trade-off is a higher TTFB, because the server pays the rendering cost.

**SSG (static site generation).** The HTML is pre-built and the CDN serves it instantly, which gives an optimal TTFB **and** FCP. The trade-off is that there is no personalization without hydration.

## TTI — Time to Interactive

### What "interactive" means technically

TTI is the point after which the page **reliably responds to interactions within 50ms**. Lighthouse computes it like this, simplified:

1. Find FCP — that is where the search starts.
2. Look for a "quiet window" five seconds long. Inside it there must be no Long Tasks, that is no tasks over 50 ms on the main thread. There must also be no more than two in-flight network requests.
3. TTI is the beginning of that quiet window, that is the end of the last Long Task before the five-second window.

Between FCP and TTI the page is **visible but not responsive**, and clicks are buffered or ignored.

| Rating | TTI |
|---|---|
| ✅ Good | under 3.8 s |
| ⚠️ Needs improvement | 3.8 — 7.3 s |
| ❌ Poor | over 7.3 s |

The distinction between TTI and FCP is what bites in practice. The user **sees** content, which is FCP, taps a button, and nothing happens, because JS is still executing and TTI hasn't been reached. This is one of the most frustrating patterns on the mobile web.

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

**A practical rule for TTI:** the total amount of JS parsed and executed before TTI must be minimal.

On mobile devices JS parsing is roughly three to four times slower than on desktop, because the CPU (central processing unit) is weaker:

- 100 kilobytes of JS on a MacBook Pro — about 50 ms.
- 100 kilobytes of JS on a mid-range Android phone — about 150–200 ms.

That difference directly lengthens Long Tasks and pushes TTI out.

## TBT — Total Blocking Time

### The formula and what it means

TBT is a lab metric: it is measured in Lighthouse, not in real-user field data. It sums the **"excess" time** of all Long Tasks between FCP and TTI. A Long Task is any task on the main thread lasting longer than 50 ms.

```txt
TBT = sum of (Long Task duration − 50ms)
      for every Long Task between FCP and TTI
```

Worked example with three Long Tasks:

- 250 ms contributes 250 − 50 = 200 ms.
- 90 ms contributes 90 − 50 = 40 ms.
- 180 ms contributes 180 − 50 = 130 ms.

The total is a TBT of 370 ms. Why 50 ms? That is the threshold at which an interaction still feels immediate, under 100 ms. The first 50 ms of a Long Task "don't count" and are acceptable; everything beyond that is real blocking time.

| Rating | TBT |
|---|---|
| ✅ Good | under 200 ms |
| ⚠️ Needs improvement | 200 — 600 ms |
| ❌ Poor | over 600 ms |

### TBT as a lab proxy for INP

INP is a **field** metric, measured on real users. TBT is a **lab** metric, produced by Lighthouse and reproducible on demand. The correlation between them is high, but not one to one. TBT shows the **potential** for a bad INP. If there are many Long Tasks, an interaction that lands on one of them will produce a poor INP.

In practice, TBT above 600 ms makes an INP above 500 ms very likely. TBT below 200 ms makes an INP below 200 ms likely. But INP can be poor with a good TBT, if one specific event handler is heavy. TBT is page-wide, while INP is about specific interactions.

### Diagnosing TBT — where to find Long Tasks

Open Chrome DevTools → Performance and record a page load. In the Main thread track, the red rectangles above tasks are the Long Tasks. Click one and open Bottom-up or Call Tree to see what is taking the time.

Typical causes:

- JS parsing and compilation, shown as Script Evaluation;
- hydration in React, Vue or Angular;
- third-party scripts: chat widgets, analytics, A/B tests;
- large DOM operations, such as rendering long lists.

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

**Step 1. Lighthouse audit,** as a tab or as a command-line tool. It gives all four metrics plus the Core Web Vitals, and points at specific problems as audit items. Run it in incognito mode, so that extensions don't distort the numbers.

**Step 2. The Performance panel, for TTFB and Long Tasks.** Open DevTools → Performance → ⏺, or press Ctrl+Shift+E to reload with recording on.

- The Timings track holds the FCP, LCP and TBT markers.
- The Network track shows whether anything blocks rendering early.
- The Main track shows where the Long Tasks are.

**Step 3. The Network tab, for TTFB.** Hover over the waterfall bar of the document to get the Timing breakdown, where `Waiting for server response` is the real server time. Compare it with the TTFB measured from a CDN node. If that node is close to the user and the response is still slow, the problem is the server, not the network.

**Step 4. The Coverage tab.** Open DevTools → ⋮ → More tools → Coverage → ⏺ and reload the page. It shows the share of unused JS and CSS during load, and the red bars mark code that loaded but wasn't needed.

## Connection to other topics

- [Core Web Vitals](./01-core-web-vitals.md) — LCP, CLS and INP are the user-facing metrics. TTFB, FCP, TBT and TTI are the tools for diagnosing why they're poor.
- [Resource Loading](./03-resource-loading.md) — `preload`, `prefetch` and render-blocking resources directly affect FCP.
- [JavaScript Performance](./04-javascript-performance.md) — code splitting reduces TTI and TBT, and Long Tasks are the foundation of TBT.
- [Caching Strategies](./07-caching-strategies.md) — the browser cache and a CDN cut TTFB.

## Common interview traps

- **"TTFB is page load time"** — no. TTFB ends at the first byte of the response. Loading all resources is the Load Event — a completely different metric.

- **"FCP and LCP are the same thing"** — FCP records any first content (including a spinner); LCP records the largest meaningful element. A page can have an excellent FCP and a poor LCP.

- **"TTI is when the page has loaded"** — TTI is defined by a 5-second quiet window free of Long Tasks, not by the Load event. A page can be "loaded" (all resources downloaded) while TTI hasn't been reached because JS is still executing.

- **"TBT can be measured in real-user field data"** — no. TBT is a lab metric (Lighthouse). In the field, INP is used. Confusing them signals shallow knowledge.

- **Not knowing the thresholds** — interviews often ask "what counts as good TTFB?" TTFB: <800ms; FCP: <1.8s; TTI: <3.8s; TBT: <200ms. Memorizing exact numbers matters less than knowing the order of magnitude.

- **"I added defer to all scripts — FCP is good now"** — `defer` does help FCP. But if the CSS itself is large or unoptimized, FCP will still be slow. You need the whole picture: TTFB, then render-blocking resources, then the size of the critical CSS.

- **Ignoring the mobile/desktop difference** — Lighthouse by default simulates a mobile device (4x CPU slowdown, slow network). TTI and TBT on mobile can be 3–5× worse than on desktop. Saying "our TTI is good" without specifying the device is an incomplete answer.
