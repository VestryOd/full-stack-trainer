# Build, deploy and capstone

## Theory

### Builds and environment configurations

The `@angular/build:application` builder (esbuild/Vite) is the same one for the dev server and for production — the differences live in **configurations** in `angular.json`:

```json
"configurations": {
  "production": {
    "optimization": true,
    "outputHashing": "all",
    "sourceMap": false,
    "budgets": [{ "type": "initial", "maximumError": "500kB" }],
    "define": { "ngDevMode": "false" }
  },
  "staging": {
    "optimization": true,
    "sourceMap": true,
    "fileReplacements": [
      { "replace": "src/config/config.ts", "with": "src/config/config.staging.ts" }
    ]
  }
}
```

Run it with `ng build --configuration staging`. Useful options: `optimization`, `outputHashing` (`none`/`media`/`bundles`/`all` — hashes for caching), `sourceMap`, `define` (substituting constants into the code — a way to pass a build flag), `extractLicenses`, `subresourceIntegrity`, `budgets` (chapter 12).

On environment configuration there is a position worth taking: `fileReplacements` works, but it swaps a **file at build time**, so the values are baked into the bundle and never tested. The modern approach is to deliver config through a DI token (chapter 04) and fill it from `define`, from a server response, or from `index.html`. Then config is swappable in tests and needs no rebuild when the stand changes.

### SSR and hydration — an overview

```
                         Render modes: what to pick for a route
┌────────────┬────────────────────────────────────────┬───────────────────────────────┐
│ RenderMode │ when the HTML is produced              │ what it suits                 │
├────────────┼────────────────────────────────────────┼───────────────────────────────┤
│ Client     │ in the browser (the default behaviour) │ admin panels, private screens │
├────────────┼────────────────────────────────────────┼───────────────────────────────┤
│ Server     │ on the server, per request             │ personalized data, SEO        │
├────────────┼────────────────────────────────────────┼───────────────────────────────┤
│ Prerender  │ at build time, a static file           │ landing pages, docs, a blog   │
└────────────┴────────────────────────────────────────┴───────────────────────────────┘
                  outputMode: static — prerender only, no server file;
            outputMode: server — a runtime is required, so no static hosting
```

You add it with `ng new --ssr` or `ng add @angular/ssr`. The mode is set **per route**, not per application:

```ts
// app.routes.server.ts
export const serverRoutes: ServerRoute[] = [
  { path: '', renderMode: RenderMode.Prerender },
  { path: 'tickets', renderMode: RenderMode.Server },
  { path: 'admin/**', renderMode: RenderMode.Client },
  {
    path: 'tickets/:id',
    renderMode: RenderMode.Prerender,
    // which ids to prerender at build time
    async getPrerenderParams() {
      const api = inject(TicketApi);
      const ids = await api.listIds();
      return ids.map((id) => ({ id: String(id) }));
    },
    fallback: PrerenderFallback.Server,   // the rest are rendered on the server
  },
];

// app.config.server.ts
export const serverConfig: ApplicationConfig = {
  providers: [provideServerRendering(withRoutes(serverRoutes))],
};
```

**Hydration** is the process where the browser-side Angular brings server-rendered markup to life without recreating the DOM:

```ts
provideClientHydration(
  withEventReplay(),           // events that happened before hydration are replayed
  withIncrementalHydration(),  // @defer blocks with hydrate triggers (chapter 12)
)
```

What SSR buys you: faster first content, working SEO, better loading metrics. What it costs: a server runtime (or prerendering), code that can execute without a DOM (no direct `window`/`document` — use the `DOCUMENT`, `REQUEST`, `RESPONSE_INIT`, `REQUEST_CONTEXT` tokens instead), a new class of "different on the server than in the browser" bugs, and state that must travel between environments (for HTTP that is the transfer cache — `withHttpTransferCacheOptions`, chapter 08).

The practical rule: adopt SSR when there are public pages that must be indexed or open instantly. For an internal admin panel behind a login the benefit is close to zero while the complexity is very real.

### Deploying static output

If no server runtime is needed, use `outputMode: 'static'`: the build emits ready HTML files you drop onto any static host (S3+CDN, Netlify, GitHub Pages, nginx). Two mandatory details:

