# Серверные компоненты (Server Components)

## Сдвиг ментальной модели

До React Server Components (RSC) React всегда выполнялся на клиенте. Серверный рендеринг (SSR) означал одно: запустить тот же React-код на сервере, чтобы получить HTML. Дальше клиент этот HTML гидратировал — то есть привязывал к готовой разметке обработчики событий и состояние. Код был один и тот же, он выполнялся в обоих окружениях.

RSC вводит фундаментальное разделение:

```txt
ДО RSC:
  Все компоненты выполняются на клиенте.
  SSR = клиентские компоненты запускаются ещё и на сервере,
        чтобы получить первый HTML.
  Каждый компонент отправляет свой JS в браузер.

С RSC:
  Server Components выполняются только на сервере.
  Client Components выполняются на клиенте и на сервере (для SSR).
  Server Components никогда не отправляют свой код в браузер.
  Граница между ними явная: 'use client'.
```

Это не просто оптимизация производительности. Это другой способ думать о том, где живёт код.

---

## Что где исполняется

| | Серверные компоненты | Клиентские компоненты |
|---|---|---|
| Где выполняются | только на сервере: при сборке или на запрос | в браузере, а также на сервере для SSR |
| `useState`, `useEffect` | нет | да |
| Обработчики событий | нет | да |
| Браузерные API (`window`, `localStorage`) | нет | да |
| `async`/`await` в теле компонента | да | нет, пока не поддерживается |
| База данных, файловая система, переменные окружения | прямой доступ | прямого доступа нет |
| Тяжёлые серверные библиотеки | да, и без влияния на размер бандла | нет |
| Ref и контекст | нет | да, и как provider, и как consumer |

**Серверный модуль** (`server-only`) — это модуль, которому нельзя попадать в браузер: клиент базы данных, чтение файлов, файл с секретным ключом.

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

Когда серверный компонент рендерит клиентский, он не может передать через границу произвольные JavaScript-объекты. Пересекать границу могут только **сериализуемые значения**. Сервер создаёт RSC payload — JSON-подобный формат передачи по сети (wire format). Клиент его разбирает обратно.

```txt
Сервер                    формат передачи             Клиент
────────────────────────────────────────────────────────────
Серверный компонент  ──▶  RSC payload         ──▶  клиент
рендерит                  (похож на JSON)          гидратирует
                          - деревья React-элементов
                          - сериализованные пропсы
                          - ссылки на чанки клиентских компонентов
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

**Что пересечь границу не может:**

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

Функции не могут пересекать границу сервер→клиент: сериализовать их пришлось бы как код, а это угроза безопасности. Именно поэтому обработчики событий должны жить в клиентских компонентах.

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

`HeavyServerComponent` выполняется на сервере и сериализуется в RSC payload как React-элемент. `ClientShell` получает его как `children`, то есть как сериализованное поддерево, а не как функцию, которую можно вызвать. Код серверного компонента никогда не попадает в браузер.

---

## Когда требуется 'use client'

`'use client'` — **маркер границы**, а не указание «выполнять этот компонент только на клиенте». Он отмечает точку, где заканчивается дерево серверных компонентов и начинается дерево клиентских.

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

**'use client' распространяется вниз.** Как только компонент стал клиентским, все компоненты, которые он импортирует, тоже становятся клиентскими. Это верно даже если у них самих нет `'use client'`. Директива отмечает корень клиентского поддерева, а не отдельные компоненты.

```txt
Page (серверный)
  → импортирует ProductList (серверный)
      → импортирует AddToCart ('use client')   ← граница
          → импортирует Button (без директивы)

У Button своей директивы нет. Но его импортировал клиентский
компонент — значит, Button тоже клиентский.
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

Server Actions выглядят как обычные async-функции, но выполняются на сервере. При вызове из клиентского компонента они сериализуют аргументы, отправляют на сервер POST-запрос, выполняются и возвращают сериализованный результат. Клиент никогда не видит серверный код.

---

## Потоковый серверный рендеринг (Streaming SSR)

