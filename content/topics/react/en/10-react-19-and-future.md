# React 19 and the Future

## What React 19 actually shipped (stable, December 2024)

React 19.0 went stable on 5 December 2024. The release candidate and the upgrade guide came earlier, on 25 April 2024 — that April date is often mistaken for the stable release. React 19 does not break existing React 18 code; the upgrade is mostly additive. The headline changes:

```txt
Stable in React 19
  Actions (async transitions)
  useActionState (formerly useFormState)
  useFormStatus
  useOptimistic
  use() hook
  ref as a regular prop (no forwardRef needed)
  Server Components and Server Actions
    (integrated by the framework)
  Better error reporting: hydration errors show a diff
  Document metadata (title, meta tags) in components
  Stylesheet and script loading APIs
```

React Compiler is not part of React 19 itself. It is a separate build-time
package, and it reached version 1.0 on 7 October 2025.

---

## Actions — async transitions

React 18's `startTransition` only handled synchronous updates. The most common real-world pattern had no first-class support: submit a form, await a server response, update the UI. UI here means user interface — what the person on the other side of the screen sees.

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

`useFormStatus` reads the submission status of the parent `<form>`. It solves one specific problem. A submit button inside a form needs to know whether the form is submitting. Passing `isPending` as a prop to every such button is repetitive.

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

The `data` field contains the `FormData` that was submitted. That is useful for showing an optimistic preview of the submitted values while the request is still running.

---

## useOptimistic

`useOptimistic` shows an update as though it had already succeeded, while the async action is still pending. When the action finishes, React replaces that guess with the real state. If the action failed, the guess is discarded.

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
type WithRef = InputProps & { ref?: React.Ref<HTMLInputElement> };

function Input({ ref, placeholder, ...props }: WithRef) {
  return <input ref={ref} placeholder={placeholder} {...props} />;
}

// Or with the new shorthand (TypeScript inference handles it):
function Input({ ref, ...props }: React.ComponentProps<'input'>) {
  return <input ref={ref} {...props} />;
}
```

`forwardRef` still works in React 19, and as of React 19.2 it is **not** deprecated. The API reference says it "is no longer necessary" and "will be deprecated in a future release". There is no development warning for using it today.

What *is* deprecated, with a warning, is reading `ref` off an element — `element.ref`. That is a different thing, and the two are easy to confuse. A codemod exists for the migration:

```bash
npx codemod react/19/remove-forward-ref --target ./src
```

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

This replaces `react-helmet` and `next/head` in most cases. In the Next.js App Router, `generateMetadata` is still the recommended API. It integrates more deeply with streaming and with SSR — server-side rendering, where the HTML is produced on the server. But the native support is now enough for simpler cases.

---

## React Compiler (1.0, opt-in)

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

The compiler only applies memoization where it can prove it is safe. It does not memoize a component that breaks React's rules — mutating props, reading values outside of render, and so on.

### What the Compiler means for your code

```txt
With React Compiler
  ✓ useMemo / useCallback / React.memo become
    largely unnecessary
  ✓ No risk of "wrong memoization" — the compiler
    understands React's model
  ✓ Faster code without manual optimization
  ✗ You still have to add and configure it per project
  ✗ Requires your code to follow React's rules strictly
  ✗ Doesn't help with structural problems: state living
    too high, re-renders caused by architecture
```

### Current status (React Compiler 1.0, October 2025)

The Compiler shipped 1.0 on 7 October 2025, after a beta in October 2024. It is a Babel plugin, `babel-plugin-react-compiler`, and it also runs through SWC — the Speedy Web Compiler, the Rust-based build tool Next.js uses. Meta has been running it in production on Instagram since 2023.

For an existing app it is still opt-in. You install the plugin and turn it on, either project-wide or per file with the `'use memo'` directive. New apps can start with it enabled. Expo ships it on by default from version 54 of its toolkit, and Vite and Next.js offer compiler-enabled templates. The compiler-powered lint rules are in the `recommended` preset of `eslint-plugin-react-hooks`.

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
Stable in React 19.0 — use today
  Actions / async transitions
  useActionState
  useFormStatus
  useOptimistic
  use() hook
  ref as prop
  Document metadata: <title>, <meta>, <link> hoisting
  Stylesheet ordering:
    <link rel="stylesheet" precedence="...">
  Script deduplication: <script async>
  Server Components (Next.js App Router, Remix, ...)
  Server Actions (via Next.js)

Stable in React 19.2 — October 2025
  <Activity> (formerly Offscreen) — hide UI and keep
    the state of its children
  useEffectEvent — pull non-reactive logic out of an Effect
  cacheSignal — tells server code when a cache() lifetime
    is over, so it can abort work
  Performance Tracks in Chrome DevTools:
    Scheduler and Components
  Partial pre-rendering: prerender() plus resume()

Stable, but shipped separately from React itself
  React Compiler 1.0 — a build-time package you add
    to a project yourself

Experimental / future
  React DevTools improvements for Server Components
  Taint API — stop specific server data reaching the client
    (a db.user.create result must never be serializable)
```