- **`--base-href`** when the app does not live at the domain root: `ng build --base-href /support-desk/`.
- **A fallback to `index.html`** for SPA routes: without it a direct visit to `/tickets/101` returns a server 404. On nginx that is `try_files $uri $uri/ /index.html;`, on S3 the error document, and on hosting platforms the equivalent setting.

On caching: with `outputHashing: "all"` filenames contain a hash, so static assets can be served with a long `max-age` while `index.html` gets `no-cache`. This standard scheme closes the "the user still sees the old version" question.

### Security

```
                               What Angular protects and what is on you
┌───────────────────────────┬────────────────────────────────┬───────────────────────────────────────┐
│ context                   │ what Angular does              │ what you do                           │
├───────────────────────────┼────────────────────────────────┼───────────────────────────────────────┤
│ interpolation {{ }}       │ escapes everything as text     │ nothing                               │
├───────────────────────────┼────────────────────────────────┼───────────────────────────────────────┤
│ [innerHTML]               │ sanitizes the HTML             │ never call bypassSecurityTrustHtml    │
├───────────────────────────┼────────────────────────────────┼───────────────────────────────────────┤
│ [href], [src]             │ sanitizes the URL              │ validate the scheme for foreign links │
├───────────────────────────┼────────────────────────────────┼───────────────────────────────────────┤
│ resource URL (script src) │ does NOT sanitize: it is code  │ never build it from user data         │
├───────────────────────────┼────────────────────────────────┼───────────────────────────────────────┤
│ nativeElement.innerHTML   │ not involved at all            │ do not use it (chapter 06)            │
├───────────────────────────┼────────────────────────────────┼───────────────────────────────────────┤
│ CSP                       │ nonce via ngCspNonce/CSP_NONCE │ a unique nonce per request            │
└───────────────────────────┴────────────────────────────────┴───────────────────────────────────────┘
                 security.autoCsp in angular.json generates a hash-based strict CSP;
                          off by default — it is still a preview capability
```

Angular defines four security contexts — HTML, style, URL and resource URL — and sanitizes HTML and URL values automatically. A resource URL (`<script src>`, for instance) is never sanitized: it points at arbitrary code, and code cannot be "cleaned". Hence the rule: the value for a script's or an iframe's `[src]` is never built from user data.

`DomSanitizer` with its `bypassSecurityTrust*` methods exists for "I know this is safe" cases. The documentation states the risk plainly: trusting a potentially malicious value introduces a vulnerability. In practice, a `bypassSecurityTrustHtml` in a code review needs an explanation of where the value came from.

CSP: three ways to supply a nonce — `security.autoCsp` in `angular.json` (generating a hash-based strict CSP; off by default while the feature is in preview), the `ngCspNonce` attribute on the root element, or the `CSP_NONCE` token. There is one hard requirement: the nonce must be unique per request and unpredictable. For SSR there are also `security.allowedHosts` and `trustProxyHeaders` — protection against SSRF via spoofed host headers.

## React parallels

- **Configurations versus `.env`.** In the React stack the environment usually arrives through `.env` and `process.env.NEXT_PUBLIC_*` substituted by the bundler. Angular's equivalent is `configurations` + `define` (or `fileReplacements` in the older style), but the idiomatic route is a DI token: it is the only variant that can be swapped in tests.
- **`RenderMode` per route ≈ Next.js per-route rendering.** The same idea as `dynamic`/`static` in Next.js: the decision belongs to a route rather than the application. The difference is that in Angular SSR is an option added to an SPA, while in Next.js server rendering is the model's foundation.
- **Hydration.** In React (and Next.js) hydration is a mandatory SSR step, and "hydration mismatch" is a familiar error. In Angular hydration is enabled by a provider and can do two things base React cannot: replay events that happened before the app was ready (`withEventReplay`) and hydrate `@defer` blocks in portions (`withIncrementalHydration`).
- **Sanitization out of the box.** JSX escapes text, but `dangerouslySetInnerHTML` is a direct path to XSS with no cleaning at all; you sanitize yourself (DOMPurify). Angular sanitizes `[innerHTML]` for you, and bypassing it requires an explicit `bypassSecurityTrust*` — so the unsafe action is visible in the code by the method's name.
- **Where the habit breaks:** touching `window`/`localStorage` in a constructor. In an SPA that always works; under SSR it crashes on the server. A React developer knows the symptom ("ReferenceError: window is not defined"), but Angular's answer is different: not `typeof window !== 'undefined'` but injecting the `DOCUMENT` token or moving the code into `afterNextRender` (chapter 03), which never runs on the server.

