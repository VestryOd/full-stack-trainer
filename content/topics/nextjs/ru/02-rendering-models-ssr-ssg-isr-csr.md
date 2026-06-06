<!-- verified: 2026-06-05, corrections: 0 -->
# Rendering Models: CSR, SSR, SSG, ISR

## Самая популярная тема Next.js

Если по Next задают один вопрос,
то обычно это:

```txt
SSR
SSG
ISR
CSR
```

---

# Что такое Rendering

Rendering — процесс получения HTML страницы.

---

Вопрос:

```txt
Где создается HTML?
Когда создается HTML?
```

---

От ответа зависит модель рендера.

---

# CSR

Client Side Rendering.

---

Классический React SPA.

---

Процесс:

```txt
Browser
 ↓
Download JS
 ↓
Execute React
 ↓
Fetch Data
 ↓
Render HTML
```

---

# Пример

```tsx
useEffect(() => {
  fetch(...)
}, []);
```

---

HTML появляется только после выполнения JS.

---

# Плюсы CSR

- меньше нагрузки на сервер
- хороший UX после загрузки
- интерактивность

---

# Минусы CSR

- плохой SEO
- медленный First Paint
- пустой HTML

---

# SSR

Server Side Rendering.

---

HTML создается на сервере
при каждом запросе.

---

Схема:

```txt
Request
 ↓
Server Render
 ↓
HTML
 ↓
Browser
```

---

Пример (Page Router):

```ts
getServerSideProps()
```

---

Каждый запрос:

```txt
новый рендер
```

---

# Плюсы SSR

- отличный SEO
- актуальные данные
- быстрый First Paint

---

# Минусы SSR

- нагрузка на сервер
- выше TTFB
- меньше кеширования

---

# SSG

Static Site Generation.

---

HTML генерируется:

```txt
во время build
```

---

До появления пользователей.

---

Схема:

```txt
Build
 ↓
HTML
 ↓
CDN
 ↓
Users
```

---

Пример:

```ts
getStaticProps()
```

---

# Плюсы SSG

- очень быстрый
- отлично кешируется
- идеален для CDN

---

# Минусы SSG

Данные могут устаревать.

---

# Когда использовать SSG

```txt
Blog
Marketing Pages
Docs
Landing Pages
```

---

# ISR

Incremental Static Regeneration.

---

Комбинация:

```txt
SSG
+
SSR
```

---

Очень любят спрашивать.

---

# Как работает ISR

Во время build:

```txt
создается HTML
```

---

Через:

```ts
revalidate: 60
```

---

Next может пересоздать страницу.

---

# Схема

```txt
Request
 ↓
Old Cached Page
 ↓
Background Regeneration
 ↓
New Page
```

---

Пользователь не ждет рендер.

---

# Пример

```ts
export async function
getStaticProps() {

  return {
    props: {...},

    revalidate: 60,
  };
}
```

---

# Когда использовать ISR

```txt
E-commerce
Catalogs
News
CMS Content
```

---

Данные обновляются,
но не каждую секунду.

---

# Hydration

Очень популярный вопрос.

---

После SSR:

```txt
HTML уже есть
```

---

Но интерактивности нет.

---

React должен:

```txt
подключить события
```

---

Этот процесс называется:

```txt
Hydration
```

---

# Hydration Flow

```txt
Server Render HTML
 ↓
Browser receives HTML
 ↓
JS bundle downloads
 ↓
Hydration
 ↓
Interactive UI
```

---

# Hydration Mismatch

Очень популярный Senior вопрос.

---

Сервер сгенерировал:

```txt
Hello
```

---

Клиент:

```txt
Hello World
```

---

React видит различия.

---

Получаем:

```txt
Hydration Mismatch
```

---

# Типичный пример

```tsx
<Date.now()>
```

---

На сервере:

```txt
10:00
```

---

На клиенте:

```txt
10:01
```

---

Результат отличается.

---

# Сравнение моделей

| Model | HTML генерируется |
|---------|---------|
| CSR | Browser |
| SSR | Request Time |
| SSG | Build Time |
| ISR | Build + Revalidation |

---

# Что любят спрашивать

Какую модель выбрать?

---

Blog:

```txt
SSG
```

---

Product Catalog:

```txt
ISR
```

---

Dashboard:

```txt
CSR
```

---

Personalized Page:

```txt
SSR
```

---

# Interview Answer

CSR рендерит HTML на клиенте после загрузки JavaScript. SSR создает HTML на сервере при каждом запросе. SSG генерирует HTML во время сборки проекта. ISR позволяет периодически пересоздавать статические страницы без полного билда приложения. Выбор модели зависит от требований к SEO, свежести данных и производительности.