<!-- verified: 2026-06-05, corrections: 0 -->
# SEO, Metadata и Performance

## Почему SEO важен для Next.js

Одна из главных причин появления Next.js:

```txt
SEO
```

---

Обычный React SPA:

```html
<body>
  <div id="root"></div>
</body>
```

---

Поисковый робот получает почти пустую страницу.

---

SSR и SSG решают эту проблему.

---

# Что нужно для SEO

Минимальный набор:

```txt
Title
Description
Canonical
OpenGraph
Robots
Sitemap
Structured Data
```

---

# Metadata API

Современный способ в App Router.

---

Пример:

```ts
export const metadata = {
  title: 'Products',
  description: 'Product Catalog',
};
```

---

Next автоматически создаст:

```html
<title>Products</title>

<meta
  name="description"
/>
```

---

# Dynamic Metadata

Очень популярный вопрос.

---

Пример:

```tsx
export async function
generateMetadata({ params }) {

  const product =
    await getProduct(
      params.id
    );

  return {
    title: product.name,
  };
}
```

---

Для каждого товара:

```txt
свой title
```

---

# OpenGraph

Управляет превью ссылок.

---

Например:

```txt
Facebook
LinkedIn
Telegram
Slack
```

---

Пример:

```ts
export const metadata = {

  openGraph: {
    title: 'Product',
    description: 'Details',
    images: ['/cover.jpg']
  }
};
```

---

# Twitter Cards

Похожий механизм.

---

Используется Twitter/X.

---

# Canonical URL

Очень популярный вопрос.

---

Проблема:

```txt
/product/1

/product/1?sort=asc
```

---

Одинаковый контент.

---

Поисковик считает:

```txt
дубликаты
```

---

Решение:

```html
<link rel="canonical" />
```

---

# robots.txt

Указывает поисковикам:

```txt
что индексировать
что не индексировать
```

---

В Next можно создать:

```txt
app/robots.ts
```

---

Пример:

```ts
export default function robots() {

  return {
    rules: {
      userAgent: '*',
      allow: '/'
    }
  };
}
```

---

# sitemap.xml

Список страниц сайта.

---

Очень помогает SEO.

---

В Next:

```txt
app/sitemap.ts
```

---

Пример:

```ts
export default function sitemap() {

  return [
    {
      url: '/'
    },
    {
      url: '/products'
    }
  ];
}
```

---

# Structured Data

Schema.org.

---

Очень любят спрашивать.

---

Позволяет Google понимать:

```txt
Product
Article
Review
Organization
```

---

Пример:

```json
{
 "@type": "Product"
}
```

---

# next/image

Одна из сильнейших оптимизаций Next.

---

Проблема:

```html
<img src="big.jpg" />
```

---

Браузер скачивает:

```txt
оригинальное изображение
```

---

# Next Image

```tsx
<Image
  src={...}
  width={300}
  height={300}
/>
```

---

Автоматически:

```txt
responsive sizes
lazy loading
modern formats
optimization
```

---

# Lazy Loading

Изображение загружается:

```txt
только когда нужно
```

---

Улучшает:

```txt
LCP
```

---

# next/font

Очень популярный вопрос.

---

Проблема:

```txt
Google Fonts
```

---

Дополнительный сетевой запрос.

---

# Решение

```ts
import {
  Roboto
} from 'next/font/google';
```

---

Next:

```txt
скачивает шрифт заранее
```

---

Улучшается:

```txt
CLS
FCP
```

---

# Core Web Vitals

Очень важно.

---

Google использует:

```txt
LCP
CLS
INP
```

---

# LCP

Largest Contentful Paint.

---

Скорость отображения
главного контента.

---

# CLS

Cumulative Layout Shift.

---

Прыжки интерфейса.

---

# INP

Interaction to Next Paint.

---

Реакция интерфейса
на действия пользователя.

---

# Hydration

Очень популярный вопрос.

---

После SSR:

```txt
HTML уже есть
```

---

Но события ещё не работают.

---

React подключает их.

---

Это:

```txt
Hydration
```

---

# Hydration Mismatch

Очень любят спрашивать.

---

Сервер:

```txt
10:00
```

---

Клиент:

```txt
10:01
```

---

Получаем:

```txt
Hydration Error
```

---

# Типичные причины

```tsx
Date.now()
Math.random()
window
localStorage
```

---

Во время рендера.

---

# Streaming

Очень современная тема.

---

Раньше:

```txt
рендерим всё
потом отправляем
```

---

Теперь:

```txt
отправляем частями
```

---

Пользователь быстрее видит UI.

---

# Suspense

Используется вместе со Streaming.

---

```tsx
<Suspense
 fallback={<Loading />}
>
  <Products />
</Suspense>
```

---

# Interview Answer

Next.js предоставляет встроенные инструменты для SEO через Metadata API, robots.txt и sitemap.xml. Для производительности используются next/image, next/font, Streaming, Suspense и Server Components. Особое внимание стоит уделять Core Web Vitals и избегать Hydration Mismatch ошибок.