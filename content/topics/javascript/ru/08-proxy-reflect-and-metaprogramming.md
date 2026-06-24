# Proxy, Reflect и метапрограммирование

## Proxy — перехват фундаментальных операций

`Proxy` позволяет обернуть любой объект или функцию и перехватить **внутренние методы** ECMAScript — те низкоуровневые операции, которые движок выполняет при обращении к свойству, присваивании, вызове функции и т.д.

```js
const proxy = new Proxy(target, handler);
```

- `target` — любой объект, функция, массив, другой Proxy
- `handler` — объект с методами-**ловушками** (traps). Каждая ловушка соответствует внутреннему методу спецификации

Если ловушка не определена — операция прозрачно проходит к `target`.

### Полный список ловушек

```txt
Trap                    Перехватывает
───────────────────────────────────────────────────────────────
get(t, p, r)            obj.prop, obj[prop]
set(t, p, v, r)         obj.prop = value
has(t, p)               prop in obj
deleteProperty(t, p)    delete obj.prop
apply(t, this, args)    fn(), fn.call(), fn.apply()
construct(t, args, new) new Fn()
ownKeys(t)              Object.keys/getOwnPropertyNames/getOwnPropertySymbols
getOwnPropertyDescriptor(t, p)   Object.getOwnPropertyDescriptor()
defineProperty(t, p, d) Object.defineProperty()
getPrototypeOf(t)       Object.getPrototypeOf(), instanceof
setPrototypeOf(t, p)    Object.setPrototypeOf()
isExtensible(t)         Object.isExtensible()
preventExtensions(t)    Object.preventExtensions()
```

`t` = target, `p` = prop, `r` = receiver, `v` = value, `d` = descriptor

### Инварианты ловушек

Ловушки не всемогущи — спецификация требует соблюдения **инвариантов**. Нарушение → `TypeError` при вызове:

```js
const obj = {};
Object.defineProperty(obj, 'x', { value: 42, writable: false, configurable: false });

const proxy = new Proxy(obj, {
  get(target, prop) {
    return 100; // ❌ нарушение: non-writable non-configurable свойство
                // должно возвращать точно своё значение (42)
  },
});

proxy.x; // TypeError: 'get' on proxy: property 'x' is a non-configurable
          // and non-writable data property on the proxy target but the
          // proxy did not return its actual value
```

## Reflect — зеркало внутренних методов

`Reflect` — объект со статическими методами, **зеркально совпадающими** с именами ловушек Proxy. Он предоставляет способ выполнить "дефолтное поведение" внутри ловушки.

```txt
Reflect.get(target, prop, receiver)
Reflect.set(target, prop, value, receiver)
Reflect.has(target, prop)
Reflect.deleteProperty(target, prop)
Reflect.apply(target, thisArg, args)
Reflect.construct(target, args, newTarget)
// ... и т.д. для всех 13 ловушек
```

### Почему `Reflect` нужен рядом с `Proxy` — проблема `receiver`

Самая частая ошибка в Proxy: форвардить `get` через `target[prop]` вместо `Reflect.get`.

```js
const obj = {
  _x: 10,
  get doubled() { return this._x * 2; }, // getter использует this
};

const naiveProxy = new Proxy(obj, {
  get(target, prop) {
    console.log(`get: ${prop}`);
    return target[prop]; // ← проблема: this в getter = target, не proxy
  },
});

const correctProxy = new Proxy(obj, {
  get(target, prop, receiver) {
    console.log(`get: ${prop}`);
    return Reflect.get(target, prop, receiver); // ← receiver передаётся в getter
  },
});
```

```js
// Зачем это важно: цепочка наследования + getter
const base = {
  get value() { return this._val; }
};
const child = Object.create(base);
child._val = 42;

const proxy = new Proxy(child, {
  get(target, prop, receiver) {
    return Reflect.get(target, prop, receiver); // receiver = proxy
    // Когда getter 'value' обращается к this._val,
    // this = receiver (proxy), что правильно
  },
});

proxy.value; // 42 ✅
// Без Reflect: this в getter = base (target прототипа), _val не найден → undefined
```

**Принцип**: внутри ловушки всегда использовать `Reflect.*` для дефолтной операции — это гарантирует корректную передачу `receiver` через цепочку прототипов.

