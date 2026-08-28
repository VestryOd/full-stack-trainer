<!-- verified: 2026-06-16, corrections: 0 -->
# Core Web Vitals

## Зачем Google придумал CWV — и почему это не просто SEO

Core Web Vitals — это три метрики, которые Google с 2021 года использует как сигнал ранжирования. Это делает их темой SEO (поисковая оптимизация), но ранжирование — меньшая половина истории. Они формализуют **три самых болезненных момента пользовательского опыта**. Каждая метрика отвечает на один вопрос, который пользователь задаёт себе не задумываясь:

- **"Долго ли мне ждать, пока увижу главный контент?"** — это LCP (Largest Contentful Paint), момент, когда дорисовался самый большой видимый кусок контента.
- **"Сдвигается ли контент под пальцем, пока страница грузится?"** — это CLS (Cumulative Layout Shift). Целишься в кнопку, а попадаешь мимо.
- **"Когда я кликаю или тапаю, страница отвечает мгновенно или зависает на полсекунды?"** — это INP (Interaction to Next Paint).

На интервью CWV часто обсуждают только через призму ранжирования. Рамка при этом перевёрнута. Это прокси-метрики пользовательского опыта: оптимизируют их ради людей, а рост в поиске — следствие.

## LCP — Largest Contentful Paint

### Что именно измеряется

LCP фиксирует момент, когда в вьюпорте отрисовывается **самый большой элемент** из допустимого списка.

**Что считается LCP-элементом,** в порядке приоритета браузера:

- `<img>`
- `<image>` внутри SVG (масштабируемая векторная графика)
- `<video>`, через его poster-картинку
- элемент с `background-image` через CSS
- блочный элемент с текстовым содержимым: `<h1>`, `<p>`, `<div>`

**Что не считается:**

- `<svg>` сам по себе
- `<canvas>`
- элементы за пределами вьюпорта
- элементы с `opacity: 0`

Браузер может **передумать**, какой элемент считать LCP-элементом. Если сначала он нашёл большой текстовый блок, а потом загрузилась картинка побольше, LCP переезжает на неё. Последнее значение перед первым взаимодействием пользователя фиксируется как финальное.

### Пороговые значения и их смысл

| Оценка | LCP |
|---|---|
| ✅ Хорошо | меньше 2.5 сек |
| ⚠️ Требует работы | 2.5 — 4.0 сек |
| ❌ Плохо | больше 4.0 сек |

Эти числа — не произвольные. Google исследовал корреляцию между временем загрузки и показателем отказов. При LCP больше 4 секунд вероятность того, что пользователь уйдёт, значительно выше. Сайт в целом оценивают по 75-му перцентилю от реальных пользователей.

### Что влияет на LCP — диагностика

Время до LCP складывается из четырёх компонентов:

| Компонент | Что в него входит |
|---|---|
| TTFB (время до первого байта) | Как быстро сервер вообще отвечает |
| Resource load delay | Пауза до того, как браузер начал грузить LCP-ресурс |
| Resource load time | Сколько этот ресурс качается |
| Element render delay | Рендер элемента после загрузки |

У каждого компонента свои типичные причины:

- **TTFB больше 600 мс** — медленный сервер, нет CDN (сеть доставки контента), нет кэша.
- **Resource load delay** — картинка не попалась preload-сканеру, потому что приходит из CSS-фона или подставляется через JS.
- **Resource load time** — большой файл, нет сжатия, нет CDN.
- **Element render delay** — рендер заблокирован JS или CSS.

### Оптимизация LCP — конкретные техники

```html
<!-- ❌ LCP-изображение загружается лениво — грубая ошибка -->
<img src="/hero.jpg" loading="lazy" alt="Hero" />

<!-- ✅ Для LCP-элемента: eager + fetchpriority -->
<img
  src="/hero.jpg"
  fetchpriority="high"
  loading="eager"
  alt="Hero"
/>
```

```html
<!-- ✅ Preload для LCP-картинки, если она не в HTML
     (например, определяется через CSS или JS) -->
<link
  rel="preload"
  as="image"
  href="/hero.webp"
  imagesrcset="/hero-400.webp 400w, /hero-800.webp 800w"
  imagesizes="(max-width: 800px) 400px, 800px"
/>
```

```ts
// ❌ LCP-изображение через JS — preload-сканер его не видит,
// браузер узнает о нём только после выполнения JS
const hero = document.createElement('img');
hero.src = '/hero.jpg';
document.body.prepend(hero);

// ✅ Если неизбежно — добавляйте preload в <head>,
// а не полагайтесь на сканер
```

```ts
// Для Next.js — правильное использование next/image для LCP
import Image from 'next/image';

// priority={true} ставит fetchpriority="high" и добавляет preload
<Image
  src="/hero.jpg"
  priority={true}
  width={1200}
  height={600}
  alt="Hero"
/>
```

**Серверные оптимизации для TTFB:**

