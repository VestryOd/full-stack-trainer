# React 19 и будущее

## Что React 19 действительно выпустил (стабильно, декабрь 2024)

React 19.0 вышел стабильным 5 декабря 2024 года. Раньше, 25 апреля 2024 года, вышли release candidate и руководство по обновлению — именно эту апрельскую дату часто принимают за дату стабильного релиза. Существующий код React 18 версия 19 не ломает: обновление в основном добавляет новое. Ключевые изменения:

```txt
Стабильно в React 19
  Actions (асинхронные переходы)
  useActionState (ранее useFormState)
  useFormStatus
  useOptimistic
  хук use()
  ref как обычный проп (forwardRef больше не нужен)
  Server Components и Server Actions
    (подключает фреймворк)
  Понятные ошибки: расхождения гидратации показывают diff
  Метаданные документа (title, meta-теги) в компонентах
  API загрузки стилей и скриптов
```

React Compiler не входит в сам React 19. Это отдельный пакет времени сборки,
и версии 1.0 он достиг 7 октября 2025 года.

---

## Actions — асинхронные переходы

`startTransition` в React 18 работал только с синхронными обновлениями. Самый частый реальный сценарий полноценной поддержки не имел: отправить форму, дождаться ответа сервера, обновить UI. UI — это user interface, то, что видит пользователь на экране.

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

`useFormStatus` читает статус отправки родительского `<form>`. Он решает одну конкретную задачу. Кнопка отправки внутри формы должна знать, идёт ли отправка. А передавать `isPending` пропом в каждую такую кнопку — лишнее повторение.

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

Поле `data` содержит отправленные `FormData`. Это удобно, чтобы показать оптимистичный предпросмотр отправленных значений, пока запрос ещё выполняется.

---

## useOptimistic

`useOptimistic` показывает обновление так, будто оно уже прошло успешно, пока асинхронный экшн ещё выполняется. Когда экшн завершится, React заменит эту догадку реальным состоянием. Если экшн упал, догадка отбрасывается.

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
    // Когда промис выполнится, React заменит оптимистичное состояние
    // реальными сообщениями с сервера — через ре-рендер с новыми пропсами
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

`useOptimistic` возвращает оптимистичное состояние, пока экшн выполняется, и реальное — во всех остальных случаях. Важно: если экшн падает с ошибкой, оптимистичное обновление отбрасывается само. React откатывается к исходному состоянию, переданному первым аргументом.

---

## Хук `use()`

`use()` — новый примитив, который умеет читать значение промиса или контекста. И, в отличие от всех остальных хуков, его можно вызывать условно:

```tsx
import { use, Suspense } from 'react';

// Чтение Promise (заменяет async-компоненты в некоторых сценариях):
function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  // Приостанавливает компонент, пока промис не выполнится;
  // поэтому компонент обязан находиться внутри <Suspense>:
  const user = use(userPromise);
  return <h1>{user.name}</h1>;
}

function Page() {
  // Запрос запускает серверный компонент или родитель
  // и передаёт промис пропом:
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

`use()` отличается от `useContext` в одном важном пункте: его можно вызывать внутри циклов и условий. Это удобнее, когда значение контекста нужно не всегда. Если передать промис, `use()` работает вместе с Suspense: он приостанавливает компонент, пока промис не выполнится, — ровно как `useSuspenseQuery` в React Query.

**Паттерн «передавайте промис, а не данные»:**

```tsx
// Запускайте загрузку как можно раньше — в родителе:
async function Page({ params }: { params: { id: string } }) {
  // Запрос уходит сразу, но его никто ещё не дожидается:
  const userPromise = getUser(params.id);    // возвращает Promise<User>
  const postsPromise = getPosts(params.id);  // возвращает Promise<Post[]>

  return (
    <div>
      <Suspense fallback={<UserSkeleton />}>
        <UserHeader promise={userPromise} />   {/* ждёт сам за себя */}
      </Suspense>
      <Suspense fallback={<PostsSkeleton />}>
        <PostList promise={postsPromise} />    {/* ждёт независимо */}
      </Suspense>
    </div>
  );
}

