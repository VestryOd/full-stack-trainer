# Приведение типов и равенство

## Алгоритм Abstract Equality Comparison (`==`)

`==` не "безумный JS" — это детерминированный алгоритм из спецификации. Если знать шаги, любой результат предсказуем.

Алгоритм для `x == y` (упрощённо, но точно по шагам):

```txt
1. Если Type(x) === Type(y):
     return x === y (Strict Equality, без дальнейших преобразований)
     (NaN !== NaN — даже здесь)

2. null == undefined → true (и undefined == null → true)
   null/undefined == что-угодно_другое → false

3. Если один — Number, другой — String:
     привести String к Number → повторить

4. Если один — Boolean:
     привести Boolean к Number (true→1, false→0) → повторить

5. Если один — Object, другой — String/Number/Symbol/BigInt:
     привести Object к примитиву через ToPrimitive → повторить

6. Иначе → false
```

Разберём наиболее запутанные случаи через этот алгоритм:

```js
// Predict the output — объясни каждый через алгоритм:
console.log([] == false);    // ?
console.log([] == 0);        // ?
console.log('' == false);    // ?
console.log(null == 0);      // ?
console.log(null == false);  // ?
console.log('' == 0);        // ?
```

<details>
<summary>Разбор пошагово</summary>

```txt
[] == false
  Шаг 4: false — Boolean → ToNumber(false) = 0 → [] == 0
  Шаг 5: [] — Object → ToPrimitive([]) = '' (toString→'') → '' == 0
  Шаг 3: '' — String → ToNumber('') = 0 → 0 == 0
  Шаг 1: оба Number, 0 === 0 → true ✅

[] == 0
  Шаг 5: [] — Object → ToPrimitive([]) = '' → '' == 0
  Шаг 3: '' — String → ToNumber('') = 0 → 0 == 0 → true ✅

'' == false
  Шаг 4: false — Boolean → ToNumber(false) = 0 → '' == 0
  Шаг 3: '' — String → ToNumber('') = 0 → 0 == 0 → true ✅

null == 0
  Шаг 2: null == что-то (не null/undefined) → false ✅
  (алгоритм гарантирует: null == только null и undefined)

null == false
  Шаг 2: null == что-то (не null/undefined) → false ✅
  (несмотря на то что оба "ложные"!)

'' == 0
  Шаг 3: '' — String → ToNumber('') = 0 → 0 == 0 → true ✅
```

Итог: `true, true, true, false, false, true`

Ключевое наблюдение: `null == 0` и `null == false` — false, хотя `'' == false`, `'' == 0` и `[] == false` — true. `null` особый: по алгоритму он равен только `null` и `undefined`.

</details>

## ToPrimitive — как объекты становятся примитивами

При приведении объекта к примитиву движок вызывает алгоритм ToPrimitive с **hint** (`'number'`, `'string'`, `'default'`):

```txt
ToPrimitive(obj, hint):
  1. Если есть [Symbol.toPrimitive] → вызвать его с hint → результат
  2. Если hint = 'string':
       попробовать obj.toString() → если примитив → вернуть
       попробовать obj.valueOf() → если примитив → вернуть
  3. Если hint = 'number' или 'default':
       попробовать obj.valueOf() → если примитив → вернуть
       попробовать obj.toString() → если примитив → вернуть
  4. Иначе → TypeError
```

Встроенные объекты:

```js
// Array:
[].toString()       // ''
[1,2,3].toString()  // '1,2,3'
[].valueOf()        // [] (не примитив → toString вызывается)

// Object:
({}).toString()     // '[object Object]'
({}).valueOf()      // {} (не примитив → toString вызывается)

// Date — hint 'default' трактует как 'string':
new Date().valueOf()  // timestamp (число)
new Date().toString() // 'Tue Jun 24 2026 ...'
```

```js
// Почему [] + [] = ''
// hint = 'default': valueOf → [] (не примитив), toString → '' → '' + '' = ''
[] + []  // ''

// Почему [] + {} = '[object Object]'
// [] → '', {} → '[object Object]' → '' + '[object Object]'
[] + {}  // '[object Object]'

// Знаменитая ловушка:
{} + []  // 0 (не '[object Object]'!)
// {} парсится как пустой блок, +[] = ToNumber([]) = ToNumber('') = 0
// Но только в statement-контексте (консоль, отдельная строка)!
// В expression-контексте: ({}) + [] = '[object Object]'
({}) + [] // '[object Object]'
```

## Оператор `+` — двойственность

`+` — единственный оператор с двойным поведением: числовое сложение ИЛИ строковая конкатенация.

```txt
Алгоритм x + y:
  1. lprim = ToPrimitive(x) [hint: 'default']
  2. rprim = ToPrimitive(y) [hint: 'default']
  3. Если lprim или rprim — строка → конкатенация (ToString оба)
  4. Иначе → ToNumber оба, сложить
```

