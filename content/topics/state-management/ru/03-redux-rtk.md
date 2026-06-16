# Redux Toolkit

## Почему ванильный Redux был болезненным — и что RTK исправляет

Redux без вспомогательных инструментов требовал огромного количества boilerplate. Вот типичный async-флоу на ванильном Redux:

```ts
// ❌ Vanilla Redux — action types, action creators, reducer, thunk — всё вручную

// actionTypes.ts
const FETCH_USER_REQUEST = 'FETCH_USER_REQUEST';
const FETCH_USER_SUCCESS = 'FETCH_USER_SUCCESS';
const FETCH_USER_FAILURE = 'FETCH_USER_FAILURE';

// actions.ts
const fetchUserRequest = () => ({ type: FETCH_USER_REQUEST });
const fetchUserSuccess = (user: User) => ({ type: FETCH_USER_SUCCESS, payload: user });
const fetchUserFailure = (error: string) => ({ type: FETCH_USER_FAILURE, payload: error });

// thunk.ts
const fetchUser = (id: string) => async (dispatch: Dispatch) => {
  dispatch(fetchUserRequest());
  try {
    const user = await api.getUser(id);
    dispatch(fetchUserSuccess(user));
  } catch (e) {
    dispatch(fetchUserFailure(String(e)));
  }
};

// reducer.ts — иммутабельные обновления вручную (вложенные объекты — боль)
interface UserState {
  data: User | null;
  isLoading: boolean;
  error: string | null;
}
const initialState: UserState = { data: null, isLoading: false, error: null };

function userReducer(state = initialState, action: AnyAction): UserState {
  switch (action.type) {
    case FETCH_USER_REQUEST:
      return { ...state, isLoading: true, error: null };
    case FETCH_USER_SUCCESS:
      return { ...state, isLoading: false, data: action.payload };
    case FETCH_USER_FAILURE:
      return { ...state, isLoading: false, error: action.payload };
    default:
      return state;
  }
}
```

**Проблемы ванильного Redux:**
1. Каждый async-флоу требует 3 action types + 3 action creators + ветки в reducer
2. Иммутабельные обновления вложенных объектов — многострочный spread-ад
3. Нет стандарта для async — redux-thunk, redux-saga, redux-observable — каждая команда изобретала подход
4. TypeScript-типизация требовала отдельных усилий

RTK — это **официальная** библиотека-обёртка, написанная командой Redux. Она не меняет архитектуру Redux, а устраняет boilerplate:

```ts
// ✅ То же самое на Redux Toolkit — в разы меньше кода
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

const fetchUser = createAsyncThunk('user/fetch', async (id: string) => {
  return await api.getUser(id); // RTK сам генерирует pending/fulfilled/rejected
});

interface UserState {
  data: User | null;
  isLoading: boolean;
  error: string | null;
}

const userSlice = createSlice({
  name: 'user',
  initialState: { data: null, isLoading: false, error: null } as UserState,
  reducers: {
    clearUser(state) {
      state.data = null; // Immer под капотом — мутации разрешены!
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchUser.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchUser.fulfilled, (state, action: PayloadAction<User>) => {
        state.isLoading = false;
        state.data = action.payload;
      })
      .addCase(fetchUser.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.error.message ?? 'Unknown error';
      });
  },
});

export const { clearUser } = userSlice.actions;
export default userSlice.reducer;
```

## createSlice — ядро RTK

`createSlice` объединяет action types, action creators и reducer в один объект:

```ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface CartState {
  items: CartItem[];
  discount: number;
  status: 'idle' | 'loading' | 'error';
}

const cartSlice = createSlice({
  name: 'cart',   // префикс для action types: 'cart/addItem', 'cart/removeItem'
  initialState: {
    items: [],
    discount: 0,
    status: 'idle',
  } as CartState,
  reducers: {
    // Immer позволяет писать "мутабельный" код — под капотом всё иммутабельно
    addItem(state, action: PayloadAction<CartItem>) {
      const existing = state.items.find(i => i.id === action.payload.id);
      if (existing) {
        existing.qty += action.payload.qty;
      } else {
        state.items.push(action.payload); // push — OK благодаря Immer
      }
    },

    removeItem(state, action: PayloadAction<string>) {
      state.items = state.items.filter(i => i.id !== action.payload);
    },

    applyDiscount(state, action: PayloadAction<number>) {
      state.discount = action.payload;
    },

    // Если нужно вернуть новое состояние явно (например, сбросить):
    resetCart() {
      return { items: [], discount: 0, status: 'idle' };
      // Возврат нового значения — альтернатива мутации state
    },
  },
});

export const { addItem, removeItem, applyDiscount, resetCart } = cartSlice.actions;
export default cartSlice.reducer;
```

