# Server Components

## Сдвиг ментальной модели

До React Server Components (RSC) React всегда выполнялся на клиенте. Серверный рендеринг (SSR) означал «запустить тот же React-код на сервере для генерации HTML, затем гидратировать его на клиенте». Код был идентичным — он выполнялся в обоих окружениях.

RSC вводит фундаментальное разделение:

```txt
ДО RSC:
  Все компоненты выполняются на клиенте.
  SSR = запуск клиентских компонентов на сервере тоже (для первоначального HTML).
  Каждый компонент отправляет свой JS в браузер.

С RSC:
  Server Components выполняются ТОЛЬКО на сервере.
  Client Components выполняются на клиенте (и на сервере для SSR).
  Server Components никогда не отправляют свой код в браузер.
  Граница между ними явная: 'use client'.
```

Это не просто оптимизация производительности — это другой способ думать о том, где живёт код.

---

## Что где исполняется

```txt
SERVER COMPONENTS                       CLIENT COMPONENTS
─────────────────────────────────────   ────────────────────────────────────
Выполняются: только на сервере          Выполняются: браузер + сервер (для SSR)
  (build time или request time)
Могут: async/await напрямую             Могут: useState, useEffect, обработчики событий
Могут: доступ к БД, файловой системе,  Могут: браузерные API (window, localStorage)
       переменным окружения             Могут: refs, context (как provider или consumer)
Могут: импортировать тяжёлые server-
       only библиотеки (без влияния
       на размер бандла)
Не могут: useState, useEffect           Не могут: прямой доступ к БД/файловой системе
Не могут: браузерные API                Не могут: async тело компонента (пока)
Не могут: обработчики событий           Не могут: импортировать server-only модули
```

```tsx
// SERVER COMPONENT — выполняется на сервере, результат сериализуется и отправляется клиенту
// Нет 'use client' = server component по умолчанию в Next.js App Router

import { db } from '@/lib/db'; // db клиент — никогда не отправляется в браузер

async function ProductList() {
  const products = await db.product.findMany(); // прямой доступ к БД, API не нужен

  return (
    <ul>
      {products.map(p => (
        <li key={p.id}>
          {p.name} — {p.price}₽
          <AddToCartButton productId={p.id} /> {/* Client Component */}
        </li>
      ))}
    </ul>
  );
}
```

```tsx
// CLIENT COMPONENT — выполняется в браузере (и на сервере для SSR)
'use client';

import { useState } from 'react';

function AddToCartButton({ productId }: { productId: string }) {
  const [added, setAdded] = useState(false);

  return (
    <button onClick={() => setAdded(true)}>
      {added ? 'Добавлено ✓' : 'В корзину'}
    </button>
  );
}
```

---

## Граница сериализации

Когда Server Component рендерит Client Component, он не может передавать произвольные JavaScript-объекты через границу — только **сериализуемые значения**. Сервер создаёт JSON-подобный wire format (RSC payload), который клиент десериализует.

```txt
СЕРВЕР                         WIRE FORMAT               КЛИЕНТ
──────────────────────────────────────────────────────────────────
Server Component рендерит  →   RSC payload (JSON-like)  →  Клиент гидратирует
                               - деревья React-элементов
                               - сериализованные props
                               - ссылки на Client Component чанки
```

**Что может пересечь границу сериализации (props от Server к Client Components):**

```tsx
// ✅ Сериализуемые — безопасно передавать как props:
<ClientComp
  str="привет"
  num={42}
  bool={true}
  arr={[1, 2, 3]}
  obj={{ name: 'Алиса' }}
  date={new Date().toISOString()} // сериализуйте даты в строки
  node={<AnotherServerComponent />} // React-элементы — сериализуемы
/>
```

**Что НЕ может пересечь границу:**

```tsx
// ❌ Не сериализуемые — нельзя передавать как props в Client Components:
<ClientComp
  fn={() => console.log('hi')}    // функции — не сериализуемы
  classInstance={new MyClass()}   // экземпляры классов с методами
  symbol={Symbol('id')}           // Symbol
  map={new Map()}                 // Map, Set, WeakMap
  undefined={undefined}           // undefined (в JSON его нет)
/>
```

