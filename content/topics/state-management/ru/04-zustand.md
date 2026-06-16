# Zustand

## Минимальный API — идея в одной строке

Zustand строится на одном принципе: стор — это хук. Никаких провайдеров, никаких экшенов, никаких редьюсеров. Вызвал `create` с функцией инициализации — получил хук:

```ts
import { create } from 'zustand';

interface CartState {
  items: CartItem[];
  discount: number;
  addItem: (item: CartItem) => void;
  removeItem: (id: string) => void;
  applyDiscount: (percent: number) => void;
  total: () => number;
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  discount: 0,

  addItem: (item) =>
    set((state) => {
      const existing = state.items.find(i => i.id === item.id);
      if (existing) {
        return {
          items: state.items.map(i =>
            i.id === item.id ? { ...i, qty: i.qty + item.qty } : i
          ),
        };
      }
      return { items: [...state.items, item] };
    }),

  removeItem: (id) =>
    set((state) => ({
      items: state.items.filter(i => i.id !== id),
    })),

  applyDiscount: (percent) => set({ discount: percent / 100 }),

  // get() — синхронный доступ к текущему state из любого метода
  total: () => {
    const { items, discount } = get();
    return items.reduce((sum, i) => sum + i.price * i.qty, 0) * (1 - discount);
  },
}));
```

```tsx
// Использование — просто хук, никакого провайдера
const CartSummary = () => {
  // Подписка на конкретные поля — ре-рендер только при их изменении
  const items = useCartStore(state => state.items);
  const total = useCartStore(state => state.total());
  const addItem = useCartStore(state => state.addItem);

  return (
    <div>
      <span>{items.length} items — ${total.toFixed(2)}</span>
      <button onClick={() => addItem({ id: '1', name: 'Book', price: 20, qty: 1 })}>
        Add
      </button>
    </div>
  );
};
```

**Три параметра фабрики:**

```ts
create<State>((set, get, api) => ({
  //  set  — обновить state (как setState в React, но для всего стора)
  //  get  — прочитать текущий state синхронно
  //  api  — объект стора: { getState, setState, subscribe, destroy }
}))
```

## set и get — механика обновлений

```ts
export const useCounterStore = create<{
  count: number;
  multiplier: number;
  increment: () => void;
  incrementBy: (n: number) => void;
  reset: () => void;
  computedDouble: () => number;
}>((set, get) => ({
  count: 0,
  multiplier: 2,

  // set с функцией — получает предыдущий state, возвращает partial update
  increment: () => set((state) => ({ count: state.count + 1 })),

  // set с объектом — шорткат, когда не нужен предыдущий state
  incrementBy: (n) => set((state) => ({ count: state.count + n })),

  // Zustand делает shallow merge по умолчанию —
  // не нужно spread-ить весь state
  reset: () => set({ count: 0 }), // multiplier остаётся нетронутым

  // get() — читаем current state без подписки
  // Используется внутри методов, не в компонентах
  computedDouble: () => get().count * get().multiplier,
}));

// Полная замена state (replace = true) — редко нужно
useCounterStore.setState({ count: 0, multiplier: 1 }, true); // replace!
```

**Гранулярные подписки — главное для производительности:**

```tsx
const Counter = () => {
  // ✅ Подписываемся только на count — ре-рендер только при изменении count
  const count = useCounterStore(state => state.count);
  return <span>{count}</span>;
};

const Controls = () => {
  // ✅ actions — стабильные функции, не меняются — ре-рендера нет совсем
  const increment = useCounterStore(state => state.increment);
  const reset = useCounterStore(state => state.reset);
  return (
    <>
      <button onClick={increment}>+</button>
      <button onClick={reset}>Reset</button>
    </>
  );
};

// ❌ Подписка на весь стор — ре-рендер при ЛЮБОМ изменении
const BadComponent = () => {
  const store = useCounterStore(); // ре-рендерится даже при изменении multiplier
  return <span>{store.count}</span>;
};
```

**subscribe — подписка вне компонентов:**

```ts
// subscribe работает вне React — полезно для синхронизации с внешними системами
const unsubscribe = useCartStore.subscribe(
  (state) => state.total(),
  (total, prevTotal) => {
    // Срабатывает только при изменении total (второй аргумент — selector)
    analytics.track('cart_total_changed', { total, prevTotal });
  }
);

// Отписаться, когда больше не нужно
unsubscribe();
```

