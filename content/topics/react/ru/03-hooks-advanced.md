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
  ✓ Вычисление занимает ощутимое время (проверено через React Profiler)
  ✓ Мемоизированное значение передаётся как prop в React.memo-компонент
    и иначе вызвало бы его ре-рендер
  ✓ Мемоизированное значение — зависимость useEffect
    и иначе вызвало бы повторный запуск эффекта при каждом рендере

КОГДА useMemo ВРЕДИТ (или в лучшем случае ничего не делает):
  ✗ Дешёвое вычисление (фильтрация < 100 элементов, простая математика)
  ✗ Результат — примитив: примитивы сравниваются по значению,
    ссылочная стабильность не имеет значения
  ✗ Компонент и так рендерится редко
  ✗ Зависимости меняются почти при каждом рендере
    (кешированное значение инвалидируется до повторного использования)
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
1. Функция передаётся как prop в `React.memo`-обёрнутый дочерний компонент
2. Функция является зависимостью `useEffect` или другого `useMemo`/`useCallback`

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

`useRef` обычно преподают как «способ получить DOM-элемент». Это один из сценариев. Более глубокая цель: **мутируемый контейнер, сохраняющийся между рендерами без инициирования ре-рендеров**.

```tsx
const ref = useRef(initialValue);
// ref это: { current: initialValue }
// - ref.current мутируем
// - мутация ref.current НЕ планирует ре-рендер
// - ref.current выживает между рендерами (один объект на весь жизненный цикл компонента)
// - ref.current НЕ является частью вывода рендера (не захватывается в замыканиях каждого рендера)
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
  }, []); // пустые deps — эффект запускается один раз, но всегда вызывает АКТУАЛЬНЫЙ onScroll
}
```

Это паттерн `useEffectEvent` в скрытой форме — React 19 формализует его как хук, но трюк с ref — это лежащая в основе концепция реализации.

### Сценарий 3: отслеживание предыдущих значений

```tsx
function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T | undefined>(undefined);

  useEffect(() => {
    ref.current = value; // запускается после рендера, поэтому ref.current хранит ПРЕДЫДУЩЕЕ значение во время рендера
  });

  return ref.current;
}

function Component({ count }: { count: number }) {
  const prevCount = usePrevious(count);
  return <div>Изменилось с {prevCount} на {count}</div>;
}
```

### Сценарий 4: переменные экземпляра (вместо useState для не-рендер данных)

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

По умолчанию, когда родитель держит `ref` на дочерний компонент, он получает DOM-узел напрямую. `useImperativeHandle` позволяет дочернему компоненту контролировать, что именно `ref.current` родителя открывает.

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

Родитель не может получить доступ к `videoRef.current.play`, если дочерний компонент явно не открывает это через `useImperativeHandle`. Сырой DOM-узел `<video>` недоступен родителю — у дочернего компонента полная инкапсуляция. Это правильный паттерн для компонентов вроде date-picker'ов, rich text редакторов и кастомных медиаплееров.

**Когда использовать:** редко. Большинство коммуникации компонентов должно идти через props и callbacks (модель React data-down / events-up). `useImperativeHandle` — для случаев, когда родителю нужно инициировать императивное действие (фокус, скролл, play/pause), которое не вписывается в модель props.

---

## useId — стабильные ID на сервере и клиенте

`useId` генерирует уникальную строку ID, которая **стабильна между рендерами на сервере и клиенте** — предотвращая ошибки гидратации, когда компоненты с уникальными ID рендерятся на сервере.

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

**Почему не `Math.random()` или счётчик?** `Math.random()` генерирует разные значения на сервере и клиенте → ошибка гидратации. Счётчик на уровне модуля сбрасывается между серверными рендерами, но не клиентскими (из-за различий кеширования модулей). `useId` внутренне производится из позиции компонента в Fiber-дереве, которая идентична на сервере и клиенте.

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

Кастомный хук — функция, имя которой начинается с `use` и которая может вызывать другие хуки. Префикс `use` — не украшение: линтер `eslint-plugin-react-hooks` считает функции, начинающиеся с `use`, хуками и применяет к ним Правила Хуков.

### Паттерн 1: извлечение и переиспользование стейтовой логики

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

Если вы назвали функцию `useSomething`, она ОБЯЗАНА следовать всем правилам хуков, даже если сейчас не вызывает ни одного встроенного хука — потому что может в будущем, и линтер применяет это немедленно.

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
`useCallback(fn, deps)` это точно `useMemo(() => fn, deps)` — они отличаются только тем, что кешируют: функцию vs вычисленное значение. Оба про ссылочную стабильность между рендерами.

**«Нужно ли оборачивать всё в useMemo/useCallback для производительности?»**
Нет. Это один из самых распространённых паттернов избыточной оптимизации в React-кодовых базах. `useMemo` и `useCallback` имеют собственные накладные расходы. Они помогают только когда: (1) вычисление ощутимо дорогое, (2) мемоизированное значение передаётся в `React.memo`-дочерний компонент, или (3) это зависимость `useEffect`. По умолчанию: никакой мемоизации. Добавляйте когда профилирование показывает реальную проблему.

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
В React < 19, `ref` не является обычным prop — React обрабатывает его специально и не передаёт через `props`. `forwardRef` — обёртка, явно передающая `ref` родителя дочернему компоненту, где `useImperativeHandle` может его перехватить. В React 19, `ref` — обычный prop и `forwardRef` больше не нужен.

**«Когда использовать useRef вместо useState?»**
Когда нужно хранить значение, которое компонент использует внутренне, но изменение которого НЕ должно вызывать ре-рендер: ID таймеров, ID анимационных кадров, WebSocket-экземпляры, предыдущие значения рендера, состояние фокуса для невизуального отслеживания. Если изменение значения должно обновить UI → `useState`. Если нет → `useRef`.
