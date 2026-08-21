# Mongoose: схемы, модели и валидация

## Что Mongoose добавляет к драйверу — и какой ценой

Mongoose — не самостоятельный клиент, а слой над официальным `mongodb`-драйвером. Он возвращает в код то, чего MongoDB не требует: описанную схему, приведение типов, валидацию и хуки.

Его часто называют ORM (object-relational mapper — библиотека, которая отображает записи базы данных в объекты вашего языка). Название подходит лишь приблизительно: MongoDB не реляционная, и Mongoose отображает документы, а не строки таблиц.

```txt
   Что именно добавляет Mongoose между кодом и сервером
┌───────────────────────────────────────────────────────┐
│ код приложения: сервисы, контроллеры                  │
├───────────────────────────────────────────────────────┤
│ Mongoose: Schema · каст типов · валидация · хуки      │
│ virtuals · methods/statics · populate · query builder │
│ гидрация результата в Document-обёртки                │
├───────────────────────────────────────────────────────┤
│ официальный Node.js driver: BSON, пул соединений,     │
│ мониторинг топологии, retryable writes, сессии        │
├───────────────────────────────────────────────────────┤
│ mongod / mongos: индексы, план запроса, репликация    │
└───────────────────────────────────────────────────────┘
каждая строка слоя Mongoose — это удобство, у которого есть цена в поведении
```

```txt
Что вы получаете:
  + схема как единая точка правды о форме документа — та самая
    схема, которая в MongoDB «живёт в коде» (об этом статья про
    документную модель)
  + автоматический каст типов: "42" из query-строки станет числом,
    строка с датой — Date, строка с id — ObjectId
  + валидация перед записью и понятные ошибки вместо мусора в базе
  + middleware: единое место для хеширования пароля, аудита,
    soft delete
  + virtuals, methods, statics — поведение рядом с данными
  + populate и цепочечный query builder

Чем вы платите:
  - результат запроса — не документ базы, а Document-обёртка:
    геттеры/сеттеры, отслеживание изменений, валидация. Это память
    и процессорное время на каждый объект (лечится lean() —
    об этом статья про запросы Mongoose и populate)
  - «скрытая магия»: часть механизмов работает не там, где ожидаешь
    (валидация и pre('save') на update-операциях — главная тема этой
    статьи)
  - ещё один слой при отладке: между вашим вызовом и запросом к
    серверу есть трансформация, которую надо уметь смотреть
    (mongoose.set('debug', true))
  - расхождение с драйвером в мелочах: имена коллекций,
    возвращаемые значения, значения по умолчанию

Когда Mongoose не нужен: скрипты миграций, тяжёлые агрегации,
узкие сервисы на 3-4 запроса. Там прямой драйвер честнее и
предсказуемее.
```

## Schema, Model, Document — три разных объекта

Эти три слова часто употребляют как синонимы, а это не одно и то же. Schema описывает форму документа и правила. Model — класс, привязанный к одной коллекции. Document — один экземпляр, который вернул запрос.

```typescript
import { Schema, model, Types, HydratedDocument } from 'mongoose';

// 1. Интерфейс — то, чем документ является для TypeScript
export interface Post {
  _id: Types.ObjectId;
  title: string;
  slug: string;
  body: string;
  author: { _id: Types.ObjectId; name: string };
  tags: string[];
  status: 'draft' | 'published';
  stats: { views: number; comments: number };
  publishedAt?: Date;
  createdAt: Date;
  updatedAt: Date;
}

// 2. Schema — форма документа и правила
const postSchema = new Schema<Post>(
  {
    title:  { type: String, required: true, trim: true, maxlength: 200 },
    slug:   { type: String, required: true, unique: true, lowercase: true },
    body:   { type: String, required: true },
    author: {
      _id:  { type: Schema.Types.ObjectId, ref: 'User', required: true },
      name: { type: String, required: true },
    },
    tags:   { type: [String], default: [] },
    status: { type: String, enum: ['draft', 'published'], default: 'draft' },
    stats: {
      views:    { type: Number, default: 0, min: 0 },
      comments: { type: Number, default: 0, min: 0 },
    },
    publishedAt: { type: Date },
  },
  {
    timestamps: true,        // createdAt/updatedAt поддерживаются сами
    collection: 'posts',     // иначе имя выводится из имени модели
    versionKey: '__v',       // см. раздел про __v в статье 08
  },
);

// 3. Model — класс, привязанный к коллекции
export const PostModel = model<Post>('Post', postSchema);

// 4. Document — экземпляр, который приходит из запроса
export type PostDoc = HydratedDocument<Post>;
```

