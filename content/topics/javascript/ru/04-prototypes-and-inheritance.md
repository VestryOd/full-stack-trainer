# Прототипы и наследование

## Запутанное трио: `[[Prototype]]`, `__proto__`, `prototype`

Первый шаг к пониманию прототипов — разобраться в трёх разных вещах, которые часто называют одним словом.

### `[[Prototype]]` — внутренний слот

`[[Prototype]]` — это **внутренний слот** спецификации, присутствующий у каждого объекта. Он содержит ссылку на объект-прототип или `null`. Напрямую из кода недоступен — только через специальные API:

```js
const obj = {};
Object.getPrototypeOf(obj); // {} (Object.prototype) — рекомендуемый способ
Object.setPrototypeOf(obj, null); // установить (медленно, не делайте в hot code)
```

### `__proto__` — устаревший аксессор

`__proto__` — это **get/set аксессор** на `Object.prototype`, который читает и пишет `[[Prototype]]`. Технически это не часть ECMAScript core — это наследие V8/SpiderMonkey, стандартизированное в Annex B (опциональная часть спека, для браузеров). Не использовать в новом коде.

```js
const obj = {};
obj.__proto__ === Object.getPrototypeOf(obj); // true
// __proto__ — это просто синтаксический сахар над getPrototypeOf/setPrototypeOf
```

### `prototype` — свойство функций

`prototype` — это **обычное свойство** на объектах типа `Function`. Оно не имеет отношения к `[[Prototype]]` самой функции. Это объект, который становится `[[Prototype]]` объектов, созданных через `new Fn()`:

```js
function Foo() {}

// Foo — это Function object:
Foo[[Prototype]] → Function.prototype   // как к Foo применяются методы .call, .bind, etc.
Foo.prototype   → { constructor: Foo }  // что станет [[Prototype]] объектов new Foo()

const obj = new Foo();
// obj[[Prototype]] → Foo.prototype
// obj[[Prototype]][[Prototype]] → Object.prototype
// obj[[Prototype]][[Prototype]][[Prototype]] → null
```

```txt
Диаграмма для наглядности:

  Foo (Function)
    .prototype ──────────────────────────────────────┐
    [[Prototype]] → Function.prototype               │
                                                     ▼
  obj = new Foo()                            Foo.prototype
    [[Prototype]] ──────────────────────────►  { constructor: Foo }
                                               [[Prototype]] → Object.prototype
                                                                [[Prototype]] → null
```

## Алгоритм разрешения прототипной цепочки

При обращении к свойству `obj.prop` движок выполняет следующее:

```txt
1. Есть ли у obj собственное свойство 'prop'?
   → ДА: вернуть его значение (конец поиска)
   → НЕТ: перейти к шагу 2

2. Есть ли у obj[[Prototype]]?
   → НЕТ (null): вернуть undefined (конец поиска)
   → ДА: перейти к шагу 3

3. Есть ли у obj[[Prototype]] собственное свойство 'prop'?
   → ДА: вернуть его значение
   → НЕТ: obj = obj[[Prototype]], перейти к шагу 2
```

```js
const base = { greet() { return 'hello'; } };
const child = Object.create(base);
const grandchild = Object.create(child);

grandchild.greet();
// 1. grandchild.greet — нет собственного
// 2. grandchild[[Prototype]] = child → child.greet — нет собственного
// 3. child[[Prototype]] = base → base.greet — НАЙДЕНО → 'hello'

grandchild.missing;
// Проходим всю цепочку: grandchild → child → base → Object.prototype → null
// Не найдено → undefined
```

**Производительность**: поиск по цепочке происходит **каждый раз** при обращении к свойству (без кеширования на уровне языка). V8 оптимизирует это через **hidden classes** и **inline caches**, но глубокая цепочка всё равно медленнее, чем собственное свойство.

## `Object.create` vs конструктор vs `class`

### `Object.create` — прямое задание прототипа

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

