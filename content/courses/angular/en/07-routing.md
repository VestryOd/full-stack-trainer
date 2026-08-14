# Routing

## Theory

### Route configuration

Routes are a plain array of objects handed to `provideRouter(routes)`:

```ts
export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'tickets' },
  {
    path: 'tickets',
    title: 'Tickets',                    // the tab title, set by the router
    loadComponent: () => import('./tickets/ticket-list').then((m) => m.TicketList),
    children: [
      { path: 'new', loadComponent: () => import('./tickets/ticket-form').then((m) => m.TicketForm) },
      { path: ':id', loadComponent: () => import('./tickets/ticket-detail').then((m) => m.TicketDetail) },
    ],
  },
  {
    path: 'admin',
    canMatch: [adminGuard],              // rejects the route BEFORE the chunk loads
    providers: [provideAdminTools()],    // its own EnvironmentInjector (chapter 04)
    loadChildren: () => import('./admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  { path: '**', loadComponent: () => import('./core/not-found').then((m) => m.NotFound) },
];
```

Worth noting up front: order matters (routes are matched top-down, `'**'` always last); `path: ':id'` comes **after** `path: 'new'`, otherwise `/tickets/new` matches the parameter; `providers` on a route creates its own injector that lives as long as the route does.

### What happens during navigation

```
      What happens between the click and the screen
┌───────────────────────────────────────────────────────┐
│ URL: /admin/reports?range=7d                          │
└───────────────────────────────────────────────────────┘
                            │  matching
                            ▼
┌───────────────────────────────────────────────────────┐
│ routes are matched top-down + canMatch                │
│ false → this route is skipped, try the next one       │
└───────────────────────────────────────────────────────┘
                            │  route found
                            ▼
┌───────────────────────────────────────────────────────┐
│ the lazy chunk is loaded                              │
│ loadComponent / loadChildren + route providers        │
└───────────────────────────────────────────────────────┘
                            │  code loaded
                            ▼
┌───────────────────────────────────────────────────────┐
│ canDeactivate of the current → canActivate of the new │
│ false → navigation is cancelled, the URL stays        │
└───────────────────────────────────────────────────────┘
                            │  access granted
                            ▼
┌───────────────────────────────────────────────────────┐
│ resolve: navigation WAITS for data                    │
│ an error fails the navigation                         │
└───────────────────────────────────────────────────────┘
                            │  data ready
                            ▼
┌───────────────────────────────────────────────────────┐
│ components are created in the router-outlet           │
│ inputs are filled by withComponentInputBinding        │
└───────────────────────────────────────────────────────┘
canMatch rejects a route BEFORE the chunk loads, canActivate after:
for role-gated lazy sections that difference is measured in megabytes
```

Navigation is not "show a component" but a pipeline with several failure points. Knowing the order gives you two things: you know where to insert a check, and you understand why "the page flashed and came back" (a guard fired after navigation had started).

### Guards

```
┌──────────────────┬────────────────────────────────────┬─────────────────────────┬────────────────────┐
│ guard            │ when it runs                       │ what false means        │ typical use        │
├──────────────────┼────────────────────────────────────┼─────────────────────────┼────────────────────┤
│ canMatch         │ while matching routes              │ try the next route      │ feature flag, role │
├──────────────────┼────────────────────────────────────┼─────────────────────────┼────────────────────┤
│ canActivate      │ after matching, before resolve     │ navigation is cancelled │ login required     │
├──────────────────┼────────────────────────────────────┼─────────────────────────┼────────────────────┤
│ canActivateChild │ for every child route              │ navigation is cancelled │ guarding a section │
├──────────────────┼────────────────────────────────────┼─────────────────────────┼────────────────────┤
│ canDeactivate    │ when leaving a route               │ you stay where you are  │ unsaved form       │
├──────────────────┼────────────────────────────────────┼─────────────────────────┼────────────────────┤
│ resolve          │ after guards, before the component │ navigation error        │ data before render │
└──────────────────┴────────────────────────────────────┴─────────────────────────┴────────────────────┘
```