```txt
Три вещи, которые удивляют в первый раз:

1. Имя коллекции выводится из имени модели: model('Post') →
   коллекция posts (нижний регистр + плюрализация). model('Person')
   → people. Если коллекция уже существует под другим именем,
   указывайте collection явно — иначе Mongoose молча создаст новую
   и «данные пропадут».

2. Модель регистрируется глобально в экземпляре mongoose. Повторный
   model('Post', schema) в другом файле бросит
   OverwriteModelError — типично при hot reload в Next.js
   (лечится проверкой mongoose.models.Post ?? model(...)).

3. Схема НЕ создаёт ничего в базе, кроме индексов. Никакого DDL
   (data definition language — та часть SQL, где CREATE TABLE
   и ALTER TABLE) нет: коллекция появится при первой записи.
```

## SchemaTypes и приведение типов: значение сначала преобразуют, потом проверяют

SchemaType — это объявленный тип поля, и он делает настоящую работу: Mongoose приводит пришедшее значение к этому типу до валидации. Поэтому строка `"42"` из query-строки сама становится числом `42`. А значение, которое привести нельзя, даёт ошибку входа, а не сбой сервера.

```txt
Типы: String · Number · Date · Boolean · ObjectId · Buffer
      Decimal128 · Map · Array · Mixed (Schema.Types.Mixed) ·
      вложенные схемы и поддокументы

Каст выполняется ПЕРЕД валидацией:
  { views: "42" }        → 42
  { publishedAt: "2026-08-13" } → Date
  { authorId: "66b0f2c1..." }   → ObjectId
  { active: "true" }     → true (строки 'true'/'1'/'yes' и число 1)

Если каст невозможен — CastError, и это ошибка ВХОДА (400),
а не сбой сервера (500):
  { views: "много" } → CastError: Cast to Number failed
Именно поэтому маппинг ошибок Mongoose в HTTP-коды нужно делать
осознанно — об этом статья про запросы Mongoose и populate.
```

```typescript
// Опции полей, которые используются постоянно
{
  email: {
    type: String,
    required: [true, 'email is required'],   // сообщение вместо дефолтного
    unique: true,          // ← ЭТО ИНДЕКС, А НЕ ВАЛИДАТОР (см. ниже)
    lowercase: true,       // сеттер: приводит к нижнему регистру
    trim: true,
    match: [/^\S+@\S+$/, 'invalid email'],
  },
  passwordHash: { type: String, required: true, select: false }, // не
                          // возвращать по умолчанию — удобно для секретов
  role: { type: String, enum: ['user', 'admin'], default: 'user' },
  createdBy: { type: Schema.Types.ObjectId, ref: 'User', immutable: true },
  meta: { type: Schema.Types.Mixed },     // произвольная структура
  score: { type: Number, default: () => 0 },  // функция-дефолт
}
```

```txt
Три ловушки SchemaTypes:

1. unique — это НЕ валидатор. Mongoose лишь создаёт уникальный
   индекс; проверку делает сервер, и нарушение приходит как ошибка
   E11000 duplicate key ПОСЛЕ отправки запроса, а не как
   ValidationError. Следствия: (а) обработчик ошибок обязан знать
   про E11000; (б) если индекс не создан (autoIndex отключён в
   проде), никакой уникальности НЕТ вообще, хотя в схеме написано
   unique: true (об этом статья про запросы Mongoose и populate).

2. Mixed не отслеживает изменения. doc.meta.x = 1 не будет сохранено,
   пока не сказать doc.markModified('meta').

3. Массив по умолчанию — пустой массив, а не undefined. Поле
   tags: [String] без значения даст [] в документе. Для вложенного
   объекта верно похожее: он может быть создан, даже если вы его не
   задавали (управляется опцией minimize).
```