## Slices pattern — организация крупных сторов

Zustand не навязывает структуру, но для больших сторов рекомендован паттерн слайсов — аналог combineReducers в Redux:

```ts
// store/slices/cartSlice.ts
import type { StateCreator } from 'zustand';
import type { RootStore } from '../index';

export interface CartSlice {
  cart: {
    items: CartItem[];
    discount: number;
  };
  addToCart: (item: CartItem) => void;
  removeFromCart: (id: string) => void;
  getCartTotal: () => number;
}

export const createCartSlice: StateCreator<
  RootStore,            // полный тип стора — для доступа к другим слайсам
  [],
  [],
  CartSlice
> = (set, get) => ({
  cart: {
    items: [],
    discount: 0,
  },

  addToCart: (item) =>
    set((state) => ({
      cart: {
        ...state.cart,
        items: [...state.cart.items, item],
      },
    })),

  removeFromCart: (id) =>
    set((state) => ({
      cart: {
        ...state.cart,
        items: state.cart.items.filter(i => i.id !== id),
      },
    })),

  // Доступ к другому слайсу через get()
  getCartTotal: () => {
    const { cart, user } = get();
    const base = cart.items.reduce((s, i) => s + i.price * i.qty, 0);
    // user.isPremium — из userSlice, но get() даёт доступ ко всему стору
    return user.isPremium ? base * 0.9 : base;
  },
});

// store/slices/userSlice.ts
export interface UserSlice {
  user: {
    data: User | null;
    isPremium: boolean;
  };
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}

export const createUserSlice: StateCreator<RootStore, [], [], UserSlice> =
  (set) => ({
    user: { data: null, isPremium: false },

    login: async (credentials) => {
      const user = await authApi.login(credentials);
      set({ user: { data: user, isPremium: user.subscription === 'premium' } });
    },

    logout: () =>
      set({ user: { data: null, isPremium: false } }),
  });

// store/index.ts — объединяем слайсы
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { createCartSlice, CartSlice } from './slices/cartSlice';
import { createUserSlice, UserSlice } from './slices/userSlice';

export type RootStore = CartSlice & UserSlice;

export const useStore = create<RootStore>()(
  devtools(
    (...args) => ({
      ...createCartSlice(...args),
      ...createUserSlice(...args),
    }),
    { name: 'AppStore' }
  )
);

// Для удобства — отдельные хуки для каждого домена:
export const useCartStore = () => useStore(state => ({
  items: state.cart.items,
  total: state.getCartTotal(),
  addToCart: state.addToCart,
  removeFromCart: state.removeFromCart,
}));
```

## Middleware — persist, devtools, immer

Zustand имеет middleware-систему через функциональную композицию:

```ts
import { create } from 'zustand';
import { persist, devtools, subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

// persist — автоматическое сохранение в localStorage/sessionStorage
export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'light',
      language: 'en',
      notifications: true,
      setTheme: (theme) => set({ theme }),
      setLanguage: (lang) => set({ language: lang }),
    }),
    {
      name: 'app-settings',        // ключ в localStorage
      partialize: (state) => ({    // сохранять только эти поля
        theme: state.theme,
        language: state.language,
        // notifications — не сохраняем (сессионное)
      }),
      // Кастомное хранилище (например, AsyncStorage для React Native):
      // storage: createJSONStorage(() => AsyncStorage),
    }
  )
);

// devtools — интеграция с Redux DevTools
export const useCartStore = create<CartState>()(
  devtools(
    (set, get) => ({
      items: [],
      addItem: (item) => {
        set(
          (state) => ({ items: [...state.items, item] }),
          false,               // replace? false = merge
          'cart/addItem'       // имя action в DevTools
        );
      },
    }),
    { name: 'CartStore', enabled: process.env.NODE_ENV === 'development' }
  )
);

// immer middleware — мутабельные обновления как в RTK
export const useTaskStore = create<TaskState>()(
  immer((set) => ({
    tasks: [] as Task[],

    addTask: (task: Task) =>
      set((state) => {
        state.tasks.push(task); // мутация — OK с immer
      }),

    toggleTask: (id: string) =>
      set((state) => {
        const task = state.tasks.find(t => t.id === id);
        if (task) task.completed = !task.completed; // мутация вложенного объекта
      }),

    deleteTask: (id: string) =>
      set((state) => {
        const index = state.tasks.findIndex(t => t.id === id);
        if (index !== -1) state.tasks.splice(index, 1);
      }),
  }))
);

// Комбинирование middleware — порядок важен (снаружи → внутри)
export const useComplexStore = create<ComplexState>()(
  devtools(           // снаружи — первый в цепочке
    persist(          // второй
      immer(          // ближайший к create — применяется первым
        (set) => ({
          // ...
        })
      ),
      { name: 'complex-store' }
    ),
    { name: 'ComplexStore' }
  )
);
```

