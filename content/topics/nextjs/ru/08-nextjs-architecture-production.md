<!-- verified: 2026-06-05, corrections: 0 -->
# Production Architecture и Best Practices

## Самый Senior блок

Здесь уже спрашивают:

```txt
Как бы вы построили проект?
Как масштабировать Next?
Как организовать архитектуру?
```

---

# Типичная архитектура

```txt
Browser
 ↓
CDN
 ↓
Next.js
 ↓
Backend APIs
 ↓
Database
```

---

# Вариант 1

Next как Frontend.

---

```txt
Next
 ↓
NestJS
 ↓
PostgreSQL
```

---

Очень распространенная схема.

---

# Вариант 2

BFF Architecture

---

Backend For Frontend.

---

```txt
Browser
 ↓
Next
 ↓
Microservices
```

---

Next агрегирует данные.

---

Frontend получает:

```txt
один API
```

---

# Почему BFF удобен

Frontend не знает про:

```txt
User Service
Product Service
Order Service
```

---

Всё скрыто внутри BFF.

---

# Server Actions

Очень популярная тема.

---

Позволяют выполнять серверный код
без API Routes.

---

Пример:

```tsx
'use server';

export async function
createUser() {

}
```

---

Форма:

```tsx
<form action={createUser}>
```

---

Без:

```txt
REST
GraphQL
API Route
```

---

# Когда использовать Server Actions

Хорошо:

```txt
формы
CRUD
мутации
```

---

Плохо:

```txt
публичный API
интеграции
```

---

# API Routes

Старый подход.

---

```txt
app/api/users/route.ts
```

---

Создаем endpoint.

---

```ts
export async function GET() {}
```

---

# Когда API Routes лучше

Когда нужен:

```txt
REST API
Webhook
External Integration
```

---

# Edge Runtime

Очень популярный вопрос.

---

Код выполняется:

```txt
ближе к пользователю
```

---

На Edge Nodes.

---

Не на основном сервере.

---

# Ограничения Edge

Нет:

```txt
fs
net
child_process
```

---

Не все npm пакеты работают.

---

# Caching Strategy

Очень любят спрашивать.

---

Главное правило:

```txt
не всё SSR
не всё SSG
```

---

Обычно:

```txt
Homepage → SSG

Product List → ISR

Product Page → ISR

Cart → CSR

Profile → SSR

Admin → CSR
```

---

# Environment Variables

Server:

```txt
process.env.SECRET
```

---

Client:

```txt
NEXT_PUBLIC_API_URL
```

---

Очень популярный вопрос.

---

# Почему NEXT_PUBLIC

Без него переменная:

```txt
не попадет в клиентский bundle
```

---

# Security

Нельзя:

```txt
JWT Secret
DB Password
API Keys
```

---

Передавать в Client Components.

---

# Monitoring

Production проект обычно использует:

```txt
Sentry
Datadog
Application Insights
New Relic
```

---

# Deployment

Самый частый вариант:

```txt
Vercel
```

---

Также:

```txt
AWS
Docker
Kubernetes
Azure
GCP
```

---

# Очень популярный вопрос

Как бы вы построили e-commerce?

Ответ:

```txt
Homepage → SSG

Categories → ISR

Products → ISR

Cart → Client State

Checkout → Server Actions/API

Admin Panel → CSR
```

---

# Очень популярный вопрос

Как бы вы построили CMS сайт?

Ответ:

```txt
Next.js
 ↓
Strapi
 ↓
PostgreSQL
```

---

Страницы:

```txt
ISR
```

---

После публикации статьи:

```txt
revalidateTag
```

---

# Самый сильный Senior ответ

Что самое важное в production Next.js приложении?

Ответ:

Не существует одной универсальной модели рендеринга. Production приложение обычно сочетает SSG, ISR, SSR, Client Components, Server Components, кеширование и revalidation в зависимости от требований конкретного экрана. Основная задача архитектора — выбрать правильный компромисс между SEO, производительностью, стоимостью рендера и свежестью данных.