- CDN с edge-кэшированием (CloudFront, Cloudflare)
- `Cache-Control: s-maxage=31536000` для статики
- Streaming SSR (потоковый серверный рендеринг, React 18 `renderToPipeableStream`) — браузер начинает получать HTML до окончания рендера на сервере

## CLS — Cumulative Layout Shift

### Формула расчёта — почему "0.1" не так очевидно

CLS — это **сумма** всех неожиданных сдвигов макета на протяжении всего времени на странице. У каждого отдельного сдвига есть своя оценка:

```txt
Layout Shift Score = impact fraction × distance fraction
```

- **impact fraction** — какая доля вьюпорта была затронута сдвигом, то есть размер двигающихся элементов.
- **distance fraction** — на какую долю вьюпорта сдвинулись элементы.

Разберём пример. Баннер высотой 50% вьюпорта появился и сдвинул контент на 25% вьюпорта вниз. Impact fraction равен 0.75: сам баннер 50% плюс сдвинутый контент 25%. Distance fraction равен 0.25, поэтому оценка этого сдвига — 0.75 × 0.25 = 0.1875.

Сдвиги, вызванные **пользователем** — кликом, скроллом, — в CLS не считаются. То же самое касается сдвигов в пределах 500 мс после такого взаимодействия.

| Оценка | CLS |
|---|---|
| ✅ Хорошо | меньше 0.1 |
| ⚠️ Требует работы | 0.1 — 0.25 |
| ❌ Плохо | больше 0.25 |

### Главные причины CLS и их решения

```html
<!-- ❌ Изображение без размеров — браузер не знает, сколько
     места зарезервировать до загрузки -->
<img src="/photo.jpg" alt="Photo" />

<!-- ✅ Всегда указывайте width и height — браузер вычислит
     aspect ratio и зарезервирует место заранее -->
<img src="/photo.jpg" width="800" height="450" alt="Photo" />
```

```css
/* ✅ Альтернатива через CSS aspect-ratio */
.image-container {
  aspect-ratio: 16 / 9;
  width: 100%;
}
.image-container img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
```

```html
<!-- ❌ Шрифт загружается и вызывает FOUT (Flash of Unstyled Text)
     со сдвигом макета из-за разных метрик шрифтов -->
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter" />

<!-- ✅ font-display: optional — браузер использует fallback,
     если шрифт не загрузился за первый render;
     при следующем визите шрифт уже в кэше -->
<style>
  @font-face {
    font-family: 'Inter';
    src: url('/fonts/inter.woff2') format('woff2');
    font-display: optional;
  }
</style>
```

```css
/* ✅ size-adjust + ascent/descent-override для точного
     совпадения метрик fallback-шрифта с кастомным */
@font-face {
  font-family: 'Inter-fallback';
  src: local('Arial');
  ascent-override: 90%;
  descent-override: 22%;
  line-gap-override: 0%;
  size-adjust: 107%;
}

body {
  font-family: 'Inter', 'Inter-fallback', sans-serif;
}
```

```ts
// ❌ Динамическое содержимое (реклама, баннеры) без
// зарезервированного места — классический источник CLS
const AdBanner = () => {
  const [ad, setAd] = useState<Ad | null>(null);
  useEffect(() => { fetchAd().then(setAd); }, []);
  return ad ? <div>{ad.content}</div> : null;
};

// ✅ Резервировать место явно, даже если контент ещё не загружен
const AdBanner = () => {
  const [ad, setAd] = useState<Ad | null>(null);
  useEffect(() => { fetchAd().then(setAd); }, []);
  return (
    <div style={{ minHeight: '90px', width: '728px' }}>
      {ad && <div>{ad.content}</div>}
    </div>
  );
};
```

## INP — Interaction to Next Paint

### Почему INP заменил FID в марте 2024

FID (First Input Delay) измерял задержку только **первого** взаимодействия и только задержку до начала обработки (не само время обработки). INP измеряет **все** взаимодействия на странице и **полный цикл** от события до отрисовки ответа:

```txt
FID (устарел):
  [User click] → [начало обработки JS]
                 ↑
                 FID = только это время ожидания

INP (актуален с марта 2024):
  [User click] → [начало обработки] → [JS выполнен] → [отрисовка]
  ↑_________________________________________________↑
                    INP = полный цикл
```

За сессию в отчёт идёт 98-й перцентиль всех её взаимодействий: кликов, тапов, нажатий клавиш.

| Оценка | INP |
|---|---|
| ✅ Хорошо | меньше 200 мс |
| ⚠️ Требует работы | 200 — 500 мс |
| ❌ Плохо | больше 500 мс |

### Что блокирует INP — и как чинить

