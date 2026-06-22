# SEO, Metadata, and Performance

## The Metadata API — static, dynamic, and inheritance

In the App Router, metadata is declared via an exported `metadata` object (static) or `generateMetadata` (dynamic) in `layout.tsx`/`page.tsx`. A key, often-missed detail: metadata is **inherited and merged** across the layout tree — a `page.tsx` doesn't have to repeat what's already set in a parent `layout.tsx`, but it can override individual fields.

```tsx
// app/layout.tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  metadataBase: new URL('https://example.com'), // base for relative URLs in OG/canonical
  title: {
    default: 'Acme Store',
    template: '%s | Acme Store', // used by child segments
  },
  description: 'Default site description',
};

// app/products/[id]/page.tsx
export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params; // Next.js 15: params is async
  const product = await getProduct(id);

  return {
    title: product.name, // final title: "Product Name | Acme Store"
    description: product.shortDescription,
    openGraph: {
      images: [{ url: product.imageUrl, width: 1200, height: 630 }],
    },
  };
}
```

A nuance with `title.template`: it only applies if a child segment sets `title` as a plain string, not as an `{ absolute: ... }` object. `absolute` explicitly "opts out" of the template inheritance — useful for pages that shouldn't get the ` | Acme Store` suffix (e.g. a campaign landing page with its own branding).

### generateMetadata and the cost of duplicate requests

`generateMetadata` often fetches the same data as the page component itself (e.g. `getProduct(id)` is needed for both the title and the content). Thanks to **Request Memoization** (see the data fetching article), calling the same `fetch`/`React.cache`-wrapped function twice doesn't trigger an extra request — but only if the function is actually memoized, not written as two independent direct DB calls.

```ts
import { cache } from 'react';

export const getProduct = cache(async (id: string) => {
  return db.product.findUnique({ where: { id } });
});
```

## robots.ts and sitemap.ts — typed file conventions

```ts
// app/robots.ts
import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: '*', allow: '/', disallow: ['/admin', '/api'] },
    ],
    sitemap: 'https://example.com/sitemap.xml',
  };
}
```

```ts
// app/sitemap.ts
import type { MetadataRoute } from 'next';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const products = await getAllProductIds();

  const productEntries = products.map((id) => ({
    url: `https://example.com/products/${id}`,
    lastModified: new Date(),
    changeFrequency: 'weekly' as const,
    priority: 0.8,
  }));

  return [
    { url: 'https://example.com', lastModified: new Date(), priority: 1 },
    ...productEntries,
  ];
}
```

For very large catalogs (>50,000 URLs — the per-file limit in the sitemap protocol), Next supports **generating multiple sitemap files** via `generateSitemaps`, something even candidates who know about `sitemap.ts` often miss.

## Structured Data (JSON-LD)

Next doesn't provide a dedicated API for structured data — it's plain JSON inserted into a `<script type="application/ld+json">` via JSX:

```tsx
export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; // Next.js 15: params is async
  const product = await getProduct(id);

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.name,
    image: product.imageUrl,
    offers: {
      '@type': 'Offer',
      price: product.price,
      priceCurrency: 'USD',
      availability: product.inStock ? 'InStock' : 'OutOfStock',
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <ProductView product={product} />
    </>
  );
}
```

Important: `dangerouslySetInnerHTML` is justified here because the content is server-serialized JSON, not user-supplied HTML. But if `product.name` contains user input (e.g. a customizable product title), be careful — `JSON.stringify` doesn't escape `</script>` inside strings, which could theoretically break out of the `<script>` tag and lead to XSS. In practice the risk is low for controlled data from your own DB, but it's a nuance worth raising in a senior interview.

## next/image — what happens under the hood

```tsx
import Image from 'next/image';

export function ProductCard({ product }: { product: Product }) {
  return (
    <Image
      src={product.imageUrl}
      alt={product.name}
      width={400}
      height={300}
      sizes="(max-width: 768px) 100vw, 400px"
      placeholder="blur"
      blurDataURL={product.blurHash}
    />
  );
}
```

- `width`/`height` are required for static images — Next reserves space for the image **before** it loads, directly reducing CLS (Cumulative Layout Shift).
- `sizes` tells the browser which variant of the generated `srcset` to pick based on viewport width — without it, the browser may download a larger image than what's actually displayed.
- `placeholder="blur"` shows a blurred version (from `blurDataURL`, usually generated at build time) while the original loads — improves perceived performance.
- `priority` — for above-the-fold images (e.g. a hero image), disables `loading="lazy"` and raises fetch priority; for the LCP element this often gives a measurable improvement.

A common anti-pattern is `fill` without `sizes` on a parent with no explicit dimensions:

```tsx
// ❌ parent has no position: relative and no fixed size —
// fill can't correctly compute the image's dimensions
<div>
  <Image src={...} alt="" fill />