```js
1 + 2          // 3    — оба числа
1 + '2'        // '12' — строка → конкатенация
'1' + 2        // '12' — строка → конкатенация
1 + true       // 2    — true → 1
1 + null       // 1    — null → 0
1 + undefined  // NaN  — undefined → NaN
1 + {}         // '1[object Object]' — {} → '[object Object]' → строка
1 + []         // '1'  — [] → '' → строка

// Числовые операторы (-,*,/) всегда ToNumber:
'3' - 1   // 2   — '3' → 3
'3' * '2' // 6
[] - 1    // -1  — [] → 0
{} - 1    // -1  (в statement-контексте: пустой блок, -1)
```

## `typeof null === 'object'` — исторический баг

В оригинальной реализации JavaScript (Brendan Eich, 1995) значения хранились как 32-битные слова. Младшие 3 бита — тег типа:

```txt
000 → object
001 → integer
010 → double
100 → string
110 → boolean
```

Специальное значение `null` было представлено как **нулевой указатель** (0x00000000 на большинстве платформ). Тег типа нулевого указателя = `000` → object.

Это баг, не фича. Его хотели исправить в ES2015, но предложение отклонили из-за совместимости с миллиардами строк существующего кода.

```js
typeof null        // 'object'  ← баг, исторически
typeof undefined   // 'undefined'
typeof 42          // 'number'
typeof 'str'       // 'string'
typeof true        // 'boolean'
typeof Symbol()    // 'symbol'
typeof 42n         // 'bigint'
typeof function(){} // 'function' (тоже особый случай — функции объекты, но typeof 'function')
typeof {}          // 'object'
typeof []          // 'object'  ← массив — объект

// Правильная проверка на null:
x === null         // ✅ единственный надёжный способ
typeof x === 'object' && x !== null // ✅ проверка что объект и не null
```

## NaN — число, не равное самому себе

`NaN` (Not-a-Number) — единственное значение в JS, которое не равно самому себе. Это предписано спецификацией IEEE 754.

```js
NaN === NaN  // false
NaN !== NaN  // true
NaN == NaN   // false

typeof NaN   // 'number' ← парадокс: "не число" имеет тип 'number'

// Почему это так: NaN — результат невалидных числовых операций
0 / 0          // NaN
parseInt('abc') // NaN
Math.sqrt(-1)  // NaN
Number(undefined) // NaN
```

### `isNaN` vs `Number.isNaN` — критическая разница

```js
// isNaN() — старая глобальная функция, сначала применяет ToNumber:
isNaN(NaN)        // true
isNaN('hello')    // true! ('hello' → Number('hello') = NaN)
isNaN(undefined)  // true! (undefined → NaN)
isNaN({})         // true! ({} → '[object Object]' → NaN)
isNaN(null)       // false! (null → 0)
isNaN([])         // false! ([] → '' → 0)

// Number.isNaN() — строгая проверка, НЕ применяет ToNumber:
Number.isNaN(NaN)        // true
Number.isNaN('hello')    // false ← строка, не NaN
Number.isNaN(undefined)  // false
Number.isNaN(1/0)        // false ← Infinity, не NaN

// Как проверить NaN без Number.isNaN:
x !== x  // true только для NaN (использование свойства NaN ≠ NaN)
```

### Number edge cases

```js
Infinity         // превышение диапазона числа
-Infinity
1 / 0            // Infinity
-1 / 0           // -Infinity
isFinite(Infinity) // false (ToNumber сначала!)
Number.isFinite(Infinity) // false (строго: только конечные числа)
Number.isFinite('42')     // false (строго: только number тип)
isFinite('42')            // true  (ToNumber('42') = 42)

// Числа с плавающей точкой (IEEE 754):
0.1 + 0.2         // 0.30000000000000004
0.1 + 0.2 === 0.3 // false

// +0 и -0:
+0 === -0      // true (!!!)
1 / +0         // Infinity
1 / -0         // -Infinity (единственный способ различить +0 и -0 через ===)
Object.is(+0, -0) // false
```

## `===` vs `==` vs `Object.is`

Три разных алгоритма равенства:

```txt
==   Abstract Equality:     приведение типов (алгоритм выше)
===  Strict Equality:       нет приведения, но: NaN≠NaN, +0===−0
Object.is: Same Value:      NaN===NaN, +0≠−0 (математически точно)
```

```js
// Два особых случая === (нарушения интуиции):
NaN === NaN  // false  (Object.is → true)
+0 === -0    // true   (Object.is → false)

// Object.is реализует SameValue алгоритм из спецификации:
Object.is(NaN, NaN) // true
Object.is(+0, -0)   // false
Object.is(1, 1)     // true
Object.is(null, null) // true

// Где Object.is важен:
// 1. Реализация Map/Set — ключи сравниваются через SameValueZero
//    (как Object.is, но +0 === -0)
const map = new Map();
map.set(NaN, 'found');
map.get(NaN); // 'found' ← Map корректно обрабатывает NaN как ключ

// 2. React.memo, useMemo, useEffect dependencies —
//    React использует Object.is для сравнения props/deps
Object.is(prevValue, nextValue); // если false → ре-рендер
```

## Таблица truthy/falsy — неочевидные случаи

**Все falsy значения** (только 9 штук):

