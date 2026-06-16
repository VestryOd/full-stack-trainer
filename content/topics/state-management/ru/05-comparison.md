# Сравнение инструментов управления состоянием

## Разные mental model — не разные решения одной задачи

Главная ошибка при выборе между MobX, Redux и Zustand — считать их взаимозаменяемыми. Они решают похожую проблему, но исходят из принципиально разных мировоззрений.

### MobX — реактивный граф: "объяви данные, а UI сам подтянется"

```ts
// MobX: вы описываете СТРУКТУРУ данных и СВЯЗИ между ними
// Фреймворк сам отслеживает, кто что читал, и уведомляет подписчиков

class OrderStore {
  items: OrderItem[] = [];
  taxRate = 0.2;

  constructor() { makeAutoObservable(this); }

  get subtotal() { return this.items.reduce((s, i) => s + i.price * i.qty, 0); }
  get tax()      { return this.subtotal * this.taxRate; }
  get total()    { return this.subtotal + this.tax; }

  addItem(item: OrderItem) { this.items.push(item); }
}

// Граф зависимостей строится автоматически:
// items → subtotal → tax → total
// Изменение items → MobX пересчитает subtotal, затем tax и total
// и ре-рендерит ТОЛЬКО те компоненты, которые реально читали изменившиеся значения
```

**Парадигма**: императивная OOP. Данные — это объекты с методами. Изменения происходят через мутации (внутри actions). Реактивность — скрытая инфраструктура.

### Redux/RTK — конечный автомат: "явный поток событий → детерминированное состояние"

```ts
// Redux: вы описываете СОБЫТИЯ (actions) и ПЕРЕХОДЫ между состояниями (reducers)
// State — дерево иммутабельных значений. Изменить его можно только через dispatch.

// Любое изменение state — это ответ на конкретное событие
const orderSlice = createSlice({
  name: 'order',
  initialState: { items: [], taxRate: 0.2 } as OrderState,
  reducers: {
    itemAdded(state, action: PayloadAction<OrderItem>) {
      state.items.push(action.payload); // Immer — под капотом иммутабельно
    },
    taxRateChanged(state, action: PayloadAction<number>) {
      state.taxRate = action.payload;
    },
  },
});

// Производные значения — через selector'ы вне store
const selectSubtotal = createSelector(
  [(s: RootState) => s.order.items],
  (items) => items.reduce((s, i) => s + i.price * i.qty, 0)
);
const selectTotal = createSelector(
  [selectSubtotal, (s: RootState) => s.order.taxRate],
  (subtotal, taxRate) => subtotal * (1 + taxRate)
);
```

**Парадигма**: функциональная. State — иммутабельный снимок. Reducer — чистая функция перехода. Весь поток данных — явный и линейный.

### Zustand — минималистичный атомарный store: "меньше абстракций, больше контроля"

```ts
// Zustand: вы просто описываете state и функции его изменения
// Нет событий, нет редьюсеров, нет реактивного графа —
// только store как объект и явные подписки через selector

const useOrderStore = create<OrderState>()((set, get) => ({
  items: [],
  taxRate: 0.2,

  get subtotal() { /* Zustand не имеет computed — это обычный метод */ },

  // Производные значения — computed геттеры или inline в компоненте
  getSubtotal: () => get().items.reduce((s, i) => s + i.price * i.qty, 0),
  getTotal: () => {
    const { taxRate } = get();
    return get().getSubtotal() * (1 + taxRate);
  },

  addItem: (item) => set(state => ({ items: [...state.items, item] })),
}));

// Компонент подписывается явно, выбирая что именно отслеживать
const total = useOrderStore(state => state.getTotal());
```

**Парадигма**: минималистичная. Store — это просто объект в замыкании. Вся мощь — в явных selector-подписках. Никаких скрытых механизмов.

---

## Производительность и поведение ре-рендеров

Разные инструменты дают разные гарантии по ре-рендерам — это критично для крупных приложений:

### MobX — автоматическая гранулярность

