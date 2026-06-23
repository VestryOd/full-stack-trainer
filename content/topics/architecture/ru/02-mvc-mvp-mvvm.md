# MVC, MVP и MVVM

> **Область применения:** Эти паттерны описывают организацию кода внутри одного приложения — конкретно, как отделить UI-логику от бизнес-логики. Они не касаются взаимодействия между сервисами.

## Зачем существуют эти паттерны

До появления MVC (Model-View-Controller, Модель-Представление-Контроллер) GUI-приложения писались как один большой монолит: код, рендеривший интерфейс, одновременно делал запросы к базе данных и содержал бизнес-правила. Изменение вида кнопки требовало погружения в логику ценообразования. Тест расчёта требовал инстанциирования полного UI.

MVC, введённый в 1970-х в Smalltalk, дал имя разделению, позволяющему этим аспектам развиваться независимо. MVP (Model-View-Presenter, Модель-Представление-Презентер) и MVVM (Model-View-ViewModel, Модель-Представление-Модель-Представления) — варианты, появившиеся позже для решения конкретных проблем MVC в определённых средах.

Все три паттерна делят код приложения на три аспекта:
- **Model** (Модель) — данные и бизнес-логика
- **View** (Представление) — то, что видит пользователь
- **Третий компонент** (Controller / Presenter / ViewModel) — посредник между Model и View

Разница между тремя паттернами целиком в том, как работает этот третий компонент и что он знает.

## MVC — Model-View-Controller

```txt
         Ввод пользователя
              │
              ▼
┌─────────────────────┐
│      Controller      │  ← обрабатывает ввод, оркестрирует
└──────┬──────────────┘
       │ обновляет       │ выбирает view
       ▼                 ▼
┌──────────────┐   ┌─────────────┐
│    Model     │──►│    View     │
│ (данные/лог.)│   │ (рендерит)  │
└──────────────┘   └─────────────┘
       Model уведомляет View напрямую (в оригинальном MVC)
```

**Controller** — получает пользовательский ввод (HTTP-запросы, клики, отправки форм), решает что делать, обновляет Model и выбирает View для рендеринга. Знает и о Model, и о View.

**Model** — данные и бизнес-логика. Ничего не знает о том, как данные отображаются.

**View** — рендерит данные Model для пользователя. В оригинальном Smalltalk MVC View наблюдал за Model напрямую (паттерн Observer) и перерисовывался при изменении Model.

### MVC на сервере — где он реально живёт сегодня

Серверный MVC (Rails, Laravel, Django, NestJS с шаблонизаторами) отображается чётко:

```ts
// NestJS контроллер — это "C" в MVC
@Controller('orders')
export class OrdersController {
  constructor(private readonly ordersService: OrdersService) {}

  // Получает ввод (HTTP-запрос) → обновляет модель (через сервис) → выбирает view (возвращает JSON)
  @Get(':id')
  async findOne(@Param('id') id: string) {
    return this.ordersService.findById(id); // model
  }

  @Post()
  async create(@Body() dto: CreateOrderDto) {
    return this.ordersService.create(dto); // model
    // "view" в REST API — это JSON-сериализация, шаблон не нужен
  }
}
```

```ts
// Express — тот же паттерн, меньше церемоний
app.get('/orders/:id', async (req, res) => {
  const order = await ordersService.findById(req.params.id); // model
  res.json(order); // view
});
```

В REST API "View" — это просто JSON-сериализация. Нет HTML-шаблона. Паттерн всё равно применяется: контроллер получает HTTP-ввод, делегирует в модель (сервис/репозиторий) и выбирает формат ответа.

### MVC при серверном рендеринге HTML (NestJS + шаблонизатор)

```ts
// С Handlebars/EJS — View это реальный шаблон
@Controller('orders')
export class OrdersController {
  @Get(':id')
  @Render('orders/show')  // ← выбирает шаблон View
  async show(@Param('id') id: string) {
    const order = await this.ordersService.findById(id);
    return { order }; // данные, передаваемые в шаблон (View)
  }
}
```

Здесь разделение ощутимее: контроллер выбирает шаблон; шаблон (View) знает, как отрендерить объект заказа; сервис (Model) ничего не знает о шаблонах.

## MVP — Model-View-Presenter

MVP появился из проблем применения MVC к desktop GUI-фреймворкам (Windows Forms, Android до Jetpack). Ключевое отличие: **View пассивен** — в нём нет логики, он просто рендерит то, что говорит Presenter.