```js
false
0           // числовой ноль
-0          // отрицательный ноль (отдельное значение!)
0n          // BigInt ноль
''          // пустая строка ('' === "" === ``)
null
undefined
NaN
document.all // ← единственный объект в JS, который falsy (исторический баг)
```

**Неочевидные truthy**:

```js
// Всё нижеследующее — truthy:
[]              // пустой массив — truthy!
{}              // пустой объект — truthy!
'0'             // непустая строка — truthy!
'false'         // непустая строка — truthy!
new Boolean(false) // объект Boolean (не примитив) — truthy!
function(){}    // любая функция — truthy
Infinity        // truthy
-Infinity       // truthy
```

```js
// Predict the output:
if ([]) console.log('array truthy');   // ?
if ({}) console.log('object truthy');  // ?
if ('0') console.log('string truthy'); // ?
if (new Boolean(false)) console.log('bool obj truthy'); // ?
if ([] == false) console.log('array == false'); // ?
```

<details>
<summary>Ответ</summary>

```
array truthy    // [] — truthy объект
object truthy   // {} — truthy объект
string truthy   // '0' — непустая строка, truthy
bool obj truthy // new Boolean(false) — объект, всегда truthy
array == false  // true! [] == false через алгоритм == (см. выше)
```

Именно это и делает `==` опасным: `[]` truthy в boolean-контексте (`if`), но `[] == false` — `true` через алгоритм. Кажущееся противоречие объясняется тем, что `if` использует ToBoolean (нет приведения), а `==` — AbstractEquality (с приведением через шаг 4: Boolean → Number, потом шаг 5: Object → String).

</details>

### `document.all` — единственный объект-исключение

```js
// document.all — HTMLAllCollection, особый случай для совместимости с IE
typeof document.all // 'undefined' (хотя это объект!)
Boolean(document.all) // false (хотя это объект!)
document.all == null  // true

// Это явно прописано в спецификации HTML как "willful violation of the ECMAScript spec"
// ради совместимости со старыми сайтами, проверявшими document.all на существование
```

## ToNumber, ToString, ToBoolean — быстрая шпаргалка

```txt
ToNumber:
  undefined  → NaN
  null       → 0
  true       → 1
  false      → 0
  ''         → 0
  '   '      → 0  (пробелы игнорируются)
  '42'       → 42
  '0x1A'     → 26 (hex)
  'Infinity' → Infinity
  '42abc'    → NaN (не валидное число)
  []         → 0  (через ToPrimitive: [] → '' → 0)
  [1]        → 1  (через ToPrimitive: [1] → '1' → 1)
  [1,2]      → NaN (через ToPrimitive: [1,2] → '1,2' → NaN)
  {}         → NaN (через ToPrimitive: {} → '[object Object]' → NaN)

ToString:
  undefined  → 'undefined'
  null       → 'null'
  true       → 'true'
  false      → 'false'
  0          → '0'
  -0         → '0'  (!)
  NaN        → 'NaN'
  Infinity   → 'Infinity'
  []         → ''
  [1,2,3]    → '1,2,3'
  {}         → '[object Object]'

ToBoolean (нет вычислений, просто таблица):
  falsy: false, 0, -0, 0n, '', null, undefined, NaN, document.all
  всё остальное → true (включая [], {}, '0', 'false', new Boolean(false))
```

## Связь с другими темами

```txt
[Прокси/Symbol]       — Symbol.toPrimitive перехватывает ToPrimitive;
                         без него — valueOf/toString цепочка
[Современный JS]      — Object.hasOwn, Number.isNaN, Number.isFinite —
                         строгие версии старых функций без неявного ToNumber
[Управление памятью]  — typeof используется для проверки типов, но
                         typeof null = 'object' требует отдельной проверки
```

## Типичные ошибки на интервью

- **"`==` непредсказуем"** — предсказуем на 100%, если знать алгоритм. Проблема не в "безумии JS", а в том, что алгоритм нелинейный (7 шагов с повторением). Знание алгоритма позволяет объяснить любой результат.

- **"Чтобы проверить NaN, используй `isNaN`"** — `isNaN` применяет `ToNumber` к аргументу, поэтому `isNaN('hello')` = true. Нужно `Number.isNaN` (строгая проверка) или `x !== x`.

- **"`===` — абсолютно точное сравнение"** — нет двух исключений: `NaN !== NaN` и `+0 === -0`. Для математически корректного сравнения — `Object.is`.

- **"Пустой массив `[]` — falsy"** — нет! `[]` truthy. Но `[] == false` — true (через алгоритм ==). Это одна из самых частых путаниц на интервью.

- **"`typeof null === 'object'` — правильное поведение"** — нет, это признанный баг с 1995 года, не исправленный ради обратной совместимости.

- **"Оператор `+` — это всегда сложение"** — нет. Если хотя бы один операнд после ToPrimitive стал строкой, `+` — это конкатенация. Именно поэтому `1 + []` = `'1'` (не `1`).

- **"Не знать разницу между `Object.is`, `===` и `==`"** — для senior обязательно: все три существуют, решают разные задачи. `Object.is` используется в React для сравнения зависимостей, в спецификации Map/Set (SameValueZero — вариант Object.is где +0 === -0).
