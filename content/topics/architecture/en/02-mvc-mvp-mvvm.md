# MVC, MVP, and MVVM

> **Scope note:** These patterns describe how to organize code within a single application — specifically how to separate UI concerns from business logic. They are not about how services communicate with each other.

## Why these patterns exist

Before MVC (Model-View-Controller), GUI applications were written as one large blob: the code that rendered the UI also made database calls, also contained business rules. Changing how a button looked meant wading through pricing logic. Testing a calculation meant instantiating a full UI.

MVC, introduced in the 1970s in Smalltalk, gave a name to a separation that let these concerns evolve independently. MVP (Model-View-Presenter) and MVVM (Model-View-ViewModel) are variants that emerged later to solve specific problems that MVC had in certain environments.

All three patterns split application code into three concerns:
- **Model** — data and business logic
- **View** — what the user sees
- **The third piece** (Controller / Presenter / ViewModel) — the mediator between Model and View

The difference between the three patterns is entirely in how this third piece works and what it knows about.

## MVC — Model-View-Controller

```txt
         User input
              │
              ▼
┌─────────────────────┐
│      Controller      │  ← handles input, orchestrates
└──────┬──────────────┘
       │ updates          │ selects view
       ▼                  ▼
┌──────────────┐   ┌─────────────┐
│    Model     │──►│    View     │
│ (data/logic) │   │ (renders)   │
└──────────────┘   └─────────────┘
       Model notifies View directly (in original MVC)
```

**Controller** — receives user input (HTTP requests, button clicks, form submissions), decides what to do, updates the Model, and selects which View to render. It knows about both the Model and the View.

**Model** — the data and business logic. Knows nothing about how data is displayed.

**View** — renders the Model's data for the user. In the original Smalltalk MVC, the View observed the Model directly (the Observer pattern) and re-rendered when the Model changed.

### MVC on the server — where it actually lives today

Server-side MVC (Rails, Laravel, Django, NestJS with template rendering) maps cleanly:

```ts
// NestJS controller — the "C" in MVC
@Controller('orders')
export class OrdersController {
  constructor(private readonly ordersService: OrdersService) {}

  // Receives input (HTTP request) → updates model (via service) → selects view (returns JSON)
  @Get(':id')
  async findOne(@Param('id') id: string) {
    return this.ordersService.findById(id); // model
  }

  @Post()
  async create(@Body() dto: CreateOrderDto) {
    return this.ordersService.create(dto); // model
    // "view" in a REST API is the JSON serialization — no template needed
  }
}
```

```ts
// Express — same pattern, less ceremony
app.get('/orders/:id', async (req, res) => {
  const order = await ordersService.findById(req.params.id); // model
  res.json(order); // view
});
```

In a REST API, the "View" is just JSON serialization. There's no HTML template. The pattern still applies: the controller receives HTTP input, delegates to the model (service/repository), and chooses how to render the response.

### MVC in server-rendered HTML (NestJS + template engines)

```ts
// With Handlebars/EJS — the View is a real template
@Controller('orders')
export class OrdersController {
  @Get(':id')
  @Render('orders/show')  // ← selects the view template
  async show(@Param('id') id: string) {
    const order = await this.ordersService.findById(id);
    return { order }; // data passed to the template (the View)
  }
}
```

Here the separation is more tangible: the controller selects the template; the template (View) knows how to render an order object; the service (Model) knows nothing about templates.

## MVP — Model-View-Presenter

MVP emerged from the problems of applying MVC to desktop GUI frameworks (Windows Forms, Android pre-Jetpack). The key difference: the **View is passive** — it has no logic, it just renders what the Presenter tells it to render.

