# Patterns and Composition

## Why patterns matter at the senior level

React's primitive API is small: components, props, state, context. Patterns are reusable answers to recurring problems — how to share logic, how to give consumers control, how to compose without coupling. At the senior level you are expected to recognize which pattern fits a problem and explain why you chose it over alternatives.

---

## Compound Components

### The problem

A `<Select>` component needs internal coordination between `<Option>` children — which one is hovered, which one is selected. Passing all that state as props creates an explosion of API surface:

```tsx
// ❌ Monolithic API — leaks implementation details, hard to customize layout:
<Select
  options={[{ label: 'A', value: 'a' }, { label: 'B', value: 'b' }]}
  selectedValue="a"
  onSelect={setValue}
  renderOption={opt => <span>{opt.label}</span>}
  showBorder
  maxHeight={300}
/>
```

### The pattern

Split the component into a parent that owns state and children that consume it via context:

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

// Parent owns the state and coordination logic:
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

// Children consume context without prop drilling:
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

// Namespace the sub-components for discoverability:
Select.Option = Option;
```

Consumer has full control over layout and composition:

```tsx
<Select defaultValue="react">
  <div className="header">Choose a framework</div>
  <Select.Option value="react">React</Select.Option>
  <Select.Option value="vue">Vue</Select.Option>
  <div className="divider" />
  <Select.Option value="svelte">Svelte</Select.Option>
</Select>
```

### When to use

- Component families where children need to share state without explicit prop passing
- When consumers need layout flexibility — they control where children appear
- Classic examples: `<Tabs>/<Tab>/<TabPanel>`, `<Accordion>/<AccordionItem>`, `<Menu>/<MenuItem>`

---

## Controlled vs Uncontrolled Components

### The core distinction

A **controlled** component has its state owned by the parent: the parent passes the current value and a change handler. An **uncontrolled** component manages its own state internally. The parent reads the value only when it needs it — through a ref to the DOM node, or on submit. DOM is the Document Object Model, the tree of objects the browser builds from the page.

```tsx
// CONTROLLED — parent owns the value:
function ControlledInput({ value, onChange }: {
  value: string;
  onChange: (v: string) => void;
}) {
  return <input value={value} onChange={e => onChange(e.target.value)} />;
}

// Usage — parent is the single source of truth:
function Form() {
  const [name, setName] = useState('');
  return <ControlledInput value={name} onChange={setName} />;
}
```

```tsx
// UNCONTROLLED — component owns the value, parent reads via ref:
function UncontrolledInput({ defaultValue = '' }: { defaultValue?: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return <input ref={inputRef} defaultValue={defaultValue} />;
}

// Parent reads value only on submit — no re-render on each keystroke:
function Form() {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    console.log(inputRef.current?.value); // read on demand
  }

  return (
    <form onSubmit={handleSubmit}>
      <input ref={inputRef} defaultValue="" />
      <button type="submit">Submit</button>
    </form>
  );
}
```

### When to use which

| Reach for controlled when… | Reach for uncontrolled when… |
|---|---|
| you validate as the user types | the form is simple and read on submit only |
| field visibility is conditional | it is a file input — always uncontrolled |
| the value syncs to external state | you integrate a third-party DOM library |
| you set the value programmatically | the form is performance-sensitive, 1000+ fields |

### Building a library component that supports both

```tsx
type InputProps = {
  // Controlled: pass value + onChange together
  value?: string;
  onChange?: (value: string) => void;
  // Uncontrolled: pass defaultValue
  defaultValue?: string;
};

function Input({ value, onChange, defaultValue }: InputProps) {
  // If value is provided, we're in controlled mode
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

The pattern React itself uses for all native form elements: `value` + `onChange` = controlled, `defaultValue` without `value` = uncontrolled.

---

## Render Props

### The pattern (historical context)

Render props were the primary logic-sharing mechanism before hooks. A component accepts a function as a prop. That function receives the state and logic, and returns JSX. JSX is the HTML-like syntax React components are written in. The component decides when to call the function.

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
        {this.props.render(this.state)} {/* call the render function */}
      </div>
    );
  }
}

// Usage:
<MouseTracker render={({ x, y }) => <p>Mouse: {x}, {y}</p>} />
```

### Why hooks replaced render props

```tsx
// Render prop — creates extra component in the tree, awkward nesting:
<DataFetcher
  url="/api/users"
  render={({ data, loading, error }) => {
    if (loading) return <Spinner />;
    if (error) return <Error message={error.message} />;
    return <UserList users={data} />;
  }}
/>