## What you will see in legacy code

- **`@angular-devkit/build-angular:browser`** with webpack configs (`custom-webpack`) and an `angular.json` full of `main`/`polyfills`/`scripts`. The webpack builders are deprecated as of v22 (chapter 00).
- **`environment.ts` + `environment.prod.ts` with `fileReplacements`** as the only configuration mechanism, plus `import { environment } from '../environments/environment'` all over the code — the very thing that prevents swapping the URL in tests.
- **`@nguniversal/express-engine`** and a `server.ts` with hand-written Express setup — the predecessor of `@angular/ssr`. The tells: `ngExpressEngine`, a manual `APP_BASE_HREF`, no `ServerRoute`.
- **`isPlatformBrowser(inject(PLATFORM_ID))`** in every service as a way to live with SSR: it works, but it is usually a consequence of touching `window` directly where `DOCUMENT` or `afterNextRender` would have been enough.
- **`DomSanitizer.bypassSecurityTrustHtml(userContent)`** with no comment about where the data came from — the most common vulnerability in Angular applications.
- **`ng build --prod`** in scripts (the flag was removed in Angular 12 in favour of `--configuration production`) and `ng build && cp -r dist ...` deploy scripts with no `--base-href`.

## What we add to the project

The final Support Desk build: `production`/`staging` configurations, config through a token instead of `environment.ts`, a static deployment with an `index.html` fallback, CSP enabled, and an audit of every place where the app trusts data. Prerendering the landing page is optional, as a `RenderMode` demonstration.

## Exercise

**Input:** the project from chapter 14 — reorganized and tested.
**Output:** an application that builds for two stands and deploys to static hosting.

Requirements:

1. Configurations: add `staging` next to `production` (differing in `sourceMap` and the API address). Verify `ng build --configuration staging`.
2. Remove `environment.ts` if any remains: the API address and flags arrive through `APP_CONFIG` (chapter 04). Pass build values via `define` rather than file replacement, and explain the difference in a comment.
3. Production build: enable `outputHashing: "all"`, the budgets from chapter 12, and confirm the build fails when they are exceeded. Build with `--base-href` for deployment into a subdirectory.
4. Static deployment: configure the `index.html` fallback (an nginx config, a `netlify.toml` or equivalent) and verify that a direct visit to `/tickets/101` works rather than 404s.
5. Caching: describe the headers for `index.html` and for hashed files. Explain why the scheme is safe.
6. Security: enable `security.autoCsp` in the build configuration, run the app and fix whatever breaks. Separately, find every place where data reaches `[innerHTML]` or `[src]` and confirm none of them is built from user input.
7. Optional SSR: add `@angular/ssr`, make the landing page `RenderMode.Prerender`, the list `RenderMode.Server` and the admin section `RenderMode.Client`. Find and fix the first thing that breaks on the server.
8. Capstone: walk through the senior-polish checklist below and write the project README — what it demonstrates and which decisions were deliberate.

Edge cases to think about:

- `outputMode: 'static'`, but one route is marked `RenderMode.Server`. What happens at build time?
- CSP is on and a third-party widget demands `unsafe-inline`. What options exist besides "disable CSP"?
- The app is deployed into a subdirectory with no `--base-href`. How does that show up?
- A service reads `localStorage` in a class field. What happens when SSR is enabled, and how do you fix it?
- Hashed files are cached for a year, yet the user still sees an old version. Where do you look?

## Solution walkthrough

Configurations and config through a token:

