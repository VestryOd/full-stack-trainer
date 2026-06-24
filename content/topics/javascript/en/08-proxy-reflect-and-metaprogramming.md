# Proxy, Reflect, and Metaprogramming

## Proxy — intercepting fundamental operations

`Proxy` lets you wrap any object or function and intercept **internal methods** of ECMAScript — the low-level operations the engine performs on property access, assignment, function calls, and so on.

```js
const proxy = new Proxy(target, handler);
```

- `target` — any object, function, array, or another Proxy
- `handler` — an object with **trap** methods. Each trap corresponds to an internal method in the spec

If a trap is not defined, the operation passes through transparently to `target`.

### Full trap list

```txt
Trap                    Intercepts
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

### Trap invariants

Traps are not omnipotent — the spec requires **invariants** to be respected. Violations throw `TypeError`:

```js
const obj = {};
Object.defineProperty(obj, 'x', { value: 42, writable: false, configurable: false });

const proxy = new Proxy(obj, {
  get(target, prop) {
    return 100; // ❌ violation: a non-writable, non-configurable property
                // must return its actual value (42)
  },
});

proxy.x; // TypeError: 'get' on proxy: property 'x' is a non-configurable
          // and non-writable data property on the proxy target but the
          // proxy did not return its actual value
```

## Reflect — a mirror of internal methods

`Reflect` is an object with static methods that **exactly mirror the trap names** in Proxy. It provides a way to perform the "default behavior" inside a trap.

```txt
Reflect.get(target, prop, receiver)
Reflect.set(target, prop, value, receiver)
Reflect.has(target, prop)
Reflect.deleteProperty(target, prop)
Reflect.apply(target, thisArg, args)
Reflect.construct(target, args, newTarget)
// ... and so on for all 13 traps
```

### Why `Reflect` pairs with `Proxy` — the `receiver` problem

The most common Proxy mistake: forwarding `get` via `target[prop]` instead of `Reflect.get`.

```js
const obj = {
  _x: 10,
  get doubled() { return this._x * 2; }, // getter uses this
};

const naiveProxy = new Proxy(obj, {
  get(target, prop) {
    console.log(`get: ${prop}`);
    return target[prop]; // ← problem: this inside getter = target, not proxy
  },
});

const correctProxy = new Proxy(obj, {
  get(target, prop, receiver) {
    console.log(`get: ${prop}`);
    return Reflect.get(target, prop, receiver); // ← receiver is passed to the getter
  },
});
```

```js
// Why this matters: prototype chain + getter
const base = {
  get value() { return this._val; }
};
const child = Object.create(base);
child._val = 42;

const proxy = new Proxy(child, {
  get(target, prop, receiver) {
    return Reflect.get(target, prop, receiver); // receiver = proxy
    // When the 'value' getter accesses this._val,
    // this = receiver (proxy), which is correct
  },
});

proxy.value; // 42 ✅
// Without Reflect: this in the getter = base (prototype target), _val not found → undefined
```

**The rule**: always use `Reflect.*` inside a trap for the default operation — it guarantees correct `receiver` propagation through the prototype chain.

## Practical use cases

### 1. Data validation

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

### 2. Reactive systems — how Vue 3 and MobX work under the hood

This is the most important production use case. Reactivity in Vue 3 (`reactive()`) and observable objects in MobX are built exactly on Proxy.

```js
// Simplified version of Vue 3's reactive() mechanism
let currentEffect = null; // the currently-running "computed" function

function track(target, prop) {
  if (currentEffect) {
    // Remember: this effect depends on target[prop]
    const deps = getDepsMap(target);
    if (!deps.has(prop)) deps.set(prop, new Set());
    deps.get(prop).add(currentEffect);
  }
}

function trigger(target, prop) {
  // When target[prop] changes — re-run all dependent effects
  getDepsMap(target).get(prop)?.forEach(effect => effect());
}