## Практические use cases

### 1. Валидация данных

```js
function createValidatedObject(schema) {
  return new Proxy({}, {
    set(target, prop, value) {
      const validator = schema[prop];
      if (validator && !validator(value)) {
        throw new TypeError(`Invalid value for "${prop}": ${value}`);
      }
      return Reflect.set(target, prop, value);
    },
  });
}

const user = createValidatedObject({
  age:   v => Number.isInteger(v) && v >= 0 && v <= 150,
  email: v => typeof v === 'string' && v.includes('@'),
});

user.age = 25;        // ✅
user.email = 'a@b.c'; // ✅
user.age = -1;        // ❌ TypeError: Invalid value for "age": -1
user.email = 'bad';   // ❌ TypeError: Invalid value for "email": bad
```

### 2. Реактивные системы — как работают Vue 3 и MobX

Это самый важный production use case. Реактивность в Vue 3 (`reactive()`) и наблюдаемые объекты в MobX построены именно на Proxy.

```js
// Упрощённая версия механизма Vue 3 reactive()
let currentEffect = null; // текущая "вычисляемая" функция

function track(target, prop) {
  if (currentEffect) {
    // Запомнить: этот effect зависит от target[prop]
    const deps = getDepsMap(target);
    if (!deps.has(prop)) deps.set(prop, new Set());
    deps.get(prop).add(currentEffect);
  }
}

function trigger(target, prop) {
  // При изменении target[prop] — перезапустить все зависимые effects
  getDepsMap(target).get(prop)?.forEach(effect => effect());
}

function reactive(obj) {
  return new Proxy(obj, {
    get(target, prop, receiver) {
      track(target, prop); // отслеживаем чтение
      return Reflect.get(target, prop, receiver);
    },
    set(target, prop, value, receiver) {
      const result = Reflect.set(target, prop, value, receiver);
      trigger(target, prop); // уведомляем зависимых
      return result;
    },
  });
}

// Использование:
const state = reactive({ count: 0, name: 'Vue' });

// watchEffect эквивалент:
function effect(fn) {
  currentEffect = fn;
  fn(); // запускаем, при этом отслеживаем какие свойства читались
  currentEffect = null;
}

effect(() => {
  console.log(`Count is: ${state.count}`); // читает count → track
});

state.count++; // trigger → effect перезапускается → 'Count is: 1'
state.name = 'React'; // trigger → НО никакой effect не читал name
                       // (в данном примере) → ничего не происходит
```

### 3. Proxy для автоматических значений по умолчанию (autovivification)

```js
function deepDefault(defaultFn) {
  return new Proxy({}, {
    get(target, prop) {
      if (!(prop in target)) {
        target[prop] = defaultFn();
      }
      return target[prop];
    },
  });
}

// Автоматические вложенные Map:
const counter = deepDefault(() => deepDefault(() => 0));

// В обычном объекте: нужно counter[a] ??= {}; counter[a][b] ??= 0
// С Proxy: просто читаем
counter['apple']['green']; // автоматически создаёт вложенность
```

### 4. Revocable Proxy — временный доступ

```js
const { proxy, revoke } = Proxy.revocable(sensitiveData, {
  get(target, prop, receiver) {
    console.log(`[access] ${prop}`);
    return Reflect.get(target, prop, receiver);
  },
});

// Передать proxy во временный контекст:
processData(proxy);

// Закрыть доступ — любое обращение к proxy после revoke() бросит TypeError
revoke();
proxy.anyProp; // TypeError: Cannot perform 'get' on a proxy that has been revoked
```

### 5. Логирующий Proxy для отладки

```js
function createLogger(target, name = 'obj') {
  return new Proxy(target, {
    get(t, p, r) {
      const value = Reflect.get(t, p, r);
      if (typeof value === 'function') {
        return function(...args) {
          console.log(`${name}.${p}(${args.map(a => JSON.stringify(a)).join(', ')})`);
          const result = value.apply(this === proxy ? t : this, args);
          console.log(`  → ${JSON.stringify(result)}`);
          return result;
        };
      }
      console.log(`get ${name}.${p} → ${JSON.stringify(value)}`);
      return value;
    },
    set(t, p, v, r) {
      console.log(`set ${name}.${p} = ${JSON.stringify(v)}`);
      return Reflect.set(t, p, v, r);
    },
  });
}

const proxy = createLogger({ x: 1 }, 'myObj');
proxy.x;      // get myObj.x → 1
proxy.x = 5;  // set myObj.x = 5
```

