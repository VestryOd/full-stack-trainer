# Продвинутые хуки

## useMemo — реальный анализ затрат и выгоды

`useMemo` кеширует результат вычисления между рендерами. Кешированное значение используется повторно, пока зависимости не изменились (сравнение `Object.is`).

```tsx
const sorted = useMemo(
  () => [...items].sort((a, b) => a.name.localeCompare(b.name)),
  [items]
);
```

### Что на самом деле стоит useMemo

`useMemo` не бесплатен. При каждом рендере React должен:
1. Получить сохранённый узел хука из связного списка
2. Сравнить каждую зависимость с помощью `Object.is`
3. Либо вернуть кешированное значение, либо заново вычислить и сохранить новый результат

Для дешёвых вычислений (фильтрация массива из 10 элементов, простая арифметика) накладные расходы самого `useMemo` могут **превысить стоимость простого пересчёта значения**. Команда React прямо говорила об этом — `useMemo` нужен для действительно дорогих вычислений и ссылочной стабильности, а не для защитного программирования.

```txt
КОГДА useMemo ПОМОГАЕТ:
  ✓ Вычисление занимает ощутимое время
    (замерено через React Profiler)
  ✓ Мемоизированное значение уходит как prop в компонент,
    обёрнутый в React.memo, и иначе вызвало бы его ре-рендер
  ✓ Мемоизированное значение — зависимость useEffect
    и иначе вызвало бы повторный запуск эффекта при каждом рендере

КОГДА useMemo ВРЕДИТ (или в лучшем случае ничего не делает):
  ✗ Дешёвое вычисление: фильтрация < 100 элементов,
    простая арифметика
  ✗ Результат — примитив: примитивы сравниваются по значению,
    ссылочная стабильность не имеет значения
  ✗ Компонент и так рендерится редко
  ✗ Зависимости меняются почти при каждом рендере: кеш
    сбрасывается раньше, чем им успевают воспользоваться
```

### Измеряйте перед мемоизацией

```tsx
// Перед добавлением useMemo — измерьте:
console.time('sort');
const sorted = [...items].sort(...);
console.timeEnd('sort');

// Если выводит "sort: 0.01ms" — useMemo добавляет накладные расходы, не экономию.
// Если выводит "sort: 12ms" — useMemo оправдан.
```

Эвристика команды React: если вы не можете измерить видимую проблему производительности с помощью React DevTools Profiler, `useMemo` — это шум.

---

## useCallback — тот же анализ, другой тип результата

`useCallback(fn, deps)` идентичен `useMemo(() => fn, deps)` — мемоизирует ссылку на функцию вместо вычисленного значения.

```tsx
// Они эквивалентны:
const handleClick = useCallback(() => doSomething(id), [id]);
const handleClick = useMemo(() => () => doSomething(id), [id]);
```

### Когда useCallback реально важен

```tsx
// ❌ Бессмысленно — Button не memo'd, ре-рендерится в любом случае:
function Parent() {
  const handleClick = useCallback(() => setCount(c => c + 1), []);
  return <Button onClick={handleClick} />;
}

// ✅ Осмысленно — Button memo'd, стабильная ссылка предотвращает ре-рендер:
const Button = React.memo(({ onClick }: { onClick: () => void }) => {
  return <button onClick={onClick}>Нажать</button>;
});

function Parent() {
  const handleClick = useCallback(() => setCount(c => c + 1), []);
  return <Button onClick={handleClick} />;
  // Без useCallback: новая ссылка на функцию → Button ре-рендерится
  // С useCallback: та же ссылка → Button пропускает ре-рендер
}
```

`useCallback` осмысленен ровно в двух сценариях:
1. Функция передаётся как prop в дочерний компонент, обёрнутый в `React.memo`
2. Функция стоит в зависимостях `useEffect` или другого `useMemo`/`useCallback`

Во всех остальных случаях `useCallback` добавляет накладные расходы без выгоды.

### Ловушка бесконечного цикла

```tsx
// Классическая ошибка — эффект зависит от функции, меняющейся при каждом рендере:
function Component({ userId }: { userId: string }) {
  const fetchUser = async () => {          // новая ссылка при каждом рендере
    const user = await api.getUser(userId);
    setUser(user);
  };

  useEffect(() => {
    fetchUser();
  }, [fetchUser]); // → fetchUser меняется → эффект повторяется → fetchUser меняется → ∞
}

// Исправление: обернуть в useCallback с правильными deps:
const fetchUser = useCallback(async () => {
  const user = await api.getUser(userId);
  setUser(user);
}, [userId]); // стабильная ссылка; пересоздаётся только при изменении userId
```

---

## useRef — за пределами DOM-ссылок

`useRef` обычно преподают как «способ получить элемент DOM». DOM — это Document Object Model, дерево объектов, по которому браузер рисует страницу. Но это лишь один из сценариев. Настоящее назначение шире: **мутируемый контейнер, который живёт между рендерами и при изменении не вызывает ре-рендер**.