**subscribeWithSelector** — расширенная подписка с selector'ом (встроена в middleware):

```ts
import { subscribeWithSelector } from 'zustand/middleware';

const useStore = create<State>()(
  subscribeWithSelector((set) => ({
    count: 0,
    increment: () => set(state => ({ count: state.count + 1 })),
  }))
);

// Подписка с selector — срабатывает только при изменении выбранного значения
const unsubscribe = useStore.subscribe(
  state => state.count,            // selector
  (count, prevCount) => {          // listener
    if (count > 10) {
      console.log('Count exceeded 10!', { count, prevCount });
    }
  },
  { equalityFn: (a, b) => a === b, fireImmediately: true }
);
```

## Async в Zustand — без ceremony

Zustand не нуждается в специальных обёртках для async — это обычные async-функции:

```ts
export const useProductStore = create<ProductState>()((set, get) => ({
  products: [],
  isLoading: false,
  error: null,

  fetchProducts: async (filters: ProductFilters) => {
    set({ isLoading: true, error: null });
    try {
      const products = await productsApi.getAll(filters);
      set({ products, isLoading: false });
    } catch (e) {
      set({ isLoading: false, error: (e as Error).message });
    }
  },

  // Доступ к текущему state через get() в async-методах
  refreshIfStale: async () => {
    const { products, fetchProducts } = get();
    if (products.length === 0) {
      await fetchProducts({});
    }
  },
}));
```

Никакого `runInAction`, `flow`, `createAsyncThunk` — просто async/await. Это и есть главная причина, почему Zustand так быстро осваивается командой.

## Zustand vs Context + useReducer

Context + useReducer — встроенная альтернатива, которую часто используют "чтобы не тащить зависимость":

```tsx
// Context + useReducer — выглядит знакомо, но с проблемами:
type Action =
  | { type: 'ADD_ITEM'; payload: CartItem }
  | { type: 'REMOVE_ITEM'; payload: string };

function cartReducer(state: CartState, action: Action): CartState {
  switch (action.type) {
    case 'ADD_ITEM':
      return { ...state, items: [...state.items, action.payload] };
    case 'REMOVE_ITEM':
      return { ...state, items: state.items.filter(i => i.id !== action.payload) };
    default:
      return state;
  }
}

const CartContext = createContext<{
  state: CartState;
  dispatch: React.Dispatch<Action>;
} | null>(null);

// Проблема 1: нужен Provider — изменения топологии дерева компонентов
function App() {
  const [state, dispatch] = useReducer(cartReducer, { items: [], discount: 0 });
  return (
    <CartContext.Provider value={{ state, dispatch }}>
      <CartPage />
    </CartContext.Provider>
  );
}

// Проблема 2: ВСЕ потребители ре-рендерятся при ЛЮБОМ изменении
// Компонент, который показывает только кол-во товаров, ре-рендерится
// при изменении discount — потому что context целиком
function CartBadge() {
  const { state } = useContext(CartContext)!;
  return <span>{state.items.length}</span>;
  // ре-рендерится при изменении ЛЮБОГО поля state
}
```

```tsx
// ✅ Zustand — те же цели, без проблем Context
function CartBadge() {
  // Подписка только на items.length — ре-рендер только при его изменении
  const count = useCartStore(state => state.items.length);
  return <span>{count}</span>;
}

// Нет Provider'а — стор доступен из любого компонента в любом месте дерева
// Нет boilerplate action types и dispatch
// Гранулярные подписки из коробки
```

