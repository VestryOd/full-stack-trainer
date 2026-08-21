# Паттерны производительности

## Правильная отправная точка: сначала измерь

Оптимизация производительности в React имеет ровно одну правильную отправную точку: **сначала замерить в React DevTools Profiler**, и только потом трогать код. Оптимизация без замеров — это угадывание. Вы расставите `useMemo` и `React.memo` везде, замедлите приложение и всё равно не устраните реальное узкое место.

```txt
Рабочий процесс
  1. Найти реальную, видимую пользователю проблему
     (рывки при взаимодействии, медленная первая
     загрузка, лагающий ввод)
  2. Открыть React DevTools → Profiler и записать
     сессию, воспроизводя проблему
  3. Найти самые медленные компоненты — самые
     длинные полосы на flame chart
  4. Понять, почему они медленные: лишние
     ре-рендеры или дорогие вычисления?
  5. Применить точечное исправление
  6. Замерить снова и подтвердить улучшение
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

### Три условия, которые должны выполняться **одновременно** для пользы от React.memo

1. Компонент рендерится часто — его родитель перерисовывается часто.
2. Ре-рендер дорогой: много дочерних компонентов или тяжёлые вычисления
   в рендере.
3. Пропсы стабильны по ссылке между рендерами. Примитивы не меняются,
   а объекты, массивы и функции мемоизированы.

Если условие 3 не выполняется, `React.memo` не даёт никакой пользы. Сравнение пропсов всегда возвращает false, то есть «изменились»: новые ссылки на объекты и функции создаются при каждом рендере родителя.

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

Свой компаратор нужен, когда поверхностного равенства по умолчанию слишком мало: новая ссылка на массив с тем же содержимым всегда вызвала бы ре-рендер. Но будьте осторожны. Неправильный компаратор, который возвращает `true` при фактически изменившихся пропсах, оставит на экране устаревшие данные. UI — user interface, то, что видит пользователь, — перестанет соответствовать состоянию.

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
        // Если массив items перестраивается при каждом рендере
        // (типично при фильтрах и сортировках), ссылки на item меняются.
        // React.memo всё равно перерисует, да ещё и потратит время
        // на сравнение пропсов.
        <Row key={item.id} item={item} index={index} />
      ))}
    </tbody>
  );
}
```

В этом случае `React.memo` запускает сравнение при каждом рендере и всё равно решает перерисоваться. Вы платите за сравнение и не получаете ничего взамен.

---

## Устранение лишних ре-рендеров — системный подход

### 1. Держите состояние рядом с тем, кто им пользуется

Опустите состояние вниз по дереву — туда, где оно действительно нужно. Частый источник лишних ре-рендеров — состояние, живущее слишком высоко в дереве:

```tsx
// ❌ Родитель владеет состоянием, нужным только Modal:
// каждое изменение перерисовывает Page
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

// ✅ Держим состояние в отдельном компоненте:
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

Когда компонент вынужден владеть быстро меняющимся состоянием, передавайте медленное содержимое через `children`, а не импортируйте его напрямую:

```tsx
// ❌ MouseTracker импортирует HeavyChart, и HeavyChart
// перерисовывается при каждом движении мыши:
function MouseTracker() {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  return (
    <div onMouseMove={e => setPos({ x: e.clientX, y: e.clientY })}>
      <p>Мышь: {pos.x}, {pos.y}</p>
      <HeavyChart />  {/* постоянно перерисовывается */}
    </div>
  );
}

// ✅ Передаём HeavyChart как children: его родитель (Page)
// не перерисовывается при движении мыши
function MouseTracker({ children }: { children: React.ReactNode }) {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  return (
    <div onMouseMove={e => setPos({ x: e.clientX, y: e.clientY })}>
      <p>Мышь: {pos.x}, {pos.y}</p>
      {children}  {/* готовое поддерево, MouseTracker его не перерисовывает */}
    </div>
  );
}

function Page() {
  return (
    <MouseTracker>
      <HeavyChart />  {/* HeavyChart принадлежит рендеру Page */}
    </MouseTracker>
  );
}
```

### 3. Разделение контекстов (в контексте производительности)

Подробности — в статье [Контекст и состояние](./04-context-and-state.md). Кратко: разбейте монолитный контекст на несколько, сгруппировав их по частоте обновлений. Компоненты, использующие `NotificationsContext`, не перерисовываются при изменении `CartContext`.

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

Рендер 10 000 строк списка создаёт 10 000 узлов DOM. DOM — это Document Object Model, дерево объектов, из которого браузер рисует страницу. Эти узлы появятся, даже если видны всего 20 строк. Виртуализация рендерит только видимые строки плюс небольшой запас (overscan). Это сокращает и размер DOM, и время рендера.

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

Каждый импортируемый компонент попадает в основной JavaScript-бандл — даже если нужен только на одной странице или за кнопкой. Разбиение кода (code splitting) делит бандл на чанки: отдельные файлы, которые браузер скачивает только по необходимости.

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

### Разбиение по маршрутам (Next.js)

В Next.js App Router каждый `page.tsx` и `layout.tsx` автоматически попадает в отдельный чанк — файл, который браузер скачивает только при заходе на этот маршрут. Динамические импорты дополнительно разбивают крупные компоненты внутри страницы:

```tsx
// next/dynamic — обёртка Next.js над React.lazy + Suspense:
import dynamic from 'next/dynamic';

const Map = dynamic(() => import('./Map'), {
  loading: () => <MapSkeleton />,
  ssr: false,           // не рендерить на сервере (для браузерных библиотек)
});