// Custom hook — same logic, no wrapper component:
function UserList() {
  const { data, loading, error } = useFetch<User[]>('/api/users');
  if (loading) return <Spinner />;
  if (error) return <Error message={error.message} />;
  return <ul>{data?.map(u => <li key={u.id}>{u.name}</li>)}</ul>;
}
```

Hooks extract the same stateful logic without adding levels to the component tree and without the awkward `render` prop syntax.

### When render props still appear in modern code

Render props survive in cases where a component needs **render-time control** over its consumers:

```tsx
// react-hook-form's Controller — needs to manage the field's render lifecycle:
<Controller
  name="email"
  control={control}
  render={({ field, fieldState }) => (
    <Input {...field} error={fieldState.error?.message} />
  )}
/>

// react-window — virtualizer controls which rows render and when:
<FixedSizeList height={600} itemCount={1000} itemSize={48} width="100%">
  {({ index, style }) => (
    <div style={style}>{items[index].name}</div>
  )}
</FixedSizeList>
```

In both cases the library component injects props into the consumer's JSX at render time. `Controller` injects the field registration; `FixedSizeList` injects a `style` with absolute positioning. Hooks alone cannot replace that.

---

## Higher-Order Components (HOC)

### The pattern

An HOC is a function that takes a component and returns a new component with additional behavior:

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

// Usage:
const ProtectedDashboard = withAuth(Dashboard);
```

### Why hooks replaced HOCs

```tsx
// HOC — wraps the component, introduces extra nodes in the DevTools tree,
// prop name collisions if multiple HOCs inject the same prop:
const Enhanced = withAuth(withTheme(withRouter(Dashboard)));
// DevTools shows: WithAuthComponent > WithThemeComponent > WithRouterComponent > Dashboard

// Custom hook — same injected logic, component stays at one level:
function Dashboard() {
  const { user } = useAuth();       // same as withAuth
  const { theme } = useTheme();     // same as withTheme
  const { params } = useRouter();   // same as withRouter
  // ...
}
```

Problems HOCs introduce that hooks avoid:
1. **Wrapper hell** — every HOC adds a component level visible in DevTools
2. **Prop collision** — two HOCs injecting a `data` prop silently overwrite each other
3. **Ref forwarding** — HOCs must explicitly forward refs; hooks don't need to
4. **Type complexity** — typing `Omit<P, 'injectedProp'>` is mechanical boilerplate

### When HOCs still make sense today

