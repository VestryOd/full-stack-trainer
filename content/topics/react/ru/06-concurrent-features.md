# Конкурентные возможности

## Что на самом деле меняет «конкурентный рендеринг»

«Concurrent mode» — это не режим, в который нужно явно переключаться: в React 18 это поведение по умолчанию при использовании `createRoot`. Термин означает, что React может работать над несколькими рендерами одновременно и прерывать, приостанавливать и возобновлять работу по мере изменения приоритетов.

```txt
ДО REACT 18 (legacy mode):
  Каждый setState → синхронный рендер → обновление DOM.
  Однажды начавшись, рендер выполняется до конца.
  Браузер заблокирован на всё время рендера.

REACT 18 (concurrent mode):
  setState → планирует работу с приоритетом (lane)
  Высокоприоритетная работа прерывает низкоприоритетные рендеры.
  Браузер получает управление между порциями Fiber.
  Несколько версий UI могут быть «в полёте» одновременно.
```

Для большей части повседневного кода изменение невидимо — `useState`, `useEffect`, обработчики событий работают как раньше. Конкурентный рендеринг становится заметным через новые API: `useTransition`, `useDeferredValue` и `Suspense` для данных.

---

## startTransition и useTransition

### Проблема, которую они решают

Пользовательский ввод должен быть мгновенным. Фильтрация списка, поисковые результаты, навигация — они могут слегка запаздывать, прежде чем пользователь это заметит. До React 18 не было способа выразить это различие: каждый `setState` имел одинаковую срочность.

`startTransition` помечает обновление состояния как несрочное (transition). React рендерит transition в фоне без блокировки UI. Если во время рендера transition приходит более высокоприоритетное обновление, React прерывает transition, обрабатывает его, затем возобновляет или перезапускает transition.

```tsx
import { startTransition, useTransition } from 'react';

// startTransition — отдельная функция, хук не нужен:
function SearchBox({ onSearch }: { onSearch: (q: string) => void }) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Срочно: обновить поле ввода немедленно
    setInputValue(e.target.value);

    // Несрочно: результаты поиска могут запаздывать
    startTransition(() => {
      onSearch(e.target.value);
    });
  };
  return <input onChange={handleChange} />;
}
```

`useTransition` — хуковая версия, также предоставляющая флаг `isPending`:

```tsx
function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Result[]>([]);
  const [isPending, startTransition] = useTransition();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);                       // срочно — обновляется немедленно

    startTransition(() => {
      const filtered = heavyFilter(allData, value);
      setResults(filtered);                // несрочно — может быть прервано
    });
  };

  return (
    <>
      <input value={query} onChange={handleChange} />
      {isPending && <Spinner />}           {/* показывается пока transition в процессе */}
      <ResultList results={results} />
    </>
  );
}
```

`isPending` равен `true` с момента вызова `startTransition` до момента, когда transition-рендер зафиксируется. Используйте его для показа индикатора загрузки на *текущем* контенте (не пустой экран), пока новая версия рендерится в фоне.

### Что startTransition НЕ делает

```tsx
// ❌ startTransition НЕ предназначен для асинхронных операций:
startTransition(async () => {
  const data = await fetchData(); // НЕПРАВИЛЬНО — async-часть выполняется вне transition
  setData(data);
});

// Transition завершается когда синхронная часть callback'а заканчивается.
// Ожидаемые операции НЕ являются частью transition.
// Для async-данных используйте Suspense + библиотеку данных (React Query, SWR)
// или React 19 Actions.
```

`startTransition` влияет только на синхронные обновления состояния внутри callback. Он помечает их как низкоприоритетные — вычисление всё ещё выполняется в главном потоке, просто может быть прервано и перезапущено. Он не переносит работу в web worker.

---

## useDeferredValue

`useDeferredValue` — альтернатива `startTransition` со стороны потребителя. Вместо оборачивания сеттера состояния вы оборачиваете значение, которому позволено запаздывать:

```tsx
function SearchResults({ query }: { query: string }) {
  const deferredQuery = useDeferredValue(query);
  // deferredQuery запаздывает относительно query.
  // Во время запаздывания используется предыдущее значение deferredQuery,
  // поэтому показываются предыдущие результаты, а не пустой экран.

  const isStale = query !== deferredQuery; // true пока отложенный рендер в процессе

  return (
    <div style={{ opacity: isStale ? 0.5 : 1 }}>
      <ExpensiveList query={deferredQuery} />
    </div>
  );
}
```

### startTransition vs useDeferredValue — что использовать

