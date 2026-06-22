# Паттерны и композиция

## Почему паттерны важны на уровне senior

Примитивный API React небольшой: компоненты, пропсы, состояние, контекст. Паттерны — это переиспользуемые ответы на повторяющиеся задачи: как делиться логикой, как давать потребителям контроль, как компоновать без связывания. На уровне senior ожидается, что ты узнаёшь, какой паттерн подходит задаче, и объясняешь, почему выбрал его, а не альтернативы.

---

## Составные компоненты (Compound Components)

### Проблема

Компонент `<Select>` нуждается во внутренней координации между дочерними `<Option>` — какой из них в фокусе, какой выбран. Передача всего этого состояния через пропсы порождает взрыв API:

```tsx
// ❌ Монолитный API — утечка деталей реализации, сложно кастомизировать layout:
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

Разбей компонент на родителя, владеющего состоянием, и дочерних, потребляющих его через контекст:

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

Потребитель полностью контролирует layout и компоновку:

```tsx
<Select defaultValue="react">
  <div className="header">Выбери фреймворк</div>
  <Select.Option value="react">React</Select.Option>
  <Select.Option value="vue">Vue</Select.Option>
  <div className="divider" />
  <Select.Option value="svelte">Svelte</Select.Option>
</Select>
```

### Когда использовать

- Семейства компонентов, где дочерним нужно разделять состояние без явной передачи пропсов
- Когда потребителям нужна гибкость layout — они контролируют где появляются дочерние
- Классические примеры: `<Tabs>/<Tab>/<TabPanel>`, `<Accordion>/<AccordionItem>`, `<Menu>/<MenuItem>`

---

## Контролируемые и неконтролируемые компоненты

### Ключевое различие

**Контролируемый** компонент — его состоянием владеет родитель: передаёт текущее значение и обработчик изменения. **Неконтролируемый** компонент управляет собственным состоянием внутри — родитель читает значение только когда нужно (через ref или при сабмите).

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

```txt
КОНТРОЛИРУЕМЫЙ                          НЕКОНТРОЛИРУЕМЫЙ
──────────────────────────────────────  ──────────────────────────────────────
Валидация на каждый символ              Простые формы с чтением только на сабмите
Условная видимость полей                File input (всегда неконтролируемый)
Синхронизация с внешним состоянием      Интеграция DOM-библиотек сторонних разработчиков
Программная установка значения          Формы с 1000+ полей (производительность)
```

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

Render props были основным механизмом переиспользования логики до хуков. Компонент принимает функцию как проп; функция получает состояние/логику и возвращает JSX. Компонент контролирует когда вызывать функцию.

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

Хуки извлекают ту же stateful-логику без добавления уровней в дерево компонентов и без неудобного синтаксиса пропа `render`.

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

В этих случаях библиотечный компонент должен внедрить пропсы (регистрацию поля, style с абсолютным позиционированием) в JSX потребителя во время рендера — паттерн, который хуки сами по себе не заменяют.

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
4. **Сложность типов** — типизация `Omit<P, 'injectedProp'>` — механический boilerplate

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

Error Boundary должен быть класс-компонентом (хукового эквивалента `componentDidCatch` нет), поэтому HOC-обёртка здесь оправдана. В остальных случаях предпочитай кастомные хуки.

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

### Что Error Boundary ПЕРЕХВАТЫВАЕТ

```txt
✓ Ошибки в фазе рендера (внутри return компонента / вычисления JSX)
✓ Ошибки в методах жизненного цикла (componentDidMount, componentDidUpdate)
✓ Ошибки в конструкторах дочерних компонентов
```

### Что Error Boundary НЕ ПЕРЕХВАТЫВАЕТ

```txt
✗ Обработчики событий — используй try/catch внутри обработчика
✗ Асинхронный код — ошибки в setTimeout, Promise, async/await
✗ Ошибки серверного рендеринга
✗ Ошибки в самом Error Boundary
```

```tsx
// ❌ Эта ошибка НЕ будет поймана ErrorBoundary выше:
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

