<!-- verified: 2026-06-16, corrections: 0 -->
# Caching Strategies

## Почему кэширование — самая важная оптимизация

Кэширование — единственная оптимизация, которая может снизить время загрузки **до нуля**: закэшированный ресурс не требует ни одного байта сетевого трафика.

```txt
Без кэша (каждый запрос):
  DNS → TCP → TLS → Request → Server → Response
  = 200-800ms даже для маленьких ресурсов

С кэшем (memory cache):
  = 0ms (< 1ms из RAM)

С кэшем (disk cache):
  = 2-10ms (чтение с диска)

С кэшем (CDN edge, ближайший сервер):
  = 10-50ms (сетевой RTT к ближайшей ноде)

Приоритет кэшей браузера (от быстрого к медленному):
  1. Memory cache (вкладка не закрыта)
  2. Service Worker cache
  3. HTTP disk cache
  4. Push cache (HTTP/2, короткоживущий)
  → Сеть (если ничего не нашли)
```

## HTTP Cache-Control — основа всего

`Cache-Control` — главный заголовок. Его значения определяют: кто может кэшировать, как долго, и нужна ли валидация.

### Директивы Cache-Control

```txt
max-age=N         — кэшировать N секунд (считается от времени ответа)
s-maxage=N        — то же, но только для shared caches (CDN, прокси)
                    переопределяет max-age для CDN

no-cache          — МОЖНО кэшировать, но НУЖНА валидация перед
                    каждым использованием (не значит "не кэшировать"!)

no-store          — НЕЛЬЗЯ кэшировать вообще (чувствительные данные)

public            — можно кэшировать в shared cache (CDN)
private           — только в браузере пользователя (не CDN)

immutable         — ресурс НИКОГДА не изменится, не валидировать
                    даже при явном refresh (F5)

must-revalidate   — по истечении max-age ОБЯЗАТЕЛЬНО валидировать
                    (не отдавать stale даже при ошибке сервера)

stale-while-revalidate=N  — отдавать stale до N секунд,
                            параллельно обновляя в фоне

stale-if-error=N  — отдавать stale если сервер недоступен (до N секунд)
```

### Стратегии кэширования по типу ресурса

```ts
// Стратегия 1: Статические ресурсы с хэшем в имени
// (JS, CSS, изображения из сборщика)
// Имя: main.a3f2c9d.js — изменится только если изменился контент
// Поэтому: кэшируем навсегда

// Express/Node.js
app.use('/static', express.static('dist', {
  maxAge: '1 year',
  immutable: true,
  // Cache-Control: public, max-age=31536000, immutable
}));

// Next.js делает это автоматически для /_next/static/
// (хэш в пути гарантирует cache busting при деплое)
```

```ts
// Стратегия 2: HTML-документы
// НЕ хэшируем имя (URL должен быть стабильным).
// Используем no-cache — браузер валидирует при каждом запросе,
// но если ETag совпал — отдаёт из кэша (304, не скачивает)

res.setHeader(
  'Cache-Control',
  'no-cache' // или: max-age=0, must-revalidate
);

// С CDN — отличаем браузерный и CDN-кэш:
res.setHeader(
  'Cache-Control',
  'public, max-age=0, s-maxage=60, stale-while-revalidate=600'
  // Браузер: не кэшировать (max-age=0)
  // CDN: кэшировать 60 секунд, потом stale ещё 600
);
```

```ts
// Стратегия 3: API-ответы
// Зависит от природы данных:

// Персональные данные (корзина, профиль):
res.setHeader('Cache-Control', 'private, no-cache');

// Публичные данные, меняются редко (список статей):
res.setHeader(
  'Cache-Control',
  'public, max-age=60, stale-while-revalidate=3600'
);

// Данные реального времени (цены, доступность):
res.setHeader('Cache-Control', 'no-store');
```