## Валидаторы и главный нюанс: когда они срабатывают

Валидатор — это правило, привязанное к полю: встроенное (`required`, `enum`, `min`) или ваша собственная функция. Он может быть и асинхронным, тогда внутри можно обратиться к базе. Код ниже показывает оба вида, а таблица после него — то, на чём спотыкаются: какие операции вообще доходят до валидатора.

```typescript
const userSchema = new Schema<User>({
  email: {
    type: String,
    required: true,
    // синхронный кастомный валидатор
    validate: {
      validator: (v: string) => /^\S+@\S+\.\S+$/.test(v),
      message: (props) => `${props.value} is not a valid email`,
    },
  },
  username: {
    type: String,
    required: true,
    // асинхронный валидатор: обращение к базе внутри валидации
    validate: {
      validator: async function (v: string) {
        const exists = await UserModel.exists({ username: v });
        return !exists;
      },
      message: 'username is taken',
    },
  },
});
```

Асинхронный валидатор «занят ли username» полезен для понятного сообщения об ошибке, но он **не даёт гарантии уникальности**. Между проверкой и записью проходит время, и в это окно может вклиниться чужая запись. Эта гонка разобрана в статье про CRUD (create, read, update, delete — создание, чтение, обновление, удаление) и операторы запросов. Гарантию даёт только уникальный индекс.

Дальше — то, что ломает больше всего кода в реальных проектах:

```txt
Какие операции проходят через валидацию и хуки
┌────────────────────────────────────────┐
│ doc.save()                             │
│                                        │
│ валидация       да                     │
│ pre/post save   да                     │
│ query-хуки      нет                    │
└────────────────────────────────────────┘
┌────────────────────────────────────────┐
│ Model.create()                         │
│                                        │
│ валидация       да                     │
│ pre/post save   да                     │
│ query-хуки      нет                    │
└────────────────────────────────────────┘
┌────────────────────────────────────────┐
│ Model.insertMany()                     │
│                                        │
│ валидация       да                     │
│ pre/post save   нет                    │
│ query-хуки      нет                    │
└────────────────────────────────────────┘
┌────────────────────────────────────────┐
│ findOneAndUpdate()                     │
│                                        │
│ валидация       только с runValidators │
│ pre/post save   НЕТ                    │
│ query-хуки      да                     │
└────────────────────────────────────────┘
┌────────────────────────────────────────┐
│ updateOne() / updateMany()             │
│                                        │
│ валидация       только с runValidators │
│ pre/post save   НЕТ                    │
│ query-хуки      да                     │
└────────────────────────────────────────┘
┌────────────────────────────────────────┐
│ bulkWrite()                            │
│                                        │
│ валидация       нет                    │
│ pre/post save   нет                    │
│ query-хуки      нет                    │
└────────────────────────────────────────┘
    отсюда баг с хешированием пароля:
  pre('save') не увидит findOneAndUpdate
```

```typescript
// Валидация НЕ выполняется на update-операциях по умолчанию
await PostModel.updateOne(
  { _id: id },
  { $set: { status: 'nonsense', title: '' } },
);
// → записано без ошибок: enum и required не проверены

// Включается явно
await PostModel.updateOne(
  { _id: id },
  { $set: { status: 'nonsense' } },
  { runValidators: true },       // → ValidationError
);
```

```txt
И даже с runValidators есть ограничения, которые нужно знать:

  - required не проверяется для полей, которых НЕТ в обновлении.
    Это логично (обновление частичное), но означает: «документ
    обязательно валиден» гарантируется только через save()
  - кастомный валидатор получает значение поля, но `this` — это
    Query, а не документ. Валидатор, которому нужны другие поля
    документа, на update не работает так же, как на save
  - context: 'query' переключает `this` в валидаторе на объект
    запроса — так можно достать сам апдейт через this.getUpdate()
  - валидаторы для $push/$addToSet проверяют добавляемый элемент,
    а не весь массив

Практический вывод: если инварианты важны, есть два честных подхода:
  (1) весь домен пишет через doc.save() — тогда валидация и хуки
      работают всегда, ценой лишнего чтения документа;
  (2) update-операции разрешены, но валидацию дублируем на входе
      (zod/class-validator в DTO), а на схему смотрим как на
      последнюю линию, не единственную.

DTO здесь — data transfer object, объект передачи данных: та форма,
которую принимает и отдаёт ваш API, отдельно от документа базы.
```

