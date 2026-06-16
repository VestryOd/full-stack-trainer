# MobX — продвинутые паттерны

## Асинхронные actions: flow vs async/await

Асинхронность в MobX — частый источник путаницы. Проблема в том, что `async/await` разрывает action-контекст: код после первого `await` выполняется **вне** оригинального action.

```ts
import { action, makeObservable, observable, runInAction } from 'mobx';

class UserStore {
  user: User | null = null;
  isLoading = false;
  error: string | null = null;

  constructor() {
    makeObservable(this, {
      user: observable,
      isLoading: observable,
      error: observable,
      fetchUser: action,  // только начало метода — action
    });
  }

  // ❌ Проблема: мутации после await — вне action
  async fetchUser_BROKEN(id: string) {
    this.isLoading = true; // OK — синхронная часть, в action
    try {
      const user = await api.getUser(id); // await разрывает action
      this.user = user;       // ❌ MobX warning в strict mode:
      this.isLoading = false; //    мутация вне action
    } catch (e) {
      this.error = String(e); // ❌ тоже вне action
      this.isLoading = false;
    }
  }

  // ✅ Вариант 1: runInAction для каждого "блока мутаций после await"
  async fetchUser(id: string) {
    this.isLoading = true;
    try {
      const user = await api.getUser(id);
      runInAction(() => {
        this.user = user;
        this.isLoading = false;
      });
    } catch (e) {
      runInAction(() => {
        this.error = String(e);
        this.isLoading = false;
      });
    }
  }
}
```

### flow — идиоматическое решение MobX для асинхронности

`flow` использует генераторы вместо async/await. Внутри него `yield` делает то же, что `await`, но MobX умеет оборачивать каждый "шаг" после yield в action автоматически:

```ts
import { flow, makeObservable, observable } from 'mobx';

class UserStore {
  user: User | null = null;
  isLoading = false;
  error: string | null = null;

  constructor() {
    makeObservable(this, {
      user: observable,
      isLoading: observable,
      error: observable,
      fetchUser: flow, // не action — flow
    });
  }

  // ✅ flow: генератор, yield вместо await
  // Все мутации автоматически в action-контексте
  *fetchUser(id: string) {
    this.isLoading = true;
    try {
      const user: User = yield api.getUser(id); // yield = await
      this.user = user;       // автоматически в action — OK
      this.isLoading = false;
    } catch (e) {
      this.error = String(e); // тоже OK
      this.isLoading = false;
    }
  }
}

// Использование идентично async методу:
const store = new UserStore();
await store.fetchUser('123');
```

**Дополнительное преимущество flow — отмена:**

```ts
class SearchStore {
  results: SearchResult[] = [];
  isLoading = false;

  constructor() {
    makeObservable(this, {
      results: observable,
      isLoading: observable,
      search: flow,
    });
  }

  *search(query: string) {
    this.isLoading = true;
    this.results = yield api.search(query);
    this.isLoading = false;
  }
}

const store = new SearchStore();
const cancel = store.search('react'); // flow возвращает объект с cancel
// ...пользователь изменил запрос раньше, чем пришёл ответ
cancel(); // отменяем предыдущий поиск
store.search('redux'); // запускаем новый
```

**Когда что выбирать:**

```txt
runInAction  — когда нужно быстро исправить существующий async-метод
               или логика простая (один запрос, один блок мутаций)

flow         — идиоматический MobX-способ, предпочтителен для:
               - сложных асинхронных сценариев с несколькими await
               - когда нужна отмена (cancel)
               - новых сторов (более явно, что это "MobX async action")
```

## reaction / autorun / when — когда что использовать

Все три создают реакцию на изменения observable, но с разными контрактами:

```ts
import { autorun, reaction, when } from 'mobx';

const store = new CartStore();

// autorun:
// - запускается СРАЗУ при создании (side effect при инициализации)
// - отслеживает зависимости динамически (что прочитал — то и отслеживает)
// - запускается при ЛЮБОМ изменении прочитанных observables
const dispose1 = autorun(() => {
  // Запустится сейчас, и потом при каждом изменении
  // store.total или store.itemCount
  document.title = `Cart (${store.itemCount}) — $${store.total}`;
});

// reaction:
// - НЕ запускается при создании (только при изменениях)
// - явно разделяет "что отслеживать" и "что делать"
// - получает предыдущее и текущее значение
const dispose2 = reaction(
  () => store.total,           // tracked expression — MobX отслеживает это
  (total, prevTotal) => {      // effect — выполняется при изменении
    if (total > prevTotal) {
      analytics.track('cart_value_increased', { total, prevTotal });
    }
  },
  { fireImmediately: false }   // default — но можно сделать как autorun
);

// when:
// - одноразово: срабатывает при выполнении условия и диспоузится сам
// - возвращает Promise (можно await)
// - с timeout: автоматически reject, если условие не выполнилось вовремя
const dispose3 = when(
  () => store.total > 500,
  () => {
    notification.show('You qualify for free shipping!');
  }
);

// await-вариант when:
async function waitForCartReady() {
  await when(() => store.isLoaded);
  // код после этой строки выполнится только когда isLoaded станет true
  return store.total;
}
```

**Практические правила выбора:**

```txt
autorun  — логирование, синхронизация с внешними системами
           (document.title, localStorage), которые должны
           отработать сразу и при каждом изменении

reaction — analytics, отправка запросов при изменении фильтров,
           дебаунс-сохранение формы — когда нужно знать
           предыдущее значение или не нужен немедленный запуск

when     — ожидание условия: "когда данные загрузятся",
           "когда пользователь авторизуется" — одноразовый триггер
```

## RootStore — паттерн композиции сторов

Самый распространённый способ организации MobX в средних и крупных приложениях — RootStore, который создаёт все сторы и передаёт им ссылку на себя:

```ts
// stores/CartStore.ts
import type { RootStore } from './RootStore';

export class CartStore {
  items: CartItem[] = [];

  constructor(private root: RootStore) {
    makeAutoObservable(this);
  }

  get total() {
    return this.items.reduce((sum, item) => sum + item.price * item.qty, 0);
  }

  // Доступ к другому стору через root
  get isEligibleForDiscount() {
    // CartStore знает о UserStore через root — без прямой зависимости
    return this.root.userStore.isPremium && this.total > 100;
  }

  addItem(item: CartItem) {
    this.items.push(item);
    // Можно вызвать action другого стора
    this.root.analyticsStore.track('item_added', { item });
  }
}

// stores/UserStore.ts
import type { RootStore } from './RootStore';

export class UserStore {
  currentUser: User | null = null;
  isPremium = false;

  constructor(private root: RootStore) {
    makeAutoObservable(this);
  }

  *login(credentials: LoginCredentials) {
    const user: User = yield authApi.login(credentials);
    this.currentUser = user;
    this.isPremium = user.subscription === 'premium';
    // Инициализируем корзину после логина
    yield this.root.cartStore.loadSavedCart(user.id);
  }
}

// stores/RootStore.ts
import { CartStore } from './CartStore';
import { UserStore } from './UserStore';
import { AnalyticsStore } from './AnalyticsStore';

export class RootStore {
  cartStore: CartStore;
  userStore: UserStore;
  analyticsStore: AnalyticsStore;

  constructor() {
    // Каждый стор получает ссылку на root
    this.cartStore = new CartStore(this);
    this.userStore = new UserStore(this);
    this.analyticsStore = new AnalyticsStore(this);
  }
}

// Создаём один раз — синглтон или через context
export const rootStore = new RootStore();
```

**Подключение к React через Context:**

```tsx
// stores/StoreContext.tsx
import React, { createContext, useContext } from 'react';
import { RootStore } from './RootStore';

const StoreContext = createContext<RootStore | null>(null);

export const StoreProvider: React.FC<{
  store: RootStore;
  children: React.ReactNode;
}> = ({ store, children }) => (
  <StoreContext.Provider value={store}>
    {children}
  </StoreContext.Provider>
);

// Типизированные хуки для каждого стора
export const useCartStore = () => {
  const root = useContext(StoreContext);
  if (!root) throw new Error('StoreContext not provided');
  return root.cartStore;
};

export const useUserStore = () => {
  const root = useContext(StoreContext);
  if (!root) throw new Error('StoreContext not provided');
  return root.userStore;
};

// App.tsx
const store = new RootStore();

function App() {
  return (
    <StoreProvider store={store}>
      <Router />
    </StoreProvider>
  );
}

// В компоненте:
const CartPage = observer(() => {
  const cartStore = useCartStore();
  return <div>{cartStore.total}</div>;
});
```