Функции не могут пересекать границу сервер→клиент — их сериализация как кода была бы угрозой безопасности. Именно поэтому обработчики событий должны жить в Client Components.

### Передача children — паттерн «поднятия»

Самый мощный обходной путь: Server Component может рендерить Client Component и передавать *другие Server Components* как `children`:

```tsx
// ✅ Server Component может передаваться как children в Client Component:
// Это работает, потому что children — React-элементы — сериализуемы.

// ServerPage.tsx (Server Component):
import { ClientShell } from './ClientShell';
import { HeavyServerComponent } from './HeavyServerComponent';

export default function Page() {
  return (
    <ClientShell>
      <HeavyServerComponent /> {/* Server Component передаётся как children */}
    </ClientShell>
  );
}

// ClientShell.tsx (Client Component):
'use client';
import { useState } from 'react';

export function ClientShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(!open)}>Переключить</button>
      {open && children} {/* children — уже готовый HTML с сервера */}
    </div>
  );
}
```

`HeavyServerComponent` выполняется на сервере и сериализуется в RSC payload как React-элемент. `ClientShell` получает его как `children` — сериализованное поддерево, — а не как функцию, которую можно вызвать. Код серверного компонента никогда не попадает в браузер.

---

## Когда требуется 'use client'

`'use client'` — **маркер границы**, а не директива «этот компонент должен выполняться только на клиенте». Он отмечает точку, где дерево server component'ов заканчивается и начинается дерево client component'ов.

```tsx
// 'use client' требуется когда компонент использует:

// 1. React state:
'use client';
const [count, setCount] = useState(0);

// 2. React effects:
'use client';
useEffect(() => { ... }, []);

// 3. Браузерные API:
'use client';
const width = window.innerWidth;

// 4. Обработчики событий (нужны замыкания с setState):
'use client';
<button onClick={handleClick}>

// 5. Потребители Context (useContext):
'use client';
const theme = useContext(ThemeContext);

// 6. useRef, useReducer, useCallback, useMemo:
'use client';
const ref = useRef(null);
```

**'use client' распространяется вниз:** как только компонент является Client Component, все компоненты, которые он импортирует, также считаются Client Components — даже если у них нет `'use client'`. Директива отмечает корень клиентского поддерева, а не отдельные компоненты.

```txt
Page (Server) ── импортирует ──▶ ProductList (Server) ── импортирует ──▶ AddToCart ('use client')
                                                                            └── Button (без директивы)
                                                                                  ↑ неявно Client
                                                                                    (импортирован Client'ом)
```

### Директива 'use server'

`'use server'` помечает функцию как **Server Action** — функцию, которую можно вызвать с клиента, но которая выполняется на сервере:

```tsx
// В файле Server Component:
async function createUser(formData: FormData) {
  'use server'; // эта функция выполняется на сервере

  const name = formData.get('name') as string;
  await db.user.create({ data: { name } });
  revalidatePath('/users');
}

export default function NewUserForm() {
  return (
    <form action={createUser}>
      <input name="name" type="text" />
      <button type="submit">Создать</button>
    </form>
  );
}
```

Или в отдельном файле actions с `'use server'` вверху:

```tsx
// actions.ts
'use server'; // все экспорты из этого файла — Server Actions

export async function deletePost(id: string) {
  await db.post.delete({ where: { id } });
  revalidatePath('/posts');
}

export async function updatePost(id: string, data: Partial<Post>) {
  await db.post.update({ where: { id }, data });
  revalidatePath(`/posts/${id}`);
}
```

Server Actions выглядят как обычные async-функции, но выполняются на сервере. При вызове из Client Component они сериализуют аргументы, отправляют HTTP POST запрос на сервер, выполняются и возвращают сериализованный результат. Клиент никогда не видит серверный код.

---

## Streaming SSR: объяснение

Традиционный SSR: сервер рендерит всю страницу в HTML, отправляет всё сразу, затем клиент загружает JS и гидратирует всё.

