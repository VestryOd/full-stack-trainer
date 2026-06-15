<!-- verified: 2026-06-05, corrections: 0 -->
# SEO, Metadata и Performance

## Metadata API — статика, динамика и наследование

В App Router метаданные задаются декларативно — экспортом `metadata` (статика) или `generateMetadata` (динамика) из `layout.tsx`/`page.tsx`. Ключевой, часто упускаемый момент: метаданные **наследуются и сливаются (merge)** по дереву layout'ов — `page.tsx` не обязан повторять то, что уже задано в `layout.tsx` выше, но может переопределить отдельные поля.

```tsx
// app/layout.tsx
import type { Metadata } from 'next';

export const metadata: Metadata = {
  metadataBase: new URL('https://example.com'), // база для относительных URL в OG/canonical
  title: {
    default: 'Acme Store',
    template: '%s | Acme Store', // используется дочерними сегментами
  },
  description: 'Default site description',
};

// app/products/[id]/page.tsx
export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const product = await getProduct(params.id);

  return {
    title: product.name, // итоговый title: "Product Name | Acme Store"
    description: product.shortDescription,
    openGraph: {
      images: [{ url: product.imageUrl, width: 1200, height: 630 }],
    },
  };
}
```

Нюанс с `title.template`: он применяется только если дочерний сегмент задаёт `title` как строку, а не как объект `{ absolute: ... }`. `absolute` явно "отключает" наследование шаблона — полезно для страниц, где не нужен суффикс ` | Acme Store` (например, для лендинга кампании с собственным брендингом).

### generateMetadata и стоимость дублирующих запросов

`generateMetadata` часто запрашивает те же данные, что и сам компонент страницы (например, `getProduct(id)` нужен и для title, и для контента). Благодаря **Request Memoization** (см. статью про data fetching) повторный вызов одной и той же обёрнутой в `fetch`/`React.cache` функции не приводит к лишнему запросу — но это работает только если функция действительно мемоизирована, а не написана как два независимых прямых вызова к БД.

```ts
import { cache } from 'react';

export const getProduct = cache(async (id: string) => {
  return db.product.findUnique({ where: { id } });
});
```

## robots.ts и sitemap.ts — типизированные файловые конвенции

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

Для очень больших каталогов (>50 000 URL — лимит на один sitemap-файл по протоколу) Next поддерживает **генерацию нескольких sitemap-файлов** через `generateSitemaps`, что часто упускают даже знающие про `sitemap.ts` кандидаты.

## Structured Data (JSON-LD)

Next не предоставляет отдельный API для structured data — это обычный JSON, вставляемый в `<script type="application/ld+json">` через JSX:

```tsx
export default async function ProductPage({ params }: { params: { id: string } }) {
  const product = await getProduct(params.id);

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

Важно: `dangerouslySetInnerHTML` здесь оправдан, потому что контент — это JSON, сериализованный сервером, а не пользовательский HTML. Но если `product.name` содержит пользовательский ввод (например, кастомизируемое название товара), нужна осторожность — `JSON.stringify` сам по себе не экранирует `</script>` внутри строк, что теоретически может привести к XSS через "разрыв" тега `<script>`. На практике для controlled-данных из своей БД риск низкий, но это нюанс, который стоит проговорить на senior-собеседовании.

## next/image — что происходит "под капотом"

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

- `width`/`height` обязательны для статических изображений — Next резервирует место под изображение **до** его загрузки, что напрямую снижает CLS (Cumulative Layout Shift).
- `sizes` сообщает браузеру, какой вариант из сгенерированного `srcset` выбрать в зависимости от ширины viewport — без него браузер может скачать изображение большего размера, чем реально отображается.
- `placeholder="blur"` показывает размытую версию (по `blurDataURL`, обычно сгенерированному при билде) пока грузится оригинал — улучшает perceived performance.
- `priority` — для above-the-fold изображений (например, hero-картинки) отключает `loading="lazy"` и поднимает приоритет загрузки; для LCP-элемента это часто даёт измеримый прирост.

Частый антипаттерн — `fill` без `sizes` на родителе без явных размеров:

```tsx
// ❌ родитель без position: relative и фиксированных размеров —
// fill не может корректно вычислить размеры изображения
<div>
  <Image src={...} alt="" fill />
</div>

// ✅
<div style={{ position: 'relative', width: '100%', height: '300px' }}>
  <Image src={...} alt="" fill style={{ objectFit: 'cover' }} />
