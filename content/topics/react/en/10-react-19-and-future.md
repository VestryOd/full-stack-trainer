# React 19 and the Future

## What React 19 actually shipped (stable, April 2024)

React 19 is a stable release. It does not break existing React 18 code — the upgrade is mostly additive. The headline changes are:

```txt
STABLE IN REACT 19:
  Actions (async transitions)
  useActionState (formerly useFormState)
  useFormStatus
  useOptimistic
  use() hook
  ref as a regular prop (no forwardRef needed)
  Server Components and Server Actions (framework-integrated)
  Improved error reporting (hydration errors show diffs)
  Document metadata (title, meta tags) in components
  Stylesheet and script loading APIs
  React Compiler (beta, opt-in)
```

---

## Actions — async transitions

React 18's `startTransition` only handled synchronous updates. The most common real-world pattern — submit a form, await a server response, update UI — had no first-class support.

React 19 extends transitions to support async functions. An **Action** is an async function passed to a transition:

```tsx
// React 18 — manual loading/error state management:
function UpdateUsername() {
  const [username, setUsername] = useState('');
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setIsPending(true);
    setError(null);
    try {
      await updateUsername(username);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsPending(false);
    }
  }

  return (/* ... */);
}

// React 19 — the transition handles pending/error automatically:
import { useTransition } from 'react';

function UpdateUsername() {
  const [username, setUsername] = useState('');
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    startTransition(async () => {
      const result = await updateUsername(username);
      if (result.error) {
        setError(result.error);
      }
    });
  }

  // isPending is true while the async transition is in flight
  return (/* ... */);
}
```

`startTransition` in React 19 correctly tracks the pending state of async functions — `isPending` stays true until the awaited work completes. In React 18, `isPending` would go false immediately after the synchronous part.

---

## useActionState

`useActionState` (called `useFormState` in React 18 canary) combines a reducer-like action with automatic pending/error tracking:

```tsx
import { useActionState } from 'react';

// The action: receives previous state + form data, returns new state:
async function submitForm(
  prevState: { error: string | null; success: boolean },
  formData: FormData
): Promise<{ error: string | null; success: boolean }> {
  const name = formData.get('name') as string;

  if (!name) {
    return { error: 'Name is required', success: false };
  }

  try {
    await createUser({ name });
    return { error: null, success: true };
  } catch {
    return { error: 'Server error', success: false };
  }
}

function CreateUserForm() {
  const [state, formAction, isPending] = useActionState(submitForm, {
    error: null,
    success: false,
  });

  return (
    <form action={formAction}>
      <input name="name" type="text" disabled={isPending} />
      {state.error && <p className="error">{state.error}</p>}
      {state.success && <p className="success">User created!</p>}
      <button type="submit" disabled={isPending}>
        {isPending ? 'Saving…' : 'Create'}
      </button>
    </form>
  );
}
```

The action is called with the **previous state** (like a reducer) and the `FormData`. The returned value becomes the new state. `isPending` is true while the action is running.

Key properties:
- Works with native HTML `<form action={...}>` — no `onSubmit` handler needed
- When used with Server Actions, works without JavaScript enabled (progressive enhancement)
- The action is called on the server when it's a Server Action, on the client when it's a regular function

---

## useFormStatus

`useFormStatus` reads the submission status of the parent `<form>`. This solves a specific problem: a submit button inside a form needs to know if the form is submitting, but adding `isPending` as a prop to every button is repetitive.

```tsx
import { useFormStatus } from 'react-dom';

// This component can live anywhere inside a <form>:
function SubmitButton() {
  const { pending, data, method, action } = useFormStatus();

  return (
    <button type="submit" disabled={pending}>
      {pending ? 'Saving…' : 'Save'}
    </button>
  );
}

// No props needed — it reads from the parent form context:
function ProfileForm() {
  return (
    <form action={updateProfile}>
      <input name="bio" />
      <SubmitButton />  {/* reads pending from the form above */}
    </form>
  );
}
```

`useFormStatus` only works **inside** a `<form>` element — it reads from the nearest parent form, not from its own component. If used outside a form, `pending` is always `false`.

The `data` field contains the `FormData` that was submitted — useful for showing optimistic previews of what was submitted while the request is in flight.

---

## useOptimistic

`useOptimistic` lets you show an optimistic (assumed-to-succeed) UI update while an async action is pending, then automatically revert to the real state when the action completes (or show the real result if it succeeds).

```tsx
import { useOptimistic } from 'react';

type Message = { id: string; text: string; sending?: boolean };

function MessageThread({ messages }: { messages: Message[] }) {
  const [optimisticMessages, addOptimisticMessage] = useOptimistic(
    messages,
    // Reducer: how to merge an optimistic update into current state:
    (currentMessages, newMessage: Message) => [
      ...currentMessages,
      { ...newMessage, sending: true },
    ]
  );

  async function sendMessage(formData: FormData) {
    const text = formData.get('text') as string;
    const tempMessage = { id: crypto.randomUUID(), text };

    // Show immediately — doesn't wait for the server:
    addOptimisticMessage(tempMessage);

    // Then actually send it:
    await postMessage(text);
    // When this resolves, React replaces the optimistic state
    // with the real messages from the server (via re-render with new props)
  }

  return (
    <div>
      {optimisticMessages.map(msg => (
        <div key={msg.id} style={{ opacity: msg.sending ? 0.5 : 1 }}>
          {msg.text}
          {msg.sending && ' (sending…)'}
        </div>
      ))}
      <form action={sendMessage}>
        <input name="text" />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
```

