<!-- verified: 2026-06-16, corrections: 0 -->
# Image Optimization

## Почему изображения — первое, с чего начинают

Изображения в среднем составляют **50–70% веса** веб-страницы. Оптимизация изображений — одна из немногих областей, где результат виден быстро и измеримо, и ради него не нужно переписывать код.

Изображения давят сразу на три вещи:

- **LCP** — Largest Contentful Paint, момент, когда дорисовался самый крупный видимый элемент. Чаще всего этот элемент и есть картинка.
- **CLS** — Cumulative Layout Shift, насколько страница дёргается, пока грузится. Картинка без указанных размеров — классическая причина.
- **Трафик**, за который вы платите дважды: счётом от CDN (сети доставки контента) и мобильным пакетом пользователя.

Вот одна и та же картинка в трёх форматах, замер на 4G. TTFB — это время до первого байта: сколько браузер ждёт, прежде чем файл начнёт приходить.

| Файл | Размер | TTFB + загрузка |
|---|---|---|
| `hero.png` | 2,4 мегабайта | 3,2 с |
| `hero.webp` | 380 килобайт | 0,5 с |
| `hero.avif` | 210 килобайт | 0,3 с |

Одна только смена формата убирает 91% байтов. При прочих равных она убирает те же 91% из вклада картинки в LCP, и стоит это ноль строк JavaScript.

## Форматы изображений — когда что использовать

### Матрица выбора формата

На практике важны шесть форматов. JPEG — это классический формат для фотографий, а PNG — формат сжатия без потерь. Оба понимает любой браузер, и так было всегда. Современная замена им — WebP (формат Google для веба) и AVIF (более новый формат, который сжимает заметно сильнее).

SVG — векторный формат: он хранит не пиксели, а фигуры, поэтому масштабируется до любого размера без потери резкости. GIF — древний формат анимации, и это единственная строка таблицы, от которой пора отказаться.

| Формат | Сжатие | Прозрачность | Поддержка | Лучше всего для |
|---|---|---|---|---|
| JPEG | с потерями | нет | 100% | фото без прозрачности |
| PNG | без потерь | да | 100% | скриншоты, иконки |
| WebP | оба | да | 97%+ | замена JPEG и PNG |
| AVIF | оба | да | 93%+ | максимум сжатия |
| SVG | вектор | да | 100% | иконки, логотипы |
| GIF | без потерь | да (1 бит) | 100% | ничего — заменяйте |

Анимированный GIF заменяйте на WebP-анимацию или на беззвучное видео с автозапуском: `<video autoplay loop muted playsinline>`. В 2025 году оба варианта меньше по размеру и плавнее.

### WebP vs AVIF — в чём разница

WebP появился в Google в 2010 году и сегодня остаётся безопасным выбором для реальных проектов:

- На 25–35% меньше JPEG при том же визуальном качестве.
- Поддержка: Chrome 23+, Firefox 65+, Safari 14+.
- Быстро кодируется и быстро декодируется.

AVIF — это AV1 Image File Format, опубликованный Alliance for Open Media в 2019 году. Внутри лежит один кадр, сжатый кодеком AV1 (свободный от лицензионных отчислений видеокодек).

- На 40–60% меньше JPEG и на 20–30% меньше WebP.
- Поддержка: Chrome 85+, Firefox 93+, Safari 16+.
- Кодируется медленнее — это важно, если сервер генерирует картинки по запросу.
- Декодируется быстрее на устройствах с аппаратной поддержкой AV1.
- Лучше работает с градиентами и сложными текстурами.

Отсюда стратегия: сначала предлагаем AVIF, потом WebP, в конце JPEG или PNG — а выбирает элемент `<picture>`.

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

Экран телефона шириной 375px с двойной плотностью пикселей требует картинку на 750px. Двойная плотность — это DPR (device pixel ratio), отношение физических пикселей к CSS-пикселям. Экран десктопа на 1440px с той же плотностью требует уже 2880px, и одним файлом оба случая хорошо не закрыть.

Отдадите всем файл на 2880px — телефон скачает 2,4 мегабайта там, где хватило бы 200 килобайт. Браузер уменьшит картинку, и лишние байты пропадут зря. Отдадите всем файл на 750px — на Retina-экране десктопа картинка будет размытой.

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

Браузер выбирает файл из `srcset` в три шага:

1. Смотрит `sizes` и вычисляет ширину слота. При ширине окна 375px срабатывает первое правило, `100vw`, и слот равен 375px.
2. Умножает на плотность пикселей устройства: 375 × 2 = 750px.
3. Берёт из `srcset` наименьший файл шириной не меньше 750px — здесь это `/photo-800.webp`.

Та же арифметика на десктопе. При 1440px и плотности 1 браузер просит 1440px и берёт `/photo-1600.webp`. При 1440px и плотности 2 он просит 2880px и берёт тот же `/photo-1600.webp`, потому что это самый большой файл из предложенных.

Важно помнить: браузер **оставляет за собой право** взять другой файл. На медленном соединении он может выбрать вариант меньше, чем показывает арифметика. Вы предлагаете варианты, решение принимает браузер.

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

Возьмём `<Image src="/photo.jpg" width={800} height={600} />`. Дальше происходит вот что:

1. Next.js рендерит `<img>`, у которого `src` указывает на собственный маршрут `/_next/image`, а путь, ширина и качество едут в параметрах запроса.
2. При первом запросе этот маршрут загружает оригинал и конвертирует его в WebP или AVIF. Формат выбирается по заголовку `Accept` от браузера.
3. Затем картинка уменьшается до запрошенной ширины, а результат кладётся в кэш на диске.
4. Все последующие запросы обслуживаются прямо из этого кэша.
5. CDN перед приложением кэширует по URL, поэтому ширина и качество входят в ключ кэша.

