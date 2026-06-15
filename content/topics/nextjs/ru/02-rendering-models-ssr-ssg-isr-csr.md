<!-- verified: 2026-06-05, corrections: 0 -->
# Rendering Models: CSR, SSR, SSG, ISR

## Что вообще такое "rendering model"

Rendering — это процесс превращения React-дерева в HTML. Модель рендеринга отвечает на два вопроса:

```txt
Где создаётся HTML?   — на сервере, на CDN при билде, или в браузере
Когда создаётся HTML? — на каждый запрос, один раз при билде,
                         или периодически через revalidation
```

В App Router (Next.js 13+) выбор модели больше не делается "на уровне всего приложения" — он делается *гранулярно*, на уровне отдельного route segment, через `fetch`-опции и экспортируемые конфигурации (`export const dynamic`, `export const revalidate`). Это важное отличие от Pages Router, где модель выбиралась функцией экспорта (`getServerSideProps`/`getStaticProps`/ничего) на уровне всей страницы.

## CSR — Client Side Rendering

Классическая модель SPA: сервер отдаёт минимальный HTML, всё остальное достраивает JS в браузере.

```txt
Browser
 ↓
скачивание HTML (почти пустой) + JS bundle
 ↓
выполнение React, mount
 ↓
fetch данных (useEffect / react-query / SWR)
 ↓
повторный рендер с данными
```

```tsx
'use client';

import { useEffect, useState } from 'react';

export function UserDashboard() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    fetch('/api/me').then((res) => res.json()).then(setUser);
  }, []);

  if (!user) return <Spinner />;
  return <Profile user={user} />;
}
```

**Плюсы**: минимальная нагрузка на сервер (он отдаёт статику), отличный UX *после* загрузки — переходы между состояниями мгновенные, не требуют похода на сервер.

**Минусы**: пустой HTML до выполнения JS (плохо для SEO и для метрик типа FCP/LCP), data fetching внутри `useEffect` создаёт *водопады* запросов (request waterfalls) — компонент должен сначала смонтироваться, потом запросить данные, потом отрендерить детей, которые тоже могут что-то запрашивать.

В App Router CSR достигается через Client Components (`'use client'`) — это осознанный выбор для интерактивных частей UI (формы, дропдауны, графики), а не модель по умолчанию для целых страниц.

## SSR — Server Side Rendering

HTML генерируется на сервере **при каждом запросе**.

```txt
Request → Server рендерит React в HTML → HTML отдаётся браузеру → Hydration
```

**В Pages Router** это делалось через `getServerSideProps`:

```ts
export async function getServerSideProps(context) {
  const data = await fetchUserData(context.params.id);
  return { props: { data } };
}
```

**В App Router** SSR — это поведение *по умолчанию* для Server Component, если он использует динамические данные (например, `cookies()`, `headers()`, или `fetch` с `cache: 'no-store'`):

```tsx
// app/profile/page.tsx
import { cookies } from 'next/headers';

export default async function ProfilePage() {
  const sessionId = cookies().get('session')?.value;
  const user = await fetch(`https://api.example.com/me`, {
    headers: { Authorization: `Bearer ${sessionId}` },
    cache: 'no-store', // → форсирует SSR для этого fetch
  }).then((r) => r.json());

  return <Profile user={user} />;
}
```

Можно явно форсировать SSR на уровне всего сегмента:

```ts
export const dynamic = 'force-dynamic';
```

**Плюсы**: всегда свежие данные, отличный SEO (полный HTML на каждый запрос), персонализация (можно читать cookies/headers до рендера).

**Минусы**: нагрузка на сервер пропорциональна трафику, выше TTFB (нужно подождать рендер + fetch перед отправкой первого байта), сложнее кешировать на CDN (хотя Next умеет кешировать и SSR-ответы через `Cache-Control` заголовки и Data Cache).

## SSG — Static Site Generation

HTML генерируется **во время build**, один раз, до прихода пользователей.

```txt
Build time → HTML для каждой страницы → деплой на CDN → пользователи получают статику
```

**В Pages Router**: `getStaticProps` (+ `getStaticPaths` для динамических маршрутов).

**В App Router**: Server Component без динамических API и с `fetch`, у которого `cache: 'force-cache'` (это значение по умолчанию!). Для динамических маршрутов используется `generateStaticParams`:

```tsx
// app/blog/[slug]/page.tsx
export async function generateStaticParams() {
  const posts = await getAllPostSlugs();
  return posts.map((post) => ({ slug: post.slug }));
}

