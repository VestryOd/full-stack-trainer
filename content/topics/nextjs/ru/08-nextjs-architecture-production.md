<!-- verified: 2026-06-05, corrections: 0 -->
# Продакшен-архитектура и лучшие практики

## Где Next.js стоит в стеке

Продакшен-приложение на Next.js — это не весь бэкенд. Это слой рендеринга плюс слой BFF (Backend For Frontend), и он занимает одно вполне определённое место:

```txt
Browser
 ↓
CDN / Edge
 ↓
Next.js (rendering + BFF layer)
 ↓
Backend APIs / Microservices
 ↓
Database
```

Все архитектурные вопросы ниже — про то, где именно вы проводите границы внутри этого места. На интервью это спрашивают разными словами:

- "Как бы вы построили проект на Next.js?"
- "Где граница между Next и бэкендом?"
- "Что вы вынесете в Server Actions, а что в Route Handlers?"

## Вариант 1: Next как тонкий frontend-слой

```txt
Next.js (UI, SSR/SSG)
 ↓
NestJS API (бизнес-логика, авторизация, БД)
 ↓
PostgreSQL
```

Next отвечает только за рендеринг и UX (user experience, пользовательский опыт), вся бизнес-логика — в отдельном backend-сервисе. Это понятная и распространённая схема. Особенно хорошо она ложится, когда бэкенд уже существует и обслуживает несколько клиентов: веб, мобильное приложение, партнёрский API. Next тогда просто ещё один потребитель этого API.

## Вариант 2: Next как BFF (Backend For Frontend)

```txt
Browser
 ↓
Next.js (агрегирует, трансформирует, кеширует)
 ↓
 ├─→ User Service
 ├─→ Product Service
 └─→ Order Service
      ↓
     PostgreSQL / отдельная БД на каждый сервис
```

Next агрегирует данные из нескольких микросервисов и отдаёт фронтенду единый, заточенный под конкретный экран API (через Route Handlers или прямо через Server Components). Frontend не знает про внутреннюю топологию сервисов — вся сложность инкапсулирована в BFF.

**Где проходит граница BFF vs полноценный backend** — практический вопрос. BFF хорош для *агрегации и трансформации под UI (user interface, пользовательский интерфейс)*. Например: объединить данные из трёх сервисов в один JSON для конкретного экрана или кешировать на уровне Next.

Чем BFF быть не должен — местом, где живёт бизнес-логика с побочными эффектами на несколько доменов. Канонический пример — "оформление заказа": оно должно атомарно списать остатки, создать платёж и отправить уведомление. Это ответственность доменных сервисов с собственными транзакционными гарантиями.

## Server Actions vs Route Handlers — когда что

Это один из самых частых "практических" вопросов на Next.js собеседованиях, и ответ "и то, и то — для бэкенда" — недостаточен.

```tsx
// Server Action — мутация, инициированная формой/UI текущего приложения
'use server';

import { revalidatePath } from 'next/cache';

export async function createComment(formData: FormData) {
  const text = formData.get('text');
  if (typeof text !== 'string' || text.trim().length === 0) {
    return { error: 'Comment cannot be empty' };
  }

  await db.comment.create({ data: { text, postId: formData.get('postId') as string } });
  revalidatePath('/posts'); // инвалидация кеша сразу после мутации
  return { success: true };
}
```

```tsx
// app/posts/[id]/page.tsx
import { createComment } from './actions';

export default function PostPage() {
  return (
    <form action={createComment}>
      <textarea name="text" />
      <button type="submit">Send</button>
    </form>
  );
}
```

```ts
// Route Handler — публичный API endpoint, вызываемый извне (не только из UI)
// app/api/webhooks/stripe/route.ts
export async function POST(request: Request) {
  const signature = request.headers.get('stripe-signature');
  const body = await request.text();

  const secret = process.env.STRIPE_WEBHOOK_SECRET!;
  const event = stripe.webhooks.constructEvent(body, signature!, secret);
  // ... обработка события
  return new Response('ok', { status: 200 });
}
```

