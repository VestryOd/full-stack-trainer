# HTTP и интерсепторы

## Теория

### Подключение и типизированные запросы

`HttpClient` не доступен по умолчанию — его нужно провайдить:

```ts
provideHttpClient(
  withInterceptors([authInterceptor, loggingInterceptor, errorInterceptor]),
)
```

Важное изменение, о котором до сих пор пишут неверно: **`withFetch()` больше не нужен**. `FetchBackend` — транспорт по умолчанию, а сам флаг помечен deprecated («`withFetch` is not required anymore»). Если нужен старый транспорт, есть `withXhr()`.

Остальные фичи `provideHttpClient`:

- `withInterceptorsFromDi()` — классовые интерсепторы из legacy-кода.
- `withXsrfConfiguration()` и `withNoXsrfProtection()`.
- `withRequestsMadeViaParent()`.
- `withJsonpSupport()` — помечен deprecated с 22.1, потому что это источник XSS (cross-site scripting, межсайтовый скриптинг).

Запросы типизируются параметром метода, а не `as`:

```ts
private readonly http = inject(HttpClient);

// Тип относится к распарсенному телу ответа
readonly tickets$ = this.http.get<readonly Ticket[]>('/api/tickets', {
  params: { status: 'open', page: 1 },   // объект вместо ручной сборки строки
  headers: { 'X-Client': 'support-desk' },
  timeout: 10_000,                       // fetch-опция, доступна прямо здесь
});
```

Помимо `timeout` у запроса есть и другие опции современного fetch: `keepalive`, `cache`, `priority`, `mode`, `redirect`, `credentials`. Есть и `transferCache`. Он переносит ответ из SSR (server-side rendering, серверный рендеринг) в браузер без повторного запроса (глава 15). Важно помнить: `HttpClient` возвращает **холодный** Observable. Без подписки (или без `httpResource`) запрос не уйдёт.

### httpResource: загрузка данных как сигнал

Стабильный с v22 способ загрузить данные экрана:

```ts
readonly ticketsResource = httpResource<readonly Ticket[]>(
  // функция, а не строка: она читает сигналы и перезапрашивает при их изменении
  () => `/api/tickets?status=${this.status() ?? ''}`,
  { defaultValue: [] },
);

// в шаблоне доступны сигналы состояния
// ticketsResource.value()     — данные
// ticketsResource.isLoading() — идёт загрузка
// ticketsResource.error()     — ошибка
// ticketsResource.status()    — 'idle' | 'loading' | 'reloading' | 'resolved' | 'error'
// ticketsResource.reload()    — принудительное обновление
```

Ключевая идея: запрос описывается **реактивно**. Функция URL (или объект `HttpResourceRequest`) читает сигналы. Когда сигнал меняется, `httpResource` отменяет предыдущий запрос и делает новый. Флаги `loading`/`error` больше не нужно дублировать в каждом компоненте, потому что они часть ресурса.

Опции: `defaultValue`, `parse` (валидация/преобразование тела, удобно с zod), `map`, `equal`, `injector`. Для не-JSON есть `httpResource.text()`, `.blob()`, `.arrayBuffer()`. Дополнительно ресурс отдаёт `headers()`, `statusCode()`, `progress()` и `hasValue()`.

Более общий `resource({ params, loader })` тоже стабилен с v22, и он не привязан к HTTP. `loader` получает `params`, `previous` и `abortSignal`, поэтому годится для любого асинхронного источника. Например: WebSocket-запроса, IndexedDB, чужого SDK (software development kit, комплект средств разработки). Оба API предназначены для **чтения**, а мутации (POST/PUT/DELETE) остаются обычными вызовами `HttpClient`.

Способов загрузки пять, и первый — вариант по умолчанию для данных экрана:

| способ загрузки | что даёт | когда брать |
|---|---|---|
| `httpResource(() => url)` | `value`/`isLoading`/`error` как сигналы | данные экрана — по умолчанию |
| `resource({ params, loader })` | то же, но `loader` любой async | не-HTTP источник, свой fetch |
| `http.get<T>()` + `subscribe` | ручное управление и отписка | команды: `POST`/`PUT`/`DELETE` |
| `http.get<T>()` + `toSignal` | сигнал из Observable | нужен RxJS-конвейер (глава 09) |
| `ResolveFn` в маршруте | данные до рендера | проверки перед навигацией (глава 07) |

