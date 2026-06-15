# V8 and Node.js Runtime

## V8 is a pipeline, not "one compiler"

V8 doesn't compile code entirely up front, and it doesn't interpret it line by line forever — it's a multi-stage pipeline that **progressively raises compilation quality for hot code** and falls back if assumptions about that code turn out to be wrong.

```txt
Source code
    ↓
Parser → AST (Abstract Syntax Tree)
    ↓
Ignition (baseline interpreter) → Bytecode
    ↓ (if the function is called often — "hot")
TurboFan (optimizing JIT compiler) → optimized machine code
    ↑ ↓
    └── Deoptimization (if assumptions are violated —
        falls back to bytecode, see below)
```

The main practical takeaway from this diagram: V8 optimizes code **based on observed behavior**, not static type analysis (unlike, say, TypeScript at compile time). This means the same code can run at different speeds depending on what data has flowed through it before — which is why "warm-up" is a real phenomenon worth accounting for in load testing Node services.

## Ignition and TurboFan: baseline vs optimized

```txt
Ignition:
  - starts running the function immediately, no compile delay
  - generates compact bytecode
  - collects feedback (a profile of argument types, object shapes)

TurboFan:
  - kicks in once V8 sees a function is "hot"
    (called many times with the same "profile")
  - uses Ignition's feedback to generate machine code
    specialized for the OBSERVED types
  - the result is machine code several times faster than
    interpreted code, but valid ONLY for that type profile
```

```ts
function add(a: number, b: number) {
  return a + b;
}

// If add is called thousands of times ALWAYS with numbers —
// TurboFan generates machine code that expects numbers
// (e.g., uses an unboxed SMI representation)
for (let i = 0; i < 100_000; i++) add(i, i + 1);

// A sudden call with a different type — the TurboFan code is
// no longer valid for this case → DEOPTIMIZATION
add('5', '10'); // V8 falls back to Ignition bytecode for this
                 // call site (at minimum, for it)
```

## Deoptimization — the flip side of JIT that's rarely discussed

Deoptimization isn't an "error" — it's a normal V8 mechanism: when optimized code hits a situation it wasn't specialized for (a different argument type, a changed object shape, a deleted property), V8 **falls back** to bytecode execution for that part of the code, losing TurboFan's benefits on that path.

```ts
// ❌ A polymorphic function — called with objects of different "shapes"
function getArea(shape) {
  return shape.width * shape.height;  // Circle has no height!
}

getArea({ width: 10, height: 5 });          // Rectangle-like shape
getArea({ width: 10, radius: 5 });          // a different "shape" → polymorphic call site
```

Senior nuance: one or two polymorphic types at a call site (bimorphic) is fine — V8 handles a small number of shapes reasonably well. The problem starts with **megamorphic** call sites (many different object shapes flow through the same function) — V8 stops trying to specialize the code and falls back to the slowest generic path. For hot paths (parsing thousands of records in a loop, middleware handlers on every request), the shape of objects flowing through a function genuinely matters for performance.

## Hidden Classes (Shapes) and why an object's shape matters

V8 doesn't store objects as a "property name → value" hash map — that would be too slow for property access. Instead, each object is associated with a **Hidden Class** (internally called a "Map" or "Shape") that describes the in-memory layout of properties — similar to how a C++ compiler knows the field offsets of a struct.

```ts
// Both objects are created with the SAME order and set of properties
const user1 = { name: 'Alice', age: 30 };
const user2 = { name: 'Bob', age: 25 };
// → user1 and user2 share the same Hidden Class
// → functions operating on such objects can be monomorphic and fast

// ❌ Changing the shape of an object AFTER creation —
// creates a NEW Hidden Class for this specific object
const user3 = { name: 'Carol', age: 28 };
user3.address = 'London';  // a new Hidden Class, different from user1/user2

// ❌ Deleting a property — also creates a new (and often
// "slow", dictionary-mode) Hidden Class
delete user3.age;
```

```txt
Practical consequence — constructors/factories should ALWAYS
initialize ALL fields of an object, even if the value isn't
known yet:

  ❌ class User {
       constructor(name) {
         this.name = name;
         // address is added later, in a different method
       }
     }

  ✅ class User {
       constructor(name, address = null) {
         this.name = name;
         this.address = address;  // the field exists from the
                                   // start, even if null
       }
     }
```

This isn't a "micro-optimization for enthusiasts" — for code that creates thousands of same-shaped objects on a hot path (e.g., mapping DB rows to DTOs), consistent object shapes directly determine whether V8 stays in its "fast" mode or falls back to dictionary-mode property storage.

## Inline Caches — a cache of "where to find this property"

Inline Cache (IC) is a mechanism that complements Hidden Classes: for each place in the code where a property is accessed (`obj.name`), V8 remembers the object's Hidden Class and the property's offset **right at that code site**.

