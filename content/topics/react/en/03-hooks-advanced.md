# Advanced Hooks

## useMemo — real cost/benefit analysis

`useMemo` caches the result of a computation between renders. The cached value is reused as long as the dependencies haven't changed (compared with `Object.is`).

```tsx
const sorted = useMemo(
  () => [...items].sort((a, b) => a.name.localeCompare(b.name)),
  [items]
);
```

### What useMemo actually costs

`useMemo` is not free. On every render React must:
1. Retrieve the stored hook node from the linked list
2. Compare each dependency with `Object.is`
3. Either return the cached value or re-run the computation and store the new result

For cheap computations (filtering a 10-item array, simple arithmetic), the overhead of `useMemo` itself can **exceed the cost of just recomputing the value**. The React team has stated this explicitly — `useMemo` is for genuinely expensive computations and referential stability, not defensive programming.

```txt
WHEN useMemo HELPS:
  ✓ Computation takes measurable time (verified with React Profiler)
  ✓ The memoized value is used as a prop to a React.memo'd component
    and would otherwise cause it to re-render
  ✓ The memoized value is a dep of useEffect and would otherwise
    cause the effect to re-run every render

WHEN useMemo HURTS (or at best does nothing):
  ✗ Cheap computation (filtering < 100 items, simple math)
  ✗ The result is a primitive — primitives are compared by value,
    so referential stability is irrelevant
  ✗ The component re-renders rarely anyway
  ✗ Dependencies change on almost every render
    (the cached value is invalidated before it's reused)
```

### Measuring before memoizing

```tsx
// Before adding useMemo, measure:
console.time('sort');
const sorted = [...items].sort(...);
console.timeEnd('sort');

// If this logs "sort: 0.01ms", useMemo adds overhead, not savings.
// If it logs "sort: 12ms", useMemo is worth it.
```

The React team's heuristic: if you can't measure a visible performance problem with the React DevTools Profiler, `useMemo` is noise.

---

## useCallback — the same analysis, different output type

`useCallback(fn, deps)` is identical to `useMemo(() => fn, deps)` — it memoizes a function reference instead of a computed value.

```tsx
// These are equivalent:
const handleClick = useCallback(() => doSomething(id), [id]);
const handleClick = useMemo(() => () => doSomething(id), [id]);
```

### When useCallback actually matters

```tsx
// ❌ Pointless — Button is not memo'd, it re-renders regardless:
function Parent() {
  const handleClick = useCallback(() => setCount(c => c + 1), []);
  return <Button onClick={handleClick} />;
}

// ✅ Meaningful — Button is memo'd, stable ref prevents re-render:
const Button = React.memo(({ onClick }: { onClick: () => void }) => {
  return <button onClick={onClick}>Click</button>;
});

function Parent() {
  const handleClick = useCallback(() => setCount(c => c + 1), []);
  return <Button onClick={handleClick} />;
  // Without useCallback: new function reference → Button re-renders
  // With useCallback: same reference → Button skips re-render
}
```

`useCallback` is meaningful in exactly two scenarios:
1. The function is passed as a prop to a `React.memo`'d child
2. The function is a dependency of a `useEffect` or another `useMemo`/`useCallback`

In all other cases, `useCallback` adds overhead without benefit.

### The infinite loop trap

```tsx
// Classic mistake — effect dep on a function that changes every render:
function Component({ userId }: { userId: string }) {
  const fetchUser = async () => {          // new reference every render
    const user = await api.getUser(userId);
    setUser(user);
  };

  useEffect(() => {
    fetchUser();
  }, [fetchUser]); // → fetchUser changes → effect re-runs → fetchUser changes → ∞
}

// Fix: wrap in useCallback with correct deps:
const fetchUser = useCallback(async () => {
  const user = await api.getUser(userId);
  setUser(user);
}, [userId]); // stable ref; only re-creates when userId changes
```

---

## useRef — beyond DOM refs

`useRef` is commonly taught as "a way to get a DOM element." That's one use case. The deeper purpose: **a mutable container that persists across renders without triggering re-renders**.

```tsx
const ref = useRef(initialValue);
// ref is: { current: initialValue }
// - ref.current is mutable
// - mutating ref.current does NOT schedule a re-render
// - ref.current survives re-renders (the same object across the component's lifetime)
// - ref.current is NOT part of the render output (not captured in closures per render)
```

### Use case 1: accessing DOM nodes

```tsx
function AutoFocusInput() {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return <input ref={inputRef} />;
}
```

### Use case 2: storing the latest value without triggering re-renders

