<!-- verified: 2026-06-05, corrections: 1 -->
# Data Fetching, Caching и Revalidation

## Самое большое изменение App Router

В Pages Router были:

```ts
getServerSideProps()
getStaticProps()
getStaticPaths()
```

---

В App Router основной API:

```ts
fetch()
```

---

# Data Fetching в App Router

Пример:

```tsx
export default async function Page() {

  const res =
    await fetch(
      'https://api.com/users'
    );

  const users =
    await res.json();

  return (...);
}
```

---

Очень важно понимать:

```txt
fetch выполняется на сервере
```

---

Не в браузере.

---

# Почему это важно

Можно использовать:

```txt
Database
Private APIs
Environment Variables
```

---

Без утечки данных клиенту.

---

# Автоматическое кеширование

Очень популярный вопрос.

---

В обычном React:

```txt
fetch
=
каждый раз новый запрос
```

---

В App Router (Next.js 13/14):

```txt
fetch кешировался
по умолчанию
```

---

В Next.js 15 поведение изменилось.

---

# Default Behavior

```ts
await fetch(...)
```

---

Next.js 13/14 по умолчанию:

```txt
force-cache
```

Next.js 15 по умолчанию:

```txt
no-store
```

---

То есть в Next.js 15 кеширование нужно указывать явно.

---

# force-cache

Явно указываем:

```ts
fetch(url, {
  cache: 'force-cache'
});
```

---

Поведение:

```txt
статический результат
```

---

Похоже на:

```txt
SSG
```

---

# no-store

Очень популярный вопрос.

---

```ts
fetch(url, {
  cache: 'no-store'
});
```

---

Каждый запрос:

```txt
новый fetch
```

---

Похоже на:

```txt
SSR
```

---

# Сравнение

force-cache:

```txt
кешировать
```

---

no-store:

```txt
никогда не кешировать
```

---

# Revalidation

Самая важная тема.

---

Представим:

```txt
Product Catalog
```

---

Обновляется:

```txt
раз в 5 минут
```

---

SSR слишком дорого.

---

SSG слишком устаревает.

---

Используем:

```txt
ISR
```

---

Через:

```ts
next: {
  revalidate: 300
}
```

---

# Пример

```ts
fetch(url, {
  next: {
    revalidate: 60
  }
});
```

---

Что означает:

```txt
кешировать 60 секунд
```

---

После этого:

```txt
перегенерировать
```

---

# Revalidate Path

Очень любят спрашивать.

---

Когда контент изменился.

---

Например:

```txt
новая статья
```

---

Можно вручную инвалидировать кеш.

---

```ts
revalidatePath('/blog');
```

---

Следующий запрос:

```txt
создаст новую страницу
```

---

# Revalidate Tag

Еще мощнее.

---

Назначаем тег.

---

```ts
fetch(url, {
  next: {
    tags: ['products']
  }
});
```

---

После обновления:

```ts
revalidateTag('products');
```

---

Инвалидируются все связанные данные.

---

Очень удобно для CMS.

---

# generateStaticParams

Аналог:

```txt
getStaticPaths
```

из Pages Router.

---

Пример:

```tsx
export async function
generateStaticParams() {

  return [
    { id: '1' },
    { id: '2' }
  ];
}
```

---

Во время build:

```txt
создаются страницы
```

---

# Dynamic Rendering

Очень популярный вопрос.

---

Что делает страницу динамической?

---

Например:

```ts
cookies()
headers()
```

---

или:

```ts
cache: 'no-store'
```

---

Next понимает:

```txt
эту страницу нельзя статически кешировать
```

---

# Request Memoization

Очень интересная тема.

---

Если в рамках одного рендера:

```ts
fetch('/users')
```

вызвали 5 раз

---

Next выполнит:

```txt
один запрос
```

---

Остальное из памяти.

---

# Что любят спрашивать

Чем App Router fetch отличается от browser fetch?

---

Ответ:

В App Router fetch интегрирован с системой кеширования и revalidation Next.js и по умолчанию поддерживает серверный рендеринг и автоматическое кеширование.

---

# Interview Answer

В App Router данные обычно загружаются через встроенный fetch API. В отличие от браузерного fetch он интегрирован с системой кеширования Next.js. Для управления кешем используются cache: 'force-cache', cache: 'no-store', revalidate, revalidatePath и revalidateTag. Это позволяет гибко комбинировать статический и динамический рендеринг.