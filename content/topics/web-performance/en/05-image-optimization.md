# Image Optimization

## Why images are the first place to start

Images account for **50–70% of a web page's total weight** on average. They directly affect three metrics at once: LCP (the main content), CLS (if dimensions are missing), and bandwidth costs (and CDN bills). Image optimization is also one of the few areas where you can see fast, measurable results without refactoring code.

```txt
Typical before/after:

  hero.png  — 2.4 MB, TTFB + download = 3.2s on 4G
  hero.webp — 380 KB, TTFB + download = 0.5s on 4G
  hero.avif — 210 KB, TTFB + download = 0.3s on 4G

  Format conversion = −91% file size, −91% LCP impact (all else equal)
  — without a single line of JavaScript
```

## Image formats — when to use what

### Format selection matrix

```txt
┌──────────┬──────────┬──────────────┬────────────┬──────────────────────┐
│ Format   │ Compress │ Transparency │ Support    │ Best for             │
├──────────┼──────────┼──────────────┼────────────┼──────────────────────┤
│ JPEG     │ lossy    │ no           │ 100%       │ photos without transp│
│ PNG      │ lossless │ yes          │ 100%       │ screenshots, icons   │
│ WebP     │ both     │ yes          │ 97%+       │ JPEG/PNG replacement │
│ AVIF     │ both     │ yes          │ 93%+       │ maximum compression  │
│ SVG      │ vector   │ yes          │ 100%       │ icons, logos         │
│ GIF      │ lossless │ yes (1-bit)  │ 100%       │ don't use            │
└──────────┴──────────┴──────────────┴────────────┴──────────────────────┘

GIF in 2025 — always replace with WebP animation
or <video autoplay loop muted playsinline>
```

### WebP vs AVIF — what's the difference

```txt
WebP (Google, 2010):
  - 25–35% smaller than JPEG at the same visual quality
  - Support: Chrome 23+, Firefox 65+, Safari 14+
  - Fast encoding and decoding
  - The safe production choice right now

AVIF (Alliance for Open Media, 2019, AV1 codec):
  - 40–60% smaller than JPEG (20–30% smaller than WebP)
  - Support: Chrome 85+, Firefox 93+, Safari 16+
  - Slower to encode (matters for on-demand server generation)
  - Faster to decode on devices with hardware AV1 support
  - Better at gradients and complex textures

Strategy:
  AVIF → WebP → JPEG/PNG (via <picture> element)
```

### <picture> — progressive enhancement by format

```html
<!-- Browser picks the FIRST supported format -->
<picture>
  <source srcset="/hero.avif" type="image/avif" />
  <source srcset="/hero.webp" type="image/webp" />
  <!-- Fallback for older browsers -->
  <img
    src="/hero.jpg"
    alt="Hero image"
    width="1200"
    height="600"
    fetchpriority="high"
  />
</picture>
```

```html
<!-- <picture> for art direction — different crops
     for different screen sizes -->
<picture>
  <!-- Mobile: square crop (portrait) -->
  <source
    media="(max-width: 600px)"
    srcset="/hero-square-400.avif 400w, /hero-square-800.avif 800w"
    type="image/avif"
  />
  <!-- Desktop: widescreen (16:9) -->
  <source
    media="(min-width: 601px)"
    srcset="/hero-wide-800.avif 800w, /hero-wide-1600.avif 1600w"
    type="image/avif"
  />
  <img src="/hero-wide-1600.jpg" alt="Hero" width="1600" height="900" />
</picture>
```

## Responsive Images — srcset and sizes

### Why a single image isn't enough

```txt
The problem:
  375px screen (iPhone) → needs a 750px image (2x DPR)
  1440px screen (desktop) → needs a 2880px image (2x DPR)

  Serving everyone the 2880px image:
  - Mobile downloads 2.4MB instead of 200KB
  - Browser scales it down — pure bandwidth waste

  Serving everyone the 750px image:
  - Blurry on Retina desktop displays
```

```html
<!-- srcset: list of variants with their physical widths -->
<img
  src="/photo-800.webp"
  srcset="
    /photo-400.webp  400w,
    /photo-800.webp  800w,
    /photo-1200.webp 1200w,
    /photo-1600.webp 1600w
  "
  sizes="
    (max-width: 600px)  100vw,
    (max-width: 1024px) 50vw,
    800px
  "
  alt="Product photo"
  width="800"
  height="600"
/>
```

