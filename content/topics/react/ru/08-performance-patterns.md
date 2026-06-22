# Паттерны производительности

## Правильная отправная точка: сначала измерь

Оптимизация производительности в React имеет ровно одну правильную отправную точку: **замерить с помощью React DevTools Profiler** прежде чем трогать какой-либо код. Оптимизация без замеров — это гадание на кофейной гуще: ты расставишь `useMemo` и `React.memo` везде, замедлишь приложение и всё равно не устранишь реальное узкое место.

```txt
РАБОЧИЙ ПРОЦЕСС:
  1. Зафиксировать реальную, видимую пользователем проблему производительности
     (рывки при взаимодействии, медленная первая загрузка, лагающий ввод)
  2. Открыть React DevTools → Profiler → запись во время воспроизведения проблемы
  3. Найти самые медленные компоненты (самые длинные полосы на flame chart)
  4. Понять ПОЧЕМУ они медленные (лишние ре-рендеры? дорогие вычисления?)
  5. Применить точечное исправление
  6. Замерить снова для подтверждения улучшения
```

Без шагов 2–4 любое исправление — это догадка.

---

## React.memo — правильное объяснение

`React.memo` оборачивает компонент и пропускает его ре-рендер, когда его пропсы не изменились (сравнение поверхностным равенством через `Object.is`).

```tsx
const ExpensiveList = React.memo(function ExpensiveList({
  items,
  onSelect,
}: {
  items: Item[];
  onSelect: (id: string) => void;
}) {
  // Ре-рендер только когда items или onSelect изменились (по ссылке)
  return (
    <ul>
      {items.map(item => (
        <li key={item.id} onClick={() => onSelect(item.id)}>{item.name}</li>
      ))}
    </ul>
  );
});
```

### Три условия, которые должны выполняться ОДНОВРЕМЕННО для пользы от React.memo

```txt
1. Компонент рендерится часто (родитель перерисовывается часто)
2. Ре-рендер дорогой (много дочерних компонентов, тяжёлые вычисления в рендере)
3. Пропсы референтно стабильны между рендерами
   (примитивы не меняются, объекты/массивы/функции мемоизированы)
```

Если условие 3 не выполняется, `React.memo` не даёт никакой пользы — сравнение пропсов всегда возвращает false (изменились), потому что новые ссылки на объекты/функции создаются при каждом рендере родителя.

### Самая распространённая ошибка с React.memo

```tsx
function Parent() {
  const [count, setCount] = useState(0);

  return (
    <>
      <button onClick={() => setCount(c => c + 1)}>+</button>
      {/* ❌ Новая ссылка на объект при каждом рендере — React.memo бесполезен: */}
      <MemoChild config={{ theme: 'dark' }} onSelect={() => doSomething()} />
    </>
  );
}

// Исправление: стабилизировать пропсы
function Parent() {
  const [count, setCount] = useState(0);

  const config = useMemo(() => ({ theme: 'dark' }), []);   // стабильная ссылка
  const handleSelect = useCallback(() => doSomething(), []); // стабильная ссылка

  return (
    <>
      <button onClick={() => setCount(c => c + 1)}>+</button>
      <MemoChild config={config} onSelect={handleSelect} />
    </>
  );
}
```

`React.memo`, `useMemo` и `useCallback` образуют триаду — `React.memo` на дочернем компоненте работает только тогда, когда родитель стабилизирует свои выходные данные с помощью `useMemo`/`useCallback`.

### Пользовательская функция сравнения

```tsx
const MemoizedChart = React.memo(
  function Chart({ data, title }: { data: number[]; title: string }) {
    return <canvas>...</canvas>;
  },
  (prevProps, nextProps) => {
    // true = пропсы равны = пропустить ре-рендер
    // false = пропсы изменились = выполнить ре-рендер
    return (
      prevProps.title === nextProps.title &&
      prevProps.data.length === nextProps.data.length &&
      prevProps.data.every((v, i) => v === nextProps.data[i])
    );
  }
);
```

Пользовательский компаратор нужен когда поверхностное равенство по умолчанию слишком строгое (новая ссылка на массив с идентичным содержимым всегда вызывала бы ре-рендер). Но будь осторожен: неправильный компаратор, возвращающий `true` при фактически изменившихся пропсах, приведёт к багам с устаревшим UI.

### Когда React.memo активно вредит