A guard is a plain function executed in an injection context, so `inject()` is available inside:

```ts
export const authGuard: CanActivateFn = (route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isLoggedIn()) return true;

  // you may return a boolean, a UrlTree or a RedirectCommand — the last one
  // also lets you specify navigation options
  return new RedirectCommand(router.parseUrl('/login'), {
    state: { returnTo: state.url },
  });
};
```

The key distinction, and a common interview question: **`canMatch` runs while matching, `canActivate` runs after**. Two practical consequences. First, `canMatch: false` does not cancel navigation — it makes the router keep looking, so one path can render different components for different roles. Second, `canMatch` rejects a route **before** the lazy chunk loads while `canActivate` runs after it; for an admin section that is the difference between "the user never downloaded the admin code" and "downloaded it but did not see it".

The older `canLoad` is deprecated in favour of `canMatch`; so are class-based guards (`implements CanActivate`).

### Reading route state

```
                                         How to read route state
┌─────────────────────────────────────┬───────────────────────────────────┬──────────────────────────────┐
│ approach                            │ what you get                      │ when to use it               │
├─────────────────────────────────────┼───────────────────────────────────┼──────────────────────────────┤
│ input() + withComponentInputBinding │ a signal the router keeps updated │ in a component — the default │
├─────────────────────────────────────┼───────────────────────────────────┼──────────────────────────────┤
│ toSignal(route.params)              │ a signal from an Observable       │ in a service or a guard      │
├─────────────────────────────────────┼───────────────────────────────────┼──────────────────────────────┤
│ route.snapshot.paramMap             │ the value at creation time        │ a one-off read               │
├─────────────────────────────────────┼───────────────────────────────────┼──────────────────────────────┤
│ route.params.subscribe              │ a stream of changes               │ older code, chapter 09       │
└─────────────────────────────────────┴───────────────────────────────────┴──────────────────────────────┘
                a snapshot does not update when :id changes and the component is reused —
                         the source of the "opened another ticket, same data" bug
```

The modern approach is `withComponentInputBinding()`: the router itself feeds route params, query params and `data` into the component's **inputs**, matching them by name.

```ts
provideRouter(routes, withComponentInputBinding());

// a component on the route /tickets/:id?tab=history
export class TicketDetail {
  readonly id = input.required<string>();       // from the route parameter
  readonly tab = input('details');              // from the query parameter
}
```

No `ActivatedRoute`, no subscriptions, and the inputs update when the parameter changes — even if the component is reused. `ActivatedRoute` has no signal API of its own: outside components (in a service or a guard) params become signals via `toSignal(route.params, { requireSync: true })`.

A word on `snapshot`: it is valid as of the moment the component was created. If navigating from `/tickets/1` to `/tickets/2` makes the router reuse the same instance — and it does, when only the parameter changes — the `snapshot` stays as it was and `ngOnInit` never runs again. This is the single most common trap in Angular routing.

### Lazy loading

`loadComponent` loads one component, `loadChildren` a set of routes (usually a `feature.routes.ts` file exporting `Routes`). Both take a function with a dynamic `import()`, so the bundler splits a chunk automatically.

Preloading is configured as a feature: `withPreloading(PreloadAllModules)` pulls every lazy chunk after startup, and custom strategies can load, say, only routes marked `data: { preload: true }`.

Useful `provideRouter` features: `withComponentInputBinding()`, `withViewTransitions()` (animation through the View Transitions API), `withInMemoryScrolling({ scrollPositionRestoration: 'enabled', anchorScrolling: 'enabled' })`, `withRouterConfig({ onSameUrlNavigation: 'reload' })`, `withHashLocation()`, `withNavigationErrorHandler(fn)`, `withDebugTracing()`. v22 adds the experimental `withExperimentalPlatformNavigation()` (integration with the browser Navigation API) and `withExperimentalAutoCleanupInjectors` (automatic destruction of unused route injectors).

### Are resolvers worth it

