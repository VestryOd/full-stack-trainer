<!-- verified: 2026-06-05, corrections: 0 -->
# Server Components vs Client Components

## Самая популярная тема современного Next.js

Очень многие разработчики путают:

```txt
SSR
```

и

```txt
Server Components
```

---

Это НЕ одно и то же.

---

# Что такое Server Component

Компонент,
который выполняется только на сервере.

---

Никогда не попадает в браузер.

---

Пример:

```tsx
export default async function Page() {

  const users =
    await getUsers();

  return (...);
}
```

---

Это Server Component.

---

# Что означает

```txt
код выполняется на сервере
```

---

После рендера:

```txt
HTML отправляется клиенту
```

---

Но сам компонент:

```txt
в браузер не попадает
```

---

# Что такое Client Component

Компонент,
который выполняется в браузере.

---

Нужно явно указать:

```tsx
'use client';
```

---

Пример:

```tsx
'use client';

export default function Counter() {

  const [count, setCount] =
    useState(0);

  ...
}
```

---

# Почему нужен 'use client'

Потому что App Router считает:

```txt
все компоненты серверными
```

по умолчанию.

---

# Что нельзя в Server Component

Очень популярный вопрос.

---

Нельзя:

```txt
useState
useEffect
useRef
window
document
event handlers
```

---

Например:

```tsx
<button onClick={...}>
```

---

Ошибка.

---

# Почему нельзя

Потому что компонент
не существует в браузере.

---

# Что можно в Server Component

Можно:

```txt
fetch()
database queries
server logic
filesystem
env variables
```

---

Очень мощная возможность.

---

# Пример

```tsx
const users =
  await prisma.user.findMany();
```

---

Без API.

Без fetch.

Без дополнительного backend.

---

# Большой плюс

Меньше JavaScript.

---

Client Component:

```txt
HTML
+
JS
```

---

Server Component:

```txt
только HTML
```

---

Меньше bundle.

---

Быстрее загрузка.

---

# Composition Pattern

Очень популярный вопрос.

---

Рекомендуемый подход:

```txt
максимум Server Components
минимум Client Components
```

---

Пример:

```txt
Page
 ↓
ProductList
 ↓
ProductCard
 ↓
AddToCartButton
```

---

Первые три:

```txt
Server Components
```

---

Последний:

```txt
Client Component
```

---

Потому что нужен:

```txt
onClick
```

---

# SSR vs Server Components

Самый популярный вопрос.

---

SSR:

```txt
рендер на сервере
НО
компонент потом гидратируется
в браузере
```

---

Server Component:

```txt
никогда
не выполняется
в браузере
```

---

Очень большая разница.

---

# Передача данных

Server Component:

```tsx
<UserList users={users} />
```

---

Передает данные вниз.

---

Client Component получает:

```txt
обычные props
```

---

# Можно ли импортировать Client в Server?

Да.

---

Очень часто так делают.

---

```txt
Server
 ↓
Client
```

---

# Можно ли импортировать Server в Client?

Нет.

---

Потому что браузер не может выполнить серверный код.

---

# Частый вопрос

Почему Server Components быстрее?

---

Причины:

```txt
меньше JS
меньше hydration
меньше bundle
данные ближе к серверу
```

---

# Частый вопрос

Когда использовать Client Component?

---

Когда нужны:

```txt
useState
useEffect
browser APIs
event handlers
```

---

# Частый вопрос

Когда использовать Server Component?

---

Почти всегда.

---

Особенно:

```txt
Data Fetching
SEO Pages
Static Content
Lists
Tables
```

---

# Interview Answer

Server Components выполняются только на сервере и не попадают в клиентский JavaScript bundle. Они идеально подходят для data fetching и отображения контента. Client Components выполняются в браузере и используются для интерактивности, состояния и работы с browser APIs. В App Router все компоненты являются Server Components по умолчанию, а Client Components помечаются директивой `'use client'`.