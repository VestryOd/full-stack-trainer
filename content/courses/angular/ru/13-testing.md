# Тестирование

## Теория

### Стек: Vitest вместо Karma

С v21 тестовый ранер по умолчанию — **Vitest**: в схеме билдера `unit-test` опция `runner` имеет значение по умолчанию `vitest` и допускает `karma` для старых проектов. Тесты запускаются в Node с jsdom, а если указать `browsers`, — в настоящем браузере. Полезные опции билдера: `setupFiles`, `providersFile` (файл с массивом провайдеров для всего тестового окружения), `coverage`, `filter`, `ui`, `debug`, `isolate`.

Из этого следует важное практическое ограничение, которое ломает половину старых тестов: **`fakeAsync`/`tick` с Vitest не работают** — zone.js для этого ранера не патчится, и документация прямо говорит, что `fakeAsync` больше не рекомендуется. Вместо него — обычный `async`/`await`, `await fixture.whenStable()` и фейковые таймеры самого Vitest (`vi.useFakeTimers()`).

### Что чем тестировать

```
                         Что чем тестировать в Angular-приложении
┌──────────────────────────┬───────────────────────────────┬─────────────────────────────┐
│ что тестируем            │ инструмент                    │ нужен ли TestBed            │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ сигнальный стор, команды │ обычный юнит-тест             │ нет: new Store() или inject │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ чистая функция, пайп     │ обычный юнит-тест             │ нет                         │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ компонент и его шаблон   │ TestBed + fixture             │ да                          │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ HTTP-слой и интерсепторы │ provideHttpClientTesting      │ да                          │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ гард, резолвер           │ TestBed.runInInjectionContext │ да                          │
├──────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ сценарий пользователя    │ Playwright / Cypress          │ нет: настоящий браузер      │
└──────────────────────────┴───────────────────────────────┴─────────────────────────────┘
                чем меньше TestBed, тем быстрее и стабильнее набор тестов:
                    логику выносят в сервисы именно поэтому (глава 05)
```

Ключевая мысль: **сигнальный стор тестируется как обычный класс**. Никакого `TestBed`, никакого рендеринга — создали, вызвали команду, прочитали сигнал, сравнили. Это прямое следствие архитектуры из главы 05, и это основной аргумент за вынос логики из компонентов: тесты становятся быстрыми и не зависят от разметки.

### TestBed и подмена зависимостей

`TestBed` — это конфигурируемый инжектор плюс возможность создать компонент. Именно подмена зависимостей через DI — то, за что Angular-тесты стоит любить: не нужно мокать модули, достаточно дать другой провайдер (глава 04).

```
                Тест компонента: порядок шагов
┌────────────────────────────────────────────────────────────┐
│ TestBed.configureTestingModule({ providers: [...] })       │
│ здесь подменяются зависимости: useValue с моком вместо API │
└────────────────────────────────────────────────────────────┘
                               │  создание
                               ▼
┌────────────────────────────────────────────────────────────┐
│ const fixture = TestBed.createComponent(TicketList)        │
│ инстанс создан, шаблон ещё не проверялся                   │
└────────────────────────────────────────────────────────────┘
                               │  входы
                               ▼
┌────────────────────────────────────────────────────────────┐
│ fixture.componentRef.setInput('ticket', ticket)            │
│ setInput помечает компонент изменённым (глава 11)          │
└────────────────────────────────────────────────────────────┘
                               │  синхронизация
                               ▼
┌────────────────────────────────────────────────────────────┐
│ await fixture.whenStable()                                 │
│ ждём проверку шаблона и микротаски,                        │
│ вместо ручного detectChanges()                             │
└────────────────────────────────────────────────────────────┘
                               │  проверка
                               ▼
┌────────────────────────────────────────────────────────────┐
│ expect(...) по DOM, harness или сигналам                   │
│ httpTesting.verify() в afterEach                           │
└────────────────────────────────────────────────────────────┘
fakeAsync/tick НЕ работают с ранером Vitest: zone.js там не патчится,
        и документация больше не рекомендует fakeAsync
```

Два места, где тесты v22 отличаются от тестов трёхлетней давности:

1. **`await fixture.whenStable()` вместо `fixture.detectChanges()`.** В zoneless-тестах ручной `detectChanges()` — это принудительная синхронизация, которая может скрыть настоящую ошибку: компонент, забывший уведомить фреймворк, в тесте «работает», а в приложении нет. `whenStable()` даёт Angular запланировать проверку самому — то есть тест проверяет ровно то поведение, которое будет в продакшене.
2. **Входы задаются через `fixture.componentRef.setInput(...)`.** Прямая запись `component.ticket = x` не помечает компонент изменённым (глава 11), а с сигнальными входами ещё и не скомпилируется: `input()` возвращает read-only сигнал.

Полезные приёмы: `TestBed.inject(Token)` — достать зависимость; `TestBed.overrideProvider(...)` — подменить после конфигурации; `TestBed.runInInjectionContext(fn)` — вызвать гард, резолвер или функцию с `inject()` внутри; `DeferBlockBehavior.Manual` — пошагово проверять состояния `@defer`-блока (глава 12).

### HTTP: HttpTestingController

```ts
TestBed.configureTestingModule({
  providers: [TicketApi, provideHttpClient(), provideHttpClientTesting()],
});

const httpTesting = TestBed.inject(HttpTestingController);
const api = TestBed.inject(TicketApi);

const promise = firstValueFrom(api.list({ status: 'open' }));

// expectOne падает с понятным сообщением, если запросов ноль или больше одного
const req = httpTesting.expectOne((r) => r.url.endsWith('/tickets'));
expect(req.request.method).toBe('GET');
expect(req.request.params.get('status')).toBe('open');

req.flush([{ id: 1, title: 'Test' }]);       // отдаём ответ
expect(await promise).toHaveLength(1);

httpTesting.verify();                         // не осталось незакрытых запросов
```

API контроллера: `expectOne`, `expectNone`, `match` (несколько запросов), `verify`. У запроса: `flush(body, opts)` для успеха, `error(new ProgressEvent('error'), { status: 500 })` для ошибки. `verify()` лучше вынести в `afterEach` — тогда каждый тест заодно проверяет, что лишних запросов не было.

### Harness: тест, не привязанный к разметке

`cdk/testing` даёт слой абстракции между тестом и DOM: harness описывает компонент через его *поведение* (нажать, прочитать текст, выбрать опцию), а тест не знает про классы и вложенность. Загружается через `TestbedHarnessEnvironment.loader(fixture)`, дальше `getHarness(Predicate)` / `getAllHarnesses(...)`. Свой harness — класс, наследующий `ComponentHarness`, с локаторами (`this.locatorFor('.selector')`) и методами домена.

Смысл прост: рефакторинг разметки не должен ломать тесты. Если тест ищет `.ticket-card__title > span`, любая правка вёрстки его сломает; harness с методом `getTitle()` — нет.

### e2e — обзорно

Юнит- и компонентные тесты не проверяют то, что интересует пользователя: работает ли путь «открыл список → отфильтровал → создал тикет → увидел его в списке». Для этого нужен настоящий браузер: **Playwright** (де-факто стандарт сейчас) или Cypress. Правила разумного e2e: их мало (единицы ключевых сценариев), они не заменяют юнит-тесты, ищут элементы по роли/тексту/`data-testid`, а не по CSS-классам, и не мокают бэкенд без причины — иначе теряется смысл. Protractor, который поставлялся с Angular исторически, давно удалён.

## Параллели с React

```
┌───────────────────────┬──────────────────────────┬────────────────────────────────┐
│ задача                │ React: Jest/Vitest + RTL │ Angular: TestBed               │
├───────────────────────┼──────────────────────────┼────────────────────────────────┤
│ подменить зависимость │ jest.mock модуля         │ провайдер в TestBed            │
├───────────────────────┼──────────────────────────┼────────────────────────────────┤
│ отрендерить компонент │ render(<Cmp prop={x} />) │ createComponent + setInput     │
├───────────────────────┼──────────────────────────┼────────────────────────────────┤
│ дождаться обновления  │ await waitFor(...)       │ await fixture.whenStable()     │
├───────────────────────┼──────────────────────────┼────────────────────────────────┤
│ найти элемент         │ screen.getByRole(...)    │ harness или DebugElement       │
├───────────────────────┼──────────────────────────┼────────────────────────────────┤
│ замокать сеть         │ msw / fetch-mock         │ provideHttpClientTesting       │
├───────────────────────┼──────────────────────────┼────────────────────────────────┤
│ проверить состояние   │ через DOM                │ через DOM или сигналы напрямую │
└───────────────────────┴──────────────────────────┴────────────────────────────────┘
```