export default async function BlogPost({ params }: { params: { slug: string } }) {
  const post = await fetch(`https://cms.example.com/posts/${params.slug}`)
    .then((r) => r.json()); // cache: 'force-cache' по умолчанию → SSG

  return <Article post={post} />;
}
```

**Плюсы**: максимальная скорость (отдаётся статика прямо с CDN, без участия Node.js на запрос), идеальное кеширование, нулевая нагрузка на origin-сервер при чтении.

**Минусы**: данные "застывают" на момент билда — обновление контента требует пересборки (или ISR). Для сайтов с тысячами/миллионами страниц `generateStaticParams` может сделать билд непрактично долгим — здесь и нужен ISR с `on-demand` генерацией недостающих страниц.

**Когда использовать**: блоги, документация, маркетинговые лендинги, страницы, где контент меняется редко (часы/дни).

## ISR — Incremental Static Regeneration

ISR — это SSG, который умеет "протухать" и пересобираться без полного редеплоя.

```txt
Request 1 (в пределах TTL)  → отдаётся закешированная страница (мгновенно)
Request после истечения TTL → отдаётся СТАРАЯ страница + в фоне запускается regeneration
Следующий request           → отдаётся уже новая страница
```

Ключевой нюанс: пользователь, который "запускает" revalidation, **не ждёт** пересборки — он получает старую (stale) версию, а новая версия кешируется для последующих запросов (паттерн stale-while-revalidate).

**В Pages Router**:

```ts
export async function getStaticProps() {
  const data = await fetchProducts();
  return {
    props: { data },
    revalidate: 60, // секунд
  };
}
```

**В App Router** — то же самое через опцию `fetch`:

```tsx
export default async function ProductsPage() {
  const products = await fetch('https://api.example.com/products', {
    next: { revalidate: 60 }, // ISR: страница "протухает" через 60с
  }).then((r) => r.json());

  return <ProductList products={products} />;
}
```

Или на уровне всего сегмента:

```ts
export const revalidate = 60;
```

Помимо time-based revalidation есть **on-demand revalidation** — точечная инвалидация по тегу или пути, например после публикации статьи в CMS:

```ts
// app/api/revalidate/route.ts
import { revalidateTag } from 'next/cache';

export async function POST(request: Request) {
  const { tag } = await request.json();
  revalidateTag(tag); // мгновенно помечает закешированные данные с этим тегом как stale
  return Response.json({ revalidated: true });
}
```

```tsx
// при фетче данные помечаются тегом
fetch('https://cms.example.com/posts', { next: { tags: ['posts'] } });
```

**Когда использовать**: каталоги товаров, новостные сайты, CMS-контент — данные обновляются, но не нужна свежесть "до миллисекунды".

## Hydration и Hydration Mismatch

После SSR/SSG браузер получает готовый HTML — контент виден сразу, но он **не интерактивен**: обработчики событий ещё не подключены. Hydration — это процесс, в котором React проходит по уже существующему DOM-дереву и "подключает" к нему свой виртуальный DOM и обработчики, *без* пересоздания разметки с нуля.

```txt
Server рендерит HTML
 ↓
Browser получает и показывает HTML (контент виден, но не работает)
 ↓
JS bundle скачивается и выполняется
 ↓
React сверяет SSR-разметку с тем, что он бы отрендерил сам
 ↓
Hydration: подключение event listeners → UI интерактивен
```

**Hydration Mismatch** возникает, когда HTML, отрендеренный на сервере, не совпадает с тем, что React рендерит на клиенте при первом рендере. React в этом случае логирует предупреждение и (в продакшене) может "перетереть" серверную разметку клиентским рендером — что приводит к видимому "миганию" контента (visual flicker).

Типичные причины:

```tsx
// 1. Использование значений, зависящих от окружения
function Clock() {
  return <span>{new Date().toLocaleTimeString()}</span>;
  // на сервере: 10:00:00, на клиенте при гидратации: 10:00:02 → mismatch
}