```tsx
// ❌ React.memo на компоненте, который всегда получает новые пропсы:
const Row = React.memo(({ item, index }: { item: Item; index: number }) => (
  <tr>...</tr>
));

function Table({ items }: { items: Item[] }) {
  return (
    <tbody>
      {items.map((item, index) => (
        // Если массив items перестраивается при каждом рендере (типично при фильтрах/сортировках),
        // ссылки на item меняются → React.memo всё равно делает ре-рендер
        // + добавляет накладные расходы на сравнение пропсов сверху.
        <Row key={item.id} item={item} index={index} />
      ))}
    </tbody>
  );
}
```

В этом случае `React.memo` запускает сравнение при каждом рендере и всегда решает перерисоваться — ты платишь за сравнение и не получаешь ничего взамен.

---

## Устранение лишних ре-рендеров — системный подход

### 1. Колокация состояния

Перемести состояние вниз туда, где оно действительно используется. Частый источник лишних ре-рендеров — состояние, живущее слишком высоко в дереве:

```tsx
// ❌ Родитель владеет состоянием, нужным только Modal → каждое изменение перерисовывает Parent:
function Page() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div>
      <HeavyDataGrid />    {/* перерисовывается каждый раз при открытии/закрытии модала */}
      <button onClick={() => setModalOpen(true)}>Открыть</button>
      {modalOpen && <Modal onClose={() => setModalOpen(false)} />}
    </div>
  );
}

// ✅ Коллоцировать состояние в выделенном компоненте:
function ModalTrigger() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Открыть</button>
      {open && <Modal onClose={() => setOpen(false)} />}
    </>
  );
}

function Page() {
  return (
    <div>
      <HeavyDataGrid />    {/* никогда не перерисовывается из-за состояния модала */}
      <ModalTrigger />
    </div>
  );
}
```

### 2. Поднять контент (паттерн children)

Когда компонент вынужден владеть быстро меняющимся состоянием, передавай медленный контент через `children` вместо прямого импорта:

```tsx
// ❌ MouseTracker импортирует HeavyChart → HeavyChart перерисовывается при каждом движении мыши:
function MouseTracker() {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  return (
    <div onMouseMove={e => setPos({ x: e.clientX, y: e.clientY })}>
      <p>Мышь: {pos.x}, {pos.y}</p>
      <HeavyChart />  {/* постоянно перерисовывается */}
    </div>
  );
}

// ✅ Передать HeavyChart как children — его родитель (Page) не перерисовывается при движении мыши:
function MouseTracker({ children }: { children: React.ReactNode }) {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  return (
    <div onMouseMove={e => setPos({ x: e.clientX, y: e.clientY })}>
      <p>Мышь: {pos.x}, {pos.y}</p>
      {children}  {/* уже отрендеренное поддерево — не перерисовывается MouseTracker'ом */}
    </div>
  );
}

function Page() {
  return (
    <MouseTracker>
      <HeavyChart />  {/* фаза рендера Page владеет HeavyChart — перерисовывается только с Page */}
    </MouseTracker>
  );
}
```

### 3. Разделение контекстов (в контексте производительности)

Подробности — в статье о контексте. Кратко: разбей монолитный контекст на несколько, сгруппированных по частоте обновлений. Компоненты, использующие `NotificationsContext`, не перерисовываются при изменении `CartContext`.

### 4. Вычисление производного состояния вместо хранения

```tsx
// ❌ Производное состояние в useState → нужно постоянно синхронизировать:
const [items, setItems] = useState<Item[]>([]);
const [filteredItems, setFilteredItems] = useState<Item[]>([]);

// setItems + setFilteredItems всегда нужно вызывать вместе → источник багов

// ✅ Вычислять при каждом рендере (или useMemo если дорого):
const [items, setItems] = useState<Item[]>([]);
const [filter, setFilter] = useState('');

const filteredItems = useMemo(
  () => items.filter(i => i.name.includes(filter)),
  [items, filter]
);
```

---

## Виртуализация — рендер только видимого

Рендер 10 000 строк списка создаёт 10 000 DOM-узлов — даже если видны только 20. Виртуализация рендерит только видимые строки (плюс небольшой буфер overscan), резко сокращая размер DOM и время рендера.