## Symbol — уникальные ключи и метапрограммирование

`Symbol` — примитивный тип, каждое значение которого **гарантированно уникально**:

```js
const s1 = Symbol('desc');
const s2 = Symbol('desc');
s1 === s2; // false — одинаковое описание, разные символы

// Описание — только для отладки, не влияет на идентичность
s1.toString();   // 'Symbol(desc)'
s1.description;  // 'desc'

// Как ключи объекта:
const KEY = Symbol('key');
const obj = { [KEY]: 'value', regular: 'prop' };
obj[KEY];            // 'value'
Object.keys(obj);    // ['regular'] — Symbol-ключи не видны
Object.getOwnPropertySymbols(obj); // [Symbol(key)]
JSON.stringify(obj); // '{"regular":"prop"}' — Symbol игнорируется
```

### Глобальный реестр: `Symbol.for` / `Symbol.keyFor`

```js
// Symbol.for — глобальный реестр: один ключ = один символ, везде
const a = Symbol.for('app.userId');
const b = Symbol.for('app.userId');
a === b; // true — один и тот же объект из реестра

// Работает между модулями и realm-ами (iframe, Worker)
Symbol.keyFor(a); // 'app.userId'
Symbol.keyFor(Symbol('local')); // undefined — не в реестре
```

## Well-Known Symbols — точки расширения языка

Спецификация определяет **well-known symbols** — предопределённые символы, через которые можно изменить поведение объекта в стандартных операциях.

### `Symbol.toPrimitive` — кастомное приведение типов

```js
class Money {
  constructor(amount, currency) {
    this.amount = amount;
    this.currency = currency;
  }

  [Symbol.toPrimitive](hint) {
    // hint: 'number' | 'string' | 'default'
    if (hint === 'number') return this.amount;
    if (hint === 'string') return `${this.amount} ${this.currency}`;
    return this.amount; // 'default' — для + и == операторов
  }
}

const price = new Money(42, 'USD');

+price;            // 42          — hint: 'number'
`${price}`;        // '42 USD'    — hint: 'string'
price + 0;         // 42          — hint: 'default'
price == 42;       // true        — hint: 'default'
```

### `Symbol.toStringTag` — кастомный `Object.prototype.toString`

```js
class MyCollection {
  get [Symbol.toStringTag]() {
    return 'MyCollection';
  }
}

const c = new MyCollection();
Object.prototype.toString.call(c); // '[object MyCollection]'

// Встроенные примеры:
Object.prototype.toString.call(new Map());     // '[object Map]'
Object.prototype.toString.call(Promise.resolve()); // '[object Promise]'
// Это то, что использует typeof-free type checking в библиотеках
```

### `Symbol.hasInstance` — кастомный `instanceof`

```js
class TypeChecker {
  static [Symbol.hasInstance](value) {
    return typeof value === 'number' && !isNaN(value) && isFinite(value);
  }
}

42 instanceof TypeChecker;       // true
NaN instanceof TypeChecker;      // false
Infinity instanceof TypeChecker; // false
'str' instanceof TypeChecker;    // false
```

### `Symbol.iterator` и `Symbol.asyncIterator`

Подробно разобраны в [Генераторы и итераторы]. Краткий пример кастомного итерируемого:

```js
class Range {
  constructor(start, end) {
    this.start = start;
    this.end = end;
  }

  [Symbol.iterator]() {
    let current = this.start;
    const end = this.end;
    return {
      next() {
        return current <= end
          ? { value: current++, done: false }
          : { value: undefined, done: true };
      },
    };
  }
}

[...new Range(1, 5)]; // [1, 2, 3, 4, 5]
for (const n of new Range(1, 3)) console.log(n); // 1, 2, 3
```

### `Symbol.isConcatSpreadable`

