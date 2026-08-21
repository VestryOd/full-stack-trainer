# Паттерны и композиция

## Почему паттерны важны на уровне senior

Базовый набор API у React небольшой: компоненты, пропсы, состояние, контекст. Паттерны — это готовые ответы на повторяющиеся задачи: как делиться логикой, как давать потребителям контроль, как компоновать без лишних связей. На уровне senior от вас ждут, что вы узнаете подходящий паттерн и объясните, почему выбрали именно его.

---

## Составные компоненты (Compound Components)

### Проблема

Компонент `<Select>` нуждается во внутренней координации между дочерними `<Option>` — какой из них в фокусе, какой выбран. Передача всего этого состояния через пропсы порождает взрыв API:

```tsx
// ❌ Монолитный API: детали реализации наружу, разметку не поменять
<Select
  options={[{ label: 'A', value: 'a' }, { label: 'B', value: 'b' }]}
  selectedValue="a"
  onSelect={setValue}
  renderOption={opt => <span>{opt.label}</span>}
  showBorder
  maxHeight={300}
/>
```

### Паттерн

Разбейте компонент на родителя, который владеет состоянием, и дочерние компоненты, которые читают его через контекст:

```tsx
import { createContext, useContext, useState } from 'react';

type SelectContextValue = {
  selected: string;
  onSelect: (value: string) => void;
};

const SelectContext = createContext<SelectContextValue | null>(null);

function useSelectContext() {
  const ctx = useContext(SelectContext);
  if (!ctx) throw new Error('useSelectContext must be used inside <Select>');
  return ctx;
}

// Родитель владеет состоянием и логикой координации:
function Select({ children, defaultValue = '' }: {
  children: React.ReactNode;
  defaultValue?: string;
}) {
  const [selected, setSelected] = useState(defaultValue);
  return (
    <SelectContext.Provider value={{ selected, onSelect: setSelected }}>
      <div role="listbox">{children}</div>
    </SelectContext.Provider>
  );
}

// Дочерние компоненты потребляют контекст без prop drilling:
function Option({ value, children }: { value: string; children: React.ReactNode }) {
  const { selected, onSelect } = useSelectContext();
  return (
    <div
      role="option"
      aria-selected={selected === value}
      onClick={() => onSelect(value)}
      style={{ fontWeight: selected === value ? 'bold' : 'normal' }}
    >
      {children}
    </div>
  );
}

// Вложить суб-компоненты в пространство имён для удобства:
Select.Option = Option;
```

Потребитель полностью контролирует расположение элементов (layout) и компоновку:

```tsx
<Select defaultValue="react">
  <div className="header">Выберите фреймворк</div>
  <Select.Option value="react">React</Select.Option>
  <Select.Option value="vue">Vue</Select.Option>
  <div className="divider" />
  <Select.Option value="svelte">Svelte</Select.Option>
</Select>
```

### Когда использовать

- Семейства компонентов, где дочерним нужно разделять состояние без явной передачи пропсов
- Когда потребителям нужна свобода в разметке — они решают, где появятся дочерние элементы
- Классические примеры: `<Tabs>/<Tab>/<TabPanel>`, `<Accordion>/<AccordionItem>`, `<Menu>/<MenuItem>`

---

## Контролируемые и неконтролируемые компоненты

### Ключевое различие

**Контролируемый** компонент — тот, чьим состоянием владеет родитель: он передаёт текущее значение и обработчик изменения. **Неконтролируемый** компонент управляет своим состоянием сам. Родитель читает значение только когда оно нужно: через ref на узел DOM или при отправке формы. DOM — это Document Object Model, дерево объектов, из которого браузер рисует страницу.

```tsx
// КОНТРОЛИРУЕМЫЙ — родитель владеет значением:
function ControlledInput({ value, onChange }: {
  value: string;
  onChange: (v: string) => void;
}) {
  return <input value={value} onChange={e => onChange(e.target.value)} />;
}

// Использование — родитель является единственным источником истины:
function Form() {
  const [name, setName] = useState('');
  return <ControlledInput value={name} onChange={setName} />;
}
```

