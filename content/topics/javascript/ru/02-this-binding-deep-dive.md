# this: глубокий разбор привязки

## Почему `this` так часто путает — переформулировка проблемы

`this` — это не переменная. Это **неявный параметр функции**, значение которого определяется **в момент вызова**, а не в момент определения. Именно поэтому интуиция, привязанная к лексическому расположению кода, здесь подводит. Чтобы узнать значение `this`, нужно смотреть не на то, где написана функция, а на то, **как именно она вызвана**.

Спецификация задаёт четыре правила разрешения `this`. Движок применяет их в строгом порядке приоритета.

## Алгоритм разрешения `this` — четыре правила

### Правило 1: Default binding (привязка по умолчанию)

Применяется, когда функция вызвана как **самостоятельный вызов** (без получателя, без `new`, без `call/apply/bind`).

```js
function showThis() {
  console.log(this);
}

showThis(); // window (браузер, sloppy mode) / global (Node.js, sloppy mode)
            // undefined (strict mode — и браузер, и Node.js)
```

В **strict mode** `this` при default binding = `undefined`. Это одна из причин, почему `'use strict'` существует: в sloppy mode случайное `this.property = value` в глобальной функции тихо создавало свойство глобального объекта — классический источник багов.

```js
'use strict';
function strict() {
  console.log(this); // undefined
}

function sloppy() {
  console.log(this); // globalThis
}
```

### Правило 2: Implicit binding (неявная привязка)

Применяется, когда функция вызвана **через объект** (вызов метода). `this` = объект, стоящий **непосредственно слева от точки** в момент вызова.

```js
const user = {
  name: 'Alice',
  greet() {
    console.log(this.name);
  },
};

user.greet(); // 'Alice' — this = user
```

Ключевое слово — "непосредственно". Только прямой получатель вызова:

```js
const outer = {
  name: 'outer',
  inner: {
    name: 'inner',
    greet() {
      console.log(this.name);
    },
  },
};

outer.inner.greet(); // 'inner' — this = outer.inner, не outer
```

### Правило 3: Explicit binding (явная привязка)

`Function.prototype.call`, `apply`, `bind` — явно указываем, что будет `this`.

```js
function greet(greeting) {
  console.log(`${greeting}, ${this.name}`);
}

const user = { name: 'Bob' };

greet.call(user, 'Hello');         // 'Hello, Bob'   — вызов немедленно
greet.apply(user, ['Hi']);         // 'Hi, Bob'       — вызов немедленно, аргументы массивом
const boundGreet = greet.bind(user); // возвращает НОВУЮ функцию
boundGreet('Hey');                 // 'Hey, Bob'      — вызов позже
```

**Internals `bind`**: создаётся объект **bound function exotic object** с тремя внутренними слотами:

```txt
BoundFunction {
  [[BoundTargetFunction]] → greet
  [[BoundThis]]           → user
  [[BoundArguments]]      → []
}
```

При вызове bound function движок берёт `[[BoundThis]]` как `this` и prepend-ит `[[BoundArguments]]` к переданным аргументам. `call`/`apply` на bound function **не могут переопределить** `[[BoundThis]]` — он зафиксирован навсегда (кроме случая `new`, см. ниже).

**Частичное применение (partial application)**:

```js
function multiply(a, b) {
  return a * b;
}

const double = multiply.bind(null, 2); // [[BoundArguments]] = [2]
double(5);  // 10 — фактически multiply(2, 5)
double(10); // 20 — фактически multiply(2, 10)
```

**Разница `call` vs `apply`** — только в способе передачи аргументов:

```js
// Эквивалентные вызовы:
fn.call(ctx, 1, 2, 3);
fn.apply(ctx, [1, 2, 3]);

// Практический пример: apply удобен со spread-подобными ситуациями
const nums = [3, 1, 4, 1, 5, 9];
Math.max.apply(null, nums); // 9
// В современном JS: Math.max(...nums) — то же самое
```

### Правило 4: new binding

При вызове через `new` происходит следующее (алгоритм `[[Construct]]`):

```txt
1. Создаётся новый объект: obj = Object.create(Fn.prototype)
2. Fn вызывается с this = obj
3. Если Fn явно возвращает объект → возвращается тот объект
   Если Fn не возвращает объект (или return примитив/undefined)
   → возвращается obj
```

