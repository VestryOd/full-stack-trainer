# this: A Deep Dive into Binding

## Why `this` is confusing — reframing the problem

`this` is not a variable. It's an **implicit parameter** of a function whose value is determined **at the moment of the call**, not at the moment of definition. That's why intuition tied to the lexical position of code fails here. To know the value of `this`, look not at where the function is written, but at **exactly how it is called**.

The spec defines four rules for resolving `this`. The engine applies them in strict priority order.

## The `this` resolution algorithm — four rules

### Rule 1: Default binding

Applies when a function is called as a **standalone call** — no receiver, no `new`, no `call/apply/bind`.

```js
function showThis() {
  console.log(this);
}

showThis(); // window (browser, sloppy mode) / global (Node.js, sloppy mode)
            // undefined (strict mode — browser and Node.js)
```

In **strict mode**, `this` under default binding = `undefined`. This is one reason `'use strict'` exists: in sloppy mode, an accidental `this.property = value` inside a standalone function silently created a property on the global object — a classic source of bugs.

```js
'use strict';
function strict() {
  console.log(this); // undefined
}

function sloppy() {
  console.log(this); // globalThis
}
```

### Rule 2: Implicit binding

Applies when a function is called **through an object** (a method call). `this` = the object **immediately to the left of the dot** at the call site.

```js
const user = {
  name: 'Alice',
  greet() {
    console.log(this.name);
  },
};

user.greet(); // 'Alice' — this = user
```

The keyword is "immediately." Only the direct receiver of the call:

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

outer.inner.greet(); // 'inner' — this = outer.inner, not outer
```

### Rule 3: Explicit binding

`Function.prototype.call`, `apply`, `bind` — explicitly state what `this` will be.

```js
function greet(greeting) {
  console.log(`${greeting}, ${this.name}`);
}

const user = { name: 'Bob' };

greet.call(user, 'Hello');           // 'Hello, Bob'   — called immediately
greet.apply(user, ['Hi']);           // 'Hi, Bob'       — called immediately, args as array
const boundGreet = greet.bind(user); // returns a NEW function
boundGreet('Hey');                   // 'Hey, Bob'      — called later
```

**`bind` internals**: creates a **bound function exotic object** with three internal slots:

```txt
BoundFunction {
  [[BoundTargetFunction]] → greet
  [[BoundThis]]           → user
  [[BoundArguments]]      → []
}
```

When a bound function is called, the engine uses `[[BoundThis]]` as `this` and prepends `[[BoundArguments]]` to the provided arguments. `call`/`apply` on a bound function **cannot override** `[[BoundThis]]` — it's permanently fixed (except for `new`, see below).

**Partial application:**

```js
function multiply(a, b) {
  return a * b;
}

const double = multiply.bind(null, 2); // [[BoundArguments]] = [2]
double(5);  // 10 — effectively multiply(2, 5)
double(10); // 20 — effectively multiply(2, 10)
```

**`call` vs `apply` difference** — only in how arguments are passed:

```js
// Equivalent calls:
fn.call(ctx, 1, 2, 3);
fn.apply(ctx, [1, 2, 3]);

// Practical example: apply is convenient with array-like data
const nums = [3, 1, 4, 1, 5, 9];
Math.max.apply(null, nums); // 9
// Modern JS equivalent: Math.max(...nums)
```

### Rule 4: new binding

When called via `new`, the `[[Construct]]` algorithm runs:

```txt
1. A new object is created: obj = Object.create(Fn.prototype)
2. Fn is called with this = obj
3. If Fn explicitly returns an object → that object is returned
   If Fn doesn't return an object (or returns a primitive/undefined)
   → obj is returned
```

```js
function Person(name) {
  this.name = name;
  // implicitly: return this (obj) — because there's no explicit return object
}

const alice = new Person('Alice');
alice.name; // 'Alice'

// The explicit return edge case:
function Weird() {
  this.value = 1;
  return { value: 99 }; // explicit return object → new returns THAT object
}
const w = new Weird();
w.value; // 99, not 1!
```

## Priority order

```txt
new  >  explicit (bind)  >  implicit  >  default

new:      new Fn()
explicit: fn.call/apply/bind(ctx)
implicit: obj.fn()
default:  fn()
```

Verifying that `new` beats `bind`:

```js
function Counter(start) {
  this.value = start;
}

const BoundCounter = Counter.bind({ value: 999 });
const c = new BoundCounter(0); // new wins over bind
c.value; // 0, not 999 — this under new = new object, not [[BoundThis]]
```

This isn't accidental — the spec explicitly states: `[[Construct]]` on a bound function ignores `[[BoundThis]]` and creates a new object through `[[BoundTargetFunction]].prototype`.

## Arrow functions — why they have no `this` of their own

An arrow function does not create its own `ThisBinding` in its Function Environment Record. This is not "syntactic sugar over `bind`" — it's a different environment record creation semantics.

When the engine creates an arrow function, it:
1. Does **NOT** create a `[[ThisValue]]` field in the function's Environment Record
2. Any access to `this` inside the arrow resolves via the Scope Chain — finding `this` in the **lexically enclosing** context

```js
const obj = {
  name: 'obj',
  regular() {
    console.log(this.name); // 'obj' — this from implicit binding
  },
  arrow: () => {
    console.log(this.name); // undefined (or globalThis.name)
    // this = lexically enclosing context — here it's the global context,
    // since an object literal doesn't create a new this
  },
};

obj.regular(); // 'obj'
obj.arrow();   // undefined
```

Arrows are especially useful in methods that need the object's `this` inside callbacks:

```js
class Timer {
  constructor() {
    this.count = 0;
  }

