# Core Web Vitals

## Why Google created CWV — and why this isn't just about SEO

Core Web Vitals are three metrics that Google has used as a ranking signal since 2021. That makes them an SEO (search engine optimization) topic, but ranking is the smaller half of the story. They formalize **the three most painful moments of user experience**. Each metric answers one question that the user asks without thinking about it:

- **"How long until I see the main content?"** — that is LCP (Largest Contentful Paint), the moment the biggest visible piece of content finishes rendering.
- **"Does content shift under my finger while the page loads?"** — that is CLS (Cumulative Layout Shift). You aim at a button and hit something else.
- **"When I click or tap, does the page answer instantly or freeze for half a second?"** — that is INP (Interaction to Next Paint).

In interviews CWV is often discussed only through the lens of ranking. That frame is backwards. These are proxy metrics for the user's experience: you optimize them for people, and better search ranking follows as a side effect.

## LCP — Largest Contentful Paint

### What exactly is measured

LCP records the moment when the **largest element** from an allowed set renders in the viewport.

**What counts as an LCP element,** in the browser's order of priority:

- `<img>`
- `<image>` inside an SVG (scalable vector graphics) document
- `<video>`, through its poster image
- an element with a CSS `background-image`
- a block-level element with text content, such as `<h1>`, `<p>` or `<div>`

**What does not count:**

- `<svg>` on its own
- `<canvas>`
- elements outside the viewport
- elements with `opacity: 0`

The browser can **change its mind** about which element is the LCP element. If it first picked a large text block and a bigger image loads later, LCP moves to the image. The last value before the first user interaction is recorded as the final one.

### Threshold values and their meaning

| Rating | LCP |
|---|---|
| ✅ Good | under 2.5 s |
| ⚠️ Needs improvement | 2.5 — 4.0 s |
| ❌ Poor | over 4.0 s |

These numbers aren't arbitrary. Google studied the correlation between load time and bounce rate. Past an LCP of 4 seconds the likelihood of a user leaving increases significantly. A site as a whole is evaluated by the 75th percentile across its real users.

### What affects LCP — diagnosing the problem

Time-to-LCP is the sum of four components:

| Component | What it covers |
|---|---|
| TTFB (time to first byte) | How quickly the server responds at all |
| Resource load delay | The gap before the browser starts loading the LCP resource |
| Resource load time | How long that resource takes to download |
| Element render delay | Rendering the element after it has loaded |

Each component has its own typical causes:

- **TTFB above 600 ms** — a slow server, no CDN (content delivery network), no cache.
- **Resource load delay** — the preload scanner never saw the image, because it comes from a CSS background or is injected by JS.
- **Resource load time** — a large file, no compression, no CDN.
- **Element render delay** — rendering is blocked by JS or CSS.

### Optimizing LCP — concrete techniques

```html
<!-- ❌ LCP image loaded lazily — a serious mistake -->
<img src="/hero.jpg" loading="lazy" alt="Hero" />

<!-- ✅ For the LCP element: eager + fetchpriority -->
<img
  src="/hero.jpg"
  fetchpriority="high"
  loading="eager"
  alt="Hero"
/>
```

```html
<!-- ✅ Preload for an LCP image not in HTML
     (e.g. defined via CSS or JS) -->
<link
  rel="preload"
  as="image"
  href="/hero.webp"
  imagesrcset="/hero-400.webp 400w, /hero-800.webp 800w"
  imagesizes="(max-width: 800px) 400px, 800px"
/>
```

```ts
// ❌ LCP image injected via JS — the preload scanner never
// sees it; the browser learns of it only after JS runs
const hero = document.createElement('img');
hero.src = '/hero.jpg';
document.body.prepend(hero);

// ✅ If unavoidable — add a preload to <head>
// rather than relying on the scanner
```

```ts
// In Next.js — correct next/image usage for LCP
import Image from 'next/image';

// priority={true} sets fetchpriority="high" and adds a preload link
<Image
  src="/hero.jpg"
  priority={true}
  width={1200}
  height={600}
  alt="Hero"
/>
```

**Server-side optimizations for TTFB:**

- CDN with edge caching (CloudFront, Cloudflare)
- `Cache-Control: s-maxage=31536000` for static assets
- Streaming server-side rendering, SSR (React 18 `renderToPipeableStream`) — browser starts receiving HTML before the server finishes rendering

