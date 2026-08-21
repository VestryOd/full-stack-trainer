<!-- verified: 2026-06-05, corrections: 0 -->
# SEO, метаданные и производительность

## Metadata API — статика, динамика и наследование

В App Router метаданные задаются декларативно — экспортом `metadata` (статика) или `generateMetadata` (динамика) из `layout.tsx` или `page.tsx`. Именно этот текст читают поисковики, так что это базовый слой SEO (search engine optimization, поисковая оптимизация).

Ключевой, часто упускаемый момент: метаданные **наследуются и сливаются** по дереву layout'ов. Файл `page.tsx` не обязан повторять то, что уже задано в `layout.tsx` выше, и может переопределить отдельные поля.

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
type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params; // Next.js 15: params стал async
  const product = await getProduct(id);

  return {
    title: product.name, // итоговый title: "Product Name | Acme Store"
    description: product.shortDescription,
    openGraph: {
      images: [{ url: product.imageUrl, width: 1200, height: 630 }],
    },
  };
}
```

Нюанс с `title.template`: он применяется только если дочерний сегмент задаёт `title` строкой. Передайте вместо строки объект `{ absolute: ... }` — и шаблон будет пропущен. Такое явное отключение полезно для страниц, где не нужен суффикс ` | Acme Store`: например, для лендинга кампании с собственным брендингом.

### generateMetadata и стоимость дублирующих запросов

`generateMetadata` часто запрашивает те же данные, что и сам компонент страницы. Например, `getProduct(id)` нужен и для title, и для контента.

Здесь выручает **Request Memoization** (см. статью про data fetching): повторный вызов той же функции, обёрнутой в `fetch` или `React.cache`, не приводит к лишнему запросу. Но это работает только если функция действительно мемоизирована, а не написана как два независимых прямых вызова к БД (базе данных).

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

Протокол sitemap ограничивает один файл 50 000 адресами. Для каталога сверх этого Next умеет **генерировать несколько sitemap-файлов** через `generateSitemaps` — деталь, которую упускают даже кандидаты, знающие про `sitemap.ts`.

## Структурированные данные (JSON-LD)

Отдельного API для структурированных данных в Next нет. JSON-LD (JSON for Linked Data) — это обычный JSON, который вставляется в `<script type="application/ld+json">` через JSX:

```tsx
export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; // Next.js 15: params стал async
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

Важно: `dangerouslySetInnerHTML` здесь оправдан, потому что контент — это JSON, сериализованный сервером, а не пользовательский HTML.

Но если `product.name` может содержать пользовательский ввод — скажем, кастомизируемое название товара, — нужна осторожность. `JSON.stringify` сам по себе не экранирует `</script>` внутри строк. Специально подобранное название может "разорвать" тег `<script>` и привести к XSS (cross-site scripting, межсайтовый скриптинг).

Для проверенных данных из своей БД риск низкий, но это нюанс, который стоит проговорить на senior-собеседовании.

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
- `sizes` сообщает браузеру, какой вариант из сгенерированного `srcset` выбрать под текущую ширину viewport. Без него браузер может скачать изображение больше того, что реально отображается.
- `placeholder="blur"` показывает размытую версию (по `blurDataURL`, обычно сгенерированному при билде) пока грузится оригинал — улучшает воспринимаемую скорость.
- `priority` — для изображений в первом экране (above the fold, то, что видно без прокрутки) отключает `loading="lazy"` и поднимает приоритет загрузки. Если это изображение и есть LCP-элемент (Largest Contentful Paint — самый крупный видимый элемент страницы), прирост обычно измеримый.

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

У классической проблемы веб-шрифтов две формы. Браузер либо отображает текст системным шрифтом (FOUT — Flash of Unstyled Text), либо не отображает вовсе (FOIT — Flash of Invisible Text). И в том, и в другом случае после загрузки кастомного шрифта текст переразмечивается, а это и есть CLS.