```json
"configurations": {
  "production": {
    "optimization": true,
    "outputHashing": "all",
    "sourceMap": false,
    "budgets": [
      { "type": "initial", "maximumWarning": "420kB", "maximumError": "500kB" },
      { "type": "anyComponentStyle", "maximumWarning": "4kB", "maximumError": "8kB" }
    ],
    "security": { "autoCsp": true },
    "define": { "API_URL": "'/api/v1'", "ENABLE_ANALYTICS": "true" }
  },
  "staging": {
    "optimization": true,
    "outputHashing": "all",
    "sourceMap": true,
    "define": { "API_URL": "'https://staging.example.com/api'", "ENABLE_ANALYTICS": "false" }
  }
}
```

```ts
// src/app/core/build-flags.d.ts — declare what define will substitute
declare const API_URL: string;
declare const ENABLE_ANALYTICS: boolean;

// app.config.ts
providers: [
  // Config reaches the app through a token rather than an import from
  // environment.ts: this way it can be swapped in tests (chapter 13) and per
  // stand, while define merely supplies the build's default values
  ...provideAppConfig({ apiUrl: API_URL, analyticsEnabled: ENABLE_ANALYTICS }),
]
```

The difference from `fileReplacements` is fundamental: replacing a file means a different module ships in the bundle and cannot be verified in a test; `define` is a constant, and the token is an extension point a test overrides with a provider.

Building and deploying:

```bash
# a production build into a subdirectory, with hashes and budgets
npx ng build --configuration production --base-href /support-desk/

# the result is static: dist/support-desk/browser
```

```nginx
# nginx: the key part is the index.html fallback, or a direct visit
# to /tickets/101 returns a 404
location /support-desk/ {
  alias /var/www/support-desk/browser/;
  try_files $uri $uri/ /support-desk/index.html;

  # hashed files: the name changes whenever the content does,
  # so they can be cached forever
  location ~* \.(js|css|woff2|png|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
  }
}

# index.html is NOT cached: it is what holds the links to the new hashes
location = /support-desk/index.html {
  add_header Cache-Control "no-cache";
}
```

Security in the project's code:

```ts
// The only place Support Desk renders HTML is the ticket description that
// came from the server. Angular sanitizes it automatically
@Component({
  template: `<div [innerHTML]="ticket().descriptionHtml"></div>`,
})
export class TicketDescription {
  readonly ticket = input.required<Ticket>();
  // bypassSecurityTrustHtml is NOT used here: the moment it appears,
  // responsibility for XSS moves from the framework to us
}
```

```ts
// A link to an external resource: Angular sanitizes the URL context, but the
// scheme is worth checking ourselves — it strips javascript:, yet a link to a
// phishing http address will pass, and that is not its job
protected readonly safeLink = computed(() => {
  const url = new URL(this.ticket().sourceUrl, location.origin);
  return url.protocol === 'https:' ? url.href : null;
});
```

SSR — the minimal configuration and the first thing you will have to fix:

```ts
// app.routes.server.ts
export const serverRoutes: ServerRoute[] = [
  { path: '', renderMode: RenderMode.Prerender },        // the landing page as static
  { path: 'tickets', renderMode: RenderMode.Server },    // the list on the server
  { path: 'admin/**', renderMode: RenderMode.Client },   // the admin section behind a login
];

// app.config.server.ts
export const serverConfig: ApplicationConfig = {
  providers: [provideServerRendering(withRoutes(serverRoutes))],
};

// app.config.ts — hydration on the client
providers: [
  provideClientHydration(
    withEventReplay(),          // a click made before hydration is not lost
    withIncrementalHydration(), // @defer blocks hydrate in portions (chapter 12)
  ),
]
```

```ts
// BEFORE: crashes on the server — window does not exist there
export class ThemeStore {
  private readonly theme = signal(localStorage.getItem('theme') ?? 'light');
}

// AFTER: browser APIs are touched only after rendering in the browser.
// afterNextRender never runs on the server at all (chapter 03)
export class ThemeStore {
  private readonly current = signal<'light' | 'dark'>('light');
  readonly theme = this.current.asReadonly();

  constructor() {
    afterNextRender(() => {
      const stored = localStorage.getItem('theme');
      if (stored === 'dark' || stored === 'light') this.current.set(stored);
    });
  }
}
```

### Capstone: what we built

Over fifteen chapters Support Desk accumulated the full set of Angular mechanisms:

- **Components and templates** (chapters 00–01): standalone, the new control flow, host bindings, style isolation.
- **Reactivity** (02–03): signals as the single source of state, `computed` instead of recomputation, zoneless and `OnPush` as defaults, diagnostics through `provideCheckNoChangesConfig` and the Profiler.
- **DI and state** (04–05): `@Service()`, config through an `InjectionToken`, a multi token of rules, the domain in an app-level store and screen state in a route-level one.
- **UI mechanics** (06, 11): a highlight directive, a pure SLA pipe, `hostDirectives`, a generic table on `ng-template`, a modal with dynamic components.
- **Data and navigation** (07–09): routes with `canMatch`, inputs from parameters, `httpResource`, three interceptors, live search and polling on RxJS.
- **Forms** (10): a typed form, cross-field validation, an async validator, `ControlValueAccessor`, a look at Signal Forms.
- **Quality** (12–14): profiling, `@defer`, budgets, tests without `fakeAsync` and with harnesses, a feature-based structure with checkable boundaries.
- **Production** (15): configurations, static deployment, CSP, an SSR overview.

```
                 The senior-polish checklist: what people look at
┌──────────────────────────┬─────────────────────────────────────────────────────┐
│ what is checked          │ the "done" signal                                   │
├──────────────────────────┼─────────────────────────────────────────────────────┤
│ the modern model         │ signals, standalone, inject, control flow           │
├──────────────────────────┼─────────────────────────────────────────────────────┤
│ no mechanism leaks       │ not a single effect for derived values              │
├──────────────────────────┼─────────────────────────────────────────────────────┤
│ state split honestly     │ domain in a service, screen state in a screen store │
├──────────────────────────┼─────────────────────────────────────────────────────┤
│ errors handled per level │ 401/5xx in an interceptor, 404/422 on the screen    │
├──────────────────────────┼─────────────────────────────────────────────────────┤
│ code split               │ lazy routes + @defer, budgets in CI                 │
├──────────────────────────┼─────────────────────────────────────────────────────┤
│ tests that catch bugs    │ whenStable, harnesses, no fakeAsync                 │
├──────────────────────────┼─────────────────────────────────────────────────────┤
│ accessibility            │ roles, focus, keyboard, aria on controls            │
├──────────────────────────┼─────────────────────────────────────────────────────┤
│ README and ARCHITECTURE  │ what the project demonstrates and how it is built   │
└──────────────────────────┴─────────────────────────────────────────────────────┘
     interviews value not the size of the project but your ability to explain
               every decision and name the alternative you rejected
```

### Where to grow next

Directions, each a topic of its own, and none mandatory for confident work:

- **NgRx (Store or SignalStore)** — when the reasons from chapter 05 appear: a large team, a traceability requirement, complex async orchestration. Start with SignalStore: moving from a signal service is mechanical.
- **Signal Forms** — the API has been stable since v22, and in new projects it is worth trying on one form so you have an opinion by the time it becomes mainstream (chapter 10).
- **Angular in a monorepo** — Nx, library boundaries, caching and affected: fully covered by the Nx course, with the architectural link described in chapter 14.
- **Micro frontends on Angular** — Module Federation, dependency versions, style isolation; a topic where mistakes are expensive, so take it on for a concrete organizational reason rather than "to try it".
- **Advanced accessibility** — `@angular/aria` and CDK a11y (chapters 06, 11), keyboard patterns, testing with a screen reader; an underrated skill that visibly separates senior code.
- **SSR in earnest** — the transfer cache, server-side caching strategies, incremental hydration in a real application (this chapter is only an overview).
- **The framework's internals** — how templates compile, how the reactive graph works, reading `@angular/core` sources. That is most often what separates "I know the API" from "I understand the mechanism" in an interview — and the whole course was built so that you can explain the mechanism.

## Check yourself

1. Why is config through an `InjectionToken` preferable to `environment.ts` with `fileReplacements`? Name two practical consequences.
2. What happens on a direct visit to `/tickets/101` in a static deployment with no `index.html` fallback, and why?
3. How does `RenderMode.Prerender` differ from `RenderMode.Server` in terms of infrastructure and data?
4. What does Angular sanitize automatically and what does it not, and why can a resource URL not be cleaned?
5. The caching scheme "hashed files forever, `index.html` uncached" — why is it safe, and what breaks it?

