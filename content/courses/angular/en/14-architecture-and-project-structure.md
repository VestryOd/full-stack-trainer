# Architecture and project structure

## Theory

### Organizing by feature

```
             Feature-based layout: Support Desk
src/app/
├── app.ts                the entry point
├── app.config.ts         root providers
├── app.routes.ts         the map of screens
├── core/                 what the whole app needs
│   ├── app-config.ts     the config token (chapter 04)
│   ├── interceptors.ts   auth, logging, errors (chapter 08)
│   └── auth-store.ts     the current user and roles
├── ui/                   reusable, no domain
│   ├── data-table/       nothing about tickets (chapter 11)
│   └── modal/
└── tickets/              the feature: all things ticket
    ├── ticket.ts         the domain model
    ├── ticket-api.ts     the feature's HTTP layer
    ├── ticket-store.ts   domain state (chapter 05)
    ├── ticket-list/      a screen: ts + html + css + spec
    ├── ticket-detail/
    └── ticket-form/
```

The official style guide states the rules outright, and they match practice:

- **Group by features**, not by code type. The guide advises against creating `components/`, `directives/` and `services/` directories: they scatter one feature across four places, and any change touches half the tree.
- **One concept per file** — one component, service or directive.
- **Tests next to the code**, `*.spec.ts` in the same directory.
- **No `utils.ts`, `helpers.ts` or `common.ts`.** The guide explicitly warns against such names: they describe nothing, so everything ends up inside them.

The test for "is this one feature or two" is simple: if two screens always change together and share a model, that is one feature. If one can be deleted without touching the other, that is two.

### What is wrong with core/shared

Every name below looks harmless, and every one of them ends up holding the wrong thing.

| what goes in | why it hurts | where it belongs |
|---|---|---|
| `shared/components` | domain leaks into the shared layer | `ui/` — domain-free only |
| `shared/utils.ts` | a file nobody ever cleans | next to whoever uses it |
| `shared/models` | every feature depends on every type | the model lives in its feature |
| `shared/services` | a feature's service becomes global | in the feature it belongs to |
| `core/` everything | `core/` grows faster than features | `core/` = truly app-wide only |

The style guide says it outright: organize by feature, and do **not** create directories by code type (`components`, `directives`, `services`). Avoid `utils.ts` as well.

`CoreModule` + `SharedModule` is a pattern from the NgModules era, and there it had a technical justification. `CoreModule` was imported once into `AppModule`, to keep singletons single. `SharedModule` was imported into every feature module, for components and pipes. With standalone components the justification is gone: providers are configured by `provide*` functions, and components are imported individually.

The problem is not the names but the fact that "shared" is an invitation to put anything there. A working replacement splits that layer in two:

- **`core/` holds only what the application cannot start without** — config, auth, interceptors, error handling.
- **`ui/` holds components that know nothing about the domain** — a table, a modal, a button.

Everything else lives inside its own feature. The membership test for `ui/` is one line: if a component imports a domain model, it is not `ui/`.

### Boundaries between features

A rule worth adopting as a contract:

- A feature may depend on `core/` and `ui/`.
- A feature does **not** depend on another feature's internals. If `admin` needs the ticket list, it takes `TicketStore` from the public part of `tickets/` rather than importing `tickets/ticket-list/ticket-list.css` or private helpers.
- A dependency shared by two features is a sign the shared part should be extracted (into `core/`, into `ui/`, or into a third feature).

In plain Angular these boundaries rest on discipline and code review. They can be automated with the ESLint rule `import/no-restricted-paths` or with `eslint-plugin-boundaries`.

In a monorepo it is done systematically: with tags and `@nx/enforce-module-boundaries`, where the linter knows the dependency graph. See the Nx course, the chapter on library architecture and module boundaries.

The connection matters: **folders in one application and libraries in a monorepo solve the same problem**. A monorepo just gives the boundary a mechanical check.

### Smart and dumb in Angular terms

The classic "a smart component fetches data, a dumb one only displays it" takes a concrete shape in Angular:

- **Smart (a screen, a routed component)**: injects stores and services, reads route params, calls commands. Usually one per route.
- **Dumb (presentational)**: receives everything through `input()`, reports outwards through `output()`, injects no domain services. Such a component is testable without `TestBed` mocks and is reusable.

But there is a nuance React does not have: dependency injection (DI) makes "smartness" cheap. Any component can inject a store in one line, so the boundary erodes on its own and has to be maintained deliberately.