```txt
function getName(obj) {
  return obj.name;  // ← V8 creates an Inline Cache here
}

First call getName(user1):
  - V8 sees user1's Hidden Class
  - remembers: "for this Hidden Class, name is at offset 0"
  - the IC becomes monomorphic (1 remembered shape)

Subsequent calls with objects of the SAME Hidden Class:
  - V8 reads offset 0 directly, no property lookup — very fast

A call with an object of a DIFFERENT Hidden Class:
  - the IC becomes polymorphic (remembers 2-4 shapes)
  - past the shape limit → megamorphic, the IC stops helping,
    a generic lookup is used
```

Hidden Classes and Inline Caches are two sides of the same idea: V8 tries to turn JS's dynamic nature ("any property can be added/removed at any time") into static, predictable structures similar to those in compiled languages — but this only works as long as the code actually behaves predictably.

## The Heap: where V8 stores objects, and why it matters for GC

```txt
Stack:
  - primitives, references, function call frames
  - managed automatically on function enter/exit

Heap — split into "generations" (the generational hypothesis:
most objects die young):

  New Space (Young Generation):
    - new objects are created here
    - small size → garbage collection here (Scavenger) —
      FREQUENT but FAST (most objects are already dead)

  Old Space (Old Generation):
    - objects that "survive" several Scavenger cycles get
      "promoted" here
    - collection here (Mark-Compact/Mark-Sweep) — LESS FREQUENT
      but EXPENSIVE (a full traversal of the object graph)
```

The full breakdown of GC algorithms, practical memory-leak patterns, and heap snapshots is in [Memory and Garbage Collection]; the connection worth fixing here is: whether an object created in New Space quickly dies or gets "promoted" to Old Space is directly tied to Hidden Classes and object shapes — reusing same-shaped objects in hot loops reduces GC pressure, not just speeding up property access.

## Runtime = V8 + Node APIs + libuv

```txt
V8 can:           V8 CANNOT (and that's fine — it's not
  - run JS           its responsibility):
  - manage the heap    - read files
  - JIT/deopt           - open sockets
  - GC                   - work with OS timers
                         - resolve DNS
```

Node fills this gap:

```txt
fs, net, http, crypto, timers, dgram, ...
    ↓ (C++ bindings)
libuv — provides the event loop and thread pool
    ↓
OS system calls (epoll/kqueue/IOCP, read a file, ...)
```

This chain is covered further in [The Event Loop] and [libuv and the Thread Pool] — the key thing here is understanding that when you write `await fs.promises.readFile(...)`, the execution path crosses ALL three layers: V8 runs your async code and manages the Promise (see [Microtasks, Macrotasks, and process.nextTick]), the Node API wraps the call into a form libuv understands, and libuv decides how to physically perform the operation (via the thread pool or a native OS async API).

## Practical takeaway: when V8 internals actually matter

```txt
MATTERS:
  - hot paths with thousands/millions of iterations (parsing,
    data mapping, computation in a loop)
  - libraries/frameworks that ALL traffic flows through
    (ORM row-to-object mapping, validators, serializers)
  - data structure choices for frequently mutated objects
    with unpredictable shape (a Map instead of a plain object,
    if keys are dynamic)

ALMOST NEVER matters:
  - "handle one HTTP request" business logic — a nanosecond
    difference in property access disappears next to
    milliseconds of I/O (DB call, network)
  - micro-optimizations that hurt readability for the sake of
    "monomorphism" at a call site invoked 10 times in the
    process's entire lifetime
```

This is a deliberate calibration worth voicing in an interview: knowing about Hidden Classes/ICs demonstrates engine understanding, but applying that knowledge imperatively ("always initialize every field in the constructor, even unused ones") in code that isn't a hot path is an example of optimizing where it isn't needed — and that's also a signal (a negative one, in this case) in a senior interview.

## Common interview mistakes

- **"V8 interprets JS"** — without mentioning Ignition (baseline bytecode) and TurboFan (optimizing JIT), and that modern V8 is a multi-stage pipeline, not a pure interpreter.

- **Hidden Classes as "just a Wikipedia fact"** — without tying it to a concrete consequence: inconsistent field initialization or dynamically adding/removing properties creates new Hidden Classes and can deoptimize hot functions.

- **Not knowing about deoptimization** — treating JIT as "compiled once, always fast" without understanding that V8 can fall back to bytecode if type assumptions are violated.

- **Confusing V8 and Node** — attributing fs/net/http capabilities to V8 when they're actually provided by Node via libuv and C++ bindings.

- **Applying micro-optimizations in the wrong place** — over-engineering ordinary business code "for V8's sake" when the real bottleneck is I/O, not property access.
