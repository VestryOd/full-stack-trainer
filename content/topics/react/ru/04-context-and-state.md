# Context и управление состоянием

## Что такое Context на самом деле — и чем он не является

Context — встроенный механизм React для передачи значения любому компоненту в поддереве без передачи через props каждого промежуточного компонента. Это система **инъекции зависимостей**, а не менеджер состояния.

```txt
ЧТО ДАЁТ CONTEXT:
  ✓ Способ передавать значения вниз по дереву без prop drilling
  ✓ Любой потребитель в поддереве ре-рендерится при изменении значения
  ✓ Несколько независимых контекстов могут сосуществовать

ЧЕМ CONTEXT НЕ ЯВЛЯЕТСЯ:
  ✗ Заменой Redux / Zustand / Jotai
  ✗ Оптимизированным для частых детальных обновлений
  ✗ Кешем (нет встроенной дедупликации запросов или синхронизации серверного состояния)
```

Репутация «Context медленный» исходит из конкретного и избегаемого паттерна. Понимание механики ре-рендеров точно говорит, когда эта репутация заслужена.

---

## Механика ре-рендеров — ключевое правило

**Каждый компонент, вызывающий `useContext(MyContext)`, ре-рендерится при изменении значения контекста** — независимо от того, изменилась ли конкретная часть значения, которую использует этот компонент.

```tsx
const ThemeContext = React.createContext({ color: 'blue', fontSize: 14 });

function App() {
  const [theme, setTheme] = useState({ color: 'blue', fontSize: 14 });
  return (
    <ThemeContext.Provider value={theme}>
      <Toolbar />
      <Sidebar />
    </ThemeContext.Provider>
  );
}

function Button() {
  const theme = useContext(ThemeContext);
  // Button использует только theme.color. Но если theme.fontSize изменится,
  // Button ВСЁ РАВНО ре-рендерится, потому что ссылка на объект контекста изменилась.
  return <button style={{ color: theme.color }}>Нажать</button>;
}
```

Сравнение, которое использует React: `Object.is(previousValue, nextValue)`. При изменении стейта создаётся новый объект (`setTheme(prev => ({ ...prev, fontSize: 16 }))`), ссылка меняется, `Object.is` возвращает false, и **все потребители ре-рендерятся** — даже те, кто не использует `fontSize`.

### Почему обёртка в React.memo обычно не помогает

```tsx
// ❌ Memo не защищает от изменений контекста:
const Button = React.memo(function Button() {
  const theme = useContext(ThemeContext); // подписывается на контекст
  return <button style={{ color: theme.color }}>Нажать</button>;
});
```

`React.memo` пропускает ре-рендеры когда **props** не изменились. Изменения контекста обходят `React.memo` полностью — компонент напрямую подписан на контекст и ре-рендерится при любом обновлении контекста вне зависимости от memo.

Единственный способ предотвратить ре-рендер потребителя контекста при изменении несвязанных частей — **разделить контекст**.

---

## Разделение контекстов для производительности

Правило: помещайте значения, изменяющиеся вместе, в один контекст; значения, изменяющиеся с разной частотой — в отдельные контексты.

```tsx
// ❌ Один монолитный контекст — любое изменение ре-рендерит ВСЕХ потребителей:
const AppContext = React.createContext<{
  user: User;
  theme: Theme;
  notifications: Notification[];
  cart: CartItem[];
}>(null!);

// ✅ Отдельные контексты — каждый потребитель подписан только на нужное:
const UserContext = React.createContext<User>(null!);
const ThemeContext = React.createContext<Theme>(null!);
const NotificationsContext = React.createContext<Notification[]>([]);
const CartContext = React.createContext<CartItem[]>([]);

function App() {
  const [user, setUser] = useState<User>(...);
  const [theme, setTheme] = useState<Theme>(...);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);

  return (
    <UserContext.Provider value={user}>
      <ThemeContext.Provider value={theme}>
        <NotificationsContext.Provider value={notifications}>
          <CartContext.Provider value={cart}>
            <App />
          </CartContext.Provider>
        </NotificationsContext.Provider>
      </ThemeContext.Provider>
    </UserContext.Provider>
  );
}
```

Теперь добавление уведомления ре-рендерит только потребителей `NotificationsContext`. Потребители `CartContext`, `ThemeContext` и `UserContext` не затронуты.

### Разделение state и dispatch

Конкретный паттерн разделения, важный для форм и редюсеров: помещайте state и его сеттер/dispatch в отдельные контексты.

```tsx
type Action = { type: 'increment' } | { type: 'decrement' } | { type: 'reset' };

const CountStateContext = React.createContext<number>(0);
const CountDispatchContext = React.createContext<React.Dispatch<Action>>(() => {});

function CountProvider({ children }: { children: React.ReactNode }) {
  const [count, dispatch] = useReducer(reducer, 0);

  return (
    <CountDispatchContext.Provider value={dispatch}>
      <CountStateContext.Provider value={count}>
        {children}
      </CountStateContext.Provider>
    </CountDispatchContext.Provider>
  );
}

// Компонент, который только диспатчит экшены, не подписывается на state.
// Он НЕ будет ре-рендериться при изменении count.
function ResetButton() {
  const dispatch = useContext(CountDispatchContext); // стабильная ссылка — dispatch никогда не меняется
  return <button onClick={() => dispatch({ type: 'reset' })}>Сброс</button>;
}

// Компонент, который только отображает state.
function Counter() {
  const count = useContext(CountStateContext);
  return <div>{count}</div>;
}
```