```tsx
// НЕКОНТРОЛИРУЕМЫЙ — компонент владеет значением, родитель читает через ref:
function UncontrolledInput({ defaultValue = '' }: { defaultValue?: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return <input ref={inputRef} defaultValue={defaultValue} />;
}

// Родитель читает значение только при сабмите — нет ре-рендера на каждый символ:
function Form() {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    console.log(inputRef.current?.value); // читаем по требованию
  }

  return (
    <form onSubmit={handleSubmit}>
      <input ref={inputRef} defaultValue="" />
      <button type="submit">Отправить</button>
    </form>
  );
}
```

### Когда какой использовать

| Контролируемый нужен, когда… | Неконтролируемый нужен, когда… |
|---|---|
| валидация идёт на каждый символ | форма простая и читается только при отправке |
| видимость полей зависит от условий | это `file input` — он всегда неконтролируемый |
| значение синхронизируется с внешним состоянием | вы подключаете стороннюю библиотеку, работающую с DOM |
| значение ставится программно | форма чувствительна к производительности, 1000+ полей |

### Компонент библиотеки, поддерживающий оба режима

```tsx
type InputProps = {
  // Контролируемый: value + onChange вместе
  value?: string;
  onChange?: (value: string) => void;
  // Неконтролируемый: defaultValue
  defaultValue?: string;
};

function Input({ value, onChange, defaultValue }: InputProps) {
  // Если value передан — контролируемый режим
  const isControlled = value !== undefined;

  const [internalValue, setInternalValue] = useState(defaultValue ?? '');
  const displayValue = isControlled ? value : internalValue;

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (!isControlled) setInternalValue(e.target.value);
    onChange?.(e.target.value);
  }

  return <input value={displayValue} onChange={handleChange} />;
}
```

Именно этот паттерн React использует для всех нативных элементов форм: `value` + `onChange` = контролируемый, `defaultValue` без `value` = неконтролируемый.

---

## Render Props

### Паттерн (исторический контекст)

Render props были основным механизмом переиспользования логики до хуков. Компонент принимает функцию как проп. Эта функция получает состояние и логику и возвращает JSX. JSX — это HTML-подобный синтаксис, на котором пишут компоненты React. Компонент сам решает, когда вызвать функцию.

```tsx
type RenderPropMousePosition = {
  render: (pos: { x: number; y: number }) => React.ReactNode;
};

class MouseTracker extends React.Component<RenderPropMousePosition> {
  state = { x: 0, y: 0 };

  handleMouseMove = (e: React.MouseEvent) => {
    this.setState({ x: e.clientX, y: e.clientY });
  };

  render() {
    return (
      <div onMouseMove={this.handleMouseMove}>
        {this.props.render(this.state)} {/* вызываем render-функцию */}
      </div>
    );
  }
}

// Использование:
<MouseTracker render={({ x, y }) => <p>Мышь: {x}, {y}</p>} />
```

### Почему хуки вытеснили render props

```tsx
// Render prop — добавляет лишний компонент в дерево, неудобная вложенность:
<DataFetcher
  url="/api/users"
  render={({ data, loading, error }) => {
    if (loading) return <Spinner />;
    if (error) return <Error message={error.message} />;
    return <UserList users={data} />;
  }}
/>

// Кастомный хук — та же логика, никаких компонентов-обёрток:
function UserList() {
  const { data, loading, error } = useFetch<User[]>('/api/users');
  if (loading) return <Spinner />;
  if (error) return <Error message={error.message} />;
  return <ul>{data?.map(u => <li key={u.id}>{u.name}</li>)}</ul>;
}
```

Хуки выносят ту же логику с состоянием, не добавляя уровней в дерево компонентов и без неудобного синтаксиса пропа `render`.

### Где render props встречаются в современном коде

Render props сохраняются там, где компоненту нужен **контроль над рендером** его потребителей:

```tsx
// Controller из react-hook-form — управляет жизненным циклом рендера поля:
<Controller
  name="email"
  control={control}
  render={({ field, fieldState }) => (
    <Input {...field} error={fieldState.error?.message} />
  )}
/>

// react-window — виртуализатор контролирует какие строки рендерить и когда:
<FixedSizeList height={600} itemCount={1000} itemSize={48} width="100%">
  {({ index, style }) => (
    <div style={style}>{items[index].name}</div>
  )}
</FixedSizeList>
```