```txt
ТРАДИЦИОННЫЙ SSR:
  Сервер:  ──────────────── рендер всего ────────────── отправить HTML ──▶
  Клиент:  ──────────────────────────────── получить ── гидратировать ──▶
  TTFB:    долгий (нужно отрендерить всё перед отправкой чего-либо)
```

Streaming SSR (React 18): сервер отправляет HTML порциями по мере завершения рендера компонентов. Клиент начинает рендерить и гидратировать сразу при получении первой порции.

```txt
STREAMING SSR (React 18):
  Сервер:  ── отправить shell ─── рендер A ─ отправить A ─── рендер B ─ отправить B ──▶
  Клиент:  ── получить & показать shell ── получить & гидратировать A ── получить & гидратировать B ──▶
  TTFB:    быстрый (shell отправляется немедленно)
```

Границы Suspense — это точки разделения потока:

```tsx
// Next.js App Router — streaming автоматически с Suspense:
export default async function Page() {
  return (
    <div>
      <Header />           {/* рендерится немедленно — в начальном shell */}

      <Suspense fallback={<Skeleton />}>
        <SlowComponent />  {/* рендерится async — стримится когда готов */}
      </Suspense>

      <Suspense fallback={<Skeleton />}>
        <AnotherSlow />    {/* рендерится async — стримится независимо */}
      </Suspense>
    </div>
  );
}

async function SlowComponent() {
  await db.slowQuery();    // занимает 800мс
  return <div>...</div>;
}
```

Браузер получает и рендерит `<Header />` и оба `<Skeleton />` немедленно (TTFB быстрый). По мере того как каждый медленный компонент завершается на сервере, его HTML стримится и вставляется в страницу — границы Suspense заменяются реальным контентом.

### Selective hydration

Streaming также включает selective hydration: клиент может гидратировать компоненты в порядке приоритета. Если пользователь кликает на компонент, который ещё не гидратирован, React приоритизирует его гидратацию первым (перед другими компонентами, загрузившимися раньше).

---

## Причины hydration mismatch

Гидратация — процесс, при котором клиентский React прикрепляет обработчики событий и состояние к серверно-отрендеренному HTML. Для успешной гидратации клиент должен произвести точно тот же HTML, что и сервер.

**Hydration mismatch** возникает когда клиент и сервер рендерят разный вывод:

```tsx
// 1. Обращение к browser-only API во время рендера:
function Component() {
  // window не определён на сервере → рендерит '' на сервере, 'dark' на клиенте
  const theme = window.localStorage.getItem('theme') ?? 'light';
  return <div className={theme}>...</div>;
}

// Исправление: использовать useEffect (запускается только на клиенте) или кастомный хук:
function Component() {
  const [theme, setTheme] = useState('light'); // одинаково на сервере и клиенте
  useEffect(() => {
    setTheme(localStorage.getItem('theme') ?? 'light'); // обновляется после гидратации
  }, []);
  return <div className={theme}>...</div>;
}
```

```tsx
// 2. Дата/время рендерятся по-разному на сервере и клиенте:
function Timestamp() {
  return <span>{new Date().toLocaleTimeString()}</span>;
  // Сервер рендерит "10:30:00", клиент рендерит "10:30:01" → mismatch
}

// Исправление: использовать стабильное значение или рендерить чувствительные к времени данные только на клиенте:
function Timestamp() {
  const [time, setTime] = useState<string | null>(null);
  useEffect(() => {
    setTime(new Date().toLocaleTimeString());
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);
  }, []);
  return <span>{time}</span>; // null на сервере → нет mismatch; обновляется на клиенте
}
```

```tsx
// 3. Случайные значения:
function Avatar() {
  const color = `#${Math.random().toString(16).slice(2, 8)}`; // разное на сервере и клиенте
  return <div style={{ background: color }} />;
}

// Исправление: использовать стабильное значение из prop (ID пользователя, seed):
function Avatar({ userId }: { userId: string }) {
  const color = hashToColor(userId); // детерминировано — одинаково на сервере и клиенте
  return <div style={{ background: color }} />;
}
```

```tsx
// 4. Условный рендеринг на основе browser-only информации:
function Component() {
  if (typeof window !== 'undefined') {
    return <ClientOnlyContent />;
  }
  return null; // → разный вывод на сервере и клиенте: null vs <ClientOnlyContent />
}