Традиционный SSR: сервер рендерит всю страницу в HTML, отправляет всё сразу, затем клиент загружает JS и всё гидратирует. Страдает от этого метрика TTFB — time to first byte, задержка до первого байта ответа в браузере.

```txt
Традиционный SSR
  Сервер: ──── рендер всей страницы ──── отправка HTML ──▶
  Клиент: ─────────────────── приём ──── гидратация ──▶

  TTFB долгий: пока не отрендерено всё, не отправлено ничего.
```

Потоковый SSR (React 18): сервер отправляет HTML порциями, по мере того как компоненты дорендериваются. Клиент начинает рендерить и гидратировать сразу, как пришла первая порция. Первая порция называется **shell** — это каркас страницы, та её часть, которая ничего не ждёт.

```txt
Потоковый SSR (React 18)
  Сервер: shell ─ рендер A ─ отдал A ─ рендер B ─ отдал B ──▶
  Клиент: показал shell ─── гидратация A ──── гидратация B ──▶

  TTFB короткий: каркас уходит в браузер сразу.
```

Границы Suspense — это точки разделения потока:

```tsx
// Next.js App Router — streaming автоматически с Suspense:
export default async function Page() {
  return (
    <div>
      <Header />           {/* рендерится немедленно — в начальном shell */}

      <Suspense fallback={<Skeleton />}>
        <SlowComponent />  {/* async: уйдёт в поток, когда будет готов */}
      </Suspense>

      <Suspense fallback={<Skeleton />}>
        <AnotherSlow />    {/* async: уйдёт в поток независимо */}
      </Suspense>
    </div>
  );
}

async function SlowComponent() {
  await db.slowQuery();    // занимает 800мс
  return <div>...</div>;
}
```

Браузер получает и рендерит `<Header />` и оба `<Skeleton />` немедленно, поэтому TTFB короткий. По мере того как каждый медленный компонент дорендеривается на сервере, его HTML уходит в поток и вставляется в страницу. Границы Suspense заменяются реальным содержимым.

### Избирательная гидратация (selective hydration)

Поток даёт ещё и избирательную гидратацию: клиент может гидратировать компоненты в порядке приоритета.

```txt
Пользователь кликнул по компоненту, который ещё не гидратирован

  React ставит этот компонент в начало очереди и гидратирует
  его раньше тех, что загрузились до него.
```

---

## Причины расхождений при гидратации

Гидратация — процесс, при котором React на клиенте привязывает обработчики событий и состояние к HTML, отрендеренному сервером. Чтобы гидратация прошла успешно, клиент должен получить ровно тот же HTML, что и сервер.

**Расхождение при гидратации** (hydration mismatch) возникает, когда клиент и сервер рендерят разный результат:

```tsx
// 1. Обращение к чисто браузерным API во время рендера:
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
  // Сервер рендерит "10:30:00", клиент — "10:30:01" → расхождение
}

// Исправление: взять стабильное значение или рендерить время
// только на клиенте:
function Timestamp() {
  const [time, setTime] = useState<string | null>(null);
  useEffect(() => {
    setTime(new Date().toLocaleTimeString());
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);
  }, []);
  return <span>{time}</span>; // на сервере null → расхождения нет
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
// 4. Условный рендер по данным, которые есть только в браузере:
function Component() {
  if (typeof window !== 'undefined') {
    return <ClientOnlyContent />;
  }
  return null; // → разный вывод на сервере и клиенте: null vs <ClientOnlyContent />
}

// Исправление: suppressHydrationWarning для намеренных расхождений
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

Это подавляет предупреждение, но само расхождение не убирает. Клиент всё равно обновит DOM — Document Object Model, дерево объектов, из которого браузер рисует страницу, — уже после гидратации. Пользуйтесь этим редко.

---

## RSC и размер бандла

Наиболее недооценённое преимущество Server Components: **нулевой вклад в клиентский бандл**.

```tsx
// Этот импорт остаётся на сервере — в браузер не попадает ничего:
import { marked } from 'marked';           // 45 килобайт
import { highlight } from 'highlight.js';  // 200 килобайт
import { prisma } from '@/lib/prisma';     // + Prisma клиент

