<!-- verified: 2026-06-05, corrections: 0 -->
# Next.js Fundamentals

## Что такое Next.js

Next.js — это Full-Stack React Framework.

---

Очень важно понимать:

```txt
React
≠
Next.js
```

---

React предоставляет:

```txt
Components
Hooks
State
Virtual DOM
```

---

Next.js строится поверх React и добавляет:

```txt
Routing
SSR
SSG
ISR
Middleware
API Routes
Image Optimization
SEO
Caching
```

---

# Почему появился Next.js

Чтобы решить проблемы SPA.

---

# Проблема №1

SEO.

---

Обычный React SPA:

```html
<body>
  <div id="root"></div>
</body>
```

---

Поисковый робот видит почти пустую страницу.

---

Особенно раньше это было проблемой.

---

# Проблема №2

Большой First Load.

---

В SPA происходит:

```txt
HTML
↓
JS Bundle Download
↓
React Mount
↓
API Requests
↓
Render
```

---

Пользователь долго ждет.

---

# Проблема №3

Data Fetching.

---

React долгое время вообще не отвечал на вопрос:

```txt
Когда получать данные?
Где получать данные?
```

---

Каждая команда решала по-своему.

---

# Что дает Next.js

Next позволяет рендерить страницу:

```txt
на сервере
во время билда
частично
динамически
```

---

# Next.js = Opinionated Framework

Очень популярный вопрос.

---

Что означает:

```txt
Opinionated
```

---

Фреймворк предлагает:

```txt
структуру проекта
routing
rendering model
data fetching
```

---

Вместо полной свободы.

---

# Fullstack Framework

Следующий популярный вопрос.

---

Почему Fullstack?

---

Потому что внутри Next есть:

```txt
Frontend
Backend
```

---

Например:

```txt
React Components
```

---

И одновременно:

```txt
API Routes
Server Actions
Middleware
```

---

# Основные части Next.js

Упрощенно:

```txt
Routing
Rendering
Data Fetching
Caching
Optimization
```

---

# Routing

Next автоматически строит роуты.

---

Например:

```txt
pages/about.tsx
```

---

Становится:

```txt
/about
```

---

# Code Splitting

Очень важная тема.

---

В React SPA:

```txt
1 большой bundle
```

---

В Next:

```txt
bundle per route
```

---

Пользователь скачивает только нужный код.

---

# Built-In Optimizations

Next содержит:

```txt
Image Optimization
Font Optimization
Code Splitting
Tree Shaking
Minification
Streaming
```

---

# API Routes

Можно писать backend прямо внутри Next.

---

Например:

```ts
/api/users
```

---

Получаем:

```txt
Backend Endpoint
```

---

# Middleware

Позволяет выполнить код до рендера страницы.

---

Примеры:

```txt
Authentication
Geo Routing
A/B Testing
Redirects
```

---

# Почему компании любят Next.js

Один проект:

```txt
Frontend
+
Backend
+
SSR
+
SEO
```

---

Вместо нескольких сервисов.

---

# React vs Next

React:

```txt
UI Library
```

---

Next:

```txt
Application Framework
```

---

# Самая важная мысль

Next.js не заменяет React.

---

Next использует React как rendering engine.

---

# Interview Answer

Next.js — это full-stack framework поверх React, который решает проблемы SEO, производительности первой загрузки, маршрутизации, data fetching и server-side rendering. Он предоставляет встроенные механизмы SSR, SSG, ISR, routing, caching и backend-функциональность через API Routes и Server Actions.