**Immer под капотом** — ключевая деталь: RTK использует библиотеку Immer, которая оборачивает `state` в Proxy. Вы пишете мутабельный код (`state.items.push(...)`), но Immer перехватывает все изменения и создаёт новый иммутабельный объект. Redux DevTools покажет именно иммутабельный diff — всё работает корректно.

**Store configuration:**

```ts
// store/index.ts
import { configureStore } from '@reduxjs/toolkit';
import cartReducer from './cartSlice';
import userReducer from './userSlice';

export const store = configureStore({
  reducer: {
    cart: cartReducer,
    user: userReducer,
  },
  // configureStore автоматически добавляет:
  // - redux-thunk middleware
  // - Redux DevTools Extension (только в dev)
  // - serializability check middleware (предупреждает о Date/функциях в state)
});

// TypeScript: выводим типы стора из самого стора
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// Типизированные хуки
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
```

## createAsyncThunk — стандарт для async

```ts
import { createAsyncThunk } from '@reduxjs/toolkit';

// Простой случай
export const fetchProducts = createAsyncThunk(
  'products/fetchAll',
  async (filters: ProductFilters) => {
    const data = await productsApi.getAll(filters);
    return data; // становится action.payload в fulfilled
  }
);

// С доступом к state и обработкой ошибок
export const addToCart = createAsyncThunk(
  'cart/addItem',
  async (productId: string, { getState, rejectWithValue }) => {
    const state = getState() as RootState;
    const userId = state.user.data?.id;

    if (!userId) {
      // rejectWithValue — контролируемая ошибка (попадёт в action.payload)
      // в отличие от throw (попадёт в action.error)
      return rejectWithValue('User not authenticated');
    }

    try {
      const item = await cartApi.add({ userId, productId });
      return item;
    } catch (e) {
      return rejectWithValue((e as Error).message);
    }
  }
);

// Использование в компоненте:
const ProductCard = ({ product }: { product: Product }) => {
  const dispatch = useAppDispatch();

  const handleAdd = async () => {
    const result = await dispatch(addToCart(product.id));

    // createAsyncThunk возвращает объект с .unwrap() —
    // позволяет получить результат или пробросить ошибку
    if (addToCart.fulfilled.match(result)) {
      toast.success('Added to cart!');
    } else {
      toast.error(result.payload as string);
    }
  };

  return <button onClick={handleAdd}>Add to cart</button>;
};
```

**Отмена запроса через AbortController:**

```ts
export const searchProducts = createAsyncThunk(
  'products/search',
  async (query: string, { signal }) => {
    // signal — AbortSignal, автоматически создаётся thunk-ом
    const response = await fetch(`/api/search?q=${query}`, { signal });
    return response.json();
  }
);

// В компоненте — отмена при unmount или новом запросе:
useEffect(() => {
  const promise = dispatch(searchProducts(query));
  return () => promise.abort(); // отменяет fetch через AbortController
}, [query]);
```

## RTK Query — кэширование и data fetching

RTK Query — встроенный в RTK инструмент для server-state. Для большинства проектов он заменяет необходимость писать async thunks для CRUD:

```ts
// store/api.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const productsApi = createApi({
  reducerPath: 'productsApi',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  tagTypes: ['Product', 'Cart'],
  endpoints: (builder) => ({
    // Query — для чтения данных
    getProducts: builder.query<Product[], ProductFilters>({
      query: (filters) => ({
        url: '/products',
        params: filters,
      }),
      providesTags: ['Product'],
    }),

    getProduct: builder.query<Product, string>({
      query: (id) => `/products/${id}`,
      providesTags: (result, error, id) => [{ type: 'Product', id }],
    }),

    // Mutation — для изменения данных
    addProduct: builder.mutation<Product, Partial<Product>>({
      query: (body) => ({
        url: '/products',
        method: 'POST',
        body,
      }),
      invalidatesTags: ['Product'], // после успешного запроса — сбросить кэш
    }),

    updateProduct: builder.mutation<Product, { id: string } & Partial<Product>>({
      query: ({ id, ...patch }) => ({
        url: `/products/${id}`,
        method: 'PATCH',
        body: patch,
      }),
      invalidatesTags: (result, error, { id }) => [{ type: 'Product', id }],
    }),
  }),
});

// RTK Query генерирует хуки автоматически:
export const {
  useGetProductsQuery,
  useGetProductQuery,
  useAddProductMutation,
  useUpdateProductMutation,
} = productsApi;

// Добавить в store:
export const store = configureStore({
  reducer: {
    [productsApi.reducerPath]: productsApi.reducer,
    cart: cartReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(productsApi.middleware),
});
```

