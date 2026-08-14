# The Angular model and your first run

## Theory

### A framework, not a library

React is a rendering library. Everything else is your choice: the router, the data layer, forms, DI, the testing stack, the build. Angular is a framework: the same problems are already solved inside the package, and solved consistently with each other.

```
REACT: a library plus a stack you assemble           ANGULAR: one shipped package
┌───────────────────────────┐                 ┌───────────────────────────────────────┐
│ react + react-dom         │                 │ @angular/core                         │
│                           │                 │                                       │
│ routing   react-router    │                 │ routing   @angular/router             │
│ data      TanStack Query  │                 │ data      HttpClient, httpResource    │
│ forms     react-hook-form │                 │ forms     @angular/forms              │
│ DI        Context + props │                 │ DI        injector in the core        │
│ tests     Vitest + RTL    │                 │ tests     TestBed (+ Vitest)          │
│ build     Vite / Next.js  │                 │ build     Angular CLI, @angular/build │
└───────────────────────────┘                 └───────────────────────────────────────┘
every line is a separate choice with                one major for everything, one
its own major and release cycle                   ng update, fewer upfront decisions
```

What that buys you in practice:

- **One upgrade for everything.** `ng update` bumps the core, router, forms, HTTP and CLI in one consistent step and runs **migration schematics** — codemods that mechanically rewrite your code for the new APIs. In a React stack an upgrade is N independent migrations, each with its own guide.
- **One way to do the routine things.** An unfamiliar Angular project reads faster: routing is where you expect it, HTTP goes through `HttpClient`, dependencies come from the injector. Two React projects on the same stack can have nothing in common at all.
- **A compiler, not just a runtime.** Templates are compiled, and the types inside them are checked (`strictTemplates`). A typo in a property name in a template is a build error, not a blank spot on the screen.

The price is exactly what you would expect: more conventions and more APIs to know before you write the first line; less freedom to bring "your" router or "your" data layer; idioms of its own (decorators, DI, templates) that cannot be explained away as "it's just JS". Plus sheer size — you cannot adopt Angular partially the way you can adopt React.

### The mental model: an instance, not a function

This is the core difference, and almost every mistake a React developer makes in Angular grows out of it.

In React a component is a function that runs again on every update. State lives outside the function (in hooks) precisely because the function body is single-use. In Angular a component is a **class whose instance is created once**, when the view enters the tree, and lives until the view is destroyed. Instance fields *are* the state — they need no external container. The class body and the constructor are not re-run on updates; only the template's expressions are re-evaluated.

```
    REACT: a function of state         ANGULAR: a long-lived instance
┌───────────────────────────────┐    ┌───────────────────────────────┐
│ setState(next)                │    │ count.set(next)               │
│               ↓               │    │               ↓               │
│ the component function runs   │    │ the signal marks dependent    │
│ again — new closures, new     │    │ templates dirty and schedules │
│ props for the children        │    │ a check                       │
│               ↓               │    │               ↓               │
│ React walks the subtree;      │    │ change detection walks the    │
│ children re-render too unless │    │ marked views; class instances │
│ memo stops them               │    │ stay, only the DOM changes    │
└───────────────────────────────┘    └───────────────────────────────┘
  state lives outside, in hooks;     the class instance is created once
the function body *is* the render    per view lifetime; the class body is
                                         never re-run on an update
```

Consequences worth accepting up front:

- **There are no "rules of hooks"**, because closures are never rebuilt: call order carries no meaning, a conditional call breaks nothing. `inject()` has its own constraint instead — the injection context (chapter 04).
- **Stale closures disappear as a class of bug:** `this.filter` is always current, because it is a field on a live object rather than a value captured in an old render.
- **A separate mechanism appears — change detection.** Since the class body is never re-run, something has to decide when to re-evaluate the template and touch the DOM. The answer is signals (chapter 02) and change detection (chapter 03).
- **Mutation is not blocked by the runtime, but it is just as dangerous.** In React, mutating state left you with no re-render. In Angular with `OnPush` (now the default) mutating an object inside a signal likewise tells the system nothing — a different mechanism, the same symptom.

### Where Angular is right now: versions and API status

Angular has changed fast over the last three years, and the internet is full of material describing the previous generation of APIs as "modern". The reference point at the time of writing:

- **The current major is Angular v22** (released 3 June 2026). A major lands every six months, each with its own support window and an LTS phase; v21 (November 2025) is in LTS.
- **Stable and the main path:** standalone components (the default since v19), `inject()`, the new control flow `@if`/`@for`/`@switch`/`@let`, `@defer`, functional guards and interceptors, and all signal-based reactivity — `signal`, `computed`, `effect`, `linkedSignal`, signal-based `input()`/`output()`/`model()` and signal queries (stabilized in v20), async reactivity via `resource()`/`httpResource`, and Signal Forms (stabilized in v22), plus the esbuild/Vite build system (`@angular/build`).
- **Zoneless change detection is the default for new projects since v21.** A fresh workspace simply has no `zone.js`; `provideZonelessChangeDetection()` shows up only when an older project is upgraded.
- **`OnPush` is the default for components since v22.** Not via a schematic setting: a component with no `changeDetection` field now runs in `OnPush` mode. The old "always check" behaviour got the honest name `ChangeDetectionStrategy.Eager` (an alias of `Default`, added in v21.2), and the `ng update` migration to v22 writes `Eager` explicitly into every existing component so old code keeps behaving as before.
- **Experimental / developer preview** (worth knowing about, not worth building a course on): selectorless components (importing a component directly in the template, with no string selector), the `@Service` decorator, `injectAsync()`, and `@boundary` for handling errors in templates.
- **Deprecated:** the webpack-based build and the `@angular-devkit/build-angular` builders. Karma/Jasmine have been displaced by Vitest (`--test-runner` defaults to `vitest`), but you will still meet them in every other existing project.