function UserHeader({ promise }: { promise: Promise<User> }) {
  const user = use(promise); // здесь компонент ждёт промис
  return <h1>{user.name}</h1>;
}
```

Оба запроса идут параллельно. Цепочки ожиданий («водопада») не возникает: ни один запрос не дожидаются раньше, чем запустят второй.

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
type WithRef = InputProps & { ref?: React.Ref<HTMLInputElement> };

function Input({ ref, placeholder, ...props }: WithRef) {
  return <input ref={ref} placeholder={placeholder} {...props} />;
}

// Или с новым сокращением (TypeScript сам выводит тип):
function Input({ ref, ...props }: React.ComponentProps<'input'>) {
  return <input ref={ref} {...props} />;
}
```

`forwardRef` по-прежнему работает в React 19 и на момент React 19.2 **не** помечен как deprecated. В справочнике сказано, что он «больше не нужен» и «будет объявлен устаревшим в одном из будущих релизов». Предупреждения в режиме разработки за его использование сейчас нет.

Устаревшим с предупреждением объявлено другое — чтение `ref` у элемента, то есть `element.ref`. Это разные вещи, и их легко перепутать. Для миграции есть готовый codemod:

```bash
npx codemod react/19/remove-forward-ref --target ./src
```

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

В большинстве случаев это заменяет `react-helmet` и `next/head`. В Next.js App Router рекомендованным остаётся `generateMetadata`: он глубже связан с потоковой отдачей и с SSR — server-side rendering, когда HTML собирается на сервере. Но встроенной поддержки уже хватает для простых случаев.

---

## React Compiler (версия 1.0, подключается вручную)

React Compiler (раньше назывался «React Forget») — компилятор времени сборки, который **сам добавляет мемоизацию** в компоненты и хуки. Он статически анализирует код и вставляет эквиваленты `useMemo`, `useCallback` и `React.memo` там, где выполняются правила реактивности React.

```tsx
// Вы пишете это:
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

Компилятор применяет мемоизацию только там, где может доказать её безопасность. Компонент, нарушающий правила React, он не мемоизирует: это мутирование пропсов, чтение значений вне рендера и подобное.

### Что Compiler означает для кода

```txt
С React Compiler
  ✓ useMemo / useCallback / React.memo становятся
    в основном ненужными
  ✓ Нет риска «неправильной мемоизации»: компилятор
    понимает модель React
  ✓ Код быстрее без ручной оптимизации
  ✗ Его всё равно надо добавить и настроить в проекте
  ✗ Требует строгого следования правилам React
  ✗ Не помогает со структурными проблемами: состояние
    живёт слишком высоко, ре-рендеры из-за архитектуры
```

### Текущий статус (React Compiler 1.0, октябрь 2025)

Версия 1.0 вышла 7 октября 2025 года, после беты в октябре 2024-го. Это плагин для Babel — `babel-plugin-react-compiler`, — и он же работает через SWC (Speedy Web Compiler, сборщик на Rust, который использует Next.js). Meta держит его в production на Instagram с 2023 года.

В существующем приложении его по-прежнему включают вручную: ставите плагин и активируете его на весь проект или на отдельные файлы директивой `'use memo'`. Новые приложения могут стартовать сразу с ним: Expo включает его по умолчанию с 54-й версии своего набора инструментов, а Vite и Next.js дают готовые шаблоны. Правила линтера от компилятора лежат в пресете `recommended` пакета `eslint-plugin-react-hooks`.

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
Стабильно в React 19.0 — можно использовать сейчас
  Actions / асинхронные переходы
  useActionState
  useFormStatus
  useOptimistic
  хук use()
  ref как проп
  Метаданные документа: поднятие <title>, <meta>, <link>
  Порядок стилей:
    <link rel="stylesheet" precedence="...">
  Дедупликация скриптов: <script async>
  Server Components (Next.js App Router, Remix, ...)
  Server Actions (через Next.js)

Стабильно в React 19.2 — октябрь 2025
  <Activity> (ранее Offscreen) — скрывает часть интерфейса
    и сохраняет состояние дочерних компонентов
  useEffectEvent — выносит нереактивную логику из эффекта
  cacheSignal — сообщает серверному коду, что время жизни
    cache() истекло, и работу можно прервать
  Треки производительности в Chrome DevTools:
    Scheduler и Components
  Частичный пре-рендер: prerender() и resume()

Стабильно, но выпускается отдельно от React
  React Compiler 1.0 — пакет времени сборки,
    который подключают к проекту вручную

Экспериментальное / будущее
  Улучшения React DevTools для Server Components
  Taint API — запрет на попадание конкретных серверных
    данных на клиент (результат db.user.create
    не должен быть сериализуемым)
```