```txt
         Ввод пользователя
              │
              ▼
┌─────────────────────┐
│        View          │  ← пассивен: только рендерит, делегирует все события
└──────┬──────────────┘
       │ события (пользователь нажал "Отправить")
       ▼
┌─────────────────────┐
│      Presenter       │  ← вся логика здесь, знает интерфейс View
└──────┬──────────────┘
       │ запросы/обновления    │ явно обновляет View
       ▼                      ▼
┌──────────────┐    ┌──────────────────┐
│    Model     │    │  View (через     │
│              │    │  интерфейс)      │
└──────────────┘    └──────────────────┘
```

Критическое отличие от MVC: **Presenter общается с View через интерфейс**. Presenter не знает об HTML, Android-разметке или конкретном UI-фреймворке. Он вызывает `view.showOrder(order)`, `view.showError(message)`, `view.setSubmitEnabled(false)` — абстрактные методы интерфейса `IOrderView`, который реальный View реализует.

```ts
// Пример MVP — обработчик API на сервере в стиле MVP-мышления
interface IOrderView {
  showOrder(order: Order): void;
  showError(message: string): void;
  showLoading(isLoading: boolean): void;
}

class OrderPresenter {
  constructor(
    private view: IOrderView,
    private ordersService: OrdersService,
  ) {}

  async loadOrder(id: string): Promise<void> {
    this.view.showLoading(true);
    try {
      const order = await this.ordersService.findById(id);
      this.view.showOrder(order);
    } catch {
      this.view.showError('Заказ не найден');
    } finally {
      this.view.showLoading(false);
    }
  }
}

// "View" может быть Express, CLI, тестовый дубль — всё, реализующее IOrderView
class ExpressOrderView implements IOrderView {
  constructor(private res: Response) {}
  showOrder(order: Order) { this.res.json(order); }
  showError(message: string) { this.res.status(404).json({ error: message }); }
  showLoading(_: boolean) { /* no-op в HTTP */ }
}
```

**Где MVP используется сегодня:** MVP был доминирующим паттерном для Android-разработки до появления ViewModel API в Android Jetpack. Он до сих пор встречается в legacy Android-кодовых базах и некоторых фронтенд-фреймворках. На бэкенде явный MVP редок — но идея "Presenter говорит с View через интерфейс" проявляется везде, где нужно отвязать формат ответа от бизнес-логики.

## MVVM — Model-View-ViewModel

MVVM (Model-View-ViewModel) был введён Microsoft для WPF (Windows Presentation Foundation) и стал доминирующим паттерном в современных фронтенд-фреймворках. Ключевое нововведение: **data binding (привязка данных)** — ViewModel предоставляет наблюдаемое состояние, и View автоматически перерисовывается при его изменении.

```txt
┌──────────────┐   двусторонняя   ┌─────────────────┐
│     View     │◄───привязка────►│   ViewModel     │
│ (шаблон/     │                  │ (наблюдаемое    │
│  компонент)  │                  │  состояние)     │
└──────────────┘                  └────────┬────────┘
                                           │ вызывает
                                           ▼
                                  ┌────────────────┐
                                  │     Model      │
                                  │ (данные/сервис)│
                                  └────────────────┘
```

**ViewModel** — хранит UI-состояние (идёт ли отправка формы? есть ли ошибка? каков текущий список элементов?) как наблюдаемые свойства. При изменении свойства ViewModel View автоматически обновляется — ViewModel никогда не нужно явно вызывать `view.showError()`. View — это "тупая" проекция состояния ViewModel.

### MVVM в React (концептуальный маппинг)

React не использует термин MVVM, но паттерн отображается напрямую:

```tsx
// ViewModel — кастомный хук: хранит состояние, предоставляет действия, вызывает "Model" (сервисы/API)
function useOrderDetail(orderId: string) {
  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ordersApi.getById(orderId)
      .then(setOrder)
      .catch(() => setError('Заказ не найден'))
      .finally(() => setIsLoading(false));
  }, [orderId]);

  return { order, isLoading, error }; // наблюдаемое состояние
}

// View — тупой компонент, просто рендерит то, что даёт ViewModel
function OrderDetail({ orderId }: { orderId: string }) {
  const { order, isLoading, error } = useOrderDetail(orderId); // привязывается к ViewModel

  if (isLoading) return <Spinner />;
  if (error) return <ErrorMessage message={error} />;
  if (!order) return null;
  return <OrderCard order={order} />;
}
```

Кастомный хук — это ViewModel: он хранит состояние, общается с Model (API/сервисом), а View (компонент) автоматически перерисовывается при изменении состояния хука. Это двусторонняя привязка данных без церемоний явных binding-аннотаций.

### MVVM во Vue и Angular