// 2. Доступ к browser-only API во время рендера
function Banner() {
  // window недоступен на сервере → на сервере один HTML, на клиенте другой
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  return <div>{isMobile ? 'Mobile' : 'Desktop'}</div>;
}

// 3. Невалидный HTML, который браузер исправляет сам
function Wrapper() {
  // <p> не может содержать <div> — браузер "разорвёт" тег при парсинге,
  // итоговое DOM-дерево не совпадёт с тем, что ожидает React
  return <p><div>content</div></p>;
}
```

**Правильные решения**:

```tsx
// Для значений, известных только на клиенте — рендерить после монтирования
function Clock() {
  const [time, setTime] = useState<string | null>(null);

  useEffect(() => {
    setTime(new Date().toLocaleTimeString());
  }, []);

  // null на сервере и при первом клиентском рендере — совпадают
  return <span>{time ?? '--:--:--'}</span>;
}

// Либо явно сообщить React, что несовпадение ожидаемо (использовать ОЧЕНЬ точечно)
<span suppressHydrationWarning>{new Date().toLocaleTimeString()}</span>
```

`suppressHydrationWarning` подавляет warning только для конкретного узла и только для текстового/атрибутного содержимого — это не "общее выключение" hydration-проверок, и злоупотребление им маскирует реальные баги.

## Сравнение моделей

| Модель | Когда генерируется HTML | TTFB | Свежесть данных | Кешируемость |
|---|---|---|---|---|
| CSR | В браузере, после JS | Низкий (статика) | Всегда свежие (client fetch) | Отличная (статика) |
| SSR | На каждый запрос | Высокий | Всегда свежие | Сложнее (per-request) |
| SSG | Во время билда | Низкий (CDN) | Фиксированная на момент билда | Идеальная |
| ISR | Билд + периодическая регенерация | Низкий (CDN) | Настраиваемая задержка (TTL) | Хорошая |

## Как выбирать модель — практические сценарии

```txt
Блог / документация          → SSG
Каталог товаров               → ISR (revalidate по TTL + on-demand при изменении товара)
Личный дашборд пользователя   → SSR или CSR (данные привязаны к сессии)
Лендинг / маркетинг           → SSG
Страница товара в e-commerce  → ISR + on-demand revalidation после обновления цены/наличия
Real-time данные (биржа, чат) → CSR + WebSocket/polling, либо Server Components + streaming
```

Важно: в App Router выбор не "одна модель на всё приложение", а *композиция* — Layout может быть статическим (SSG), а вложенный в него Server Component с динамическими данными — рендериться по SSR-модели, при этом обёрнутый в `<Suspense>` он может стримиться отдельным чанком (Partial Prerendering — экспериментальная возможность, развивающая эту идею ещё дальше).

## Типичные ошибки на интервью

- **"SSG — это когда сервер рендерит HTML"** — нет, SSG означает, что HTML создаётся *во время билда*, сервер на момент запроса вообще не участвует в рендере, он просто отдаёт готовый файл.

- **"ISR — это SSR с кешем"** — точнее: ISR — это SSG с механизмом фонового пересоздания. Пользователь, инициировавший revalidation по TTL, получает *старую* версию, а не ждёт новую.

- **Путают `revalidate: 0` и `cache: 'no-store'`** — оба "отключают" статический кеш, но семантически это разные вещи: `revalidate: 0` всё ещё часть модели ISR/кеширования Data Cache (эквивалентно "не кешировать вообще"), а `no-store` — явный SSR per-request без участия Data Cache. На практике результат близкий, но при ответе стоит показать, что вы понимаете разницу между Full Route Cache и Data Cache.

- **Думают, что hydration mismatch — это просто "warning в консоли, можно игнорировать"** — в продакшене это может привести к видимому "перерисовыванию" контента и потере состояния (например, сброс значения инпута, в который пользователь уже начал печатать).

- **Не могут объяснить, почему `Date.now()` или `Math.random()` напрямую в JSX — антипаттерн** — потому что результат вычисляется и на сервере (при SSR/SSG), и на клиенте (при первом рендере до гидратации), и эти значения почти гарантированно разойдутся.

- **Считают, что выбор модели делается один раз для всего приложения** — в App Router модель выбирается per-segment и может комбинироваться в рамках одной страницы (статический layout + динамический контент + стриминг через Suspense).
