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

A **controlled** component has its state owned by the parent — the parent passes the current value and a change handler. An **uncontrolled** component manages its own state internally — the parent reads the value only when needed (via ref or on submit).

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

```txt
CONTROLLED                              UNCONTROLLED
──────────────────────────────────────  ──────────────────────────────────────
Instant validation as user types        Simple forms with submit-only reads
Conditional field visibility            File inputs (always uncontrolled)
Syncing value to external state         Integrating third-party DOM libraries
Programmatically setting the value      Performance-sensitive forms (1000+ fields)
```

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

Render props were the primary logic-sharing mechanism before hooks. A component accepts a function as a prop; that function receives state/logic and returns JSX. The component controls when to call the function.

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

In these cases the library component needs to inject props (field registration, style with absolute positioning) into the consumer's JSX at render time — a pattern hooks alone can't replace.

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

### What Error Boundaries DO catch

```txt
✓ Errors thrown during render (inside component return / JSX evaluation)
✓ Errors in lifecycle methods (componentDidMount, componentDidUpdate)
✓ Errors in constructors of child components
```

### What Error Boundaries DO NOT catch

```txt
✗ Event handlers — use try/catch inside the handler
✗ Async code — errors in setTimeout, Promises, async/await
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

A Portal renders a child component into a DOM node that exists outside the React root element:

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

Without a portal, a modal inside a parent with `overflow: hidden` or a z-index stacking context will be clipped or hidden behind other elements — CSS containment traps it. Portals escape the visual containment while keeping the component in the React tree.

```txt
REACT TREE (event bubbling, context):       DOM TREE (visual rendering):
<App>                                        <body>
  <Dashboard>                                  <div id="root">
    <Modal isOpen={true}>     ─────────────      <div id="main">...</div>
      <ConfirmDialog />         portal           </div>
    </Modal>                  ─────────────    <div class="modal-overlay">
  </Dashboard>                                   <div class="modal-content">
</App>                                             <ConfirmDialog />
                                                 </div>
                                               </div>
                                             </body>

React tree: Modal is still inside Dashboard — context and event bubbling work normally.
DOM tree: Modal renders directly in <body> — no CSS clipping.
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
Compound Components use context to share state implicitly between a parent and its children — consumers assemble the UI from provided sub-components. Render Props call a function prop to inject state into consumer JSX at render time. Compound Components give consumers layout freedom; Render Props give consumers rendering control per-item. Both were largely superseded by custom hooks for the logic-sharing use case, but Compound Components remain the right pattern when consumer layout flexibility is the actual goal.

**"Can Error Boundaries catch async errors?"**
No. An error thrown inside a `setTimeout`, a `Promise.catch`, or an `async` function runs outside the React render cycle. By the time it throws, React has already returned from rendering. To surface an async error through an Error Boundary, you must catch it manually and set it into state — React will then throw it during the next render, which the boundary will catch.

**"When would you use a Portal over just rendering inline?"**
When CSS containment of an ancestor makes inline rendering visually wrong: `overflow: hidden` clips the content, a low `z-index` hides it behind siblings, or a CSS transform creates a new stacking context. A dialog inside a card with `overflow: hidden` will be clipped. A portal renders it in `document.body` where none of those constraints apply, while keeping it in the React tree for context and events.

**"Why did HOCs fall out of favor if they work perfectly fine?"**
HOCs work, but they compose awkwardly. Each HOC wraps the component in a new component, making DevTools traces confusing. Multiple HOCs injecting the same prop name silently overwrite each other. Typing the component props minus the injected props (`Omit<P, 'user'>`) requires mechanical TypeScript boilerplate. `forwardRef` must be added explicitly. Custom hooks achieve the same logic reuse without any of these costs — the hook's output is just variables, named explicitly by the caller.

**"Is a controlled or uncontrolled input better?"**
Neither is categorically better — they optimize for different things. Controlled inputs make the current value available synchronously in React state, enabling immediate validation, conditional rendering, and programmatic updates. They re-render on every keystroke. Uncontrolled inputs avoid the keystroke re-renders and simplify code when you only need the value on submit. React Hook Form uses uncontrolled inputs internally for this reason — it achieves better performance on large forms by bypassing the React render cycle for individual keystrokes.
