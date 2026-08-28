# Resource Loading

## The Critical Rendering Path — the starting point

Before discussing resource hints, you need to understand what the browser does with resources by default — and why that's suboptimal.

The browser receives the HTML and builds the Critical Rendering Path out of it:

- HTML becomes the DOM (document object model).
- CSS becomes the CSSOM (CSS object model).
- The two are combined into a Render Tree, and then come Layout and Paint.
- JS blocks HTML parsing until it has executed.

From that order follows the "waterfall" problem:

1. The browser starts parsing the HTML.
2. It encounters `<link rel="stylesheet" href="style.css">` and **stops** to download the CSS.
3. Inside that CSS sits `url('/fonts/inter.woff2')`, but the browser **doesn't know about this font yet** — it is still parsing the CSS.
4. The CSS finishes downloading, gets parsed, the font is discovered, and only then does its download start. The **delay** is the CSS parse time plus one extra round trip for the font request.

Resource hints solve exactly this. They tell the browser about resources **upfront**, in `<head>`. That happens before the browser encounters them in CSS or JS, and even before they exist on the current page at all.

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

The `modulepreload` hint is the preload variant for ES (ECMAScript) modules. A regular `preload` on a module downloads the file but does not process its dependencies. The `modulepreload` hint downloads the module **and** its transitive dependencies, and parses all of them.

```html
<!-- modulepreload takes the whole dependency subtree,
     not just the entry file. -->
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

Use `preload` only for resources that satisfy all three conditions:

1. They are needed on the **current** page.
2. They are discovered **late**, not in the first-screen HTML.
3. They are critical for LCP (largest contentful paint) or for the first render.

Good candidates are the LCP image, a custom font, the critical CSS file and the main JS bundle. Bad candidates are anything below the fold, widgets and analytics.

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

The difference between the two hints is fundamental, not a matter of degree:

| | `preload` | `prefetch` |
|---|---|---|
| Which navigation | The current one | A future one |
| Priority | High | Low |
| When it is used | Immediately | On the next navigation |
| Browser may skip it | No | Yes, for example on a slow connection |

If a preloaded resource isn't used within about three seconds, the browser warns about it in the console. A prefetched resource is kept in the HTTP cache for subsequent requests.

## preconnect and dns-prefetch

### preconnect — warming up connections

Establishing a TCP (transmission control protocol) and TLS (transport layer security) connection takes one to three round trips. The `preconnect` hint does that work upfront:

```html
<!-- ✅ preconnect for critical external domains —
     fonts, CDN, APIs -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="preconnect" href="https://api.example.com" />

<!-- crossorigin is required when the resource uses
     CORS (fonts, fetch API) -->
```

Without `preconnect`, a font requested from CSS runs the whole chain **after** the CSS has been parsed. The chain is: name lookup (`DNS`), then TCP, then TLS, then the request, then the response.

With `preconnect` in `<head>` the name lookup and both handshakes start immediately, as soon as the HTML loads. By the time the CSS gets to requesting the font, the connection is already open.

The saving is 100–500 ms on slow name resolution or on high-latency connections.

### dns-prefetch — the lighter alternative

The `dns-prefetch` hint only resolves the domain name and stops there, opening no TCP or TLS connection, so it costs fewer resources:

```html
<!-- For domains connected to later during the session
     rather than at page load (analytics, chat widgets,
     lazy-loaded third-party content) -->
