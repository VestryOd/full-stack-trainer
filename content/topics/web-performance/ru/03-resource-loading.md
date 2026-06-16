<!-- verified: 2026-06-16, corrections: 0 -->
# Resource Loading

## Критический путь рендера — точка отсчёта

Прежде чем говорить о resource hints, нужно понять, что браузер делает с ресурсами по умолчанию — и почему это не оптимально.

```txt
Браузер получает HTML и строит Critical Rendering Path:

  HTML → DOM
  CSS  → CSSOM     } объединяются в Render Tree → Layout → Paint
  JS   → блокирует парсинг HTML, пока не выполнится

Проблема "водопада":
  1. Браузер начинает парсить HTML
  2. Встречает <link rel="stylesheet" href="style.css">
     → СТОП, скачиваем CSS
  3. В CSS: url('/fonts/inter.woff2')
     → браузер ЕЩЁНЕ знает об этом шрифте (только парсит CSS)
  4. Скачали CSS → парсим → видим шрифт → начинаем скачивать шрифт
     → ЗАДЕРЖКА = время парсинга CSS + RTT на запрос шрифта

Resource hints решают эту проблему: сообщают браузеру
о ресурсах ЗАРАНЕЕ, ещё в <head>, до того как он встретит
их в CSS/JS или вовсе — в другом документе.
```

## preload — "этот ресурс нужен прямо сейчас"

`<link rel="preload">` говорит браузеру: скачай этот ресурс **немедленно**, с высоким приоритетом, независимо от того, когда он встретится в HTML/CSS/JS.

```html
<!-- Базовый синтаксис — as="" обязателен -->
<link rel="preload" href="/fonts/inter.woff2" as="font" crossorigin />
<link rel="preload" href="/hero.jpg" as="image" />
<link rel="preload" href="/critical.css" as="style" />
<link rel="preload" href="/app.js" as="script" />
```

```html
<!-- as="" влияет на приоритет и Content-Security-Policy.
     Без него браузер скачает ресурс с низким приоритетом
     и проигнорирует CORS — шрифт не загрузится -->

<!-- ❌ Неправильно — нет as="" и crossorigin для шрифта -->
<link rel="preload" href="/fonts/inter.woff2" />

<!-- ✅ Правильно — с as="font" и crossorigin
     (шрифты всегда требуют CORS, даже с того же домена) -->
<link rel="preload" href="/fonts/inter.woff2" as="font" type="font/woff2" crossorigin />
```

### preload для адаптивных изображений

```html
<!-- ✅ imagesrcset + imagesizes — браузер выберет
     правильный файл ещё до парсинга <img> -->
<link
  rel="preload"
  as="image"
  href="/hero-800.webp"
  imagesrcset="/hero-400.webp 400w, /hero-800.webp 800w, /hero-1600.webp 1600w"
  imagesizes="(max-width: 600px) 100vw, 800px"
/>

<!-- Затем в HTML — браузер уже знает какой файл нужен -->
<img
  src="/hero-800.webp"
  srcset="/hero-400.webp 400w, /hero-800.webp 800w, /hero-1600.webp 1600w"
  sizes="(max-width: 600px) 100vw, 800px"
  fetchpriority="high"
  alt="Hero"
/>
```

### modulepreload — preload для ES-модулей

```html
<!-- Обычный preload для модуля не обрабатывает
     его зависимости. modulepreload скачивает модуль
     И его транзитивные зависимости, и парсит их -->
<link rel="modulepreload" href="/app.js" />
<link rel="modulepreload" href="/vendor.js" />

<!-- В отличие от <script type="module">, который ждёт
     очереди выполнения модулей, modulepreload
     позволяет начать скачивание немедленно -->
```

### Когда preload вредит

```html
<!-- ❌ Лишние preload — браузер скачивает ресурс с высоким
     приоритетом, но страница не использует его сразу.
     Это вытесняет другие важные ресурсы из очереди -->
<link rel="preload" href="/sidebar-widget.js" as="script" />
<link rel="preload" href="/footer-image.jpg" as="image" />
<link rel="preload" href="/admin-panel.js" as="script" />
```