```js
const arrayLike = { 0: 'a', 1: 'b', length: 2 };
[].concat(arrayLike); // [{ 0: 'a', 1: 'b', length: 2 }] — не разворачивается

arrayLike[Symbol.isConcatSpreadable] = true;
[].concat(arrayLike); // ['a', 'b'] — теперь разворачивается как массив
```

## Predict the output — Proxy + Symbol

```js
const handler = {
  get(target, prop, receiver) {
    if (prop === Symbol.toPrimitive) {
      return (hint) => hint === 'number' ? target.value * 2 : String(target.value);
    }
    return Reflect.get(target, prop, receiver);
  },
  has(target, prop) {
    return prop === 'secret' ? false : Reflect.has(target, prop);
  },
};

const obj = new Proxy({ value: 21, real: true, secret: true }, handler);

console.log(+obj);           // ?
console.log(`${obj}`);       // ?
console.log('real' in obj);  // ?
console.log('secret' in obj); // ?
console.log('missing' in obj); // ?
```

<details>
<summary>Ответ</summary>

```
42       // +obj → hint 'number' → target.value * 2 = 42
21       // `${obj}` → hint 'string' → String(21) = '21'
true     // 'real' in obj → has не скрывает 'real' → Reflect.has → true
false    // 'secret' in obj → has скрывает 'secret' → false (хотя в target оно есть)
false    // 'missing' in obj → Reflect.has → false (реально отсутствует)
```

</details>

## Производительность Proxy

Proxy добавляет накладные расходы на каждую перехватываемую операцию. V8 не может инлайнить доступ к свойствам через Proxy так же эффективно, как к обычным объектам. В hot path с миллионами операций это заметно.

```txt
Практические рекомендации:
  ✅ Proxy для конфигурационных объектов, реактивного состояния
  ✅ Proxy для разового перехвата (валидация при создании, revocable доступ)
  ❌ Proxy в tight loop с миллионами итераций
  ❌ Proxy как замена кеша (накладные расходы на каждое чтение)
```

Vue 3 решает это проблемой через компилятор: шаблоны компилируются в код, который точно знает какие свойства реактивные и минимизирует трансп через Proxy.

## Связь с другими темами

```txt
[Прототипы]            — getPrototypeOf/setPrototypeOf ловушки, invariants
                          завязаны на прототипные механики
[Замыкания]            — handler замыкается на данные/состояние, это обычные
                          замыкания внутри ловушек
[Генераторы/Symbol]    — Symbol.iterator, Symbol.asyncIterator — well-known
                          symbols, реализующие протокол итерации
[Управление памятью]   — Proxy удерживает target; revocable proxy —
                          способ явно разорвать эту ссылку
```

## Типичные ошибки на интервью

- **"Proxy перехватывает любой доступ к свойствам"** — только через сам Proxy объект. Прямой доступ к `target` обходит все ловушки. Vue-компонент, случайно передавший raw target вместо proxy, теряет реактивность.

- **"В ловушке `get` можно использовать `target[prop]` вместо `Reflect.get`"** — обычно работает, но теряет `receiver`. При наследовании через прототипы с геттерами это даёт неверный `this` внутри геттера. Правильно: всегда `Reflect.get(target, prop, receiver)`.

- **"Proxy не имеет ограничений — можно перехватить всё"** — нет. Инварианты спецификации запрещают нарушать семантику non-writable/non-configurable свойств. Нарушение → TypeError. Это гарантирует, что Proxy не может "солгать" о неизменяемых свойствах.

- **"`Symbol.for('key') === Symbol('key')`"** — нет. `Symbol.for` возвращает из глобального реестра, `Symbol` всегда создаёт новый. `Symbol.for('key') === Symbol.for('key')` — true, но `Symbol('key') !== Symbol('key')`.

- **"Well-known symbols — это просто константы"** — нет. Это точки расширения языка. Объект с `[Symbol.iterator]()` участвует в `for...of`, spread, деструктуризации. Объект с `[Symbol.toPrimitive]()` управляет всеми неявными приведениями типов. Это мощнее, чем просто именованные методы.

- **Не знать, что `Symbol`-ключи не видны через `JSON.stringify`, `Object.keys`, `for...in`** — используются как "полупривате" ключи: видны через `Object.getOwnPropertySymbols`, но не в стандартных обходах. Это их главное практическое свойство.