- **Подмена зависимостей — главное преимущество Angular.** `jest.mock('./api')` перехватывает импорт на уровне сборщика: путь надо знать, hoisting надо помнить, а типизация мока — на вашей совести. В Angular зависимость запрашивается по токену, поэтому подмена — обычная запись `{ provide: TicketApi, useValue: fake }`, типизированная и не зависящая от путей файлов. Именно это делает DI не «лишним слоем», а инструментом (глава 04).
- **Философия RTL против доступа к инстансу.** RTL сознательно не даёт добраться до состояния компонента: проверяйте то, что видит пользователь. В Angular у вас есть `fixture.componentInstance`, а с сигналами — прямое чтение состояния. Это удобно, но легко скатиться в тесты, проверяющие реализацию: разумная граница — состояние проверять в тестах сервисов, а компоненты тестировать через DOM или harness.
- **Ожидание обновлений.** `waitFor` в RTL опрашивает DOM до успеха; `whenStable()` в Angular дожидается, пока фреймворк отработает запланированную синхронизацию. Разница в надёжности: `whenStable()` знает про планировщик, а не угадывает по таймауту.
- **Скорость.** Юнит-тесты сервисов в Angular быстрые ровно так же, как в React, а вот `TestBed` дороже `render()` из RTL: он поднимает компилятор и инжектор. Отсюда практический вывод, обратный React-привычке «тестируем всё через рендер»: в Angular логику выгоднее держать в сервисах и тестировать без `TestBed`.
- **Где ломается привычка:** `component.input = value` вместо `setInput()`. В React пропсы задаются при рендере, и аналогия подсказывает «просто присвой полю». В Angular с сигнальными входами это ошибка компиляции, а с обычными — молчаливый провал: компонент не помечен изменённым, шаблон не обновится, и тест упадёт на непонятном `expect`.

## Что увидишь в legacy-коде

- **Karma + Jasmine:** `karma.conf.js`, `test.ts` с `require.context`, `ng test` открывающий браузер. Работает и сейчас (`runner: karma`), но в новых проектах ранер — Vitest, а синтаксис ассертов — `expect` из Vitest, а не из Jasmine.
- **`fakeAsync`/`tick`/`flushMicrotasks`** в каждом асинхронном тесте — с Vitest они не работают вовсе. Замена: `async`/`await`, `await fixture.whenStable()`, `vi.useFakeTimers()`.
- **`fixture.detectChanges()` после каждой строки** — привычка zone-эпохи. В zoneless это ещё и опасно: тест начинает проходить там, где приложение бы не обновилось.
- **`component.ticket = ticket; fixture.detectChanges();`** вместо `componentRef.setInput()`.
- **`TestBed.configureTestingModule({ declarations: [...], imports: [SomeModule] })`** — модульная эпоха; со standalone-компонентами их просто перечисляют в `imports`.
- **Спай на всё:** `jasmine.createSpyObj('TicketApi', ['list'])` с ручной типизацией и `spyOn(service, 'method')` там, где достаточно подставить простой объект-заглушку через провайдер.
- **`HttpClientTestingModule` в `imports`** — заменён функцией `provideHttpClientTesting()`.

## Что добавляем в проект

Три набора тестов: юнит-тесты `TicketStore` (без `TestBed`), тест HTTP-слоя с `HttpTestingController` (включая проверку интерсептора), тест компонента списка с подменой API через провайдер и harness для карточки тикета. Плюс один e2e-сценарий как пример.

## Практическое задание

**Вход:** проект из главы 12.
**Выход:** набор тестов, который падает по делу и не ломается от правок вёрстки.

Требования:

1. Юнит-тесты `TicketStore` без `TestBed`: `add` добавляет в начало, `update` сохраняет порядок и не трогает остальные объекты, `remove` по несуществующему id не бросает, `computed`-счётчики пересчитываются. Проверяйте сигналы прямым чтением.
2. Тест HTTP-слоя: `TicketApi.list()` формирует правильный URL и параметры; `create()` отправляет тело; ошибка 500 приводит к ожидаемому поведению. `verify()` — в `afterEach`.
3. Тест интерсептора: запрос с токеном получает заголовок `Authorization`, запрос с `SKIP_AUTH` — нет. Подумайте, как проверить порядок интерсепторов.
4. Тест компонента `TicketList`: подмените `TicketApi` заглушкой через провайдер, дождитесь `whenStable()`, проверьте, что отрисовалось нужное число карточек и что при пустом ответе показан пустой стейт. Никаких `fixture.detectChanges()` и никакого `fakeAsync`.
5. Тест взаимодействия: клик по карточке меняет выбор. Задайте входы через `componentRef.setInput()`.
6. Harness: напишите `TicketCardHarness` с методами `getTitle()`, `getStatus()`, `isSelected()`, `click()`. Перепишите тест из п.5 на harness и убедитесь, что переименование CSS-класса его не ломает.
7. Гард: протестируйте `adminMatchGuard` через `TestBed.runInInjectionContext()` с двумя вариантами роли.
8. Один e2e на Playwright: открыть список, отфильтровать по статусу, создать тикет, увидеть его в списке. Селекторы — по роли и тексту.

Edge cases на подумать:

- Тест проходит с `fixture.detectChanges()`, но падает с `await fixture.whenStable()`. О чём это говорит про компонент?
- В компоненте есть `httpResource`. Что нужно сделать в тесте, чтобы запрос ушёл и ответ пришёл?
- `httpTesting.verify()` падает с «one request is outstanding». Какие три причины наиболее вероятны?
- Вы подменили `TicketApi` заглушкой, но компонент всё равно шлёт настоящие запросы. Где искать ошибку?
- Тест на `@defer`-блок: как проверить, что показан `@placeholder`, а не содержимое?

## Разбор решения

`src/app/tickets/ticket-store.spec.ts` — самый быстрый и самый ценный тест:

```ts
import { TestBed } from '@angular/core/testing';
import { TicketStore } from './ticket-store';

describe('TicketStore', () => {
  // TestBed нужен только чтобы получить инстанс с его зависимостями;
  // ни компонента, ни шаблона, ни change detection здесь нет
  function createStore(): TicketStore {
    TestBed.configureTestingModule({ providers: [TicketStore] });
    return TestBed.inject(TicketStore);
  }

  it('добавляет тикет в начало списка', () => {
    const store = createStore();
    const before = store.tickets().length;

    store.add(makeTicket({ id: 999, title: 'New' }));

    // состояние читается напрямую: сигнал — это просто вызов
    expect(store.tickets()).toHaveLength(before + 1);
    expect(store.tickets()[0].id).toBe(999);
  });

  it('update сохраняет порядок и не пересоздаёт остальные объекты', () => {
    const store = createStore();
    const [first, second] = store.tickets();

    store.update(second.id, { title: 'Patched' });

    const after = store.tickets();
    expect(after[1].title).toBe('Patched');
    // важное свойство иммутабельного update: соседи — те же ссылки,
    // а значит OnPush-карточки не будут перепроверены (глава 03)
    expect(after[0]).toBe(first);
  });

  it('remove по несуществующему id ничего не ломает', () => {
    const store = createStore();
    const before = store.tickets();

    expect(() => store.remove(-1)).not.toThrow();
    expect(store.tickets()).toEqual(before);
  });

  it('счётчики выводятся из состояния', () => {
    const store = createStore();
    store.add(makeTicket({ id: 1000, assignee: null }));

    // computed пересчитался сам: никаких «обновить счётчик» в коде стора
    expect(store.unassignedCount()).toBeGreaterThan(0);
  });
});
```

`src/app/tickets/ticket-api.spec.ts` — HTTP-слой:

```ts
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { provideAppConfig } from '../core/app-config';
import { TicketApi } from './ticket-api';

describe('TicketApi', () => {
  let httpTesting: HttpTestingController;
  let api: TicketApi;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        TicketApi,
        provideHttpClient(),
        provideHttpClientTesting(),   // подменяет backend, реальной сети нет
        ...provideAppConfig({ apiUrl: '/api' }),
      ],
    });
    httpTesting = TestBed.inject(HttpTestingController);
    api = TestBed.inject(TicketApi);
  });

  // проверка «не осталось незакрытых запросов» для каждого теста сразу
  afterEach(() => httpTesting.verify());

  it('передаёт фильтры как параметры запроса', async () => {
    const promise = firstValueFrom(api.list({ status: 'open', q: 'pdf' }));

    const req = httpTesting.expectOne((r) => r.url === '/api/tickets');
    expect(req.request.method).toBe('GET');
    // params, а не подстрока URL: так тест не зависит от порядка параметров
    expect(req.request.params.get('status')).toBe('open');
    expect(req.request.params.get('q')).toBe('pdf');

    req.flush([]);
    await promise;
  });

  it('пробрасывает ошибку 500 наружу', async () => {
    const promise = firstValueFrom(api.list({}));
    httpTesting
      .expectOne('/api/tickets?page=1')
      .error(new ProgressEvent('error'), { status: 500, statusText: 'Server Error' });

    await expect(promise).rejects.toMatchObject({ status: 500 });
  });
});
```

Тест интерсептора — тот же `HttpTestingController`, но с реальной цепочкой:

```ts
describe('authInterceptor', () => {
  it('добавляет токен и уважает SKIP_AUTH', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthStore, useValue: { token: signal('t0ken') } },
      ],
    });
    const http = TestBed.inject(HttpClient);
    const httpTesting = TestBed.inject(HttpTestingController);

    void firstValueFrom(http.get('/api/tickets'));
    expect(httpTesting.expectOne('/api/tickets').request.headers.get('Authorization'))
      .toBe('Bearer t0ken');

    void firstValueFrom(
      http.get('/api/public/status', { context: new HttpContext().set(SKIP_AUTH, true) }),
    );
    expect(httpTesting.expectOne('/api/public/status').request.headers.has('Authorization'))
      .toBe(false);

    httpTesting.verify();
  });
});
```

`src/app/tickets/ticket-list.spec.ts` — компонент с подменённым API:

```ts
describe('TicketList', () => {
  const fakeApi = {
    list: (params: TicketListParams) => of(TICKETS.filter((t) => !params.status || t.status === params.status)),
  };

  async function setup() {
    TestBed.configureTestingModule({
      imports: [TicketList],                    // standalone-компонент: просто imports
      providers: [
        // Подмена через DI: не нужно мокать модуль, не нужно знать путь к файлу.
        // Заглушка типизирована структурно — компилятор проверит совместимость
        { provide: TicketApi, useValue: fakeApi },
      ],
    });

    const fixture = TestBed.createComponent(TicketList);
    // whenStable вместо detectChanges: даём Angular самому запланировать
    // проверку — так тест проверяет то же поведение, что и продакшен
    await fixture.whenStable();
    return fixture;
  }

  it('рисует карточку на каждый тикет', async () => {
    const fixture = await setup();
    const cards = fixture.nativeElement.querySelectorAll('app-ticket-card');
    expect(cards).toHaveLength(TICKETS.length);
  });

  it('показывает пустое состояние, когда ответ пустой', async () => {
    TestBed.configureTestingModule({
      imports: [TicketList],
      providers: [{ provide: TicketApi, useValue: { list: () => of([]) } }],
    });
    const fixture = TestBed.createComponent(TicketList);
    await fixture.whenStable();

    expect(fixture.nativeElement.textContent).toContain('No tickets match the filter');
  });
});
```

`src/app/tickets/ticket-card.harness.ts` — harness, не завязанный на разметку:

```ts
import { ComponentHarness, HarnessPredicate } from '@angular/cdk/testing';

export class TicketCardHarness extends ComponentHarness {
  // единственное место в тестах, где упоминается селектор компонента
  static hostSelector = 'app-ticket-card';

  static with(options: { title?: string } = {}): HarnessPredicate<TicketCardHarness> {
    return new HarnessPredicate(TicketCardHarness, options).addOption(
      'title',
      options.title,
      async (harness, title) => (await harness.getTitle()) === title,
    );
  }

  // локаторы спрятаны внутри: правка вёрстки правится здесь, а не в тестах
  private readonly title = this.locatorFor('.ticket-card__title');
  private readonly badge = this.locatorFor('.badge');

  async getTitle(): Promise<string> {
    return (await this.title()).text();
  }

  async getStatus(): Promise<string> {
    return (await this.badge()).text();
  }

  async isSelected(): Promise<boolean> {
    return (await this.host()).hasClass('ticket-card--selected');
  }

  async click(): Promise<void> {
    return (await this.host()).click();
  }
}
```