```typescript
// Ручные проверки, когда нужен контроль момента
const post = new PostModel(input);
await post.validate();               // бросит ValidationError
const err = post.validateSync();     // вернёт ошибку, не бросит

// Структура ValidationError → маппинг в 400 с полями
try {
  await post.save();
} catch (e) {
  if (e instanceof mongoose.Error.ValidationError) {
    const fields = Object.entries(e.errors).map(([path, err]) => ({
      path,
      message: err.message,
    }));
    throw new BadRequestError(fields);
  }
  throw e;
}
```

## Middleware: document hooks против query hooks

Хуки Mongoose делятся на два семейства с разным `this`, и путаница между ними — источник тех самых «загадочных» багов.

```typescript
// DOCUMENT middleware: this — сам документ
userSchema.pre('save', async function () {
  // isModified — без него пароль перехешируется на каждом save
  if (!this.isModified('passwordHash')) return;
  this.passwordHash = await bcrypt.hash(this.passwordHash, 12);
});

userSchema.post('save', function (doc) {
  logger.info({ userId: doc._id }, 'user saved');
});

// QUERY middleware: this — Query, документа ещё/уже нет
postSchema.pre(/^find/, function () {
  // soft delete: скрыть удалённые из всех find-запросов
  this.where({ deletedAt: { $exists: false } });
});

postSchema.pre('findOneAndUpdate', function () {
  this.set({ updatedAt: new Date() });          // правим сам апдейт
  const update = this.getUpdate();              // что именно меняется
});

// AGGREGATE middleware: this — Aggregate
postSchema.pre('aggregate', function () {
  this.pipeline().unshift({ $match: { deletedAt: { $exists: false } } });
});

// ERROR handling middleware: 4 аргумента → обработчик ошибок
userSchema.post('save', function (err: any, doc: unknown, next: Function) {
  if (err?.code === 11000) next(new ConflictError('email already exists'));
  else next(err);
});
```

Теперь главный баг, который спрашивают на интервью почти всегда:

```typescript
// Схема хеширует пароль в pre('save')
userSchema.pre('save', async function () { /* bcrypt.hash */ });

// Код смены пароля написан через findOneAndUpdate
await UserModel.findOneAndUpdate(
  { _id: userId },
  { $set: { passwordHash: newPassword } },   // ← это ОТКРЫТЫЙ пароль
);
// pre('save') НЕ вызывается: findOneAndUpdate — это операция уровня
// запроса, документ в приложение не поднимается, save() не
// происходит. В базе оказывается пароль в открытом виде, и логин
// перестаёт работать (bcrypt.compare сравнивает с не-хешем).
```

```txt
Почему так: pre('save') — document middleware. Он привязан к
жизненному циклу ДОКУМЕНТА (загрузили → изменили → сохранили).
findOneAndUpdate/updateOne/updateMany/bulkWrite документ не
загружают: они отправляют серверу описание изменений. Никакого
документа, чей save() можно перехватить, не существует.

Три способа это лечить:

1. Домен пишет только через документ:
     const user = await UserModel.findById(id);
     user.passwordHash = newPassword;
     await user.save();               // хук сработает
   Плюс: инварианты в одном месте. Минус: лишнее чтение и потеря
   атомарности «read-modify-write» (об этом статья про CRUD
   и операторы запросов).

2. Дублировать хук на query-операции — с учётом, что this это Query:
     userSchema.pre('findOneAndUpdate', async function () {
       const update = this.getUpdate() as any;
       const raw = update?.$set?.passwordHash ?? update?.passwordHash;
       if (!raw) return;
       const hash = await bcrypt.hash(raw, 12);
       this.set({ passwordHash: hash });
     });
   Плюс: работает для обоих путей. Минус: логика продублирована,
   и про третий путь (bulkWrite) всё равно надо помнить.

3. Убрать хеширование из схемы вообще: делать его в сервисе
   (единственное место, где меняется пароль), а схему не нагружать
   магией. Часто самый честный вариант для «interview-ready» кода.
```

