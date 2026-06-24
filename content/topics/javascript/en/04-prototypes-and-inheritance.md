# Prototypes and Inheritance

## The confusing trio: `[[Prototype]]`, `__proto__`, `prototype`

The first step to understanding prototypes is separating three different things that are often referred to with the same word.

### `[[Prototype]]` — the internal slot

`[[Prototype]]` is a **spec-level internal slot** present on every object. It contains a reference to the prototype object or `null`. It's not directly accessible from code — only through specific APIs:

```js
const obj = {};
Object.getPrototypeOf(obj); // {} (Object.prototype) — the recommended way
Object.setPrototypeOf(obj, null); // set it (slow — avoid in hot code)
```

### `__proto__` — the legacy accessor

`__proto__` is a **get/set accessor** on `Object.prototype` that reads and writes `[[Prototype]]`. Technically not part of ECMAScript core — it's a V8/SpiderMonkey legacy, standardized in Annex B (the optional, browser-targeted appendix). Don't use it in new code.

```js
const obj = {};
obj.__proto__ === Object.getPrototypeOf(obj); // true
// __proto__ is just syntactic sugar over getPrototypeOf/setPrototypeOf
```

### `prototype` — a property on functions

`prototype` is a **regular property** on `Function` objects. It has nothing to do with the function's own `[[Prototype]]`. It's the object that becomes the `[[Prototype]]` of objects created via `new Fn()`:

```js
function Foo() {}

// Foo is a Function object:
Foo[[Prototype]] → Function.prototype   // how .call, .bind, etc. work on Foo
Foo.prototype   → { constructor: Foo }  // what becomes [[Prototype]] of new Foo() objects

const obj = new Foo();
// obj[[Prototype]] → Foo.prototype
// obj[[Prototype]][[Prototype]] → Object.prototype
// obj[[Prototype]][[Prototype]][[Prototype]] → null
```

```txt
Visual diagram:

  Foo (Function)
    .prototype ──────────────────────────────────────┐
    [[Prototype]] → Function.prototype               │
                                                     ▼
  obj = new Foo()                            Foo.prototype
    [[Prototype]] ──────────────────────────►  { constructor: Foo }
                                               [[Prototype]] → Object.prototype
                                                                [[Prototype]] → null
```

## Prototype chain resolution algorithm

When accessing a property `obj.prop`, the engine does the following:

```txt
1. Does obj have an own property 'prop'?
   → YES: return its value (search ends)
   → NO: go to step 2

2. Does obj have a [[Prototype]]?
   → NO (null): return undefined (search ends)
   → YES: go to step 3

3. Does obj[[Prototype]] have an own property 'prop'?
   → YES: return its value
   → NO: obj = obj[[Prototype]], go to step 2
```

```js
const base = { greet() { return 'hello'; } };
const child = Object.create(base);
const grandchild = Object.create(child);

grandchild.greet();
// 1. grandchild.greet — no own property
// 2. grandchild[[Prototype]] = child → child.greet — no own property
// 3. child[[Prototype]] = base → base.greet — FOUND → 'hello'

grandchild.missing;
// Traverse the full chain: grandchild → child → base → Object.prototype → null
// Not found → undefined
```

**Performance**: the chain walk happens **every time** a property is accessed (no language-level caching). V8 optimizes this through **hidden classes** and **inline caches**, but a deep chain is still slower than an own property.

## `Object.create` vs constructor function vs `class`

### `Object.create` — direct prototype assignment

```js
const animalMethods = {
  speak() {
    return `${this.name} makes a sound`;
  },
  toString() {
    return `[Animal: ${this.name}]`;
  },
};

const dog = Object.create(animalMethods);
dog.name = 'Rex';
dog.speak(); // 'Rex makes a sound'

Object.getPrototypeOf(dog) === animalMethods; // true

// Special case: an object with no prototype (null-prototype object)
const bare = Object.create(null);
bare.key = 'value';
// bare has no toString, hasOwnProperty, or other Object.prototype methods
// Used for "pure" dictionaries with no risk of key collisions
```

### Constructor function — ES5 style

```js
function Animal(name, sound) {
  this.name = name;
  this.sound = sound;
}

Animal.prototype.speak = function() {
  return `${this.name} says ${this.sound}`;
};

Animal.prototype.toString = function() {
  return `[Animal: ${this.name}]`;
};

function Dog(name) {
  Animal.call(this, name, 'woof'); // super() by hand
}

// Setting up the prototype chain:
Dog.prototype = Object.create(Animal.prototype);
Dog.prototype.constructor = Dog; // restore constructor (overwritten above)

Dog.prototype.fetch = function() {
  return `${this.name} fetches the ball`;
};

const rex = new Dog('Rex');
rex.speak();           // 'Rex says woof' (from Animal.prototype)
rex.fetch();           // 'Rex fetches the ball' (from Dog.prototype)
rex instanceof Dog;    // true
rex instanceof Animal; // true
```