A pragmatic compromise works here. Presentational components in `ui/` stay strictly on inputs and outputs. Components inside a feature may inject their own feature's store. That does not make them unreusable, because they are not needed outside the feature anyway.

### Barrel files and circular imports

An `index.ts` re-exporting a folder's contents looks tidy and creates two problems.

The first is **cycles**. `tickets/index.ts` exports `ticket-store.ts`, which imports `ticket-api.ts`, which imports a type from `tickets/index.ts`. At runtime that cycle yields `undefined` in the most unexpected places, and the classic symptom is `NG0201: No provider for undefined` from chapter 04.

The second is **extra code in the bundle**. Importing one symbol drags in the whole barrel. If tree-shaking cannot help, because a module has side effects, everything ships in the chunk.

Practice: import by direct paths inside the application, and introduce a barrel only at a genuine boundary. That boundary is where a feature really is a library with a public API. In a monorepo it is the library's entry point.

### Legacy: NgModules and the migration path

An NgModules project is not rewritten in one go. There is an official schematic with three modes, run in sequence, with the application verified between steps:

```bash
ng generate @angular/core:standalone   # pick the mode in the prompt
```

- `convert-to-standalone` — converts components, directives and pipes to standalone;
- `prune-ng-modules` — removes the modules that became unnecessary;
- `standalone-bootstrap` — switches startup to `bootstrapApplication`.

The order matters, and after every step you must confirm the app still works. A mixed state is normal during the migration. A standalone component can be imported into an NgModule through `imports`, and an NgModule can be used by a standalone component the same way. That is what makes feature-by-feature progress possible.

The order of work in a real project:

1. Standalone first, because it unblocks everything else.
2. Then the new control flow (`ng generate @angular/core:control-flow`).
3. Then signal inputs and queries.
4. Only then zoneless, because it requires state to already live in signals (chapter 03).

### A checklist for reading an unfamiliar project

Eight questions, in this order, tell you almost everything about a codebase.

| the question | where to look | what it tells you |
|---|---|---|
| which version, what was migrated | `package.json`, `angular.json` | the API generation |
| is zone.js present? | `package.json`, polyfills | zoneless or not (chapter 03) |
| how the app boots | `main.ts` | `bootstrapApplication` or a module |
| what is provided globally | `app.config.ts` or `AppModule` | HTTP, router, interceptors |
| the map of screens | `app.routes.ts` | features, lazy borders, guards |
| where state lives | services with `signal`/`BehaviorSubject` | the state model (chapter 05) |
| how it talks to the network | `HttpClient`, `httpResource`, interceptors | the data layer (chapter 08) |
| how alive the tests are | the runner in `angular.json`, `*.spec.ts` | whether refactoring is safe |

The same order works as an interview answer, when you are asked how you would find your way around an unfamiliar project.

## React parallels

- **Structure is a convention, not a freedom.** In React the structure is decided by the team and the metaframework (`app/` in Next.js dictates routing). In Angular routing is not tied to folders, so the discipline is entirely yours. But Angular has an official style guide with concrete rules, and that is a rare case where the right way is documented.
- **`core/` means providers, not "context providers".** In React shared dependencies usually take the shape of a tree of contexts around the app. In Angular their equivalent is `provide*` functions in `app.config.ts` (chapter 04). The global layer is then a flat list of providers rather than wrapper components.
- **Smart/dumb works the same, but the temptation is stronger.** In React making a component "smart" requires calling a store hook, and that is visible in the code. In Angular one line of `inject(Store)` is enough, so every component quietly becomes smart and none stay reusable.
- **Barrel files: the same problem, different consequences.** An `index.ts` creates cycles and hurts tree-shaking in React projects too. But in Angular a cycle also breaks DI. The provider receives `undefined`, and the error reads `No provider for undefined` instead of a sensible message about imports.
- **Where the habit breaks:** expecting a "feature folder" to be a module with isolation. In Angular a plain folder gives no isolation whatsoever: anything can import anything, and nothing stops `import '../tickets/ticket-list/private-helper'`. Isolation appears only with lint rules or with library boundaries in a monorepo.

## What you will see in legacy code