```txt
Ещё несколько мест, где хуки ведут себя не как ожидается:
  - insertMany() валидирует документы, но НЕ вызывает pre('save')
  - bulkWrite() не проходит ни через валидацию, ни через хуки
  - deleteOne() на МОДЕЛИ — это query middleware; deleteOne() на
    ДОКУМЕНТЕ — document middleware. Одинаковое имя, разный this
  - post-хуки для find получают массив документов, для findOne —
    один документ
  - хуки должны быть зарегистрированы ДО компиляции модели
    (model(...)), иначе они просто не применятся
```

## Virtuals, methods, statics, query helpers: поведение рядом с данными

Эти четыре механизма позволяют привязать поведение к схеме, а не рассыпать его по сервисам. Virtual — вычисляемое поле. Method принадлежит одному документу, static — модели, а query helper — переиспользуемое звено цепочки запроса.

```typescript
// Virtual — вычисляемое поле, в базе не хранится
postSchema.virtual('url').get(function () {
  return `/posts/${this.slug}`;
});

// Virtual с сеттером
userSchema.virtual('fullName')
  .get(function () { return `${this.firstName} ${this.lastName}`; })
  .set(function (v: string) {
    const [first, ...rest] = v.split(' ');
    this.firstName = first;
    this.lastName = rest.join(' ');
  });

// Virtuals НЕ попадают в JSON без явного включения
postSchema.set('toJSON', { virtuals: true });
postSchema.set('toObject', { virtuals: true });

// Method — поведение экземпляра
userSchema.methods.checkPassword = function (plain: string) {
  return bcrypt.compare(plain, this.passwordHash);
};

// Static — поведение модели
postSchema.statics.findPublishedBySlug = function (slug: string) {
  return this.findOne({ slug, status: 'published' });
};

// Query helper — переиспользуемое звено цепочки
postSchema.query.published = function () {
  return this.where({ status: 'published' });
};
// await PostModel.find().published().sort({ publishedAt: -1 });
```

Важно про virtuals: они не существуют для базы. По virtual нельзя фильтровать, сортировать и строить индекс — и `find({ url: ... })` просто ничего не найдёт. Если по значению нужно искать, это должно быть настоящее поле.

## strict mode: почему лишние поля исчезают молча

`strict` решает, что Mongoose делает с полем, которого нет в схеме. По умолчанию — отбрасывает его: без ошибки и без строки в логе. Это защита от мусора в базе и очень хороший способ спрятать опечатку.

```typescript
const schema = new Schema({ title: String }, { strict: true }); // default

await Model.create({ title: 'A', hackerField: 'x' });
// → в базе только title. hackerField молча ОТБРОШЕН, без ошибки
```

```txt
strict: true    (по умолчанию) — поля не из схемы отбрасываются
strict: false   — сохраняются как есть (обратно к «schemaless»)
strict: 'throw' — попытка записать лишнее поле бросает ошибку

strictQuery — то же для фильтров: поле не из схемы в условии find
              по умолчанию... поведение менялось между версиями
              Mongoose, поэтому задавайте его явно:
              mongoose.set('strictQuery', true)

Практика: strict: true защищает от мусора, но молчаливое
отбрасывание маскирует опечатки — сохранили createdAtt, ошибки нет,
поля нет. Для сервисов, где важно поймать несоответствие рано,
'throw' полезнее. И отдельно помнить: strict не удаляет поля,
которые УЖЕ есть в документах от старых версий кода — схема ничего
не «мигрирует».
```

## Типизация схем в TypeScript (обзорно)

Есть два направления, и на проект выбирают одно. Либо интерфейс — источник правды, а схема следует за ним. Либо схема — источник правды, а тип выводится из неё.