`ResolveFn` delays navigation until the data is ready. The upside: the component opens with data and never flashes empty. The downsides: the user stares at the old page with no idea what is happening; an error in the resolver breaks navigation entirely; and the data arrives in `data` rather than in signals, so there is nothing to refresh it with later.

The practical position: a resolver fits things that genuinely must exist before rendering — checking that an entity exists and redirecting to 404, supplying a `title`, loading a section's configuration. The screen's own data is better fetched in the component with `httpResource` (chapter 08), where loading and error states become part of the UI rather than of navigation.

## React parallels

- **The router is part of the framework.** In React you pick a library and a version, and the API shifts noticeably between majors. Angular has one router, upgraded with the framework and migrated by schematics during `ng update`. Less freedom, but fewer decisions: route configuration looks the same in every project.
- **Guards versus wrapper components.** The typical React approach is `<RequireAuth><Dashboard/></RequireAuth>`: the check happens **during rendering**, meaning the component is already mounted and the chunk already downloaded. An Angular guard runs before the component is created, and `canMatch` before the code is even fetched. The practical difference: in React, protecting against "accidentally downloaded the admin bundle" takes extra work; in Angular it is one line of configuration.
- **A resolver versus a `loader` in React Router's data API.** Same idea — data before render. But in React Router a `loader` is the primary way to fetch data, whereas in Angular a resolver competes with `httpResource`, which exposes `loading`/`error` as signals. So resolvers deserve to be used more sparingly in Angular than loaders are in React.
- **Route parameters.** `useParams()` returns values on every render, and a React component usually remounts when its key changes. In Angular the component is reused and the inputs update — so no `key` equivalent is needed, but you must write code that reacts to an input change (a `computed`, not a one-off read in `ngOnInit`).
- **Where the habit breaks:** expecting `/tickets/1` → `/tickets/2` to "recreate" the screen. It does not: same instance, same `snapshot`, no `ngOnInit`. Code written the React way — "read the parameter on mount" — silently keeps showing stale data.

## What you will see in legacy code

- **`RouterModule.forRoot(routes)` / `forChild(routes)`** inside NgModules and `loadChildren: './admin/admin.module#AdminModule'` as a string (before Angular 8). Today it is `provideRouter` and a dynamic `import()`.
- **Class-based guards and resolvers:** `@Injectable({providedIn:'root'}) export class AuthGuard implements CanActivate` and `class TicketResolver implements Resolve<Ticket>`, referenced from the route as classes. The functional equivalents are shorter and need no registration.
- **`canLoad: [AuthGuard]`** — the predecessor of `canMatch`, now deprecated. The difference: `canLoad` only prevented the chunk from loading, `canMatch` also lets the router continue matching other routes.
- **`route.params.subscribe(...)` in `ngOnInit`** with manual unsubscription, and `route.snapshot.paramMap.get('id')` with no reaction to changes — two generations of solving one problem that `withComponentInputBinding` now covers.
- **`data: { roles: ['admin'] }` plus one generic guard** reading `route.data` — a workable technique, though with functional guards people more often write a factory: `canActivate: [hasRole('admin')]`.
- **A custom `RouteReuseStrategy`** with `shouldDetach`/`shouldAttach` for "tabs that keep their state". v22 added an official `destroyDetachedRouteHandle()` for this — detached views used to leak surprisingly often.

## What we add to the project

Support Desk gets real navigation: the ticket list, a detail page by `:id`, a creation form and a lazy admin section gated by role through `canMatch`. Parameters arrive as component inputs, and leaving a half-filled form is intercepted by `canDeactivate`.

## Exercise

**Input:** the project from chapter 06 (stores, a directive, a pipe).
**Output:** four routes, a lazy admin section and two working protections.

Requirements:

