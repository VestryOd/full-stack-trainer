# Resource Loading

## The Critical Rendering Path — the starting point

Before discussing resource hints, you need to understand what the browser does with resources by default — and why that's suboptimal.

```txt
The browser receives HTML and builds the Critical Rendering Path:

  HTML → DOM
  CSS  → CSSOM    } combined into Render Tree → Layout → Paint
  JS   → blocks HTML parsing until it executes

The "waterfall" problem:
  1. Browser starts parsing HTML
  2. Encounters <link rel="stylesheet" href="style.css">
     → STOP, downloading CSS
  3. In the CSS: url('/fonts/inter.woff2')
     → the browser DOESN'T KNOW about this font yet (still parsing CSS)
  4. CSS downloaded → parsed → font discovered → download starts
     → DELAY = CSS parse time + one RTT for the font request

Resource hints solve this: they tell the browser about resources
UPFRONT, in <head>, before it encounters them in CSS/JS —
or even before they exist on the current page at all.
```

## preload — "this resource is needed right now"

`<link rel="preload">` tells the browser: download this resource **immediately**, at high priority, regardless of when it appears in HTML/CSS/JS.

```html
<!-- Basic syntax — as="" is required -->
<link rel="preload" href="/fonts/inter.woff2" as="font" crossorigin />
<link rel="preload" href="/hero.jpg" as="image" />
<link rel="preload" href="/critical.css" as="style" />
<link rel="preload" href="/app.js" as="script" />
```

```html
<!-- as="" affects priority and Content-Security-Policy.
     Without it, the browser downloads the resource at low
     priority and ignores CORS — the font won't load. -->

<!-- ❌ Wrong — missing as="" and crossorigin for a font -->
<link rel="preload" href="/fonts/inter.woff2" />

<!-- ✅ Correct — with as="font" and crossorigin
     (fonts always require CORS, even from the same domain) -->
<link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2" crossorigin />
```

### preload for responsive images

```html
<!-- ✅ imagesrcset + imagesizes — the browser picks the
     correct file before it even parses the <img> tag -->
<link
  rel="preload"
  as="image"
  href="/hero-800.webp"
  imagesrcset="/hero-400.webp 400w, /hero-800.webp 800w, /hero-1600.webp 1600w"
  imagesizes="(max-width: 600px) 100vw, 800px"
/>

<!-- Then in the HTML — the browser already knows which file it needs -->
<img
  src="/hero-800.webp"
  srcset="/hero-400.webp 400w, /hero-800.webp 800w, /hero-1600.webp 1600w"
  sizes="(max-width: 600px) 100vw, 800px"
  fetchpriority="high"
  alt="Hero"
/>
```

### modulepreload — preload for ES modules

```html
<!-- A regular preload for a module doesn't process its
     dependencies. modulepreload downloads the module AND
     its transitive dependencies, and parses all of them. -->
<link rel="modulepreload" href="/app.js" />
<link rel="modulepreload" href="/vendor.js" />

<!-- Unlike <script type="module">, which waits in the
     module execution queue, modulepreload lets downloading
     start immediately. -->
```

### When preload hurts

```html
<!-- ❌ Unnecessary preloads — the browser downloads the resource
     at high priority, but the page doesn't use it immediately.
     This pushes other important resources down the queue. -->
<link rel="preload" href="/sidebar-widget.js" as="script" />
<link rel="preload" href="/footer-image.jpg" as="image" />
<link rel="preload" href="/admin-panel.js" as="script" />
```

```txt
Rule: preload only for resources that:
  1. Are needed on the CURRENT page
  2. Are discovered LATE (not in the first-screen HTML)
  3. Are critical for LCP or the first render

  Good candidates: LCP image, custom font,
  critical CSS file, main JS bundle
  Bad candidates: anything below the fold, widgets, analytics
```

## prefetch — "this resource will be needed later"

`<link rel="prefetch">` asks the browser to download a resource **in the background, at low priority**, for use during the next navigation.

```html
<!-- When the user is on /products —
     high probability they'll navigate to /checkout -->
<link rel="prefetch" href="/checkout.js" as="script" />
<link rel="prefetch" href="/payment-icons.webp" as="image" />
```

```ts
// ✅ Smart prefetch: trigger on link hover/focus —
// the user has ~100–200ms before clicking
const handleLinkHover = (href: string) => {
  const link = document.createElement('link');
  link.rel = 'prefetch';
  link.href = href;
  document.head.appendChild(link);
};

document.querySelectorAll('a[data-prefetch]').forEach(a => {
  a.addEventListener('mouseenter', () => handleLinkHover(a.href));
  a.addEventListener('focus', () => handleLinkHover(a.href));
});
```