```tsx
// Pattern: keep the latest callback without staling effects
function useLatest<T>(value: T): React.RefObject<T> {
  const ref = useRef(value);
  // Synchronously update during render (safe — just assigning to ref.current)
  ref.current = value;
  return ref;
}

function Component({ onScroll }: { onScroll: (y: number) => void }) {
  const onScrollRef = useLatest(onScroll);

  useEffect(() => {
    const handler = () => onScrollRef.current(window.scrollY);
    window.addEventListener('scroll', handler);
    return () => window.removeEventListener('scroll', handler);
  }, []); // empty deps — effect runs once, but always calls the LATEST onScroll
}
```

This is the `useEffectEvent` pattern in disguise — React 19 formalizes it as a hook, but the ref trick is the underlying implementation concept.

### Use case 3: tracking previous values

```tsx
function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T | undefined>(undefined);

  useEffect(() => {
    ref.current = value; // runs after render, so ref.current holds the PREVIOUS value during render
  });

  return ref.current;
}

function Component({ count }: { count: number }) {
  const prevCount = usePrevious(count);
  return <div>Changed from {prevCount} to {count}</div>;
}
```

### Use case 4: instance variables (avoiding useState for non-render data)

```tsx
function VideoPlayer({ src }: { src: string }) {
  const playerRef = useRef<PlayerInstance | null>(null);

  // playerRef holds the player instance — it's not part of the render output,
  // and mutating it should NOT trigger a re-render.
  // Using useState for this would cause unnecessary re-renders on every init.
  useEffect(() => {
    playerRef.current = new PlayerInstance(src);
    return () => playerRef.current?.destroy();
  }, [src]);

  const handlePause = () => playerRef.current?.pause(); // imperative, no re-render

  return <button onClick={handlePause}>Pause</button>;
}
```

---

## useImperativeHandle — controlled parent-to-child imperative API

By default, when a parent holds a `ref` to a child, it gets the DOM node directly. `useImperativeHandle` lets the child component control exactly what the parent's `ref.current` exposes.

```tsx
interface VideoHandle {
  play: () => void;
  pause: () => void;
  seek: (seconds: number) => void;
}

// React 19+ — ref is just a prop:
function VideoPlayer(
  { src, ref }: { src: string; ref: React.Ref<VideoHandle> }
) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useImperativeHandle(ref, () => ({
    play: () => videoRef.current?.play(),
    pause: () => videoRef.current?.pause(),
    seek: (s) => { if (videoRef.current) videoRef.current.currentTime = s; },
  }), []); // deps: re-compute the handle object if these change

  return <video ref={videoRef} src={src} />;
}

// Parent:
function Page() {
  const videoRef = useRef<VideoHandle>(null);

  return (
    <>
      <VideoPlayer src="/video.mp4" ref={videoRef} />
      <button onClick={() => videoRef.current?.seek(30)}>Jump to 0:30</button>
    </>
  );
}
```

The parent cannot access `videoRef.current.play` unless the child explicitly exposes it via `useImperativeHandle`. The raw `<video>` DOM node is not accessible to the parent — the child has full encapsulation. This is the correct pattern for components like date pickers, rich text editors, and custom media players.