```tsx
// Class component lifecycle wrapping (when class components can't use hooks):
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

Error Boundaries must be class components (there is no hook equivalent for `componentDidCatch`), so HOC-wrapping them is still valid. Outside of this case, prefer custom hooks.

---

## Error Boundaries

### What they are

Error Boundaries are class components that catch JavaScript errors in their child tree during the render phase, commit phase, and constructors of child components.

```tsx
class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error) {
    // Update state so the next render shows the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log to your error reporting service
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

### What Error Boundaries **do** catch

```txt
✓ Errors thrown during render, inside the component's
  return or while JSX is evaluated
✓ Errors in lifecycle methods: componentDidMount,
  componentDidUpdate
✓ Errors in the constructors of child components
```

### What Error Boundaries **do not** catch

```txt
✗ Event handlers — use try/catch inside the handler
✗ Async code — setTimeout, Promises, async/await
✗ Server-side rendering errors
✗ Errors in the Error Boundary itself
```

```tsx
// ❌ This error will NOT be caught by an ErrorBoundary above:
function Button() {
  function handleClick() {
    throw new Error('Event handler error'); // escapes the boundary
  }
  return <button onClick={handleClick}>Click</button>;
}

// ✅ Catch it manually:
function Button() {
  function handleClick() {
    try {
      riskyOperation();
    } catch (error) {
      setError(error); // store in state → render an error UI
    }
  }
  return <button onClick={handleClick}>Click</button>;
}
```

### Granular boundary placement

```tsx
// ❌ Single boundary catches everything — one broken widget kills the whole page:
<ErrorBoundary fallback={<ErrorPage />}>
  <App />
</ErrorBoundary>

// ✅ Granular boundaries isolate failures:
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
// If RevenueChart throws, only its slot shows the error — Stats and Feed still work.
```

### react-error-boundary package

The `react-error-boundary` package provides a reusable `ErrorBoundary` component that avoids writing a class component yourself:

```tsx
import { ErrorBoundary } from 'react-error-boundary';

function ErrorFallback({ error, resetErrorBoundary }: {
  error: Error;
  resetErrorBoundary: () => void;
}) {
  return (
    <div role="alert">
      <p>Something went wrong:</p>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try again</button>
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

## Portals

### What they are

A Portal renders a child component into a DOM node that sits outside the React root element:

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
    document.body  // renders into <body>, outside the React root
  );
}
```

### Why portals exist

Put a modal inside a parent with `overflow: hidden`, or inside a z-index stacking context. It will be clipped, or hidden behind other elements. The ancestor's CSS locks it in. A portal frees the modal from those visual limits while keeping the component in the React tree.

```txt
React tree                    DOM tree
(events, context)             (what the browser paints)
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

React tree: Modal is still inside Dashboard, so context and
event bubbling work normally.
DOM tree: Modal renders straight into <body>, so no CSS clips it.
```

Key property: **events still bubble through the React tree**, not the DOM tree. A click inside the portal's content bubbles to `<Dashboard>` and `<App>` in React even though in the DOM it's a sibling of `<div id="root">`.

### Common use cases

```tsx
// Modals and dialogs — escape overflow:hidden and stacking contexts:
const modalRoot = document.getElementById('modal-root')!;
createPortal(<ModalContent />, modalRoot);

// Tooltips — need to position relative to viewport, not a container:
createPortal(<Tooltip text="Help" style={{ top: 100, left: 200 }} />, document.body);

// Notifications/toasts — fixed position, independent of scroll:
createPortal(<Toast message="Saved!" />, document.getElementById('toast-container')!);
```

### Portals and SSR

`document.body` is not available during server-side rendering. Guard portal rendering:

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

## Combining patterns

These patterns are not mutually exclusive. A real component library combines them:

```tsx
// Dialog combining Compound Components + Portal + Error Boundary:
function Dialog({ children, open }: { children: React.ReactNode; open: boolean }) {
  return (
    <ErrorBoundary fallback={<div>Dialog failed to render</div>}>
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

// Usage — consumer controls layout, no prop explosion:
<Dialog open={isOpen}>
  <Dialog.Title>Confirm deletion</Dialog.Title>
  <Dialog.Body>This action cannot be undone.</Dialog.Body>
  <Dialog.Footer>
    <Button variant="ghost" onClick={onClose}>Cancel</Button>
    <Button variant="danger" onClick={onConfirm}>Delete</Button>
  </Dialog.Footer>
</Dialog>
```

---

## Common interview traps

**"What's the difference between Compound Components and Render Props?"**
They hand the consumer a different kind of control. Compound Components let the consumer assemble the UI — the user interface, what the reader sees on screen — out of provided sub-components.

Custom hooks have largely replaced both patterns for plain logic sharing. But Compound Components stay the right choice when layout freedom for the consumer is the actual goal.

| | Compound Components | Render Props |
|---|---|---|
| How state reaches children | through context, implicitly | passed into a function prop |
| What the consumer controls | the layout: where each part goes | the rendering of each item |
| Consumer writes | sub-components inside the parent | a function that returns JSX |

**"Can Error Boundaries catch async errors?"**
No. An error thrown inside a `setTimeout`, a `Promise.catch`, or an `async` function runs outside the React render cycle. By the time it throws, React has already returned from rendering. To surface an async error through an Error Boundary, catch it manually and put it into state. React then throws it during the next render, and the boundary catches it there.

**"When would you use a Portal over just rendering inline?"**
When an ancestor's CSS makes inline rendering visually wrong. Three shapes of that:

- `overflow: hidden` clips the content.
- A low `z-index` hides it behind its siblings.
- A CSS transform creates a new stacking context.

A dialog inside a card with `overflow: hidden` will be clipped. A portal renders it in `document.body`, where none of those constraints apply, and it stays in the React tree for context and events.

**"Why did HOCs fall out of favor if they work perfectly fine?"**
They work, but they compose awkwardly. Four costs add up, and a custom hook has none of them.

| HOC cost | With a custom hook |
|---|---|
| wraps the component, so DevTools traces get confusing | no wrapper component at all |
| two HOCs injecting the same prop name overwrite each other | outputs are variables named by the caller |
| `Omit<P, 'user'>` boilerplate to type the injected props away | the return type is inferred |
| `forwardRef` has to be added by hand | nothing to forward |

**"Is a controlled or uncontrolled input better?"**
Neither is categorically better. They optimize for different things.

A controlled input keeps the current value in React state, available synchronously. That enables immediate validation, conditional rendering and programmatic updates. The cost is a re-render on every keystroke.

An uncontrolled input avoids those re-renders and keeps the code simpler when you only need the value on submit. React Hook Form uses uncontrolled inputs internally for exactly this reason. It gets better performance on large forms by keeping individual keystrokes out of the React render cycle.