### Интерсепторы

```
          Один запрос сквозь цепочку интерсепторов
┌──────────────────────────────────────────────────────────┐
│ httpResource(() => url) или http.get<Ticket[]>(url)      │
│ запрос уходит вниз по цепочке в порядке withInterceptors │
└──────────────────────────────────────────────────────────┘
                              │  req
                              ▼
┌──────────────────────────────────────────────────────────┐
│ authInterceptor                                          │
│ вниз: req.clone({ headers: … Bearer token })             │
│ вверх: 401 → refresh или разлогин                        │
└──────────────────────────────────────────────────────────┘
                              │  req
                              ▼
┌──────────────────────────────────────────────────────────┐
│ loggingInterceptor                                       │
│ вниз: время старта, метод, url                           │
│ вверх: код ответа и длительность                         │
└──────────────────────────────────────────────────────────┘
                              │  req
                              ▼
┌──────────────────────────────────────────────────────────┐
│ errorInterceptor                                         │
│ вниз: ничего                                             │
│ вверх: 5xx → retry, затем маппинг в свою ошибку          │
└──────────────────────────────────────────────────────────┘
                              │  req
                              ▼
┌──────────────────────────────────────────────────────────┐
│ FetchBackend — реальный fetch()                          │
│ ответ идёт обратно вверх в обратном порядке              │
└──────────────────────────────────────────────────────────┘
запрос иммутабелен: менять его можно только через req.clone();
   метаданные для интерсепторов передаются в req.context
```

Функциональный интерсептор — обычная функция:

```ts
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // интерсептор выполняется в контексте инъекции — inject() работает
  const token = inject(AuthStore).token();
  if (token === null) return next(req);

  // запрос иммутабелен: модификация только через clone()
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};
```

Порядок в массиве `withInterceptors([...])` — это порядок обработки **запроса**, а ответ идёт в обратном порядке. Отсюда практическое правило из двух половин. Интерсептор, который должен видеть окончательный вид запроса — логирование, подпись, — ставится ближе к концу. Интерсептор, который решает судьбу ответа — обработка ошибок, retry, — ставится так, чтобы ошибка дошла до него раньше остальных.

Метаданные для интерсепторов передаются через `HttpContext` — не через заголовки и не через флаги в сервисе:

```ts
export const SKIP_AUTH = new HttpContextToken(() => false);

// на стороне вызова
this.http.get('/api/public/status', { context: new HttpContext().set(SKIP_AUTH, true) });

// в интерсепторе
if (req.context.get(SKIP_AUTH)) return next(req);
```

### Ошибки: где что обрабатывать

Не всякую ошибку обрабатывают в одном и том же месте:

| ситуация | где обрабатывать | что видит пользователь |
|---|---|---|
| 401 Unauthorized | интерсептор | редирект на вход |
| 403 Forbidden | интерсептор | страница «нет доступа» |
| 404 на конкретной сущности | экран или резолвер | «тикет не найден» |
| 422 / ошибки валидации | форма, отправившая запрос | сообщения у полей |
| 5xx | интерсептор: retry, затем баннер | «попробуйте позже» |
| сеть недоступна, timeout | интерсептор | офлайн-состояние |

Общее правило: если реакция одинакова для всего приложения — это интерсептор. Если она зависит от экрана, обработка идёт там, где запрос был вызван.

Ошибка приходит как `HttpErrorResponse`. Различать нужно два случая. При `status === 0` запрос не дошёл. Причина — нет сети, отмена или блокировка со стороны CORS (cross-origin resource sharing — правила браузера для межсайтовых запросов). При `status >= 400` сервер ответил ошибкой.

В интерсепторе ошибки перехватываются оператором `catchError`, повторы — `retry({ count, delay })`.

### Отмена запросов

Отмена работает через отписку: `HttpClient` при unsubscribe прерывает запрос (с `FetchBackend` — через `AbortController`). Три практических способа:

- **`httpResource`/`resource`** — отменяет предыдущий запрос сам, когда меняются зависимости; `resource` дополнительно передаёт `abortSignal` в загрузчик.
- **`switchMap`** — отменяет предыдущий запрос при новом значении: основа живого поиска (глава 09).
- **`takeUntilDestroyed()`** — привязывает подписку к жизни компонента (глава 09).

## Параллели с React

