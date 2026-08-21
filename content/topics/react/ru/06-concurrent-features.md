# Конкурентные возможности

## Что на самом деле меняет «конкурентный рендеринг»

«Concurrent mode» — это не режим, в который нужно явно переключаться: в React 18 это поведение по умолчанию при использовании `createRoot`. Термин означает, что React умеет работать над несколькими рендерами одновременно. Он может прерывать, приостанавливать и возобновлять работу по мере изменения приоритетов.

```txt
ДО REACT 18 (legacy mode):
  Каждый setState → синхронный рендер → обновление DOM.
  Однажды начавшись, рендер выполняется до конца.
  Браузер заблокирован на всё время рендера.

REACT 18 (concurrent mode):
  setState → планирует работу с приоритетом (lane)
  Высокоприоритетная работа прерывает низкоприоритетные рендеры.
  Браузер получает управление между порциями Fiber.
  React держит сразу несколько недоделанных версий интерфейса:
  считает их параллельно и ни одну ещё не показывает на экране.
```

Для большей части повседневного кода изменение невидимо — `useState`, `useEffect`, обработчики событий работают как раньше. Конкурентный рендеринг становится заметным через новые API: `useTransition`, `useDeferredValue` и `Suspense` для данных.

---

## startTransition и useTransition

### Проблема, которую они решают

Пользовательский ввод должен быть мгновенным. Фильтрация списка, поисковые результаты, навигация — они могут слегка запаздывать, прежде чем пользователь это заметит. До React 18 не было способа выразить это различие: каждый `setState` имел одинаковую срочность.

`startTransition` помечает обновление состояния как несрочное (transition). React рендерит transition в фоне, не блокируя интерфейс (UI, user interface). Если во время рендера transition приходит более приоритетное обновление, React прерывает transition, обрабатывает срочное обновление, а потом возобновляет или перезапускает transition.

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

`isPending` равен `true` с момента вызова `startTransition` и до момента, когда transition-рендер зафиксируется. Показывайте по нему индикатор загрузки поверх *текущего* содержимого, а не пустой экран, пока новая версия рендерится в фоне.

### Границы возможностей startTransition

```tsx
// ❌ startTransition НЕ предназначен для асинхронных операций:
startTransition(async () => {
  const data = await fetchData(); // НЕПРАВИЛЬНО — async-часть выполняется вне transition
  setData(data);
});

// Transition завершается, когда заканчивается синхронная часть колбэка.
// Всё, что за await, частью transition уже НЕ является.
// Для async-данных используйте Suspense + библиотеку данных (React Query, SWR)
// или React 19 Actions.
```

`startTransition` влияет только на синхронные обновления состояния внутри колбэка. Он помечает их как низкоприоритетные: вычисление по-прежнему идёт в главном потоке, просто его можно прервать и перезапустить. Работу в web worker он не переносит.

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
  Когда обновление состояния контролируете вы (владеете сеттером).
  Сеттер вызывается внутри startTransition.
  Transition начинается в момент его вызова.

useDeferredValue:
  Когда обновление состояния контролируете НЕ вы
  (значение приходит из props, библиотеки или родителя).
  Вы получаете значение и откладываете его локально.
  React рендерит две версии: с текущим значением (её видно)
  и с отложенным значением (считается в фоне).
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

Suspense появился для разбиения кода на части — code splitting (`React.lazy`). React 18 расширил его на загрузку данных. Базовая механика одна и та же:

```txt
Компонент «приостанавливается», бросая Promise.
React перехватывает брошенный Promise.
React показывает fallback ближайшей границы Suspense.
Когда Promise выполнится, React заново отрендерит
приостановленный компонент.
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

`React.lazy` оборачивает динамический импорт. При первом рендере `HeavyChart` бросает Promise. React показывает `<Skeleton />`. Когда импорт завершится, React отрендерит `HeavyChart` заново: на этот раз тот ничего не бросает, React фиксирует результат, и `<Skeleton />` исчезает.

### Suspense с библиотеками данных

В React нет встроенного механизма загрузки данных, интегрированного с Suspense (вне Server Components). Библиотеки вроде React Query и SWR реализуют протокол «бросить Promise». Название SWR идёт от stale-while-revalidate — стратегии кеширования, которую библиотека использует.

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

Если не обернуть каждый блок в свою границу, одна общая обёртка Suspense покажет единственный fallback на весь дашборд — и будет держать его, пока не приедут **все** данные.

### SuspenseList (экспериментально в React 18)

`SuspenseList` координирует порядок раскрытия нескольких границ Suspense:

```tsx
import { SuspenseList } from 'react';