```js
function Person(name) {
  this.name = name;
  // неявно: return this (obj) — потому что нет явного return object
}

const alice = new Person('Alice');
alice.name; // 'Alice'

// Нюанс с явным return:
function Weird() {
  this.value = 1;
  return { value: 99 }; // явный return object → new вернёт этот объект
}
const w = new Weird();
w.value; // 99, а не 1!
```

## Приоритет правил

```txt
new  >  explicit (bind)  >  implicit  >  default

new:      new Fn()
explicit: fn.call/apply/bind(ctx)
implicit: obj.fn()
default:  fn()
```

Пример проверки приоритета `new` над `bind`:

```js
function Counter(start) {
  this.value = start;
}

const BoundCounter = Counter.bind({ value: 999 });
const c = new BoundCounter(0); // new выигрывает над bind
c.value; // 0, а не 999 — this при new = новый объект, не [[BoundThis]]
```

Это не случайность — спецификация явно описывает: `[[Construct]]` на bound function игнорирует `[[BoundThis]]` и создаёт новый объект через `[[BoundTargetFunction]].prototype`.

## Arrow functions — почему у них нет своего `this`

Стрелочная функция не создаёт собственного `ThisBinding` в своём Function Environment Record. Это не "синтаксический сахар" над `bind` — это другая семантика создания окружения.

Когда движок создаёт стрелочную функцию, он:
1. **НЕ** создаёт поле `[[ThisValue]]` в Environment Record функции
2. Любое обращение к `this` внутри стрелки разрешается по Scope Chain — то есть находит `this` в **лексически объемлющем** контексте

```js
const obj = {
  name: 'obj',
  regular() {
    console.log(this.name); // 'obj' — this от implicit binding
  },
  arrow: () => {
    console.log(this.name); // undefined (или globalThis.name)
    // this = лексически объемлющий контекст — здесь это глобальный
    // контекст, где объектный литерал не создаёт нового this
  },
};

obj.regular(); // 'obj'
obj.arrow();   // undefined
```

Стрелки особенно полезны в методах, которым нужен `this` объекта в callback-ах:

```js
class Timer {
  constructor() {
    this.count = 0;
  }

  start() {
    // Без стрелки: this внутри callback = undefined (strict) или global
    setInterval(function() {
      this.count++; // ❌ this потерян
    }, 1000);

    // Со стрелкой: this захвачен из lexical context (из start())
    setInterval(() => {
      this.count++; // ✅ this = экземпляр Timer
    }, 1000);
  }
}
```

**`call`/`apply`/`bind` на стрелках — не работают для `this`:**

```js
const arrow = () => console.log(this);
const obj = { name: 'obj' };

arrow.call(obj);  // globalThis — аргумент this проигнорирован
arrow.bind(obj)(); // globalThis — bind не меняет this стрелки
// (аргументы передаются нормально, только this игнорируется)
```

## Типичные сценарии потери `this`

### Сценарий 1: Извлечение метода из объекта

```js
const user = {
  name: 'Alice',
  greet() { console.log(this.name); },
};

const greet = user.greet; // извлечение — implicit binding теряется
greet(); // undefined (strict) / '' (globalThis.name в браузере)
// this = globalThis, а не user
```

**Почему:** при вызове `greet()` уже нет объекта слева от точки. Привязка к `user` существовала только в синтаксисе `user.greet()`. Сама по себе функция никакого "памяти об объекте" не имеет.

### Сценарий 2: Передача метода как callback

```js
class Button {
  label = 'Click me';

  handleClick() {
    console.log(this.label);
  }
}

const btn = new Button();

document.addEventListener('click', btn.handleClick);
// ❌ handleClick вызывается как fn(), this = element или undefined (strict)

document.addEventListener('click', btn.handleClick.bind(btn)); // ✅
document.addEventListener('click', (e) => btn.handleClick(e)); // ✅
```

### Сценарий 3: Деструктуризация методов класса

```js
class Api {
  baseUrl = 'https://api.example.com';

  async fetchUser(id) {
    return fetch(`${this.baseUrl}/users/${id}`); // this.baseUrl???
  }
}

const { fetchUser } = new Api();
await fetchUser(1); // ❌ TypeError: Cannot read properties of undefined ('baseUrl')
```

**Три способа фикса — с разными трейдоффами:**