## CLS — Cumulative Layout Shift

### The scoring formula — why "0.1" isn't obvious

CLS is the **cumulative sum** of all unexpected layout shifts throughout the entire time on the page. Every single shift gets its own score:

```txt
Layout Shift Score = impact fraction × distance fraction
```

- **impact fraction** — what fraction of the viewport was affected by the shift, that is the area of the moving elements.
- **distance fraction** — how far the elements moved, as a fraction of the viewport.

A worked example. A banner 50% of the viewport tall appears and pushes content down by 25% of the viewport. The impact fraction is 0.75: the banner's own 50% plus the 25% of content that moved. The distance fraction is 0.25, so the score of this shift is 0.75 × 0.25 = 0.1875.

Shifts triggered by the **user** — a click, a scroll — do not count in CLS. The same goes for shifts occurring within 500 ms of such an interaction.

| Rating | CLS |
|---|---|
| ✅ Good | under 0.1 |
| ⚠️ Needs improvement | 0.1 — 0.25 |
| ❌ Poor | over 0.25 |

### Common CLS causes and their fixes

```html
<!-- ❌ Image without dimensions — the browser doesn't know
     how much space to reserve before loading -->
<img src="/photo.jpg" alt="Photo" />

<!-- ✅ Always specify width and height — the browser computes
     aspect ratio and reserves space upfront -->
<img src="/photo.jpg" width="800" height="450" alt="Photo" />
```

```css
/* ✅ Alternative via CSS aspect-ratio */
.image-container {
  aspect-ratio: 16 / 9;
  width: 100%;
}
.image-container img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
```

```html
<!-- ❌ Font loads and causes FOUT (Flash of Unstyled Text)
     with a layout shift due to different font metrics -->
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter" />

<!-- ✅ font-display: optional — browser uses the fallback
     if the font didn't load in time for the first render;
     on the next visit the font is already cached -->
<style>
  @font-face {
    font-family: 'Inter';
    src: url('/fonts/inter.woff2') format('woff2');
    font-display: optional;
  }
</style>
```

```css
/* ✅ size-adjust + ascent/descent-override to match fallback
     font metrics precisely to the custom font */
@font-face {
  font-family: 'Inter-fallback';
  src: local('Arial');
  ascent-override: 90%;
  descent-override: 22%;
  line-gap-override: 0%;
  size-adjust: 107%;
}

body {
  font-family: 'Inter', 'Inter-fallback', sans-serif;
}
```

```ts
// ❌ Dynamic content (ads, banners) without reserved space
// — the classic source of CLS
const AdBanner = () => {
  const [ad, setAd] = useState<Ad | null>(null);
  useEffect(() => { fetchAd().then(setAd); }, []);
  return ad ? <div>{ad.content}</div> : null;
};

// ✅ Reserve space explicitly, even before content loads
const AdBanner = () => {
  const [ad, setAd] = useState<Ad | null>(null);
  useEffect(() => { fetchAd().then(setAd); }, []);
  return (
    <div style={{ minHeight: '90px', width: '728px' }}>
      {ad && <div>{ad.content}</div>}
    </div>
  );
};
```

## INP — Interaction to Next Paint

### Why INP replaced FID in March 2024

FID (First Input Delay) measured the delay of only the **first** interaction and only the delay until processing began (not the processing time itself). INP measures **all** interactions on the page and the **complete cycle** from event to paint:

```txt
FID (deprecated):
  [User click] → [start of JS processing]
                 ↑
                 FID = only this waiting time

INP (current since March 2024):
  [User click] → [processing starts] → [JS done] → [paint]
  ↑___________________________________________________↑
                       INP = the full cycle
```

The number reported for a session is the 98th percentile of all its interactions: clicks, taps and key presses.

| Rating | INP |
|---|---|
| ✅ Good | under 200 ms |
| ⚠️ Needs improvement | 200 — 500 ms |
| ❌ Poor | over 500 ms |

### What blocks INP — and how to fix it

```ts
// ❌ Heavy synchronous handler — blocks the main thread,
// browser can't paint the response
button.addEventListener('click', () => {
  const result = heavyComputation(largeData); // 300ms synchronously
  updateUI(result);
});

// ✅ Split with a yield back to the event loop via the Scheduler API
button.addEventListener('click', async () => {
  updateUI({ loading: true });

  // Yield — give the browser a chance to paint the loading state
  await scheduler.yield(); // or: await new Promise(r => setTimeout(r, 0))

  const result = await runInChunks(largeData);
  updateUI({ data: result, loading: false });
});
```

