# MobX — основы реактивности

## Зачем MobX — и в чём его фундаментальная идея

React сам по себе требует явного управления ре-рендерами: `useState`, `useReducer`, `useMemo`, `useCallback` — всё это ручной контроль того, *что* пересчитывается и *когда*. MobX предлагает другой контракт: **объявить данные наблюдаемыми, и всё, что от них зависит, обновится автоматически**.

```txt
Ручная модель (React без MobX):
  state изменился → вы вручную вызываете setState → React
  перерендеривает компонент → компонент сам решает, что
  нужно пересчитать через memo/useMemo

MobX-модель:
  observable-данные изменились → MobX автоматически
  находит всё, что их читало (computed, reactions, observer-
  компоненты) → обновляет только это, и ничего лишнего
```

Это не магия — это **явное отслеживание зависимостей во время выполнения** (dependency tracking). Каждый раз, когда `computed` или `observer`-компонент читает observable-значение, MobX регистрирует: "этот читатель зависит от этого значения". Когда значение меняется — MobX точно знает, кого уведомить.

## Четыре примитива реактивности

### observable — наблюдаемое состояние

```ts
import { observable, makeObservable } from 'mobx';

class CartStore {
  items: CartItem[] = [];
  discount = 0;

  constructor() {
    makeObservable(this, {
      items: observable,
      discount: observable,
    });
  }
}
```

`observable` делает значение "отслеживаемым". MobX оборачивает его Proxy (MobX 6+), который перехватывает каждое чтение и каждую запись. Чтение во время выполнения `computed` или `observer` — регистрирует зависимость. Запись — уведомляет подписчиков.

**Что именно становится observable:** примитивы (number, string, boolean) отслеживаются напрямую; массивы и объекты оборачиваются Proxy-версией, которая отслеживает мутации (push, pop, присвоение по ключу). Map и Set поддерживаются через `observable.map()` и `observable.set()`.

### computed — производные значения

```ts
import { observable, computed, makeObservable } from 'mobx';

class CartStore {
  items: CartItem[] = [];
  discount = 0;

  constructor() {
    makeObservable(this, {
      items: observable,
      discount: observable,
      total: computed,
      itemCount: computed,
    });
  }

  get total() {
    return this.items.reduce((sum, item) => sum + item.price * item.qty, 0)
      * (1 - this.discount);
  }

  get itemCount() {
    return this.items.reduce((sum, item) => sum + item.qty, 0);
  }
}
```

`computed` — это **мемоизированная производная**. Ключевые свойства:

- Вычисляется **лениво** (только когда его кто-то читает).
- **Кэшируется** — если `items` и `discount` не менялись, повторное чтение `total` вернёт кэш без пересчёта.
- Автоматически **пересчитывается** только при изменении своих зависимостей.
- Если на `computed` нет наблюдателей — он "засыпает" и не пересчитывается совсем.

Это принципиально отличается от `useMemo`: `useMemo` пересчитывается при каждом ре-рендере, если зависимости поменялись; `computed` — глобально, один раз, и кэшируется до следующего изменения зависимостей.

### action — мутации состояния

```ts
import { observable, computed, action, makeObservable } from 'mobx';

class CartStore {
  items: CartItem[] = [];
  discount = 0;

  constructor() {
    makeObservable(this, {
      items: observable,
      discount: observable,
      total: computed,
      addItem: action,
      removeItem: action,
      applyDiscount: action,
    });
  }

  addItem(item: CartItem) {
    const existing = this.items.find(i => i.id === item.id);
    if (existing) {
      existing.qty += item.qty; // мутация внутри action — OK
    } else {
      this.items.push(item);
    }
  }

  removeItem(id: string) {
    const index = this.items.findIndex(i => i.id === id);
    if (index !== -1) this.items.splice(index, 1);
  }

  applyDiscount(percent: number) {
    this.discount = percent / 100;
  }
}
```

`action` делает две важные вещи:

1. **Батчинг уведомлений**: все изменения observable внутри action накапливаются, и реакции (computed, observer-компоненты) вызываются **один раз после завершения** action, а не после каждой отдельной строки. Это критично для производительности.