```txt
Правило: preload — только для ресурсов, которые:
  1. Нужны на ТЕКУЩЕЙ странице
  2. Обнаруживаются ПОЗДНО (не в первом экране HTML)
  3. Критичны для LCP или первого рендера

  Хорошие кандидаты: LCP-изображение, кастомный шрифт,
  критический CSS-файл, главный JS-бандл
  Плохие кандидаты: всё что ниже fold, виджеты, аналитика
```

## prefetch — "этот ресурс понадобится потом"

`<link rel="prefetch">` просит браузер скачать ресурс **в фоне, с низким приоритетом**, для использования при следующей навигации.

```html
<!-- Когда пользователь на странице /products —
     высокая вероятность перейти на /checkout -->
<link rel="prefetch" href="/checkout.js" as="script" />
<link rel="prefetch" href="/payment-icons.webp" as="image" />
```

```ts
// ✅ Умный prefetch: начинаем при наведении/фокусе
// на ссылку — у пользователя ~100-200ms до клика
const handleLinkHover = (href: string) => {
  const link = document.createElement('link');
  link.rel = 'prefetch';
  link.href = href;
  document.head.appendChild(link);
};

document.querySelectorAll('a[data-prefetch]').forEach(a => {
  a.addEventListener('mouseenter', () => handleLinkHover(a.href));
  a.addEventListener('focus', () => handleLinkHover(a.href));
});
```

```ts
// Next.js делает это автоматически:
// <Link> prefetch'ит страницу при появлении в вьюпорте
import Link from 'next/link';

// prefetch по умолчанию включён для всех <Link>
// (отключить: prefetch={false})
<Link href="/checkout">Перейти к оплате</Link>
```

```txt
preload vs prefetch — принципиальная разница:

  preload:  ТЕКУЩАЯ навигация, высокий приоритет,
            использование ОЖИДАЕТСЯ немедленно.
            Браузер будет ругаться в консоли, если
            ресурс не используется в течение ~3 сек.

  prefetch: БУДУЩАЯ навигация, низкий приоритет,
            браузер может отложить или отменить
            (например, на медленном соединении).
            Хранится в HTTP-кэше для следующих запросов.
```

## preconnect и dns-prefetch

### preconnect — прогрев соединения

Установка TCP + TLS соединения занимает 1-3 RTT (round-trip). `preconnect` делает это заранее:

```html
<!-- ✅ preconnect для критичных внешних доменов —
     шрифты, CDN, API -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="preconnect" href="https://api.example.com" />

<!-- crossorigin нужен, если ресурс запрашивается
     с CORS (шрифты, fetch API) -->
```

```txt
Что даёт preconnect:

  Без preconnect (запрос шрифта из CSS):
  HTML → CSS discovered → DNS → TCP → TLS → Request → Response
          ↑ это всё происходит ПОСЛЕ парсинга CSS

  С preconnect (в <head>):
  DNS → TCP → TLS (начинается немедленно при загрузке HTML)
  Когда CSS дойдёт до запроса шрифта — соединение уже готово.

  Экономия: 100–500ms при медленном DNS/соединении
```

### dns-prefetch — лёгкая альтернатива

`dns-prefetch` делает только DNS-резолвинг (без TCP/TLS), потребляет меньше ресурсов:

```html
<!-- Для доменов, к которым подключение происходит
     не при загрузке страницы, а позже (аналитика,
     виджеты чата, lazy-loaded виджеты) -->
<link rel="dns-prefetch" href="https://analytics.google.com" />
<link rel="dns-prefetch" href="https://cdn.intercom.io" />
```

```html
<!-- Правило выбора:
     Критичный домен (нужен при загрузке) → preconnect
     Некритичный домен (нужен позже)      → dns-prefetch
     Слишком много доменов для preconnect  → оставить
       только 2-3 самых важных, остальные → dns-prefetch

     preconnect держит соединение открытым ~10 секунд,
     потребляя ресурсы сервера и клиента.
     Злоупотребление preconnect хуже, чем его отсутствие -->
```