1. Configure `provideRouter` with `withComponentInputBinding()` and scroll position restoration. Routes: `/tickets` (list), `/tickets/new` (a stub form), `/tickets/:id` (detail), `/admin` (lazy), `**` (404). Verify that the order of `new` and `:id` matters.
2. `TicketDetail` receives `id` as an **input**, not through `ActivatedRoute`. The ticket comes from `TicketStore` by `id` via a `computed`. Confirm that navigating from `/tickets/101` to `/tickets/102` changes the content, and explain why `ngOnInit` does not run in the process.
3. The admin section: a separate `admin.routes.ts` with two child routes, wired through `loadChildren`, plus a `canMatch` guard by role. Check in DevTools (Network tab) that the admin chunk is not downloaded by a user without the role.
4. `canDeactivate` for the form: leaving with unsaved changes asks for confirmation. The guard must work with a typed component, not with `any`.
5. A resolver: for `/tickets/:id`, verify the ticket exists and redirect to 404 when it does not (`RedirectCommand` or `UrlTree`). Explain in a comment why you do **not** pass the ticket data itself through the resolver.
6. Links: use `routerLink` with an array of segments plus `routerLinkActive`; keep programmatic navigation only where it is genuinely needed (after saving the form).

Edge cases to think about:

- What happens to `/tickets/new` if you declare it after `/tickets/:id`?
- The detail component is reused when `:id` changes. What happens to state you keep in its fields, and what happens to `input()`?
- `canMatch` returned `false` and no other route matches. What does the user see?
- The query parameter `?tab=history` is bound to the `tab` input. What ends up in the input for `?tab=history&tab=notes`?
- Why is `providers` on the admin route not the same as `providers` in the root config, and when are those services destroyed?

## Solution walkthrough

`src/app/app.routes.ts`:

```ts
import { Routes } from '@angular/router';
import { adminMatchGuard } from './admin/admin-guard';
import { ticketExistsGuard } from './tickets/ticket-exists-guard';
import { unsavedChangesGuard } from './core/unsaved-changes-guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'tickets' },
  {
    path: 'tickets',
    title: 'Tickets',
    loadComponent: () => import('./tickets/ticket-list').then((m) => m.TicketList),
  },
  {
    // IMPORTANT: the static segment is declared before the parameter, or
    // /tickets/new matches :id and the id becomes the string "new"
    path: 'tickets/new',
    title: 'New ticket',
    loadComponent: () => import('./tickets/ticket-form').then((m) => m.TicketForm),
    canDeactivate: [unsavedChangesGuard],
  },
  {
    path: 'tickets/:id',
    loadComponent: () => import('./tickets/ticket-detail').then((m) => m.TicketDetail),
    // the resolver only checks existence and redirects to 404; the data
    // itself is read from the store (and from httpResource in chapter 08)
    resolve: { exists: ticketExistsGuard },
  },
  {
    path: 'admin',
    // canMatch rather than canActivate: without the role the route does not
    // match at all, and the admin chunk is never loaded
    canMatch: [adminMatchGuard],
    loadChildren: () => import('./admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  { path: '**', loadComponent: () => import('./core/not-found').then((m) => m.NotFound) },
];
```

`src/app/app.config.ts`:

```ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      // the router fills component inputs with route params, query params
      // and data, matching them by name
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'enabled', anchorScrolling: 'enabled' }),
    ),
    ...provideAppConfig(),
    ...provideTicketRules(),
  ],
};
```

`src/app/tickets/ticket-detail.ts`:

```ts
import { Component, computed, inject, input, numberAttribute } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TicketStore } from './ticket-store';

@Component({
  selector: 'app-ticket-detail',
  imports: [RouterLink],
  templateUrl: './ticket-detail.html',
})
export class TicketDetail {
  private readonly store = inject(TicketStore);

  // The router fills this input. transform: numberAttribute because URLs
  // deliver strings while the store works with numeric ids
  readonly id = input.required({ transform: numberAttribute });
  // the ?tab=… query parameter lands in the input of the same name
  readonly tab = input<'details' | 'history'>('details');

  // Reacting to an :id change is a dependency, not a hook: the computed
  // recomputes itself when the router updates the input, even though the
  // component instance was reused
  protected readonly ticket = computed(() =>
    this.store.tickets().find((t) => t.id === this.id()) ?? null,
  );
}
```