<SuspenseList revealOrder="forwards" tail="collapsed">
  <Suspense fallback={<Skeleton />}><Article id={1} /></Suspense>
  <Suspense fallback={<Skeleton />}><Article id={2} /></Suspense>
  <Suspense fallback={<Skeleton />}><Article id={3} /></Suspense>
</SuspenseList>
// revealOrder="forwards": статьи раскрываются сверху вниз,
// даже если нижние загрузились первыми.
// tail="collapsed": показывается только один скелетон —
// для того элемента, который раскроется следующим.
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

С `startTransition`: текущая страница (Главная) остаётся видимой, пока Профиль загружается в фоне. `isPending` равен `true`, поэтому можно показать неброский индикатор. Когда Профиль готов, он заменяет Главную одним коммитом — без промежуточного пустого экрана.

---

## useDeferredValue для предотвращения Suspense fallback при обновлениях

Граница Suspense может уже показывать своё содержимое, и тут обновление состояния снова заставляет её приостановиться. У React в этот момент есть выбор: показать fallback заново или оставить устаревшее содержимое на экране. Без transition по умолчанию он показывает fallback:

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

Значение `deferredId` запаздывает относительно `categoryId`. Пока `deferredId !== categoryId`, то есть пока отложенный рендер ещё считается, граница Suspense показывает предыдущий `ProductList` — устаревший, но видимый, — вместо скелетона. Когда приходят новые данные, `deferredId` догоняет, и на экране появляются новые товары.

---

## Типичные ловушки на интервью

**«Делает ли useTransition рендеринг быстрее?»**
Нет. `startTransition` не ускоряет вычисление: та же работа по-прежнему выполняется в главном потоке.

Меняется *приоритет* этой работы. Браузер получает возможность обрабатывать более срочные события — набор текста, клики — не дожидаясь конца transition-рендера. Суммарное время CPU остаётся тем же или чуть растёт из-за возможных прерываний и перезапусков. CPU — это central processing unit, центральный процессор. А воспринимаемая скорость растёт, потому что ввод больше не блокируется.

**«Когда React показывает Suspense fallback vs держит существующий контент?»**
При начальном рендере содержимого ещё нет, поэтому React всегда показывает fallback. При обновлении, которое вызывает приостановку, ответ зависит от обёртки:

- Внутри `startTransition`: React оставляет существующее содержимое на экране, пока грузится новая версия. Fallback не появляется.
- Вне `startTransition`: React сразу переключается на fallback. Он считает обновление срочным, а срочным обновлениям показывать устаревшее содержимое нельзя.

**«Можно ли использовать Suspense без библиотеки данных?»**
Да, но протокол «бросить Promise» придётся реализовать самому. Функция загрузки данных должна делать три вещи:

- Бросать Promise при первом вызове.
- Возвращать значение при последующих вызовах — после того как этот Promise выполнился.
- Бросать Error, если запрос не удался.

На практике все берут React Query, SWR или Relay. Написать корректный кеш, который дружит с Suspense, тяжело.

**«В чём разница между isPending из useTransition и isLoading из React Query?»**
Флаг `isPending` из `useTransition` равен true, пока React вычисляет transition-рендер. Он отражает фазу рендера и становится false в момент фиксации transition.

Флаг `isLoading` из React Query равен true, пока идёт сетевой запрос. Он отражает состояние загрузки данных. Флаги независимы, поэтому оба могут быть true одновременно. Transition может завершиться, когда запрос ещё идёт, — и наоборот, запрос может завершиться, когда React ещё рендерит результат.

**«useDeferredValue — это то же самое что debounce?»**
Нет, они работают по-разному. Debounce откладывает само обновление состояния: сеттер не вызывается, пока не истечёт таймаут.

`useDeferredValue` обновление не откладывает вовсе. Он получает уже обновлённое значение и говорит React рендерить его с более низким приоритетом. Пока этот низкоприоритетный рендер идёт в фоне, на экране остаётся предыдущее отложенное значение. Ни задержки, ни таймера, ни потерянных обновлений здесь нет: React в итоге всегда отрисует последнее значение.
