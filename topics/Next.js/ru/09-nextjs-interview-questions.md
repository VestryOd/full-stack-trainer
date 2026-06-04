# Next.js Interview Questions (Middle → Senior)

---

# 1. Что такое Next.js?

Next.js — это full-stack framework поверх React.

Предоставляет:

- Routing
- SSR
- SSG
- ISR
- API Routes
- Middleware
- Caching
- SEO инструменты

---

# 2. Какие проблемы React решает Next.js?

- SEO
- Routing
- SSR
- Data Fetching
- Code Splitting
- Performance Optimization

---

# 3. Почему Next.js называют Fullstack Framework?

Потому что он содержит:

```txt
Frontend
+
Backend
```

через:

- API Routes
- Server Actions
- Middleware

---

# 4. Чем React отличается от Next.js?

React:

```txt
UI Library
```

---

Next.js:

```txt
Application Framework
```

---

# 5. Что такое Rendering?

Процесс генерации HTML.

---

# 6. Что такое CSR?

Client Side Rendering.

HTML создается в браузере после загрузки JavaScript.

---

# 7. Что такое SSR?

Server Side Rendering.

HTML создается на сервере при каждом запросе.

---

# 8. Что такое SSG?

Static Site Generation.

HTML создается во время build.

---

# 9. Что такое ISR?

Incremental Static Regeneration.

Позволяет пересоздавать статические страницы после деплоя.

---

# 10. Когда использовать SSR?

Когда нужны:

- персонализированные данные
- актуальные данные
- SEO

---

# 11. Когда использовать SSG?

Для:

- блогов
- лендингов
- документации

---

# 12. Когда использовать ISR?

Для:

- интернет-магазинов
- каталогов
- CMS-контента

---

# 13. Что такое Hydration?

Процесс подключения React к уже готовому HTML.

---

# 14. Что такое Hydration Mismatch?

Когда серверный HTML отличается от клиентского.

---

# 15. Основные причины Hydration Mismatch?

```tsx
Date.now()
Math.random()
window
localStorage
```

во время рендера.

---

# 16. Что такое App Router?

Новая архитектура маршрутизации Next.js.

Построена вокруг:

- Server Components
- Streaming
- Nested Layouts

---

# 17. Что такое Pages Router?

Старая система маршрутизации через папку:

```txt
pages/
```

---

# 18. Главное отличие App Router?

Server Components по умолчанию.

---

# 19. Что такое Server Component?

Компонент, выполняющийся только на сервере.

---

# 20. Что такое Client Component?

Компонент, выполняющийся в браузере.

---

# 21. Как пометить Client Component?

```tsx
'use client';
```

---

# 22. Что нельзя использовать в Server Components?

- useState
- useEffect
- useRef
- window
- document
- event handlers

---

# 23. Что можно использовать в Server Components?

- fetch
- database queries
- server code
- environment variables

---

# 24. Почему Server Components быстрее?

Потому что:

- меньше JS
- меньше hydration
- меньше bundle size

---

# 25. Чем SSR отличается от Server Components?

SSR отвечает:

```txt
Где создается HTML
```

---

Server Components:

```txt
Где выполняется React код
```

---

# 26. Как работает Data Fetching в App Router?

Через:

```tsx
await fetch()
```

внутри Server Components.

---

# 27. Чем Next fetch отличается от browser fetch?

Интегрирован с:

- caching
- revalidation
- rendering

---

# 28. Что делает cache: 'force-cache'?

Использует кешированный результат.

---

# 29. Что делает cache: 'no-store'?

Отключает кеширование.

---

# 30. Что такое revalidate?

Время жизни кеша.

---

Пример:

```ts
revalidate: 60
```

---

# 31. Что такое revalidatePath?

Инвалидирует кеш конкретного маршрута.

---

# 32. Что такое revalidateTag?

Инвалидирует кеш группы запросов.

---

# 33. Что такое generateStaticParams?

Аналог getStaticPaths.

---

Используется для генерации динамических маршрутов во время build.

---

# 34. Что делает cookies()?

Позволяет получить cookies на сервере.

---