У `<Activity>` в React 19.2 два режима:

- `hidden` — скрывает дочерние компоненты, размонтирует их эффекты и откладывает их обновления, пока у React есть другая работа.
- `visible` — показывает дочерние компоненты, монтирует их эффекты и обрабатывает обновления как обычно.

Другие режимы обещают добавить позже.

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

// 3. forwardRef — работает, и на 19.2 устаревшим не объявлен.
// Переезжайте, когда удобно: dev-предупреждения за него нет.
// Codemod: npx codemod react/19/remove-forward-ref --target ./src

// 4. Строковые ref (очень старые) — полностью удалены в React 19.
```

---

## Типичные ошибки на интервью

**«В чём разница между useActionState и useFormStatus?»**
Один владеет экшном, другой только читает форму, в которой находится.

| | `useActionState` | `useFormStatus` |
|---|---|---|
| Где живёт | в компоненте, владеющем формой | в любом компоненте *внутри* формы |
| Что даёт | результат экшна и `isPending` | `pending`, `data`, `method`, `action` |
| Откуда читает | из экшна, который обернул | из ближайшего родительского `<form>` |

Они дополняют друг друга. `useActionState` отдаёт форме проп `action`, а `useFormStatus` читает статус этой же формы изнутри дочернего компонента.

**«Можно ли использовать Actions из React 19 без Server Actions?»**
Да. Actions — это просто async-функции, переданные в `startTransition` или `useActionState`. Server Actions — один конкретный вид экшна: функция помечена `'use server'` и выполняется на сервере.

Обычная асинхронная клиентская функция, которая вызывает API через `fetch`, с точки зрения React ведёт себя точно так же. Отслеживание pending-состояния и обработка ошибок работают одинаково.

```tsx
// Клиентский Action — никакого 'use server':
async function saveTitle(prev: string, formData: FormData) {
  const title = formData.get('title') as string;
  const res = await fetch('/api/title', { method: 'POST', body: title });
  return res.ok ? title : prev;   // возвращённое значение станет состоянием
}
```

**«Какую проблему решает useOptimistic, которую нельзя было решить раньше?»**
Ничего невозможного — паттерн старый. Оптимистичное состояние всегда можно было держать в `useState` и сбрасывать вручную при ошибке.

`useOptimistic` исправляет удобство и корректность. Он привязывает оптимистичное состояние к жизненному циклу экшна, поэтому реальное состояние подхватывается автоматически, когда экшн завершился.

| | Вручную через `useState` | `useOptimistic` |
|---|---|---|
| Сброс после экшна | пишете сами, в каждой ветке ошибки | автоматически |
| Привязка к жизненному циклу экшна | нет | да |
| Риск мерцания | есть, если сброс и реальное обновление разъедутся | нет |

**«Во что на самом деле компилирует React Compiler?»**
В обычный React-код, где `useMemo`, `useCallback` и мемоизация компонентов расставлены с нужной точностью.

Формальной моделью служат правила реактивности React. Значение «реактивно», если зависит от пропсов, состояния или других реактивных значений. Компилятор отслеживает, какие значения реактивны, и оборачивает в `useMemo` те вычисления, все входные данные которых нереактивны.

Результат — корректный React-код, работающий на любом runtime начиная с React 18. Компилятор — исключительно оптимизация времени сборки, а не изменение runtime.

**«Почему `use()` разрешён в условиях, а другие хуки нет?»**
Потому что `use()` не отслеживается по порядку вызова, а обычные хуки — отслеживаются.

```txt
Хуки находят по позиции в списке, а не по имени:

  рендер 1:  [1] useState   [2] useEffect   [3] useMemo
  рендер 2:  [1] useState   [2] useMemo     ← useEffect пропущен
                             ↑ React отдаст состояние
                               от useEffect хуку useMemo
```

Хуки лежат в связанном списке на Fiber-узле, и React находит каждый по его позиции в этом списке. Вставьте или уберите вызов хука между двумя рендерами — и все позиции после него сдвинутся, список испорчен. В этом и вся причина правила.

`use()` — не хук в этом смысле. Это примитив, который умеет приостановить компонент, бросив специальное значение, и возобновить его позже. После возобновления React выполняет компонент заново с самого начала, поэтому позиция вызова может меняться. Правила хуков к `use()` не относятся.
