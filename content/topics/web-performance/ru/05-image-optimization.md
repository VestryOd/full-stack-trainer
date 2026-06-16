<!-- verified: 2026-06-16, corrections: 0 -->
# Image Optimization

## Почему изображения — первое, с чего начинают

Изображения в среднем составляют **50–70% веса** веб-страницы. Они напрямую влияют на три метрики одновременно: LCP (главный контент), CLS (если нет размеров), трафик (и деньги на CDN). При этом оптимизация изображений — одна из немногих областей, где можно получить быстрый результат без рефакторинга кода.

```txt
Типичный "до/после":

  hero.png  — 2.4 MB, TTFB + download = 3.2s при 4G
  hero.webp — 380 KB, TTFB + download = 0.5s при 4G
  hero.avif — 210 KB, TTFB + download = 0.3s при 4G

  Конвертация формата = −91% размера, −91% LCP (при прочих равных)
  — без единой строки JavaScript
```

## Форматы изображений — когда что использовать

### Матрица выбора формата

```txt
┌──────────┬──────────┬──────────────┬────────────┬──────────────────┐
│ Формат   │ Сжатие   │ Прозрачность │ Поддержка  │ Лучше всего для  │
├──────────┼──────────┼──────────────┼────────────┼──────────────────┤
│ JPEG     │ lossy    │ нет          │ 100%       │ фото без прозр.  │
│ PNG      │ lossless │ да           │ 100%       │ скриншоты, иконки│
│ WebP     │ оба      │ да           │ 97%+       │ замена JPEG/PNG  │
│ AVIF     │ оба      │ да           │ 93%+       │ максимум сжатия  │
│ SVG      │ vector   │ да           │ 100%       │ иконки, логотипы │
│ GIF      │ lossless │ да (1 бит)   │ 100%       │ не использовать  │
└──────────┴──────────┴──────────────┴────────────┴──────────────────┘

GIF в 2025 году — всегда заменяйте на WebP-анимацию
или на <video autoplay loop muted playsinline>
```

### WebP vs AVIF — в чём разница

```txt
WebP (Google, 2010):
  - 25–35% меньше JPEG при том же визуальном качестве
  - Поддержка: Chrome 23+, Firefox 65+, Safari 14+
  - Быстрое кодирование и декодирование
  - Безопасный выбор для production уже сейчас

AVIF (Alliance for Open Media, 2019, кодек AV1):
  - 40–60% меньше JPEG (20–30% меньше WebP)
  - Поддержка: Chrome 85+, Firefox 93+, Safari 16+
  - Медленнее кодируется (важно при серверной генерации)
  - Быстрее декодируется на устройствах с аппаратным AV1
  - Лучше работает с градиентами и сложными текстурами

Стратегия:
  AVIF → WebP → JPEG/PNG (через <picture> element)
```

### <picture> — прогрессивное улучшение по формату

```html
<!-- Браузер выбирает ПЕРВЫЙ поддерживаемый формат -->
<picture>
  <source srcset="/hero.avif" type="image/avif" />
  <source srcset="/hero.webp" type="image/webp" />
  <!-- Fallback для старых браузеров -->
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
<!-- <picture> для art direction — разные кадрирования
     на разных размерах экрана -->
<picture>
  <!-- Мобильный: квадратное кадрирование (портрет) -->
  <source
    media="(max-width: 600px)"
    srcset="/hero-square-400.avif 400w, /hero-square-800.avif 800w"
    type="image/avif"
  />
  <!-- Desktop: широкоформатное (16:9) -->
  <source
    media="(min-width: 601px)"
    srcset="/hero-wide-800.avif 800w, /hero-wide-1600.avif 1600w"
    type="image/avif"
  />
  <img src="/hero-wide-1600.jpg" alt="Hero" width="1600" height="900" />
</picture>
```

## Responsive Images — srcset и sizes

### Почему одного изображения недостаточно

```txt
Проблема:
  Экран 375px (iPhone) → нужна картинка 750px (2x DPR)
  Экран 1440px (desktop) → нужна картинка 2880px (2x DPR)

  Отдать всем 2880px картинку:
  - Мобильный скачает 2.4MB вместо 200KB
  - Браузер масштабирует её вниз — пустая трата трафика

  Отдать всем 750px:
  - На Retina desktop картинка размытая
```

```html
<!-- srcset: список вариантов с их физической шириной -->
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
Как браузер выбирает из srcset:

  1. Смотрит sizes: при ширине окна 375px → "100vw" → 375px
  2. Учитывает DPR устройства: 375px × 2 DPR = 750px
  3. Выбирает из srcset наименьший файл >= 750px
     → /photo-800.webp (800w)

  При ширине 1440px, 1x DPR → 1440 × 1 = 1440px
  → /photo-1600.webp (1600w)

  При ширине 1440px, 2x DPR → 1440 × 2 = 2880px
  → /photo-1600.webp (ближайший сверху)

  Важно: браузер СОХРАНЯЕТ ПРАВО выбрать другой файл
  (например, при медленном соединении выбрать меньший).
  Это его решение, не ваше.
```