```ts
it('выбирает тикет по клику', async () => {
  const fixture = await setup();
  const loader = TestbedHarnessEnvironment.loader(fixture);

  const card = await loader.getHarness(TicketCardHarness.with({ title: 'Invoice PDF is empty' }));
  expect(await card.isSelected()).toBe(false);

  await card.click();
  await fixture.whenStable();

  // тест не знает ни одного CSS-класса: переименование вёрстки его не сломает
  expect(await card.isSelected()).toBe(true);
});
```

Тест гарда — через контекст инъекции:

```ts
it('пускает в админку только с ролью admin', () => {
  TestBed.configureTestingModule({
    providers: [{ provide: CurrentUser, useValue: { roles: signal(['agent']) } }],
  });

  // гард — функция с inject() внутри, поэтому её нужно вызвать в контексте
  const result = TestBed.runInInjectionContext(() =>
    adminMatchGuard({} as Route, [] as UrlSegment[], {} as RouterStateSnapshot),
  );

  expect(result).toBe(false);
});
```

Один e2e-сценарий на Playwright:

```ts
test('агент создаёт тикет и видит его в списке', async ({ page }) => {
  await page.goto('/tickets');

  // селекторы по роли и тексту: устойчивы к правкам разметки
  await page.getByRole('button', { name: 'open' }).click();
  await page.getByRole('button', { name: 'New ticket' }).click();

  await page.getByLabel('Title').fill('Printer does not respond');
  await page.getByRole('button', { name: 'Save' }).click();

  await expect(page.getByText('Printer does not respond')).toBeVisible();
});
```

Ответы на edge cases:

- Это значит, что компонент **не уведомляет** Angular об изменении: ручной `detectChanges()` принудительно синхронизирует и скрывает проблему, а `whenStable()` ждёт запланированной проверки, которую никто не запланировал. Причина обычно в мутации вместо `set` или в записи в обычное поле из асинхронного колбэка (глава 03). В продакшене такой компонент тоже не обновится — то есть тест обнаружил реальный баг, а не «неудобство API».
- Ничего особенного: `httpResource` подписывается сам, поэтому достаточно `provideHttpClientTesting()`, ожидание `expectOne` и `flush()`, а затем `await fixture.whenStable()`, чтобы шаблон увидел новое значение. Важно помнить, что ресурс отправляет запрос при создании компонента, так что `expectOne` идёт **после** `createComponent`.
- Три частые причины: (1) поллинг или `interval` в компоненте отправил ещё один запрос, о котором тест не знает; (2) `httpResource` перезапросил данные, потому что изменился читаемый им сигнал; (3) вы ждали `whenStable()` после `flush()`, и за это время ушёл следующий запрос цепочки (например, `reload()` после мутации). Диагностика — `httpTesting.match(() => true)` перед `verify()`, чтобы увидеть, что осталось.
- Скорее всего провайдер объявлен не там, где ищется зависимость: компонент (или его дочерний компонент) объявил `providers: [TicketApi]` у себя, и локальный провайдер перекрыл тестовый (глава 04). Второй вариант — сервис инжектит не `TicketApi`, а `HttpClient` напрямую, и подменять надо было backend (`provideHttpClientTesting`). Третий — вы сконфигурировали `TestBed` дважды и второй вызов не применился, потому что компонент уже создан.
- Через `DeferBlockBehavior.Manual`: тогда блок не загружается автоматически, и вы явно управляете его состоянием, получив `fixture.getDeferBlocks()`. Без этого режима поведение зависит от триггера, и проверка «показан placeholder» становится гонкой.

## Проверь себя

1. Почему `await fixture.whenStable()` предпочтительнее `fixture.detectChanges()`, и какой класс ошибок скрывает второй вариант?
2. Почему `fakeAsync`/`tick` перестали быть рабочим инструментом, и что использовать вместо них?
3. В чём преимущество подмены зависимостей через DI перед `jest.mock`? Приведите два конкретных следствия.
4. Почему сигнальный стор можно тестировать без `TestBed`, и что это даёт набору тестов?
5. Зачем нужен harness, если можно найти элемент через `querySelector`?

<details>
<summary>Ответы</summary>