`src/app/tickets/ticket-exists-guard.ts` — a resolver with a redirect:

```ts
import { ResolveFn, RedirectCommand, Router } from '@angular/router';
import { inject } from '@angular/core';
import { TicketStore } from './ticket-store';

export const ticketExistsGuard: ResolveFn<boolean> = (route) => {
  const store = inject(TicketStore);
  const router = inject(Router);
  const id = Number(route.paramMap.get('id'));

  if (store.tickets().some((t) => t.id === id)) return true;

  // RedirectCommand instead of a bare UrlTree: it also carries navigation
  // options (state, replaceUrl, skipLocationChange)
  return new RedirectCommand(router.parseUrl('/not-found'), {
    state: { reason: `Ticket ${id} not found` },
  });
};
```

`src/app/admin/admin-guard.ts` and `admin.routes.ts`:

```ts
export const adminMatchGuard: CanMatchFn = () => {
  const user = inject(CurrentUser);
  // false here means "this route does not apply" — the router keeps looking
  // and eventually lands on '**'. The admin chunk is never fetched
  return user.roles().includes('admin');
};

// admin.routes.ts — the separate file that becomes the lazy chunk
export const ADMIN_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () => import('./admin-shell').then((m) => m.AdminShell),
    // route-level providers: these services live while the section is active
    // and are destroyed when the user leaves it (chapter 04)
    providers: [AdminMetrics],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'reports' },
      { path: 'reports', loadComponent: () => import('./admin-reports').then((m) => m.AdminReports) },
      { path: 'users', loadComponent: () => import('./admin-users').then((m) => m.AdminUsers) },
    ],
  },
];
```

`src/app/core/unsaved-changes-guard.ts` — a typed `canDeactivate`:

```ts
// A contract instead of any: the guard works with any component that can
// answer the question "is it safe to leave"
export interface HasUnsavedChanges {
  readonly hasUnsavedChanges: Signal<boolean>;
}

export const unsavedChangesGuard: CanDeactivateFn<HasUnsavedChanges> = (component) => {
  if (!component.hasUnsavedChanges()) return true;
  return confirm('You have unsaved changes. Leave this page?');
};
```

The list template with links:

```html
<a
  [routerLink]="['/tickets', ticket.id]"
  [queryParams]="{ tab: 'details' }"
  routerLinkActive="is-active"
>
  {{ ticket.title }}
</a>

<!-- router-outlet — where the router inserts the routed component -->
<router-outlet />
```

Answers to the edge cases:

- `/tickets/new` would match `/tickets/:id`, and `id` would receive the string `"new"`. With `transform: numberAttribute` you get `NaN`, no ticket is found, and the screen shows "not found" — the bug surfaces as "the create form does not open". The rule: static segments are declared before parameterized ones.
- The component's fields survive: the instance is the same, and neither the constructor nor `ngOnInit` runs again. `input()` updates, and everything derived from it through `computed` recomputes. Hence the rule: screen state that depends on a parameter must be derived from the input rather than written into a field at initialization.
- The router keeps matching and reaches `'**'` — the user sees a 404 page rather than "access denied". If an explicit refusal is required, use `canActivate` with a redirect to `/forbidden` instead: exactly the case where "cancel the navigation" beats "skip the route".
- With a repeated key you get a single value — the last one in the query string (`'notes'`), not an array: `withComponentInputBinding` reads from a paramMap-like structure. If you need the array, read `queryParamMap.getAll('tab')` through `ActivatedRoute`.
- Route `providers` create a **separate environment injector** for that route: the services are created when the section is entered and destroyed when it is left, rather than living for the whole application. That is precisely the case where state must outlive a component but not the application.

## Check yourself