`dispatch` из `useReducer` **ссылочно стабилен** (один и тот же объект во всех рендерах) — идентично тому, как `setState` из `useState` стабилен. Помещение его в отдельный контекст означает, что компоненты, только диспатчащие экшены, никогда не ре-рендерятся из-за изменений state.

---

## Мемоизация значения контекста

Когда значение контекста конструируется inline в JSX, это новый объект при каждом рендере родителя Provider — даже если фактические данные не изменились:

```tsx
// ❌ Новый объект при каждом рендере → все потребители ре-рендерятся при каждом рендере:
function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  return (
    <AuthContext.Provider value={{ user, setUser }}> {/* новый объект при каждом рендере */}
      {children}
    </AuthContext.Provider>
  );
}

// ✅ Мемоизировано — потребители ре-рендерятся только при реальном изменении user:
function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const value = useMemo(() => ({ user, setUser }), [user]);
  // setUser стабилен (от useState) → только изменение user инвалидирует memo
  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
```

---

## useContext + useReducer — встроенный паттерн управления состоянием

Для состояния средней сложности, которое нужно разделить между многими компонентами, `useReducer` + Context — идиоматический React без внешних зависимостей:

```tsx
// 1. Определяем форму state и экшены с discriminated union
type CartState = { items: CartItem[]; total: number };
type CartAction =
  | { type: 'add'; item: CartItem }
  | { type: 'remove'; id: string }
  | { type: 'clear' };

function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'add':
      return {
        items: [...state.items, action.item],
        total: state.total + action.item.price,
      };
    case 'remove': {
      const item = state.items.find(i => i.id === action.id)!;
      return {
        items: state.items.filter(i => i.id !== action.id),
        total: state.total - item.price,
      };
    }
    case 'clear':
      return { items: [], total: 0 };
  }
}

// 2. Разделяем state и dispatch на отдельные контексты
const CartStateCtx = React.createContext<CartState>(null!);
const CartDispatchCtx = React.createContext<React.Dispatch<CartAction>>(null!);

// 3. Provider инкапсулирует редюсер
export function CartProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(cartReducer, { items: [], total: 0 });
  return (
    <CartDispatchCtx.Provider value={dispatch}>
      <CartStateCtx.Provider value={state}>
        {children}
      </CartStateCtx.Provider>
    </CartDispatchCtx.Provider>
  );
}

// 4. Кастомные хуки инкапсулируют потребление — нет прямого useContext в компонентах
export function useCartState() {
  const ctx = useContext(CartStateCtx);
  if (ctx === null) throw new Error('useCartState должен использоваться внутри CartProvider');
  return ctx;
}

export function useCartDispatch() {
  const ctx = useContext(CartDispatchCtx);
  if (ctx === null) throw new Error('useCartDispatch должен использоваться внутри CartProvider');
  return ctx;
}

// 5. Удобный хук для частого действия
export function useAddToCart() {
  const dispatch = useCartDispatch();
  return useCallback((item: CartItem) => dispatch({ type: 'add', item }), [dispatch]);
}
```

Обёртка в кастомный хук (`useCartState`, `useCartDispatch`) служит двум целям:
1. Бросает понятную ошибку, если потребитель находится за пределами Provider (намного лучше, чем загадочный краш с дефолтным значением `null`)
2. Скрывает деталь Context API — вызывающий код не должен импортировать сам объект контекста

---

## Context vs prop drilling vs внешние менеджеры состояния

```txt
PROP DRILLING
  Когда: 2-3 уровня, немного компонентов нуждаются в значении
  Плюс:  явно, локализовано, TypeScript прослеживает поток данных
  Минус: шумно при глубокой вложенности; добавление нового prop
         требует обновления каждого промежуточного компонента

CONTEXT
  Когда: по-настоящему общее значение (авторизованный пользователь, тема,
         локаль, feature flags), нужное многим компонентам на разных уровнях
  Плюс:  нет промежуточной передачи props; встроен; нет зависимостей
  Минус: все потребители ре-рендерятся при изменении значения;
         не оптимизирован для высокочастотных обновлений;
         нет devtools, time-travel или middleware из коробки

ZUSTAND / JOTAI / REDUX
  Когда: высокочастотные обновления (кадры, real-time данные);
         сложная логика обновлений; нужны devtools, middleware
         или персистентность; глобальный серверный state
         (лучше React Query / SWR)
  Плюс:  детальные подписки (ре-рендерится только компонент,
         использующий изменившийся срез); devtools; middleware
  Минус: внешняя зависимость; кривая обучения; избыточно для простых случаев
```

### Когда Context — не тот инструмент