```tsx
// Использование в компонентах:
const ProductList = ({ filters }: { filters: ProductFilters }) => {
  const { data, isLoading, isError, isFetching } = useGetProductsQuery(filters);
  // RTK Query сам: кэширует, дедуплицирует запросы, рефетчит при фокусе/reconnect

  if (isLoading) return <Spinner />;
  if (isError) return <Error />;

  return (
    <ul>
      {data?.map(product => (
        <ProductCard key={product.id} product={product} />
      ))}
      {isFetching && <Spinner size="small" />} {/* фоновое обновление */}
    </ul>
  );
};

const AddProductForm = () => {
  const [addProduct, { isLoading }] = useAddProductMutation();

  const handleSubmit = async (data: Partial<Product>) => {
    await addProduct(data).unwrap(); // .unwrap() — пробрасывает ошибку
    // После успеха RTK Query автоматически инвалидирует кэш 'Product'
    // и ProductList обновится сам
  };

  return <form onSubmit={handleSubmit}>{/* ... */}</form>;
};
```

## Selector-паттерны и createSelector

Селекторы — функции, которые вычисляют производные данные из Redux state. `createSelector` из библиотеки Reselect (встроена в RTK) мемоизирует их:

```ts
import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '../store';

// Простые "input" селекторы — без мемоизации, просто чтение
const selectCartItems = (state: RootState) => state.cart.items;
const selectDiscount = (state: RootState) => state.cart.discount;
const selectUserId = (state: RootState) => state.user.data?.id;

// Мемоизированный производный селектор
export const selectCartTotal = createSelector(
  [selectCartItems, selectDiscount],
  (items, discount) => {
    // Эта функция вызывается ТОЛЬКО если items или discount изменились
    // Иначе возвращается кэшированный результат
    return items.reduce((sum, item) => sum + item.price * item.qty, 0)
      * (1 - discount);
  }
);

export const selectCartItemCount = createSelector(
  [selectCartItems],
  (items) => items.reduce((sum, item) => sum + item.qty, 0)
);

// Параметризованный селектор — через factory
export const makeSelectItemById = (id: string) =>
  createSelector(
    [selectCartItems],
    (items) => items.find(item => item.id === id)
  );

// Использование в компоненте:
const CartSummary = () => {
  const total = useAppSelector(selectCartTotal);
  const count = useAppSelector(selectCartItemCount);
  // Ре-рендер ТОЛЬКО если total или count изменились —
  // промежуточные вычисления мемоизированы

  return <div>{count} items — ${total.toFixed(2)}</div>;
};

// Параметризованный:
const CartItemRow = ({ id }: { id: string }) => {
  // useMemo чтобы не создавать новый селектор на каждый рендер
  const selectItem = useMemo(() => makeSelectItemById(id), [id]);
  const item = useAppSelector(selectItem);

  return <div>{item?.name}</div>;
};
```

**Почему важна мемоизация селекторов:**

```ts
// ❌ Без мемоизации — пересчитывается при КАЖДОМ dispatch,
// даже если cart.items не менялся
const selectExpensiveItems = (state: RootState) =>
  state.cart.items.filter(item => item.price > 100); // новый массив каждый раз

// useSelector сравнивает результат по ссылке (===)
// Новый массив [] !== [] → компонент ре-рендерится при любом action
const ExpensiveItems = () => {
  const items = useAppSelector(selectExpensiveItems); // ре-рендер при КАЖДОМ action
};

// ✅ С createSelector — пересчёт только при изменении items
export const selectExpensiveItems = createSelector(
  [selectCartItems],
  (items) => items.filter(item => item.price > 100) // вызывается только если items изменился
);
```

## Redux data flow и middleware

Redux строго однонаправленный: `Action → Middleware → Reducer → Store → View`:

```txt
dispatch(action)
      ↓
  Middleware chain (thunk, logger, serializability check...)
      ↓
  Reducer (чистая функция: (state, action) → newState)
      ↓
  Store обновляется (новый state)
      ↓
  Подписанные компоненты (useSelector) получают уведомление
      ↓
  React ре-рендерит компоненты, у которых изменился результат selector
```

Middleware перехватывают dispatch. Redux-thunk, например, проверяет: если задиспатчено не объект, а функция — вызвать её с `(dispatch, getState)`, иначе передать дальше:

```ts
// Кастомный middleware — логирование action'ов
import { Middleware } from '@reduxjs/toolkit';

const loggerMiddleware: Middleware = (store) => (next) => (action) => {
  console.group(action.type);
  console.log('dispatching:', action);
  const result = next(action); // передаём дальше по цепочке
  console.log('next state:', store.getState());
  console.groupEnd();
  return result;
};

export const store = configureStore({
  reducer: rootReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(loggerMiddleware),
    // getDefaultMiddleware() включает: thunk + serializability + immutability
});
```

