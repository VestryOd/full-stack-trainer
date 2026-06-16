<!-- verified: 2026-06-16, corrections: 0 -->
# Rendering Performance

## Пайплайн рендеринга браузера — основа всего

Прежде чем оптимизировать, нужно понять что именно происходит когда браузер рисует пиксели на экране:

```txt
JavaScript / CSS Animations
          ↓
    [Style]          — какие CSS-правила применимы к каждому элементу
          ↓
    [Layout]         — размеры и позиции всех элементов
    (Reflow)           (самый дорогой шаг)
          ↓
    [Paint]          — заполнение пикселей для каждого слоя
          ↓
    [Composite]      — склейка слоёв и вывод на экран

Ключевой принцип: чем раньше в пайплайне вы "выходите",
тем дешевле изменение:

  Composite-only (transform, opacity):
    пропускает Layout И Paint — только GPU
    = 0.1ms, стабильно 60fps

  Paint-only (color, background):
    пропускает Layout — только перерисовка пикселей
    = несколько ms, может вызвать джанк

  Layout (width, margin, font-size, позиция DOM):
    весь пайплайн сначала — самое дорогое
    = десятки ms, заметные зависания
```

## Reflow (Layout) — самый дорогой тип изменения

Reflow происходит когда браузер пересчитывает **геометрию страницы** — размеры и позиции элементов.

### Что вызывает reflow

```ts
// ❌ Всё это вызывает reflow:

// Изменение геометрических свойств
element.style.width = '200px';
element.style.margin = '10px';
element.style.padding = '20px';
element.style.fontSize = '16px';
element.style.display = 'flex';

// Добавление/удаление DOM-узлов
parent.appendChild(newChild);
parent.removeChild(oldChild);

// Изменение текстового содержимого
element.textContent = 'New text'; // может изменить размер

// Изменение классов, влияющих на геометрию
element.classList.add('expanded'); // если .expanded меняет width/height
```

```ts
// ❌ ЧТЕНИЕ layout-свойств также вызывает reflow!
// Браузер обязан сначала применить все отложенные изменения,
// чтобы вернуть актуальное значение

const properties = [
  'offsetWidth', 'offsetHeight', 'offsetTop', 'offsetLeft',
  'scrollWidth', 'scrollHeight', 'scrollTop', 'scrollLeft',
  'clientWidth', 'clientHeight', 'clientTop', 'clientLeft',
  'getComputedStyle()',
  'getBoundingClientRect()',
];
// Чтение любого из них = принудительный синхронный reflow
```

### Layout thrashing — чередование чтения и записи

```ts
// ❌ Layout thrashing — каждый цикл вызывает reflow
// (read → write → read → write → ...)
const boxes = document.querySelectorAll('.box');

boxes.forEach(box => {
  const width = box.offsetWidth;        // READ  → принудительный reflow
  box.style.width = `${width * 2}px`;  // WRITE → помечает layout "грязным"
  // следующий read снова вызовет reflow...
});
```

```ts
// ✅ Батчинг: сначала все читаем, потом все пишем
const boxes = document.querySelectorAll('.box');

// Один reflow — читаем все размеры сразу
const widths = Array.from(boxes).map(box => box.offsetWidth);

// Пишем — браузер применит изменения в следующем кадре
boxes.forEach((box, i) => {
  box.style.width = `${widths[i] * 2}px`;
});
```

```ts
// ✅ requestAnimationFrame — гарантирует что работаем
// в начале кадра, до Paint
function animateBoxes() {
  requestAnimationFrame(() => {
    // Все DOM-операции в одном rAF-callback
    // выполняются атомарно перед следующим кадром
    const widths = Array.from(boxes).map(b => b.offsetWidth);
    boxes.forEach((b, i) => {
      b.style.width = `${widths[i] + 1}px`;
    });
    animateBoxes(); // следующий кадр
  });
}
```

```ts
// ✅ FastDOM — библиотека для батчинга read/write
import fastdom from 'fastdom';

boxes.forEach(box => {
  fastdom.measure(() => {
    const width = box.offsetWidth; // все measure — в одном reflow
    fastdom.mutate(() => {
      box.style.width = `${width * 2}px`; // все mutate — после
    });
  });
});
```

## Repaint — перерисовка пикселей

Repaint происходит когда меняются визуальные свойства **без изменения геометрии**. Дешевле reflow, но всё равно нагружает CPU.