- **`CoreModule` and `SharedModule`** with a comment saying "import CoreModule only in AppModule", sometimes with a constructor guard (`if (parentModule) throw new Error(...)`). With standalone components the pattern is obsolete.
- **Organization by type:** `app/components/`, `app/services/`, `app/models/`, `app/pipes/` — the directories the style guide explicitly discourages. The sign is simple: understanding one feature requires opening four folders.
- **A `SharedModule` dragging in half the application:** it imports `CommonModule`, `FormsModule`, Material and 30 components, and exports everything. Every lazy module then pulls it whole, which is a classic cause of bloated chunks (chapter 12).
- **`app/features/*/**.module.ts` with `forRoot()`/`forChild()`** — module-based configuration; the modern equivalent is a `provideFeature()` function (chapter 04).
- **Barrels on every folder** with `import { X } from '../..'`, which is where cycles come from. Sometimes there is a `// eslint-disable-next-line import/no-cycle` next to it, which means "we know and did not fix it".
- **`environment.ts`/`environment.prod.ts` with `fileReplacements`** as the only configuration mechanism; chapter 04 offers a token instead. Also `assets/` instead of `public/`, which new projects renamed.

## What we add to the project

Support Desk is reorganized by feature:

- `core/` shrinks to what is genuinely shared.
- `ui/` is cleared of domain knowledge.
- Everything ticket-related gathers in `tickets/`.
- An ESLint rule forbids importing one feature's internals from another.
- A project checklist is written down.

## Exercise

**Input:** the project from chapter 13 — working, but grown organically.
**Output:** a structure you can explain to a new developer in five minutes.

Requirements:

1. Take inventory: list every file and answer, for each, which feature it belongs to and why. Files whose answer is "all of them" are candidates for `core/`; "no particular one, and it knows no domain" belongs in `ui/`.
2. Reorganize the tree: `core/`, `ui/`, `tickets/`, `admin/`. Inside a feature: the model, the api, the store and screen folders. Verify nothing broke after the move (the tests from chapter 13 pay off here).
3. Eliminate `shared/`: every file in it must move either to `ui/` (if it knows no domain), or into a specific feature, or into `core/`. If something fits none of them, it is probably two different things in one file.
4. Boundaries: add an ESLint rule forbidding imports from `tickets/**` other than its public files (`ticket.ts`, `ticket-store.ts`, `ticket-api.ts`) inside `admin/`. Verify the rule actually fires.
5. Barrel audit: find every `index.ts` and keep only those sitting on a real boundary. Replace the rest with direct imports. If you find a cycle, describe how it manifested.
6. Smart/dumb: confirm that no component in `ui/` injects a domain service or imports a domain model. Where one does, lift the data into inputs.
7. Write a one-page `ARCHITECTURE.md`: the folder map, the dependency rules, where to find what. This is the document you hand a new developer.

Edge cases to think about:

- The `TicketCard` component is needed both in `tickets/` and in the admin section. Where does it go, and what must be true for that?
- Two features use the same date-formatting function. Where does it belong?
- The ESLint rule forbids imports between features, but one feature must open another's screen. How do you do that without breaking the boundary?
- You found a cycle between `ticket-store.ts` and `ticket-api.ts` through a barrel. How does it manifest at runtime?
- The `Ticket` model is needed by both the frontend and a mock backend in the same repository. What changes if the project moves into a monorepo?

## Solution walkthrough

The resulting tree (the same diagram, with decisions on the debatable files):

```
src/app/
├── app.ts, app.config.ts, app.routes.ts
├── core/
│   ├── app-config.ts          # the token + provider (chapter 04)
│   ├── http-context.ts        # SKIP_AUTH, SKIP_RETRY (chapter 08)
│   ├── interceptors.ts        # auth, logging, errors
│   ├── auth-store.ts          # the current user and roles
│   ├── has-role-directive.ts  # used by every feature (chapter 06)
│   └── navigation-progress.ts # navigation indicator (chapter 09)
├── ui/
│   ├── data-table/            # generic, no domain (chapter 11)
│   ├── modal/
│   └── priority-picker/       # careful: it knows TicketPriority
└── tickets/
    ├── ticket.ts              # the model: the public part
    ├── ticket-api.ts          # public: other features use it
    ├── ticket-store.ts        # public
    ├── ticket-rules.ts        # the rules multi token (chapter 04)
    ├── sla-remaining-pipe.ts
    ├── overdue-directive.ts
    ├── ticket-list/           # ts + html + css + spec + harness
    ├── ticket-detail/
    └── ticket-form/
```

The debatable case: `PriorityPicker` from chapter 10 imports `TicketPriority`, so it is **not** `ui/`. Two honest ways out:

```ts
// Option 1: keep it in tickets/ — it is about the ticket domain and
// pointless outside it
// tickets/priority-picker/priority-picker.ts

// Option 2: make it genuinely generic by parameterizing the values,
// and then it legitimately lives in ui/
export class OptionPicker<T extends string> implements ControlValueAccessor {
  readonly options = input.required<readonly T[]>();   // the domain arrives from outside
}
```

The rule is simple: a component in `ui/` must import nothing from features. If it does, it either moves into a feature or gets generalized.

ESLint boundaries inside one application:

```js
// eslint.config.js
{
  files: ['src/app/admin/**/*.ts'],
  rules: {
    'no-restricted-imports': ['error', {
      patterns: [
        {
          // Only the tickets feature's public contract is allowed:
          // the model, the api and the store. Screen internals are not
          group: [
            '**/tickets/**',
            '!**/tickets/ticket.ts',
            '!**/tickets/ticket-api.ts',
            '!**/tickets/ticket-store.ts',
          ],
          message:
            'Import only ticket.ts, ticket-api.ts or ticket-store.ts from tickets. ' +
            'Screen internals are the feature\'s private part.',
        },
      ],
    }],
  },
}
```

The rule is cheap, but it is what turns an agreement into a checkable constraint. In a monorepo the same role belongs to `@nx/enforce-module-boundaries` with tags. There the boundary is a library rather than a folder, and the linter reasons over the dependency graph. See the Nx course, the chapter on library architecture and module boundaries.

Cross-feature navigation without breaking the boundary:

```ts
// admin/admin-reports.ts
// not allowed: import { TicketList } from '../tickets/ticket-list/ticket-list';
// allowed: navigate by route — the feature decides which component to show
protected openTickets(): void {
  void this.router.navigate(['/tickets'], { queryParams: { status: 'new' } });
}
```

A route *is* a screen's public interface: it does not reveal which component sits behind it and creates no import-level coupling.

`ARCHITECTURE.md` — the single page that saves weeks:

```md
# Support Desk architecture

## Map
- `core/` — what the whole app needs: config, auth, interceptors, navigation.
- `ui/` — reusable components with no domain knowledge.
  Importing from features is forbidden.
- `<feature>/` — everything about one domain area: model, api, store, screens.

## Dependency rules
- feature → `core/`, `ui/`: allowed.
- feature → another feature: only through its public files (model, api, store).
- `ui/` → feature: forbidden (enforced by ESLint).
- moving between features goes through the router, not through component imports.

## Where to find what
- global providers — `app.config.ts`
- the screen map and guards — `app.routes.ts`
- domain state — `<feature>/<feature>-store.ts`
- network access — `<feature>/<feature>-api.ts` + `core/interceptors.ts`
```

Answers to the edge cases:

- `TicketCard` knows about `Ticket`, so it cannot live in `ui/`. Its proper place is `tickets/`. The admin section may use it **only** if `ticket-card` is declared part of the feature's public contract. That means it sits at the top level of `tickets/`, not inside a screen folder. There is an alternative when a card is needed across domains. Split it into a presentational `ui/entity-card` with a title, a badge and slots through `ng-content` (chapter 11). The domain part becomes `tickets/ticket-card`, which configures it.
- If the function formats a **date**, it belongs in `ui/` or `core/` as a shared presentation utility. Give it a descriptive file name: `format-relative-time.ts`, not `utils.ts`. If it formats a **ticket's SLA** (service level agreement), it belongs in `tickets/`. The second feature that wants it should either go through the feature's public contract or have its own. Identical code does not always mean identical meaning.
- Through the router: `router.navigate(['/tickets'])`. A route is the public interface behind which the feature decides what to render; no import-level coupling appears. If you need embedding rather than navigation, the feature must export the component as part of its contract — and then the import is legitimate.
- It manifests as `undefined` where a class was expected. During module loading one of the two is not initialized yet, so the provider receives `undefined` instead of `TicketApi`. The error then reads `NG0201: No provider for undefined`, or `Cannot read properties of undefined (reading 'ɵprov')`, in a file unrelated to the cycle. The fix is replacing barrel imports with direct ones.
- In a monorepo `Ticket` becomes a contracts library (`libs/shared/api-types`) that both the frontend and the backend depend on. A contract change then becomes visible in the graph, and the linter prevents the frontend from importing server code. That is precisely the scenario monorepos are adopted for. See the Nx course, the chapters on library architecture and the fullstack link.

## Check yourself

