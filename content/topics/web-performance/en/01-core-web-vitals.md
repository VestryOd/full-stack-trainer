# Core Web Vitals

## Why Google created CWV — and why this isn't just about SEO

Core Web Vitals are three metrics that Google has used as a ranking signal since 2021. But more important than the SEO angle is this: they formalize **the three most painful moments of user experience**:

```txt
A user opens a page:

  "How long until I see the main content?"
  → LCP (Largest Contentful Paint)

  "Does content shift while the page loads?
   I clicked a button but hit the wrong thing?"
  → CLS (Cumulative Layout Shift)

  "When I click/tap, does the page respond instantly
   or freeze for half a second?"
  → INP (Interaction to Next Paint)
```

This framing matters because CWV is often discussed in interviews through the lens of "how to improve SEO." The correct frame is different: these are **proxy metrics for UX**, optimized for users — SEO improvement is a side effect.

## LCP — Largest Contentful Paint

### What exactly is measured

LCP records the moment when the **largest element** from an allowed set renders in the viewport:

```txt
What counts as an LCP element (in browser priority order):
  - <img>
  - <image> inside SVG
  - <video> (poster image)
  - Element with CSS background-image
  - Block-level element with text content (<h1>, <p>, <div>)

What does NOT count:
  - <svg> (by itself)
  - <canvas>
  - Elements outside the viewport
  - Elements with opacity: 0
```

The browser can **update** the LCP element as the page loads: if it first found a large text block, then a larger image loaded — LCP is updated. The last value before the first user interaction is recorded as the final one.

### Threshold values and their meaning

```txt
✅ Good:              < 2.5 s
⚠️  Needs improvement: 2.5 — 4.0 s
❌ Poor:              > 4.0 s

These numbers aren't arbitrary. Google studied the correlation
between load time and bounce rate: at LCP > 4s, the likelihood
of a user leaving increases significantly. The 75th percentile
across real users is used to evaluate a site overall.
```

### What affects LCP — diagnosing the problem

```txt
Time-to-LCP is the sum of four components:

  [TTFB] + [Resource load delay] + [Resource load time] + [Element render delay]
    ↑              ↑                       ↑                       ↑
  Server       When browser          How long the             Rendering after
  responds     started loading       resource takes            load
               the LCP resource      to download

  Typical causes:
  - TTFB > 600ms → slow server, no CDN, no cache
  - Resource load delay → image missed by preload scanner
    (CSS background, JS-injected element)
  - Resource load time → large file, no compression, no CDN
  - Element render delay → render blocked by JS/CSS
```

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
- Streaming SSR (React 18 `renderToPipeableStream`) — browser starts receiving HTML before the server finishes rendering

## CLS — Cumulative Layout Shift

### The scoring formula — why "0.1" isn't obvious

CLS is the **cumulative sum** of all unexpected layout shifts throughout the entire time on the page:

```txt
Layout Shift Score = impact fraction × distance fraction

  impact fraction   — what fraction of the viewport was affected
                      by the shift (area of moving elements)
  distance fraction — how far elements moved as a fraction
                      of the viewport

Example:
  - A banner 50% of the viewport tall appeared and pushed
    content down by 25% of the viewport
  - impact fraction = 0.75 (banner 50% + shifted content 25%)
  - distance fraction = 0.25
  - Layout Shift Score = 0.75 × 0.25 = 0.1875

Important: shifts triggered by USER INTERACTION (click, scroll)
or occurring within 500ms of an interaction do NOT count in CLS.
```

```txt
✅ Good:              < 0.1
⚠️  Needs improvement: 0.1 — 0.25
❌ Poor:              > 0.25
```

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

  INP = 98th percentile of all interactions (clicks, taps,
  key presses) during the session
```

```txt
✅ Good:              < 200 ms
⚠️  Needs improvement: 200 — 500 ms
❌ Poor:              > 500 ms
```

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

```txt
Chrome DevTools → Performance panel:

1. Open DevTools → Performance tab
2. Click ⏺ Record (or Ctrl+Shift+E to reload with recording)
3. Interact with the page
4. Stop the recording

In the "Timings" track:
  - Green LCP marker — when the LCP element appeared
  - Red Layout Shift rectangles — layout shifts
  - Long Tasks (red bars) — what's hurting INP

Performance Insights tab:
  → Higher-level view with recommendations

Lighthouse (tab or CLI):
  → Simulates mobile throttling
  → Gives CWV scores + root-cause diagnostics
```

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

```txt
[Resource Loading]        — preload/prefetch/fetchpriority
                            directly affect LCP
[JavaScript Performance]  — Long Tasks are the main enemy of INP;
                            code splitting affects TTI
                            and indirectly LCP
[Image Optimization]      — format, size, lazy loading
                            — triple impact on LCP and CLS
[Rendering Performance]   — reflow/repaint is the mechanism
                            behind CLS; compositing layers help
                            avoid Layout Shift penalties
```

## Common interview traps

- **"CWV are SEO metrics"** — wrong frame. These are UX metrics that Google added as a ranking factor. You optimize them for users; SEO improvement is a consequence.

- **"FID measures responsiveness"** — FID is deprecated and was replaced by INP in March 2024. Calling FID a current metric signals outdated knowledge.

- **"LCP is page load time"** — LCP measures the specific moment the largest visible element paints, not overall "page load time." The distinction matters: LCP is affected by TTFB + resource prioritization + render blocking.

- **"I added `loading="lazy"` to all images — nice"** — `loading="lazy"` on the LCP image (hero banner, above-the-fold content) **hurts** LCP because the browser defers loading. Lazy loading is only for images below the fold.

- **"CLS is when the page jumps"** — imprecise. CLS only counts *unexpected* shifts not triggered by user interaction. And it has an exact formula (impact × distance), not just "present/absent."

- **Not knowing the INP threshold** — 200ms is "good," 200–500ms is "needs improvement." If an interviewer asks "what's your project's INP" — you need to be able to measure it and know the thresholds.

- **"I optimized in Lighthouse — everything's green, we're good"** — Lighthouse runs under simulated conditions on one machine. Real CWV come from the Chrome User Experience Report (CrUX) — real user data (75th percentile). The numbers can differ dramatically.
