# React 19 и будущее

## Что React 19 действительно выпустил (стабильно, апрель 2024)

React 19 — стабильный релиз. Он не ломает существующий код React 18 — обновление преимущественно аддитивное. Ключевые изменения:

```txt
СТАБИЛЬНО В REACT 19:
  Actions (асинхронные переходы)
  useActionState (ранее useFormState)
  useFormStatus
  useOptimistic
  хук use()
  ref как обычный проп (forwardRef больше не нужен)
  Server Components и Server Actions (интеграция с фреймворком)
  Улучшенные сообщения об ошибках (hydration-ошибки показывают diff)
  Метаданные документа (title, meta-теги) в компонентах
  API загрузки стилей и скриптов
  React Compiler (бета, opt-in)
```

---

## Actions — асинхронные переходы

`startTransition` в React 18 работал только с синхронными обновлениями. Самый распространённый реальный паттерн — отправить форму, дождаться ответа сервера, обновить UI — не имел первоклассной поддержки.

React 19 расширяет переходы для поддержки async-функций. **Action** — это async-функция, переданная в переход:

```tsx
// React 18 — ручное управление состоянием загрузки/ошибки:
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

// React 19 — переход автоматически обрабатывает pending/error:
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

  // isPending остаётся true пока async-переход выполняется
  return (/* ... */);
}
```

`startTransition` в React 19 корректно отслеживает pending-состояние async-функций — `isPending` остаётся true до завершения ожидаемой работы. В React 18 `isPending` сразу становился false после синхронной части.

---

## useActionState

`useActionState` (в React 18 canary назывался `useFormState`) объединяет редьюсер-подобный экшн с автоматическим отслеживанием pending/error:

```tsx
import { useActionState } from 'react';

// Экшн: получает предыдущее состояние + данные формы, возвращает новое состояние:
async function submitForm(
  prevState: { error: string | null; success: boolean },
  formData: FormData
): Promise<{ error: string | null; success: boolean }> {
  const name = formData.get('name') as string;

  if (!name) {
    return { error: 'Имя обязательно', success: false };
  }

  try {
    await createUser({ name });
    return { error: null, success: true };
  } catch {
    return { error: 'Ошибка сервера', success: false };
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
      {state.success && <p className="success">Пользователь создан!</p>}
      <button type="submit" disabled={isPending}>
        {isPending ? 'Сохранение…' : 'Создать'}
      </button>
    </form>
  );
}
```

Экшн вызывается с **предыдущим состоянием** (как редьюсер) и `FormData`. Возвращаемое значение становится новым состоянием. `isPending` равен true пока экшн выполняется.

Ключевые свойства:
- Работает с нативным HTML `<form action={...}>` — обработчик `onSubmit` не нужен
- При использовании с Server Actions работает без включённого JavaScript (прогрессивное улучшение)
- Экшн вызывается на сервере если это Server Action, на клиенте если обычная функция

---

## useFormStatus

`useFormStatus` читает статус отправки родительского `<form>`. Он решает конкретную задачу: кнопка отправки внутри формы должна знать идёт ли отправка, но передавать `isPending` как проп в каждую кнопку — это повторение.

```tsx
import { useFormStatus } from 'react-dom';

// Этот компонент может находиться где угодно внутри <form>:
function SubmitButton() {
  const { pending, data, method, action } = useFormStatus();

  return (
    <button type="submit" disabled={pending}>
      {pending ? 'Сохранение…' : 'Сохранить'}
    </button>
  );
}

// Никаких пропсов не нужно — читает из контекста родительской формы:
function ProfileForm() {
  return (
    <form action={updateProfile}>
      <input name="bio" />
      <SubmitButton />  {/* читает pending из формы выше */}
    </form>
  );
}
```

`useFormStatus` работает только **внутри** элемента `<form>` — читает из ближайшей родительской формы, а не из собственного компонента. При использовании вне формы `pending` всегда `false`.

Поле `data` содержит `FormData`, которые были отправлены — полезно для показа оптимистичных превью того, что было отправлено, пока запрос в полёте.

---

## useOptimistic

`useOptimistic` позволяет показывать оптимистичное (предполагаемое успешным) обновление UI пока async-экшн в ожидании, а затем автоматически откатиться к реальному состоянию когда экшн завершается (или показать реальный результат при успехе).