```ts
// Next.js App Router — кэширование fetch на уровне сервера
async function getProducts() {
  const res = await fetch('https://api.example.com/products', {
    next: {
      revalidate: 60,  // ISR: перегенерировать через 60 секунд
      // или:
      tags: ['products'], // cache tag для ручной инвалидации
    },
  });
  return res.json();
}

// Ручная инвалидация по тегу (при CMS webhook, например)
import { revalidateTag } from 'next/cache';
revalidateTag('products'); // перегенерирует все страницы с этим тегом
```

## ETag и условные запросы

```txt
ETag — "отпечаток" версии ресурса (хэш содержимого).
Браузер сохраняет ETag и отправляет при следующем запросе.
Сервер сравнивает: совпал → 304 Not Modified (без тела),
не совпал → 200 с новым содержимым.

Первый запрос:
  Client → GET /api/articles
  Server → 200 OK
           ETag: "abc123"
           Cache-Control: no-cache
           [тело ответа: 50KB]

Следующий запрос:
  Client → GET /api/articles
           If-None-Match: "abc123"
  Server → 304 Not Modified (если данные не изменились)
           [тело: 0 байт] ← экономия трафика

  Или:   → 200 OK
           ETag: "def456"
           [новое тело: 50KB]
```

```ts
// Реализация ETag в Express
import crypto from 'crypto';

app.get('/api/articles', async (req, res) => {
  const articles = await db.article.findMany();
  const body = JSON.stringify(articles);
  const etag = crypto.createHash('md5').update(body).digest('hex');

  // Клиент отправил If-None-Match — проверяем
  if (req.headers['if-none-match'] === `"${etag}"`) {
    return res.status(304).end();
  }

  res.setHeader('ETag', `"${etag}"`);
  res.setHeader('Cache-Control', 'no-cache');
  res.json(articles);
});
```

```ts
// Last-Modified — альтернатива ETag (для статических файлов)
// Браузер отправляет: If-Modified-Since: <дата>
// Сервер: 304 если не изменилось, 200 если изменилось

// Express делает это автоматически для static files:
app.use(express.static('public')); // Last-Modified из fs.stat()
```

## stale-while-revalidate — паттерн без задержки

`stale-while-revalidate` — это ответ на вопрос "как получить свежие данные без ожидания":

```txt
Обычный no-cache:
  Запрос → ждём сервер → получили → показали
  = задержка ВСЕГДА

stale-while-revalidate:
  Запрос → немедленно отдаём из кэша (stale данные)
           → параллельно запрашиваем сервер
           → обновляем кэш
  = 0ms задержка, свежие данные на следующем запросе
```

```ts
// HTTP заголовок: stale-while-revalidate
res.setHeader(
  'Cache-Control',
  // max-age: кэш "свежий" 60 сек (отдаём без запроса к серверу)
  // stale-while-revalidate: ещё 3600 сек — отдаём stale,
  //   но ПАРАЛЛЕЛЬНО обновляем в фоне
  'public, max-age=60, stale-while-revalidate=3600'
);
```

```ts
// SWR (stale-while-revalidate) — библиотека для React
import useSWR from 'swr';

function ArticleList() {
  const { data, error, isLoading } = useSWR(
    '/api/articles',
    fetcher,
    {
      // Всегда показываем кэшированные данные мгновенно,
      // параллельно обновляем в фоне
      revalidateOnFocus: true,    // обновить когда вкладка получила фокус
      revalidateOnReconnect: true, // обновить после восстановления сети
      refreshInterval: 30_000,     // автообновление каждые 30 сек
      dedupingInterval: 2_000,     // дедупликация: один запрос за 2 сек
    }
  );

  // data — всегда есть (из кэша), даже если идёт обновление
  if (error) return <Error />;
  return <ArticleGrid articles={data} isUpdating={isLoading} />;
}
```