```tsx
// MobX: компонент ре-рендерится ТОЛЬКО при изменении прочитанных observables
// Гранулярность — автоматическая, без усилий разработчика

const OrderTotal = observer(({ store }: { store: OrderStore }) => {
  // Во время рендера MobX отслеживает: прочитаны store.total и store.items.length
  // Ре-рендер произойдёт ТОЛЬКО при изменении total или items.length
  // Изменение taxRate без добавления items → total изменится → ре-рендер
  // Изменение другого поля store (например, isLoading) → НЕТ ре-рендера
  return <div>{store.items.length} items — ${store.total}</div>;
});

// Ключевое: если в компоненте есть conditional read —
// MobX отслеживает только то, что было прочитано в ЭТОМ рендере
const ConditionalComponent = observer(({ store }: { store: OrderStore }) => {
  if (!store.isReady) return <Spinner />; // если false — total не читается
  return <div>${store.total}</div>;       // и не отслеживается!
});
```

### Redux — ре-рендер управляется selector'ом

```tsx
// Redux: useSelector вызывается при КАЖДОМ dispatch любого action
// Если результат selector'а изменился (по ===) — ре-рендер

const OrderTotal = () => {
  // selectTotal вызывается при каждом Redux action
  // Ре-рендер только если результат !== предыдущему результату
  const total = useAppSelector(selectTotal);
  return <div>${total}</div>;
};

// Проблема без мемоизации — новый объект/массив при каждом вызове:
const BadSelector = (state: RootState) => ({
  total: selectTotal(state),
  count: state.order.items.length,
}); // ❌ новый объект каждый раз → ре-рендер на каждый dispatch

// ✅ shallowEqual как второй аргумент:
import { shallowEqual } from 'react-redux';
const OrderSummary = () => {
  const { total, count } = useAppSelector(
    state => ({ total: selectTotal(state), count: state.order.items.length }),
    shallowEqual // сравниваем поля, а не ссылку на объект
  );
  return <div>{count} items — ${total}</div>;
};
```

### Zustand — ре-рендер по результату selector'а

```tsx
// Zustand: аналогично Redux, но selector выбираете вы сами
// useStore подписывается и ре-рендерит при изменении результата selector'а

const OrderTotal = () => {
  // Если getTotal() возвращает примитив — сравнение по ===, всё хорошо
  const total = useOrderStore(state => state.getTotal());
  return <div>${total}</div>;
};

// Если нужно несколько значений — можно использовать useShallow:
import { useShallow } from 'zustand/react/shallow';

const OrderSummary = () => {
  const { total, count } = useOrderStore(
    useShallow(state => ({
      total: state.getTotal(),
      count: state.items.length,
    }))
  );
  return <div>{count} items — ${total}</div>;
};
```

**Сводка по ре-рендерам:**

```txt
MobX:    Автоматическая гранулярность. Ре-рендер только при изменении
         конкретных observables, прочитанных в рендере. Работает "магически",
         но требует понимания механизма, чтобы не потерять реактивность
         (деструктуризация вне observer, чтение вне reactive context).

Redux:   Явный контроль через selector'ы. Ре-рендер при изменении
         результата selector'а. Требует мемоизации (createSelector) для
         объектов/массивов. Предсказуемо, но многословно.

Zustand: Явный контроль через inline selector'ы. Аналогично Redux,
         но без отдельного слоя selector'ов — пишешь прямо в хуке.
         Для объектов — useShallow. Самый прозрачный механизм.
```

---

## Boilerplate и Developer Experience

```txt
Сценарий: добавить новый domain "Reviews" с async загрузкой и CRUD

MobX (~40 строк):
  - Класс ReviewStore с полями и методами
  - makeAutoObservable в constructor
  - async методы с runInAction или flow
  - Добавить в RootStore, создать хук useReviewStore

Redux/RTK (~70 строк):
  - reviewSlice с createSlice (initialState + reducers)
  - createAsyncThunk для каждого async действия
  - extraReducers для pending/fulfilled/rejected
  - Selector'ы (хотя бы базовые)
  - Добавить reducer в configureStore

Zustand (~20 строк):
  - create<ReviewState>() с полями и async методами
  - Экспортировать хук
  - Всё
```

**TypeScript experience:**