</div>

// ✅
<div style={{ position: 'relative', width: '100%', height: '300px' }}>
  <Image src={...} alt="" fill style={{ objectFit: 'cover' }} />
</div>
```

## next/font — eliminating layout shift from web fonts

The classic web font problem: the browser first shows text in a system font (FOUT — Flash of Unstyled Text) or shows nothing (FOIT), then re-flows the text once the custom font loads — that's CLS.

```tsx
import { Inter, Roboto_Mono } from 'next/font/google';

const inter = Inter({
  subsets: ['latin', 'cyrillic'], // important for Cyrillic — otherwise the font won't cover Russian characters
  display: 'swap',
  variable: '--font-inter',
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
```

`next/font` downloads the font **at build time**, self-hosts the file as a static asset, and automatically generates `@font-face` with `size-adjust` — meaning: no runtime request to Google Fonts (which itself improves privacy — the user's IP isn't sent to Google on every page load), and the fallback font's metrics are tuned to occupy a size as close as possible to the real font, minimizing CLS on swap.

## Core Web Vitals — what each Next mechanism specifically improves

| Metric | What it measures | What improves it in Next.js |
|---|---|---|
| **LCP** (Largest Contentful Paint) | Time until the largest visible element renders | SSR/SSG (HTML with content arrives immediately), `next/image` with `priority`, `next/font` (text doesn't wait for the font) |
| **CLS** (Cumulative Layout Shift) | Total "jumping" shift of elements | `next/image` with explicit `width`/`height`, `next/font` (stable font metrics), avoiding hydration mismatch |
| **INP** (Interaction to Next Paint) | Delay in responding to user actions | Less client-side JS via Server Components → less main-thread work |

A good senior answer doesn't just name the metrics — it connects a *specific Next mechanism* to a *specific metric and the reason why*. That shows you understand not just "what to use" but "why it works".

## Streaming and Suspense — the link to perceived performance

```tsx
import { Suspense } from 'react';

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; // Next.js 15: params is async
  return (
    <div>
      <ProductHeader id={id} /> {/* fast fetch — part of the shell */}
      <Suspense fallback={<ReviewsSkeleton />}>
        <Reviews id={id} /> {/* slow fetch — streamed separately */}
      </Suspense>
    </div>
  );
}
```

From an SEO standpoint, streaming doesn't hurt indexing — Googlebot waits for the full response before processing it (it doesn't "see" intermediate chunks the way a browser does), but from a **real user's** standpoint, LCP can improve because content critical for the initial view (`ProductHeader`) isn't blocked by the slower `Reviews`.

## Common interview mistakes

- **"It's enough to add `<title>` and `<meta description>`, the rest doesn't matter"** — this misses `metadataBase` (without it, relative URLs in Open Graph may resolve incorrectly), `robots`/`sitemap` for crawl budget, and structured data for rich snippets.

- **Not knowing about metadata inheritance/merging across the layout tree** — and duplicating `title`/`description` in every `page.tsx` instead of using `title.template`.

- **"next/image automatically reduces CLS on its own, without width/height"** — no, it's specifically the explicit `width`/`height` (or `fill` with a correctly positioned parent) that lets the browser reserve space ahead of time.

- **Confusing `priority` and `loading="lazy"`** — `priority` doesn't just "remove lazy loading", it also raises the browser's fetch priority (`fetchpriority="high"`), which directly affects LCP for above-the-fold images.

- **"next/font just loads the font faster"** — this misses the main mechanism: build-time self-hosting (no runtime request to Google Fonts) and tuning fallback font metrics to reduce CLS, not just "faster loading".

- **Can't connect LCP/CLS/INP to specific code-level decisions** — answering abstractly ("Next is good for performance") instead of "SSR improves LCP because HTML with content arrives immediately, instead of after JS executes".

- **"Streaming hurts SEO because the page is delivered 'in pieces'"** — search crawlers receive the full final HTML once streaming completes, not a partially-loaded chunk — streaming is transparent to them.