```ts
// Next.js does this automatically:
// <Link> prefetches pages when they enter the viewport
import Link from 'next/link';

// prefetch is on by default for all <Link>
// (disable with prefetch={false})
<Link href="/checkout">Proceed to checkout</Link>
```

```txt
preload vs prefetch — the fundamental difference:

  preload:  CURRENT navigation, high priority,
            resource is expected to be used immediately.
            The browser will warn in the console if the
            resource isn't used within ~3 seconds.

  prefetch: FUTURE navigation, low priority,
            the browser may defer or cancel
            (e.g. on a slow connection).
            Stored in the HTTP cache for subsequent requests.
```

## preconnect and dns-prefetch

### preconnect — warming up connections

Establishing a TCP + TLS connection takes 1–3 RTTs. `preconnect` does this upfront:

```html
<!-- ✅ preconnect for critical external domains —
     fonts, CDN, APIs -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="preconnect" href="https://api.example.com" />

<!-- crossorigin is required when the resource uses
     CORS (fonts, fetch API) -->
```

```txt
What preconnect provides:

  Without preconnect (font request from CSS):
  HTML → CSS discovered → DNS → TCP → TLS → Request → Response
          ↑ all of this happens AFTER CSS is parsed

  With preconnect (in <head>):
  DNS → TCP → TLS (starts immediately when HTML loads)
  By the time CSS gets to requesting the font — connection is ready.

  Savings: 100–500ms on slow DNS / high-latency connections
```

### dns-prefetch — the lighter alternative

`dns-prefetch` does only DNS resolution (no TCP/TLS), consuming fewer resources:

```html
<!-- For domains connected to later during the session
     rather than at page load (analytics, chat widgets,
     lazy-loaded third-party content) -->
<link rel="dns-prefetch" href="https://analytics.google.com" />
<link rel="dns-prefetch" href="https://cdn.intercom.io" />
```

```html
<!-- Decision rule:
     Critical domain (needed at load)  → preconnect
     Non-critical domain (needed later) → dns-prefetch
     Too many domains for preconnect   → keep only 2–3
       of the most important, others  → dns-prefetch

     preconnect keeps a connection open for ~10 seconds,
     consuming resources on both client and server.
     Overusing preconnect is worse than not using it. -->
```

## Priority Hints — fetchpriority

`fetchpriority` explicitly sets a resource's loading priority (Chrome 96+, Safari 17.2+):

```html
<!-- high — for LCP images, critical resources -->
<img src="/hero.jpg" fetchpriority="high" alt="Hero" />

<!-- low — for non-critical resources that shouldn't
     consume high-priority bandwidth -->
<img src="/decoration.jpg" fetchpriority="low" alt="" />

<!-- auto — browser's default behavior -->
<img src="/product.jpg" fetchpriority="auto" alt="Product" />
```

```ts
// fetchpriority also works with the fetch() API
const criticalData = await fetch('/api/above-fold-data', {
  priority: 'high',
});

const backgroundData = await fetch('/api/recommendations', {
  priority: 'low',
});
```

```html
<!-- Common pattern: lower the priority of hidden carousel
     slides — they're in the DOM but not visible -->
<div class="carousel">
  <img src="/slide-1.jpg" fetchpriority="high" alt="Slide 1" />
  <img src="/slide-2.jpg" fetchpriority="low" alt="Slide 2" />
  <img src="/slide-3.jpg" fetchpriority="low" alt="Slide 3" />
</div>
```

## Lazy Loading

### Native lazy loading

```html
<!-- loading="lazy" — built into the browser.
     The image doesn't load until it approaches the
     viewport (the exact distance depends on browser and network). -->
<img src="/below-fold.jpg" loading="lazy" width="800" height="600" alt="..." />

<!-- ❌ Mistake: lazy on the LCP image -->
<img src="/hero.jpg" loading="lazy" alt="Hero" />

<!-- ✅ Rule: lazy only for images below the fold.
     "Above fold" depends on the device; a safe threshold is
     to skip lazy loading for the first 2–3 screens. -->
```

```html
<!-- loading="lazy" also works for <iframe> -->
<iframe
  src="https://www.youtube.com/embed/xyz"
  loading="lazy"
  width="560"
  height="315"
  title="Video"
></iframe>
```

### Intersection Observer — custom lazy loading

Needed when native `loading="lazy"` isn't enough: components, sections, data fetching.