// С именованным экспортом:
const Chart = dynamic(
  () => import('./Charts').then(mod => ({ default: mod.RevenueChart })),
  { loading: () => <Skeleton /> }
);
```

### Предзагрузка чанков

Если вы знаете, что пользователь вот-вот куда-то перейдёт, чанк можно предзагрузить ещё до клика:

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

Одна полоса — один рендер компонента. Полоса ребёнка лежит внутри полосы родителя:

```txt
┌─────────────────────────────────────────────────────────────┐
│ App 3.2 мс                                                  │
│ ┌───────────────┐ ┌───────────────────────────────────────┐ │
│ │ Header 0.1 мс │ │ Main 3.0 мс                           │ │
│ └───────────────┘ │ ┌────────────────┐ ┌────────────────┐ │ │
│                   │ │ Sidebar 0.2 мс │ │ Content 2.7 мс │ │ │
│                   │ └────────────────┘ └────────────────┘ │ │
│                   └───────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

Ширина полосы — сколько времени занял этот рендер: только фаза рендера,
без коммита. Остальное говорит цвет:

- **серый** — в этом коммите не рендерился, пропущен благодаря memo.
- **зелёный** — рендерился быстро, меньше 1 мс.
- **жёлтый** — рендерился медленно.
- **красный** — рендерился очень медленно, дольше 16 мс: это пропущенный кадр при 60 fps.

**Рабочий процесс для нахождения лишних ре-рендеров:**

1. Записать сессию профайлера во время воспроизведения медленного взаимодействия
2. Искать серые полосы и жёлтые с красными. Серая полоса — мемоизированный компонент, который в этом коммите пропущен: он работает правильно
3. Кликнуть на жёлтую/красную полосу → панель "Why did this render?" покажет причину
4. "Why did this render?" скажет какой проп или состояние изменились

### Панель "Why did this render?"

```txt
Why did <ProductList> render?
  Props changed:
    onSelect: [function] → [function]
```

Это значит, что `onSelect` — новая ссылка на функцию при каждом рендере. Именно эту проблему и решает `useCallback`.

### Время коммита против времени рендера

Profiler измеряет **фазу рендера** — вызовы функций компонентов. В это измерение не входят:

- фаза коммита, то есть применение мутаций DOM;
- время выполнения `useEffect`;
- время отрисовки браузером.

Компонент может выглядеть быстрым в Profiler и всё равно тормозить. Причин две: он создаёт много мутаций DOM в фазе коммита, либо его `useEffect` делает тяжёлую работу. Полное время кадра, вместе с коммитом и отрисовкой, смотрите на вкладке Performance в Chrome DevTools.

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

`baseDuration` особенно полезен: он оценивает, сколько времени занял бы рендер без `React.memo` и `useMemo`. Если `baseDuration` большой, а `actualDuration` маленький — мемоизация работает. Если велики оба — компонент дорог в рендере независимо от мемоизации.

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

Перед добавлением `useMemo` проверьте через `console.time`, что вычисление действительно медленное. Для массивов меньше примерно 1000 элементов с простыми преобразованиями оно обычно быстрое.

---

## Типичные ошибки на интервью

**«Предотвращает ли React.memo все ре-рендеры?»**
Нет. `React.memo` предотвращает только ре-рендеры, вызванные **изменениями пропсов**. Он не предотвращает ре-рендеры из-за: собственных изменений `useState`/`useReducer` компонента, изменений Context (компонент использует обновившийся контекст), или `forceUpdate`. Memo охраняет только путь проп → рендер.

**«В чём разница между React.memo и useMemo?»**
Они решают разные задачи: один пропускает целый рендер, другой — одно вычисление.

| | `React.memo` | `useMemo` |
|---|---|---|
| Что оборачивает | компонент | вычисление внутри компонента |
| Что пропускает | весь ре-рендер, если пропсы те же | пересчёт, если зависимости те же |
| Что снижает | частоту вызовов функции компонента | стоимость одного рендера |

**«Всегда ли виртуализация быстрее обычного рендера?»**
Не всегда. Виртуализация добавляет накладные расходы: абсолютное позиционирование, слушатели события scroll, динамический расчёт высот. Для списков меньше примерно 100 элементов обычный рендер со стабильным `key` обычно быстрее.

Виртуализация выгодна при трёх условиях сразу:

| Условие | Порог |
|---|---|
| Список длинный | 500+ элементов |
| Элемент нетривиален в рендере | не одна строка текста |
| Пользователь часто прокручивает | прокрутка — основное действие |

**«Можно ли профилировать производительность в production?»**
React DevTools Profiler работает только в разработке: production-сборки вырезают код профилирования. Остаются два варианта:

- Компонент `<Profiler>` со своим коллбэком `onRender`, отправляющим числа в аналитику.
- Сборка `react-dom/profiling` — production-сборка, которую включают вручную; она сохраняет профилирование, но чуть дороже во время работы.

**«Что вызывает больше всего ре-рендеров в типичном React-приложении?»**
Четыре причины, по частоте встречаемости в реальных кодовых базах:

1. Объекты-значения контекста, созданные прямо в JSX. JSX — это HTML-подобный синтаксис, на котором пишут компоненты React. Запись `value={{ user, setUser }}` перерисовывает всех потребителей при каждом рендере Provider.
2. Коллбэки, объявленные прямо в разметке и переданные мемоизированным дочерним компонентам.
3. Ре-рендеры родительских компонентов из-за несвязанных изменений состояния.
4. Отсутствие пропа `key`, из-за чего React перемонтирует элемент вместо обновления.

Все четыре случая показывает панель Profiler «Why did this render?».