```ts
// MobX: классы + TypeScript — естественно
// Проблема: flow-генераторы теряют типизацию в месте yield
class ReviewStore {
  reviews: Review[] = []; // TypeScript видит тип

  *fetchReviews() { // возвращаемый тип — FlowReturn, не Promise
    const data: Review[] = yield api.getReviews(); // yield без типа
    this.reviews = data;
  }
}

// Redux/RTK: требует явных дженериков, но результат — строгая типизация
const fetchReviews = createAsyncThunk<Review[], void, { rejectValue: string }>(
  'reviews/fetch',
  async (_, { rejectWithValue }) => {
    // ...
  }
);
// createSlice автоматически типизирует action.payload из PayloadAction<T>

// Zustand: create<State>() — лучший TypeScript experience из трёх
const useReviewStore = create<ReviewState>()((set, get) => ({
  reviews: [] as Review[], // TypeScript полностью выводит все типы
  fetchReviews: async () => {
    const reviews = await api.getReviews(); // reviews: Review[]
    set({ reviews });
  },
}));
```

---

## Размер бандла и зависимости

```txt
Библиотека               Размер (min+gzip)   Зависимости
─────────────────────────────────────────────────────────
zustand                  ~1 KB               0
mobx + mobx-react-lite   ~18 KB              0 (peer: react)
@reduxjs/toolkit         ~14 KB              immer, reselect
react-redux              ~3 KB               0 (peer: react, redux)
redux (без RTK)          ~2 KB               0

RTK Query (в составе RTK) ~0 KB (включена)   —
React Query (аналог)      ~13 KB             0

Итог для типичного проекта:
  Zustand                 ~1 KB
  MobX stack              ~18 KB
  RTK + react-redux       ~17 KB
```

Для мобильного web разница ощутима. Для enterprise SPA — нет. Размер бандла не должен быть главным критерием выбора.

---

## Сложность тестирования

### MobX

```ts
// Плюс: классы тестируются изолированно, без React
const store = new ReviewStore(new RootStore());
store.addReview({ id: '1', text: 'Great!', rating: 5 });
expect(store.averageRating).toBe(5); // computed тестируется напрямую

// Минус: нужно следить за disposers в тестах
// Минус: flow-генераторы требуют обёртки или await для async тестов
```

### Redux/RTK

```ts
// Плюс: reducer — чистая функция, тестируется идеально
const nextState = cartReducer(initialState, addItem({ id: '1', price: 10, qty: 1 }));
expect(nextState.items).toHaveLength(1);

// Плюс: selector'ы тестируются как обычные функции
expect(selectTotal({ order: nextState })).toBe(10);

// Минус: async thunks требуют mock dispatch + getState
const mockDispatch = jest.fn();
const mockGetState = jest.fn(() => ({ user: { id: '1' } }));
await addToCart('product-1')(mockDispatch, mockGetState, undefined);
expect(mockDispatch).toHaveBeenCalledWith(expect.objectContaining({ type: 'cart/addItem/fulfilled' }));
```

### Zustand

```ts
// Плюс: getState/setState — прямой доступ без React
const { getState, setState } = useCartStore;

// Сбросить state между тестами
beforeEach(() => setState({ items: [], discount: 0 }, true));

test('addItem works', () => {
  getState().addItem({ id: '1', price: 20, qty: 1 });
  expect(getState().items).toHaveLength(1);
});

// Async — просто await
test('fetchProducts populates store', async () => {
  (api.getProducts as jest.Mock).mockResolvedValue([{ id: '1' }]);
  await getState().fetchProducts({});
  expect(getState().products).toHaveLength(1);
});
```

---

## Пути миграции

### MobX → Zustand (постепенно)

```ts
// Стратегия: создать Zustand-стор-обёртку поверх MobX-стора
// Компоненты переводить по одному, старый MobX-стор не трогать

// Временный адаптер:
const useLegacyCartStore = create<CartState>()((set) => {
  // Синхронизация из MobX в Zustand
  const dispose = autorun(() => {
    set({
      items: mobxCartStore.items.slice(), // .slice() — из observable в plain array
      total: mobxCartStore.total,
    });
  });

  return {
    items: [],
    total: 0,
    addItem: (item) => mobxCartStore.addItem(item), // делегируем в MobX
    // ...
  };
});
// После перевода всех компонентов — удалить MobX-стор
```