```ts
// Только repaint (не reflow):
element.style.color = 'red';
element.style.backgroundColor = '#fff';
element.style.visibility = 'hidden'; // vs display:none → reflow!
element.style.boxShadow = '0 2px 4px rgba(0,0,0,.2)';
element.style.borderRadius = '8px';
element.style.outline = '2px solid blue';
```

```css
/* ✅ visibility vs display:
   display: none    → reflow (элемент убирается из потока)
   visibility: hidden → только repaint (место остаётся)
   opacity: 0       → только composite (GPU) */

.hidden-no-reflow {
  visibility: hidden; /* лучше для производительности */
}

.hidden-composite {
  opacity: 0;         /* ещё лучше — только composite */
  pointer-events: none;
}
```

## Compositing — только GPU, без CPU

Compositing-only изменения — золото производительности: браузер перемещает или меняет прозрачность **уже отрисованного слоя** на GPU, не трогая CPU совсем.

```txt
Только две CSS-свойства гарантированно composite-only:
  → transform (translate, scale, rotate, skew, matrix)
  → opacity

  + filter (в современных браузерах)
  + backdrop-filter
```

```css
/* ❌ Анимация через left/top — вызывает reflow каждый кадр */
@keyframes slide-bad {
  from { left: 0; }
  to   { left: 100px; }
}

/* ✅ Анимация через transform — только composite */
@keyframes slide-good {
  from { transform: translateX(0); }
  to   { transform: translateX(100px); }
}
```

```css
/* ❌ Анимация появления через display/visibility — reflow/repaint */
.toast {
  transition: visibility 0.3s;
  visibility: hidden;
}
.toast.visible {
  visibility: visible;
}

/* ✅ Через opacity + pointer-events — только composite */
.toast {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
}
.toast.visible {
  opacity: 1;
  pointer-events: auto;
}
```

```ts
// ❌ JS-анимация через style.top — reflow каждый кадр
let pos = 0;
function animateBad() {
  pos += 1;
  element.style.top = `${pos}px`; // reflow!
  requestAnimationFrame(animateBad);
}

// ✅ JS-анимация через transform
let pos = 0;
function animateGood() {
  pos += 1;
  element.style.transform = `translateY(${pos}px)`; // composite
  requestAnimationFrame(animateGood);
}

// ✅ CSS animation/transition — предпочтительнее JS
// (браузер может оптимизировать на уровне compositor thread,
//  независимо от main thread)
```

## will-change — подсказка для браузера

`will-change` сообщает браузеру: "этот элемент скоро будет анимирован, создай для него отдельный compositor layer заранее".

```css
/* ✅ Правильное применение — только для элементов,
   которые ТОЧНО будут анимированы */
.modal {
  will-change: transform, opacity;
}

.animated-card:hover {
  will-change: transform;
}

/* ❌ Неправильно — will-change на всём подряд */
* {
  will-change: transform; /* выделяет отдельный слой КАЖДОМУ элементу */
}

.static-div {
  will-change: transform; /* этот div никогда не анимируется */
}
```

```ts
// ✅ Динамическое will-change: включать перед анимацией,
// выключать после (освобождает GPU-память)
element.addEventListener('mouseenter', () => {
  element.style.willChange = 'transform';
});

element.addEventListener('mouseleave', () => {
  element.style.willChange = 'auto'; // возвращаем браузеру контроль
});

element.addEventListener('transitionend', () => {
  element.style.willChange = 'auto';
});
```

```txt
Почему will-change нельзя применять везде:

  Каждый compositor layer занимает GPU-память
  (примерно: ширина × высота × 4 байта × 2 буфера).

  Элемент 800×600 = ~3.7MB GPU-памяти

  На мобильных устройствах GPU-память ограничена:
  слишком много слоёв → браузер начинает их выгружать/загружать
  → анимации становятся ХУЖЕ, а не лучше.

  Правило: будьте точечны.
```

## GPU Acceleration — как это работает

```txt
Браузер и GPU взаимодействуют через compositor thread:

  Main Thread (CPU):
    JavaScript → Style → Layout → Paint
    Результат: набор paint layers (текстуры)
                ↓ передача текстур
  Compositor Thread (отдельный поток):
    Composite — склейка слоёв, transform/opacity
    Результат: готовый кадр
                ↓
  GPU:
    Финальный вывод на экран

  Ключевое: compositor thread работает независимо от
  main thread. Если main thread заблокирован (Long Task),
  CSS-анимации на compositor-only свойствах
  (transform, opacity) продолжают работать гладко.

  Именно поэтому: loader/spinner через CSS animation
  на transform/opacity будет работать даже когда
  страница "завис" из-за тяжёлого JS.
```