// Особый случай: объект без прототипа (null-prototype object)
const bare = Object.create(null);
bare.key = 'value';
// У bare нет toString, hasOwnProperty и других методов Object.prototype
// Используется для "чистых" словарей без риска коллизий ключей
```

### Конструкторная функция — ES5-стиль

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
  Animal.call(this, name, 'woof'); // super() вручную
}

// Настройка цепочки прототипов:
Dog.prototype = Object.create(Animal.prototype);
Dog.prototype.constructor = Dog; // восстанавливаем constructor (затёрт выше)

Dog.prototype.fetch = function() {
  return `${this.name} fetches the ball`;
};

const rex = new Dog('Rex');
rex.speak();  // 'Rex says woof' (из Animal.prototype)
rex.fetch();  // 'Rex fetches the ball' (из Dog.prototype)
rex instanceof Dog;    // true
rex instanceof Animal; // true
```

### `class` — во что это компилируется

`class` — это **синтаксический сахар** над той же прототипной механикой. Принципиально нового в runtime не появляется, но есть важные отличия от ручных конструкторов:

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
    super(name, 'woof'); // обязательно до обращения к this
  }

  fetch() {
    return `${this.name} fetches the ball`;
  }
}

// Концептуальный эквивалент (упрощённо):
function Animal(name, sound) {
  this.name = name;
  this.sound = sound;
}
Object.defineProperty(Animal.prototype, 'speak', {
  value: function() { return `${this.name} says ${this.sound}`; },
  writable: true,
  configurable: true,
  enumerable: false, // ← методы класса не enumerable! конструктор-версия — enumerable
});
Animal.create = function(name, sound) { return new Animal(name, sound); };
```

**Ключевые отличия `class` от конструктора вручную:**

```txt
1. Методы класса — non-enumerable (for...in их не обходит)
   Методы на prototype вручную — enumerable по умолчанию

2. class вызывает [[Construct]], а не [[Call]]:
   Animal() без new → TypeError ("Class constructor cannot be invoked without 'new'")
   function Animal() {} без new → просто вызывается

3. extends настраивает ДВЕ цепочки:
   Dog.prototype[[Prototype]] = Animal.prototype  (цепочка экземпляров)
   Dog[[Prototype]]           = Animal            (цепочка статических методов)

4. super() в конструкторе подкласса обязателен до this:
   до super() у this нет значения (TDZ-подобное состояние)
```

```js
// Проверка статической цепочки:
class A {
  static hello() { return 'A'; }
}
class B extends A {}

B.hello(); // 'A' — через цепочку B[[Prototype]] = A
Object.getPrototypeOf(B) === A; // true
Object.getPrototypeOf(B.prototype) === A.prototype; // true
```

## Механика `instanceof`

`obj instanceof Fn` выполняет следующий алгоритм:

```txt
1. Если у Fn есть Symbol.hasInstance → вызвать его (кастомная логика)
2. Иначе: взять target = Fn.prototype
3. Пройти по [[Prototype]]-цепочке obj:
   - Если очередной [[Prototype]] === target → true
   - Если [[Prototype]] === null → false (дошли до конца без совпадения)
```

```js
function Foo() {}
const foo = new Foo();

foo instanceof Foo;    // true — foo[[Prototype]] === Foo.prototype
foo instanceof Object; // true — Foo.prototype[[Prototype]] === Object.prototype

// Ловушка: instanceof смотрит на Fn.prototype, а не на Fn саму по себе
const arr = [];
arr instanceof Array;  // true
arr instanceof Object; // true — Array.prototype[[Prototype]] === Object.prototype

// Если подменить prototype после создания:
function Bar() {}
const bar = new Bar();
Bar.prototype = {}; // заменяем prototype

bar instanceof Bar; // false! bar[[Prototype]] = СТАРЫЙ Bar.prototype,
                    // а Bar.prototype теперь — новый объект
```

**Кастомный `Symbol.hasInstance`:**

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

## Shadowing (затенение свойств)

Собственное свойство **затеняет** свойство прототипа — поиск останавливается на первом найденном.

```js
const proto = { x: 1 };
const obj = Object.create(proto);

obj.x; // 1 — из прототипа (нет собственного)

obj.x = 2; // создаём собственное свойство obj.x

obj.x;       // 2 — собственное (затеняет прототипное)
proto.x;     // 1 — прототип не изменён

// Удаление затенения:
delete obj.x;
obj.x; // 1 — снова из прототипа
```

**Неочевидный кейс: setter в прототипе блокирует затенение:**

```js
const proto = {};
Object.defineProperty(proto, 'x', {
  get() { return this._x; },
  set(v) { this._x = v * 2; }, // setter изменяет _x, а не x!
  configurable: true,
});