```ts
// ❌ Тяжёлый synchronous обработчик — блокирует main thread,
// браузер не может отрисовать ответ
button.addEventListener('click', () => {
  const result = heavyComputation(largeData); // 300ms синхронно
  updateUI(result);
});

// ✅ Разбить с yield обратно в event loop через scheduler API
button.addEventListener('click', async () => {
  updateUI({ loading: true });

  // Yield — даём браузеру шанс отрисовать loading-состояние
  await scheduler.yield(); // или: await new Promise(r => setTimeout(r, 0))

  const result = await runInChunks(largeData);
  updateUI({ data: result, loading: false });
});
```

```ts
// ✅ scheduler.postTask для низкоприоритетной работы
// (доступно в Chrome 94+, polyfill через setTimeout для Safari)
async function handleClick() {
  // Критичное: обновить UI немедленно
  updateButtonState('pressed');

  // Некритичное: аналитика не должна блокировать ответ
  await scheduler.postTask(
    () => sendAnalytics({ event: 'click', target: 'cta' }),
    { priority: 'background' }
  );
}
```

```ts
// Измерение INP в реальном времени с web-vitals
import { onINP } from 'web-vitals';

onINP((metric) => {
  console.log('INP:', metric.value, 'ms');
  // metric.entries содержит PerformanceEventTiming для
  // худшего взаимодействия — можно посмотреть какое именно
  const worstInteraction = metric.entries.at(-1);
  console.log('Worst interaction:', worstInteraction?.name);
});
```

## Измерение CWV в DevTools

**Chrome DevTools, панель Performance:**

1. Открыть DevTools и перейти на вкладку Performance.
2. Нажать ⏺ Record или Ctrl+Shift+E, чтобы перезагрузить страницу с записью.
3. Взаимодействовать со страницей.
4. Остановить запись.

В треке "Timings" видно сразу три вещи:

- зелёная метка LCP — когда появился LCP-элемент;
- красные прямоугольники Layout Shift — сами сдвиги макета;
- длинные задачи (Long Tasks) красными полосами — что мешает INP.

Открыть стоит ещё два места:

- Вкладка **Performance Insights** даёт более высокоуровневый вид с рекомендациями.
- **Lighthouse**, вкладкой или как консольный инструмент, симулирует мобильные ограничения скорости и даёт CWV вместе с диагностикой причин.

```ts
// Программное получение CWV в браузере
import { onLCP, onCLS, onINP } from 'web-vitals';

// Отправка в аналитику при первом получении значения
onLCP((metric) => sendToAnalytics({ name: 'LCP', value: metric.value }));
onCLS((metric) => sendToAnalytics({ name: 'CLS', value: metric.value }));
onINP((metric) => sendToAnalytics({ name: 'INP', value: metric.value }));

// Важно: CLS вызывается несколько раз (delta каждого сдвига)
// или один раз с финальным значением при выходе со страницы
// Используйте reportAllChanges: false (дефолт) для финального значения
```

## Связь с другими темами

- [Resource Loading](./03-resource-loading.md) — `preload`, `prefetch` и `fetchpriority` напрямую влияют на LCP.
- [JavaScript Performance](./04-javascript-performance.md) — Long Tasks — главный враг INP. Code splitting влияет на TTI (время до интерактивности) и косвенно на LCP.
- [Image Optimization](./05-image-optimization.md) — формат, размер и lazy loading дают тройное влияние на LCP и CLS.
- [Rendering Performance](./06-rendering-performance.md) — reflow и repaint — механизм CLS. Compositing layers помогают избежать штрафов за Layout Shift.

## Типичные ошибки на интервью

- **"CWV — это SEO-метрики"** — неверная рамка. Это метрики пользовательского опыта, которые Google включил в ранжирование. Оптимизировать нужно ради пользователей, а не ради Google.

- **"FID измеряет отзывчивость"** — FID устарел и заменён INP в марте 2024. Называть FID актуальной метрикой — признак несвежих знаний.

- **"LCP — это время загрузки страницы"** — LCP измеряет конкретный момент отрисовки наибольшего видимого элемента, не общее "время загрузки". Разница принципиальная: на LCP влияет TTFB + приоритизация ресурса + render-блокировка.

- **"Добавил `loading="lazy"` на все картинки — молодец"** — `loading="lazy"` на LCP-изображение (герой-баннер, первый экран) **ухудшает** LCP, потому что браузер откладывает загрузку. Lazy loading — только для картинок ниже первого экрана.

- **"CLS — это когда страница дёргается"** — неточно. CLS учитывает только *неожиданные* сдвиги, не вызванные взаимодействием пользователя. И у него точная формула (impact × distance), а не просто "есть/нет".

- **Не знать INP-порог** — 200ms это "хорошо", 200–500ms "нужно работать". Если на интервью спросят "какой INP у вашего проекта" — важно уметь его измерить и знать пороги.

- **"Оптимизировал в Lighthouse — всё зелёное, значит хорошо"** — Lighthouse работает в симулированных условиях на одной машине. Реальные CWV берутся из Chrome User Experience Report (CrUX) — данные реальных пользователей (75-й перцентиль). Они могут кардинально отличаться.