```txt
         User input
              │
              ▼
┌─────────────────────┐
│        View          │  ← passive: only renders, delegates all events
└──────┬──────────────┘
       │ events (user clicked "Submit")
       ▼
┌─────────────────────┐
│      Presenter       │  ← all logic lives here, knows the View interface
└──────┬──────────────┘
       │ queries/updates       │ updates View explicitly
       ▼                       ▼
┌──────────────┐     ┌─────────────────┐
│    Model     │     │  View (via      │
│              │     │  interface)     │
└──────────────┘     └─────────────────┘
```

The critical difference from MVC: the **Presenter communicates with the View through an interface**. The Presenter doesn't know about HTML, Android layouts, or any specific UI framework. It calls `view.showOrder(order)`, `view.showError(message)`, `view.setSubmitEnabled(false)` — abstract methods defined by a `IOrderView` interface that the real View implements.

```ts
// MVP example — a backend API handler that follows MVP thinking
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
      this.view.showError('Order not found');
    } finally {
      this.view.showLoading(false);
    }
  }
}

// The "View" could be Express, a CLI, a test double — anything implementing IOrderView
class ExpressOrderView implements IOrderView {
  constructor(private res: Response) {}
  showOrder(order: Order) { this.res.json(order); }
  showError(message: string) { this.res.status(404).json({ error: message }); }
  showLoading(_: boolean) { /* no-op in HTTP */ }
}
```

**Where MVP is used today:** MVP was the dominant pattern for Android development before Android Jetpack's ViewModel API arrived. It's still found in legacy Android codebases and in some frontend frameworks. On the backend, explicit MVP is rare — but the idea of "Presenter talks to View through an interface" shows up anywhere you want to decouple the response format from the business logic.

## MVVM — Model-View-ViewModel

MVVM (Model-View-ViewModel) was introduced by Microsoft for WPF (Windows Presentation Foundation) and later became the dominant pattern in modern frontend frameworks. The key innovation: **data binding** — the ViewModel exposes observable state, and the View automatically re-renders when that state changes.

```txt
┌──────────────┐    two-way     ┌─────────────────┐
│     View     │◄──data binding─►│   ViewModel     │
│ (template/   │                │ (observable     │
│  component)  │                │  state + logic) │
└──────────────┘                └────────┬────────┘
                                         │ calls
                                         ▼
                                ┌────────────────┐
                                │     Model      │
                                │ (data/service) │
                                └────────────────┘
```