### `class` — what it actually compiles to

`class` is **syntactic sugar** over the same prototype mechanism. Nothing fundamentally new is introduced at runtime, but there are important differences from manual constructors:

```js
class Animal {
  constructor(name, sound) {
    this.name = name;
    this.sound = sound;
  }

  speak() {
    return `${this.name} says ${this.sound}`;
  }

  static create(name, sound) {
    return new Animal(name, sound);
  }
}

class Dog extends Animal {
  constructor(name) {
    super(name, 'woof'); // required before any reference to this
  }

  fetch() {
    return `${this.name} fetches the ball`;
  }
}

// Conceptual equivalent (simplified):
function Animal(name, sound) {
  this.name = name;
  this.sound = sound;
}
Object.defineProperty(Animal.prototype, 'speak', {
  value: function() { return `${this.name} says ${this.sound}`; },
  writable: true,
  configurable: true,
  enumerable: false, // ← class methods are non-enumerable!
                     //   manually assigned prototype methods are enumerable
});
Animal.create = function(name, sound) { return new Animal(name, sound); };
```

**Key differences between `class` and a manual constructor:**

```txt
1. Class methods are non-enumerable (for...in won't see them)
   Prototype methods assigned manually are enumerable by default

2. class invokes [[Construct]], not [[Call]]:
   Animal() without new → TypeError ("Class constructor cannot be invoked without 'new'")
   function Animal() {} without new → just runs

3. extends sets up TWO chains:
   Dog.prototype[[Prototype]] = Animal.prototype  (instance chain)
   Dog[[Prototype]]           = Animal            (static method chain)

4. super() in a subclass constructor is required before this:
   before super(), this has no value (TDZ-like state)
```

```js
// Verifying the static chain:
class A {
  static hello() { return 'A'; }
}
class B extends A {}

B.hello(); // 'A' — via the chain B[[Prototype]] = A
Object.getPrototypeOf(B) === A;                  // true
Object.getPrototypeOf(B.prototype) === A.prototype; // true
```

## `instanceof` mechanics

`obj instanceof Fn` runs the following algorithm:

```txt
1. If Fn has Symbol.hasInstance → call it (custom logic)
2. Otherwise: take target = Fn.prototype
3. Walk the [[Prototype]] chain of obj:
   - If the current [[Prototype]] === target → true
   - If [[Prototype]] === null → false (reached the end without a match)
```

```js
function Foo() {}
const foo = new Foo();

foo instanceof Foo;    // true — foo[[Prototype]] === Foo.prototype
foo instanceof Object; // true — Foo.prototype[[Prototype]] === Object.prototype

// Trap: instanceof looks at Fn.prototype, not Fn itself
const arr = [];
arr instanceof Array;  // true
arr instanceof Object; // true — Array.prototype[[Prototype]] === Object.prototype

// If prototype is replaced after object creation:
function Bar() {}
const bar = new Bar();
Bar.prototype = {}; // replace prototype

bar instanceof Bar; // false! bar[[Prototype]] = OLD Bar.prototype,
                    // but Bar.prototype is now a different object
```

**Custom `Symbol.hasInstance`:**

```js
class EvenNumber {
  static [Symbol.hasInstance](value) {
    return typeof value === 'number' && value % 2 === 0;
  }
}

2 instanceof EvenNumber;  // true
3 instanceof EvenNumber;  // false
4 instanceof EvenNumber;  // true
```

## Property shadowing

An own property **shadows** a prototype property — the search stops at the first match.

```js
const proto = { x: 1 };
const obj = Object.create(proto);

obj.x; // 1 — from the prototype (no own property)

obj.x = 2; // creates an own property obj.x

obj.x;       // 2 — own property (shadows the prototype one)
proto.x;     // 1 — prototype is unchanged

// Removing the shadow:
delete obj.x;
obj.x; // 1 — back to the prototype
```

**Non-obvious case: a setter in the prototype blocks shadowing:**