## Redux DevTools и time-travel отладка

Redux DevTools — одно из главных преимуществ Redux. Поскольку state иммутабелен и весь поток через reducer — каждое изменение state можно записать и воспроизвести:

```txt
Возможности DevTools:
  - Лог всех dispatched action'ов с payload
  - Diff state до и после каждого action
  - "Jump to" — прыжок к любому прошлому state без перезагрузки страницы
  - "Skip" — пропустить конкретный action и посмотреть, как выглядит state без него
  - Import/export state — воспроизвести баг с точным состоянием от пользователя
  - Тест reducer'ов прямо в DevTools (dispatch action вручную)
```

```ts
// configureStore автоматически подключает DevTools в development
// Опционально — расширенная конфигурация:
export const store = configureStore({
  reducer: rootReducer,
  devTools: process.env.NODE_ENV !== 'production'
    ? {
        name: 'MyApp Store',
        trace: true,          // показывает стек вызовов для каждого action
        traceLimit: 25,
      }
    : false,
});
```

**Time-travel отладка на практике**: когда пользователь сообщает о баге, можно экспортировать state из DevTools (кнопка "Export"), передать разработчику, тот импортирует его — и видит приложение в точно том состоянии, в котором был баг. Это невозможно с мутабельным state (MobX, Zustand без middleware).

## Когда Redux всё ещё правильный выбор

Redux часто считают "устаревшим" — это ошибка. Он остаётся правильным выбором в конкретных сценариях:

```txt
✅ Когда Redux — правильный выбор:

1. Предсказуемость как требование
   - финтех, медицина, юридические инструменты — где нужен
     полный audit trail всех изменений state
   - time-travel debugging критичен для воспроизведения bagов

2. Крупные команды с чётким разделением ответственности
   - Redux принудительно структурирует код (actions/reducers/selectors
     в отдельных файлах) — снижает вероятность хаоса при
     десятках контрибьюторов

3. Сложная бизнес-логика с множеством переходов состояний
   - reducer — это конечный автомат: каждый case явно задаёт
     переход. Тестируется изолированно, без React

4. Server-state управление через RTK Query
   - если в проекте много CRUD-операций с кэшированием,
     инвалидацией, polling — RTK Query конкурирует с
     React Query по возможностям и встроен в RTK

5. Уже используется в проекте и работает
   - миграция с Redux на MobX/Zustand без явной проблемы —
     это риск без выгоды
```

```txt
❌ Когда Redux — избыточен:

- Небольшое приложение с <5 разработчиками
- Простой UI-state (открыт/закрыт modal, активный tab)
- Нет требований к audit trail или time-travel
- Команда не знакома с Redux — цена обучения выше пользы
```

## Типичные ошибки на интервью

- **"RTK — это новая библиотека управления состоянием"** — нет. RTK — это официальный набор утилит поверх Redux. Архитектурно это тот же Redux: однонаправленный поток, immutable state, pure reducer. RTK устраняет boilerplate, но не меняет принципы.

- **Не понимать, что Immer делает state мутабельным "на вид"** — код `state.items.push(...)` в reducer выглядит как мутация, но это Immer-proxy. Реальный Redux state по-прежнему иммутабелен, и DevTools покажет корректный diff. Ошибка — думать, что RTK "отказался от иммутабельности".

- **Путать `rejectWithValue` и `throw`** в `createAsyncThunk`: `throw` → `action.error.message` (стандартная Error структура, не типизирована); `rejectWithValue(data)` → `action.payload` (ваши данные, типизируются). На интервью это знаковый вопрос — показывает, писал ли кандидат реальные error flows.

- **Не мемоизировать селекторы** — `useSelector` сравнивает результат по ссылке. Если селектор возвращает новый объект/массив при каждом вызове (например, через `.filter()`/`.map()`), компонент будет ре-рендериться при каждом Redux action, даже не связанном с этими данными. Это одна из самых частых причин проблем с производительностью в Redux-проектах.

- **"Redux DevTools — просто логгер"** — серьёзное занижение. Time-travel (прыжок к прошлому state), skip action, import/export state для воспроизведения багов — это производственные инструменты, которые напрямую влияют на скорость отладки в больших командах. Знание этих возможностей отличает кандидата, который реально работал с Redux в production, от того, кто только читал документацию.

- **Использовать RTK Query и redux thunks для одних и тех же данных** — RTK Query управляет своим кэшем в `state[api.reducerPath]`. Если параллельно диспатчить thunks, которые пишут те же данные в другой слайс — получаем два источника истины и рассинхронизацию. Надо выбрать одно: либо RTK Query отвечает за server-state, либо thunks — но не оба.