```tsx
import { useOptimistic } from 'react';

type Message = { id: string; text: string; sending?: boolean };

function MessageThread({ messages }: { messages: Message[] }) {
  const [optimisticMessages, addOptimisticMessage] = useOptimistic(
    messages,
    // Редьюсер: как объединить оптимистичное обновление с текущим состоянием:
    (currentMessages, newMessage: Message) => [
      ...currentMessages,
      { ...newMessage, sending: true },
    ]
  );

  async function sendMessage(formData: FormData) {
    const text = formData.get('text') as string;
    const tempMessage = { id: crypto.randomUUID(), text };

    // Показываем немедленно — не ждём сервер:
    addOptimisticMessage(tempMessage);

    // Затем фактически отправляем:
    await postMessage(text);
    // При resolve React заменяет оптимистичное состояние
    // реальными сообщениями с сервера (через ре-рендер с новыми пропсами)
  }

  return (
    <div>
      {optimisticMessages.map(msg => (
        <div key={msg.id} style={{ opacity: msg.sending ? 0.5 : 1 }}>
          {msg.text}
          {msg.sending && ' (отправляется…)'}
        </div>
      ))}
      <form action={sendMessage}>
        <input name="text" />
        <button type="submit">Отправить</button>
      </form>
    </div>
  );
}
```

`useOptimistic` возвращает оптимистичное состояние во время ожидающего экшна и реальное состояние в остальных случаях. Важно: если экшн падает с ошибкой, оптимистичное обновление автоматически отбрасывается — React откатывается к исходному состоянию, переданному первым аргументом.

---

## Хук `use()`

`use()` — новый примитив, способный читать значение Promise или Context — и, в отличие от всех других хуков, его можно вызывать условно:

```tsx
import { use, Suspense } from 'react';

// Чтение Promise (заменяет async-компоненты в некоторых сценариях):
function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  // Суспендит до resolve промиса — должен быть внутри Suspense boundary:
  const user = use(userPromise);
  return <h1>{user.name}</h1>;
}

function Page() {
  // Fetch инициируется в Server Component / родителе, передаётся как проп:
  const userPromise = fetchUser(userId);

  return (
    <Suspense fallback={<Skeleton />}>
      <UserProfile userPromise={userPromise} />
    </Suspense>
  );
}
```

```tsx
// Чтение Context (как useContext, но может быть условным):
import { use } from 'react';

function Component({ show }: { show: boolean }) {
  if (!show) return null;

  // ✅ Это разрешено — use() можно вызывать после условного return:
  const theme = use(ThemeContext);
  return <div className={theme}>...</div>;
}
```

`use()` отличается от `useContext` в одном важном аспекте: его можно вызывать внутри циклов и условий. Это делает его более гибким, чем `useContext`, для случаев когда значение контекста нужно не всегда. При передаче Promise интегрируется с Suspense — суспендит компонент до resolve, точно как `useSuspenseQuery` в React Query.

**Паттерн "передай промис, а не данные":**

```tsx
// Начинай fetch как можно раньше (в родителе):
async function Page({ params }: { params: { id: string } }) {
  // Fetch запускается немедленно, НЕ awaited:
  const userPromise = getUser(params.id);    // возвращает Promise<User>
  const postsPromise = getPosts(params.id);  // возвращает Promise<Post[]>

  return (
    <div>
      <Suspense fallback={<UserSkeleton />}>
        <UserHeader promise={userPromise} />   {/* суспендит самостоятельно */}
      </Suspense>
      <Suspense fallback={<PostsSkeleton />}>
        <PostList promise={postsPromise} />    {/* суспендит независимо */}
      </Suspense>
    </div>
  );
}

function UserHeader({ promise }: { promise: Promise<User> }) {
  const user = use(promise); // суспендит здесь до resolve
  return <h1>{user.name}</h1>;
}
```

Оба fetch выполняются параллельно. Водопадов нет, потому что ни один fetch не ожидается до запуска другого.

---

## ref как обычный проп (forwardRef больше не нужен)

В React 18 передача `ref` в функциональный компонент требовала `React.forwardRef`:

```tsx
// React 18 — forwardRef обязателен:
const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ placeholder, ...props }, ref) => (
    <input ref={ref} placeholder={placeholder} {...props} />
  )
);
Input.displayName = 'Input';
```

В React 19 `ref` — просто обычный проп:

```tsx
// React 19 — ref обычный проп:
function Input({ ref, placeholder, ...props }: InputProps & { ref?: React.Ref<HTMLInputElement> }) {
  return <input ref={ref} placeholder={placeholder} {...props} />;
}

// Или с новым сокращением (TypeScript сам выводит тип):
function Input({ ref, ...props }: React.ComponentProps<'input'>) {
  return <input ref={ref} {...props} />;
}
```

`forwardRef` по-прежнему работает в React 19, но помечен deprecated. В режиме разработки React выводит предупреждение при его использовании.

---

## Метаданные документа в компонентах

React 19 позволяет рендерить теги `<title>`, `<meta>` и `<link>` прямо в компонентах — React автоматически поднимает их в `<head>`:

```tsx
function BlogPost({ post }: { post: Post }) {
  return (
    <article>
      {/* Эти теги React поднимает в <head>: */}
      <title>{post.title} | Мой блог</title>
      <meta name="description" content={post.excerpt} />
      <link rel="canonical" href={`https://blog.example.com/posts/${post.slug}`} />

      <h1>{post.title}</h1>
      <p>{post.content}</p>
    </article>
  );
}
```

Это заменяет потребность в `react-helmet` / `next/head` в большинстве случаев. В Next.js App Router API `generateMetadata` остаётся рекомендованным подходом (он глубже интегрирован со стримингом и SSR), но нативная поддержка делает её жизнеспособной для простых случаев.

---

## React Compiler (бета)

React Compiler (ранее называлась "React Forget") — opt-in компилятор времени сборки, **автоматически добавляющий мемоизацию** в компоненты и хуки. Он статически анализирует код и вставляет эквиваленты `useMemo` / `useCallback` / `React.memo` там, где выполняются правила реактивности React.

```tsx
// Ты пишешь это:
function TodoList({ todos, filter }: { todos: Todo[]; filter: string }) {
  const filtered = todos.filter(t => t.title.includes(filter));
  return <ul>{filtered.map(t => <li key={t.id}>{t.title}</li>)}</ul>;
}

// Компилятор генерирует примерно это:
function TodoList({ todos, filter }: { todos: Todo[]; filter: string }) {
  const filtered = useMemo(
    () => todos.filter(t => t.title.includes(filter)),
    [todos, filter]
  );
  return <ul>{filtered.map(t => <MemoizedLi key={t.id} todo={t} />)}</ul>;
}
```

Компилятор применяет мемоизацию только там, где может доказать её безопасность — он не мемоизирует компонент нарушающий правила React (мутирование пропсов, чтение значений вне рендера и т.д.).

### Что Compiler означает для кода

```txt
С REACT COMPILER:
  ✓ useMemo / useCallback / React.memo становятся в основном ненужными
  ✓ Нет риска "неправильной мемоизации" (компилятор понимает модель React)
  ✓ Улучшение производительности без ручной оптимизации
  ✗ Всё ещё бета — обнаруживаются граничные случаи корректности
  ✗ Требует строгого следования правилам React
  ✗ Не помогает со структурными проблемами (состояние слишком высоко,
    лишние ре-рендеры из-за архитектуры)
```

### Текущий статус (по состоянию на React 19)

Compiler доступен как Babel/SWC-плагин (`babel-plugin-react-compiler`). Meta запустила его в production на Instagram с 2023 года. Он opt-in — включается для всего проекта или для отдельных файлов через директиву `'use memo'`.

```js
// babel.config.js:
module.exports = {
  plugins: [
    ['babel-plugin-react-compiler', {
      compilationMode: 'annotation', // компилировать только файлы с 'use memo'
    }],
  ],
};
```

---

## Стабильное vs экспериментальное — текущее положение

```txt
СТАБИЛЬНО В REACT 19 (использовать сейчас):
  Actions / async переходы
  useActionState
  useFormStatus
  useOptimistic
  хук use()
  ref как проп
  Метаданные документа (поднятие <title>, <meta>, <link>)
  Упорядочивание стилей (<link rel="stylesheet" precedence="...">)
  Дедупликация скриптов (<script async>)
  Server Components (через Next.js App Router, Remix и др.)
  Server Actions (через Next.js)