```js
const proto = {};
Object.defineProperty(proto, 'x', {
  get() { return this._x; },
  set(v) { this._x = v * 2; }, // setter writes to _x, not x!
  configurable: true,
});

const obj = Object.create(proto);
obj.x = 5;
// The assignment obj.x = 5 does NOT create an own property!
// Instead, the setter from the prototype is called with this = obj
// The setter writes this._x = 10

obj.x;   // 10 (via getter from the prototype, reads this._x)
obj._x;  // 10 (own property, created by the setter)
Object.hasOwn(obj, 'x'); // false! x is NOT an own property of obj
```

This is one of the most non-obvious aspects of prototypal inheritance.

## Predict the output — prototype chain

```js
function Person(name) {
  this.name = name;
}
Person.prototype.greet = function() {
  return `Hi, I'm ${this.name}`;
};

function Employee(name, role) {
  Person.call(this, name);
  this.role = role;
}
Employee.prototype = Object.create(Person.prototype);
Employee.prototype.constructor = Employee;
Employee.prototype.describe = function() {
  return `${this.greet()}, I work as ${this.role}`;
};

const emp = new Employee('Alice', 'Engineer');

console.log(emp.name);                          // ?
console.log(emp.greet());                       // ?
console.log(emp.describe());                    // ?
console.log(emp instanceof Employee);           // ?
console.log(emp instanceof Person);             // ?
console.log(Object.hasOwn(emp, 'name'));        // ?
console.log(Object.hasOwn(emp, 'greet'));       // ?
console.log(emp.constructor === Employee);      // ?
```

<details>
<summary>Answer</summary>

```
'Alice'                                       // Person.call set this.name
'Hi, I\'m Alice'                              // found in Person.prototype
'Hi, I\'m Alice, I work as Engineer'          // describe calls this.greet() via the chain
true                                          // emp[[Prototype]] = Employee.prototype
true                                          // Employee.prototype[[Prototype]] = Person.prototype
true                                          // name is an own property (Person.call(this, name))
false                                         // greet is in the prototype, not own
true                                          // we manually restored constructor
```

If the line `Employee.prototype.constructor = Employee` were missing:
- `emp.constructor` → `Person` (inherited from Person.prototype, because `Employee.prototype = Object.create(Person.prototype)` overwrote the original constructor)

</details>

## Null-prototype objects and `Object.create(null)`

```js
const dict = Object.create(null);
dict.hasOwnProperty; // undefined — no Object.prototype in the chain!
dict.toString;       // undefined
dict.__proto__;      // undefined

// A safe dictionary: keys can't collide with Object.prototype methods
dict['constructor'] = 'safe'; // OK, doesn't affect Object.prototype.constructor
dict['toString']    = 'safe'; // OK

// Usage:
Object.prototype.hasOwnProperty.call(dict, 'key'); // safe check
// or:
Object.hasOwn(dict, 'key'); // ES2022, doesn't need Object.prototype
```

Used in cache implementations, dictionaries, and data-record objects where complete isolation from prototype methods is important.

## Connection to other topics

```txt
[Execution Contexts]    — this inside a prototype method = the object
                           the call was made on (implicit binding),
                           not the object where the method is defined
[this binding]          — same principle: this for rex.speak() = rex,
                           even though speak is defined on Animal.prototype
[Proxy and Reflect]     — Reflect.get(target, prop, receiver) reproduces
                           prototype lookup explicitly; Proxy intercepts it
[Classes]               — class is syntactic sugar, but with real differences
                           (non-enumerable methods, TDZ before super())
```

## Common interview traps

- **Confusing `__proto__` and `prototype`** — `__proto__` exists on every object and points to its `[[Prototype]]`; `prototype` only exists on functions and points to the `[[Prototype]]` of future instances. Different things with similar names.

- **"class creates something fundamentally new"** — no. Under the hood it's the same `[[Prototype]]` chains. The differences are real but in the details: non-enumerable methods, mandatory `super()`, static chain via `extends`.

- **"instanceof checks the type"** — no, it checks whether `Fn.prototype` is present in the object's `[[Prototype]]` chain. It breaks if `Fn.prototype` is replaced after creating objects, or for objects from different realms (e.g., `iframe`).

- **Not knowing that class methods are non-enumerable** — consequence: `for...in` over a class instance won't show methods, but `for...in` over an object with manual prototype assignments will.

- **"A setter in the prototype works like assigning an own property"** — no. If a setter for a property exists in the `[[Prototype]]` chain, `obj.prop = val` invokes the setter rather than creating an own property `obj.prop`. A frequent trap in inheritance patterns.

- **Not restoring `constructor` when manually setting up the prototype chain** — `Derived.prototype = Object.create(Base.prototype)` overwrites `Derived.prototype.constructor`. Without explicitly restoring it, `emp.constructor` will point to `Base`, breaking reflection and some patterns.