The practical takeaway: check API status on [angular.dev](https://angular.dev) and its roadmap page, not in a blog post. The gap between "how articles from 2023 write it" and "how it is written now" is wider here than in React.

### TypeScript, decorators, strict

TypeScript is not optional in Angular: the template compiler works off types, and DI relied on constructor type metadata until recently. `ng new` creates a workspace with `--strict` on by default, and that covers more than the TS strict flags — it also turns on `strictTemplates`, which type-checks the inside of templates (component input types, binding expression types, event handler signatures).

Decorators (`@Component`, `@Injectable`, `@Directive`, `@Pipe`) are neither runtime magic nor decorative annotations. They are **metadata for the Angular compiler**: at build time (AOT) it reads the object inside the decorator, compiles `template` into rendering instructions and writes the result into the class. That is why decorator fields must be statically analyzable — you cannot assemble a metadata object at runtime and hand it to `@Component`.

### The Angular CLI and the project layout

The CLI here is not a convenience wrapper but part of the framework: building, the dev server, tests, code generation and migrations all live in it.

- `ng new <name>` — a new workspace. Useful flags: `--style`, `--ssr`, `--package-manager`, `--test-runner` (defaults to `vitest`), `--file-name-style-guide` (defaults to `2025` — files without the `.component`/`.service` suffixes), `--ai-config`, `--strict` (defaults to `true`).
- `ng generate <schematic>` (`ng g`) — generation via schematics: `component`, `service`, `directive`, `pipe`, `guard`, `interceptor`, `resolver`. `--dry-run` prints what would be created without writing anything.
- `ng serve` — dev server, `ng build` — production build (chapter 15), `ng test` — tests (chapter 13), `ng update` — upgrades with migrations.
- `angular.json` — the workspace configuration: projects, targets (`build`/`serve`/`test`), environment configurations and **schematic defaults** (in an existing project the old naming conventions are usually written in there — which is why `ng g` in a real project behaves differently from `ng g` in a fresh one).

The application skeleton `ng new` produces (2025 naming style — no type suffixes in file or class names):

```
support-desk/
├── angular.json          workspace configuration and targets
├── package.json          all @angular/* on one version
├── tsconfig.json         base TS config + angularCompilerOptions
├── tsconfig.app.json     application build config
├── tsconfig.spec.json    test config
├── public/               static assets, copied into the bundle as-is
└── src/
    ├── main.ts           entry point: bootstrapApplication(App, appConfig)
    ├── index.html         <app-root></app-root>
    ├── styles.css        global styles
    └── app/
        ├── app.ts        root component (class App, selector app-root)
        ├── app.html      its template
        ├── app.css       its styles
        ├── app.spec.ts   its test
        ├── app.config.ts ApplicationConfig: application-level providers
        └── app.routes.ts the route table
```

The key difference from what you may have seen before: **no `app.module.ts`**. The application boots from a root component, not a module — `bootstrapApplication(App, appConfig)` — and providers are listed in `app.config.ts`. Modules (`NgModule`) only survive in older projects.

## React parallels

- **Importing a class ≠ making it available in the template.** In JSX, `import { TicketList }` is enough to write `<TicketList/>`, because that is an ordinary JS reference in scope. An Angular template is not JS: for `<app-ticket-list>` to be recognized, the component must appear in the `imports` array of the component whose template uses it. The TS import is necessary but not sufficient — this is the first wall everyone hits.
- **The application entry point.** `createRoot(el).render(<App/>)` mounts a tree and stops there. `bootstrapApplication(App, appConfig)` also creates the **root injector** with every application-level provider — meaning the Angular entry point configures the DI container that the whole app later pulls dependencies from (chapter 04).
- **Lifecycle.** `useEffect(() => {...}, [])` is code inside a function that re-runs on every render, with a dependency array as your manual brake. In Angular `ngOnInit`/`ngOnDestroy` are methods on an object, called by the framework once per instance lifetime. No "what if it runs twice" — but also no automatic re-run when data changes: that is what signals are for.
- **Style isolation.** In React, isolation depends on the tool you picked (CSS modules, styled-components, Tailwind). In Angular it is built in: component styles are scoped by default through emulated Shadow DOM (attributes like `_ngcontent-*`), and it is behaviour to know about in advance — a global selector written inside a component "not working" is exactly this (chapter 01).
- **Where the habit breaks:** in React you learned that "the subtree re-rendered, so the new data definitely arrived". In Angular updates are targeted: only the templates that were told about a change get re-evaluated. If nothing told the system (a mutation instead of `set`, a value that is not a signal), the DOM stays as it was — and the React reflex of hunting for a bug in the data instead of in the notification mechanism can burn hours.

## What you will see in legacy code

- **`app.module.ts` and `platformBrowserDynamic().bootstrapModule(AppModule)`** instead of `bootstrapApplication`. Providers live in the module's `providers`, components in `declarations`, dependencies in the module's `imports` rather than the component's.
- **An explicit `standalone: true` in the decorator.** Before v19 standalone was an opt-in flag; modern code has no such flag at all, and `standalone: false` means "this component still belongs to some NgModule".
- **Type suffixes in names:** `ticket-list.component.ts` with a `TicketListComponent` class, `ticket.service.ts` with `TicketService`. That is the 2016 style guide; it is not "wrong", just previous — and in an existing project you should keep it (after `ng update` the schematic defaults in `angular.json` are usually already configured for it).
- **`zone.js` in `polyfills`** in `angular.json` (or a separate `polyfills.ts` with `import 'zone.js'`), `karma.conf.js` and `test.ts` for Karma+Jasmine, and `@angular-devkit/build-angular:browser` as the builder in `angular.json` — three reliable markers of a project that has not seen recent migrations.
- **`environment.ts` / `environment.prod.ts`** with `fileReplacements` in `angular.json` — the old way to configure environments; today config usually arrives through a DI token (chapter 04) and `--configuration` (chapter 15).

## What we add to the project

We create the **Support Desk** workspace — the support ticket system we will keep extending for all 16 chapters — and introduce the first component of our own: the application shell with a heading, plus a placeholder ticket list to hang data, routing and forms off later.

## Exercise

**Input:** an empty folder and a Node LTS installation.
**Output:** a running Support Desk application with a component of your own inside the root component.

Requirements:

1. Create the `support-desk` workspace: CSS for styles, no SSR, the default test runner. Do not rely on a globally installed `ng` of unknown version — pin the CLI version explicitly when creating the project.
2. Before writing any code, explore the generated project and answer five questions for yourself: where is the entry point; what exactly does `bootstrapApplication` do; what lives in `app.config.ts` and why is it a separate file; why is there no `app.module.ts`; how does `tsconfig.app.json` differ from `tsconfig.spec.json`.
3. Generate the ticket list component inside a `tickets` folder. First inspect the generation plan without creating files, then create them. Note the resulting file, class and selector names — and note that there is no `changeDetection` field in the decorator: find out from the documentation which strategy applies in that case.
4. The component shows a "Tickets" heading and a ticket count taken from a class field (a constant for now) via interpolation.
5. Replace the root component's template with a shell: the application title `Support Desk` and the ticket list below it. Keep the application name in a field on the root component, not in the markup.
6. Start the dev server, confirm everything renders, then run a production build and look at the bundle sizes in the report.

Edge cases to think about:

- What happens (and at which stage — build or runtime) if you remove the component from the root component's `imports` but keep the TS import?
- Why does the template use `app-ticket-list` rather than the class name? Where does the `app-` prefix come from and where is it configured?
- If you rename the file to `ticket-list.component.ts`, what breaks and what does not?
- How does `ng build` differ from `ng serve` — not in what it does, but in the configuration the code is built with?
- Next to the component sits a `.spec.ts` you have not opened yet. Does it already pass? What does it assert?

## Solution walkthrough

Creating the workspace:

```bash
# pin the CLI version explicitly, no global install
npx @angular/cli@22 new support-desk --style=css --ssr=false
cd support-desk

# what is actually installed and on which major
npx ng version
```

The entry point is `src/main.ts`, generated by the CLI:

```ts
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';

// Builds the root injector from appConfig, instantiates App
// and mounts it into <app-root> from index.html.
bootstrapApplication(App, appConfig).catch((err) => console.error(err));
```

`src/app/app.config.ts` is the application-level configuration. Anything that must be a single instance per application is registered here:

```ts
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // provideHttpClient() with interceptors joins this list later — chapter 08
  ],
};
```

Note that `provideZonelessChangeDetection()` is absent: since v21 zoneless is the default mode and there is no `zone.js` in the project at all. Create the project with `--no-zoneless` and the schematic adds `provideZoneChangeDetection({ eventCoalescing: true })` here instead — which is exactly what you will find in an older project still running on zone.js.

Generating the component — plan first, then write:

```bash
npx ng generate component tickets/ticket-list --dry-run
# CREATE src/app/tickets/ticket-list.ts
# CREATE src/app/tickets/ticket-list.html
# CREATE src/app/tickets/ticket-list.css
# CREATE src/app/tickets/ticket-list.spec.ts
# NOTE: The "--dry-run" option means no changes were made.

npx ng generate component tickets/ticket-list
```

`src/app/tickets/ticket-list.ts` (the generated skeleton, filled in):

```ts
import { Component } from '@angular/core';

@Component({
  // the selector is how the component appears in a template; the app- prefix
  // comes from the project's prefix setting in angular.json
  selector: 'app-ticket-list',
  imports: [],
  templateUrl: './ticket-list.html',
  styleUrl: './ticket-list.css',
  // the changeDetection field is deliberately absent: since v22 its absence
  // means OnPush — the component is checked only when something told it
  // about a change. An explicit Eager would restore the old
  // "always check" behaviour (chapter 03)
})
export class TicketList {
  // An instance field *is* the component state. The instance lives as long as
  // the view is in the tree, so state needs no external container.
  // We move this onto signals in chapter 02, once the data starts changing.
  readonly totalCount = 3;
}
```

`src/app/tickets/ticket-list.html`:

```html
<section class="ticket-list">
  <h2>Tickets</h2>
  <!-- interpolation: the expression is evaluated whenever this template is checked -->
  <p>{{ totalCount }} open tickets</p>
</section>
```

`src/app/app.ts` — the root component, where we register `TicketList`:

```ts
import { Component } from '@angular/core';
import { TicketList } from './tickets/ticket-list';

@Component({
  selector: 'app-root',
  // imports is the template scope of THIS component. Without an entry here
  // the app-ticket-list tag is not recognized, even with the TS import above
  imports: [TicketList],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  // The CLI generated protected readonly title = signal('support-desk') here —
  // the root component ships signal-based out of the box. Nothing changes in
  // this chapter, so a plain field is enough; signals arrive in chapter 02
  readonly appName = 'Support Desk';
}
```

`src/app/app.html`:

```html
<header class="app-header">
  <h1>{{ appName }}</h1>
</header>

<main>
  <app-ticket-list />
</main>
```

Running and building:

```bash
npx ng serve            # http://localhost:4200, hot reload
npx ng build            # production build into dist/support-desk/browser + size report
```

Answers to the edge cases:

- Removing the component from `imports` is a **build error**, not a blank screen: `NG8001: 'app-ticket-list' is not a known element`. The template is compiled, and an unknown hyphenated tag is a legitimate error. That is the fundamental difference from React, where an "unregistered tag" is not even a concept.
- The template uses the selector because the template is not JS: the compiler matches markup elements against the selectors of components and directives in scope. The `app-` prefix comes from the project's `prefix` field in `angular.json` and exists so your selectors do not collide with future native elements or third-party libraries. (The experimental selectorless mode removes this layer, but it is not production material yet.)
- Renaming the file to `ticket-list.component.ts` breaks nothing but the convention: you fix the TS import path and `templateUrl` stays as it is. File names carry no meaning for Angular — decorators and imports do. Mixing both styles in one project is still a bad idea: `ng g` will keep generating according to the setting in `angular.json`.
- `ng serve` builds with the `development` configuration (sourcemaps, no optimization, watch mode), `ng build` with `production` (minification, tree-shaking, hashed filenames, bundle budgets). Hence the classic "it worked in dev": the difference is in the configuration, not in the commands.
- The generated `.spec.ts` passes: it sets the component up through `TestBed` and asserts that it is created. Almost no value on its own, but it shows what the entry point into tests looks like — details in chapter 13.

## Check yourself

1. Explain in your own words why Angular needs no rules of hooks and produces no stale closures — and which problem appears in their place.
2. A component is imported in the TS file but missing from the decorator's `imports`. Why is that a **build** error rather than a silently empty DOM? What does that tell you about how Angular templates work?
3. How does `bootstrapApplication(App, appConfig)` differ from `createRoot(el).render(<App/>)` in terms of work done — what exists in Angular that has no counterpart at all in the React version?
4. Why can't the fields of the `@Component` decorator be computed at runtime? What exactly does Angular do with them, and when?
5. Zoneless is the default since v21, `OnPush` is the default for components since v22. What do those two defaults tell you about where the framework now expects the "data changed" signal to come from?

<details>
<summary>Answers</summary>

1. Rules of hooks exist in React because state is matched to calls by their order inside a function that re-runs on every render; stale closures exist because a callback captures the values of one particular render. In Angular a component is a long-lived instance: state sits in object fields, `this.x` always reads the current value, and the class body runs exactly once. Neither call order nor value capture matters. A new problem appears instead: since nothing re-runs automatically, a separate notification mechanism is required — change detection and signals. A "not updating" bug in Angular is almost always about that mechanism, not about the data.
2. An Angular template is compiled, not executed as JS. Every component has its own **template scope** — the list of components, directives and pipes from `imports`; the compiler matches each markup element against the selectors in that list. An unknown hyphenated tag cannot be a valid HTML element, so this is a diagnosable compile error (`NG8001`) rather than "nothing on screen". The TS import only makes the class available as a value for the `imports` array — by itself it registers nothing.
3. `createRoot().render()` mounts a tree and that is all; there are no contexts, providers or services until you render them as components. `bootstrapApplication` additionally builds the **root injector** from `appConfig`: every `provide*` function (router, HTTP, configuration) runs and forms an application-level DI container from which dependencies are pulled via `inject()` anywhere, with no threading through the tree. In other words, the Angular entry point configures not just rendering but the entire dependency system.
4. A decorator is metadata for the Angular compiler (AOT), which reads it **at build time**: it compiles `template` into rendering instructions, derives the template scope from `imports` and generates the component factory. By the time the application runs in a browser the metadata is already baked into the code, so its values must be statically analyzable — a dynamically assembled object is invisible to the compiler.
5. Both defaults mean the framework no longer tries to guess that something changed by patching async APIs (`zone.js`) or by checking the whole tree on every tick. The change signal now arrives explicitly and precisely — from signals (`set`/`update`), plus template events and `markForCheck`. The practical consequence: state that affects the markup should live in signals, otherwise the system has no way to learn that a template needs rechecking.

</details>

## Common mistake

The first mistake nearly every React developer makes: generate a component, drop the tag into a template, get `NG8001: 'app-ticket-list' is not a known element` — and start looking for the problem in the import path or the file name, because "the class *is* imported". In React, importing into JS scope **is** the registration: `<TicketList/>` is just a function reference. In Angular the template is compiled separately and has its own scope, defined by the `imports` array of the component where the tag is used. The rule is simple: in every component where you write someone else's tag, directive or pipe, the corresponding class must be listed in that component's `imports` — locally, not "once somewhere in the application" (the latter was true for NgModules and lingers as a habit from legacy code).

The second mistake is subtler and surfaces later: constructor code gets treated as "the component function body", so logic that should react to changing data is put there — but the constructor runs once per instance lifetime and never again. The mirror image of the same confusion is computing things in a getter or in a method called from the template (`{{ getFilteredTickets() }}`): such a method runs on **every** check of that template, i.e. arbitrarily often, and while "it's just a call inside the render" sounds harmless in the React model, in Angular it becomes a performance sink. Initialization belongs in the constructor or `ngOnInit`; reacting to changing data belongs in `computed` (chapter 02).