### Redux → Zustand (домен за доменом)

```ts
// Zustand и Redux могут сосуществовать в одном приложении
// Новые фичи — на Zustand, старые — остаются в Redux

// Если нужен доступ к Redux state из Zustand:
const useHybridStore = create<HybridState>()((set, get) => ({
  localData: [],

  syncWithRedux: () => {
    // Читаем из Redux store напрямую
    const reduxState = reduxStore.getState();
    set({ localData: reduxState.someSlice.data });
  },
}));

// Подписаться на Redux из вне React:
reduxStore.subscribe(() => {
  useHybridStore.getState().syncWithRedux();
});
```

### Redux → RTK (в рамках Redux)

```ts
// RTK обратно совместим с vanilla Redux
// Можно мигрировать по одному reducer за раз:

// Шаг 1: заменить reducer на slice
// Шаг 2: заменить action creators на slice.actions
// Шаг 3: заменить thunks на createAsyncThunk
// Шаг 4: добавить createSelector для мемоизации selector'ов
// configureStore работает со старыми reducer'ами
```

### Zustand → RTK (если проект вырос)

```ts
// Наиболее болезненная миграция — разные paradigm
// Стратегия: RTK Query для server-state, Zustand для client-state

// Гибрид работает хорошо:
// - RTK Query управляет данными с сервера (кэш, запросы, мутации)
// - Zustand управляет UI-state и client-only данными

export const store = configureStore({
  reducer: {
    [productsApi.reducerPath]: productsApi.reducer,
  },
  middleware: (gdm) => gdm().concat(productsApi.middleware),
});

// Zustand для UI state:
const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: false,
  activeTab: 'overview',
  toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),
}));
```

---

## Когда что выбирать — практическое руководство

```txt
Выбирай Zustand если:
  ✓ Новый проект, команда < 10 разработчиков
  ✓ Нет сложных требований к audit trail
  ✓ Важна скорость старта и минимум boilerplate
  ✓ Server-state управляет React Query или SWR
  ✓ Команда уже знает React hooks — Zustand освоят за день

Выбирай Redux/RTK если:
  ✓ Большая команда с чётким разделением ответственности
  ✓ Требуется полный audit trail и time-travel debugging
  ✓ Много CRUD с кэшированием → добавить RTK Query
  ✓ Уже используется в проекте (не мигрировать ради миграции)
  ✓ Сложная бизнес-логика с множеством state transitions

Выбирай MobX если:
  ✓ Команда с OOP-бэкграундом (backend-разработчики, .NET/Java)
  ✓ Сложные реактивные вычисления (derived data из derived data)
  ✓ Большие объёмы мутируемых данных (финансовые таблицы, real-time данные)
  ✓ Нужна минимальная конфигурация с максимальной реактивностью

Не выбирай ни одно из трёх если:
  - Простой UI-state: modal/tab/accordion → useState или useReducer
  - Server-state без client-кэша: React Query / SWR обрабатывают
    loading/error/caching лучше любого из трёх
```

---

## Большая сравнительная таблица

