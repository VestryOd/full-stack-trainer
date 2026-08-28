<!-- verified: 2026-06-16, corrections: 0 -->
# Resource Loading

## Критический путь рендера — точка отсчёта

Прежде чем говорить о resource hints, нужно понять, что браузер делает с ресурсами по умолчанию — и почему это не оптимально.

Браузер получает HTML и строит из него Critical Rendering Path:

- HTML превращается в DOM (объектная модель документа).
- CSS превращается в CSSOM (объектная модель CSS).
- Эти два дерева объединяются в Render Tree, а дальше идут Layout и Paint.
- JS блокирует парсинг HTML, пока не выполнится.

Из этого порядка и следует проблема "водопада":

1. Браузер начинает парсить HTML.
2. Он встречает `<link rel="stylesheet" href="style.css">` и **останавливается**, чтобы скачать CSS.
3. Внутри этого CSS лежит `url('/fonts/inter.woff2')`, но браузер **ещё не знает** об этом шрифте — он только парсит CSS.
4. CSS скачался, распарсился, шрифт обнаружен, и только теперь начинается его загрузка. **Задержка** равна времени парсинга CSS плюс один лишний круговой рейс на запрос шрифта.

Resource hints решают ровно эту проблему. Они сообщают браузеру о ресурсах **заранее**, ещё в `<head>`. Это происходит до того, как браузер встретит их в CSS или JS, и даже до того, как они появятся на текущей странице.

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

Подсказка `modulepreload` — это вариант preload для модулей ES (ECMAScript). Обычный `preload` на модуле скачивает файл, но не обрабатывает его зависимости. А `modulepreload` скачивает модуль **и** его транзитивные зависимости, и парсит их все.

```html
<!-- modulepreload забирает всё поддерево зависимостей,
     а не только входной файл -->
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

Используйте `preload` только для ресурсов, которые выполняют все три условия:

1. Они нужны на **текущей** странице.
2. Они обнаруживаются **поздно**, не в HTML первого экрана.
3. Они критичны для LCP (largest contentful paint) или для первого рендера.

Хорошие кандидаты — это LCP-изображение, кастомный шрифт, критический CSS-файл и главный JS-бандл. Плохие кандидаты — всё, что ниже первого экрана, виджеты и аналитика.

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
// <Link> предзагружает страницу при появлении в вьюпорте
import Link from 'next/link';

// prefetch по умолчанию включён для всех <Link>
// (отключить: prefetch={false})
<Link href="/checkout">Перейти к оплате</Link>
```

Разница между двумя подсказками принципиальная, а не в степени:

| | `preload` | `prefetch` |
|---|---|---|
| Какая навигация | Текущая | Будущая |
| Приоритет | Высокий | Низкий |
| Когда используется | Немедленно | При следующей навигации |
| Браузер может пропустить | Нет | Да, например на медленном соединении |

Если предзагруженный ресурс не используется примерно три секунды, браузер ругается об этом в консоли. Ресурс, взятый через `prefetch`, хранится в HTTP-кэше для следующих запросов.

## preconnect и dns-prefetch

### preconnect — прогрев соединения

Установка соединения TCP (протокол управления передачей) и TLS (протокол защиты транспортного уровня) занимает от одного до трёх круговых рейсов. Подсказка `preconnect` делает эту работу заранее:

```html
<!-- ✅ preconnect для критичных внешних доменов —
     шрифты, CDN, API -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="preconnect" href="https://api.example.com" />

<!-- crossorigin нужен, если ресурс запрашивается
     с CORS (шрифты, fetch API) -->
```

Без `preconnect` шрифт, запрошенный из CSS, проходит всю цепочку **после** того, как CSS распарсен. Цепочка такая: разрешение имени (`DNS`), потом TCP, потом TLS, потом запрос, потом ответ.

С `preconnect` в `<head>` разрешение имени и оба рукопожатия начинаются немедленно, как только загрузился HTML. К моменту, когда CSS дойдёт до запроса шрифта, соединение уже открыто.

Экономия составляет 100–500 мс при медленном разрешении имён или на соединениях с большой задержкой.

### dns-prefetch — лёгкая альтернатива

Подсказка `dns-prefetch` только разрешает имя домена и на этом останавливается, не открывая ни соединения TCP, ни TLS, поэтому стоит дешевле:

```html
<!-- Для доменов, к которым подключение происходит
     не при загрузке страницы, а позже (аналитика,
     виджеты чата, lazy-loaded виджеты) -->
<link rel="dns-prefetch" href="https://analytics.google.com" />
<link rel="dns-prefetch" href="https://cdn.intercom.io" />
```

Как выбирать между ними:

- Критичный домен, нужный при загрузке, — берите `preconnect`.
- Некритичный домен, нужный позже, — берите `dns-prefetch`.
- Доменов слишком много для `preconnect` — оставьте два-три самых важных, остальным дайте `dns-prefetch`.

