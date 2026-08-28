<!-- verified: 2026-06-16, corrections: 0 -->
# Caching Strategies

## Почему кэширование — самая важная оптимизация

Кэширование — единственная оптимизация, которая может снизить время загрузки **до нуля**: закэшированный ресурс не требует ни одного байта сетевого трафика.

Каждый запрос без кэша сначала платит полную стоимость установки связи: поиск домена, новое соединение, рукопожатие шифрования. И только потом идёт обмен с сервером. Это 200–800ms даже для крошечного файла. Запрос из кэша всё это пропускает:

| Откуда приходит ответ | Цена |
|---|---|
| Кэш в памяти | практически 0ms — меньше 1ms из памяти |
| Дисковый кэш | 2–10ms на чтение с диска |
| Ближайший к пользователю узел CDN (сети доставки контента) | 10–50ms, один сетевой обход |

Браузер заглядывает в эти места в фиксированном порядке, от быстрого к медленному:

1. Кэш в памяти, пока вкладка ещё открыта.
2. Кэш Service Worker.
3. Дисковый кэш HTTP.
4. Push-кэш, который приходит из HTTP/2 и живёт недолго.
5. Сеть, если больше нигде ничего не нашлось.

## HTTP Cache-Control — основа всего

`Cache-Control` — главный заголовок. Его директивы решают, кому можно кэшировать ответ, как долго и нужно ли сначала проверять его актуальность.

### Директивы Cache-Control

| Директива | Что означает |
|---|---|
| `max-age=N` | Кэшировать N секунд, отсчёт от времени ответа. |
| `s-maxage=N` | То же самое, но только для общих кэшей — CDN и прокси. Там она перекрывает `max-age`. |
| `no-cache` | Кэшировать **можно**, но перед каждым использованием **нужно** проверить актуальность. Это не значит "не кэшировать". |
| `no-store` | Не кэшировать вообще. Эта директива — для чувствительных данных. |
| `public` | Можно хранить в общем кэше. |
| `private` | Только в браузере самого пользователя, в общий кэш класть нельзя. |
| `immutable` | Ресурс никогда не изменится, поэтому не проверять его даже при явном обновлении страницы. |
| `must-revalidate` | После истечения `max-age` нужно проверить актуальность перед отдачей. Отдавать устаревшее нельзя даже при ошибке сервера. |
| `stale-while-revalidate=N` | Ещё N секунд отдавать устаревший ответ, обновляя его в фоне. |
| `stale-if-error=N` | Отдавать устаревший ответ до N секунд, если сервер недоступен. |

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

ETag — это отпечаток одной версии ресурса, обычно хэш её содержимого. Браузер запоминает отпечаток и отправляет его обратно при следующем запросе. Если отпечаток на сервере совпал, сервер отвечает `304 Not Modified` вообще без тела. Если не совпал — `200` с новым содержимым.