В этих случаях библиотечный компонент внедряет пропсы в JSX потребителя во время рендера. `Controller` внедряет регистрацию поля, `FixedSizeList` — `style` с абсолютным позиционированием. Хуки сами по себе это не заменяют.

---

## Higher-Order Components (HOC)

### Паттерн

HOC — это функция, принимающая компонент и возвращающая новый компонент с дополнительным поведением:

```tsx
function withAuth<P extends { user: User }>(
  WrappedComponent: React.ComponentType<P>
) {
  return function WithAuthComponent(props: Omit<P, 'user'>) {
    const { user, isLoading } = useAuth();

    if (isLoading) return <Spinner />;
    if (!user) return <Navigate to="/login" />;

    return <WrappedComponent {...(props as P)} user={user} />;
  };
}

// Использование:
const ProtectedDashboard = withAuth(Dashboard);
```

### Почему хуки вытеснили HOC

```tsx
// HOC — оборачивает компонент, добавляет лишние узлы в DevTools-дерево,
// коллизии имён пропсов при нескольких HOC, внедряющих одноимённый проп:
const Enhanced = withAuth(withTheme(withRouter(Dashboard)));
// DevTools: WithAuthComponent > WithThemeComponent > WithRouterComponent > Dashboard

// Кастомный хук — та же внедрённая логика, компонент на одном уровне:
function Dashboard() {
  const { user } = useAuth();       // то же что withAuth
  const { theme } = useTheme();     // то же что withTheme
  const { params } = useRouter();   // то же что withRouter
  // ...
}
```

Проблемы HOC, которые решают хуки:
1. **Wrapper hell** — каждый HOC добавляет уровень компонента, видимый в DevTools
2. **Коллизии пропсов** — два HOC, внедряющих проп `data`, молча перезаписывают друг друга
3. **Пробрасывание ref** — HOC должны явно пробрасывать refs; хукам это не нужно
4. **Сложность типов** — типизация `Omit<P, 'injectedProp'>` пишется вручную и ничего не объясняет

### Когда HOC по-прежнему оправдан

```tsx
// Оборачивание жизненного цикла класс-компонентов (когда нельзя использовать хуки):
const withErrorBoundary = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback: React.ReactNode
) => {
  return class extends React.Component<P, { hasError: boolean }> {
    state = { hasError: false };
    static getDerivedStateFromError() { return { hasError: true }; }
    render() {
      if (this.state.hasError) return fallback;
      return <WrappedComponent {...this.props} />;
    }
  };
};
```

Error Boundary обязан быть класс-компонентом: хукового эквивалента `componentDidCatch` нет. Поэтому HOC-обёртка здесь оправдана. В остальных случаях выбирайте кастомные хуки.

---

## Error Boundaries

### Что это такое

Error Boundary — это класс-компоненты, перехватывающие JavaScript-ошибки в дереве дочерних компонентов во время фазы рендера, фазы коммита и конструкторов дочерних компонентов.

```tsx
class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error) {
    // Обновляем состояние — следующий рендер покажет fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Логируем в сервис отслеживания ошибок
    logErrorToService(error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}
```

### Что Error Boundary **перехватывает**

```txt
✓ Ошибки в фазе рендера: внутри return компонента
  или при вычислении JSX
✓ Ошибки в методах жизненного цикла: componentDidMount,
  componentDidUpdate
✓ Ошибки в конструкторах дочерних компонентов
```

### Что Error Boundary **не перехватывает**

```txt
✗ Обработчики событий — нужен try/catch внутри обработчика
✗ Асинхронный код — setTimeout, Promise, async/await
✗ Ошибки серверного рендеринга
✗ Ошибки в самом Error Boundary
```

```tsx
// ❌ Эту ошибку ErrorBoundary выше не поймает:
function Button() {
  function handleClick() {
    throw new Error('Ошибка обработчика события'); // вырывается за пределы boundary
  }
  return <button onClick={handleClick}>Нажми</button>;
}

// ✅ Ловим вручную:
function Button() {
  function handleClick() {
    try {
      riskyOperation();
    } catch (error) {
      setError(error); // сохраняем в состояние → рендерим UI ошибки
    }
  }
  return <button onClick={handleClick}>Нажми</button>;
}
```