```ts
// TanStack Query — более мощная альтернатива SWR
import { useQuery, useQueryClient } from '@tanstack/react-query';

function ArticleList() {
  const { data, isStale } = useQuery({
    queryKey: ['articles'],
    queryFn: () => fetch('/api/articles').then(r => r.json()),
    staleTime: 60_000,  // данные "свежие" 60 секунд
    gcTime: 5 * 60_000, // держать в памяти 5 минут после unmount
  });

  return <ArticleGrid articles={data} />;
}

// Ручная инвалидация (например после мутации)
const queryClient = useQueryClient();
await queryClient.invalidateQueries({ queryKey: ['articles'] });
```

## CDN Caching

### Как CDN решает задачу кэширования

```txt
Без CDN:
  Пользователь (Токио) → Сервер (Вирджиния) = 150ms RTT × 2 = 300ms

С CDN (Cloudflare, CloudFront, Fastly):
  Пользователь (Токио) → CDN Edge (Токио) = 5-10ms RTT
  CDN Edge проверяет свой кэш:
    Hit  → отвечает немедленно (5-10ms)
    Miss → запрашивает Origin-сервер (300ms), кэширует ответ
           следующие запросы — снова hit (5-10ms)
```

```ts
// s-maxage — для CDN (переопределяет max-age для shared caches)
res.setHeader(
  'Cache-Control',
  // Браузер кэширует 5 минут
  // CDN кэширует 1 час
  'public, max-age=300, s-maxage=3600'
);

// CDN-специфичные заголовки (Cloudflare):
res.setHeader('Cloudflare-CDN-Cache-Control', 's-maxage=86400');

// Surrogate-Control (Fastly, Varnish):
res.setHeader('Surrogate-Control', 'max-age=86400');
```

### Cache invalidation на CDN

```ts
// CloudFront (AWS) — инвалидация через API
import { CloudFrontClient, CreateInvalidationCommand } from '@aws-sdk/client-cloudfront';

const client = new CloudFrontClient({ region: 'us-east-1' });

async function invalidateCDNPaths(paths: string[]) {
  await client.send(new CreateInvalidationCommand({
    DistributionId: process.env.CLOUDFRONT_DISTRIBUTION_ID!,
    InvalidationBatch: {
      CallerReference: Date.now().toString(),
      Paths: {
        Quantity: paths.length,
        Items: paths, // ['/', '/articles/*', '/static/hero.jpg']
      },
    },
  }));
}

// Вызов при деплое новой версии:
await invalidateCDNPaths(['/*']); // инвалидировать всё
// или точечно:
await invalidateCDNPaths(['/articles/*', '/']);
```

```ts
// Cloudflare — инвалидация через API
async function purgeCloudflareCache(urls: string[]) {
  await fetch(
    `https://api.cloudflare.com/client/v4/zones/${process.env.CF_ZONE_ID}/purge_cache`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${process.env.CF_API_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ files: urls }),
    }
  );
}
```

### Cache Stampede (thundering herd) — и как с ним бороться

```txt
Проблема: кэш истёк → 10 000 пользователей одновременно
запрашивают → 10 000 запросов к Origin → Origin падает

Решения:

1. stale-while-revalidate — только один фоновый запрос,
   остальные получают stale

2. Probabilistic Early Expiration (PER):
   Начинать обновление заранее, случайно, до истечения кэша
   (XFetch алгоритм)

3. Lock/mutex: первый запрос "берёт блокировку",
   остальные ждут или получают stale
```

```ts
// Простой mutex через Redis для предотвращения stampede
import { Redis } from 'ioredis';

const redis = new Redis(process.env.REDIS_URL!);

async function getCachedWithLock<T>(
  key: string,
  ttl: number,
  fetchFn: () => Promise<T>
): Promise<T> {
  // Пробуем получить из кэша
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached);

  // Берём блокировку (SET NX = только если не существует)
  const lockKey = `lock:${key}`;
  const locked = await redis.set(lockKey, '1', 'EX', 10, 'NX');

  if (!locked) {
    // Другой процесс уже получает данные — ждём и повторяем
    await new Promise(r => setTimeout(r, 100));
    return getCachedWithLock(key, ttl, fetchFn);
  }

  try {
    const data = await fetchFn();
    await redis.setex(key, ttl, JSON.stringify(data));
    return data;
  } finally {
    await redis.del(lockKey);
  }
}
```

## Service Workers — полный контроль над кэшем

Service Worker — JS-файл, работающий в отдельном потоке и перехватывающий все сетевые запросы страницы.

### Стратегии кэширования Service Worker

```ts
// sw.ts — стратегии кэширования