2. **Строгий режим**: в `configure({ enforceActions: 'always' })` изменение observable **вне** action — это ошибка. Action явно маркирует, где допустимы мутации.

### reaction — побочные эффекты

```ts
import { reaction, autorun, when } from 'mobx';

const store = new CartStore();

// autorun: запускается сразу, затем — при каждом изменении зависимостей
const disposer = autorun(() => {
  console.log('Cart total:', store.total);
  // MobX запомнил, что мы читали store.total
  // при следующем изменении total — перезапустит этот блок
});

// reaction: явно разделяет "что отслеживать" и "что делать"
const disposer2 = reaction(
  () => store.itemCount,                    // отслеживаемое выражение
  (count, prevCount) => {                   // эффект
    analytics.track('cart_items_changed', { count, prevCount });
  }
);

// when: одноразово, срабатывает при выполнении условия
when(
  () => store.total > 1000,
  () => store.applyDiscount(10) // скидка при достижении порога
);

// ВАЖНО: всегда сохранять и вызывать disposer
// при размонтировании компонента или уничтожении store
disposer();
disposer2();
```

## makeObservable vs makeAutoObservable

```ts
// makeObservable — явное объявление каждого поля
class UserStore {
  name = '';
  age = 0;
  isAdmin = false;

  constructor() {
    makeObservable(this, {
      name: observable,
      age: observable,
      isAdmin: observable,
      displayName: computed,
      rename: action,
    });
  }

  get displayName() {
    return `${this.name} (${this.age})`;
  }

  rename(newName: string) {
    this.name = newName;
  }
}

// makeAutoObservable — автовывод типов по соглашению:
// поля → observable, геттеры → computed, методы → action
class UserStore2 {
  name = '';
  age = 0;
  isAdmin = false;

  constructor() {
    makeAutoObservable(this);
    // Эквивалентно явному объявлению выше
  }

  get displayName() {
    return `${this.name} (${this.age})`;
  }

  rename(newName: string) {
    this.name = newName;
  }
}
```

**Когда что выбрать:**

- `makeAutoObservable` — для большинства стор-классов: меньше кода, меньше ошибок от пропущенных полей.
- `makeObservable` — когда нужен тонкий контроль (например, часть полей observable, часть нет) или когда класс использует наследование (с `makeAutoObservable` наследование работает с ограничениями).

```ts
// Ограничение makeAutoObservable: не работает с наследованием
class BaseStore {
  isLoading = false;
  constructor() {
    makeAutoObservable(this); // ❌ бросит ошибку, если класс наследуется
  }
}

class DerivedStore extends BaseStore {
  // MobX не может корректно проинициализировать прототип цепочку
}

// ✅ Для наследования — только makeObservable в каждом классе
class BaseStore2 {
  isLoading = false;
  constructor() {
    makeObservable(this, { isLoading: observable });
  }
}
```

## observer HOC и useObserver — когда React-компонент ре-рендерится

```tsx
import { observer } from 'mobx-react-lite';
import { useLocalObservable } from 'mobx-react-lite';

// observer оборачивает компонент, делая его реактивным
const CartSummary = observer(({ store }: { store: CartStore }) => {
  // Во время рендера MobX отслеживает каждое чтение observable
  // Этот компонент зависит от store.total и store.itemCount
  return (
    <div>
      <span>{store.itemCount} items</span>
      <span>Total: ${store.total.toFixed(2)}</span>
    </div>
  );
});

// Если store.items изменился → store.total пересчитался →
// CartSummary ре-рендерится. И только CartSummary.
// Родительский компонент НЕ ре-рендерится.
```

**Механизм под капотом**: `observer` оборачивает `render`-функцию компонента в `reaction`. При рендере MobX начинает отслеживание зависимостей. Когда рендер завершается — MobX знает, какие observable были прочитаны. При изменении любого из них — React вызывает принудительный ре-рендер через `forceUpdate` (или `setState`).