| | Server Actions | Route Handlers |
|---|---|---|
| Кто вызывает | Формы и UI-код этого же приложения | Любой клиент: webhook, mobile-приложение, сторонний сервис |
| Контракт | Неявный (привязан к конкретной форме/функции) | Явный версионируемый контракт REST (representational state transfer) |
| Типичные кейсы | CRUD-мутации (create, read, update, delete), формы, optimistic UI | Webhooks, публичный API, интеграции, OAuth callbacks |
| Кеш-инвалидация | `revalidatePath`/`revalidateTag` прямо в действии | Обычно тоже, но часто как отдельный `/api/revalidate` |

Здесь два антипаттерна. Первый — городить публичный API через Server Actions. Под капотом они создают неявные, "магические" endpoint'ы: без версионирования и не рассчитанные на внешних потребителей.

Второй — делать Route Handler для каждой формы в UI. Так теряется прогрессивное улучшение: `<form action={...}>` работает даже без JS.

## Edge Runtime vs Node.js Runtime

```ts
// app/api/heavy/route.ts
export const runtime = 'nodejs'; // по умолчанию для Route Handlers

// app/api/light/route.ts
export const runtime = 'edge'; // выполняется на Edge (V8 isolates)
```

| | Node.js Runtime | Edge Runtime |
|---|---|---|
| Доступные API | Полный Node.js (`fs`, `net`, нативные модули) | Web-стандартные API (fetch, crypto, Streams) |
| Холодный старт | Выше | Минимальный/отсутствует |
| География | Один регион (или несколько, в зависимости от хостинга) | Близко к пользователю, множество edge-локаций |
| ORM (Prisma и т.п.) | Работает "из коробки" | Требует Edge-совместимого драйвера/адаптера |
| Размер бандла | Без жёстких лимитов | Лимиты на размер (обычно 1-4 мегабайта) |

Практическое правило: всё, что открывает прямое TCP-соединение (Transmission Control Protocol) к реляционной БД (базе данных), требует Node runtime. Обычный случай — Prisma с `pg`. Edge подходит для лёгких операций, критичных по латентности: geo-логика, простые проверки токенов, прокси-запросы к внешним API.

## Стратегия кеширования — не "одна модель", а карта по экранам

Production-приложение почти никогда не использует одну модель рендеринга. Хороший ответ на "как вы будете кешировать e-commerce" — это таблица, а не одно слово:

```txt
Главная         → SSG + revalidate раз в час (почти статика)
Категории       → ISR, revalidateTag('category-X') при правках
Страница товара → ISR + on-demand revalidate (webhook CMS/PIM)
Поиск/фильтры   → SSR или CSR (комбинации непредсказуемы)
Корзина         → CSR (state привязан к сессии/cookie юзера)
Checkout        → Server Actions или Route Handler, Node runtime
Личный кабинет  → SSR (cookies() для сессии) или CSR
Admin-панель    → CSR, свой auth-слой, SEO не нужен
```

## Переменные окружения — граница безопасности

```bash
# .env
DATABASE_URL=postgres://...          # доступен ТОЛЬКО на сервере
STRIPE_SECRET_KEY=sk_live_...         # доступен ТОЛЬКО на сервере
NEXT_PUBLIC_API_URL=https://api...    # попадает в клиентский бандл
```

```ts
// ❌ Опасно — секрет читается в модуле, который может импортировать клиент
export function getApiKey() {
  // если этот модуль импортирован в 'use client' файл,
  // значение может быть инлайнено в клиентский бандл при сборке
  return process.env.STRIPE_SECRET_KEY;
}

// ✅ Защита через server-only
import 'server-only';
export function getApiKey() {
  return process.env.STRIPE_SECRET_KEY;
}
```

Правило `NEXT_PUBLIC_*` — это не "удобный префикс". Это **инлайнинг значения переменной в JS-бандл во время сборки**.

Следствие нетривиальное: смена значения `NEXT_PUBLIC_*` требует **пересборки** приложения. Поменять переменную окружения в runtime-конфигурации контейнера или хостинга недостаточно — старое значение останется "зашитым" в уже собранный бандл.