### Генерация вариантов размеров — sharp

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
    // Не апскейлить — пропустить если оригинал меньше
    if (metadata.width && width > metadata.width) continue;

    for (const format of formats) {
      await image
        .resize(width)
        [format]({
          quality: format === 'avif' ? 60 : 80,
          effort: format === 'avif' ? 4 : 6, // баланс скорость/размер
        })
        .toFile(`${outputDir}/${name}-${width}.${format}`);
    }

    // JPEG-фолбек
    await image
      .resize(width)
      .jpeg({ quality: 85, progressive: true })
      .toFile(`${outputDir}/${name}-${width}.jpg`);
  }
}
```

## next/image — всё включено

`next/image` автоматически решает большинство проблем: конвертация форматов, адаптивные размеры, lazy loading, предотвращение CLS.

```ts
import Image from 'next/image';

// ✅ LCP-изображение — priority={true}
// Добавляет fetchpriority="high" + <link rel="preload">
// НЕ добавлять loading="lazy"
<Image
  src="/hero.jpg"
  priority={true}       // ← обязательно для LCP
  width={1200}
  height={600}
  alt="Hero"
  quality={85}          // default: 75; для hero можно выше
/>
```

```ts
// ✅ Изображения ниже fold — без priority (lazy по умолчанию)
<Image
  src="/product.jpg"
  width={400}
  height={400}
  alt="Product"
  // sizes помогает Next.js выбрать правильный вариант
  sizes="(max-width: 768px) 100vw, 400px"
/>
```

```ts
// ✅ fill — для изображений, занимающих контейнер
// (не знаем заранее размер)
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
// ✅ placeholder="blur" — показывает размытую версию
// пока грузится полная (устраняет CLS)
import heroImage from '/public/hero.jpg'; // статический импорт

<Image
  src={heroImage}
  placeholder="blur"   // blurDataURL генерируется автоматически
  alt="Hero"
  priority={true}
/>

// Для внешних URL — нужен явный blurDataURL
<Image
  src="https://cdn.example.com/photo.jpg"
  placeholder="blur"
  blurDataURL="data:image/jpeg;base64,/9j/4AAQ..." // сгенерировать через plaiceholder
  width={800}
  height={600}
  alt="Photo"
/>
```

### Настройка next/image для внешних доменов

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
    // Форматы в порядке приоритета (браузер выберет первый поддерживаемый)
    formats: ['image/avif', 'image/webp'],
    // Устройства для генерации srcset
    deviceSizes: [640, 750, 828, 1080, 1200, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },
};
```

### Как next/image работает под капотом

```txt
Запрос: <Image src="/photo.jpg" width={800} height={600} />

1. Next.js рендерит <img> с src="/_next/image?url=/photo.jpg&w=828&q=75"
2. При первом запросе: API route /_next/image:
   - Загружает оригинальный /photo.jpg
   - Конвертирует в WebP/AVIF (зависит от Accept заголовка браузера)
   - Ресайзит до запрошенной ширины
   - Кэширует результат на диске
3. При последующих запросах: отдаёт из кэша
4. CDN кэширует по URL (включая w= и q= параметры)

Минус: первый запрос с нового размера — cold start (генерация)
Плюс: последующие — мгновенно из кэша
```

## Image CDN — альтернатива для нестатичного контента

Когда изображения динамические (user-generated, контент из CMS), нужен Image CDN:

```ts
// Cloudinary — трансформации через URL
const getCloudinaryUrl = (
  publicId: string,
  options: { width: number; quality?: number; format?: 'auto' | 'webp' | 'avif' }
) => {
  const { width, quality = 'auto', format = 'auto' } = options;
  return `https://res.cloudinary.com/your-cloud/image/upload/f_${format},q_${quality},w_${width}/${publicId}`;
};

// Использование в компоненте
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
// Imgix — аналогичный подход
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
  fm: 'avif',  // format
  q: 80,
  auto: 'compress',
});
```

## LCP-оптимизация изображений — чеклист

```txt
Для изображения, которое является LCP-элементом:

  □ fetchpriority="high" на <img>
  □ loading="eager" (или отсутствие loading="lazy")
  □ <link rel="preload" as="image"> в <head>
  □ Формат: AVIF с fallback на WebP
  □ Правильный srcset + sizes (не грузить 2MB на мобильном)
  □ Ширина/высота указаны (предотвращает CLS)
  □ Изображение на CDN (низкий TTFB)
  □ Изображение НЕ через CSS background
    (preload scanner не видит background)
```

```html
<!-- ✅ Полный "идеальный" LCP-элемент -->
<head>
  <!-- Preload: сообщаем браузеру ещё до парсинга CSS/JS -->
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

## Lazy Loading — правильное применение