```tsx
// useLocalObservable — локальное observable состояние в компоненте
const LocalCounter = observer(() => {
  const state = useLocalObservable(() => ({
    count: 0,
    get doubled() { return this.count * 2; },
    increment() { this.count++; },
  }));

  return (
    <div>
      <button onClick={state.increment}>+</button>
      <span>{state.count} (doubled: {state.doubled})</span>
    </div>
  );
});
```

**Гранулярность ре-рендеров** — ключевое преимущество MobX перед Context:

```tsx
// ❌ Context: при изменении любого поля контекста ре-рендерятся
// ВСЕ потребители этого контекста
const AppContext = createContext(store);
const PriceTag = () => {
  const { cartStore } = useContext(AppContext);
  return <span>{cartStore.total}</span>;
  // Ре-рендерится при изменении ЛЮБОГО поля cartStore,
  // даже если total не изменился
};

// ✅ MobX: компонент ре-рендерится ТОЛЬКО при изменении
// тех observable, которые он реально прочитал во время рендера
const PriceTag2 = observer(({ store }: { store: CartStore }) => {
  return <span>{store.total}</span>;
  // Ре-рендерится ТОЛЬКО при изменении store.total
  // (или его зависимостей: items, discount)
});
```

## Строгий режим и enforceActions

```ts
import { configure } from 'mobx';

// Рекомендуется включать в разработке
configure({
  enforceActions: 'always',     // изменения observable ТОЛЬКО через action
  computedRequiresReaction: true, // computed нельзя читать вне reactive context
  reactionRequiresObservable: true, // reaction должен читать хоть один observable
  observableRequiresReaction: true, // observable нельзя читать вне reactive context
});

// ❌ Бросит ошибку в strict mode:
const store = new CartStore();
store.items.push(newItem); // MobX error: не обёрнуто в action

// ✅ Правильно:
store.addItem(newItem); // через задекларированный action

// ❌ Бросит ошибку с computedRequiresReaction:
console.log(store.total); // читаем computed вне observer/reaction/action

// ✅ Правильно: читать computed только внутри observer-компонента или reaction
```

Строгий режим помогает на ранних этапах обнаружить паттерны, которые приведут к трудноотлаживаемым проблемам в production.

## Типичные ошибки на интервью

- **"MobX автоматически делает весь класс реактивным"** — нет. Только то, что явно объявлено через `makeObservable`/`makeAutoObservable`. Поля, добавленные динамически после инициализации, не будут observable (в Proxy-режиме MobX 6 динамические поля поддерживаются, но только если они наблюдаемы изначально через `observable.object`).

- **Мутация observable вне action** — самая частая ошибка. `store.items.push(item)` напрямую в компоненте работает без строгого режима, но ломает батчинг уведомлений: каждая строка вызывает отдельную реакцию. Это и производительность, и сложность отладки.

- **Не вызывать disposer у reaction/autorun** — классическая утечка памяти. MobX держит ссылку на reaction до явного `dispose()`. Если reaction создан в компоненте, он будет жить после его unmount и продолжать реагировать на изменения.

- **Читать computed вне reactive context** — `computed` вычислится, но не будет кэшироваться и не будет автоматически обновляться. Это работает как обычный метод, а не как реактивное вычисление.

- **Деструктуризация observable объекта вне observer** — теряет реактивность:
  ```tsx
  const MyComponent = observer(({ store }: { store: CartStore }) => {
    const { total, itemCount } = store; // ❌ destructuring до рендера
    // total и itemCount — обычные числа, MobX не отследит чтение
    return <span>{total}</span>; // ре-рендера не будет при изменении
  });

  // ✅ Читать напрямую в JSX:
  const MyComponent2 = observer(({ store }: { store: CartStore }) => {
    return <span>{store.total}</span>; // читаем в reactive context
  });
  ```

- **"MobX — это как Redux, только с меньшим кодом"** — принципиально разные парадигмы. Redux: явный поток данных (dispatch → reducer → selector), иммутабельное состояние, предсказуемость через ограничения. MobX: реактивный граф зависимостей, мутабельное состояние, предсказуемость через строгий режим. Они решают разные проблемы и сравнивать их нужно через призму конкретных требований проекта.
