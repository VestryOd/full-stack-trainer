<!-- verified: 2026-06-05, corrections: 1 -->
# Routing, Layouts и Middleware

## Routing в Next.js

Одна из сильнейших сторон Next.

---

Маршруты строятся автоматически.

---

По структуре папок.

---

# App Router

Пример:

```txt
app/
 ├─ page.tsx
 ├─ about/
 │   └─ page.tsx
```

---

Маршруты:

```txt
/
/about
```

---

# Dynamic Routes

Очень популярный вопрос.

---

Структура:

```txt
app/blog/[id]/page.tsx
```

---

Маршрут:

```txt
/blog/123
```

---

Получаем:

```ts
params.id
```

---

# Nested Routes

```txt
app
 └─ dashboard
     └─ settings
         └─ page.tsx
```

---

Маршрут:

```txt
/dashboard/settings
```

---

# Catch-All Routes

Пример:

```txt
[...slug]
```

---

Подходит для:

```txt
CMS
Docs
Knowledge Base
```

---

Пример URL:

```txt
/docs/react/hooks/useEffect
```

---

Получим:

```ts
[
 'react',
 'hooks',
 'useEffect'
]
```

---

# Layout

Самая важная фича App Router.

---

Файл:

```txt
layout.tsx
```

---

Оборачивает дочерние страницы.

---

Пример:

```tsx
export default function Layout({
  children
}) {

  return (
    <>
      <Navbar />
      {children}
    </>
  );
}
```

---

# Root Layout

Обязательный.

---

```txt
app/layout.tsx
```

---

Аналог:

```html
<html>
<body>
```

---

уровня приложения.

---

# Nested Layouts

Очень любят спрашивать.

---

```txt
Root Layout
 ↓
Dashboard Layout
 ↓
Page
```

---

При переходе:

```txt
Dashboard → Settings
```

---

Dashboard Layout не размонтируется.

---

# Почему это важно

Меньше:

```txt
rerender
network requests
UI flickering
```

---

# Template

Редко спрашивают.

---

Но полезно знать.

---

```txt
template.tsx
```

---

Похож на layout.

---

Но:

```txt
перемонтируется
каждый переход
```

---

# Loading UI

Очень крутая фича.

---

```txt
loading.tsx
```

---

Показывается автоматически.

---

Пока загружается страница.

---

# Error Boundary

Встроено.

---

```txt
error.tsx
```

---

Ловит ошибки
для конкретного сегмента маршрута.

---

# Not Found

```txt
not-found.tsx
```

---

Автоматический 404.

---

# Middleware

Очень популярный Senior вопрос.

---

Middleware выполняется:

```txt
до маршрутизации
до рендера
```

---

# Где находится

```txt
middleware.ts
```

---

В корне проекта.

---

# Пример

```ts
export function middleware(req) {

  return NextResponse.next();
}
```

---

# Что может Middleware

```txt
redirect
rewrite
auth
geo routing
ab testing
cookies
headers
```

---

# Authentication

Самый частый кейс.

---

```ts
if (!token) {

  return NextResponse.redirect(
    '/login'
  );
}
```

---

# Rewrite

Очень любят спрашивать.

---

Redirect:

```txt
URL меняется
```

---

Rewrite:

```txt
URL остается прежним
```

---

Пример:

```txt
/blog
```

---

Фактически отдаём:

```txt
/news
```

---

Пользователь не замечает.

---

# Geo Routing

Пример.

---

Пользователь из:

```txt
Germany
```

---

Получает:

```txt
/de
```

---

Пользователь из:

```txt
France
```

---

Получает:

```txt
/fr
```

---

# A/B Testing

Middleware может распределять:

```txt
Variant A
Variant B
```

---

До рендера страницы.

---

# Ограничения Middleware

Очень популярный вопрос.

---

Middleware работает:

```txt
Edge Runtime
```

---

Поэтому:

```txt
нет доступа к Node API
```

---

Например:

```txt
fs
net
child_process
```

---

недоступны.

---

# Когда использовать Middleware

Хорошо:

```txt
Auth
Redirects
Headers
Localization
A/B Tests
```

---

Плохо:

```txt
тяжелая бизнес логика
работа с БД
```

---

# Interview Answer

Routing в App Router основан на файловой структуре и поддерживает динамические, вложенные и catch-all маршруты. Layouts позволяют сохранять общие части интерфейса между переходами и уменьшают количество перерисовок. Middleware выполняется до рендера страницы и используется для авторизации, редиректов, локализации и A/B тестирования.