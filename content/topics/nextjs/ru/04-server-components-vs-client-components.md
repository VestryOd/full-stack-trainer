<!-- verified: 2026-06-05, corrections: 0 -->
# Server Components vs Client Components

## SSR ≠ Server Components — главное, что нужно развести в голове

Это, наверное, самая частая путаница на собеседованиях по Next.js. SSR — это *когда* (на каком этапе) генерируется HTML. Server Components — это *где исполняется код компонента и попадает ли он в клиентский бандл вообще*.

```txt
SSR (Pages Router / Client Component с SSR):
  компонент рендерится на сервере в HTML
  → HTML отправляется браузеру
  → JS-код компонента ТОЖЕ отправляется
  → React гидратирует — компонент "оживает" в браузере

Server Component (App Router):
  компонент рендерится на сервере в HTML / RSC Payload
  → HTML отправляется браузеру
  → JS-код этого компонента НЕ отправляется вообще
  → гидратации для этого компонента не происходит — ему нечего "оживлять"
```

Server Component — это не "SSR-версия компонента", это компонент, который **в принципе не существует на клиенте**. Если в нём нет ни одного интерактивного элемента, его код за пределами сервера просто не нужен — и Next его не отправляет.

## Server Component — что это и что в нём можно

По умолчанию **все** компоненты в `app/` — Server Components. Это асинхронные функции, которые могут напрямую обращаться к серверным ресурсам:

```tsx
// app/users/page.tsx — Server Component (без 'use client')
import { db } from '@/lib/db';

export default async function UsersPage() {
  // Прямой запрос к БД — без отдельного API-слоя
  const users = await db.user.findMany({ select: { id: true, name: true, email: true } });

  return (
    <ul>
      {users.map((u) => (
        <li key={u.id}>{u.name} — {u.email}</li>
      ))}
    </ul>
  );
}
```

Доступно:

```txt
fetch() с расширенным кешированием
прямые запросы к БД (Prisma, Drizzle, raw SQL)
доступ к файловой системе, env-переменным
читать cookies()/headers()
выполнять "тяжёлые" зависимости (markdown-парсеры, image processing),
  которые не должны попадать в клиентский бандл
```

Недоступно — потому что у Server Component **нет жизненного цикла в браузере**:

```tsx
// ❌ Ошибка компиляции/рантайма в Server Component
export default function Page() {
  const [count, setCount] = useState(0); // useState недоступен
  useEffect(() => {});                     // useEffect недоступен
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
  // event handler как проп нельзя передать функцией — см. ниже про serialization
}
```

## Client Component — explicit opt-in

`'use client'` — это не "сделай этот компонент клиентским", а маркер **границы модуля**: всё, что импортируется из файла с этой директивой (и всё, что импортирует *этот* модуль), попадает в клиентский граф зависимостей.

```tsx
// app/components/Counter.tsx
'use client';

import { useState } from 'react';

export function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount((c) => c + 1)}>{count}</button>;
}
```

Важный, часто упускаемый нюанс: **директива действует на весь модуль и на всё, что он импортирует**. Если `Counter.tsx` импортирует утилиту из `utils/date.ts`, эта утилита тоже попадёт в клиентский бандл, даже если сама по себе не содержит браузерных API — она находится "ниже по графу" от `'use client'`-границы.

## Композиция: Server и Client компоненты вместе

### Server → Client: можно, и это норма

```tsx
// app/products/page.tsx — Server Component
import { AddToCartButton } from './AddToCartButton'; // Client Component

export default async function ProductsPage() {
  const products = await getProducts();

  return (
    <ul>
      {products.map((p) => (
        <li key={p.id}>
          {p.name} — {p.price}₸
          <AddToCartButton productId={p.id} /> {/* данные передаются как props */}
        </li>
      ))}
    </ul>
  );
}
```

### Client → Server: напрямую нельзя, но есть паттерн "слотов" (children)

Импортировать Server Component внутрь Client Component **напрямую** нельзя — потому что в момент рендера Client Component на клиенте у него попросту нет доступа к серверным ресурсам, которые нужны импортированному компоненту. Но Server Component можно передать как `children`/`prop` *еще на сервере*, до пересечения границы:

```tsx
// app/components/ClientWrapper.tsx
'use client';

export function ClientWrapper({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setIsOpen((v) => !v)}>Toggle</button>
      {isOpen && children}
    </div>
  );
}

// app/page.tsx — Server Component
import { ClientWrapper } from './components/ClientWrapper';
import { ServerOnlyContent } from './ServerOnlyContent'; // Server Component

export default function Page() {
  return (
    <ClientWrapper>
      <ServerOnlyContent /> {/* рендерится на сервере ДО передачи в ClientWrapper */}
    </ClientWrapper>
  );
}
```

`ServerOnlyContent` рендерится на сервере как часть родительского Server Component **до** того, как его готовый результат (RSC payload, а не исходный код) передаётся в `ClientWrapper` как `children`. С точки зрения `ClientWrapper` это просто непрозрачный React-узел — он не "знает", что внутри был серверный код, и не может на него повлиять (например, обернуть в условие, зависящее от клиентского состояния, и заставить перерендериться на сервере).

## Что можно передавать через props на границе Server → Client

Граница `'use client'` — это **сериализационная граница**. Server Component сериализует props в специальный RSC-формат (похожий на JSON, но с поддержкой Promise/Date и некоторых других типов), который передаётся клиенту. Отсюда ограничения:

```tsx
// ❌ Нельзя передать функцию — функции не сериализуются
<ClientButton onSave={() => saveToDb(id)} />

// ✅ Можно: примитивы, объекты, массивы, Date, Promise (для streaming/Suspense)
<ClientButton productId={id} createdAt={product.createdAt} />

// ✅ Можно: Server Action — это специальный случай, Next превращает
// ссылку на серверную функцию в защищённый "action id"
<form action={createOrder}>
  <ClientSubmitButton />
</form>
```

Это частая причина runtime-ошибки `Functions cannot be passed directly to Client Components` — обычно она возникает, когда разработчик по привычке передаёт callback из Server Component, как делал бы это в обычном React.

## "use server-only" и защита от случайных импортов

Так как граница `'use client'` определяется по *графу импортов*, легко случайно "протащить" серверный код (с секретами, прямыми запросами к БД) в клиентский бандл — простой пример: утилитарный файл с функцией, обращающейся к `process.env.DB_PASSWORD`, импортируется и в Server, и в Client компонент.

Пакет `server-only` (и симметричный `client-only`) добавляет защиту на этапе сборки:

```ts
// lib/db.ts
import 'server-only';

export const db = new PrismaClient();
```

Если этот модуль случайно попадёт в граф зависимостей Client Component, билд завершится с явной ошибкой, а не с утечкой секретов в продакшен-бандл.

## Почему Server Components быстрее — конкретные механизмы

```txt
1. Меньше JS в бандле
   Client Component  → HTML + JS-код компонента + зависимости (попадают в бандл)
   Server Component  → только результат рендера (HTML/RSC payload), 0 байт JS

2. Меньше hydration-работы
   Каждый Client Component при гидратации требует, чтобы React сопоставил
   серверный HTML с виртуальным DOM и навесил обработчики событий.
   Server Component — нет hydration вообще, нет затрат CPU на клиенте.

3. Прямой доступ к данным
   Server Component может обратиться к БД напрямую — нет лишнего
   HTTP round-trip "браузер → API → БД", который был бы нужен Client Component.

4. Тяжёлые зависимости не попадают на клиент
   Например, markdown-парсер (remark/rehype) или библиотека форматирования
   используется только на сервере — клиент не платит за её вес.
```

## Композиционный паттерн: "максимум Server, минимум Client"

Рекомендуемая стратегия — спускать `'use client'` границу как можно ниже по дереву, оставляя интерактивным только то, что реально требует интерактивности:

```txt
ProductsPage (Server)
 └─ ProductList (Server)        — рендерит список, фетчит данные
     └─ ProductCard (Server)     — статическая карточка
         └─ AddToCartButton (Client) — нужен onClick → useState/useTransition
```

Антипаттерн — пометить `'use client'` на верхнем уровне "для удобства" (например, потому что где-то глубоко внутри нужен один интерактивный элемент). Это превращает в Client Component весь поддерево — со всем фетчем данных, который теперь придётся переписывать через `useEffect`/react-query, и со всем весом зависимостей.

## Контекст и провайдеры — неизбежно Client

React Context (через `useContext`/`createContext` с состоянием) работает только в браузере, поэтому провайдеры темы, React Query, состояния авторизации и т.п. обязаны быть Client Components — но их обычно выносят в отдельный "тонкий" слой в корне дерева:

```tsx
// app/providers.tsx
'use client';

import { ThemeProvider } from 'next-themes';

export function Providers({ children }: { children: React.ReactNode }) {
  return <ThemeProvider attribute="class">{children}</ThemeProvider>;
}

// app/layout.tsx — Server Component
import { Providers } from './providers';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <Providers>{children}</Providers> {/* children может быть Server Component */}
      </body>
    </html>
  );
}
```

Важно: сам `RootLayout` остаётся Server Component, граница `'use client'` локализована в `Providers`, а всё, что передаётся как `children`, может оставаться серверным благодаря паттерну "слотов", описанному выше.

## Типичные ошибки на интервью

- **"Server Components — это новое название для SSR"** — нет. SSR-компонент в Pages Router всё равно гидратируется и отправляет свой JS клиенту. Server Component не отправляет JS вообще — для него нет понятия "гидратация".

- **"`'use client'` делает только этот компонент клиентским"** — директива определяет границу *модуля*, и распространяется на весь импортируемый из этого файла граф. Часто забывают, что вспомогательные утилиты, импортированные Client Component, тоже окажутся в бандле.

- **"Можно просто передать функцию из Server Component в Client как callback"** — нет, props сериализуются через RSC-протокол, функции не сериализуются (кроме специального случая Server Actions). Это типичная runtime-ошибка у новичков в App Router.

- **"Если нужен один интерактивный элемент — помечаем `'use client'` всю страницу"** — антипаттерн, превращающий весь поддерево в клиентский код. Правильный подход — выносить интерактивность в маленький листовой компонент.

- **"Server Component нельзя использовать внутри Client Component вообще"** — можно, но только через паттерн `children`/слотов: Server Component рендерится на сервере *до* пересечения границы и передаётся как уже отрисованный React-узел, а не как импортируемый компонент.

- **Не знают про `server-only`/`client-only` пакеты** — это стандартный способ зафиксировать на этапе сборки, что модуль с секретами или браузерным API не пересечёт границу случайно через цепочку импортов.