## CSS Containment — изоляция рендеринга

`contain` позволяет браузеру изолировать поддерево DOM: изменения внутри не влияют на внешнее дерево.

```css
/* contain: layout — layout-изменения не выходят за пределы */
.card {
  contain: layout;
  /* Если содержимое карточки изменится — reflow
     затронет только саму карточку, не всю страницу */
}

/* contain: paint — paint клипируется к границам элемента */
.sidebar {
  contain: paint;
  /* Браузер не рисует за пределы sidebar.
     Экономит перерисовку при скролле */
}

/* contain: size — размер не зависит от содержимого */
.fixed-size-widget {
  contain: size;
  /* Браузер не проверяет детей для расчёта размера */
}

/* contain: strict — all of the above (кроме style) */
.isolated-widget {
  contain: strict; /* layout + paint + size */
}
```

```css
/* content-visibility: auto — "убрать" элементы за пределами
   вьюпорта из рендеринга полностью */
.article-section {
  content-visibility: auto;
  /* Браузер пропускает Style, Layout, Paint для секций
     за пределами вьюпорта до тех пор, пока они не приблизятся.
     Может дать 5–10× ускорение для длинных страниц */

  /* contain-intrinsic-size: резервирует место, чтобы
     scrollbar не прыгал при появлении контента */
  contain-intrinsic-size: 0 500px;
}
```

```ts
// Измерение выигрыша от content-visibility
// (через PerformanceObserver для Layout)
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.name === 'layout') {
      console.log(`Layout duration: ${entry.duration}ms`);
    }
  }
});
observer.observe({ type: 'layout-shift', buffered: true });
```

## React-специфичный рендеринг

### Что вызывает лишние ре-рендеры

```ts
// ❌ Новый объект при каждом рендере родителя —
// React считает props изменёнными → ре-рендер дочернего
function Parent() {
  const [count, setCount] = useState(0);

  // Новая функция при каждом рендере Parent
  const handleClick = () => setCount(c => c + 1);
  // Новый объект при каждом рендере Parent
  const config = { theme: 'dark', size: 'large' };

  return <Child onClick={handleClick} config={config} />;
}
```

```ts
// ✅ useCallback + useMemo — стабильные ссылки
function Parent() {
  const [count, setCount] = useState(0);

  const handleClick = useCallback(
    () => setCount(c => c + 1),
    [] // нет зависимостей → стабильная ссылка
  );

  const config = useMemo(
    () => ({ theme: 'dark', size: 'large' }),
    [] // тоже стабильна
  );

  return <Child onClick={handleClick} config={config} />;
}

// ✅ React.memo — пропускает ре-рендер если props не изменились
const Child = React.memo(function Child({ onClick, config }) {
  return <button onClick={onClick}>{config.theme}</button>;
});
```

```ts
// ✅ useDeferredValue — откладывает тяжёлый рендер,
// не блокируя ввод пользователя (React 18)
function SearchResults({ query }: { query: string }) {
  // deferredQuery обновляется с задержкой, когда main thread свободен
  const deferredQuery = useDeferredValue(query);

  // Тяжёлый компонент рендерится со "старым" query
  // пока пользователь продолжает печатать
  return <ExpensiveList query={deferredQuery} />;
}

function SearchPage() {
  const [query, setQuery] = useState('');

  return (
    <>
      {/* Ввод всегда отзывчивый — не ждёт ExpensiveList */}
      <input value={query} onChange={e => setQuery(e.target.value)} />
      <SearchResults query={query} />
    </>
  );
}
```

```ts
// ✅ useTransition — помечает обновление как некритичное
function TabSwitcher() {
  const [tab, setTab] = useState('home');
  const [isPending, startTransition] = useTransition();

  return (
    <>
      <button
        onClick={() => {
          // Переключение таба — некритичное обновление
          startTransition(() => setTab('profile'));
        }}
      >
        {isPending ? 'Загрузка...' : 'Профиль'}
      </button>
      <TabContent tab={tab} />
    </>
  );
}
```

### Виртуализация длинных списков

```ts
// ❌ Рендер 10 000 строк — тяжёлый DOM, медленный скролл
function BigList({ items }: { items: Item[] }) {
  return (
    <ul>
      {items.map(item => (
        <li key={item.id}>{item.name}</li>
      ))}
    </ul>
  );
}

// ✅ react-window: рендерит только видимые строки (~10-20)
import { FixedSizeList } from 'react-window';

function VirtualizedList({ items }: { items: Item[] }) {
  return (
    <FixedSizeList
      height={600}       // высота контейнера
      itemCount={items.length}
      itemSize={50}      // фиксированная высота строки
      width="100%"
    >
      {({ index, style }) => (
        <div style={style}>
          {items[index].name}
        </div>
      )}
    </FixedSizeList>
  );
}
```