`<Activity>` in React 19.2 supports two modes:

- `hidden` — hides the children, unmounts their effects, and defers their updates until React has nothing else to work on.
- `visible` — shows the children, mounts their effects, and processes updates normally.

More modes are planned.

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

// 3. forwardRef — still works, and is not deprecated as of 19.2.
// Migrate when convenient; there is no dev warning for using it.
// Codemod: npx codemod react/19/remove-forward-ref --target ./src

// 4. String refs (very old) — removed entirely in React 19.
```

---

## Common interview traps

**"What is the difference between useActionState and useFormStatus?"**
One owns the action, the other only reads the form it sits in.

| | `useActionState` | `useFormStatus` |
|---|---|---|
| Lives in | the component that owns the form | any component *inside* the form |
| Gives you | the action's result, plus `isPending` | `pending`, `data`, `method`, `action` |
| Reads from | the action it wraps | the nearest parent `<form>` |

They compose. `useActionState` supplies the `action` prop to the form, and `useFormStatus` reads that same form's status from inside a child.

**"Can you use React 19 Actions without Server Actions?"**
Yes. Actions are just async functions passed to `startTransition` or `useActionState`. Server Actions are one specific kind of action: the function is marked `'use server'` and runs on the server.

A plain async client-side function that calls an API with `fetch` behaves identically from React's point of view. Pending-state tracking and error handling work the same way.

```tsx
// A client-side Action — no 'use server' anywhere:
async function saveTitle(prev: string, formData: FormData) {
  const title = formData.get('title') as string;
  const res = await fetch('/api/title', { method: 'POST', body: title });
  return res.ok ? title : prev;   // the return value becomes the new state
}
```

**"What problem does useOptimistic solve that you couldn't solve before?"**
Nothing that was impossible — the pattern is old. You could always hold optimistic state in `useState` and reset it by hand on error.

What `useOptimistic` fixes is ergonomics and correctness. It ties the optimistic state to the lifecycle of the pending action, so the real state takes over automatically when the action finishes.

| | Manual `useState` | `useOptimistic` |
|---|---|---|
| Reset after the action | you write it, in every error path | automatic |
| Tied to the action's lifecycle | no | yes |
| Flicker risk | yes, if the reset and the real update desync | no |

**"What does React Compiler actually compile to?"**
Regular React code, with `useMemo`, `useCallback` and memoized components inserted at the right granularity.

It uses React's rules of reactivity as a formal model. A value is "reactive" if it depends on props, on state, or on other reactive values. The compiler tracks which values are reactive, and wraps computations whose inputs are all non-reactive in `useMemo`. The output is valid React code that runs on any React 18 or newer runtime. The compiler is purely a build-time optimization, not a runtime change.

**"Why is `use()` allowed in conditionals when other hooks are not?"**
Because `use()` is not tracked by call order, and ordinary hooks are.

```txt
Hooks are found by position in the list, not by name:

  render 1:  [1] useState   [2] useEffect   [3] useMemo
  render 2:  [1] useState   [2] useMemo     ← useEffect skipped
                             ↑ React hands useEffect's
                               state to useMemo
```

Hooks live on a linked list attached to the Fiber, and React finds each one by its position in that list. Insert or remove a hook call between two renders, and every position after it shifts — the list is corrupted. That is the whole reason for the rule.

`use()` is not a hook in that sense. It is a primitive that can suspend the component by throwing a special value, and be resumed later. After resuming, React re-executes the component from the top, so the call position is allowed to change. The Rules of Hooks do not apply to `use()`.