```ts
// ✅ General-purpose hook for lazy-loading React components
import { useEffect, useRef, useState } from 'react';

function useLazyLoad(options?: IntersectionObserverInit) {
  const ref = useRef<HTMLElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsVisible(true);
        observer.disconnect(); // stop observing after first reveal
      }
    }, { rootMargin: '200px', ...options }); // start loading 200px early

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, isVisible };
}

// Usage:
function HeavySection() {
  const { ref, isVisible } = useLazyLoad();

  return (
    <section ref={ref}>
      {isVisible
        ? <ExpensiveChart />
        : <div style={{ height: '400px' }} />  // placeholder
      }
    </section>
  );
}
```

```ts
// ✅ Lazy data loading — only fetch the API when the
// section approaches the viewport
function ProductRecommendations() {
  const { ref, isVisible } = useLazyLoad({ rootMargin: '400px' });
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    if (!isVisible) return;
    fetch('/api/recommendations').then(r => r.json()).then(setProducts);
  }, [isVisible]);

  return (
    <section ref={ref}>
      {products.length > 0
        ? <ProductGrid products={products} />
        : <Skeleton count={4} />
      }
    </section>
  );
}
```

## Resource priority strategy — the full picture

```txt
When the browser discovers resources, it assigns priorities:

  Critical (immediate):
    → CSS in <head>
    → Synchronous <script> in <head>
    → preload with fetchpriority="high"

  High:
    → <img fetchpriority="high"> (or first in-viewport images)
    → preload without fetchpriority
    → <script defer> in document order

  Medium:
    → <img> without attributes (in viewport)
    → <script async>

  Low:
    → <img loading="lazy">
    → prefetch
    → <img fetchpriority="low">

  The browser preload scanner (speculative parser):
    In parallel with DOM parsing, the browser scans the
    raw HTML for resources (src, href) to start downloading
    early — but it only sees static HTML, not CSS url()
    values or JS-injected elements.
    This is exactly why explicit preload is critical for
    resources discovered through CSS or JavaScript.
```

## Practical DevTools workflow

```txt
Chrome DevTools → Network tab:
  1. Reload the page with Network open
  2. Waterfall — visualizes order and parallelism of loading
  3. Bar colors:
     - blue   = HTML
     - purple = CSS
     - yellow = JS
     - green  = images
  4. Priority column (right-click header → Priority):
     → "Highest"/"High" — correct for the LCP image?
     → "Low" — correct for below-fold content?

DevTools → Performance → record page load:
  → "Initiator" — what triggered the resource to load
  → Bar width = download time
  → Bar start = when the browser learned about the resource

Typical diagnosis:
  Font starts downloading 500ms after the page starts →
  the browser learned about it late (from CSS) →
  add <link rel="preload" as="font"> to <head>
```

## Connection to other topics

```txt
[Core Web Vitals]         — preloading the LCP resource directly
                            reduces LCP; fixing loading="lazy"
                            on the LCP element is a common quick win
[Performance Metrics]     — preconnect reduces TTFB for external
                            resources; preload reduces FCP
[JavaScript Performance]  — modulepreload speeds up ES module
                            loading; prefetch implements
                            route-based code splitting
[Image Optimization]      — lazy loading + srcset + fetchpriority
                            work together for optimal LCP
                            and bandwidth savings
```

## Common interview traps

- **"preload and prefetch do the same thing, just at different priorities"** — no. preload is for the CURRENT page (high priority, used immediately). prefetch is for the NEXT navigation (low priority, cached for future use). Conflating them means understanding neither.

- **"I added preload to everything — the site got faster"** — it can have the opposite effect. Every preload competes for bandwidth. If a preload for a non-critical resource displaces the LCP image, LCP gets worse. Lighthouse specifically warns about "unused preload."

- **"You can add preconnect for all domains"** — no. preconnect opens and holds a TCP/TLS connection for ~10 seconds. With 10+ domains this loads down the client and can tie up connections needed for real requests. Rule: 2–3 most critical domains, everything else gets dns-prefetch.

- **"loading="lazy" solves all image problems"** — no. It's one tool. Apply it to the LCP image and you directly hurt LCP. Without `width`/`height` it causes CLS. It doesn't help with format, compression, or srcset.

- **"The preload scanner sees everything in the HTML"** — no. It only sees static `src`/`href` attributes in raw HTML. CSS `url()`, JS-injected elements, dynamic `import()` — it can't see those. That's exactly why explicit `<link rel="preload">` exists for those cases.

- **"fetchpriority="high" is the same as preload"** — they're different things. `preload` says "download this resource now, regardless of whether you'll encounter it in the document." `fetchpriority` says "when you download this already-known resource, do it at this priority." `preload` changes when discovery happens; `fetchpriority` changes the priority of a resource the browser already knows about.