## DevTools-воркфлоу для рендеринга

```txt
Chrome DevTools → Rendering tab (⋮ → More tools → Rendering):

  ✅ "Paint flashing" — зелёные прямоугольники при repaint
     → покажет что перерисовывается при скролле/анимации
     → если мигает всё — что-то вызывает избыточный repaint

  ✅ "Layout Shift Regions" — синие прямоугольники при CLS
     → видно WHERE происходят сдвиги

  ✅ "FPS meter" — счётчик fps в реальном времени
     → должен держаться у 60fps при анимациях

Chrome DevTools → Performance panel → запись анимации:

  1. ⏺ Record → воспроизвести анимацию → Stop
  2. Summary tab: "Rendering" + "Painting" — сколько времени
  3. Frames timeline: зелёный = хорошо, жёлтый/красный = проблема
  4. Main thread: длинные зелёные блоки "Paint" = дорогой repaint

Chrome DevTools → Layers panel (⋮ → More tools → Layers):
  → Визуализация compositor layers
  → Какие элементы получили отдельный слой и почему
  → Memory usage каждого слоя
  → "Reasons" column: почему создан слой (will-change, transform, etc.)
```

```ts
// Программный способ: измерение времени рендеринга
performance.mark('render-start');
// ... ваши изменения DOM
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    // Два rAF — гарантия что обновление уже применено
    performance.mark('render-end');
    performance.measure('render', 'render-start', 'render-end');
    const [measure] = performance.getEntriesByName('render');
    console.log(`Render took: ${measure.duration.toFixed(2)}ms`);
  });
});
```

## Связь с другими темами

```txt
[Core Web Vitals]         — reflow — механизм CLS;
                            Long Paint Tasks → плохой INP
[JavaScript Performance]  — Long Tasks на main thread мешают
                            compositor thread; layout thrashing
                            создаёт Long Tasks
[Performance Metrics]     — Rendering + Painting входят
                            в TBT если занимают > 50ms
[CSS Containment]         — content-visibility: auto
                            радикально снижает initial layout
                            для длинных страниц
```

## Типичные ошибки на интервью

- **"GPU ускорение — добавь transform: translateZ(0) везде"** — это хак для принудительного создания compositor layer, который работал в старых браузерах. Сегодня достаточно `will-change: transform`. Применять `translateZ(0)` ко всему — тот же эффект что и `will-change: all`: лишние слои, лишний расход GPU-памяти.

- **"opacity: 0 и display: none — одно и то же"** — нет. `display: none` удаляет элемент из потока документа → reflow. `opacity: 0` оставляет место, только меняет прозрачность → composite. Разница в производительности и в том, что `opacity: 0` элемент продолжает получать события (нужен `pointer-events: none`).

- **"will-change улучшает производительность"** — не само по себе. Оно сигнализирует браузеру создать слой заранее, что убирает задержку при начале анимации. Но если слоёв слишком много — GPU переполняется и производительность падает. Это оптимизация с потенциальными негативными последствиями.

- **"CSS-анимации всегда быстрее JS-анимаций"** — только если они анимируют composite-only свойства (transform, opacity). CSS-анимация на `width` или `margin` так же вызывает reflow как и JS. Правильное сравнение: "composite-only анимации (CSS или JS) быстрее анимаций с reflow/repaint".

- **"React.memo решит проблему производительности рендеринга"** — React.memo сравнивает props. Если каждый рендер родителя создаёт новые объекты/функции в props — React.memo бесполезен. Нужна связка: useCallback + useMemo в родителе + React.memo в дочернем.

- **"Layout thrashing — это когда много DOM-операций"** — неточно. Layout thrashing — это чередование ЧТЕНИЯ layout-свойств и ЗАПИСИ стилей. Тысяча записей подряд — батч, один reflow. Read → write → read → write в цикле — тысяча reflow.

- **"content-visibility: auto — волшебная таблетка для длинных страниц"** — почти, но есть нюансы: работает только для блочных элементов с известной высотой; нужен `contain-intrinsic-size` для предотвращения прыжка скроллбара; Find-in-page (Ctrl+F) работает, но поиск может не найти скрытый контент сразу (браузер его рендерит при необходимости).