Подсказка `preconnect` держит соединение открытым около 10 секунд, потребляя ресурсы и клиента, и сервера. Злоупотреблять ей хуже, чем не использовать её вовсе.

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

Когда браузер обнаруживает ресурсы, он назначает каждому приоритет.

**Критичный, забирается немедленно:**

- CSS в `<head>`;
- синхронные `<script>` в `<head>`;
- `preload` с `fetchpriority="high"`.

**Высокий:**

- `<img fetchpriority="high">` и первые изображения в вьюпорте;
- `preload` без `fetchpriority`;
- `<script defer>` в порядке появления в документе.

**Средний:**

- `<img>` без атрибутов, в вьюпорте;
- `<script async>`.

**Низкий:**

- `<img loading="lazy">`;
- `prefetch`;
- `<img fetchpriority="low">`.

Сверх этого браузер запускает **preload scanner**, он же спекулятивный парсер. Параллельно с парсингом DOM он сканирует исходный HTML в поиске ссылок на ресурсы вроде `src` и `href`, чтобы загрузка стартовала раньше.

Сканер видит только статический HTML. Он не видит значений `url()` в CSS и не видит элементов, подставленных через JS. Именно поэтому явный `preload` критичен для ресурсов, обнаруживаемых через CSS или JavaScript.

## Практический DevTools-воркфлоу

**Chrome DevTools, вкладка Network:**

1. Перезагрузите страницу с открытой вкладкой Network.
2. Waterfall визуализирует порядок и параллельность загрузки.
3. Цвет полосы: синий — HTML, фиолетовый — CSS, жёлтый — JS, зелёный — изображения.
4. Добавьте колонку Priority правой кнопкой по заголовку таблицы. Проверьте, что LCP-картинка получает "Highest" или "High", а контент ниже первого экрана — "Low".

**DevTools → Performance → запись загрузки страницы.** Колонка "Initiator" говорит, что инициировало загрузку ресурса. Ширина бара — это время загрузки, а начало бара — момент, когда браузер узнал о ресурсе.

Типичный диагноз выглядит так. Шрифт начинает грузиться через 500 мс после старта, а значит браузер узнал о нём поздно, из CSS. Лечение — добавить `<link rel="preload" as="font">` в `<head>`.

## Связь с другими темами

- [Core Web Vitals](./01-core-web-vitals.md) — preload LCP-ресурса напрямую снижает LCP. Снять `loading="lazy"` с LCP-элемента — частая быстрая победа.
- [Performance Metrics](./02-performance-metrics.md) — `preconnect` снижает TTFB (time to first byte) для внешних ресурсов, а `preload` снижает FCP (first contentful paint).
- [JavaScript Performance](./04-javascript-performance.md) — `modulepreload` ускоряет загрузку модулей ES, а `prefetch` реализует code splitting по маршрутам.
- [Image Optimization](./05-image-optimization.md) — lazy loading, `srcset` и `fetchpriority` работают в связке ради оптимального LCP и экономии трафика.

## Типичные ошибки на интервью

- **"preload и prefetch делают одно и то же, только с разным приоритетом"** — нет. Подсказка `preload` работает на **текущую** страницу: высокий приоритет, использование немедленное. Подсказка `prefetch` работает на **следующую** навигацию: низкий приоритет, кэш на будущее. Смешивать их — значит не понимать ни одной.

- **"Добавил preload на всё — сайт стал быстрее"** — обратный эффект. Каждый preload конкурирует за полосу пропускания. Если preload для некритичного ресурса вытесняет LCP-картинку — LCP становится хуже. Lighthouse специально предупреждает о "unused preload".

- **"preconnect можно добавить для всех доменов"** — нет. `preconnect` открывает и удерживает соединение TCP/TLS примерно 10 секунд. Для десяти и более доменов это нагружает клиент и может занимать соединения, нужные для реальных запросов. Правило: два-три самых критичных домена, остальным — `dns-prefetch`.

- **"loading="lazy" решает все проблемы с изображениями"** — нет. Это лишь один инструмент. Применять к LCP-картинке — прямой вред. Без указания `width`/`height` вызывает CLS (cumulative layout shift). Не помогает с форматом, сжатием, `srcset`.

- **"Preload scanner видит всё в HTML"** — нет. Он видит только статические `src`/`href` атрибуты в HTML. CSS `url()`, JS-injected элементы, динамические `import()` — он не видит. Именно для этих случаев нужен явный `<link rel="preload">`.

- **"fetchpriority="high" — то же самое что preload"** — разные вещи. Подсказка `preload` говорит: скачай этот ресурс сейчас, независимо от того, встретишь ли ты его в документе. Атрибут `fetchpriority` говорит: когда будешь скачивать этот уже известный ресурс, делай это с таким приоритетом. То есть `preload` меняет момент обнаружения, а `fetchpriority` — приоритет уже известного ресурса.