**ViewModel** — holds the UI state (is the form submitting? is there an error? what's the current list of items?) as observable properties. When a ViewModel property changes, the View automatically updates — the ViewModel never needs to call `view.showError()` explicitly. The View is a "dumb" projection of the ViewModel's state.

### MVVM in React (conceptual mapping)

React doesn't use the MVVM term, but the pattern maps directly:

```tsx
// ViewModel — a custom hook: holds state, exposes actions, calls the "Model" (services/API)
function useOrderDetail(orderId: string) {
  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ordersApi.getById(orderId)
      .then(setOrder)
      .catch(() => setError('Order not found'))
      .finally(() => setIsLoading(false));
  }, [orderId]);

  return { order, isLoading, error }; // observable state
}

// View — dumb component, just renders what the ViewModel provides
function OrderDetail({ orderId }: { orderId: string }) {
  const { order, isLoading, error } = useOrderDetail(orderId); // binds to ViewModel

  if (isLoading) return <Spinner />;
  if (error) return <ErrorMessage message={error} />;
  if (!order) return null;
  return <OrderCard order={order} />;
}
```

The custom hook is the ViewModel: it holds state, talks to the Model (the API/service), and the View (the component) re-renders automatically when the hook's state changes. This is two-way data binding without the ceremony of explicit binding annotations.

### MVVM in Vue and Angular

In Vue 3, the Composition API makes the MVVM split very explicit:

```ts
// Vue 3 — the setup() function or <script setup> block is the ViewModel
const order = ref<Order | null>(null);
const isLoading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    order.value = await ordersApi.getById(props.orderId);
  } catch {
    error.value = 'Order not found';
  } finally {
    isLoading.value = false;
  }
});
// template (View) reactively binds to these refs — classic MVVM
```

Angular's Services + Component pattern follows the same structure: the Component (ViewModel) subscribes to Observables from a Service (Model), and the template (View) uses `| async` pipe to bind to the data stream.

## The honest picture — how these terms are actually used

Here is where candidates often struggle: these patterns don't have one precise, universally agreed implementation. The terms are used loosely.

```txt
What "MVC" means in different contexts:

  Rails developer:      "M = ActiveRecord, V = ERB template, C = ApplicationController"
  NestJS developer:     "M = service + repository, V = serialized JSON, C = controller"
  Angular developer:    "We use MVC but our Controller is actually a ViewModel..."
  Job description:      "Experience with MVC required" = "writes structured code, not spaghetti"
```

The concepts matter more than the labels:

| What matters | Pattern names |
|---|---|
| Separate rendering from business logic | All three |
| Controller/Presenter/ViewModel as the mediator | Specific vocabulary, loosely applied |
| View is passive and driven by the mediator | MVP and MVVM |
| View auto-updates from observable state | MVVM (data binding) |

## Comparison table

```txt
┌────────────────┬───────────────────┬──────────────────────┬─────────────────────┐
│                │       MVC         │        MVP           │        MVVM         │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ View knows     │ Model (directly   │ Nothing (only        │ Nothing (only       │
│ about          │ in original MVC)  │ an interface)        │ ViewModel's state)  │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ Mediator       │ Controller        │ Presenter            │ ViewModel           │
│ knows about    │ both Model+View   │ View interface only  │ Model only          │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ UI update      │ Controller/Model  │ Presenter calls      │ Automatic via       │
│ mechanism      │ drives View       │ view.method()        │ data binding        │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ Testability    │ Controller needs  │ Presenter fully      │ ViewModel fully     │
│                │ View to test      │ testable with mock   │ testable without UI │
├────────────────┼───────────────────┼──────────────────────┼─────────────────────┤
│ Used today in  │ Express, NestJS,  │ Legacy Android,      │ React (hooks),      │
│                │ Rails, Django     │ some frontends       │ Vue, Angular        │
└────────────────┴───────────────────┴──────────────────────┴─────────────────────┘
```

## Common interview traps

- **"MVC means the model talks directly to the view"** — that's the original Smalltalk MVC with Observer. In modern server-side MVC (Rails, NestJS), the Controller fetches from the Model and passes data to the View explicitly — the Model has no reference to the View at all. The original Observer-based flow exists conceptually but is rarely implemented literally today.

- **"MVP and MVVM are the same thing with different names"** — they solve the same broad problem (testable UI logic) but differ in the mechanism. MVP uses explicit method calls through an interface (`view.showError()`); MVVM uses data binding (ViewModel exposes state, View reacts automatically). In MVVM, the ViewModel literally doesn't know the View exists. In MVP, the Presenter holds a reference to the View interface.

- **"React uses MVC"** — React's component model is closer to MVVM: the component re-renders in response to state changes (data binding), and the data fetching/logic in a custom hook acts as a ViewModel. Calling React "MVC" isn't wrong per se, but it's imprecise and suggests you haven't thought about what each term actually means.

- **"The Controller is just a router — it delegates everything to the service"** — in a thin controller this is intentional and correct. But "delegates everything" doesn't mean the controller adds no value: it translates HTTP-level concerns (parsing params, validating request shape, mapping errors to HTTP status codes) that the service shouldn't need to know about. A controller that does `return service.doEverything(req)` and passes the raw `req` object to the service has collapsed the abstraction boundary.

- **"These patterns are only relevant for frontend"** — MVC originated in desktop GUIs and is deeply embedded in server-side frameworks (NestJS, Rails, Laravel, Django). The patterns describe a separation of concerns that applies wherever you have input, processing, and output — which is everywhere.