```typescript
// Вариант 1: интерфейс — источник правды (показан выше)
const postSchema = new Schema<Post>({ ... });
export const PostModel = model<Post>('Post', postSchema);

// Вариант 2: схема — источник правды, тип выводится
import { InferSchemaType, model, Schema } from 'mongoose';
const schema = new Schema({
  title: { type: String, required: true },
  tags:  [String],
});
type PostFromSchema = InferSchemaType<typeof schema>;
// { title: string; tags: string[] }

// Типизация methods/statics: третий дженерик модели
interface PostMethods { isFresh(): boolean }
interface PostStatics extends Model<Post, {}, PostMethods> {
  findPublishedBySlug(slug: string): Promise<PostDoc | null>;
}
const PostModel = model<Post, PostStatics>('Post', postSchema);

// ObjectId в типах — Types.ObjectId, а не string. На границе API
// он превращается в строку (Extended JSON — об этом статья про
// документную модель), и это ДВА разных типа, которые нельзя
// путать в DTO
```

```txt
Практический совет: заводите отдельный тип для «сырого» документа
(lean/DTO) и для гидрированного (HydratedDocument). Иначе в коде
появляется тип, у которого есть и save(), и то, что уже ушло в
JSON — и первый же lean() ломает типизацию. Это разобрано в статье
про запросы Mongoose и populate.
```

## Связь с другими темами

```txt
Документная модель и когда её   — схема, которая «живёт в коде»;
выбирать                          ObjectId и Extended JSON
                                  на границе API
CRUD и операторы запросов       — что реально делают updateOne
                                  и findOneAndUpdate, на которых
                                  не срабатывают document-хуки
Проектирование схемы: вложение  — что описывать вложенной схемой,
или ссылка                        а что ссылкой с ref
Индексы и производительность    — unique как индекс, а не
запросов                          валидатор; индексы, объявленные
                                  в схеме
Запросы Mongoose, populate      — lean(), populate, autoIndex, __v,
и ловушки                         маппинг E11000 в ошибку API
```

## Типичные ошибки на интервью

- **«Валидация Mongoose работает всегда»** — она работает на `save()` и `create()`. На `updateOne` и `findOneAndUpdate` — только с `runValidators: true`, и даже тогда `required` не проверяется для полей, которых нет в обновлении. `bulkWrite` не валидируется вовсе.

- **«`pre('save')` сработает при любом изменении документа»** — не сработает на `findOneAndUpdate`, `updateOne`, `updateMany`, `bulkWrite`: это query-операции, документ в приложение не поднимается. Классическое следствие — пароль, сохранённый в открытом виде.

- **«`unique: true` в схеме — это валидация»** — это объявление уникального индекса. Нарушение приходит как ошибка базы `E11000`, а не `ValidationError`. А если индекс не создан (`autoIndex: false` в проде), уникальности нет вообще.

- **«Асинхронный валидатор гарантирует уникальность»** — между проверкой и записью есть окно гонки. Гарантию даёт только уникальный индекс, валидатор нужен для понятного сообщения.

- **«Mongoose — это ORM, он абстрагирует MongoDB»** — он не убирает необходимость понимать документную модель, индексы и атомарность. `populate` останется дополнительными запросами. А плохая схема останется плохой: об этом статья про проектирование схемы.

- **«Лишнее поле в create() вызовет ошибку»** — при `strict: true` оно молча отбрасывается. Ошибка будет только при `strict: 'throw'`.

- **«Virtual можно использовать в запросе»** — virtual не существует для базы: по нему нельзя фильтровать, сортировать и строить индекс, и в JSON он попадает только при `toJSON: { virtuals: true }`.

- **«`Mixed` — удобный способ хранить произвольные данные»** — удобный, но Mongoose не отслеживает его изменения: без `markModified()` правка вложенного поля не сохранится.

- **«Имя коллекции — это имя модели»** — Mongoose приводит его к нижнему регистру и в множественное число (`Post` → `posts`, `Person` → `people`). Для существующей коллекции имя задают опцией `collection`.

- **«CastError — это баг сервера»** — это невалидный вход (`"много"` в числовое поле, битый `ObjectId` в параметре URL). Такое отдаётся как 400, а не как 500.