### Гранулярное размещение boundary

```tsx
// ❌ Единственный boundary ловит всё — один сломанный виджет убивает всю страницу:
<ErrorBoundary fallback={<ErrorPage />}>
  <App />
</ErrorBoundary>

// ✅ Гранулярные boundary изолируют сбои:
function Dashboard() {
  return (
    <div>
      <ErrorBoundary fallback={<WidgetError name="Stats" />}>
        <StatsWidget />
      </ErrorBoundary>

      <ErrorBoundary fallback={<WidgetError name="Chart" />}>
        <RevenueChart />
      </ErrorBoundary>

      <ErrorBoundary fallback={<WidgetError name="Feed" />}>
        <ActivityFeed />
      </ErrorBoundary>
    </div>
  );
}
// Если RevenueChart бросает ошибку — только его слот показывает ошибку.
// Stats и Feed продолжают работать.
```

### Пакет react-error-boundary

Пакет `react-error-boundary` предоставляет переиспользуемый компонент `ErrorBoundary`, избавляющий от написания класс-компонента вручную:

```tsx
import { ErrorBoundary } from 'react-error-boundary';

function ErrorFallback({ error, resetErrorBoundary }: {
  error: Error;
  resetErrorBoundary: () => void;
}) {
  return (
    <div role="alert">
      <p>Что-то пошло не так:</p>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Попробовать снова</button>
    </div>
  );
}

<ErrorBoundary
  FallbackComponent={ErrorFallback}
  onError={(error, info) => logErrorToService(error, info)}
  onReset={() => resetAppState()}
>
  <App />
</ErrorBoundary>
```

---

## Порталы (Portals)

### Что это такое

Portal рендерит дочерний компонент в DOM-узел, находящийся вне корневого элемента React:

```tsx
import { createPortal } from 'react-dom';

function Modal({ children, isOpen }: { children: React.ReactNode; isOpen: boolean }) {
  if (!isOpen) return null;

  return createPortal(
    <div className="modal-overlay">
      <div className="modal-content">
        {children}
      </div>
    </div>,
    document.body  // рендерится в <body>, вне React-root
  );
}
```

### Зачем порталы нужны

Поместите модальное окно внутрь родителя с `overflow: hidden` или с собственным контекстом наложения (stacking context). Окно будет обрезано или окажется за другими элементами: CSS предка запирает его внутри себя. Портал вырывает окно из этих визуальных ограничений, но оставляет его в React-дереве.

```txt
React-дерево                  DOM-дерево
(события, контекст)           (то, что рисует браузер)
─────────────────────────     ────────────────────────────
<App>                         <body>
  <Dashboard>                   <div id="root">
    <Modal isOpen={true}>         <div id="main">...</div>
      <ConfirmDialog />         </div>
    </Modal>                    <div class="modal-overlay">
  </Dashboard>                    <div class="modal-content">
</App>                              <ConfirmDialog />
                                  </div>
                                </div>
                              </body>

React-дерево: Modal по-прежнему внутри Dashboard, поэтому контекст
и всплытие событий работают как обычно.
DOM-дерево: Modal рендерится прямо в <body>, ничто его не обрежет.
```

Ключевое свойство: **события по-прежнему всплывают по React-дереву**, а не по DOM-дереву. Клик внутри содержимого портала всплывает к `<Dashboard>` и `<App>` в React, хотя в DOM портал — сосед `<div id="root">`.

### Частые сценарии использования

```tsx
// Модальные окна и диалоги — выход из overflow:hidden и stacking context:
const modalRoot = document.getElementById('modal-root')!;
createPortal(<ModalContent />, modalRoot);

// Тултипы — позиционирование относительно вьюпорта, а не контейнера:
createPortal(<Tooltip text="Помощь" style={{ top: 100, left: 200 }} />, document.body);

// Уведомления/тосты — фиксированная позиция, независимо от прокрутки:
createPortal(<Toast message="Сохранено!" />, document.getElementById('toast-container')!);
```

### Порталы и серверный рендеринг (SSR)

При серверном рендеринге `document.body` недоступен. Поставьте на рендер портала защиту:

```tsx
function Modal({ children, isOpen }: { children: React.ReactNode; isOpen: boolean }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="modal-overlay">{children}</div>,
    document.body
  );
}
```