<details>
<summary>Answers</summary>

1. `fileReplacements` swaps a **file at build time**: a different module ends up in the bundle, the value is baked into the code, and it cannot be replaced in a test — the test either uses the same file or mocks the import through the bundler. A token is an extension point: (a) in tests the config is supplied by a provider (`provideAppConfig({ apiUrl: '/api' })`), so tests do not depend on which stand the code was built for (chapter 13); (b) the value can be obtained at runtime — from `index.html`, from a server response, from an environment variable through `define` — so one artifact can be deployed to several stands with no rebuild. A token is also visible in the dependency graph: it is clear who reads the config, whereas `import { environment }` spreads through files invisibly.
2. The server returns a 404: there is no physical `/tickets/101` file in the static output, and the route exists only inside the application, which boots from `index.html`. While the user follows links inside the SPA, the router changes the URL through the History API and makes no server requests — so the problem only shows up on a direct visit, a page reload, or an inbound external link. The fix is serving `index.html` for any unknown path (`try_files` in nginx, an error document on S3, a rewrite rule on a hosting platform), after which Angular takes over routing.
3. `Prerender` (SSG) runs **at build time**: the output is static HTML files, no server runtime is needed, it deploys to any static host, and the data inside is whatever existed when the build ran (for parameterized routes the list of values comes from `getPrerenderParams`). `Server` (SSR) runs **per request**: a live Node runtime is required, personalized data, headers and status codes are possible, but every request costs server time and needs scaling. The practical choice: content that is identical for everyone and changes rarely — `Prerender`; personalized or frequently changing — `Server`; behind a login where SEO is irrelevant — `Client`.
4. Automatically sanitized are the HTML context (`[innerHTML]`) and the URL context (`[href]`, `[src]` on images and links): dangerous markup and schemes such as `javascript:` are stripped. Not sanitized is the **resource URL** — anything that specifies the source of executable code (`<script src>`, `<iframe src>`) — because the content at such an address is arbitrary code: it cannot be cleaned, and any "safe-looking" URL may return anything. That is why Angular demands an explicit `bypassSecurityTrustResourceUrl` for such values — it forces the author to take responsibility. Separately: bypassing sanitization through `nativeElement.innerHTML` skips the mechanism entirely, with no checks at all.
5. It is safe because a hashed file's name is a function of its content: content changes, name changes, so an old file is never served in place of a new one and can be cached indefinitely (`immutable`). The only entry point referring to the current names is `index.html`, and that is precisely what is not cached, so the browser always receives a fresh list of links. Three things break the scheme: `outputHashing` disabled or limited (names stay stable and the old file keeps being served); `index.html` caught by a CDN cache or a service worker; or an intermediate proxy caching it by its own rules and ignoring the headers. Hence the practice of checking response headers on the real stand rather than only the config.

</details>

## Common mistake

The first is enabling SSR "because it is better". The decision looks technical but is a product decision: SSR is justified where public pages need indexing and an instant first screen. For an internal tool behind a login the benefit is near zero while the cost is real: a server runtime in your infrastructure, no static deployment, a class of "works in the browser, crashes on the server" bugs, and the need to think about transferring state and about code executing twice. The symptom of a wrong decision is recognizable: `isPlatformBrowser()` and `typeof window !== 'undefined'` appear in ten places — that is the price of rendering nobody needed. The right order is to first answer which pages must be in search results, then enable SSR for those pages only, through `RenderMode`.

The second is `bypassSecurityTrustHtml` as a way to "fix" sanitization. It looks like this: a ticket description arrives from the backend with markup, Angular strips some tags, the developer searches and finds the method that "solves the problem", and pastes it in. From that moment the framework stops protecting the application, and any user who can influence that field gains the ability to run their script for everyone else. The documentation states it plainly: trusting a value that might be malicious introduces a vulnerability. The correct options: sanitize the HTML on the server against an allow-list of tags, deliver structured data instead of markup, or sanitize explicitly and deliberately — but never "just bypass it" because a stripped tag was breaking the layout.
