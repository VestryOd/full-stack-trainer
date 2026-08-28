# Image Optimization

## Why images are the first place to start

Images account for **50–70% of a web page's total weight** on average. Image optimization is also one of the few areas where results come fast, are measurable, and need no refactoring.

Images push on three things at once:

- **LCP** — Largest Contentful Paint, the moment the largest visible element finishes rendering. On most pages that element is an image.
- **CLS** — Cumulative Layout Shift, how much the page jumps around while it loads. An image without declared dimensions is the classic cause.
- **Bandwidth**, which you pay for twice: on the bill from your CDN (content delivery network) and on the user's mobile plan.

Here is one hero image in three formats, measured on a 4G connection. TTFB (time to first byte) is the wait before the first byte of the file arrives.

| File | Size | TTFB + download |
|---|---|---|
| `hero.png` | 2.4 megabytes | 3.2 s |
| `hero.webp` | 380 kilobytes | 0.5 s |
| `hero.avif` | 210 kilobytes | 0.3 s |

Converting the format alone removes 91% of the bytes. All else being equal, it removes the same 91% from the image's share of LCP, and it costs zero lines of JavaScript.

## Image formats — when to use what

### Format selection matrix

Six formats matter in practice. JPEG (Joint Photographic Experts Group) and PNG (Portable Network Graphics) are the two every browser has always understood. Their modern replacements are WebP (Google's picture format for the web) and AVIF (a newer format with much stronger compression).

SVG (Scalable Vector Graphics) stores shapes instead of pixels, so it scales to any size without losing sharpness. GIF (Graphics Interchange Format) is the one row of the table to retire.

| Format | Compression | Transparency | Support | Best for |
|---|---|---|---|---|
| JPEG | lossy | no | 100% | photos without transparency |
| PNG | lossless | yes | 100% | screenshots, icons |
| WebP | both | yes | 97%+ | replacing JPEG and PNG |
| AVIF | both | yes | 93%+ | maximum compression |
| SVG | vector | yes | 100% | icons, logos |
| GIF | lossless | yes (1-bit) | 100% | nothing — replace it |

Replace an animated GIF with a WebP animation, or with a muted autoplaying video: `<video autoplay loop muted playsinline>`. In 2025 both are smaller and smoother than the original.

### WebP vs AVIF — what's the difference

WebP came out of Google in 2010 and is the safe production default today:

- 25–35% smaller than JPEG at the same visual quality.
- Support: Chrome 23+, Firefox 65+, Safari 14+.
- Fast to encode and fast to decode.

AVIF is the AV1 Image File Format, published by the Alliance for Open Media in 2019. Inside it sits a single frame compressed by AV1 (a royalty-free video codec).

- 40–60% smaller than JPEG, and 20–30% smaller than WebP.
- Support: Chrome 85+, Firefox 93+, Safari 16+.
- Slower to encode, which matters when the server generates images on demand.
- Faster to decode on devices with hardware AV1 support.
- Better at gradients and complex textures.

Hence the strategy: offer AVIF first, WebP second, JPEG or PNG last, and let the `<picture>` element choose.

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

A phone screen 375px wide at double pixel density needs a 750px image. Double density means a DPR (device pixel ratio) of 2 — the count of physical pixels per CSS pixel. A 1440px desktop screen at the same density needs 2880px, and one file cannot serve both cases well.

Send everyone the 2880px file and the phone downloads 2.4 megabytes where 200 kilobytes would do. The browser scales it back down, and the extra bytes are pure waste. Send everyone the 750px file and the image is blurry on every Retina desktop display.

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

The browser picks a file from `srcset` in three steps:

1. It reads `sizes` and works out the slot width. At a window width of 375px the first rule matches, `100vw`, so the slot is 375px.
2. It multiplies by the device pixel ratio: 375 × 2 = 750px.
3. It takes the smallest file in `srcset` that is at least 750px wide — here `/photo-800.webp`.

The same arithmetic on a desktop. At 1440px and density 1 the browser asks for 1440px and takes `/photo-1600.webp`. At 1440px and density 2 it asks for 2880px and takes the same `/photo-1600.webp`, because that is the largest file on offer.

Worth remembering: the browser **reserves the right** to take a different file. On a slow connection it may pick a smaller one than the arithmetic suggests. You supply the options, the browser makes the decision.

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

Take `<Image src="/photo.jpg" width={800} height={600} />`. Here is what happens:

1. Next.js renders an `<img>` whose `src` points at its own route `/_next/image`, with the path, width and quality as query parameters.
2. On the first request that route loads the original and converts it to WebP or AVIF. The format is chosen from the browser's `Accept` header.
3. The image is then resized to the requested width, and the result is cached on disk.
4. Every later request is served straight from that cache.
5. A CDN in front caches by URL, so width and quality are part of the cache key.

The price shows up on the first hit: a size nobody has asked for before means a cold start while the file is generated. Every request after that is instant.

## Image CDN — for dynamic content

When images are dynamic — uploaded by users, or coming from a CMS (content management system) — an image CDN does the work for you.

```ts
// Cloudinary — transformations via URL
const getCloudinaryUrl = (
  publicId: string,
  options: { width: number; quality?: number; format?: 'auto' | 'webp' | 'avif' }
) => {
  const { width, quality = 'auto', format = 'auto' } = options;
  const transform = `f_${format},q_${quality},w_${width}`;
  return `https://res.cloudinary.com/your-cloud/image/upload/${transform}/${publicId}`;
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

When the image is the LCP element, walk this list:

- `fetchpriority="high"` on the `<img>` tag.
- `loading="eager"`, or simply no `loading="lazy"`.
- A `<link rel="preload" as="image">` in the `<head>`.
- Format AVIF with a WebP fallback.
- Correct `srcset` and `sizes`, so a phone never gets a two-megabyte file.
- Width and height on the tag itself, which removes the layout shift.
- The file served from a CDN, for a low TTFB.
- The image is **not** a CSS background: the preload scanner cannot see `background-image`.

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

```bash
# imagemin — batch processing in the build
npm install imagemin imagemin-webp imagemin-avif
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

The **Network** panel: filter by `Img` to leave only images. The `Size` column shows what was actually downloaded, and the `Type` column shows what arrived — `image/webp`, or `image/jpeg` after all. Hovering a bar in the `Waterfall` column opens the timings, where `Content Download` is the image's own download time.

**Lighthouse** has four audits about images. "Serve images in next-gen formats" means there is no WebP or AVIF. "Properly size images" means the file is bigger than the slot it fills. "Efficiently encode images" means the compression is too weak. "Defer offscreen images" means lazy loading is missing.

The **Performance** panel: find the `Largest Contentful Paint` marker, click it and open `Related Node` to see which element the LCP turned out to be. Then look at when its download actually started.

To find the LCP element from the console:

```js
new PerformanceObserver(list => {
  const entries = list.getEntries();
  console.log('LCP element:', entries.at(-1));
}).observe({ type: 'largest-contentful-paint', buffered: true });
```

## Connection to other topics

- [Core Web Vitals](./01-core-web-vitals.md) — the image is usually the LCP element, and a missing width or height feeds CLS.
- [Resource Loading](./03-resource-loading.md) — preloading the LCP image, `fetchpriority`, lazy loading.
- [Performance Metrics](./02-performance-metrics.md) — file size affects TTFB when the server generates the image, and download time feeds LCP.
- [Caching Strategies](./07-caching-strategies.md) — CDN caching for images, and `Cache-Control` for static assets.

## Common interview traps

- **"WebP everywhere — solves all image problems"** — WebP beats JPEG, but it's not the maximum. AVIF delivers another 20–30% size reduction at the same quality. The right strategy is AVIF → WebP → JPEG via `<picture>`, not "switched to WebP and done."

- **"next/image automatically optimizes everything"** — not quite. You still add `priority={true}` by hand for the LCP image. The `sizes` attribute is still yours to specify, or Next.js generates variants larger than needed. Default `quality` is 75, which is sometimes too low for a hero image.

- **"srcset is just a list of different sizes"** — the browser decides which to use, factoring in the device's DPR, network speed, and user preferences. You provide the options; the final choice is the browser's. This matters because on a slow connection the browser may pick a smaller image even on a Retina display.

- **"I set width and height — CLS is gone"** — not always. CSS can override the dimensions. Rules like `img { width: 100%; height: auto; }` still shift the layout without an `aspect-ratio` or a fixed-size container. You need both halves: the HTML attributes and CSS that agrees with them.

- **"loading="lazy" on all images — saves bandwidth"** — `loading="lazy"` on the LCP image (first viewport) hurts LCP because the browser intentionally defers loading it. The opposite of what you want. Rule: lazy only below the fold.

- **"AVIF is the best format — using it everywhere"** — AVIF encodes slowly. With on-demand server-side generation (like in next/image), the first request will be noticeably slower than WebP. Fine for static build-time generation. Also, AVIF support is ~93% (Safari 16+) — a fallback is required.

- **"I optimized images — LCP improved"** — possibly, but LCP depends on four components (TTFB + resource load delay + resource load time + render delay). Reducing file size only helps "resource load time." If LCP is slow due to TTFB or a missing preload, format optimization won't help.