1. Explain in your own words the difference between `canMatch` and `canActivate`, and give a case where the wrong choice hurts not security but the amount of code downloaded.
2. Why does `ngOnInit` not run when navigating `/tickets/1` → `/tickets/2`, and what is the correct way to react to a parameter change?
3. What does `withComponentInputBinding()` do, and why does it make `ActivatedRoute` nearly unnecessary in components?
4. When is a resolver justified, and when is it better to fetch data in the component itself? Name two downsides of resolvers.
5. What happens on `canMatch: false` when no other route matches, and how does that differ from `canActivate: false`?

<details>
<summary>Answers</summary>

1. `canMatch` runs while the URL is being matched against routes: returning `false` marks the route as not applicable and the router keeps looking — one path can render different components for different roles. `canActivate` runs after the route has been chosen: `false` cancels navigation entirely. The code-size case: guarding a lazy admin section with `canActivate` means the router picks the route and **downloads the chunk** first, then checks access — an ordinary user fetches code they will never see. With `canMatch` the route is rejected before loading, so the chunk is never requested.
2. The router reuses the component instance when the route is the same and only the parameter changed: the component is neither destroyed nor recreated, so the constructor and `ngOnInit` do not run. The reaction must be a dependency rather than a hook: take the parameter as an `input()` (with `withComponentInputBinding`) and derive everything else from it with `computed`. Then a change of `:id` updates the input and dependent computations refresh automatically, whereas the snapshot approach — "read it in `ngOnInit` and store it in a field" — keeps showing stale data.
3. It enables automatic binding of route params, query params and `data` to component **inputs** by matching names. The component no longer needs to inject `ActivatedRoute`, subscribe to `params` and unsubscribe: an input is a signal the router keeps updated, and it works even when the instance is reused. `ActivatedRoute` remains necessary for the unusual cases: reading `queryParamMap.getAll()`, reaching parent routes, or working outside a component (where params become signals through `toSignal`).
4. A resolver is justified when something genuinely must be ready **before** rendering and affects navigation itself: verifying an entity exists and redirecting to 404, supplying a title, loading a section's configuration. The downsides: first, navigation "hangs" — the user stays on the old page with no indication until the resolver finishes, and the slower the network the more it feels frozen; second, an error in the resolver breaks navigation completely, and loading/error state cannot be shown inside the screen's UI because it lives outside the component. The screen's own data is better fetched in the component (`httpResource`, chapter 08), where `loading` and `error` are part of the UI.
5. The router continues matching and, finding nothing, reaches `'**'` — the user sees a "not found" page while the URL stays as requested. With `canActivate: false` navigation is cancelled: the URL does not change at all and the user remains on the current screen (unless the guard returned an explicit redirect). Hence the practical choice: "this section does not exist for you" — `canMatch`; "the section exists but you must log in" — `canActivate` with a redirect to the login page.

</details>

## Common mistake

The first one is reading the parameter from `snapshot` inside `ngOnInit`. The code looks impeccable and works on first open: `const id = this.route.snapshot.paramMap.get('id')`, then fetch. The problem appears when the user moves from one ticket to another from inside the app — through a "next" link, say. The router reuses the component, `ngOnInit` never runs, the `snapshot` stays as it was, and the screen keeps showing the previous ticket while the address bar shows the new URL. The bug feels mysterious because a page reload "fixes" it. The right approach is not a one-off read but a dependency: `input()` with `withComponentInputBinding` plus a `computed` derived from it, so the update arrives on its own.

The second is using `canActivate` where `canMatch` belongs, for lazy sections. Access-wise both work: a user without the role never sees the admin screen. But with `canActivate` the router picks the route, **downloads the admin chunk** and only then asks the guard — code the user is not allowed to run still ends up in their browser. Besides the wasted traffic this sends the wrong signal: the contents of the admin section are visible to anyone who opens the Network tab. Changing one line (`canActivate` → `canMatch`) removes both the download and the leak of the section's structure. The flip side: `canMatch: false` leads to a 404 rather than "access denied", so when the user deserves an explanation, guards are combined: `canMatch` for feature flags, `canActivate` with a redirect for authentication.