```txt
How the browser picks from srcset:

  1. Checks sizes: at window width 375px → "100vw" → 375px
  2. Accounts for device DPR: 375px × 2 DPR = 750px
  3. Picks the smallest file from srcset that is >= 750px
     → /photo-800.webp (800w)

  At width 1440px, 1x DPR → 1440 × 1 = 1440px
  → /photo-1600.webp (1600w)

  At width 1440px, 2x DPR → 1440 × 2 = 2880px
  → /photo-1600.webp (nearest available)

  Important: the browser RESERVES THE RIGHT to choose a
  different file (e.g. a smaller one on a slow connection).
  It's the browser's decision, not yours.
```

### Generating size variants — sharp

```ts
import sharp from 'sharp';

const widths = [400, 800, 1200, 1600];
const formats: Array<'webp' | 'avif'> = ['avif', 'webp'];

async function generateResponsiveImages(
  inputPath: string,
  outputDir: string,
  name: string,
): Promise<void> {
  const image = sharp(inputPath);
  const metadata = await image.metadata();

  for (const width of widths) {
    // Don't upscale — skip if original is smaller
    if (metadata.width && width > metadata.width) continue;

    for (const format of formats) {
      await image
        .resize(width)
        [format]({
          quality: format === 'avif' ? 60 : 80,
          effort: format === 'avif' ? 4 : 6, // speed/size trade-off
        })
        .toFile(`${outputDir}/${name}-${width}.${format}`);
    }

    // JPEG fallback
    await image
      .resize(width)
      .jpeg({ quality: 85, progressive: true })
      .toFile(`${outputDir}/${name}-${width}.jpg`);
  }
}
```

## next/image — batteries included

`next/image` automatically handles most problems: format conversion, responsive sizes, lazy loading, CLS prevention.

```ts
import Image from 'next/image';

// ✅ LCP image — priority={true}
// Adds fetchpriority="high" + <link rel="preload">
// Do NOT add loading="lazy"
<Image
  src="/hero.jpg"
  priority={true}       // ← required for LCP
  width={1200}
  height={600}
  alt="Hero"
  quality={85}          // default: 75; higher for hero images
/>
```

```ts
// ✅ Below-fold images — no priority (lazy by default)
<Image
  src="/product.jpg"
  width={400}
  height={400}
  alt="Product"
  // sizes helps Next.js pick the right variant
  sizes="(max-width: 768px) 100vw, 400px"
/>
```

```ts
// ✅ fill — for images that fill a container
// (when you don't know the size in advance)
<div style={{ position: 'relative', aspectRatio: '16/9' }}>
  <Image
    src="/banner.jpg"
    fill
    style={{ objectFit: 'cover' }}
    sizes="100vw"
    alt="Banner"
  />
</div>
```

```ts
// ✅ placeholder="blur" — shows a blurred version while
// the full image loads (eliminates CLS)
import heroImage from '/public/hero.jpg'; // static import

<Image
  src={heroImage}
  placeholder="blur"   // blurDataURL generated automatically
  alt="Hero"
  priority={true}
/>

// For external URLs — provide explicit blurDataURL
<Image
  src="https://cdn.example.com/photo.jpg"
  placeholder="blur"
  blurDataURL="data:image/jpeg;base64,/9j/4AAQ..." // generate via plaiceholder
  width={800}
  height={600}
  alt="Photo"
/>
```

### Configuring next/image for external domains

```ts
// next.config.ts
export default {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'cdn.example.com',
        pathname: '/images/**',
      },
    ],
    // Formats in priority order (browser picks the first supported)
    formats: ['image/avif', 'image/webp'],
    // Breakpoints for srcset generation
    deviceSizes: [640, 750, 828, 1080, 1200, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },
};
```

### How next/image works under the hood

```txt
Request: <Image src="/photo.jpg" width={800} height={600} />

1. Next.js renders <img src="/_next/image?url=/photo.jpg&w=828&q=75">
2. On first request, the /_next/image API route:
   - Loads the original /photo.jpg
   - Converts to WebP/AVIF (based on browser's Accept header)
   - Resizes to the requested width
   - Caches the result on disk
3. Subsequent requests: served from cache
4. CDN caches by URL (including w= and q= params)

Downside: first request for a new size = cold start (generation)
Upside: subsequent requests = instant from cache
```