```tsx
// @tanstack/react-virtual — современное низкоуровневое решение:
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualList({ items }: { items: Item[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,  // ожидаемая высота строки в px
    overscan: 5,             // рендерить 5 лишних строк сверху и снизу вьюпорта
  });

  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      {/* Общая прокручиваемая высота — делает скроллбар точным */}
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map(virtualRow => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: virtualRow.start,    // точная позиция в пикселях
              width: '100%',
              height: virtualRow.size,
            }}
          >
            {items[virtualRow.index].name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

Для более простых случаев: `react-window` (лёгкий) или `react-virtualized` (богатый функционал, но тяжелее). Для таблиц: `@tanstack/react-table` с `@tanstack/react-virtual`.

**Когда виртуализация не нужна:**
- Списки менее ~100 элементов с простым содержимым строки
- Списки, которые редко перерисовываются
- Когда узкое место — частота ре-рендеров, а не количество DOM-узлов (виртуализация не помогает с производительностью ре-рендеров)

---

## Code splitting с React.lazy и Suspense

Каждый импортируемый компонент включается в основной JavaScript-бандл — даже если он нужен только на одной странице или за кнопкой. Code splitting разбивает бандл на чанки, загружаемые по требованию.

```tsx
// Без code splitting — HeavyEditor попадает в основной бандл:
import { HeavyEditor } from './HeavyEditor'; // 300 kB

// С code splitting — HeavyEditor загружается лениво по необходимости:
const HeavyEditor = React.lazy(() => import('./HeavyEditor'));

function Page() {
  const [editMode, setEditMode] = useState(false);

  return (
    <div>
      <button onClick={() => setEditMode(true)}>Редактировать</button>
      {editMode && (
        <Suspense fallback={<EditorSkeleton />}>
          <HeavyEditor />  {/* JS-чанк загружается когда editMode становится true */}
        </Suspense>
      )}
    </div>
  );
}
```

### Поресурсный code splitting (Next.js)

В Next.js App Router каждый `page.tsx` и `layout.tsx` автоматически является отдельным чанком. Динамические импорты дополнительно разбивают крупные компоненты внутри страницы:

```tsx
// next/dynamic — обёртка Next.js над React.lazy + Suspense:
import dynamic from 'next/dynamic';

const Map = dynamic(() => import('./Map'), {
  loading: () => <MapSkeleton />,
  ssr: false,           // не рендерить этот компонент на сервере (для browser-only библиотек)
});

// С именованным экспортом:
const Chart = dynamic(
  () => import('./Charts').then(mod => ({ default: mod.RevenueChart })),
  { loading: () => <Skeleton /> }
);
```

### Предзагрузка чанков

Если знаешь, что пользователь вот-вот перейдёт куда-то, можно предзагрузить чанк ещё до клика:

```tsx
const HeavyEditor = React.lazy(() => import('./HeavyEditor'));

function preloadEditor() {
  // Запускает динамический импорт (начинает загружать чанк)
  // без рендера компонента
  void import('./HeavyEditor');
}

function Page() {
  return (
    <button
      onMouseEnter={preloadEditor}  // начинает загрузку при наведении, до клика
      onClick={() => setEditMode(true)}
    >
      Редактировать
    </button>
  );
}
```

---

## Профилирование с React DevTools Profiler

Profiler — единственный надёжный способ найти реальные проблемы производительности.

### Чтение flame chart

```txt
FLAME CHART (одна полоса на каждый рендер компонента):
  ┌──────────────────── App (3.2ms) ─────────────────────────┐
  │ ┌─── Header (0.1ms) ───┐  ┌──────── Main (3.0ms) ──────┐ │
  │ └──────────────────────┘  │ ┌── Sidebar ──┐ ┌─ Content ─┐ │ │
  │                            │ │  (0.2ms)    │ │ (2.7ms)   │ │ │
  │                            │ └────────────┘ └───────────┘ │ │
  │                            └──────────────────────────────┘ │
  └───────────────────────────────────────────────────────────┘

  Ширина полосы = сколько времени занял этот рендер (только фаза рендера, не коммит)
  Цвет полосы:
    серый   = не рендерился в этом коммите (пропущен благодаря memo)
    зелёный = рендерился, быстро (< 1ms)
    жёлтый  = рендерился, медленно
    красный = рендерился, очень медленно (> 16ms = пропускает кадр при 60fps)
```

**Рабочий процесс для нахождения лишних ре-рендеров:**

1. Записать сессию профайлера во время воспроизведения медленного взаимодействия
2. Искать серые полосы (мемоизированные компоненты, которые были пропущены — они работают правильно) и жёлтые/красные полосы
3. Кликнуть на жёлтую/красную полосу → панель "Why did this render?" покажет причину
4. "Why did this render?" скажет какой проп или состояние изменились

### Панель "Why did this render?"

```txt
Why did <ProductList> render?
  Props changed:
    onSelect: [function] → [function]