```ts
// ✅ scheduler.postTask for low-priority work
// (available in Chrome 94+, polyfill via setTimeout for Safari)
async function handleClick() {
  // Critical: update UI immediately
  updateButtonState('pressed');

  // Non-critical: analytics shouldn't block the response
  await scheduler.postTask(
    () => sendAnalytics({ event: 'click', target: 'cta' }),
    { priority: 'background' }
  );
}
```

```ts
// Measuring INP in real time with web-vitals
import { onINP } from 'web-vitals';

onINP((metric) => {
  console.log('INP:', metric.value, 'ms');
  // metric.entries contains the PerformanceEventTiming for
  // the worst interaction — lets you identify exactly which one
  const worstInteraction = metric.entries.at(-1);
  console.log('Worst interaction:', worstInteraction?.name);
});
```

## Measuring CWV in DevTools

**Chrome DevTools, Performance panel:**

1. Open DevTools and switch to the Performance tab.
2. Click ⏺ Record, or press Ctrl+Shift+E to reload the page with recording on.
3. Interact with the page.
4. Stop the recording.

The "Timings" track then shows three things at once:

- a green LCP marker — when the LCP element appeared;
- red Layout Shift rectangles — the layout shifts themselves;
- Long Tasks as red bars — what's hurting INP.

Two more places are worth opening:

- The **Performance Insights** tab gives a higher-level view with recommendations.
- **Lighthouse**, either as a tab or as a command-line tool, simulates mobile throttling and gives CWV scores together with root-cause diagnostics.

```ts
// Getting CWV programmatically in the browser
import { onLCP, onCLS, onINP } from 'web-vitals';

// Send to analytics when the value is first available
onLCP((metric) => sendToAnalytics({ name: 'LCP', value: metric.value }));
onCLS((metric) => sendToAnalytics({ name: 'CLS', value: metric.value }));
onINP((metric) => sendToAnalytics({ name: 'INP', value: metric.value }));

// Note: CLS fires multiple times (delta per shift event)
// or once with the final value on page unload.
// Use reportAllChanges: false (default) to get the final value.
```

## Connection to other topics

- [Resource Loading](./03-resource-loading.md) — `preload`, `prefetch` and `fetchpriority` directly affect LCP.
- [JavaScript Performance](./04-javascript-performance.md) — Long Tasks are the main enemy of INP. Code splitting affects TTI (time to interactive) and, indirectly, LCP.
- [Image Optimization](./05-image-optimization.md) — format, size and lazy loading have a triple impact on LCP and CLS.
- [Rendering Performance](./06-rendering-performance.md) — reflow and repaint are the mechanism behind CLS. Compositing layers help avoid Layout Shift penalties.

## Common interview traps

- **"CWV are SEO metrics"** — wrong frame. These are user-experience metrics that Google added as a ranking factor. You optimize them for users, and better ranking is a consequence.

- **"FID measures responsiveness"** — FID is deprecated and was replaced by INP in March 2024. Calling FID a current metric signals outdated knowledge.

- **"LCP is page load time"** — no. LCP measures the specific moment when the largest visible element paints, not the overall load of the page. The distinction matters, because LCP is affected by TTFB, by resource prioritization and by render blocking.

- **"I added `loading="lazy"` to all images — nice"** — `loading="lazy"` on the LCP image (hero banner, above-the-fold content) **hurts** LCP because the browser defers loading. Lazy loading is only for images below the fold.

- **"CLS is when the page jumps"** — imprecise. CLS only counts *unexpected* shifts not triggered by user interaction. And it has an exact formula (impact × distance), not just "present/absent."

- **Not knowing the INP threshold** — under 200 ms is good, and 200–500 ms needs improvement. If an interviewer asks what your project's INP is, you have to be able to measure it and name the thresholds.

- **"I optimized in Lighthouse — everything's green, we're good"** — Lighthouse runs under simulated conditions on one machine. Real CWV come from the Chrome User Experience Report (CrUX) — real user data (75th percentile). The numbers can differ dramatically.