  start() {
    // Without arrow: this inside the callback = undefined (strict) or global
    setInterval(function() {
      this.count++; // ❌ this is lost
    }, 1000);

    // With arrow: this captured from lexical context (from start())
    setInterval(() => {
      this.count++; // ✅ this = the Timer instance
    }, 1000);
  }
}
```

**`call`/`apply`/`bind` on arrows — ignored for `this`:**

```js
const arrow = () => console.log(this);
const obj = { name: 'obj' };

arrow.call(obj);  // globalThis — this argument is ignored
arrow.bind(obj)(); // globalThis — bind doesn't change the arrow's this
// (arguments are still passed normally; only this is ignored)
```

## Common `this`-loss scenarios

### Scenario 1: Extracting a method from an object

```js
const user = {
  name: 'Alice',
  greet() { console.log(this.name); },
};

const greet = user.greet; // extraction — implicit binding is lost
greet(); // undefined (strict) / '' (globalThis.name in browser)
// this = globalThis, not user
```

**Why:** when calling `greet()` there's no object to the left of the dot. The binding to `user` only existed in the `user.greet()` syntax. The function itself carries no "memory" of the object.

### Scenario 2: Passing a method as a callback

```js
class Button {
  label = 'Click me';

  handleClick() {
    console.log(this.label);
  }
}

const btn = new Button();

document.addEventListener('click', btn.handleClick);
// ❌ handleClick is called as fn(), this = element or undefined (strict)

document.addEventListener('click', btn.handleClick.bind(btn)); // ✅
document.addEventListener('click', (e) => btn.handleClick(e)); // ✅
```

### Scenario 3: Destructuring class methods

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

**Three fixes — with different trade-offs:**

```js
class Api {
  baseUrl = 'https://api.example.com';

  // 1. Class field + arrow — bound in constructor,
  //    but: the method does NOT live on the prototype (a separate copy per instance)
  fetchUser = async (id) => {
    return fetch(`${this.baseUrl}/users/${id}`);
  };

  // 2. Regular method + bind in constructor — explicit, clear, but verbose
  fetchPost(id) {
    return fetch(`${this.baseUrl}/posts/${id}`);
  }
  constructor() {
    this.fetchPost = this.fetchPost.bind(this);
  }

  // 3. Don't destructure — always call via api.fetchUser()
}
```

### Scenario 4: setTimeout / setInterval

```js
class Poller {
  data = null;

  poll() {
    setTimeout(function() {
      this.data = fetch('/api/data'); // ❌ this = globalThis (or undefined)
    }, 1000);

    setTimeout(() => {
      this.data = fetch('/api/data'); // ✅ this = the Poller instance
    }, 1000);
  }
}
```

## Predict the output — a composite example

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
<summary>Answer</summary>

```
42          // obj.getValue() — implicit binding, this = obj
undefined   // getValueArrow: arrow, this = global (object literal doesn't create a new this)
undefined   // getValue() after destructuring — default binding, this = undefined (strict) / global
undefined   // getValueDelayed — setTimeout with function(), this = global
42          // getValueDelayedArrow — setTimeout with arrow, this captured from
            // getValueDelayedArrow() where this = obj (implicit binding on obj.getValueDelayedArrow())
```

</details>

## Hard binding via `bind` and override attempts

```js
function greet() {
  return this.name;
}

const alice = { name: 'Alice' };
const bob = { name: 'Bob' };

const greetAlice = greet.bind(alice);

greetAlice();                     // 'Alice'
greetAlice.call(bob);             // 'Alice' — bind cannot be overridden by call
greetAlice.bind(bob)();           // 'Alice' — bind on top of bind doesn't work either
new greetAlice();                 // '' — new ignores [[BoundThis]], this = new object
```

The only thing that "beats" bind is `new`.

## Connection to other topics

```txt
[Execution Contexts]    — ThisBinding is a separate field in the Execution
                           Context, unrelated to the Scope Chain
[Closures]              — arrow functions use this from the enclosing context —
                           this is where closure mechanics and this-binding intersect
[Prototypes]            — this inside a prototype-chain method always points to
                           the object the call was made on, not the prototype
                           where the method is defined
[Classes]               — class method in strict mode vs class field arrow
                           function — different trade-offs for this-binding
```

## Common interview traps

- **Confusing "where the function is written" with "how it is called"** — only the call site determines `this` (except for arrows and bound functions). The same function under different calling patterns produces different `this`.

- **"Arrow functions capture this from their parent via bind"** — no, it's a different mechanism. `bind` creates a new function with `[[BoundThis]]`. An arrow has no `ThisBinding` at all — accessing `this` resolves via the Scope Chain like any ordinary identifier. That's why `call/apply/bind` have no effect on an arrow's `this`.

- **Not knowing the priority order** — `new` beats `bind`; without this knowledge, a question like `new BoundFn()` is a dead end.

- **"An arrow method in an object literal captures the object's this"** — no. An object literal `{}` does not create a new execution context. The `this` of an arrow in `{ arrow: () => ... }` is the `this` of the lexically enclosing context (often global).

- **Not knowing that `bind` returns a bound function exotic object** — important for understanding why `bind(bind(fn, a), b)` doesn't change `this` (the outer bind wraps the bound function, but `[[BoundThis]]` is already fixed in the inner one).

- **Forgetting about strict mode for default binding** — `this = undefined` in strict mode vs `globalThis` in sloppy mode. In module code (ESM), strict mode is always on — this changes the default behavior.