Плата за это видна на первом обращении: размер, которого ещё никто не просил, означает холодный старт и генерацию файла. Все запросы после него — мгновенные.

## Image CDN — альтернатива для нестатичного контента

Когда изображения динамические — их загружают пользователи или они приходят из CMS (системы управления контентом), — работу берёт на себя специализированный CDN для картинок.

```ts
// Cloudinary — трансформации через URL
const getCloudinaryUrl = (
  publicId: string,
  options: { width: number; quality?: number; format?: 'auto' | 'webp' | 'avif' }
) => {
  const { width, quality = 'auto', format = 'auto' } = options;
  const transform = `f_${format},q_${quality},w_${width}`;
  return `https://res.cloudinary.com/your-cloud/image/upload/${transform}/${publicId}`;
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

Если картинка и есть LCP-элемент, пройдитесь по списку:

- `fetchpriority="high"` на теге `<img>`.
- `loading="eager"` — или просто отсутствие `loading="lazy"`.
- `<link rel="preload" as="image">` в `<head>`.
- Формат AVIF с запасным вариантом WebP.
- Правильные `srcset` и `sizes`, чтобы на телефон не уезжал файл на два мегабайта.
- Ширина и высота прямо в теге — это снимает сдвиг макета.
- Файл отдаётся с CDN, ради низкого TTFB.
- Картинка **не** является CSS-фоном: сканер предзагрузки не видит `background-image`.

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

Панель **Network**: фильтр `Img` оставляет только изображения. Колонка `Size` показывает, сколько реально скачано, а колонка `Type` — что именно пришло: `image/webp` или всё-таки `image/jpeg`. Наведение на полосу в колонке `Waterfall` открывает тайминги, где `Content Download` — это время самой загрузки картинки.

В **Lighthouse** про изображения есть четыре проверки. "Serve images in next-gen formats" означает, что нет WebP и AVIF. "Properly size images" — файл больше, чем место, куда его вставили. "Efficiently encode images" — сжатие слишком слабое. "Defer offscreen images" — не хватает ленивой загрузки.

Панель **Performance**: найдите маркер `Largest Contentful Paint`, кликните по нему и откройте `Related Node` — так видно, какой элемент оказался LCP. Дальше посмотрите, когда именно началась его загрузка.

Найти LCP-элемент из консоли:

```js
new PerformanceObserver(list => {
  const entries = list.getEntries();
  console.log('LCP element:', entries.at(-1));
}).observe({ type: 'largest-contentful-paint', buffered: true });
```

## Связь с другими темами

- [Core Web Vitals](./01-core-web-vitals.md) — изображение обычно и есть LCP-элемент, а отсутствие ширины и высоты кормит CLS.
- [Resource Loading](./03-resource-loading.md) — предзагрузка LCP-картинки, `fetchpriority`, ленивая загрузка.
- [Performance Metrics](./02-performance-metrics.md) — размер файла влияет на TTFB, если картинку отдаёт сервер, а время скачивания влияет на LCP.
- [Caching Strategies](./07-caching-strategies.md) — кэширование картинок на CDN и `Cache-Control` для статики.

## Типичные ошибки на интервью

- **"WebP везде — решение всех проблем с изображениями"** — WebP лучше JPEG, но не максимум. AVIF даёт ещё 20–30% сжатия при том же качестве. Правильная стратегия: AVIF → WebP → JPEG через `<picture>`, а не "перешёл на WebP и готово".

- **"next/image автоматически оптимизирует всё"** — нет. Для LCP-картинки вы всё равно вручную ставите `priority={true}`. Параметр `sizes` тоже указываете явно, иначе Next.js нагенерирует варианты крупнее нужного. Значение `quality` по умолчанию равно 75, и для главной картинки этого иногда мало.

- **"srcset — это просто список разных размеров"** — браузер сам решает, какой выбрать, и учитывает DPR устройства, скорость сети и пользовательские настройки. Вы предлагаете варианты; финальный выбор — за браузером. Это важно понимать, потому что на медленном соединении браузер может выбрать меньшую картинку даже на Retina-экране.

- **"Указал width/height — CLS исчез"** — не всегда. CSS может переопределить размеры. Правило вида `img { width: 100%; height: auto; }` без `aspect-ratio` или контейнера с фиксированным размером всё равно сдвинет макет, если картинка не успела загрузиться к первому рендеру. Нужна связка: атрибуты в теге и согласованный с ними CSS.

- **"loading="lazy" на все картинки — экономия трафика"** — loading="lazy" на LCP-картинку (первый экран) ухудшает LCP, потому что браузер намеренно откладывает её загрузку. Обратный эффект. Правило: lazy только ниже fold.

- **"AVIF — лучший формат, использую везде"** — AVIF медленно кодируется. При server-side генерации по запросу (как в next/image) первый запрос будет заметно медленнее WebP. Для статической генерации при сборке это не проблема. Также поддержка AVIF ≈ 93% (Safari 16+) — нужен fallback.

- **"Оптимизировал изображения — LCP улучшился"** — возможно, но LCP складывается из четырёх частей: TTFB, задержка до начала загрузки ресурса, время самой загрузки и задержка отрисовки. Уменьшение размера файла помогает только со временем самой загрузки. Если LCP тормозит из-за TTFB или отсутствия preload — оптимизация формата не поможет.