// Исправление: использовать suppressHydrationWarning для известных намеренных mismatch,
// или флаг монтирования:
function Component() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null; // одинаково на сервере и клиенте (изначально)
  return <ClientOnlyContent />;
}
```

### suppressHydrationWarning

Для намеренных, известных несоответствий (вроде временной метки, которая всегда будет отличаться), React предоставляет обходной путь:

```tsx
<time suppressHydrationWarning>
  {new Date().toLocaleTimeString()}
</time>
```

Это подавляет предупреждение, но не предотвращает mismatch — клиент всё равно обновит DOM после гидратации. Используйте редко.

---

## RSC и размер бандла

Наиболее недооценённое преимущество Server Components: **нулевой вклад в клиентский бандл**.

```tsx
// Этот импорт остаётся на сервере — НИЧЕГО из него не попадает в браузер:
import { marked } from 'marked';           // 45 КБ
import { highlight } from 'highlight.js';  // 200 КБ
import { prisma } from '@/lib/prisma';     // + Prisma клиент

async function BlogPost({ slug }: { slug: string }) {
  const post = await prisma.post.findUnique({ where: { slug } });
  const html = marked(highlight(post!.content, { language: 'ts' }).value);
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
```

В традиционном клиентском React-приложении импорт `marked` и `highlight.js` добавил бы ~245 КБ в JavaScript-бандл. В Server Component эти библиотеки выполняются на сервере, и клиенту отправляется только отрендеренный HTML.

---

## Типичные ловушки на интервью

**«Может ли Server Component импортировать Client Component?»**
Да. Server Component может импортировать и рендерить Client Component. Тот включается в клиентский бандл и гидратируется в браузере. Обратное направление имеет ограничения: Client Component не может импортировать Server Component (импорт завершится ошибкой, потому что server-only код вроде `fs`, `db` или `'server-only'` импортов не может выполняться в браузере). Client Component *может* получать Server Component как `children` — переданный как уже отрендеренный сериализованный элемент.

**«Может ли Server Component использовать useState?»**
Нет. У Server Components нет жизненного цикла и состояния — они выполняются один раз на сервере и создают статический вывод. Если нужна интерактивность, этот кусок должен быть Client Component. Разделение: загрузка данных и статический рендеринг → Server Component; интерактивность, состояние, эффекты → Client Component.

**«Что такое RSC payload?»**
Когда рендерится дерево Server Component, React сериализует вывод в специальный JSON-подобный wire format (RSC payload). Он содержит: виртуальное DOM-дерево из серверного рендера, ссылки на Client Component чанки (чтобы клиент знал, какой JS загружать) и сериализованные props. Клиент получает этот payload, использует его для рендера дерева Client Component и гидратирует результат против серверно-сгенерированного HTML. Это не то же самое, что серверный HTML — RSC payload потребляется React runtime, а не HTML-парсером браузера.

**«'use client' означает что компонент выполняется только на клиенте?»**
Нет. Client Components выполняются на клиенте И на сервере (для SSR/SSG). `'use client'` означает: этот компонент и его поддерево используют клиентские возможности React (state, effects, браузерные API) и должны быть включены в клиентский бандл. Директива `'use client'` отмечает границу server/client, а не границу «никогда не выполнять на сервере».

**«В чём разница между Server Actions и API routes?»**
API routes — явные HTTP-эндпоинты: вы определяете маршрут, обрабатываете запрос, парсите тело, возвращаете ответ. Server Actions — функции, помеченные `'use server'`, которые фреймворк автоматически открывает как POST-эндпоинты. Вы вызываете их как обычные функции из Client Components. Фреймворк обрабатывает сериализацию, транспорт и десериализацию. Server Actions интегрируются с React form-моделью (`<form action={serverAction}>`) и могут вызывать `revalidatePath` / `revalidateTag` для инвалидации кешированных данных без полной перезагрузки страницы.