```html
<!-- Правило: все изображения кроме тех, что в первом экране -->

<!-- ✅ Правильно: below-fold с размерами -->
<img
  src="/product-1.webp"
  loading="lazy"
  width="400"
  height="400"
  alt="Product"
/>

<!-- ❌ Неправильно: lazy без размеров → CLS -->
<img src="/product-1.webp" loading="lazy" alt="Product" />

<!-- ❌ Неправильно: lazy на LCP -->
<img src="/hero.webp" loading="lazy" alt="Hero" />
```

```ts
// Когда нативного loading="lazy" недостаточно —
// например, нужно предзагружать при приближении к вьюпорту
// а не только при входе в него
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
          // Начать загрузку за 500px до вхождения во вьюпорт
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

## Инструменты сжатия и конвертации

```bash
# sharp — наиболее производительная Node.js библиотека
npm install sharp

# CLI (для скриптов сборки)
npx sharp-cli --input hero.jpg --output hero.webp --format webp --quality 80
npx sharp-cli --input hero.jpg --output hero.avif --format avif --quality 60
```

```bash
# squoosh CLI — Google, отличное качество AVIF
npm install -g @squoosh/cli
squoosh-cli --avif '{"cqLevel":33}' hero.jpg
squoosh-cli --webp '{"quality":80}' hero.jpg
```

```bash
# imagemin — батч-обработка в сборке
npm install imagemin imagemin-webp imagemin-avif
```

```ts
// Скрипт оптимизации изображений для CI/CD
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

## DevTools-воркфлоу для изображений

```txt
Chrome DevTools → Network tab:
  1. Фильтр "Img" → видим только изображения
  2. Колонка "Size": смотрим фактический размер скачанного
  3. Колонка "Type": проверяем формат (image/webp? или image/jpeg?)
  4. Hover на Waterfall-баре → Timing:
     "Content Download" = сколько времени качалось изображение

Chrome DevTools → Lighthouse:
  → "Serve images in next-gen formats" — нет WebP/AVIF
  → "Properly size images" — изображение больше чем нужно
  → "Efficiently encode images" — недостаточное сжатие
  → "Defer offscreen images" — нет lazy loading

Chrome DevTools → Performance:
  → "Largest Contentful Paint" маркер
  → Кликнуть → "Related Node" → какой элемент является LCP
  → Смотреть когда именно начался его download

Команды в консоли:
  // Найти текущий LCP-элемент
  new PerformanceObserver(list => {
    const entries = list.getEntries();
    console.log('LCP element:', entries.at(-1));
  }).observe({ type: 'largest-contentful-paint', buffered: true });
```

## Связь с другими темами

```txt
[Core Web Vitals]         — изображения — главный LCP-элемент;
                            без width/height → CLS
[Resource Loading]        — preload для LCP-картинки;
                            fetchpriority; lazy loading
[Performance Metrics]     — размер изображений влияет
                            на TTFB (если с сервера),
                            download time → LCP
[Caching Strategies]      — CDN кэширование изображений;
                            Cache-Control для статики
```

## Типичные ошибки на интервью

- **"WebP везде — решение всех проблем с изображениями"** — WebP лучше JPEG, но не максимум. AVIF даёт ещё 20–30% сжатия при той же качестве. Правильная стратегия: AVIF → WebP → JPEG через `<picture>`, а не "перешёл на WebP и готово".

- **"next/image автоматически оптимизирует всё"** — нет. `priority={true}` нужно добавить вручную для LCP-изображения. `sizes` нужно указывать явно — иначе Next.js генерирует слишком большие варианты. `quality` по умолчанию 75 — иногда нужно поднять для hero-image.

- **"srcset — это просто список разных размеров"** — браузер сам решает какой выбрать, и учитывает DPR устройства, скорость сети, User Preferences. Вы предлагаете варианты; финальный выбор — за браузером. Это важно понимать, потому что на медленном соединении браузер может выбрать меньшую картинку даже на Retina-экране.

- **"Указал width/height — CLS исчез"** — не всегда. CSS может переопределить размеры: `img { width: 100%; height: auto; }` без `aspect-ratio` или контейнера с фиксированным размером всё равно вызовет CLS если картинка не загрузилась к первому рендеру. Нужна связка: атрибуты + CSS.

- **"loading="lazy" на все картинки — экономия трафика"** — loading="lazy" на LCP-картинку (первый экран) ухудшает LCP, потому что браузер намеренно откладывает её загрузку. Обратный эффект. Правило: lazy только ниже fold.

- **"AVIF — лучший формат, использую везде"** — AVIF медленно кодируется. При server-side генерации по запросу (как в next/image) первый запрос будет заметно медленнее WebP. Для статической генерации при сборке — норм. Также поддержка AVIF ≈ 93% (Safari 16+) — нужен fallback.

- **"Оптимизировал изображения — LCP улучшился"** — возможно, но LCP зависит от 4 компонентов (TTFB + resource load delay + resource load time + render delay). Уменьшение размера файла помогает только с "resource load time". Если LCP тормозит из-за TTFB или отсутствия preload — оптимизация формата не поможет.