- **`httpResource` ≈ TanStack Query, а не `fetch` в `useEffect`.** Оба дают `data`/`isLoading`/`error` и перезапрос при изменении ключа. Отличий два. `httpResource` не кеширует между компонентами и не дедуплицирует запросы, потому что общего кеша по ключу нет. Зато он не требует провайдера и отдаёт сигналы напрямую. Инвалидация тоже проще и грубее: `reload()` вместо `invalidateQueries`.
- **Интерсепторы против обёрток над `fetch`.** В React перехват обычно делают своей функцией `apiFetch()` или экземпляром axios с интерсепторами — и любой код, вызвавший «голый» `fetch`, обходит логику. В Angular интерсептор встроен в `HttpClient`: обойти его можно только не используя `HttpClient` вовсе, а значит слой авторизации гарантированно единый.
- **Отмена запросов.** В React отмена — ручная работа: `AbortController` плюс cleanup в `useEffect`. В Angular отмена вытекает из модели: отписка прерывает запрос, `switchMap` делает это автоматически, а `httpResource` — при смене зависимостей.
- **Где живут `loading` и `error`.** В React-проектах без библиотеки эти флаги обычно объявляют в каждом компоненте вручную. С `httpResource` они становятся частью объекта запроса, поэтому дублировать `isLoading` в компоненте не нужно. Это и отличает современный Angular-код от кода трёхлетней давности.
- **Где ломается привычка:** `http.get()` без подписки. React-разработчик, привыкший к `fetch()` как к промису, ожидает, что вызов уже отправил запрос. Ничего не произойдёт: Observable холодный, и «запрос не уходит» — самая частая первая проблема в HTTP-слое Angular.

## Что увидишь в legacy-коде

- **`HttpClientModule` в `imports`** вместо `provideHttpClient()` — модульная эпоха. Рядом `withFetch()` не найдёте, потому что транспортом был XHR (XMLHttpRequest, браузерный API запросов, появившийся до `fetch`).
- **Классовые интерсепторы:** `@Injectable() export class AuthInterceptor implements HttpInterceptor`. Регистрация идёт multi-провайдером: `{ provide: HTTP_INTERCEPTORS, useClass: AuthInterceptor, multi: true }` (пример `multi` из главы 04). Чтобы такие интерсепторы продолжали работать рядом с новыми, нужен `withInterceptorsFromDi()`.
- **Ручные `loading`/`error` в каждом компоненте:** `loading = true` перед вызовом, `subscribe({ next, error, complete })` с `loading = false` в двух местах и `cdr.markForCheck()` в придачу (глава 03).
- **`BehaviorSubject` + `async`-пайп как «кеш»:** сервис сам хранит последний ответ и раздаёт его через `state$`. Сейчас это `httpResource` или сигнальный стор (глава 05).
- **`toPromise()`** (удалён в RxJS 8; заменён на `firstValueFrom`/`lastValueFrom`) и `.subscribe()` без отписки в `ngOnInit`.
- **Сборка URL строками:** `` `${env.apiUrl}/tickets?status=${status}&page=${page}` `` вместо `params`, из-за чего теряется экранирование. И `environment.ts` как источник `apiUrl` вместо токена DI (внедрение зависимостей), см. главу 04.

## Что добавляем в проект

Support Desk получает настоящий HTTP-слой. Это `TicketApi` с типизированными запросами и три интерсептора: авторизация, логирование, обработка ошибок с повтором. Список грузится через `httpResource` с реактивными параметрами, а реакция на 401 и 500 становится централизованной.

## Практическое задание

**Вход:** проект из главы 07 (маршруты, сторы, данные в памяти).
**Выход:** данные приходят из мок-бэкенда, ошибки обрабатываются на правильном уровне.

Требования:

1. Мок-бэкенд: поднимите любой — `json-server`, `msw` или простой Express. Нужны четыре эндпоинта: `GET /api/tickets` (с поддержкой `status`, `q`, `page`), `GET /api/tickets/:id`, `POST /api/tickets` и `PATCH /api/tickets/:id`. Базовый URL приходит из `APP_CONFIG` (глава 04), а не из константы в сервисе.
2. `TicketApi`: типизированные методы `list(params)`, `byId(id)`, `create(dto)`, `patch(id, dto)`. Параметры передавайте объектом `params`, а не конкатенацией строк. Ни одного `any`.
3. Список тикетов грузится через `httpResource`, а параметры читаются из сигналов фильтров. При смене статуса или поисковой строки должен уходить новый запрос, а предыдущий — отменяться. Проверьте отмену во вкладке Network.
4. `loading` и `error` в шаблоне берутся из ресурса, а не из отдельных сигналов компонента. Пустой результат и ошибку различайте явно.
5. Три интерсептора. Первый, `authInterceptor`, подставляет токен и пропускает запросы, помеченные `SKIP_AUTH` через `HttpContext`. Второй, `loggingInterceptor`, пишет метод, URL, код ответа и длительность. Третий, `errorInterceptor`, повторяет 5xx, редиректит на `/login` при 401 и маппит `HttpErrorResponse` в собственный тип ошибки. Продумайте порядок в массиве и обоснуйте его.
6. Мутации: создание тикета — обычный `POST` через `HttpClient`, после успеха список обновляется. Решите, чем именно: `reload()` ресурса или оптимистичным обновлением стора, — и обоснуйте выбор.

Edge cases на подумать:

- Почему `this.http.get('/api/tickets')` без подписки не отправляет запрос, и как это выглядит в отладке?
- Что вернёт `httpResource` в момент между сменой фильтра и приходом ответа: старые данные, `undefined` или `defaultValue`?
- `errorInterceptor` делает `retry({ count: 2 })`. Что произойдёт с `POST`-запросом, который на сервере уже успел выполниться?
- Ошибка с `status === 0` — что это значит и почему её нельзя показывать как «ошибка сервера»?
- Токен обновляется в `authInterceptor` при 401. Что случится, если пять запросов получат 401 одновременно?

## Разбор решения

`src/app/tickets/ticket-api.ts`:

```ts
import { HttpClient, HttpContext, httpResource } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { APP_CONFIG } from '../core/app-config';
import { SKIP_AUTH } from '../core/http-context';
import { Ticket, TicketStatus } from './ticket';

export interface TicketListParams {
  readonly status?: TicketStatus | null;
  readonly q?: string;
  readonly page?: number;
}

@Service()
export class TicketApi {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(APP_CONFIG).apiUrl;

  // Тип в дженерике относится к распарсенному телу — никаких `as Ticket[]`
  list(params: TicketListParams) {
    return this.http.get<readonly Ticket[]>(`${this.baseUrl}/tickets`, {
      // объект params: Angular сам экранирует значения и опускает undefined
      params: {
        ...(params.status ? { status: params.status } : {}),
        ...(params.q ? { q: params.q } : {}),
        page: params.page ?? 1,
      },
      timeout: 10_000, // fetch-опция прямо в запросе, без RxJS-оператора
    });
  }

  byId(id: number) {
    return this.http.get<Ticket>(`${this.baseUrl}/tickets/${id}`);
  }

  create(dto: Omit<Ticket, 'id' | 'createdAt'>) {
    return this.http.post<Ticket>(`${this.baseUrl}/tickets`, dto);
  }

  patch(id: number, dto: Partial<Omit<Ticket, 'id'>>) {
    return this.http.patch<Ticket>(`${this.baseUrl}/tickets/${id}`, dto);
  }

  // публичный эндпоинт: помечаем контекстом, чтобы authInterceptor его пропустил
  status() {
    return this.http.get<{ ok: boolean }>(`${this.baseUrl}/public/status`, {
      context: new HttpContext().set(SKIP_AUTH, true),
    });
  }
}
```

`src/app/core/http-context.ts`:

```ts
import { HttpContextToken } from '@angular/common/http';

// Метаданные запроса для интерсепторов: не заголовок (он ушёл бы на сервер)
// и не глобальный флаг в сервисе (он не привязан к конкретному запросу)
export const SKIP_AUTH = new HttpContextToken(() => false);
export const SKIP_RETRY = new HttpContextToken(() => false);
```

`src/app/core/interceptors.ts`:

```ts
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, retry, tap, throwError, timer } from 'rxjs';
import { AuthStore } from './auth-store';
import { SKIP_AUTH, SKIP_RETRY } from './http-context';
import { Notifications } from './notifications';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // интерсептор выполняется в контексте инъекции
  const token = inject(AuthStore).token();

  // контекст запроса вместо «списка публичных URL» внутри интерсептора
  if (req.context.get(SKIP_AUTH) || token === null) return next(req);

  // req иммутабелен: единственный способ изменить — clone()
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};

export const loggingInterceptor: HttpInterceptorFn = (req, next) => {
  const startedAt = performance.now();

  return next(req).pipe(
    tap({
      // сюда доезжает уже модифицированный запрос: этот интерсептор стоит
      // после authInterceptor, поэтому видит финальные заголовки
      next: (event) => {
        if (event.type !== 4 /* HttpEventType.Response */) return;
        const ms = Math.round(performance.now() - startedAt);
        console.debug(`${req.method} ${req.urlWithParams} → ${event.status} (${ms}ms)`);
      },
      error: (error: HttpErrorResponse) => {
        const ms = Math.round(performance.now() - startedAt);
        console.warn(`${req.method} ${req.urlWithParams} → ${error.status} (${ms}ms)`);
      },
    }),
  );
};

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const auth = inject(AuthStore);
  const notifications = inject(Notifications);

  return next(req).pipe(
    // Повтор только для идемпотентных методов: повторять POST нельзя,
    // сервер мог уже создать сущность, а ответ потерялся по дороге
    retry({
      count: req.method === 'GET' && !req.context.get(SKIP_RETRY) ? 2 : 0,
      delay: (error: HttpErrorResponse, retryCount) =>
        error.status >= 500 || error.status === 0
          ? timer(retryCount * 500) // линейная задержка
          : throwError(() => error), // 4xx повторять бессмысленно
    }),
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401) {
        auth.signOut();
        void router.navigate(['/login'], { queryParams: { returnTo: router.url } });
      } else if (error.status === 403) {
        void router.navigate(['/forbidden']);
      } else if (error.status === 0) {
        // status 0 — запрос не дошёл: сеть, CORS или отмена.
        // Это не ошибка сервера, и текст должен быть другим
        notifications.show('No connection to the server');
      } else if (error.status >= 500) {
        notifications.show('Something went wrong. Please try again later.');
      }

      // 404 и 422 не трогаем: их обрабатывает экран или форма,
      // потому что реакция зависит от контекста, а не от кода ответа
      return throwError(() => error);
    }),
  );
};
```

`src/app/app.config.ts`:

```ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    // withFetch() здесь не нужен: FetchBackend — транспорт по умолчанию,
    // а сам флаг помечен deprecated
    provideHttpClient(
      // Порядок = порядок обработки запроса (ответ идёт в обратном).
      // auth первым — чтобы остальные видели финальные заголовки;
      // error последним — чтобы ошибка дошла до него раньше, чем до вызова
      withInterceptors([authInterceptor, loggingInterceptor, errorInterceptor]),
    ),
    ...provideAppConfig({ apiUrl: '/api' }),
  ],
};
```

`src/app/tickets/ticket-board-state.ts` — загрузка через `httpResource`:

```ts
@Service({ autoProvided: false })
export class TicketBoardState {
  private readonly config = inject(APP_CONFIG);

  private readonly statusFilter = signal<TicketStatus | null>(null);
  private readonly searchQuery = signal('');

  readonly status = this.statusFilter.asReadonly();
  readonly search = this.searchQuery.asReadonly();

  // Реактивный запрос: функция читает сигналы, поэтому при смене фильтра
  // httpResource сам отменит предыдущий запрос и отправит новый
  private readonly ticketsResource = httpResource<readonly Ticket[]>(
    () => ({
      url: `${this.config.apiUrl}/tickets`,
      params: {
        ...(this.statusFilter() ? { status: this.statusFilter()! } : {}),
        ...(this.searchQuery() ? { q: this.searchQuery() } : {}),
      },
    }),
    { defaultValue: [] },
  );

  // Наружу — только сигналы состояния ресурса; собственных loading/error
  // компонент больше не объявляет
  readonly tickets = this.ticketsResource.value;
  readonly isLoading = this.ticketsResource.isLoading;
  readonly error = this.ticketsResource.error;
  readonly isEmpty = computed(
    () => !this.isLoading() && this.error() === undefined && this.tickets().length === 0,
  );

  setStatus(status: TicketStatus | null): void {
    this.statusFilter.set(status);
  }

  setSearch(query: string): void {
    this.searchQuery.set(query);
  }

  reload(): void {
    this.ticketsResource.reload();
  }
}
```