```js
class Api {
  baseUrl = 'https://api.example.com';

  // 1. Class field + arrow — привязывается в конструкторе,
  //    но: метод НЕ попадает в prototype (отдельная копия на каждом экземпляре)
  fetchUser = async (id) => {
    return fetch(`${this.baseUrl}/users/${id}`);
  };

  // 2. Обычный метод + bind в конструкторе — явно, понятно, но verbose
  fetchPost(id) {
    return fetch(`${this.baseUrl}/posts/${id}`);
  }
  constructor() {
    this.fetchPost = this.fetchPost.bind(this);
  }

  // 3. Не деструктурировать — просто всегда вызывать через api.fetchUser()
}
```

### Сценарий 4: setTimeout / setInterval

```js
class Poller {
  data = null;

  poll() {
    setTimeout(function() {
      this.data = fetch('/api/data'); // ❌ this = globalThis (или undefined)
    }, 1000);

    setTimeout(() => {
      this.data = fetch('/api/data'); // ✅ this = экземпляр Poller
    }, 1000);
  }
}
```

## Predict the output — составной пример

```js
const obj = {
  value: 42,
  getValue() {
    return this.value;
  },
  getValueArrow: () => {
    return this.value;
  },
  getValueDelayed() {
    return new Promise((resolve) => {
      setTimeout(function() {
        resolve(this.value);
      }, 0);
    });
  },
  getValueDelayedArrow() {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(this.value);
      }, 0);
    });
  },
};

console.log(obj.getValue());        // ?
console.log(obj.getValueArrow());   // ?

const { getValue } = obj;
console.log(getValue());            // ?

obj.getValueDelayed().then(console.log);      // ?
obj.getValueDelayedArrow().then(console.log); // ?
```

<details>
<summary>Ответ</summary>

```
42          // obj.getValue() — implicit binding, this = obj
undefined   // getValueArrow: стрелка, this = global (объектный литерал не создаёт this)
undefined   // getValue() после деструктуризации — default binding, this = undefined (strict) / global
undefined   // getValueDelayed — setTimeout с function(), this = global
42          // getValueDelayedArrow — setTimeout со стрелкой, this захвачен из getValueDelayedArrow(), где this = obj (implicit binding при вызове obj.getValueDelayedArrow())
```

</details>

## Жёсткая привязка через `bind` и переопределение

```js
function greet() {
  return this.name;
}

const alice = { name: 'Alice' };
const bob = { name: 'Bob' };

const greetAlice = greet.bind(alice);

greetAlice();                     // 'Alice'
greetAlice.call(bob);             // 'Alice' — bind нельзя переопределить через call
greetAlice.bind(bob)();           // 'Alice' — bind поверх bind тоже не работает
new greetAlice();                 // '' — new игнорирует [[BoundThis]], this = новый объект
```

Единственное, что "победит" bind — это `new`.

## Связь с другими темами

```txt
[Контексты выполнения]  — ThisBinding — отдельное поле Execution Context,
                           не связанное со Scope Chain
[Замыкания]             — стрелочные функции используют this из замкнутого
                           контекста — это пересечение механики замыканий и this
[Прототипы]             — this внутри метода prototype-цепочки всегда указывает
                           на объект, для которого был сделан вызов, а не на
                           прототип, где метод определён
[Классы]                — class method в strict mode, class field arrow function —
                           разные трейдоффы для this-binding
```

## Типичные ошибки на интервью

- **Путать "где функция написана" с "как она вызвана"** — только способ вызова определяет `this` (кроме стрелок и bound functions). Одна и та же функция в разных контекстах вызова даст разный `this`.

- **"Стрелка захватывает this родителя через bind"** — нет, это другой механизм. `bind` создаёт новую функцию с `[[BoundThis]]`. Стрелка вообще не имеет собственного `ThisBinding` — обращение к `this` разрешается по Scope Chain как обычный идентификатор. Поэтому `call/apply/bind` на стрелке не влияют на `this`.

- **Не знать порядок приоритета** — `new` выигрывает у `bind`; без этого знания задача вроде `new BoundFn()` ставит в тупик.

- **"Метод стрелки в объектном литерале захватывает this объекта"** — нет. Объектный литерал `{}` не создаёт нового контекста выполнения. `this` стрелки в `{ arrow: () => ... }` — это `this` лексически объемлющего контекста (часто глобального).

- **Не знать, что `bind` возвращает bound function exotic object** — важно для понимания, почему `bind(bind(fn, a), b)` не меняет `this` (внешний bind обёртывает bound function, но `[[BoundThis]]` уже зафиксирован во внутренней).

- **Забывать про strict mode при default binding** — `this = undefined` в strict mode vs `globalThis` в sloppy mode. В модульном коде (ESM) всегда strict mode — это меняет поведение по умолчанию.
