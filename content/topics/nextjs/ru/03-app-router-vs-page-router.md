<!-- verified: 2026-06-05, corrections: 0 -->
# App Router vs Page Router

## История

До Next.js 13 существовал только:

```txt
Pages Router
```

---

Структура:

```txt
pages/
```

---

Например:

```txt
pages/
 ├─ index.tsx
 ├─ about.tsx
 └─ blog/[id].tsx
```

---

После Next.js 13 появился:

```txt
App Router
```

---

Структура:

```txt
app/
```

---

Сегодня это рекомендуемый способ разработки.

---

# Почему появился App Router

Очень популярный вопрос.

---

Pages Router был хорош для:

```txt
SSR
SSG
ISR
```

---

Но плохо поддерживал:

```txt
Streaming
Nested Layouts
Server Components
```

---

Для этого создали App Router.

---

# Pages Router

Пример.

---

```txt
pages/
 ├─ users/
 │   └─ index.tsx
```

---

Маршрут:

```txt
/users
```

---

# Data Fetching

Использовались:

```ts
getServerSideProps()
getStaticProps()
getStaticPaths()
```

---

# Пример

```ts
export async function
getServerSideProps() {

  const users =
    await getUsers();

  return {
    props: {
      users
    }
  };
}
```

---

# App Router

Структура:

```txt
app/
 ├─ users/
 │   └─ page.tsx
```

---

Маршрут:

```txt
/users
```

---

# Data Fetching

Теперь:

```ts
await fetch()
```

прямо внутри компонента.

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

# Самое важное отличие

Pages Router:

```txt
Страница
=
Client Component
```

---

App Router:

```txt
Страница
=
Server Component
по умолчанию
```

---

Это критически важно.

---

# Layouts

Одно из главных преимуществ.

---

Pages Router:

обычно:

```txt
_app.tsx
```

---

Или:

```txt
ручное оборачивание
```

---

# App Router

Встроенные Layouts.

---

```txt
app/
 ├─ layout.tsx
 ├─ dashboard/
 │   ├─ layout.tsx
 │   └─ page.tsx
```

---

Каждый сегмент маршрута
может иметь собственный Layout.

---

# Nested Layouts

Очень любят спрашивать.

---

Схема:

```txt
Root Layout
 ↓
Dashboard Layout
 ↓
Page
```

---

Не происходит полного размонтирования.

---

Это улучшает UX.

---

# Loading UI

Pages Router:

обычно вручную.

---

App Router:

встроено.

---

```txt
loading.tsx
```

---

Пример:

```txt
app/users/loading.tsx
```

---

Пока данные загружаются:

```txt
показывается Loading UI
```

---

# Error Handling

Встроено.

---

```txt
error.tsx
```

---

Для сегмента маршрута.

---

# Streaming

Очень важная тема.

---

Pages Router:

```txt
рендерим всё
потом отправляем
```

---

App Router:

```txt
отправляем частями
```

---

Пользователь видит контент раньше.

---

# Server Components

Главная причина появления App Router.

---

App Router построен вокруг:

```txt
React Server Components
```

---

# Что осталось от Pages Router

Он по-прежнему поддерживается.

---

Очень много legacy проектов:

```txt
Next 12
Next 13
Next 14
```

всё ещё используют:

```txt
pages/
```

---

# Когда встретишь Pages Router

Практически на любом существующем проекте.

---

# Interview Question

Какое главное отличие App Router?

Ответ:

App Router строится вокруг React Server Components, встроенных Layouts, Streaming и новой модели Data Fetching. В отличие от Pages Router он позволяет выполнять большинство логики на сервере по умолчанию.