БЕТА / OPT-IN (пригодно для production с осторожностью):
  React Compiler — работает в production у Meta, доступен как Babel-плагин

ЭКСПЕРИМЕНТАЛЬНОЕ / БУДУЩЕЕ:
  Activity (ранее Offscreen) — пре-рендер скрытого UI, сохранение состояния для скрытых вкладок
  Улучшения React DevTools для Server Components
  Taint API — предотвращение передачи конкретных серверных данных на клиент
    (результат db.user.create не должен быть сериализуем на клиент)
```

---

## Заметки по миграции: React 18 → React 19

```tsx
// 1. useFormState → useActionState (импорт из 'react', а не 'react-dom'):
// Было:
import { useFormState } from 'react-dom';
// Стало:
import { useActionState } from 'react';

// 2. ReactDOM.render → createRoot (уже требовалось в React 18, в 19 предупреждение):
// Было:
ReactDOM.render(<App />, document.getElementById('root'));
// Стало:
ReactDOM.createRoot(document.getElementById('root')!).render(<App />);

// 3. forwardRef — всё ещё работает, но предупреждение о deprecated:
// Мигрируй постепенно — компоненты с forwardRef работают, но показывают dev-предупреждение.

// 4. Строковые ref (очень старые) — полностью удалены в React 19.
```

---

## Типичные ошибки на интервью

**«В чём разница между useActionState и useFormStatus?»**
`useActionState` управляет состоянием, возвращённым экшном формы — хранит результат (данные успеха/ошибки) и предоставляет флаг `isPending` для экшна. Оборачивает функцию экшна и используется в компоненте, владеющем формой. `useFormStatus` читает статус отправки **ближайшего родительского `<form>`** — предназначен для кнопки отправки или инпута, живущего *внутри* формы, но не владеющего экшном. Они компонуются: `useActionState` предоставляет проп `action` для формы; `useFormStatus` читает статус этой формы изнутри.

**«Можно ли использовать Actions из React 19 без Server Actions?»**
Да. Actions — это просто async-функции, переданные в `startTransition` или `useActionState`. Server Actions — конкретный вид экшна, где функция выполняется на сервере (помеченная `'use server'`). Обычная async клиентская функция (вызывающая API через `fetch`) работает идентично с точки зрения React — отслеживание pending-состояния и обработка ошибок работают одинаково.

**«Какую проблему решает useOptimistic, которую нельзя было решить раньше?»**
Паттерн не новый — всегда можно было хранить оптимистичное состояние в `useState` и сбрасывать вручную при ошибке. `useOptimistic` решает проблему эргономики и корректности: он автоматически привязывает оптимистичное состояние к жизненному циклу ожидающего экшна. Когда экшн завершается (успех или ошибка), оптимистичное состояние автоматически заменяется реальным. С ручным `useState` нужно было помнить о сбросе в каждом пути ошибки, и timing мог вызывать мерцание при рассинхронизации обновления реального состояния и ручного сброса.

**«В что фактически компилирует React Compiler?»**
Компилятор генерирует обычный React-код с вставленными `useMemo`, `useCallback` и мемоизированными компонентами нужной гранулярности. Он использует правила реактивности React как формальную модель — значение "реактивно" если зависит от пропсов, состояния или других реактивных значений. Компилятор отслеживает какие значения реактивны и оборачивает вычисления, зависящие только от нереактивных входных данных, в `useMemo`. Результат — корректный React-код, работающий на любом runtime React 18+ — компилятор является исключительно оптимизацией времени сборки, а не изменением runtime.

**«Почему `use()` разрешён в условиях, а другие хуки нет?»**
Правило React о невызове хуков условно существует потому что хуки отслеживаются по порядку вызова в связанном списке хуков Fiber-узла — вставка или удаление вызова хука от одного рендера к другому испортит список. `use()` — не хук в этом смысле: это новый примитив React, способный суспендить компонент (бросить специальное значение) и возобновить его позже. React не отслеживает вызовы `use()` по порядку так же; вместо этого он повторно выполняет компонент с самого начала после возобновления из суспенда, так что позиция вызова может меняться. Правила хуков не применяются к `use()`.