<link rel="dns-prefetch" href="https://analytics.google.com" />
<link rel="dns-prefetch" href="https://cdn.intercom.io" />
```

How to choose between the two:

- A critical domain, needed at load time — use `preconnect`.
- A non-critical domain, needed later — use `dns-prefetch`.
- Too many domains for `preconnect` — keep the two or three most important ones and give the rest `dns-prefetch`.

The `preconnect` hint keeps a connection open for about 10 seconds, consuming resources on both the client and the server. Overusing it is worse than not using it at all.

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

When the browser discovers resources, it assigns each one a priority.

**Critical, fetched immediately:**

- CSS in `<head>`;
- synchronous `<script>` in `<head>`;
- `preload` with `fetchpriority="high"`.

**High:**

- `<img fetchpriority="high">`, and the first images inside the viewport;
- `preload` without `fetchpriority`;
- `<script defer>`, in document order.

**Medium:**

- `<img>` without attributes, inside the viewport;
- `<script async>`.

**Low:**

- `<img loading="lazy">`;
- `prefetch`;
- `<img fetchpriority="low">`.

On top of that the browser runs a **preload scanner**, also called the speculative parser. In parallel with DOM parsing it scans the raw HTML for resource references such as `src` and `href`, so that downloads can start early.

The scanner only sees static HTML. It does not see CSS `url()` values and it does not see JS-injected elements. That is exactly why an explicit `preload` is critical for resources discovered through CSS or JavaScript.

## Practical DevTools workflow

**Chrome DevTools, Network tab:**

1. Reload the page with the Network tab open.
2. The Waterfall visualizes the order and the parallelism of loading.
3. Bar colors: blue is HTML, purple is CSS, yellow is JS, green is images.
4. Add the Priority column by right-clicking the table header. Check that the LCP image gets "Highest" or "High", and that below-the-fold content gets "Low".

**DevTools → Performance → record a page load.** The "Initiator" column tells you what triggered the resource to load. The width of a bar is the download time, and the start of a bar is the moment the browser learned about the resource.

A typical diagnosis looks like this. A font starts downloading 500 ms after the page starts, which means the browser learned about it late, from the CSS. The fix is to add `<link rel="preload" as="font">` to `<head>`.

## Connection to other topics

- [Core Web Vitals](./01-core-web-vitals.md) — preloading the LCP resource directly reduces LCP. Removing `loading="lazy"` from the LCP element is a common quick win.
- [Performance Metrics](./02-performance-metrics.md) — `preconnect` reduces TTFB (time to first byte) for external resources, and `preload` reduces FCP (first contentful paint).
- [JavaScript Performance](./04-javascript-performance.md) — `modulepreload` speeds up ES module loading, and `prefetch` implements route-based code splitting.
- [Image Optimization](./05-image-optimization.md) — lazy loading, `srcset` and `fetchpriority` work together for an optimal LCP and for bandwidth savings.

## Common interview traps

- **"preload and prefetch do the same thing, just at different priorities"** — no. The `preload` hint is for the **current** page: high priority, used immediately. The `prefetch` hint is for the **next** navigation: low priority, cached for future use. Conflating them means understanding neither.

- **"I added preload to everything — the site got faster"** — it can have the opposite effect. Every preload competes for bandwidth. If a preload for a non-critical resource displaces the LCP image, LCP gets worse. Lighthouse specifically warns about "unused preload."

- **"You can add preconnect for all domains"** — no. `preconnect` opens and holds a TCP/TLS connection for about 10 seconds. With ten or more domains this loads down the client and can occupy connections needed for real requests. The rule: two or three most critical domains, everything else gets `dns-prefetch`.

- **"loading="lazy" solves all image problems"** — no. It's one tool. Apply it to the LCP image and you directly hurt LCP. Without `width`/`height` it causes CLS (cumulative layout shift). It doesn't help with format, compression, or `srcset`.

- **"The preload scanner sees everything in the HTML"** — no. It only sees static `src`/`href` attributes in raw HTML. CSS `url()`, JS-injected elements, dynamic `import()` — it can't see those. That's exactly why explicit `<link rel="preload">` exists for those cases.

- **"fetchpriority="high" is the same as preload"** — they're different things. The `preload` hint says: download this resource now, regardless of whether you'll encounter it in the document. The `fetchpriority` attribute says: when you download this already-known resource, do it at this priority. So `preload` changes when discovery happens, and `fetchpriority` changes the priority of a resource the browser already knows about.