const obj = Object.create(proto);
obj.x = 5;
// Присваивание obj.x = 5 НЕ создаёт собственное свойство!
// Вместо этого вызывается setter из прототипа с this = obj
// Setter пишет this._x = 10

obj.x;   // 10 (через getter из прототипа, читает this._x)
obj._x;  // 10 (собственное свойство, созданное setter-ом)
Object.hasOwn(obj, 'x'); // false! x — не собственное свойство obj
```

Это один из самых неочевидных аспектов прототипного наследования.

## Predict the output — цепочка прототипов

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
<summary>Ответ</summary>

```
'Alice'                          // Person.call установил this.name
'Hi, I\'m Alice'                 // найдено в Person.prototype
'Hi, I\'m Alice, I work as Engineer' // describe вызывает this.greet() через цепочку
true                             // emp[[Prototype]] = Employee.prototype
true                             // Employee.prototype[[Prototype]] = Person.prototype
true                             // name — собственное свойство (Person.call(this, name))
false                            // greet — в прототипе, не собственное
true                             // мы вручную восстановили constructor
```

Если бы строка `Employee.prototype.constructor = Employee` отсутствовала:
- `emp.constructor` → `Person` (унаследовано из Person.prototype, так как `Employee.prototype = Object.create(Person.prototype)` затёрло constructor)

</details>

## Null-prototype объекты и `Object.create(null)`

```js
const dict = Object.create(null);
dict.hasOwnProperty; // undefined — нет Object.prototype в цепочке!
dict.toString;       // undefined
dict.__proto__;      // undefined

// Безопасный словарь: ключи не могут конфликтовать с методами Object.prototype
dict['constructor'] = 'safe'; // OK, не затрагивает Object.prototype.constructor
dict['toString']    = 'safe'; // OK

// Использование:
Object.prototype.hasOwnProperty.call(dict, 'key'); // безопасная проверка
// или:
Object.hasOwn(dict, 'key'); // ES2022, не нужен Object.prototype
```

Используется в реализациях кешей, словарей и объектов-записей там, где важна полная изоляция от прототипных методов.

## Связь с другими темами

```txt
[Контексты выполнения] — this внутри метода прототипа = объект, через
                          который сделан вызов (implicit binding),
                          а не объект, где метод определён
[this-binding]         — тот же принцип: this при rex.speak() = rex,
                          хотя speak определён в Animal.prototype
[Proxy и Reflect]      — Reflect.get(target, prop, receiver) воспроизводит
                          прототипный поиск явно; Proxy перехватывает его
[Классы]               — class — синтаксический сахар, но с важными
                          отличиями (non-enumerable методы, TDZ до super())
```

## Типичные ошибки на интервью

- **Путать `__proto__` и `prototype`** — `__proto__` есть у каждого объекта и указывает на его `[[Prototype]]`; `prototype` — только у функций и указывает на `[[Prototype]]` будущих экземпляров. Разные вещи с похожими названиями.

- **"class создаёт что-то принципиально новое"** — нет. Под капотом те же `[[Prototype]]`-цепочки. Отличия реальны, но касаются деталей: non-enumerable методы, обязательный `super()`, статическая цепочка через `extends`.

- **"instanceof проверяет тип"** — нет, проверяет наличие `Fn.prototype` в `[[Prototype]]`-цепочке объекта. Сломается при замене `Fn.prototype` после создания объектов или при объектах из разных realm (например, `iframe`).

- **Не знать, что методы класса non-enumerable** — следствие: `for...in` по экземпляру класса методы не показывает, а `for...in` по объекту с ручными присвоениями на `prototype` — показывает.

- **"Setter в прототипе работает как присваивание собственного свойства"** — нет. Если в `[[Prototype]]`-цепочке есть setter для свойства, `obj.prop = val` вызовет setter, а не создаст собственное свойство `obj.prop`. Это частая ловушка при наследовании.

- **Не восстанавливать `constructor` при ручной настройке прототипной цепочки** — `Derived.prototype = Object.create(Base.prototype)` затирает `Derived.prototype.constructor`. Без явного восстановления `emp.constructor` будет указывать на `Base`, что ломает рефлексию и некоторые паттерны.