// 1. Cache First (Offline First)
// Сначала кэш, потом сеть. Идеально для статики.
async function cacheFirst(request: Request): Promise<Response> {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  const cache = await caches.open('static-v1');
  cache.put(request, response.clone()); // клонируем — body можно прочесть один раз
  return response;
}

// 2. Network First
// Сначала сеть, при ошибке — кэш. Для API с частым обновлением.
async function networkFirst(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);
    const cache = await caches.open('api-v1');
    cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw new Error('Network error and no cache available');
  }
}

// 3. Stale While Revalidate
// Кэш немедленно + обновление в фоне.
async function staleWhileRevalidate(request: Request): Promise<Response> {
  const cache = await caches.open('dynamic-v1');
  const cached = await cache.match(request);

  // Фоновое обновление (без await — не блокируем ответ)
  const fetchAndUpdate = fetch(request).then(response => {
    cache.put(request, response.clone());
    return response;
  });

  return cached ?? fetchAndUpdate; // кэш если есть, иначе ждём сеть
}

// 4. Cache Only — только для ресурсов, pre-cached при установке SW
async function cacheOnly(request: Request): Promise<Response> {
  const cached = await caches.match(request);
  if (!cached) throw new Error(`Not in cache: ${request.url}`);
  return cached;
}

// 5. Network Only — без кэша (аналитика, POST-запросы)
async function networkOnly(request: Request): Promise<Response> {
  return fetch(request);
}
```

```ts
// Полный Service Worker с маршрутизацией стратегий
self.addEventListener('fetch', (event: FetchEvent) => {
  const { request } = event;
  const url = new URL(request.url);

  // Статика с хэшем → Cache First (кэшируем навсегда)
  if (url.pathname.startsWith('/_next/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // API → Network First (свежие данные, фолбек на кэш)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // HTML страницы → Network First (всегда актуальный HTML)
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  // Всё остальное → Stale While Revalidate
  event.respondWith(staleWhileRevalidate(request));
});
```

### Workbox — абстракция над Cache API

```ts
// workbox-config.js — используется с next-pwa или @ducanh2912/next-pwa
import { registerRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';

// Статика Next.js — навсегда
registerRoute(
  ({ url }) => url.pathname.startsWith('/_next/static/'),
  new CacheFirst({
    cacheName: 'next-static',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxAgeSeconds: 365 * 24 * 60 * 60 }),
    ],
  })
);

// Изображения — Cache First, но не дольше 30 дней
registerRoute(
  ({ request }) => request.destination === 'image',
  new CacheFirst({
    cacheName: 'images',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 100,           // максимум 100 изображений
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 дней
      }),
    ],
  })
);

// API — Stale While Revalidate
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new StaleWhileRevalidate({
    cacheName: 'api-cache',
    plugins: [
      new ExpirationPlugin({ maxAgeSeconds: 60 * 60 }), // 1 час
    ],
  })
);
```

## Стратегия кэш-буcтинга при деплое

```txt
Проблема деплоя:
  Деплоем новую версию HTML + JS.
  HTML обновился (no-cache → перезагрузился).
  JS старый (max-age=1year, браузер не знает что обновился).
  Результат: новый HTML с API для нового JS +
             старый JS → ошибки.

Решение — content-addressable filenames:
  Имя файла содержит хэш от содержимого.
  Содержимое изменилось → имя изменилось → кэш не сработал.
  Содержимое то же → имя то же → кэш сработал.

  main.abc123.js → main.def456.js (новая версия)