1. `detectChanges()` — это приказ «проверь шаблон сейчас», выполняемый независимо от того, уведомлял ли кто-нибудь фреймворк об изменении. `whenStable()` дожидается **запланированной** синхронизации, то есть проверяет ту же цепочку, что произойдёт в приложении. Скрываемый класс ошибок — «состояние изменилось, но уведомления не было»: мутация массива вместо `set`, запись в обычное поле из `setTimeout` или колбэка сторонней библиотеки, `setValue` формы без отражения в сигналы (главы 03 и 10). С `detectChanges()` такой компонент проходит тесты и ломается в продакшене; с `whenStable()` тест падает там, где есть реальный дефект.
2. `fakeAsync`/`tick` построены на патчах zone.js, а ранер Vitest (дефолтный с v21) zone.js не патчит — поэтому они там просто не работают, и документация больше не рекомендует `fakeAsync` в принципе. Замена: обычные `async`/`await` для промисов, `await fixture.whenStable()` для ожидания синхронизации Angular, `vi.useFakeTimers()`/`vi.advanceTimersByTime()` для управления таймерами, а для потоков — прямой контроль источника (`Subject.next()`) вместо виртуального времени.
3. `jest.mock('./api')` работает на уровне модульной системы: нужно указать путь (ломается при переносе файла), помнить про hoisting, а сам мок типизируется вручную и легко расходится с реальным API. Провайдер в `TestBed` работает на уровне токена: `{ provide: TicketApi, useValue: fake }`. Следствия: (а) тест не зависит от расположения файлов и не сломается от рефакторинга структуры; (б) заглушка проверяется компилятором на совместимость с токеном, поэтому изменение сигнатуры сервиса ломает компиляцию теста, а не приводит к ложно зелёному прогону. Плюс третье: тем же механизмом подменяется что угодно — конфиг через `InjectionToken`, `Router`, backend HTTP.
4. Потому что сигнальный стор — обычный класс без шаблона: состояние читается вызовом сигнала, команды — вызовом методов, а `computed` пересчитывается сам при чтении. Ни компилятора шаблонов, ни change detection здесь не нужно (`TestBed` пригодится только чтобы собрать зависимости — либо их передают вручную). Набору тестов это даёт скорость (нет создания компонентов) и устойчивость: такие тесты не ломаются от правок вёрстки и проверяют поведение, а не разметку. Это и есть практическая причина выносить логику из компонентов в сервисы (глава 05).
5. Потому что `querySelector('.ticket-card__title > span')` привязывает тест к структуре разметки: любое переименование класса или добавление обёртки ломает тесты, не имеющие отношения к изменению. Harness — это API компонента для тестов: `getTitle()`, `isSelected()`, `click()`. Селекторы живут в одном месте (внутри harness), поэтому правка вёрстки правится один раз. Дополнительно harness скрывает асинхронность (все методы возвращают промисы и сами дожидаются стабилизации) и переиспользуется между юнит- и интеграционными тестами, а библиотечные компоненты часто поставляют свои harness'ы — тогда вам не нужно знать их внутреннюю разметку вовсе.

</details>

## Частая ошибка

Первая — расставить `fixture.detectChanges()` после каждой строки, по образцу тестов из старых статей. В zone-эпоху это было необходимостью, сейчас это активно вредно: принудительная проверка скрывает именно те дефекты, которые тест должен ловить. Компонент, забывший перевести состояние в сигнал, с `detectChanges()` проходит тест и ломается в браузере; хуже того, привычка приводит к тестам, которые «зелёные» ровно потому, что синхронизацию вызывали руками в нужных местах. Правильная форма — `await fixture.whenStable()` там, где нужно дождаться обновления, и ничего между действиями. Если тест без `detectChanges()` не проходит — это диагноз коду, а не тесту.

Вторая — присваивание входа напрямую: `fixture.componentInstance.ticket = ticket`. С сигнальными входами это не скомпилируется (`input()` возвращает read-only сигнал), а с оставшимися `@Input()`-полями пройдёт молча и оставит компонент непомеченным — шаблон не обновится, и `expect` упадёт на пустом DOM без внятной причины. React-опыт подсказывает «пропсы это просто значения», но в Angular вход — часть контракта, за которым стоит уведомление фреймворка. Правильно: `fixture.componentRef.setInput('ticket', ticket)`, и затем `await fixture.whenStable()`. Тот же принцип, что с динамическими компонентами из главы 11.