```tsx
const ref = useRef(initialValue);
// ref это: { current: initialValue }
// - ref.current мутируем
// - мутация ref.current НЕ планирует ре-рендер
// - ref.current выживает между рендерами:
//   это один объект на весь жизненный цикл компонента
// - ref.current НЕ является частью вывода рендера
//   и не захватывается в замыканиях отдельных рендеров
```

### Сценарий 1: доступ к DOM-узлам

```tsx
function AutoFocusInput() {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return <input ref={inputRef} />;
}
```

### Сценарий 2: хранение актуального значения без ре-рендеров

```tsx
// Паттерн: всегда иметь актуальный callback без устаревания эффектов
function useLatest<T>(value: T): React.RefObject<T> {
  const ref = useRef(value);
  // Синхронно обновляем во время рендера (безопасно — просто присваиваем ref.current)
  ref.current = value;
  return ref;
}

function Component({ onScroll }: { onScroll: (y: number) => void }) {
  const onScrollRef = useLatest(onScroll);

  useEffect(() => {
    const handler = () => onScrollRef.current(window.scrollY);
    window.addEventListener('scroll', handler);
    return () => window.removeEventListener('scroll', handler);
    // Пустые deps: эффект запускается один раз,
    // но всегда вызывает актуальный onScroll.
  }, []);
}
```

Это та же идея, которую React 19 оформил как хук `useEffectEvent`. Трюк с ref — концепция, лежащая в её основе.

### Сценарий 3: отслеживание предыдущих значений

```tsx
function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T | undefined>(undefined);

  useEffect(() => {
    // Запускается после рендера, поэтому во время рендера
    // ref.current ещё хранит значение из предыдущего рендера.
    ref.current = value;
  });

  return ref.current;
}

function Component({ count }: { count: number }) {
  const prevCount = usePrevious(count);
  return <div>Изменилось с {prevCount} на {count}</div>;
}
```

### Сценарий 4: переменные экземпляра (вместо useState для данных, не влияющих на рендер)

```tsx
function VideoPlayer({ src }: { src: string }) {
  const playerRef = useRef<PlayerInstance | null>(null);

  // playerRef хранит экземпляр плеера — он не является частью вывода рендера,
  // его мутация НЕ должна вызывать ре-рендер.
  // Использование useState для этого вызвало бы лишние ре-рендеры при каждой инициализации.
  useEffect(() => {
    playerRef.current = new PlayerInstance(src);
    return () => playerRef.current?.destroy();
  }, [src]);

  const handlePause = () => playerRef.current?.pause(); // императивно, без ре-рендера

  return <button onClick={handlePause}>Пауза</button>;
}
```

---

## useImperativeHandle — управляемое императивное API от родителя к ребёнку

По умолчанию родитель, который держит `ref` на дочерний компонент, получает его DOM-узел напрямую. С `useImperativeHandle` дочерний компонент сам решает, что именно окажется в `ref.current` у родителя.

```tsx
interface VideoHandle {
  play: () => void;
  pause: () => void;
  seek: (seconds: number) => void;
}

// React 19+ — ref это просто prop:
function VideoPlayer(
  { src, ref }: { src: string; ref: React.Ref<VideoHandle> }
) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useImperativeHandle(ref, () => ({
    play: () => videoRef.current?.play(),
    pause: () => videoRef.current?.pause(),
    seek: (s) => { if (videoRef.current) videoRef.current.currentTime = s; },
  }), []); // deps: пересчитывает объект handle при изменении зависимостей

  return <video ref={videoRef} src={src} />;
}

// Родитель:
function Page() {
  const videoRef = useRef<VideoHandle>(null);

  return (
    <>
      <VideoPlayer src="/video.mp4" ref={videoRef} />
      <button onClick={() => videoRef.current?.seek(30)}>Перейти на 0:30</button>
    </>
  );
}
```

Родитель не может обратиться к `videoRef.current.play`, если дочерний компонент явно не открыл этот метод через `useImperativeHandle`. Сам узел `<video>` родителю недоступен: инкапсуляция полная. Это правильный паттерн для компонентов вроде выбора даты, редакторов форматированного текста и своих медиаплееров.

**Когда использовать:** редко. Берите `useImperativeHandle` только там, где props не справляются: родителю нужно вызвать фокус, скролл или play/pause. Всё остальное должно идти через props и обработчики — это модель React «данные вниз, события вверх».

---

## useId — стабильные ID на сервере и клиенте

`useId` генерирует уникальную строку ID, которая **стабильна между рендерами на сервере и клиенте**. Это снимает ошибки гидратации там, где компонентам с уникальными ID нужен серверный рендеринг.

```tsx
function FormField({ label }: { label: string }) {
  const id = useId();
  // id выглядит примерно как ":r3:" — уникален в дереве компонентов,
  // стабилен между сервером и клиентом, согласован между ре-рендерами.

  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" />
    </div>
  );
}
```

**Почему не `Math.random()` или счётчик?** `Math.random()` генерирует разные значения на сервере и клиенте → ошибка гидратации. Счётчик на уровне модуля сбрасывается между серверными рендерами, но не между клиентскими: кеширование модулей работает по-другому. Значение `useId` берётся из позиции компонента в Fiber-дереве, а эта позиция одинакова на сервере и на клиенте.