Шаблон различает три состояния явно:

```html
@if (board.isLoading()) {
  <p class="ticket-list__status">Loading…</p>
} @else if (board.error()) {
  <p class="ticket-list__status ticket-list__status--error">
    Could not load tickets.
    <button type="button" (click)="board.reload()">Retry</button>
  </p>
} @else {
  <ul class="ticket-list__items">
    @for (ticket of board.tickets(); track ticket.id) {
      <li><app-ticket-card [ticket]="ticket" /></li>
    } @empty {
      <li class="ticket-list__empty">No tickets match the filter</li>
    }
  </ul>
}
```

Мутация — обычный `HttpClient`, после успеха обновляем ресурс:

```ts
export class TicketForm {
  private readonly api = inject(TicketApi);
  private readonly board = inject(TicketBoardState);
  private readonly router = inject(Router);

  protected save(dto: Omit<Ticket, 'id' | 'createdAt'>): void {
    // httpResource предназначен для чтения; создание — обычный POST.
    // takeUntilDestroyed не нужен: subscribe завершится сам после ответа,
    // но если уйти со страницы раньше, запрос стоит отменить (глава 09)
    this.api.create(dto).subscribe({
      next: () => {
        // reload() вместо ручной вставки в список: сервер — источник правды,
        // и мы избегаем расхождения (id, createdAt, серверная валидация)
        this.board.reload();
        void this.router.navigate(['/tickets']);
      },
      // 422 обрабатывается здесь: реакция зависит от формы,
      // а не от приложения в целом
      error: (error: HttpErrorResponse) => {
        if (error.status === 422) this.applyServerValidation(error.error);
      },
    });
  }
}
```

Ответы на edge cases:

- `HttpClient` возвращает **холодный** Observable: запрос отправляется в момент подписки. Без `subscribe()`, `httpResource` или `firstValueFrom` не произойдёт ничего — во вкладке Network пусто, ошибок в консоли нет. Именно поэтому симптом звучит как «метод вызывается, а запроса нет».
- Пока идёт новый запрос, `value()` сохраняет **предыдущее значение** (или `defaultValue`, если его ещё не было), а `status()` переходит в `'reloading'`, `isLoading()` — в `true`. Это удобно: список не мигает пустотой при смене фильтра. Если нужно наоборот, показывайте скелетон по `isLoading()`.
- Повтор `POST` может создать вторую сущность: сервер мог обработать запрос и не успеть доставить ответ. Поэтому в решении `retry` включён только для `GET`. Для мутаций либо не повторяют вовсе, либо сервер должен поддерживать ключ идемпотентности.
- `status === 0` означает, что HTTP-ответа не было вообще: нет сети, запрос заблокирован CORS, или подписка была отменена. Показывать «ошибка сервера» неверно вдвойне. Сервер мог быть в порядке, а причина на клиенте. И пользователю нужен другой совет — «проверьте соединение», а не «попробуйте позже».
- Пять параллельных 401 без защиты дадут пять запросов на обновление токена. Четыре из них, скорее всего, провалятся, потому что refresh-токен одноразовый, и пользователя выкинет из приложения. Решение — один общий Observable обновления в сервисе, переиспользуемый для всех ожидающих запросов. Делают это через `shareReplay` плюс флаг «обновление уже идёт», а остальные запросы после обновления повторяют.

## Проверь себя

1. Почему вызов `http.get()` сам по себе не отправляет запрос, и какие три способа его «активировать» вы знаете?
2. Что такое `httpResource` и чем он отличается от пары «`http.get` + два сигнала для loading и error»? Что происходит с данными при смене зависимости?
3. Порядок интерсепторов в `withInterceptors([a, b, c])`: в каком порядке они обрабатывают запрос и в каком — ответ? Куда поставить обработчик ошибок и почему?
4. Зачем нужен `HttpContext`, если можно передать заголовок или проверить URL внутри интерсептора?
5. По какому признаку вы решаете, обрабатывать ошибку в интерсепторе или в компоненте? Приведите по два примера.

<details>
<summary>Ответы</summary>