```

Это говорит, что `onSelect` — новая ссылка на функцию при каждом рендере — именно та проблема, которую решает `useCallback`.

### Timing коммита vs рендера

Profiler измеряет **фазу рендера** (вызов функций компонентов). Он НЕ включает:
- Фазу коммита (применение мутаций DOM)
- Время выполнения `useEffect`
- Время отрисовки браузером

Компонент может быть быстрым в Profiler, но всё равно вызывать медленную отрисовку (если генерирует много DOM-мутаций в фазе коммита) или медленное воспринимаемое время (если `useEffect` делает тяжёлую работу). Используй вкладку Performance в Chrome DevTools для измерения полного времени кадра включая коммит и отрисовку.

### Profiler API для измерений в production

```tsx
// Компонент <Profiler> — работает в production, в отличие от DevTools:
import { Profiler } from 'react';

function onRenderCallback(
  id: string,              // имя компонента, переданное в проп id
  phase: 'mount' | 'update' | 'nested-update',
  actualDuration: number,  // время в фазе рендера (ms)
  baseDuration: number,    // расчётное время без оптимизаций memo
  startTime: number,
  commitTime: number,
) {
  analytics.track('react_render', { id, phase, actualDuration });
}

function Page() {
  return (
    <Profiler id="ProductList" onRender={onRenderCallback}>
      <ProductList />
    </Profiler>
  );
}
```

`baseDuration` особенно полезен: он оценивает сколько времени занял бы рендер без `React.memo` или `useMemo`. Если `baseDuration` большой, а `actualDuration` маленький — мемоизация работает. Если оба большие — компонент дорог в рендере вне зависимости от мемоизации.

---

## Дорогое тело рендера — проблема вычислений

Если сама функция рендера компонента медленная (не частота ре-рендеров), `useMemo` — правильный инструмент:

```tsx
function ReportPage({ data }: { data: RawDataPoint[] }) {
  // ❌ Запускается при каждом рендере, даже если data не изменились:
  const processed = data
    .filter(d => d.value > 0)
    .map(d => ({ ...d, normalized: d.value / data.length }))
    .sort((a, b) => b.normalized - a.normalized);

  // ✅ Пересчитывается только при изменении data:
  const processed = useMemo(
    () =>
      data
        .filter(d => d.value > 0)
        .map(d => ({ ...d, normalized: d.value / data.length }))
        .sort((a, b) => b.normalized - a.normalized),
    [data]
  );

  return <Chart data={processed} />;
}
```

Перед добавлением `useMemo` проверь через `console.time`, что вычисление действительно медленное. Для массивов менее ~1000 элементов с простыми преобразованиями обычно нет.

---

## Типичные ошибки на интервью

**«Предотвращает ли React.memo все ре-рендеры?»**
Нет. `React.memo` предотвращает только ре-рендеры, вызванные **изменениями пропсов**. Он не предотвращает ре-рендеры из-за: собственных изменений `useState`/`useReducer` компонента, изменений Context (компонент использует обновившийся контекст), или `forceUpdate`. Memo охраняет только путь проп → рендер.

**«В чём разница между React.memo и useMemo?»**
`React.memo` оборачивает **компонент** и пропускает его ре-рендер при одинаковых пропсах. `useMemo` оборачивает **вычисление внутри компонента** и кешируется между рендерами. Они решают разные задачи: `React.memo` снижает частоту вызовов функции компонента; `useMemo` снижает стоимость одного рендера.

**«Всегда ли виртуализация быстрее обычного рендера?»**
Не всегда. Виртуализация добавляет накладные расходы: абсолютное позиционирование, слушатели события scroll, динамический расчёт высот. Для списков менее ~100 элементов обычный рендер со стабильным key-пропом обычно быстрее. Виртуализация становится выгодной когда: список очень длинный (500+ элементов), каждый элемент нетривиален в рендере, и пользователь часто прокручивает.

**«Можно ли профилировать производительность в production?»**
React DevTools Profiler работает только в разработке (production-сборки вырезают код профилирования для производительности). Для профилирования в production: используй компонент `<Profiler>` API с пользовательскими `onRender`-коллбэками, отправляющими данные в аналитику, или используй сборку `react-dom/profiling` (opt-in production-сборка с поддержкой профилирования, но немного выше runtime-стоимость).

**«Что вызывает больше всего ре-рендеров в типичном React-приложении?»**
По частоте встречаемости в реальных кодовых базах: (1) объекты значений контекста, создаваемые inline в JSX (`value={{ user, setUser }}`) — вызывают ре-рендер всех потребителей при каждом рендере Provider; (2) inline-коллбэки, передаваемые мемоизированным дочерним компонентам; (3) ре-рендеры родительских компонентов из-за несвязанных изменений состояния; (4) отсутствие `key`-пропов, из-за чего React перемонтирует вместо обновления. Панель "Why did this render?" Profiler'а выявляет все эти случаи.