## Priority Hints — fetchpriority

`fetchpriority` — атрибут для явного указания приоритета ресурса (Chrome 96+, Safari 17.2+):

```html
<!-- high — для LCP-изображений, критичных ресурсов -->
<img src="/hero.jpg" fetchpriority="high" alt="Hero" />

<!-- low — для некритичных ресурсов, которые не стоит
     грузить с высоким приоритетом -->
<img src="/decoration.jpg" fetchpriority="low" alt="" />

<!-- auto — дефолтное поведение браузера -->
<img src="/product.jpg" fetchpriority="auto" alt="Product" />
```

```ts
// fetchpriority работает и в fetch() API
const criticalData = await fetch('/api/above-fold-data', {
  priority: 'high',
});

const backgroundData = await fetch('/api/recommendations', {
  priority: 'low',
});
```

```html
<!-- Частый паттерн: понизить приоритет первых скрытых
     слайдов карусели — они в DOM, но не видны -->
<div class="carousel">
  <img src="/slide-1.jpg" fetchpriority="high" alt="Slide 1" />
  <img src="/slide-2.jpg" fetchpriority="low" alt="Slide 2" />
  <img src="/slide-3.jpg" fetchpriority="low" alt="Slide 3" />
</div>
```

## Lazy Loading

### Native lazy loading

```html
<!-- loading="lazy" — встроенный в браузер механизм.
     Изображение не загружается, пока не приблизится
     к вьюпорту (расстояние зависит от браузера и сети) -->
<img src="/below-fold.jpg" loading="lazy" width="800" height="600" alt="..." />

<!-- ❌ Ошибка: lazy на LCP-изображении -->
<img src="/hero.jpg" loading="lazy" alt="Hero" />

<!-- ✅ Правило: lazy — только для изображений ниже fold.
     "Выше fold" зависит от устройства, безопасный порог —
     первые 2-3 экрана пропускаем без lazy -->
```

```html
<!-- loading="lazy" работает и для <iframe> -->
<iframe
  src="https://www.youtube.com/embed/xyz"
  loading="lazy"
  width="560"
  height="315"
  title="Video"
></iframe>
```

### Intersection Observer — кастомный lazy loading

Нужен когда браузерного `loading="lazy"` недостаточно: компоненты, секции, данные.

```ts
// ✅ Универсальный хук для lazy загрузки React-компонентов
import { useEffect, useRef, useState } from 'react';

function useLazyLoad(options?: IntersectionObserverInit) {
  const ref = useRef<HTMLElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsVisible(true);
        observer.disconnect(); // наблюдать только до первого показа
      }
    }, { rootMargin: '200px', ...options }); // начинать загрузку за 200px

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, isVisible };
}

// Использование:
function HeavySection() {
  const { ref, isVisible } = useLazyLoad();

  return (
    <section ref={ref}>
      {isVisible
        ? <ExpensiveChart />
        : <div style={{ height: '400px' }} />  // placeholder
      }
    </section>
  );
}
```

```ts
// ✅ Lazy loading данных — запрашиваем API только
// когда секция приближается к вьюпорту
function ProductRecommendations() {
  const { ref, isVisible } = useLazyLoad({ rootMargin: '400px' });
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    if (!isVisible) return;
    fetch('/api/recommendations').then(r => r.json()).then(setProducts);
  }, [isVisible]);

  return (
    <section ref={ref}>
      {products.length > 0
        ? <ProductGrid products={products} />
        : <Skeleton count={4} />
      }
    </section>
  );
}
```

## Стратегия приоритетов загрузки — полная картина