</div>
```

## next/font — устранение layout shift от веб-шрифтов

Классическая проблема веб-шрифтов: браузер сначала отображает текст системным шрифтом (FOUT — Flash of Unstyled Text) или не отображает вовсе (FOIT), а после загрузки кастомного шрифта переразмечивает текст — это CLS.

```tsx
import { Inter, Roboto_Mono } from 'next/font/google';

const inter = Inter({
  subsets: ['latin', 'cyrillic'], // важно для кириллицы — иначе шрифт "не подхватит" русские буквы
  display: 'swap',
  variable: '--font-inter',
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
```

`next/font` скачивает шрифт **на этапе сборки**,self-host'ит файл как статический ассет и автоматически генерирует `@font-face` с `size-adjust` — это means: нет runtime-запроса к Google Fonts (что само по себе улучшает приватность — IP пользователя не уходит в Google при каждой загрузке страницы) и метрики шрифта подбираются так, чтобы fallback-шрифт занимал максимально близкую по размеру область, минимизируя CLS при свапе.

## Core Web Vitals — что конкретно улучшает каждый Next-механизм

| Метрика | Что измеряет | Чем в Next.js улучшается |
|---|---|---|
| **LCP** (Largest Contentful Paint) | Время до отображения самого крупного видимого элемента | SSR/SSG (HTML с контентом сразу), `next/image` с `priority`, `next/font` (текст не ждёт шрифт) |
| **CLS** (Cumulative Layout Shift) | Суммарный "прыгающий" сдвиг элементов | `next/image` с явными `width`/`height`, `next/font` (стабильные метрики шрифта), избегание hydration mismatch |
| **INP** (Interaction to Next Paint) | Задержка отклика на действия пользователя | Меньше JS на клиенте за счёт Server Components → меньше работы main thread |

Хороший senior-ответ не просто называет метрики, а связывает *конкретный механизм Next* с *конкретной метрикой и причиной* — это показывает, что кандидат понимает не "что нужно использовать", а "почему это работает".

## Streaming и Suspense — связь с perceived performance

```tsx
import { Suspense } from 'react';

export default function ProductPage({ params }: { params: { id: string } }) {
  return (
    <div>
      <ProductHeader id={params.id} /> {/* быстрый fetch — в основном shell */}
      <Suspense fallback={<ReviewsSkeleton />}>
        <Reviews id={params.id} /> {/* медленный fetch — стримится отдельно */}
      </Suspense>
    </div>
  );
}
```

С точки зрения SEO стриминг не ухудшает индексацию — Googlebot дожидается полного ответа перед обработкой (он не "видит" промежуточные чанки так, как видит их браузер), но с точки зрения **реального пользователя** LCP может улучшиться, потому что критичный для отображения контент (`ProductHeader`) не блокируется медленным `Reviews`.

## Типичные ошибки на интервью

- **"Достаточно добавить `<title>` и `<meta description>`, остальное не важно"** — упускают `metadataBase` (без него относительные URL в Open Graph могут резолвиться некорректно), `robots`/`sitemap` для crawl budget, и structured data для rich snippets.

- **Не знают про наследование/merge метаданных по дереву layout'ов** — и пишут дублирующий `title`/`description` в каждом `page.tsx`, не используя `title.template`.

- **"next/image автоматически уменьшает CLS сам по себе, без width/height"** — нет, именно явные `width`/`height` (или `fill` с правильно позиционированным родителем) позволяют браузеру зарезервировать место заранее.

- **Путают `priority` и `loading="lazy"`** — `priority` не просто "убирает lazy loading", он также повышает приоритет fetch в браузере (`fetchpriority="high"`), что напрямую влияет на LCP для above-the-fold изображений.

- **"next/font просто подключает шрифт быстрее"** — упускают главный механизм: self-hosting на этапе сборки (нет runtime-запроса к Google Fonts) и подгонку fallback-метрик шрифта для уменьшения CLS, а не просто "более быструю загрузку".

- **Не могут связать LCP/CLS/INP с конкретными решениями в коде** — отвечают абстрактно ("Next хорош для производительности"), вместо "SSR улучшает LCP, потому что HTML с контентом приходит сразу, а не после выполнения JS".

- **"Streaming ухудшает SEO, потому что страница отдаётся 'по частям'"** — поисковые роботы получают полный финальный HTML после завершения стрима, а не недогруженный чанк — для них Streaming прозрачен.