**Генерация нескольких ID из одного вызова:**

```tsx
function DateRangePicker() {
  const id = useId();
  const startId = `${id}-start`;
  const endId = `${id}-end`;

  return (
    <>
      <label htmlFor={startId}>С</label>
      <input id={startId} type="date" />
      <label htmlFor={endId}>По</label>
      <input id={endId} type="date" />
    </>
  );
}
```

---

## Кастомные хуки — паттерны композиции

Кастомный хук — функция, имя которой начинается с `use` и которая может вызывать другие хуки. Префикс `use` — не украшение: линтер `eslint-plugin-react-hooks` считает функции, начинающиеся с `use`, хуками и применяет к ним правила хуков.

### Паттерн 1: извлечение и переиспользование логики с состоянием

```tsx
// Без кастомного хука — логика перемешана с компонентом:
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

// С кастомным хуком — логика извлечена и переиспользуема:
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

### Паттерн 2: обобщённый асинхронный хук

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

// Использование:
function Posts({ userId }: { userId: string }) {
  const state = useAsync(() => api.getPosts(userId), [userId]);
  if (state.status === 'loading') return <Spinner />;
  if (state.status === 'error') return <p>{state.error.message}</p>;
  if (state.status === 'success') return <PostList posts={state.data} />;
  return null;
}
```

### Паттерн 3: абстракция браузерных API

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

### Паттерн 4: композиция кастомных хуков

Кастомные хуки естественно компонуются — хук может вызывать другие хуки, включая другие кастомные:

```tsx
function useAuthenticatedUser() {
  const { data: session } = useSession();       // от next-auth или аналогов
  const userId = session?.user?.id;
  const userState = useAsync(
    () => userId ? api.getUser(userId) : Promise.resolve(null),
    [userId]
  );
  return userState;
}
```

### Соглашение об именовании принудительно применяется

Префикс `use` заставляет линтер считать функцию хуком и применять:
- Запрет условных вызовов внутри
- Запрет вызовов из не-хуков и не-компонентов
- Проверку исчерпывающих deps для любых `useEffect`/`useMemo`/`useCallback`, которые он вызывает

Если вы назвали функцию `useSomething`, она **обязана** следовать всем правилам хуков. Это верно, даже если сейчас она не вызывает ни одного встроенного хука. Вызовет завтра — а линтер требует соблюдения правил уже сегодня.

---

## useDebugValue — для DevTools

```tsx
function useUser(userId: string) {
  const [user, setUser] = useState<User | null>(null);

  // В React DevTools этот хук покажет "User: Alice (42)"
  // вместо просто сырого значения состояния.
  useDebugValue(user, u => `User: ${u?.name} (${userId})`);

  // ... логика загрузки
  return user;
}
```

Второй аргумент (форматтер) вызывается только DevTools — не вызывается в production, поэтому дорогое форматирование безопасно включать.

---

## Типичные ловушки на интервью

**«В чём разница между useMemo и useCallback?»**
`useCallback(fn, deps)` — это в точности `useMemo(() => fn, deps)`. Отличаются они только тем, что кешируют: функцию или вычисленное значение. Оба нужны для ссылочной стабильности между рендерами.

**«Нужно ли оборачивать всё в useMemo/useCallback для производительности?»**
Нет. Это один из самых частых видов избыточной оптимизации в React-проектах, и у обоих хуков есть свои накладные расходы. Они помогают ровно в трёх случаях:

- Вычисление ощутимо дорогое.
- Мемоизированное значение передаётся в дочерний компонент, обёрнутый в `React.memo`.
- Значение стоит в зависимостях `useEffect`.

По умолчанию мемоизации нет. Добавляйте её, когда профилирование показало реальную проблему.

**«Может ли useRef хранить функцию?»**
Да. Распространённый паттерн — хранить обработчики событий в ref, чтобы получать актуальную версию без пересоздания эффектов:

```tsx
const handlerRef = useRef(onData);
handlerRef.current = onData; // всегда актуальный
useEffect(() => {
  socket.on('data', (d) => handlerRef.current(d));
}, []); // setup сокета запускается один раз; handler всегда актуален через ref
```

**«Почему useImperativeHandle нужен forwardRef в React < 19?»**
В React < 19 `ref` — не обычный prop. React обрабатывает его особым образом и не передаёт через `props`. Обёртка `forwardRef` явно передаёт `ref` родителя дочернему компоненту, и там его уже может перехватить `useImperativeHandle`. В React 19 `ref` стал обычным prop, и `forwardRef` больше не нужен.

**«Когда использовать useRef вместо useState?»**
Когда компоненту значение нужно внутри себя, но его изменение **не** должно вызывать ре-рендер. Типичные примеры:

- ID таймеров и ID анимационных кадров.
- Экземпляры WebSocket.
- Значения из предыдущего рендера.
- Состояние фокуса, которое вы отслеживаете, но не показываете.

Если изменение значения должно обновить интерфейс (UI, user interface) → `useState`. Если нет → `useRef`.