async function BlogPost({ slug }: { slug: string }) {
  const post = await prisma.post.findUnique({ where: { slug } });
  const html = marked(highlight(post!.content, { language: 'ts' }).value);
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
```

В обычном клиентском React-приложении импорт `marked` и `highlight.js` добавил бы к JavaScript-бандлу около 245 килобайт. В серверном компоненте эти библиотеки выполняются на сервере, и клиенту уходит только отрендеренный HTML.

---

## Типичные ловушки на интервью

**«Может ли Server Component импортировать Client Component?»**
Да. Серверный компонент может импортировать и рендерить клиентский. Тот попадает в клиентский бандл и гидратируется в браузере.

```txt
серверный  ── импортирует ──▶  клиентский    ✓
клиентский ── импортирует ──▶  серверный     ✗
клиентский ◀─  children   ──   серверный     ✓
```

Обратное направление ограничено. Клиентский компонент не может импортировать серверный — импорт завершится ошибкой. Серверный код вроде `fs`, `db` или импорта `'server-only'` не может выполняться в браузере. Но клиентский компонент *может* получить серверный как `children`: тот приходит уже отрендеренным сериализованным элементом.

**«Может ли Server Component использовать useState?»**
Нет. У серверных компонентов нет ни жизненного цикла, ни состояния: они выполняются один раз на сервере и выдают статический результат. Если нужна интерактивность, этот кусок должен стать клиентским компонентом.

```txt
загрузка данных, статический рендер  →  серверный компонент
интерактивность, состояние, эффекты  →  клиентский компонент
```

**«Что такое RSC payload?»**
Это сериализованный результат рендера дерева серверных компонентов — тот самый JSON-подобный формат передачи, который React отправляет клиенту. В нём три вида строк:

```txt
RSC payload — упрощённая схема

  дерево   ["$","ul",null,{"children":[ ... ]}]
           виртуальное дерево DOM с серверного рендера

  клиент   ссылка на чанк с <AddToCartButton>
           говорит клиенту, какой JS-файл загрузить

  пропсы   {"productId":"42"}
           сериализованные пропсы этого клиентского компонента
```

Клиент получает payload, рендерит по нему дерево клиентских компонентов и гидратирует результат поверх HTML, сгенерированного сервером. Это не тот же самый HTML, который сервер отправил браузеру. Payload разбирает runtime React, а не HTML-парсер браузера.

**«'use client' означает что компонент выполняется только на клиенте?»**
Нет. Клиентские компоненты выполняются и на клиенте, **и** на сервере. На сервере они выполняются для SSR и для SSG — static site generation, когда страницы превращаются в HTML на этапе сборки.

`'use client'` означает более узкую вещь. Этот компонент и его поддерево используют клиентские возможности React: состояние, эффекты, браузерные API. Значит, их надо включить в клиентский бандл. Директива отмечает границу «сервер / клиент», а не границу «никогда не выполнять на сервере».

**«В чём разница между Server Actions и API routes?»**
API routes — явные HTTP-эндпоинты. Вы определяете маршрут, обрабатываете запрос, разбираете тело, возвращаете ответ. Server Actions — функции, помеченные `'use server'`, и фреймворк сам публикует их как POST-эндпоинты.

| | API route | Server Action |
|---|---|---|
| Как объявляется | файл маршрута с обработчиком запроса | функция с `'use server'` |
| Как вызывается | `fetch` по URL | как обычная функция |
| Сериализация и транспорт | пишете сами | делает фреймворк |
| Работа без JavaScript | нет | да, через `<form action={...}>` |
| Сброс кеша | ваш собственный код | `revalidatePath` / `revalidateTag` |
| Для чего лучше | публичные API для сторонних клиентов | внутренние формы и мутации |

Server Action умеет сам вызвать `revalidatePath` или `revalidateTag`, поэтому сбрасывает кеш без полной перезагрузки страницы.