1. `HttpClient` возвращает холодный Observable: он описывает запрос, но не выполняет его. Отправка происходит на подписке, и на каждую подписку уходит **новый** запрос. Активировать его можно тремя способами. Первый — `subscribe()`, обычно для мутаций. Второй — `httpResource`/`resource` для данных экрана: они подписываются сами и отдают состояние сигналами. Третий — `firstValueFrom`/`lastValueFrom`, когда нужен промис, например в гарде с `async`. Обратная сторона холодности — бесплатная отмена: отписка прерывает запрос.
2. `httpResource` — реактивная обёртка над запросом. URL или объект запроса задаётся функцией, читающей сигналы. Состояние доступно как `value()`, `isLoading()`, `error()` и `status()`, плюс `reload()`. Отличие от ручной пары в том, что состояние загрузки перестаёт быть кодом компонента. Не нужно ставить `loading = true` перед вызовом и сбрасывать его в двух ветках, не нужно помнить про `markForCheck`. При смене зависимости ресурс отменяет предыдущий запрос и отправляет новый. При этом `value()` сохраняет прошлое значение, а `status()` становится `'reloading'`, поэтому UI (user interface, пользовательский интерфейс) не мигает пустотой.
3. Запрос идёт в порядке объявления: `a → b → c → backend`. Ответ (и ошибка) поднимается в обратном порядке: `c → b → a`. Обработчик ошибок логично ставить последним в массиве. Тогда на пути ответа он получает управление **первым** и может решить судьбу ошибки до того, как её увидят остальные и вызывающий код. Решить судьбу — значит повторить запрос, превратить ошибку в редирект или показать баннер. Интерсепторы, которым нужен окончательный вид запроса — логирование, подпись, метрики, — ставят после тех, кто запрос модифицирует.
4. `HttpContext` — способ передать метаданные **конкретного запроса** самим интерсепторам, не отправляя ничего на сервер. Заголовок для этого не подходит: он уйдёт по сети и станет частью протокола (а иногда и вызовет preflight). Проверка URL внутри интерсептора — хрупкая связь. Список публичных путей живёт вдали от места вызова, ломается при рефакторинге маршрутов API и не выражает намерение. С `HttpContextToken` намерение видно в точке вызова: `context.set(SKIP_AUTH, true)`. Значение типизировано и имеет дефолт, а интерсептор просто читает `req.context.get(...)`.
5. Признак — зависит ли реакция от экрана. Если она одинакова для всего приложения, обработка идёт в интерсепторе. Это 401 (разлогин и редирект на вход) и 403 (страница «нет доступа»). Сюда же 5xx (повтор и общий баннер) и `status === 0` (офлайн-состояние). Если реакция зависит от контекста, обработка остаётся там, где запрос был сделан. Ошибка 404 по конкретной сущности — дело экрана: он показывает «тикет не найден», а не общий баннер. Ошибка 422 с ошибками валидации — дело формы, потому что сообщения должны встать у её полей. Конфликт версий 409 — тоже дело экрана: он предлагает перезагрузить данные. Практический критерий: если для правильного сообщения нужно знать, что за экран сделал запрос, — это не работа интерсептора.

</details>

## Частая ошибка

Первая — `http.get()` без подписки. Код выглядит как рабочий: метод сервиса вызван, тип возвращаемого значения устраивает компилятор, ошибок нет. Но `HttpClient` возвращает холодный Observable, поэтому не происходит ничего: в Network пусто, в консоли тихо.

У React-разработчика эта ошибка почти неизбежна, потому что `fetch()` — промис, который начинает работу сразу, а `await` лишь ждёт результат. Симптом легко узнать. Звучит он так: «сервис вызывается, я поставил `console.log` в методе — он печатается, а запроса нет».

Лечение: данные экрана грузить через `httpResource` (он подписывается сам), мутации — через `subscribe()`, а `firstValueFrom` использовать только там, где действительно нужен промис.

Вторая — дублирование состояния загрузки. Компонент объявляет `loading = signal(false)` и `error = signal<string|null>(null)`, а рядом лежит ресурс, который уже отдаёт `isLoading()` и `error()`.

Дальше эти два набора расходятся. `loading` забыли сбросить в ветке ошибки, `error` не очистили перед повторной попыткой. Пользователь видит спиннер поверх сообщения об ошибке. То же и с данными: копия ответа в собственном сигнале компонента живёт своей жизнью после `reload()`.

Правило то же, что в главе 05. Состояние, которое можно прочитать, не копируется, а читается — `resource.value()`, `resource.isLoading()`, `resource.error()`, — а всё производное считается через `computed`.