`useOptimistic` returns the optimistic state during a pending action and the real state otherwise. Crucially, if the action fails, the optimistic update is automatically discarded — React reverts to the original state passed as the first argument.

---

## The `use()` hook

`use()` is a new primitive that can read the value of a Promise or Context — and unlike all other hooks, it can be called conditionally:

```tsx
import { use, Suspense } from 'react';

// Reading a Promise (replaces async components in some contexts):
function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  // Suspends until the promise resolves — must be inside a Suspense boundary:
  const user = use(userPromise);
  return <h1>{user.name}</h1>;
}

function Page() {
  // The fetch is initiated in the Server Component / parent, passed as a prop:
  const userPromise = fetchUser(userId);

  return (
    <Suspense fallback={<Skeleton />}>
      <UserProfile userPromise={userPromise} />
    </Suspense>
  );
}
```

```tsx
// Reading Context (same as useContext, but can be conditional):
import { use } from 'react';

function Component({ show }: { show: boolean }) {
  if (!show) return null;

  // ✅ This is allowed — use() can be called after a conditional return:
  const theme = use(ThemeContext);
  return <div className={theme}>...</div>;
}
```

`use()` differs from `useContext` in one important way: it can be called inside loops and conditionals. This makes it more flexible than `useContext` for cases where you only sometimes need the context value. When passed a Promise, it integrates with Suspense — it suspends the component until the Promise resolves, exactly like `useSuspenseQuery` in React Query.

**The "pass the promise, not the data" pattern:**

```tsx
// Start fetching as early as possible (in the parent):
async function Page({ params }: { params: { id: string } }) {
  // Fetch is kicked off immediately, NOT awaited yet:
  const userPromise = getUser(params.id);    // returns Promise<User>
  const postsPromise = getPosts(params.id);  // returns Promise<Post[]>

  return (
    <div>
      <Suspense fallback={<UserSkeleton />}>
        <UserHeader promise={userPromise} />   {/* suspends on its own */}
      </Suspense>
      <Suspense fallback={<PostsSkeleton />}>
        <PostList promise={postsPromise} />    {/* suspends independently */}
      </Suspense>
    </div>
  );
}

function UserHeader({ promise }: { promise: Promise<User> }) {
  const user = use(promise); // suspends here until resolved
  return <h1>{user.name}</h1>;
}
```

Both fetches run in parallel. Neither waterfall is introduced because neither fetch is awaited before the other starts.

---

## ref as a regular prop (no more forwardRef)

In React 18, passing a `ref` to a function component required `React.forwardRef`:

```tsx
// React 18 — forwardRef required:
const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ placeholder, ...props }, ref) => (
    <input ref={ref} placeholder={placeholder} {...props} />
  )
);
Input.displayName = 'Input';
```

In React 19, `ref` is just a regular prop:

```tsx
// React 19 — ref is a regular prop:
function Input({ ref, placeholder, ...props }: InputProps & { ref?: React.Ref<HTMLInputElement> }) {
  return <input ref={ref} placeholder={placeholder} {...props} />;
}

// Or with the new shorthand (TypeScript inference handles it):
function Input({ ref, ...props }: React.ComponentProps<'input'>) {
  return <input ref={ref} {...props} />;
}
```

`forwardRef` still works in React 19 but is deprecated. React will log a warning in development if you use it.

---

## Document metadata in components

React 19 allows rendering `<title>`, `<meta>`, and `<link>` tags directly in components — React hoists them to `<head>` automatically:

```tsx
function BlogPost({ post }: { post: Post }) {
  return (
    <article>
      {/* These are hoisted to <head> by React: */}
      <title>{post.title} | My Blog</title>
      <meta name="description" content={post.excerpt} />
      <link rel="canonical" href={`https://blog.example.com/posts/${post.slug}`} />

      <h1>{post.title}</h1>
      <p>{post.content}</p>
    </article>
  );
}
```

This replaces the need for `react-helmet` / `next/head` in most cases. In Next.js App Router, the `generateMetadata` API remains the recommended approach (it integrates with streaming and SSR more deeply), but the native support makes it viable for simpler cases.

---

## React Compiler (beta)

React Compiler (previously called "React Forget") is an opt-in build-time compiler that **automatically adds memoization** to your components and hooks. It analyzes your code statically and inserts the equivalent of `useMemo` / `useCallback` / `React.memo` where the React rules of reactivity are satisfied.

```tsx
// You write this:
function TodoList({ todos, filter }: { todos: Todo[]; filter: string }) {
  const filtered = todos.filter(t => t.title.includes(filter));
  return <ul>{filtered.map(t => <li key={t.id}>{t.title}</li>)}</ul>;
}