**Почему RootStore, а не просто импортировать стор напрямую:**

```ts
// ❌ Прямой импорт — проблемы:
import { cartStore } from './CartStore'; // синглтон — сложно тестировать
import { userStore } from './UserStore'; // циклические зависимости при
//  cross-store refs (UserStore импортирует CartStore и наоборот)

// ✅ RootStore решает обе проблемы:
// - В тестах создаём новый RootStore для каждого теста (нет глобального состояния)
// - Сторы не импортируют друг друга — общаются через root (нет циклов)
```

## MobX 6: Proxy-based vs декораторы

В MobX 5 и ранее декораторы были основным способом объявления observable:

```ts
// MobX 4/5 — декораторы (устарело)
import { observable, computed, action } from 'mobx';

class CartStore {
  @observable items: CartItem[] = [];
  @observable discount = 0;

  @computed get total() {
    return this.items.reduce(
      (sum, item) => sum + item.price * item.qty, 0
    ) * (1 - this.discount);
  }

  @action addItem(item: CartItem) {
    this.items.push(item);
  }
}
```

```ts
// MobX 6 — makeObservable/makeAutoObservable (текущий стандарт)
class CartStore {
  items: CartItem[] = [];
  discount = 0;

  constructor() {
    makeAutoObservable(this);
  }

  get total() {
    return this.items.reduce(
      (sum, item) => sum + item.price * item.qty, 0
    ) * (1 - this.discount);
  }

  addItem(item: CartItem) {
    this.items.push(item);
  }
}
```

**Зачем MobX 6 перешёл на Proxy:**

1. **Стандарт**: декораторы в JavaScript оставались в proposal-стадии годами, и разные реализации (Babel, TypeScript) отличались поведением. Proxy — стабильная часть ES2015+.

2. **Нет трансформации кода**: Proxy-версия работает без babel-плагинов и специальных tsconfig флагов.

3. **Декораторы всё ещё работают в MobX 6** — через отдельный импорт `mobx-react` + `"experimentalDecorators": true` в tsconfig. Но для новых проектов `makeAutoObservable` предпочтительнее.

```ts
// MobX 6 с декораторами (legacy-совместимость)
import { observable, computed, action, makeObservable } from 'mobx';

class CartStore {
  @observable items: CartItem[] = [];

  constructor() {
    makeObservable(this); // в MobX 6 нужен явный вызов даже с декораторами
  }

  @computed get total() { /* ... */ }
  @action addItem(item: CartItem) { /* ... */ }
}
```

## Тестирование MobX-сторов

MobX-сторы — обычные классы, которые легко тестировать без моков React или рендера компонентов:

```ts
// stores/__tests__/CartStore.test.ts
import { CartStore } from '../CartStore';
import { RootStore } from '../RootStore';

describe('CartStore', () => {
  let rootStore: RootStore;
  let cartStore: CartStore;

  beforeEach(() => {
    // Новый RootStore для каждого теста — изолированное состояние
    rootStore = new RootStore();
    cartStore = rootStore.cartStore;
  });

  test('addItem increases itemCount', () => {
    cartStore.addItem({ id: '1', name: 'Book', price: 20, qty: 1 });
    expect(cartStore.itemCount).toBe(1);
  });

  test('addItem to existing increments qty', () => {
    cartStore.addItem({ id: '1', name: 'Book', price: 20, qty: 1 });
    cartStore.addItem({ id: '1', name: 'Book', price: 20, qty: 2 });
    expect(cartStore.items[0].qty).toBe(3);
    expect(cartStore.itemCount).toBe(3);
  });

  test('total applies discount', () => {
    cartStore.addItem({ id: '1', name: 'Book', price: 100, qty: 1 });
    cartStore.applyDiscount(20); // 20%
    expect(cartStore.total).toBeCloseTo(80);
  });

  test('computed total is memoized', () => {
    cartStore.addItem({ id: '1', name: 'Book', price: 50, qty: 2 });
    const total1 = cartStore.total;
    const total2 = cartStore.total; // не пересчитывается
    expect(total1).toBe(total2);
    expect(total1).toBe(100);
  });
});
```

**Тестирование async flow:**