Во Vue 3 Composition API делает разделение MVVM очень явным:

```ts
// Vue 3 — функция setup() или блок <script setup> — это ViewModel
const order = ref<Order | null>(null);
const isLoading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    order.value = await ordersApi.getById(props.orderId);
  } catch {
    error.value = 'Заказ не найден';
  } finally {
    isLoading.value = false;
  }
});
// шаблон (View) реактивно привязывается к этим ref — классический MVVM
```

Паттерн Angular Services + Component следует той же структуре: Component (ViewModel) подписывается на Observable из Service (Model), а шаблон (View) использует pipe `| async` для привязки к потоку данных.

## Честная картина — как эти термины реально используются

Именно здесь кандидаты часто оказываются в тупике: у этих паттернов нет одной точной, universally agreed реализации. Термины используются свободно.

```txt
Что "MVC" означает в разных контекстах:

  Rails-разработчик:     "M = ActiveRecord, V = ERB-шаблон, C = ApplicationController"
  NestJS-разработчик:    "M = сервис + репозиторий, V = JSON, C = контроллер"
  Angular-разработчик:   "Мы используем MVC, но наш Controller — по сути ViewModel..."
  Вакансия на hh.ru:     "Опыт MVC обязателен" = "пишет структурированный код, не лапшу"
```

Концепции важнее ярлыков:

| Что важно | Имена паттернов |
|---|---|
| Отделить рендеринг от бизнес-логики | Все три |
| Controller/Presenter/ViewModel как посредник | Специфическая лексика, применяется свободно |
| View пассивен и управляется посредником | MVP и MVVM |
| View автообновляется из наблюдаемого состояния | MVVM (data binding) |

## Таблица сравнения

```txt
┌────────────────┬───────────────────┬──────────────────────┬─────────────────────┐
│                │       MVC         │        MVP           │        MVVM         │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ View знает     │ Model (напрямую   │ Ничего (только       │ Ничего (только      │
│ о              │ в оригинальном)   │ интерфейс)           │ состояние ViewModel)│
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ Посредник      │ Controller        │ Presenter            │ ViewModel           │
│ знает о        │ Model+View оба    │ только интерфейс View│ только Model        │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ Механизм       │ Controller/Model  │ Presenter вызывает   │ Автоматически через │
│ обновления UI  │ управляет View    │ view.method()        │ привязку данных     │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ Тестируемость  │ Controller требует│ Presenter полностью  │ ViewModel полностью │
│                │ View для теста    │ тестируем с моком    │ тестируем без UI    │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ Используется в │ Express, NestJS,  │ Legacy Android,      │ React (хуки),       │
│                │ Rails, Django     │ часть фронтендов     │ Vue, Angular        │
└────────────────┴───────────────────┴──────────────────────┴─────────────────────┘
```

## Типичные ошибки на интервью

- **"В MVC модель напрямую говорит с представлением"** — это оригинальный Smalltalk MVC с Observer. В современном серверном MVC (Rails, NestJS) Controller получает данные из Model и явно передаёт их в View — Model вообще не имеет ссылки на View. Оригинальный Observer-based поток существует концептуально, но буквально реализуется редко.

- **"MVP и MVVM — одно и то же с разными именами"** — они решают одну широкую проблему (тестируемая UI-логика), но различаются механизмом. MVP использует явные вызовы методов через интерфейс (`view.showError()`); MVVM использует привязку данных (ViewModel предоставляет состояние, View реагирует автоматически). В MVVM ViewModel буквально не знает, что View существует. В MVP Presenter хранит ссылку на интерфейс View.

- **"React использует MVC"** — компонентная модель React ближе к MVVM: компонент перерисовывается в ответ на изменения состояния (data binding), а логика получения данных в кастомном хуке выступает как ViewModel. Называть React "MVC" не совсем неверно, но неточно и говорит о том, что кандидат не задумывался о реальном смысле терминов.

- **"Controller — просто роутер, он делегирует всё в сервис"** — в тонком контроллере это намеренно и правильно. Но "делегирует всё" не значит, что контроллер не добавляет ценности: он транслирует HTTP-заботы (парсинг параметров, валидация формы запроса, маппинг ошибок в HTTP-коды), которые сервис не должен знать. Контроллер, делающий `return service.doEverything(req)` и передающий сырой объект `req` в сервис, разрушил границу абстракции.

- **"Эти паттерны актуальны только для фронтенда"** — MVC возник в desktop GUI и глубоко встроен в серверные фреймворки (NestJS, Rails, Laravel, Django). Паттерны описывают разделение ответственности, применимое везде, где есть ввод, обработка и вывод — то есть везде.