function reactive(obj) {
  return new Proxy(obj, {
    get(target, prop, receiver) {
      track(target, prop); // track reads
      return Reflect.get(target, prop, receiver);
    },
    set(target, prop, value, receiver) {
      const result = Reflect.set(target, prop, value, receiver);
      trigger(target, prop); // notify dependents
      return result;
    },
  });
}

// Usage:
const state = reactive({ count: 0, name: 'Vue' });

// watchEffect equivalent:
function effect(fn) {
  currentEffect = fn;
  fn(); // run it; while running, track which properties are read
  currentEffect = null;
}

effect(() => {
  console.log(`Count is: ${state.count}`); // reads count → track
});

state.count++; // trigger → effect re-runs → 'Count is: 1'
state.name = 'React'; // trigger → but no effect read 'name'
                       // (in this example) → nothing happens
```

### 3. Auto-vivification (automatic default values)

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

// Automatic nested Maps:
const counter = deepDefault(() => deepDefault(() => 0));

// With a plain object: counter[a] ??= {}; counter[a][b] ??= 0
// With Proxy: just read it
counter['apple']['green']; // automatically creates the nested structure
```

### 4. Revocable Proxy — temporary access

```js
const { proxy, revoke } = Proxy.revocable(sensitiveData, {
  get(target, prop, receiver) {
    console.log(`[access] ${prop}`);
    return Reflect.get(target, prop, receiver);
  },
});

// Pass the proxy to a temporary context:
processData(proxy);

// Revoke access — any operation on proxy after revoke() throws TypeError
revoke();
proxy.anyProp; // TypeError: Cannot perform 'get' on a proxy that has been revoked
```

### 5. Logging Proxy for debugging

```js
function createLogger(target, name = 'obj') {
  const proxy = new Proxy(target, {
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
  return proxy;
}

const logged = createLogger({ x: 1 }, 'myObj');
logged.x;      // get myObj.x → 1
logged.x = 5;  // set myObj.x = 5
```

## Symbol — unique keys and metaprogramming

`Symbol` is a primitive type where each value is **guaranteed to be unique**:

```js
const s1 = Symbol('desc');
const s2 = Symbol('desc');
s1 === s2; // false — same description, different symbols

// The description is only for debugging, doesn't affect identity
s1.toString();   // 'Symbol(desc)'
s1.description;  // 'desc'

// As object keys:
const KEY = Symbol('key');
const obj = { [KEY]: 'value', regular: 'prop' };
obj[KEY];            // 'value'
Object.keys(obj);    // ['regular'] — Symbol keys are invisible
Object.getOwnPropertySymbols(obj); // [Symbol(key)]
JSON.stringify(obj); // '{"regular":"prop"}' — Symbol is ignored
```

### The global registry: `Symbol.for` / `Symbol.keyFor`

```js
// Symbol.for — global registry: one key = one symbol, across the entire runtime
const a = Symbol.for('app.userId');
const b = Symbol.for('app.userId');
a === b; // true — the same object from the registry

// Works across modules and realms (iframe, Worker)
Symbol.keyFor(a); // 'app.userId'
Symbol.keyFor(Symbol('local')); // undefined — not in the registry
```

## Well-Known Symbols — language extension points

The spec defines **well-known symbols** — predefined symbols through which you can alter an object's behavior in standard operations.

### `Symbol.toPrimitive` — custom type coercion

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
    return this.amount; // 'default' — for + and == operators
  }
}

const price = new Money(42, 'USD');

+price;            // 42          — hint: 'number'
`${price}`;        // '42 USD'    — hint: 'string'
price + 0;         // 42          — hint: 'default'
price == 42;       // true        — hint: 'default'
```

### `Symbol.toStringTag` — custom `Object.prototype.toString`

```js
class MyCollection {
  get [Symbol.toStringTag]() {
    return 'MyCollection';
  }
}