## Image CDN — for dynamic content

When images are dynamic (user-generated, CMS content), use an Image CDN:

```ts
// Cloudinary — transformations via URL
const getCloudinaryUrl = (
  publicId: string,
  options: { width: number; quality?: number; format?: 'auto' | 'webp' | 'avif' }
) => {
  const { width, quality = 'auto', format = 'auto' } = options;
  return `https://res.cloudinary.com/your-cloud/image/upload/f_${format},q_${quality},w_${width}/${publicId}`;
};

// Usage in a component
<img
  srcset={`
    ${getCloudinaryUrl('hero', { width: 400 })} 400w,
    ${getCloudinaryUrl('hero', { width: 800 })} 800w,
    ${getCloudinaryUrl('hero', { width: 1200 })} 1200w
  `}
  sizes="(max-width: 600px) 100vw, 800px"
  src={getCloudinaryUrl('hero', { width: 800 })}
  alt="Hero"
/>
```

```ts
// Imgix — same approach
const getImgixUrl = (path: string, params: Record<string, string | number>) => {
  const query = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  );
  return `https://your-domain.imgix.net${path}?${query}`;
};

const url = getImgixUrl('/hero.jpg', {
  w: 800,
  h: 600,
  fit: 'crop',
  fm: 'avif',    // format
  q: 80,
  auto: 'compress',
});
```

## LCP image optimization — checklist

```txt
For the image that is the LCP element:

  □ fetchpriority="high" on the <img>
  □ loading="eager" (or simply no loading="lazy")
  □ <link rel="preload" as="image"> in <head>
  □ Format: AVIF with WebP fallback
  □ Correct srcset + sizes (don't send 2MB to mobile)
  □ Width and height specified (prevents CLS)
  □ Image served from CDN (low TTFB)
  □ Image is NOT a CSS background
    (the preload scanner can't see background-image)
```

```html
<!-- ✅ The complete "ideal" LCP element -->
<head>
  <!-- Preload: tells the browser before CSS/JS are parsed -->
  <link
    rel="preload"
    as="image"
    href="/hero.avif"
    imagesrcset="/hero-400.avif 400w, /hero-800.avif 800w, /hero-1600.avif 1600w"
    imagesizes="(max-width: 600px) 100vw, (max-width: 1024px) 50vw, 1200px"
  />
</head>
<body>
  <picture>
    <source
      srcset="/hero-400.avif 400w, /hero-800.avif 800w, /hero-1600.avif 1600w"
      type="image/avif"
      sizes="(max-width: 600px) 100vw, (max-width: 1024px) 50vw, 1200px"
    />
    <source
      srcset="/hero-400.webp 400w, /hero-800.webp 800w, /hero-1600.webp 1600w"
      type="image/webp"
      sizes="(max-width: 600px) 100vw, (max-width: 1024px) 50vw, 1200px"
    />
    <img
      src="/hero-1600.jpg"
      width="1600"
      height="900"
      fetchpriority="high"
      loading="eager"
      alt="Hero image"
      decoding="async"
    />
  </picture>
</body>
```

## Lazy Loading — applying it correctly

```html
<!-- Rule: all images except those in the first viewport -->

<!-- ✅ Correct: below-fold with dimensions -->
<img
  src="/product-1.webp"
  loading="lazy"
  width="400"
  height="400"
  alt="Product"
/>

<!-- ❌ Wrong: lazy without dimensions → CLS -->
<img src="/product-1.webp" loading="lazy" alt="Product" />

<!-- ❌ Wrong: lazy on the LCP image -->
<img src="/hero.webp" loading="lazy" alt="Hero" />
```

```ts
// When native loading="lazy" isn't enough —
// for example, you want to start loading before
// the element enters the viewport
function LazyImage({
  src,
  alt,
  width,
  height,
}: {
  src: string;
  alt: string;
  width: number;
  height: number;
}) {
  const ref = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const img = ref.current;
    if (!img) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          // Start loading 500px before entering the viewport
          img.src = src;
          observer.disconnect();
        }
      },
      { rootMargin: '500px' }
    );

    observer.observe(img);
    return () => observer.disconnect();
  }, [src]);

  return (
    <img
      ref={ref}
      alt={alt}
      width={width}
      height={height}
      onLoad={() => setLoaded(true)}
      style={{ opacity: loaded ? 1 : 0, transition: 'opacity 0.3s' }}
    />
  );
}
```

## Compression and conversion tools

```bash
# sharp — the most performant Node.js image library
npm install sharp