```txt
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

С обычным `no-cache` браузер отправляет запрос, ждёт сервер, получает ответ и только потом его показывает. Эта задержка возникает **каждый раз**.

С `stale-while-revalidate` порядок другой. Копия из кэша показывается сразу, пусть и устаревшая. Одновременно браузер тянет свежую копию и обновляет кэш. Пользователь ждёт 0ms, а следующий запрос уже получает свежие данные.

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

Без CDN пользователь из Токио идёт на сервер в Вирджинии. Это примерно 150ms только на дорогу туда и обратно, не считая соединения и рукопожатия шифрования, о которых сказано выше.

С CDN — Cloudflare, CloudFront, Fastly — тот же пользователь идёт на ближайший узел в Токио, до которого 5–10ms. Узел смотрит в собственный кэш:

- **Попадание** — отвечает сразу, за те же 5–10ms.
- **Промах** — один раз идёт на исходный сервер, платит 300ms и кэширует ответ. Все последующие запросы снова попадают в кэш.

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

Проблема — цепная реакция. Запись в кэше протухла, и 10 000 пользователей спрашивают ресурс в один и тот же момент. Это 10 000 запросов, разом ушедших на исходный сервер, и он падает.

Три выхода:

1. **`stale-while-revalidate`** — на сервер уходит только один фоновый запрос, а остальные получают устаревшую копию.
2. **Probabilistic Early Expiration (PER)** — начинать обновление заранее и вразнобой, ещё до истечения записи. Так работает алгоритм XFetch.
3. **Блокировка или мьютекс** — первый запрос забирает блокировку, а остальные либо ждут, либо получают устаревшие данные.

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

## Стратегия кэш-бустинга при деплое

Проблема деплоя выглядит так. Вы выкатываете новую версию HTML и JS. HTML отдаётся с `no-cache`, поэтому браузер забирает его заново. У JS всё ещё стоит `max-age=1 год`, и браузер не знает, что файл изменился. В итоге новый HTML работает со старым JS-бандлом по новому контракту API, и получаются ошибки в рантайме.

Лечится это именами файлов по содержимому. В имя попадает хэш содержимого, поэтому `main.abc123.js` превращается в `main.def456.js`, когда содержимое меняется. Изменилось содержимое — изменилось имя — промах кэша. Не изменилось — имя то же, и это попадание.

Webpack, Vite и Next.js делают это сами. Ваша часть — следить, чтобы сам HTML не кэшировался агрессивно: `no-cache` или короткий `max-age`.

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

Во вкладке **Network** в Chrome DevTools колонка `Status` говорит, откуда пришёл каждый ответ:

- `200` — свежий ответ от сервера.
- `304` — Not Modified: условный запрос подтвердил, что кэш ещё годен.
- `(disk cache)` — отдано из дискового кэша HTTP.
- `(memory cache)` — отдано из кэша в памяти.

На чём спотыкаются все: когда вы проверяете кэширование, **снимите** галочку `Disable cache` в DevTools. Пока она стоит, каждый запрос уходит с заголовком `Cache-Control: no-cache`.

Правый клик по запросу и Copy → Copy as fetch воспроизведут его с настоящими заголовками.

Во вкладке **Application** раздел Storage → Cache Storage показывает, что закэшировал Service Worker. Раздел Service Workers показывает его состояние и позволяет снять регистрацию или обойти воркер через сеть. Галочка `Update on reload` там заставляет воркер обновляться при каждой перезагрузке страницы, и это то, что нужно во время разработки.

Чтобы посмотреть заголовки без вмешательства браузера, используйте `curl`:

```bash
curl -I https://example.com/api/articles
curl -I -H 'If-None-Match: "abc123"' https://example.com/api/articles
```

## Связь с другими темами

- [Performance Metrics](./02-performance-metrics.md) — кэш CDN напрямую снижает TTFB (time to first byte — время до первого байта). Кэш Service Worker даёт мгновенный FCP (First Contentful Paint) при повторных визитах.
- [Core Web Vitals](./01-core-web-vitals.md) — LCP (Largest Contentful Paint) при повторном визите зависит от кэша картинок и JS. Стратегия `Cache-Control` для HTML тоже на него влияет.
- [Resource Loading](./03-resource-loading.md) — `prefetch` пишет в HTTP-кэш, а кэш Service Worker перехватывает предзагруженные ресурсы.
- [JavaScript Performance](./04-javascript-performance.md) — vendor-чанк кэшируется отдельно от чанка приложения, а хэш содержимого даёт эффективный cache busting без ручной инвалидации.

## Типичные ошибки на интервью

- **"no-cache значит не кэшировать"** — критическая ошибка. Директива на самом деле говорит: кэшировать можно, но перед каждым использованием нужно проверить актуальность. Если ETag совпал, браузер отдаёт свою копию и получает 304. А "не кэшировать вообще" — это `no-store`.

- **"max-age=31536000 для всего — максимальная производительность"** — нет. Для HTML-документов это катастрофа: после деплоя пользователи будут год видеть старую версию. Правило: `max-age` с большим значением только для ресурсов с хэшем в имени.

- **"Service Worker кэш — то же что HTTP кэш"** — разные механизмы. HTTP кэш (disk cache) управляется браузером через заголовки. Service Worker Cache API — управляется вашим кодом. Кэш Service Worker живёт дольше и лучше управляем, но устаревшими версиями приходится управлять вручную.

- **"CDN кэш работает автоматически"** — не работает без правильного `Cache-Control`. Если сервер отвечает `Cache-Control: private` или `no-store` — CDN ничего не закэширует. `public, s-maxage=3600` — правильная настройка для CDN.

- **"stale-while-revalidate — то же что max-age"** — разные модели. `max-age` говорит "кэш свежий до этого момента, потом ждать сервер". `stale-while-revalidate` говорит "после max-age отдавать устаревшее и обновлять в фоне". Пользователь не ждёт: устаревшие данные приходят мгновенно.

- **"Проблем с кэшем нет если использовать React Query"** — React Query кэширует данные в памяти (не в HTTP cache, не в Service Worker). Перезагрузка страницы — все данные пропали. HTTP Cache-Control заголовки и Service Worker — разные уровни кэширования, работающие вместе, а не вместо друг друга.

- **"Cache invalidation — просто, просто меняешь версию"** — это одна из двух знаменитых сложных задач в информатике. Сложного тут три вещи. Понять, *когда* инвалидировать: не слишком рано и не слишком поздно. Понять, *что ещё* инвалидировать: статья изменилась, значит устарели список статей, страница статьи и ответ API. И не поймать cache stampede, когда инвалидируется популярный ресурс.