const c = new MyCollection();
Object.prototype.toString.call(c); // '[object MyCollection]'

// Built-in examples:
Object.prototype.toString.call(new Map());          // '[object Map]'
Object.prototype.toString.call(Promise.resolve()); // '[object Promise]'
// This is what libraries use for typeof-free type checking
```

### `Symbol.hasInstance` — custom `instanceof`

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

### `Symbol.iterator` and `Symbol.asyncIterator`

Covered in detail in [Generators and Iterators]. A brief custom iterable example:

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
[].concat(arrayLike); // [{ 0: 'a', 1: 'b', length: 2 }] — not spread

arrayLike[Symbol.isConcatSpreadable] = true;
[].concat(arrayLike); // ['a', 'b'] — now spread like an array
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

console.log(+obj);            // ?
console.log(`${obj}`);        // ?
console.log('real' in obj);   // ?
console.log('secret' in obj); // ?
console.log('missing' in obj); // ?
```

<details>
<summary>Answer</summary>

```
42     // +obj → hint 'number' → target.value * 2 = 42
21     // `${obj}` → hint 'string' → String(21) = '21'
true   // 'real' in obj → has doesn't hide 'real' → Reflect.has → true
false  // 'secret' in obj → has hides 'secret' → false (even though it exists in target)
false  // 'missing' in obj → Reflect.has → false (genuinely absent)
```

</details>

## Proxy performance

Proxy adds overhead to every intercepted operation. V8 cannot inline property accesses through a Proxy as efficiently as through plain objects. In hot paths with millions of operations, this is measurable.

```txt
Practical guidance:
  ✅ Proxy for config objects, reactive state
  ✅ Proxy for one-shot interception (validation on creation, revocable access)
  ❌ Proxy in tight loops with millions of iterations
  ❌ Proxy as a substitute for a cache (overhead on every read)
```

Vue 3 addresses this via its compiler: templates are compiled to code that knows exactly which properties are reactive, minimizing the number of Proxy traversals at runtime.

## Connection to other topics

```txt
[Prototypes]            — getPrototypeOf/setPrototypeOf traps; invariants
                           are tied to the prototype mechanics
[Closures]              — the handler closes over data/state; these are
                           ordinary closures inside trap methods
[Generators/Symbol]     — Symbol.iterator, Symbol.asyncIterator are well-known
                           symbols implementing the iteration protocol
[Memory Management]     — Proxy keeps target alive; revocable proxy provides
                           a way to explicitly sever that reference
```

## Common interview traps

- **"Proxy intercepts all property access"** — only through the Proxy object itself. Direct access to `target` bypasses all traps. A Vue component that accidentally receives the raw target instead of the proxy loses reactivity.

- **"In a `get` trap you can use `target[prop]` instead of `Reflect.get`"** — usually works, but loses `receiver`. With prototype-based inheritance and getters, this gives the wrong `this` inside the getter. Correct: always `Reflect.get(target, prop, receiver)`.

- **"Proxy has no limits — you can intercept anything"** — no. Spec invariants prevent lying about the semantics of non-writable/non-configurable properties. Violations throw `TypeError`. This guarantees Proxy cannot "lie" about immutable properties.

- **"`Symbol.for('key') === Symbol('key')`"** — no. `Symbol.for` retrieves from the global registry; `Symbol` always creates a new one. `Symbol.for('key') === Symbol.for('key')` is true, but `Symbol('key') !== Symbol('key')`.

- **"Well-known symbols are just constants"** — no. They are language extension points. An object with `[Symbol.iterator]()` participates in `for...of`, spread, and destructuring. An object with `[Symbol.toPrimitive]()` controls all implicit type coercions. More powerful than just named methods.

- **Not knowing that Symbol keys are invisible to `JSON.stringify`, `Object.keys`, `for...in`** — they act as "semi-private" keys: visible through `Object.getOwnPropertySymbols`, but invisible in standard iteration. This is their main practical property.