1. Why does the style guide recommend grouping by feature and not creating `components/`, `services/` folders? What specifically breaks with type-based organization?
2. What was the technical justification for `CoreModule`/`SharedModule`, and why did it disappear with standalone components?
3. What tells you a component belongs in `ui/` rather than in a feature? Give a borderline example.
4. Why are barrel files specifically dangerous in Angular, and how does a cycle created through `index.ts` manifest?
5. In what order would you modernize an Angular 15 project with NgModules, and why is zoneless the last step?

<details>
<summary>Answers</summary>

1. Because code cohesion follows the domain, not the technical type. With type-based organization one feature is spread over four folders. Adding a field to a ticket means opening `models/`, `services/`, `components/` and `pipes/`. It also becomes impossible to see what belongs to the feature and what does not. Three things break. Deleting a feature leaves remains in every folder. Boundaries stop working, because importing "your" service and someone else's looks identical and no rule can tell them apart. Lazy loading suffers, because one feature's code is interleaved with another's and chunk splitting gets harder. Feature-based organization solves all three: a feature is a folder you can read whole, extract into a library, or delete.
2. `CoreModule` existed because in the module era providers were registered in modules. To keep singletons single, the module holding them was imported only into `AppModule`, hence the guard against a second import. `SharedModule` existed because components and pipes had to be declared and exported by a module, and imported by every feature module. Standalone components removed both reasons. Providers are configured by `provide*` functions in `app.config.ts` or on a route. Components are imported individually into the `imports` of whoever uses them. What remains is organizational separation, and that is better expressed by `core/` and `ui/` folders with explicit rules than by modules.
3. The test is mechanical: a component in `ui/` **imports nothing from features** — no model, no service, no type. It is parameterized by generics, inputs and slots (`ng-content`). The borderline case from the project is `PriorityPicker`: it imports `TicketPriority`, so formally it is not `ui/`. There are two options. Keep it in `tickets/`, since it is about the ticket domain and meaningless outside it. Or generalize it into `OptionPicker<T extends string>` that receives the options as an input, and then it lives in `ui/` legitimately. The wrong third option is keeping it in `ui/` with the domain import. Then `ui/` stops being a reusable layer and turns into yet another `shared/`.
4. Two ways. First, cycles: a barrel re-exports files that import each other through the same barrel, and the cycle closes unnoticed. In Angular that is especially bad, because DI suffers. At the moment the provider is evaluated the class is still `undefined`. The error then reads `NG0201: No provider for undefined`, or a crash mentioning `ɵprov`. It appears in a file unrelated to the cycle, which makes diagnosis expensive. Second, the bundle: importing one symbol pulls the whole barrel. If any module has side effects, tree-shaking cannot save you, and extra code ships in the chunk. Hence the practice: direct paths inside the application, barrels only at genuine public boundaries.
5. The order has four steps. First, the standalone migration with `ng generate @angular/core:standalone` in three passes: `convert-to-standalone`, then `prune-ng-modules`, then `standalone-bootstrap`, verifying the app between steps. Second, the new control flow (`ng generate @angular/core:control-flow`). Third, signal inputs and queries, moving state onto signals. Fourth and last, zoneless. Standalone comes first because it unblocks everything else: functional providers, lazy `loadComponent`, dropping `SharedModule`. Zoneless comes last because it requires changes to be announced explicitly, so state must already be in signals or the code must call `markForCheck`. Turning zoneless on over code full of plain fields and mutations gives you an application that stops updating in unpredictable places (chapter 03).

</details>

## Common mistake

The first is "architecture first". A developer arriving from React with large-app experience starts with scaffolding. That means `core/`, `shared/`, `features/`, a `components/services/models` trio inside every feature, barrels at every level, and abstract base classes for later.

In a three-screen application that produces a structure with more plumbing than code, where any change requires edits in four places. It is cheaper to start flat: a feature is a folder, and files sit next to each other. Introduce a layer once the second or third feature appears with real duplication. The official style guide backs exactly that path: group by feature, one concept per file, no folders by code type.

The second is a `shared/` growing faster than the application. It starts innocently: a component is needed in two places, so it moves to `shared/components`. Then `utils.ts` moves in, then `models/`, then a service that "seems shared". Six months later `shared/` knows every domain, every feature depends on all of it, and lazy chunks drag in half the application (chapter 12).

The sign to check in review is simple: **a file in the shared layer imports something from a feature**. If it does, it is not shared, and it belongs either in the feature or, generalized, in `ui/`. One more habit from the style guide: never create files named `utils.ts`/`helpers.ts`/`common.ts`. A name that describes nothing guarantees that everything ends up inside.