```ts
// stores/__tests__/UserStore.test.ts
import { UserStore } from '../UserStore';
import { RootStore } from '../RootStore';

// Мокаем API, не MobX
jest.mock('../../api/authApi', () => ({
  login: jest.fn(),
}));
import { login } from '../../api/authApi';

describe('UserStore.login', () => {
  test('sets currentUser on successful login', async () => {
    const mockUser = { id: '1', name: 'Alice', subscription: 'premium' };
    (login as jest.Mock).mockResolvedValue(mockUser);

    const rootStore = new RootStore();
    await rootStore.userStore.login({ email: 'a@b.com', password: '123' });

    expect(rootStore.userStore.currentUser).toEqual(mockUser);
    expect(rootStore.userStore.isPremium).toBe(true);
  });

  test('handles login failure', async () => {
    (login as jest.Mock).mockRejectedValue(new Error('Invalid credentials'));

    const rootStore = new RootStore();
    await expect(
      rootStore.userStore.login({ email: 'a@b.com', password: 'wrong' })
    ).rejects.toThrow('Invalid credentials');

    expect(rootStore.userStore.currentUser).toBeNull();
  });
});
```

**Тестирование reactions:**

```ts
import { autorun } from 'mobx';

test('reaction fires when total changes', () => {
  const rootStore = new RootStore();
  const { cartStore } = rootStore;

  const observed: number[] = [];
  const dispose = autorun(() => {
    observed.push(cartStore.total);
  });

  cartStore.addItem({ id: '1', name: 'A', price: 10, qty: 1 });
  cartStore.addItem({ id: '2', name: 'B', price: 20, qty: 1 });

  expect(observed).toEqual([0, 10, 30]); // initial + две реакции

  dispose();
});
```

**Тестирование observer-компонентов** (когда нужно проверить именно React-интеграцию):

```tsx
import { render, screen, act } from '@testing-library/react';
import { observer } from 'mobx-react-lite';
import { CartStore } from '../CartStore';
import { RootStore } from '../RootStore';
import { StoreProvider } from '../StoreContext';

const CartTotal = observer(({ store }: { store: CartStore }) => (
  <span data-testid="total">{store.total}</span>
));

test('CartTotal re-renders when total changes', () => {
  const rootStore = new RootStore();

  render(
    <StoreProvider store={rootStore}>
      <CartTotal store={rootStore.cartStore} />
    </StoreProvider>
  );

  expect(screen.getByTestId('total').textContent).toBe('0');

  act(() => {
    rootStore.cartStore.addItem({ id: '1', name: 'A', price: 42, qty: 1 });
  });

  expect(screen.getByTestId('total').textContent).toBe('42');
});
```

## Типичные ошибки на интервью

- **"flow — это просто синтаксический сахар над async/await"** — не совсем. `flow` использует генераторы, что даёт возможность отмены (`cancel()`). С async/await отмену нельзя сделать нативно — нужны AbortController или флаги. Это реальное техническое отличие, важное в UI (race conditions при быстром вводе).

- **"Можно просто писать async methods без flow/runInAction"** — работает без strict mode, но нарушает батчинг. Каждое присвоение после `await` — отдельная синхронная нотификация, то есть компонент может ре-рендериться между `this.isLoading = false` и `this.user = user`, показывая промежуточное состояние.

- **Не понимать разницу между autorun и reaction** — ключевое различие: `autorun` запускается немедленно, `reaction` — нет. `reaction` получает предыдущее значение, `autorun` — нет. На интервью часто просят объяснить, когда что выбрать.

- **Циклические зависимости между сторами через прямые импорты** — классическая ошибка при масштабировании. `UserStore` импортирует `CartStore`, `CartStore` импортирует `UserStore` → Node.js разрешает одну из них как `undefined` на старте. RootStore через ссылку `root` решает это без единого cross-store импорта.

- **Не диспоузить reactions в компонентах** — если `autorun`/`reaction` создаётся в `useEffect` без возврата disposer-функции, MobX будет держать компонент живым в памяти даже после unmount и продолжать вызывать re-render (или React strict mode выбросит предупреждение):
  ```ts
  useEffect(() => {
    const dispose = autorun(() => {
      document.title = store.cartStore.itemCount.toString();
    });
    return dispose; // ← обязательно
  }, []);
  ```
