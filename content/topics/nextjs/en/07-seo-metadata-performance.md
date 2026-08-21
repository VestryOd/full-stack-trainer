# SEO, Metadata, and Performance

## The Metadata API — static, dynamic, and inheritance

In the App Router, metadata is declared with an exported `metadata` object (static) or `generateMetadata` (dynamic) in `layout.tsx` or `page.tsx`. This is the text search engines read, so it is the base layer of SEO (search engine optimization).

A key detail people miss: metadata is **inherited and merged** across the layout tree. A `page.tsx` doesn't have to repeat what a parent `layout.tsx` already set, and it can override individual fields.

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
type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
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

A nuance with `title.template`: it applies only when a child segment sets `title` as a plain string. Pass an `{ absolute: ... }` object instead and the template is skipped. That explicit opt-out helps on pages that shouldn't get the ` | Acme Store` suffix — a campaign landing page with its own branding.

### generateMetadata and the cost of duplicate requests

`generateMetadata` often fetches the same data as the page component itself. For example, `getProduct(id)` is needed for both the title and the content.

**Request Memoization** helps here (see the data fetching article): calling the same `fetch`- or `React.cache`-wrapped function twice does not trigger a second request. But that only holds if the function is actually memoized, not written as two independent direct DB (database) calls.

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

The sitemap protocol caps one file at 50,000 URLs. For a catalog above that, Next can **generate multiple sitemap files** through `generateSitemaps` — a detail even candidates who know `sitemap.ts` often miss.

## Structured Data (JSON-LD)

Next doesn't provide a dedicated API for structured data. JSON-LD (JSON for Linked Data) is plain JSON that you insert into a `<script type="application/ld+json">` through JSX:

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

Important: `dangerouslySetInnerHTML` is justified here because the content is server-serialized JSON, not user-supplied HTML.

But be careful if `product.name` can contain user input, such as a customizable product title. `JSON.stringify` does not escape `</script>` inside strings. A crafted title could therefore break out of the `<script>` tag and lead to XSS (cross-site scripting).

For controlled data from your own DB the risk is low, but it's a nuance worth raising in a senior interview.

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
- `sizes` tells the browser which variant of the generated `srcset` to pick, based on viewport width. Without it the browser may download an image larger than the one it displays.
- `placeholder="blur"` shows a blurred version (from `blurDataURL`, usually generated at build time) while the original loads — improves perceived performance.
- `priority` — for images in the first screenful (above the fold, visible without scrolling), it disables `loading="lazy"` and raises fetch priority. If that image is the LCP element (Largest Contentful Paint — the largest visible element on the page), the gain is usually measurable.

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

The classic web font problem has two shapes. The browser either shows the text in a system font (FOUT — Flash of Unstyled Text) or shows nothing (FOIT — Flash of Invisible Text). Either way, the text re-flows once the custom font loads, and that re-flow is CLS.

```tsx
import { Inter, Roboto_Mono } from 'next/font/google';

const inter = Inter({
  // 'cyrillic' matters: without it the font has no Russian glyphs
  subsets: ['latin', 'cyrillic'],
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

`next/font` does two things. First, it downloads the font **at build time** and serves it from your own domain as a static asset. So there is no runtime request to Google Fonts. That also improves privacy: the user's IP address is never sent to Google on a page load.

Second, it generates `@font-face` with `size-adjust`, which tunes the fallback font's metrics to take up almost the same space as the real font. That way the text barely moves when the real font swaps in, so CLS stays low.

## Core Web Vitals — what each Next mechanism specifically improves

| Metric | What it measures | Next.js lever |
|---|---|---|
| **LCP** (Largest Contentful Paint) | when the largest visible element appears | server rendering (SSR) or static generation (SSG); `next/image` with `priority`; `next/font` |
| **CLS** (Cumulative Layout Shift) | how much elements jump around | `next/image` with explicit `width`/`height`; `next/font`; no hydration mismatch |
| **INP** (Interaction to Next Paint) | delay before the page answers a click | less client-side JS thanks to Server Components |

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

Streaming doesn't hurt indexing. Googlebot waits for the full response before processing it, so it never "sees" the intermediate chunks a browser does. For a **real user** it is better than neutral. LCP can improve, because content critical for the first view (`ProductHeader`) is no longer blocked by the slower `Reviews`.

## Common interview mistakes

- **"It's enough to add `<title>` and `<meta description>`, the rest doesn't matter"** — that leaves out three things. The first is `metadataBase`; without it, relative URLs in Open Graph may resolve incorrectly. The second is `robots` and `sitemap`, which shape the crawl budget. The third is structured data, which gets you rich snippets.

- **Not knowing about metadata inheritance/merging across the layout tree** — and duplicating `title`/`description` in every `page.tsx` instead of using `title.template`.

- **"next/image reduces CLS on its own, without width/height"** — no. Space is reserved ahead of time only because you gave explicit `width` and `height`, or `fill` on a correctly positioned parent.

- **Confusing `priority` and `loading="lazy"`** — `priority` does more than "remove lazy loading". It also raises the browser's fetch priority (`fetchpriority="high"`), which directly affects LCP for images in the first screenful.

- **"next/font just loads the font faster"** — that misses the actual mechanism. It self-hosts at build time, so there is no runtime request to Google Fonts. It also tunes fallback font metrics to reduce CLS.

- **Can't connect LCP/CLS/INP to specific code-level decisions** — the answer stays abstract: "Next is good for performance". The concrete version: "SSR improves LCP because HTML with content arrives immediately, instead of after JS executes".

- **"Streaming hurts SEO because the page is delivered 'in pieces'"** — no. Search crawlers receive the full final HTML once streaming completes, not a half-loaded chunk. Streaming is transparent to them.