**Когда Context + useReducer всё же оправдан:**

```txt
- Чисто UI-state: открыт ли modal, текущий шаг wizard — не нужно
  нигде кроме поддерева компонентов
- Намеренная изоляция: отдельный состояние для каждого экземпляра
  компонента (например, несколько независимых форм на одной странице)
- Нет клиентской навигации: SSR-страницы без React hydration, где
  глобальный стор не нужен
```

## Почему Zustand часто выигрывает у Redux и MobX в новых проектах

```txt
Сравнение по болевым точкам:

Boilerplate:
  Redux/RTK   — createSlice + createAsyncThunk + selectors + Provider
                + typed hooks — минимум 50 строк на один domain
  MobX        — класс + makeAutoObservable + observer + Context/Provider
                + хуки — 30-40 строк на domain
  Zustand     — create() — 10-15 строк, всё в одном месте

Кривая освоения:
  Redux/RTK   — middleware pipeline, Immer internals, RTK Query lifecycle,
                createSelector, action matching — 2-3 дня до уверенного use
  MobX        — реактивная система, Proxy, классы, strict mode, flow —
                1-2 дня
  Zustand     — create + set + get — 30 минут

TypeScript:
  Redux/RTK   — RTK имеет хорошую типизацию, но требует AppDispatch,
                RootState, TypedUseSelectorHook — шаблонный код
  MobX        — классы + TypeScript работают естественно, но flow
                генераторов теряют типизацию в месте yield
  Zustand     — create<State>() — полный вывод типов, ничего лишнего

Размер бандла (minified+gzip):
  Redux + RTK              — ~14KB
  MobX + mobx-react-lite  — ~18KB
  Zustand                 — ~1KB

Тестируемость:
  Redux/RTK   — reducer'ы — чистые функции, тестируются идеально;
                async thunks — требуют mock dispatch
  MobX        — классы тестируются без React; нужен dispose для reactions
  Zustand     — store.getState() и store.setState() в тестах — просто
```

**Главный аргумент за Zustand в новом проекте**: он не накладывает архитектурных ограничений. Если через полгода вы решите, что нужна более строгая структура — можно добавить devtools, immer, persist по одному, или перейти на RTK. Начинать с минимума и добавлять по необходимости — лучше, чем начинать с полной конфигурации Redux и не использовать 70% возможностей.

## Типичные ошибки на интервью

- **"Zustand — это просто useState для нескольких компонентов"** — принижение. Zustand имеет middleware-систему, интеграцию с DevTools, `subscribe` вне React, persist, поддержку slices, SSR. Ключевое отличие от `useState` — стор живёт вне React-дерева и не вызывает ре-рендер провайдера.

- **Подписываться на весь стор вместо конкретных полей** — самая частая ошибка с производительностью:
  ```tsx
  // ❌
  const { items, discount, total, addItem } = useCartStore();
  // ↑ ре-рендер при изменении ЛЮБОГО поля

  // ✅
  const items = useCartStore(state => state.items);
  const addItem = useCartStore(state => state.addItem);
  ```

- **Не понимать, что actions в Zustand — стабильные ссылки** — функции, определённые внутри `create`, создаются один раз и не меняются при обновлении state. Это значит, что их безопасно передавать в `useEffect` без добавления в deps array и не нужно мемоизировать через `useCallback`.

- **Использовать `set` с полной заменой state (`replace: true`) случайно** — при вызове `set({ count: 0 }, true)` второй аргумент `true` означает полную замену всего state, а не merge. Если забыть об этом — потеряешь все остальные поля стора без единой ошибки.

- **"Zustand не подходит для больших приложений"** — неверно. Zustand используется в крупных проектах через slices pattern. Ограничение не в размере приложения, а в требованиях: если нужен строгий audit trail изменений или time-travel debugging на уровне Redux DevTools — Zustand даёт это только с devtools-middleware, но менее гибко, чем Redux.

- **Сравнивать Zustand с MobX неправильно** — они решают разные проблемы по-разному: MobX строится на реактивном графе зависимостей (объявляешь данные, MobX сам находит подписчиков), Zustand — на явных подписках (ты сам выбираешь selector). Оба минимальны в boilerplate по сравнению с Redux, но их mental model принципиально отличается.