// The compiler emits something equivalent to this:
function TodoList({ todos, filter }: { todos: Todo[]; filter: string }) {
  const filtered = useMemo(
    () => todos.filter(t => t.title.includes(filter)),
    [todos, filter]
  );
  return <ul>{filtered.map(t => <MemoizedLi key={t.id} todo={t} />)}</ul>;
}
```

The compiler only applies memoization where it can prove it's safe — it does not memoize if the component violates React's rules (mutating props, reading values outside of render, etc.).

### What the Compiler means for your code

```txt
WITH REACT COMPILER:
  ✓ useMemo / useCallback / React.memo become largely unnecessary
  ✓ No risk of "wrong memoization" (the compiler understands React's model)
  ✓ Performance improvements without manual optimization
  ✗ Still in beta — correctness edge cases are being discovered
  ✗ Requires your code to follow React's rules strictly
  ✗ Doesn't help with structural problems (state too high, unnecessary re-renders from architecture)
```

### Current status (as of React 19)

The Compiler is available as a Babel/SWC plugin (`babel-plugin-react-compiler`). Meta has been running it in production on Instagram since 2023. It is opt-in — you enable it project-wide or per-file with `'use memo'` directive.

```js
// babel.config.js:
module.exports = {
  plugins: [
    ['babel-plugin-react-compiler', {
      compilationMode: 'annotation', // only compile files with 'use memo'
    }],
  ],
};
```

---

## Stable vs experimental — where things stand

```txt
STABLE IN REACT 19 (use today):
  Actions / async transitions
  useActionState
  useFormStatus
  useOptimistic
  use() hook
  ref as prop
  Document metadata (<title>, <meta>, <link> hoisting)
  Stylesheet ordering (<link rel="stylesheet" precedence="...">)
  Script deduplication (<script async>)
  Server Components (via Next.js App Router, Remix, etc.)
  Server Actions (via Next.js)

BETA / OPT-IN (production-viable with caution):
  React Compiler — running in production at Meta, available as Babel plugin

EXPERIMENTAL / FUTURE:
  Activity (formerly Offscreen) — pre-render hidden UI, preserve state for hidden tabs
  React DevTools improvements for Server Components
  Taint API — prevent specific server data from crossing to client
    (db.user.create result should never be serializable to the client)
```

---

## Migration notes: React 18 → React 19

```tsx
// 1. useFormState → useActionState (import from 'react', not 'react-dom'):
// Before:
import { useFormState } from 'react-dom';
// After:
import { useActionState } from 'react';

// 2. ReactDOM.render → createRoot (already required in React 18, warned in 19):
// Before:
ReactDOM.render(<App />, document.getElementById('root'));
// After:
ReactDOM.createRoot(document.getElementById('root')!).render(<App />);

// 3. forwardRef — still works, but deprecation warning:
// Migrate gradually — forwardRef components work but show a dev warning.

// 4. String refs (very old) — removed entirely in React 19.
```

---

## Common interview traps

**"What is the difference between useActionState and useFormStatus?"**
`useActionState` manages the state returned by a form action — it holds the result (success/error data) and provides an `isPending` flag for the action. It wraps an action function and is used in the component that owns the form. `useFormStatus` reads the submission status of the **nearest parent `<form>`** — it's designed for a submit button or input that lives *inside* the form but doesn't own the action. They compose: `useActionState` provides the `action` prop to the form; `useFormStatus` reads that form's status from inside.

**"Can you use React 19 Actions without Server Actions?"**
Yes. Actions are just async functions passed to `startTransition` or `useActionState`. Server Actions are a specific kind of action where the function runs on the server (marked with `'use server'`). A regular async client-side function (calling an API with `fetch`) works identically from React's perspective — the pending state tracking and error handling work the same way.

**"What problem does useOptimistic solve that you couldn't solve before?"**
The pattern is not new — you could always keep optimistic state in `useState` and manually reset it on error. `useOptimistic` solves the ergonomics and correctness problem: it automatically ties the optimistic state to the lifecycle of the pending action. When the action completes (success or failure), the optimistic state is automatically replaced by the real state. With manual `useState`, you had to remember to reset it in every error path, and the timing could cause flicker if the real state update and your manual reset were out of sync.

**"What does React Compiler actually compile to?"**
The compiler emits regular React code with `useMemo`, `useCallback`, and memoized components inserted at the correct granularity. It uses React's rules of reactivity as a formal model — a value is "reactive" if it depends on props, state, or other reactive values. The compiler tracks which values are reactive and wraps computations that depend only on non-reactive inputs in `useMemo`. The output is valid React code that runs on any React 18+ runtime — the compiler is purely a build-time optimization, not a runtime change.

**"Why is `use()` allowed in conditionals when other hooks are not?"**
React's rule about not calling hooks conditionally exists because hooks are tracked by call order on the Fiber's hook linked list — inserting or removing a hook call from one render to the next would corrupt the list. `use()` is not a hook in this sense — it's a new React primitive that can suspend the component (throw a special value) and be resumed later. React does not track `use()` calls by order in the same way; instead, it re-executes the component from the top after resuming from suspension, so the call position can change. The Rules of Hooks do not apply to `use()`.