Использование cookies() делает страницу динамической.

---

# 35. Что делает headers()?

Позволяет читать HTTP заголовки на сервере.

---

# 36. Что такое Dynamic Rendering?

Когда страница рендерится на каждый запрос.

---

# 37. Что такое Request Memoization?

Повторные fetch внутри одного рендера не выполняются повторно.

---

# 38. Что такое Layout?

Компонент-обертка для группы маршрутов.

---

# 39. Что такое Nested Layout?

Вложенные layout уровни.

---

Например:

```txt
Root Layout
 ↓
Dashboard Layout
 ↓
Page
```

---

# 40. Почему Layout лучше обычного компонента?

Не размонтируется при навигации.

---

# 41. Что такое loading.tsx?

Автоматический Loading UI.

---

# 42. Что такое error.tsx?

Error Boundary для сегмента маршрута.

---

# 43. Что такое not-found.tsx?

Кастомная 404 страница.

---

# 44. Что такое Middleware?

Код, выполняющийся до маршрутизации и рендера.

---

# 45. Где находится Middleware?

```txt
middleware.ts
```

---

# 46. Для чего используют Middleware?

- Auth
- Redirects
- A/B Tests
- Geo Routing
- Localization

---

# 47. Чем rewrite отличается от redirect?

Redirect:

```txt
меняет URL
```

---

Rewrite:

```txt
оставляет URL прежним
```

---

# 48. Что такое Metadata API?

Встроенная система SEO.

---

# 49. Как задать title страницы?

```ts
export const metadata = {
  title: 'Products'
}
```

---

# 50. Что такое generateMetadata()?

Позволяет создавать SEO-метаданные динамически.

---

# 51. Что такое OpenGraph?

Метаданные для социальных сетей.

---

# 52. Что такое robots.txt?

Правила индексации сайта поисковиками.

---

# 53. Что такое sitemap.xml?

Список страниц сайта для поисковых систем.

---

# 54. Что такое next/image?

Компонент оптимизации изображений.

---

Автоматически предоставляет:

- lazy loading
- responsive images
- optimization

---

# 55. Что такое next/font?

Встроенная оптимизация шрифтов.

---

# 56. Какие Core Web Vitals знаете?

- LCP
- CLS
- INP

---

# 57. Что такое Streaming?

Отправка HTML частями.

---

# 58. Что такое Suspense?

Механизм отображения fallback UI во время ожидания данных.

---

# 59. Что такое Server Actions?

Способ выполнять серверный код без API Routes.

---

Пример:

```tsx
'use server';
```

---

# 60. Когда использовать Server Actions?

Для:

- форм
- CRUD операций
- внутренних мутаций

---

# 61. Когда лучше использовать API Routes?

Для:

- REST API
- Webhooks
- внешних интеграций

---

# 62. Что такое Edge Runtime?

Выполнение кода на Edge Nodes.

---

Ближе к пользователю.

---

# 63. Какие ограничения Edge Runtime?

Нет доступа к:

- fs
- net
- child_process

---

# 64. Что такое BFF?

Backend For Frontend.

---

Next агрегирует данные из нескольких сервисов.

---

# 65. Как бы вы построили e-commerce?

```txt
Homepage → SSG

Catalog → ISR

Product → ISR

Cart → CSR

Checkout → Server Actions

Admin → CSR
```

---

# 66. Как бы вы построили CMS проект?

```txt
Next.js
 ↓
Strapi
 ↓
PostgreSQL
```

---

ISR + revalidateTag.

---

# 67. Как бы вы объяснили архитектуру современного Next.js?

Современный Next.js строится вокруг App Router, React Server Components, встроенного Data Fetching, кеширования и Streaming. Большая часть логики выполняется на сервере, а Client Components используются только там, где нужна интерактивность.

---

# 68. Самый популярный Senior вопрос

Какую модель рендеринга выбрать для приложения?

Ответ:

Нет единственной правильной модели. Production приложение обычно сочетает SSG, ISR, SSR, Server Components и Client Components в зависимости от требований к SEO, производительности, свежести данных и пользовательскому опыту.