Без портала модальное окно внутри родителя с `overflow: hidden` или контекстом наложения (stacking context) будет обрезано или скрыто за другими элементами — CSS-содержание его захватывает. Порталы вырываются из визуального содержания, оставаясь в React-дереве.

```txt
REACT-ДЕРЕВО (всплытие событий, контекст):  DOM-ДЕРЕВО (визуальный рендер):
<App>                                          <body>
  <Dashboard>                                    <div id="root">
    <Modal isOpen={true}>     ─────────────        <div id="main">...</div>
      <ConfirmDialog />         portal             </div>
    </Modal>                  ─────────────      <div class="modal-overlay">
  </Dashboard>                                     <div class="modal-content">
</App>                                               <ConfirmDialog />
                                                   </div>
                                                 </div>
                                               </body>

React-дерево: Modal всё ещё внутри Dashboard — контекст и всплытие событий работают нормально.
DOM-дерево: Modal рендерится прямо в <body> — никакого CSS-clipping.
```

Ключевое свойство: **события по-прежнему всплывают через React-дерево**, а не через DOM-дерево. Клик внутри контента портала всплывает к `<Dashboard>` и `<App>` в React, хотя в DOM портал — сосед `<div id="root">`.

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

### Порталы и SSR

`document.body` недоступен при серверном рендеринге. Защити рендер портала:

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

// Использование — потребитель контролирует layout, никакого взрыва пропсов:
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
Compound Components используют контекст для неявного разделения состояния между родителем и его потомками — потребители собирают UI из предоставленных суб-компонентов. Render Props вызывают функцию-проп для внедрения состояния в JSX потребителя во время рендера. Compound Components дают потребителям свободу layout; Render Props дают контроль над рендером каждого элемента. Оба паттерна в основном вытеснены кастомными хуками для случаев переиспользования логики, но Compound Components по-прежнему правильный паттерн когда реальная цель — гибкость layout для потребителей.

**«Могут ли Error Boundaries поймать асинхронные ошибки?»**
Нет. Ошибка, брошенная внутри `setTimeout`, `Promise.catch` или `async`-функции, выполняется вне цикла рендера React. К тому моменту как она бросается, React уже вернулся из рендеринга. Чтобы пробросить асинхронную ошибку через Error Boundary, нужно поймать её вручную и записать в состояние — React бросит её при следующем рендере, и boundary её поймает.

**«Когда использовать Portal вместо обычного рендера inline?»**
Когда CSS-содержание предка делает inline-рендер визуально неправильным: `overflow: hidden` обрезает контент, низкий `z-index` прячет его за соседями, или CSS-трансформация создаёт новый stacking context. Диалог внутри карточки с `overflow: hidden` будет обрезан. Портал рендерит его в `document.body` где ни одно из этих ограничений не применяется, оставляя его в React-дереве для контекста и событий.

**«Почему HOC вышли из моды, если они прекрасно работают?»**
HOC работают, но неудобно компонуются. Каждый HOC оборачивает компонент в новый, делая трассировки в DevTools запутанными. Несколько HOC, внедряющих одноимённый проп, молча перезаписывают друг друга. Типизация пропсов компонента минус внедряемый проп (`Omit<P, 'user'>`) требует механического TypeScript-boilerplate. `forwardRef` нужно добавлять явно. Кастомные хуки достигают того же переиспользования логики без этих издержек — вывод хука это просто переменные, явно именуемые вызывающим кодом.

**«Контролируемый или неконтролируемый инпут лучше?»**
Ни один не лучше категорически — они оптимизированы под разные задачи. Контролируемые инпуты делают текущее значение доступным синхронно в React-состоянии, обеспечивая мгновенную валидацию, условный рендер и программные обновления. Они перерисовываются на каждый символ. Неконтролируемые инпуты избегают ре-рендеров на каждый символ и упрощают код когда значение нужно только при сабмите. React Hook Form использует неконтролируемые инпуты внутри именно поэтому — достигает лучшей производительности на больших формах, обходя цикл рендера React для отдельных нажатий клавиш.