```tsx
import { Inter, Roboto_Mono } from 'next/font/google';

const inter = Inter({
  // 'cyrillic' важен: без него шрифт "не подхватит" русские буквы
  subsets: ['latin', 'cyrillic'],
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

`next/font` делает две вещи. Во-первых, скачивает шрифт **на этапе сборки** и отдаёт его сам, как статический файл проекта. Запроса к Google Fonts в рантайме больше нет. Это заодно улучшает приватность: IP-адрес пользователя (IP — Internet Protocol) не уходит в Google при каждой загрузке страницы.

Во-вторых, генерирует `@font-face` с `size-adjust`: метрики fallback-шрифта подгоняются так, чтобы он занимал почти ту же площадь, что и настоящий. За счёт этого при подмене шрифта текст почти не "прыгает" — CLS растёт минимально.

## Core Web Vitals — что конкретно улучшает каждый Next-механизм

| Метрика | Что измеряет | Рычаг в Next.js |
|---|---|---|
| **LCP** (Largest Contentful Paint) | когда появился самый крупный видимый элемент | серверный рендеринг (SSR) или статическая генерация (SSG); `next/image` с `priority`; `next/font` |
| **CLS** (Cumulative Layout Shift) | насколько сильно "прыгают" элементы | `next/image` с явными `width`/`height`; `next/font`; отсутствие hydration mismatch |
| **INP** (Interaction to Next Paint) | задержка отклика на клик | меньше JS на клиенте за счёт Server Components |

Хороший senior-ответ не просто называет метрики. Он связывает *конкретный механизм Next* с *конкретной метрикой и причиной* — и это показывает, что кандидат понимает не "что использовать", а "почему это работает".

## Streaming и Suspense — связь с воспринимаемой скоростью

```tsx
import { Suspense } from 'react';

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; // Next.js 15: params стал async
  return (
    <div>
      <ProductHeader id={id} /> {/* быстрый fetch — в основном shell */}
      <Suspense fallback={<ReviewsSkeleton />}>
        <Reviews id={id} /> {/* медленный fetch — стримится отдельно */}
      </Suspense>
    </div>
  );
}
```

Стриминг не ухудшает индексацию. Googlebot дожидается полного ответа перед обработкой, поэтому промежуточные чанки он вообще не "видит" — в отличие от браузера. А для **реального пользователя** это даже плюс. LCP может улучшиться: критичный для первого экрана контент (`ProductHeader`) больше не блокируется медленным `Reviews`.

## Типичные ошибки на интервью

- **"Достаточно добавить `<title>` и `<meta description>`, остальное не важно"** — за бортом остаются три вещи. Первая — `metadataBase`: без него относительные URL в Open Graph могут резолвиться некорректно. Вторая — `robots` и `sitemap`, они определяют crawl budget. Третья — структурированные данные, из которых собираются rich snippets.

- **Не знают про наследование/merge метаданных по дереву layout'ов** — и пишут дублирующий `title`/`description` в каждом `page.tsx`, не используя `title.template`.

- **"next/image уменьшает CLS сам по себе, без width/height"** — нет. Место заранее резервируется только потому, что вы задали явные `width` и `height` либо `fill` на правильно позиционированном родителе.

- **Путают `priority` и `loading="lazy"`** — `priority` делает больше, чем "убирает lazy loading". Он ещё повышает приоритет загрузки в браузере (`fetchpriority="high"`), а это напрямую влияет на LCP для изображений в первом экране.

- **"next/font просто подключает шрифт быстрее"** — упускают главный механизм. Шрифт отдаётся со своего домена, скачанный на этапе сборки, так что запроса к Google Fonts в рантайме нет. Плюс подгонка fallback-метрик, которая уменьшает CLS.

- **Не могут связать LCP/CLS/INP с конкретными решениями в коде** — ответ остаётся абстрактным: "Next хорош для производительности". Конкретная версия: "SSR улучшает LCP, потому что HTML с контентом приходит сразу, а не после выполнения JS".

- **"Streaming ухудшает SEO, потому что страница отдаётся 'по частям'"** — нет. Поисковый робот получает полный финальный HTML после завершения стрима, а не недогруженный чанк. Для него стриминг прозрачен.