# CLI (for build scripts)
npx sharp-cli --input hero.jpg --output hero.webp --format webp --quality 80
npx sharp-cli --input hero.jpg --output hero.avif --format avif --quality 60
```

```bash
# squoosh CLI — from Google, excellent AVIF quality
npm install -g @squoosh/cli
squoosh-cli --avif '{"cqLevel":33}' hero.jpg
squoosh-cli --webp '{"quality":80}' hero.jpg
```

```ts
// Image optimization script for CI/CD
import imagemin from 'imagemin';
import imageminWebp from 'imagemin-webp';
import imageminAvif from 'imagemin-avif';

await imagemin(['public/images/**/*.{jpg,png}'], {
  destination: 'public/images/optimized',
  plugins: [
    imageminWebp({ quality: 80 }),
    imageminAvif({ quality: 60 }),
  ],
});
```

## DevTools workflow for images

```txt
Chrome DevTools → Network tab:
  1. Filter "Img" → shows only images
  2. "Size" column: actual downloaded size
  3. "Type" column: verify format (image/webp? or image/jpeg?)
  4. Hover over the Waterfall bar → Timing:
     "Content Download" = how long the image took to download

Chrome DevTools → Lighthouse:
  → "Serve images in next-gen formats" — no WebP/AVIF
  → "Properly size images" — image larger than needed
  → "Efficiently encode images" — insufficient compression
  → "Defer offscreen images" — missing lazy loading

Chrome DevTools → Performance:
  → "Largest Contentful Paint" marker
  → Click it → "Related Node" → which element is the LCP
  → Look at when its download actually started

Console commands:
  // Find the current LCP element
  new PerformanceObserver(list => {
    const entries = list.getEntries();
    console.log('LCP element:', entries.at(-1));
  }).observe({ type: 'largest-contentful-paint', buffered: true });
```

## Connection to other topics

```txt
[Core Web Vitals]         — images are the primary LCP element;
                            missing width/height → CLS
[Resource Loading]        — preload for LCP image;
                            fetchpriority; lazy loading
[Performance Metrics]     — image size affects TTFB
                            (if server-generated),
                            download time → LCP
[Caching Strategies]      — CDN caching for images;
                            Cache-Control for static assets
```

## Common interview traps

- **"WebP everywhere — solves all image problems"** — WebP beats JPEG, but it's not the maximum. AVIF delivers another 20–30% size reduction at the same quality. The right strategy is AVIF → WebP → JPEG via `<picture>`, not "switched to WebP and done."

- **"next/image automatically optimizes everything"** — not quite. `priority={true}` must be added manually for the LCP image. `sizes` must be specified explicitly — otherwise Next.js generates oversized variants. `quality` defaults to 75 — sometimes needs to be higher for hero images.

- **"srcset is just a list of different sizes"** — the browser decides which to use, factoring in the device's DPR, network speed, and user preferences. You provide the options; the final choice is the browser's. This matters because on a slow connection the browser may pick a smaller image even on a Retina display.

- **"I set width/height — CLS is gone"** — not always. CSS can override the dimensions: `img { width: 100%; height: auto; }` without `aspect-ratio` or a fixed-size container will still cause CLS if the image hasn't loaded before the first render. You need both: HTML attributes AND matching CSS.

- **"loading="lazy" on all images — saves bandwidth"** — `loading="lazy"` on the LCP image (first viewport) hurts LCP because the browser intentionally defers loading it. The opposite of what you want. Rule: lazy only below the fold.

- **"AVIF is the best format — using it everywhere"** — AVIF encodes slowly. With on-demand server-side generation (like in next/image), the first request will be noticeably slower than WebP. Fine for static build-time generation. Also, AVIF support is ~93% (Safari 16+) — a fallback is required.

- **"I optimized images — LCP improved"** — possibly, but LCP depends on four components (TTFB + resource load delay + resource load time + render delay). Reducing file size only helps "resource load time." If LCP is slow due to TTFB or a missing preload, format optimization won't help.