```txt
startTransition:
  Используйте когда КОНТРОЛИРУЕТЕ обновление состояния (владеете сеттером).
  Сеттер вызывается внутри startTransition.
  Transition начинается в момент его вызова.

useDeferredValue:
  Используйте когда НЕ КОНТРОЛИРУЕТЕ обновление состояния
  (значение приходит из props, библиотеки или состояния родителя).
  Вы получаете значение и откладываете его локально.
  React рендерит две версии: одну с текущим значением (показывается),
  одну с отложенным значением (вычисляется в фоне).
```

```tsx
// Если контролируете сеттер → startTransition:
const [results, setResults] = useState([]);
startTransition(() => setResults(filter(data, query)));

// Если получаете значение снаружи → useDeferredValue:
function Child({ query }: { query: string }) {
  const deferredQuery = useDeferredValue(query);
  return <ExpensiveList query={deferredQuery} />;
}
```

---

## Suspense — полная картина

Suspense был введён для code splitting (`React.lazy`). React 18 расширил его на загрузку данных. Базовая механика одна и та же:

```txt
Компонент «приостанавливается», бросая Promise.
React перехватывает брошенный Promise.
React показывает fallback ближайшей границы Suspense.
Когда Promise резолвится, React повторяет рендер приостановленного компонента.
```

### Suspense с React.lazy (code splitting)

```tsx
const HeavyChart = React.lazy(() => import('./HeavyChart'));

function Dashboard() {
  return (
    <Suspense fallback={<Skeleton />}>
      <HeavyChart />  {/* приостанавливается до загрузки JS-чанка */}
    </Suspense>
  );
}
```

`React.lazy` оборачивает динамический импорт. При первом рендере `HeavyChart` бросает Promise. React показывает `<Skeleton />`. Когда импорт резолвится, React ре-рендерит `HeavyChart` — на этот раз без броска, React фиксирует результат и `<Skeleton />` исчезает.

### Suspense с библиотеками данных

В React нет встроенного механизма загрузки данных, интегрированного с Suspense (вне Server Components). Библиотеки вроде React Query и SWR реализуют протокол «бросить Promise»:

```tsx
// С React Query (режим Suspense):
function UserProfile({ userId }: { userId: string }) {
  // Если данные ещё недоступны, бросает Promise.
  // React показывает ближайший Suspense fallback.
  // Когда запрос резолвится, React ре-рендерит этот компонент.
  const { data: user } = useSuspenseQuery({
    queryKey: ['user', userId],
    queryFn: () => fetchUser(userId),
  });

  return <div>{user.name}</div>; // данные всегда есть — проверка на loading не нужна
}

function Page() {
  return (
    <Suspense fallback={<ProfileSkeleton />}>
      <UserProfile userId="42" />
    </Suspense>
  );
}
```

Код компонента становится значительно проще: никаких `if (isLoading)`, никаких `if (error)` — состояния загрузки и ошибки обрабатываются на уровне границы.

### Поведение границы Suspense

```tsx
// Несколько границ Suspense — детальные состояния загрузки:
function Dashboard() {
  return (
    <div>
      <Suspense fallback={<HeaderSkeleton />}>
        <Header />        {/* может приостанавливаться независимо */}
      </Suspense>

      <Suspense fallback={<ChartSkeleton />}>
        <RevenueChart />  {/* может приостанавливаться независимо */}
      </Suspense>

      <Suspense fallback={<TableSkeleton />}>
        <DataTable />     {/* может приостанавливаться независимо */}
      </Suspense>
    </div>
  );
}
// Header, RevenueChart, DataTable загружаются параллельно.
// Каждый показывает свой скелетон при загрузке.
// Они раскрываются независимо по мере прихода данных.
```

Без оборачивания каждого в собственную границу единственная обёртка Suspense показывала бы один fallback для всего дашборда до тех пор, пока ВСЕ данные не будут готовы.

### SuspenseList (экспериментально в React 18)

`SuspenseList` координирует порядок раскрытия нескольких границ Suspense:

```tsx
import { SuspenseList } from 'react';

<SuspenseList revealOrder="forwards" tail="collapsed">
  <Suspense fallback={<Skeleton />}><Article id={1} /></Suspense>
  <Suspense fallback={<Skeleton />}><Article id={2} /></Suspense>
  <Suspense fallback={<Skeleton />}><Article id={3} /></Suspense>
</SuspenseList>
// revealOrder="forwards": статьи раскрываются сверху вниз, даже если позже загруженные готовы первыми.
// tail="collapsed": показывается только один скелетон одновременно (для следующего к раскрытию элемента).
```

---

## Transitions + Suspense вместе

Самая мощная комбинация: навигация между страницами без раздражающего мигания при загрузке.