---

## Комбинирование паттернов

Эти паттерны не исключают друг друга. Реальная компонентная библиотека их комбинирует:

```tsx
// Dialog: Compound Components + Portal + Error Boundary:
function Dialog({ children, open }: { children: React.ReactNode; open: boolean }) {
  return (
    <ErrorBoundary fallback={<div>Ошибка рендера диалога</div>}>
      <Portal>
        {open && (
          <DialogContext.Provider value={{ onClose: () => {} }}>
            <div className="dialog-overlay">{children}</div>
          </DialogContext.Provider>
        )}
      </Portal>
    </ErrorBoundary>
  );
}

Dialog.Title = DialogTitle;
Dialog.Body = DialogBody;
Dialog.Footer = DialogFooter;

// Использование: потребитель сам решает, что где стоит
<Dialog open={isOpen}>
  <Dialog.Title>Подтверждение удаления</Dialog.Title>
  <Dialog.Body>Это действие нельзя отменить.</Dialog.Body>
  <Dialog.Footer>
    <Button variant="ghost" onClick={onClose}>Отмена</Button>
    <Button variant="danger" onClick={onConfirm}>Удалить</Button>
  </Dialog.Footer>
</Dialog>
```

---

## Типичные ошибки на интервью

**«В чём разница между Compound Components и Render Props?»**
Они дают потребителю разный вид контроля. Compound Components позволяют собрать UI — user interface, то, что видит пользователь, — из готовых суб-компонентов.

Для простого переиспользования логики оба паттерна вытеснены кастомными хуками. Но Compound Components остаются правильным выбором, когда настоящая цель — свобода потребителя в разметке.

| | Compound Components | Render Props |
|---|---|---|
| Как состояние доходит до детей | через контекст, неявно | передаётся в функцию-проп |
| Что контролирует потребитель | расположение: где что стоит | рендер каждого элемента |
| Что пишет потребитель | суб-компоненты внутри родителя | функцию, возвращающую JSX |

**«Могут ли Error Boundaries поймать асинхронные ошибки?»**
Нет. Ошибка, брошенная внутри `setTimeout`, `Promise.catch` или `async`-функции, происходит вне цикла рендера React. К моменту броска React уже вышел из рендеринга. Чтобы асинхронная ошибка дошла до Error Boundary, поймайте её вручную и запишите в состояние. React бросит её при следующем рендере, и boundary её поймает.

**«Когда использовать Portal вместо обычного рендера на месте?»**
Когда CSS предка делает рендер на месте визуально неправильным. Есть три типичных случая:

- `overflow: hidden` обрезает содержимое.
- Низкий `z-index` прячет его за соседями.
- CSS-трансформация создаёт новый контекст наложения.

Диалог внутри карточки с `overflow: hidden` будет обрезан. Портал рендерит его в `document.body`, где ни одно из этих ограничений не действует, и при этом оставляет его в React-дереве — для контекста и событий.

**«Почему HOC вышли из моды, если они прекрасно работают?»**
Они работают, но плохо компонуются. Издержек четыре, и у кастомного хука нет ни одной из них.

| Издержка HOC | С кастомным хуком |
|---|---|
| оборачивает компонент, из-за чего путаются трассировки в DevTools | компонента-обёртки нет вообще |
| два HOC с одноимённым пропом молча перезаписывают друг друга | результат — переменные, которые называет вызывающий код |
| `Omit<P, 'user'>` приходится писать руками | тип возврата выводится сам |
| `forwardRef` нужно добавлять явно | пробрасывать нечего |

**«Контролируемый или неконтролируемый инпут лучше?»**
Ни один не лучше сам по себе. Они оптимизированы под разные задачи.

Контролируемый инпут держит текущее значение в состоянии React, доступное синхронно. Это даёт мгновенную валидацию, условный рендер и программную установку значения. Плата — ре-рендер на каждый символ.

Неконтролируемый инпут этих ре-рендеров избегает и упрощает код, когда значение нужно только при отправке. React Hook Form внутри использует именно неконтролируемые инпуты. Так он получает лучшую производительность на больших формах: отдельные нажатия клавиш не попадают в цикл рендера React.