```txt
┌─────────────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Критерий                │ MobX            │ Redux/RTK       │ Zustand         │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Парадигма               │ Реактивный OOP  │ Функциональная  │ Минималистичная │
│                         │                 │ (event-driven)  │ (explicit subs) │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Мутабельность           │ Мутабельный     │ Иммутабельный   │ Иммутабельный   │
│                         │ (внутри action) │ (Immer в RTK)   │ (set возвращает │
│                         │                 │                 │ новый объект)   │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Ре-рендеры              │ Автоматически   │ Явно через      │ Явно через      │
│                         │ (reactive graph)│ selector        │ selector        │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Derived data            │ computed (lazy, │ createSelector  │ Функции в store │
│                         │ cached, auto)   │ (manual, memo)  │ (нет кэша)      │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Async                   │ flow / action + │ createAsync-    │ async функции   │
│                         │ runInAction     │ Thunk           │ (нативный)      │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Провайдер               │ Нужен (опц.)    │ Нужен           │ Не нужен        │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Boilerplate             │ Средний         │ Высокий (RTK    │ Минимальный     │
│                         │                 │ снижает)        │                 │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Бандл (min+gz)          │ ~18 KB          │ ~17 KB          │ ~1 KB           │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ TypeScript              │ Хорошо          │ Хорошо          │ Отлично         │
│                         │ (flow — хуже)   │                 │                 │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ DevTools                │ MobX DevTools   │ Redux DevTools  │ Redux DevTools  │
│                         │ (ограниченно)   │ (time-travel,   │ (devtools       │
│                         │                 │ export/import)  │ middleware)     │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Тестирование            │ Классы без React│ Reducer = pure  │ getState /      │
│                         │ (нужен dispose) │ fn (идеально);  │ setState без    │
│                         │                 │ thunks сложнее  │ React           │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Кривая освоения         │ 1-2 дня         │ 2-4 дня (RTK)   │ 30 минут        │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Сервер-стейт            │ Своя реализация │ RTK Query       │ React Query /   │
│                         │ (нет встроенной)│ (встроена)      │ SWR (внешние)   │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Inter-store             │ Через RootStore │ getState() в    │ get() в методах │
│ коммуникация            │ (DI через root) │ thunk           │ стора           │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ SSR поддержка           │ Да (с нюансами) │ Да              │ Да (из коробки) │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Строгость               │ enforceActions  │ Принудительно   │ Нет встроенной  │
│                         │ (опционально)   │ (только через   │ строгости       │
│                         │                 │ reducer)        │                 │
├─────────────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Подходит для            │ Сложные реактив.│ Большие команды,│ Новые проекты,  │
│                         │ вычисления, OOP-│ audit trail,    │ быстрый старт,  │
│                         │ команды         │ legacy проекты  │ малые команды   │
└─────────────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

---

## Типичные ошибки на интервью

- **"Мне нравится X, поэтому я всегда использую X"** — красный флаг. Хороший ответ всегда начинается с требований: размер команды, сложность бизнес-логики, нужен ли audit trail, что уже используется в проекте. Инструмент выбирается под задачу, а не задача под любимый инструмент.

- **"Redux устарел, все переходят на Zustand/MobX"** — неверно. Redux (особенно с RTK) активно развивается и остаётся правильным выбором для определённых сценариев. Zustand и MobX решают другие проблемы лучше — но не заменяют Redux полностью.

- **Не различать client-state и server-state** — управление состоянием сервера (загрузка, кэш, рефетч, мутации) — это отдельная задача. React Query, SWR и RTK Query специально предназначены для этого. Использовать MobX/Zustand для хранения данных с API без кэш-стратегии — изобретение велосипеда. Сильный кандидат понимает: MobX/Zustand/Redux — для client-state, React Query/RTK Query — для server-state, и часто оба нужны вместе.

- **Думать, что MobX "магический" и непредсказуемый** — реактивный граф MobX предсказуем при понимании механизма. Проблемы возникают только при незнании, когда прерывается reactive context (деструктуризация, async без flow, чтение вне observer). Со строгим режимом большинство ошибок обнаруживаются при разработке.

- **Говорить "Zustand маленький, значит примитивный"** — размер бандла не коррелирует со зрелостью или функциональностью. Zustand — это обдуманный минимализм, а не ограниченность. Сложность в Zustand перемещается из инфраструктуры (boilerplate Redux) в явные структуры (slices, selector'ы в хуках).

- **Не знать про Server Components и будущее state management** — в React Server Components большая часть server-state вообще не нужна на клиенте. Данные с сервера приходят как props серверного компонента, без useEffect и без store. Сильный кандидат понимает, что RSC меняет распределение: "состояние" сервера — это URL + серверные компоненты, client-state — это взаимодействие пользователя (формы, фильтры, UI). Zustand и MobX лучше вписываются в этот мир (нет Provider'а, нет serialization проблем), Redux требует адаптации.