```txt
Когда браузер обнаруживает ресурсы, он назначает приоритеты:

  Критичный (немедленно):
    → CSS в <head>
    → синхронные <script> в <head>
    → preload с fetchpriority="high"

  Высокий:
    → <img fetchpriority="high"> (или первые img в вьюпорте)
    → preload без fetchpriority
    → <script defer> в порядке появления

  Средний:
    → <img> без атрибутов (в вьюпорте)
    → <script async>

  Низкий:
    → <img loading="lazy">
    → prefetch
    → <img fetchpriority="low">

  Браузерный preload scanner (speculative parser):
    Параллельно с парсингом DOM, браузер сканирует
    исходный HTML в поиске ресурсов (src, href) для
    раннего старта загрузки — но видит только статический HTML,
    не CSS-backgrounds и не JS-injected элементы.
    Именно поэтому preload критичен для ресурсов,
    обнаруживаемых через CSS/JS.
```

## Практический DevTools-воркфлоу

```txt
Chrome DevTools → Network tab:
  1. Перезагрузить страницу с открытым Network
  2. Waterfall — визуализирует порядок и параллельность загрузки
  3. Цвет полосы:
     - синий = HTML
     - фиолетовый = CSS
     - жёлтый = JS
     - зелёный = изображения
  4. Priority column (правая кнопка на заголовке → Priority):
     → "Highest"/"High" — правильно для LCP-картинки?
     → "Low" — правильно для below-fold?

DevTools → Performance → запись загрузки:
  → "Initiator" — что инициировало загрузку ресурса
  → Ширина бара = время загрузки
  → Начало бара = когда браузер узнал о ресурсе

Типичный диагноз:
  Шрифт начинает грузиться через 500ms после старта →
  браузер узнал о нём поздно (из CSS) →
  добавить <link rel="preload" as="font"> в <head>
```

## Связь с другими темами

```txt
[Core Web Vitals]         — preload LCP-ресурса напрямую
                            снижает LCP; lazy loading исправляет
                            loading="lazy" на LCP-элементе
[Performance Metrics]     — preconnect снижает TTFB для
                            внешних ресурсов; preload снижает FCP
[JavaScript Performance]  — modulepreload ускоряет загрузку
                            JS-модулей; prefetch реализует
                            route-based code splitting
[Image Optimization]      — lazy loading + srcset + fetchpriority
                            работают в связке для оптимального
                            LCP и экономии трафика
```

## Типичные ошибки на интервью

- **"preload и prefetch делают одно и то же, только с разным приоритетом"** — нет. preload для ТЕКУЩЕЙ страницы (высокий приоритет, используется немедленно). prefetch для СЛЕДУЮЩЕЙ навигации (низкий приоритет, кэшируется для будущего). Смешивать их — значит не понимать ни одного.

- **"Добавил preload на всё — сайт стал быстрее"** — обратный эффект. Каждый preload конкурирует за полосу пропускания. Если preload для некритичного ресурса вытесняет LCP-картинку — LCP становится хуже. Lighthouse специально предупреждает о "unused preload".

- **"preconnect можно добавить для всех доменов"** — нет. preconnect открывает и удерживает TCP/TLS соединение (~10 сек). Для 10+ доменов это нагружает клиент и может занимать соединения, которые нужны для реальных запросов. Правило: 2-3 самых критичных, остальные — dns-prefetch.

- **"loading="lazy" решает все проблемы с изображениями"** — нет. Это лишь один инструмент. Применять к LCP-картинке — прямой вред. Без указания `width`/`height` вызывает CLS. Не помогает с форматом, сжатием, srcset.

- **"Preload scanner видит всё в HTML"** — нет. Он видит только статические `src`/`href` атрибуты в HTML. CSS `url()`, JS-injected элементы, динамические `import()` — он не видит. Именно для этих случаев нужен явный `<link rel="preload">`.

- **"fetchpriority="high" — то же самое что preload"** — разные вещи. `preload` говорит "скачай этот ресурс сейчас, независимо от того, встретишь ли ты его в документе". `fetchpriority` говорит "когда будешь скачивать этот ресурс, делай это с этим приоритетом". `preload` меняет момент обнаружения; `fetchpriority` меняет приоритет уже известного ресурса.