Webpack/Vite/Next.js делают это автоматически.
Ваша задача: убедиться что HTML не кэшируется или имеет
короткий max-age/no-cache.
```

```ts
// Vite — content hash в именах файлов
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name].[hash].js',
        chunkFileNames: 'assets/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash].[ext]',
      },
    },
  },
});
```

## DevTools-воркфлоу для кэширования

```txt
Chrome DevTools → Network tab:

  Колонка "Status":
    200 — свежий ответ от сервера
    304 — Not Modified (conditional request, кэш валиден)
    "(disk cache)" — из HTTP disk cache
    "(memory cache)" — из memory cache

  Важно: при тестировании кэша ВСЕГДА
  снимать галочку "Disable cache" в DevTools!
  (она отправляет Cache-Control: no-cache в запросах)

  Правый клик → Copy → Copy as fetch:
  → скопирует запрос с реальными заголовками для воспроизведения

Chrome DevTools → Application tab:
  → Storage → Cache Storage: содержимое Service Worker кэша
  → Service Workers: статус SW, unregister, bypass для сети

  Кнопка "Update on reload" в Service Workers:
  → принудительно обновляет SW при перезагрузке (для разработки)

curl для диагностики заголовков (без браузерных эффектов):
  curl -I https://example.com/api/articles
  curl -I -H 'If-None-Match: "abc123"' https://example.com/api/articles
```

## Связь с другими темами

```txt
[Performance Metrics]     — кэш CDN напрямую снижает TTFB;
                            Service Worker cache = мгновенный FCP
                            при повторных визитах
[Core Web Vitals]         — repeat visit LCP зависит от кэша
                            изображений и JS; Cache-Control
                            стратегия для HTML влияет на LCP
[Resource Loading]        — prefetch сохраняет в HTTP cache;
                            Service Worker кэш перехватывает
                            prefetched ресурсы
[JavaScript Performance]  — vendor chunk кэшируется отдельно
                            от app chunk; content hash = эффективный
                            cache busting без инвалидации вручную
```

## Типичные ошибки на интервью

- **"no-cache значит не кэшировать"** — критическая ошибка. `no-cache` означает "можно кэшировать, но нужно валидировать перед использованием". Если ETag совпал — браузер отдаёт из кэша (304). Не кэшировать вообще — это `no-store`.

- **"max-age=31536000 для всего — максимальная производительность"** — нет. Для HTML-документов это катастрофа: после деплоя пользователи будут год видеть старую версию. Правило: `max-age` с большим значением только для ресурсов с хэшем в имени.

- **"Service Worker кэш — то же что HTTP кэш"** — разные механизмы. HTTP кэш (disk cache) управляется браузером через заголовки. Service Worker Cache API — управляется вашим кодом. SW кэш живёт дольше, более управляем, но требует явного управления устаревшими версиями.

- **"CDN кэш работает автоматически"** — нет без правильного `Cache-Control`. Если сервер отвечает `Cache-Control: private` или `no-store` — CDN ничего не закэширует. `public, s-maxage=3600` — правильная настройка для CDN.

- **"stale-while-revalidate — то же что max-age"** — разные модели. `max-age` говорит "кэш свежий до этого момента, потом ждать сервер". `stale-while-revalidate` говорит "после max-age отдавать stale и обновлять в фоне". Пользователь не ждёт, получает стale немедленно.

- **"Проблем с кэшем нет если использовать React Query"** — React Query кэширует данные в памяти (не в HTTP cache, не в Service Worker). Перезагрузка страницы — все данные пропали. HTTP Cache-Control заголовки и Service Worker — разные уровни кэширования, работающие вместе, а не вместо друг друга.

- **"Cache invalidation — просто, просто меняешь версию"** — это одна из "двух сложных задач в CS". Проблемы: когда инвалидировать (не слишком рано, не слишком поздно), как инвалидировать связанные ресурсы (статья изменилась → инвалидировать список статей, страницу статьи, API-ответ), как избежать cache stampede при инвалидации популярного ресурса.