## Мониторинг и наблюдаемость

```txt
Сбор ошибок:      Sentry, Bugsnag — ошибки Server Components
                    и Client Components ловим отдельно
Производительность: Vercel Analytics, Core Web Vitals, Datadog
Серверные метрики: логи Route Handlers и Server Actions,
                    латентность запросов к БД и внешним API
```

Отдельный нюанс App Router: ошибка в Server Component происходит на сервере и **не попадает в консоль браузера**. Без серверного сбора ошибок (скажем, Sentry с серверной библиотекой) такую ошибку можно вообще не заметить. Команда увидит только общее "Something went wrong" из `error.tsx`.

## Деплой

```txt
Vercel        — "родная" платформа, нулевая конфигурация для
                 ISR, Edge, Streaming; vendor lock-in для
                 специфичных фич (on-demand ISR может работать
                 иначе на других платформах)
Self-hosted   — next start после next build, либо Docker плюс
                 Node.js-сервер; для ISR нужна персистентная
                 файловая система или внешний кеш
Static export — output: 'export' превращает приложение в чистую
                 статику: без динамических Server Components, без
                 Route Handlers, без Image Optimization API.
                 Подходит для простых сайтов без серверной части
```

## Сквозной пример: e-commerce

```txt
Главная, категории → SSG/ISR, раздаётся с CDN
Карточка товара    → ISR + revalidateTag по webhook от PIM
Поиск              → SSR (Route Handler проксирует в Elasticsearch)
Корзина            → CSR + localStorage/cookie, синхронизация
                     через Server Action
Checkout           → Server Actions (создание заказа) + Route
                     Handler (webhook платёжного провайдера)
Кабинет, заказы    → SSR (cookies() для сессии)
Admin              → CSR, отдельный auth, runtime: 'nodejs'
```

## Самый сильный senior-ответ

На вопрос "что самое важное в production Next.js приложении" слабый ответ перечисляет фичи: SSR (серверный рендеринг), ISR (инкрементальная статическая регенерация), Server Actions.

Сильный ответ говорит, что единой "правильной" модели не существует. Продакшен-приложение — это *композиция* решений по рендерингу, кешированию и runtime, принимаемых **для каждого экрана отдельно**. Входные данные для каждого решения — требования к SEO (поисковой оптимизации), свежесть данных, латентность и стоимость вычислений.

Архитектор отвечает не за "выбор Next.js фичи", а за то, чтобы эта композиция была явной и документированной. Иначе она вырождается в случайный набор `cache: 'no-store'`, расставленных по одному на каждый баг с устаревшими данными.

## Типичные ошибки на интервью

- **"Next.js заменяет backend полностью"** — нет. В большинстве продакшен-архитектур Next — это слой рендеринга и BFF, а не источник истины для бизнес-логики и данных.

- **"Server Actions — это просто новый способ писать API"** — нет. У них другая модель вызова: привязка к конкретным формам и компонентам, без стабильного публичного контракта. И случаи использования другие, чем у Route Handlers.

- **Не знают, что Edge Runtime ограничивает выбор ORM и драйверов БД** — стандартному Prisma с `pg` нужен адаптер, чтобы работать на Edge. Это частая причина "ошибок в проде, которых не было локально".

- **"NEXT_PUBLIC_ переменные можно менять в runtime без пересборки"** — нет, они инлайнятся в бандл на этапе `next build`. Изменение требует ребилда.

- **Дают один ответ на "как кешировать сайт", не различая экраны** — сильный ответ — это таблица "тип страницы → стратегия". Единое решение для всего приложения таким ответом не является.

- **Не упоминают, что ошибки Server Components не видны в браузере** — а это важно для наблюдаемости. Без серверного сбора ошибок часть продакшен-багов остаётся полностью невидимой для команды.

- **"Static export (`output: 'export'`) поддерживает все фичи App Router"** — нет. Он исключает Server Actions, динамические Route Handlers, Image Optimization API и любую серверную динамику. Фактически это режим "только статика".