```tsx
function App() {
  const [page, setPage] = useState('home');
  const [isPending, startTransition] = useTransition();

  function navigate(to: string) {
    startTransition(() => setPage(to));
    // Новая страница может приостановиться (загружать данные).
    // С startTransition: React держит текущую страницу видимой
    // (isPending=true) пока новая загружается в фоне.
    // Без startTransition: React немедленно показал бы Suspense fallback.
  }

  return (
    <>
      <nav>
        <button onClick={() => navigate('home')}>Главная</button>
        <button onClick={() => navigate('profile')}>Профиль</button>
        {isPending && <Spinner />}
      </nav>
      <Suspense fallback={<PageSkeleton />}>
        {page === 'home' ? <HomePage /> : <ProfilePage />}
      </Suspense>
    </>
  );
}
```

Без `startTransition`: клик на «Профиль» немедленно скрывает текущую страницу и показывает `<PageSkeleton />` — даже если данные загрузятся за 50 мс, будет видимое мигание.

С `startTransition`: текущая страница (Главная) остаётся видимой пока Профиль загружается в фоне. `isPending` равен `true`, можно показать тонкий индикатор. Когда Профиль готов, он заменяет Главную в одном commit — никакого промежуточного пустого экрана.

---

## useDeferredValue для предотвращения Suspense fallback при обновлениях

Когда контент границы Suspense уже показывается (не первая загрузка) и обновление состояния заставляет его снова приостановиться, у React есть выбор: показать fallback снова, или держать устаревший контент видимым. Поведение по умолчанию (без transitions) — показать fallback:

```tsx
function ProductPage({ categoryId }: { categoryId: number }) {
  // При изменении categoryId ProductList снова приостанавливается.
  // Без defer: немедленный переход к fallback.
  // С defer: продолжаем показывать предыдущую категорию пока новая загружается.
  const deferredId = useDeferredValue(categoryId);

  return (
    <Suspense fallback={<ProductSkeleton />}>
      <ProductList categoryId={deferredId} />
    </Suspense>
  );
}
```

`deferredId` запаздывает относительно `categoryId`. Пока `deferredId !== categoryId` (отложенный рендер в процессе), граница Suspense показывает предыдущий `ProductList` — устаревший, но видимый — вместо скелетона. Когда приходят новые данные, `deferredId` догоняет и показываются новые продукты.

---

## Типичные ловушки на интервью

**«Делает ли useTransition рендеринг быстрее?»**
Нет. `startTransition` не ускоряет вычисление — та же работа всё ещё выполняется в главном потоке. Он меняет *приоритет* работы, чтобы браузер мог обрабатывать более высокоприоритетные события (набор текста, клики) без ожидания завершения transition-рендера. Суммарное время CPU то же или чуть больше (из-за возможных прерываний и перезапусков). Воспринимаемая производительность улучшается, потому что ввод никогда не блокируется.

**«Когда React показывает Suspense fallback vs держит существующий контент?»**
При начальном рендере (ещё нет контента) → всегда показывает fallback. При обновлении, вызывающем приостановку: если обновление внутри `startTransition` → React держит существующий контент видимым пока новая версия загружается (fallback не показывается). Если обновление НЕ обёрнуто в `startTransition` → React немедленно переходит к fallback (потому что считает обновление срочным и не может показывать устаревший контент для срочных обновлений).

**«Можно ли использовать Suspense без библиотеки данных?»**
Да, но нужно вручную реализовать протокол «бросить Promise». Функция загрузки данных должна бросать Promise при первом вызове, возвращать разрешённое значение при последующих вызовах (после резолва Promise) и бросать Error при сбое запроса. На практике все используют React Query, SWR или Relay, потому что реализовать корректный кеш, интегрированный с Suspense, нетривиально.

**«В чём разница между isPending из useTransition и isLoading из React Query?»**
`isPending` (из `useTransition`) равен true пока React вычисляет transition-рендер — отражает фазу рендеринга. Становится false в момент фиксации transition. `isLoading` (из React Query) равен true пока сетевой запрос выполняется — отражает состояние загрузки данных. Они могут быть true одновременно (transition начат, запрос в процессе) или независимо (transition завершён но запрос ещё идёт, или запрос завершён но React ещё рендерит результат).

**«useDeferredValue — это то же самое что debounce?»**
Нет. Debounce откладывает само обновление состояния (сеттер не вызывается до истечения таймаута). `useDeferredValue` получает уже обновлённое значение и говорит React вычислять его рендер с более низким приоритетом — текущий рендер использует предыдущее отложенное значение пока новый рендер завершается в фоне. У `useDeferredValue` нет задержки, нет таймера и нет потерянных обновлений: React всегда в конечном счёте отрендерит с последним значением.