**When to use:** sparingly. Most component communication should flow through props and callbacks (React's data-down / events-up model). `useImperativeHandle` is for cases where a parent needs to trigger an imperative action (focus, scroll, play/pause) that doesn't fit the props model.

---

## useId — stable IDs across server and client

`useId` generates a unique string ID that is **stable across the server and client renders** — preventing hydration mismatches when components that need unique IDs are server-rendered.

```tsx
function FormField({ label }: { label: string }) {
  const id = useId();
  // id is something like ":r3:" — unique within the component tree,
  // stable across server and client, consistent across re-renders.

  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" />
    </div>
  );
}
```

**Why not `Math.random()` or a counter?** `Math.random()` generates different values on server and client → hydration mismatch → React error. A module-level counter is reset between server renders but not client renders (due to module caching differences). `useId` is internally derived from the component's position in the Fiber tree, which is identical on server and client.

**Generating multiple IDs from one call:**

```tsx
function DateRangePicker() {
  const id = useId();
  const startId = `${id}-start`;
  const endId = `${id}-end`;

  return (
    <>
      <label htmlFor={startId}>From</label>
      <input id={startId} type="date" />
      <label htmlFor={endId}>To</label>
      <input id={endId} type="date" />
    </>
  );
}
```

---

## Custom hooks — composition patterns

A custom hook is a function whose name starts with `use` and that may call other hooks. The `use` prefix is not decoration — the `eslint-plugin-react-hooks` linter treats functions starting with `use` as hooks and enforces the Rules of Hooks for them.

### Pattern 1: Extract and reuse stateful logic

```tsx
// Without custom hook — logic is tangled in the component:
function UserProfile({ userId }: { userId: string }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getUser(userId)
      .then(u => { if (!cancelled) { setUser(u); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(e); setLoading(false); } });
    return () => { cancelled = true; };
  }, [userId]);

  if (loading) return <Spinner />;
  if (error) return <Error message={error.message} />;
  return <div>{user?.name}</div>;
}

// With custom hook — logic is extracted and reusable:
function useUser(userId: string) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getUser(userId)
      .then(u => { if (!cancelled) { setUser(u); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(e); setLoading(false); } });
    return () => { cancelled = true; };
  }, [userId]);

  return { user, loading, error };
}

function UserProfile({ userId }: { userId: string }) {
  const { user, loading, error } = useUser(userId);
  if (loading) return <Spinner />;
  if (error) return <Error message={error.message} />;
  return <div>{user?.name}</div>;
}
```

### Pattern 2: Generic async hook

```tsx
type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error };

function useAsync<T>(
  asyncFn: () => Promise<T>,
  deps: React.DependencyList
): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: 'idle' });

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading' });
    asyncFn()
      .then(data => { if (!cancelled) setState({ status: 'success', data }); })
      .catch(error => { if (!cancelled) setState({ status: 'error', error }); });
    return () => { cancelled = true; };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  return state;
}

// Usage:
function Posts({ userId }: { userId: string }) {
  const state = useAsync(() => api.getPosts(userId), [userId]);
  if (state.status === 'loading') return <Spinner />;
  if (state.status === 'error') return <p>{state.error.message}</p>;
  if (state.status === 'success') return <PostList posts={state.data} />;
  return null;
}
```

### Pattern 3: Browser API abstraction

```tsx
function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(
    () => window.matchMedia(query).matches
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [query]);

  return matches;
}

function useLocalStorage<T>(key: string, initialValue: T) {
  const [stored, setStored] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setValue = useCallback((value: T | ((prev: T) => T)) => {
    setStored(prev => {
      const next = typeof value === 'function' ? (value as (p: T) => T)(prev) : value;
      localStorage.setItem(key, JSON.stringify(next));
      return next;
    });
  }, [key]);

  return [stored, setValue] as const;
}
```

### Pattern 4: Composing custom hooks

Custom hooks compose naturally — a hook can call other hooks, including other custom hooks:

```tsx
function useAuthenticatedUser() {
  const { data: session } = useSession();          // from next-auth or similar
  const userId = session?.user?.id;
  const userState = useAsync(
    () => userId ? api.getUser(userId) : Promise.resolve(null),
    [userId]
  );
  return userState;
}
```

### The naming convention is enforced

The `use` prefix causes the linter to treat the function as a hook and enforce:
- No conditional calls inside it
- No calls from non-hooks and non-components
- Exhaustive deps checking for any `useEffect`/`useMemo`/`useCallback` it calls

If you name a function `useSomething`, it MUST follow all hook rules even if it doesn't currently call any built-in hooks — because it might in the future, and the linter enforces it immediately.

---

## useDebugValue — for DevTools

```tsx
function useUser(userId: string) {
  const [user, setUser] = useState<User | null>(null);

  // In React DevTools, this hook will show "User: Alice (42)"
  // instead of just showing the raw state value.
  useDebugValue(user, u => `User: ${u?.name} (${userId})`);

  // ... fetch logic
  return user;
}
```

The second argument (formatter) is only called by DevTools — it is not called in production, so expensive formatting is safe to include.

---

## Common interview traps

**"What's the difference between useMemo and useCallback?"**
`useCallback(fn, deps)` is exactly `useMemo(() => fn, deps)` — they differ only in what they cache: a function vs a computed value. Both are about referential stability across renders.

**"Should I wrap everything in useMemo/useCallback for performance?"**
No. This is one of the most common over-engineering patterns in React codebases. `useMemo` and `useCallback` have their own overhead. They help only when: (1) the computation is measurably expensive, (2) the memoized value is passed to a `React.memo`'d child, or (3) it's a dependency of a `useEffect`. Default: no memoization. Add when profiling shows a real problem.

**"Can useRef hold a function?"**
Yes. A common pattern is storing event handlers in a ref to get the latest version without re-creating effects:

```tsx
const handlerRef = useRef(onData);
handlerRef.current = onData; // always latest
useEffect(() => {
  socket.on('data', (d) => handlerRef.current(d));
}, []); // socket setup runs once; handler is always current via ref
```

**"Why does useImperativeHandle need forwardRef in React < 19?"**
In React < 19, `ref` is not a regular prop — it is handled specially by React and is not passed through `props`. `forwardRef` is a wrapper that explicitly passes the parent's `ref` to the child, where `useImperativeHandle` can then intercept it. In React 19, `ref` is a regular prop and `forwardRef` is no longer needed.

**"When would you use useRef instead of useState?"**
When you need to store a value that the component uses internally but that should NOT trigger a re-render when it changes: timer IDs, animation frame IDs, WebSocket instances, previous render values, focus state for non-visual tracking. If a value change should update the UI → `useState`. If it should not → `useRef`.