**Высокочастотные обновления (не используйте Context):**
```tsx
// ❌ Context для позиции мыши — каждый mousemove ре-рендерит ВСЕХ потребителей:
const MouseContext = React.createContext({ x: 0, y: 0 });
// Даже с батчингом React 18 это генерирует много ре-рендеров в секунду.
// Используйте Zustand с подписками, или передавайте позицию мыши напрямую
// в компоненты, которым она нужна.
```

**Производные данные (не кладите в Context):**
```tsx
// ❌ Не помещайте вычисленные/производные значения в Context:
const value = useMemo(() => ({
  items,
  sortedItems: [...items].sort(...),    // производное
  totalCount: items.length,              // производное
  expensiveItems: items.filter(...),    // производное
}), [items]);

// ✅ Помещайте в Context только исходные данные; производите в потребителе:
// Context: items
// Потребитель: const sortedItems = useMemo(() => [...items].sort(...), [items]);
```

**Состояние конкретного компонента (не используйте Context):**
Состояние, принадлежащее одному компоненту и его прямым дочерним, должно оставаться локальным (`useState`). Излишний подъём состояния в Context делает компонент менее переиспользуемым и сложнее тестируемым.

---

## Дефолтное значение createContext — намеренная защитная сетка

```tsx
// Дефолтное значение используется ТОЛЬКО когда компонент вызывает useContext
// за пределами любого Provider:
const ThemeContext = React.createContext<Theme>({
  color: 'blue',     // разумный дефолт для компонентов, используемых без Provider
  fontSize: 14,
});

// null! как дефолтное значение — принуждает потребителей быть внутри Provider:
const AuthContext = React.createContext<AuthState>(null!);
// Если компонент вызывает useContext(AuthContext) за пределами AuthProvider,
// он получает null, что немедленно крашнется — лучше, чем тихое неверное поведение.
// Обёртка в кастомный хук (useAuth) должна проверять null и бросать понятную ошибку.
```

---

## Принцип размещения Provider

Provider'ы должны размещаться **как можно ниже в дереве**, при этом охватывая всех потребителей. Provider в корне приложения означает, что каждый ре-рендер этого Provider (даже из-за несвязанных изменений state в компоненте Provider) запускает проверки изменения контекста у всех потребителей.

```tsx
// ❌ UserProvider в корне ре-рендерится при каждом рендере корневого компонента:
function App() {
  const [globalTheme, setGlobalTheme] = useState(...);

  return (
    <UserProvider>  {/* ре-рендерит Provider при каждом изменении globalTheme */}
      <ThemeContext.Provider value={globalTheme}>
        <Routes />
      </ThemeContext.Provider>
    </UserProvider>
  );
}

// ✅ Каждый Provider изолирован:
function App() {
  return (
    <UserProvider>
      <ThemeProvider>
        <Routes />
      </ThemeProvider>
    </UserProvider>
  );
}
// UserProvider и ThemeProvider каждый управляют своим state внутренне.
// Изменения внутри одного не вызывают ре-рендеры другого Provider.
```

---

## Типичные ловушки на интервью

**«Context вызывает лишние ре-рендеры?»**
Может, если неправильно использовать. Context ре-рендерит всех потребителей при изменении значения. Решения: разделять контексты по частоте обновлений, мемоизировать объект значения, разделять state и dispatch. Если этих мер недостаточно — переходите на библиотеку с детальными подписками (Zustand, Jotai).

**«React.memo предотвращает ре-рендеры от Context?»**
Нет. `React.memo` сравнивает props — изменения контекста полностью обходят его. `React.memo`-обёрнутый компонент, вызывающий `useContext`, всё равно ре-рендерится при изменении значения контекста.

**«В чём разница между useReducer + Context и Redux?»**
Механизм похож (редюсер, dispatch, подписки). Различия: у Redux есть devtools (time-travel отладка), middleware (thunks, sagas, логирование), глобальный singleton store, и детальные подписки (через `useSelector`). У Context с `useReducer` ничего этого нет, зато нет внешней зависимости. Для приложения с 5 контекстами `useReducer` + Context часто достаточен. Для сложной сквозной логики обновлений, асинхронных потоков или когда devtools — требование, лучше подойдут Redux Toolkit или Zustand.

**«Context API подходит для серверного state (данные API)?»**
Нет. Серверный state имеет другой жизненный цикл: он может устаревать, нуждается в фоновом рефетче, дедупликации параллельных запросов, кешировании с инвалидацией и оптимистичных обновлениях. Context управляет локальным UI-состоянием. React Query и SWR созданы специально для серверного state и решают все эти проблемы. Использование Context для серверного state означает изобретение колеса, плохо.

**«Когда выбрать Zustand вместо Context?»**
Когда: (1) обновления высокочастотные (анимации, WebSocket-события, real-time совместная работа); (2) нужны детальные подписки — только срез, который изменился, должен вызывать ре-рендеры, а не все потребители; (3) нужны middleware (логирование, персистентность, devtools); (4) state действительно глобальный и доступен из многих несвязанных частей дерева.
