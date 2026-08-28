# Microfrontends: why, and how they work

## Theory

A conceptual chapter: the mini-shop code doesn't change. Before pressing generator buttons in chapter 10, you need to understand what exactly they'll generate and why — otherwise Module Federation stays "config magic".

### Why microfrontends: the one honest reason

Microfrontends have one real reason to exist: **independent deployment by independent teams**. Everything else from the marketing lists — "reuse", "isolation", "different technologies" — falls into two buckets. Either a monorepo already solves it (code sharing, boundaries — chapters 02 and 06), or it is an anti-pattern: a zoo of frameworks on one page.

Signs that Module Federation (MF) is genuinely needed:

- Several teams with their own release cadence keep hitting a shared "release train".
- You need to canary a part of the interface without touching the rest.
- The product is assembled from parts with different owners and different rates of change.

If none of that describes you, build-time composition from a regular monorepo is simpler, faster and more reliable. That is what we already have: shell imports catalog-feature.

The price of MF that conference talks stay quiet about:

- **Integration errors move to runtime.** With build-time composition, incompatibility is caught by the compiler; with runtime — by a user in production. Contracts between host and remote need their own protection: types (chapter 11), end-to-end (e2e) tests, canaries.
- **Shared dependency versions** become a permanent operational concern (chapter 11 is entirely about this).
- **Cross-cutting user experience** — routing, auth, the design system, analytics — must work across independently deployed parts. That's architectural work that simply doesn't exist in a monolithic build.
- **Infrastructure**: N artifacts, N deploys, a compatibility matrix of "which catalog works with which shell".

### The mechanics of Module Federation: host, remote, container

Module Federation is a bundler feature, born in webpack 5. It lets an application load modules **at runtime** from other applications, separately built and separately deployed.

```
      ┌───────────────────────────────┐
      │ shell (host)                  │
      │ router, layout, auth,         │
      │ the remotes' remoteEntry URLs │
      └───────────────────────────────┘
   loads at runtime, in the user's browser
                      ▼
┌──────────────────┐    ┌───────────────────┐
│ catalog (remote) │    │ checkout (remote) │
│ exposes:         │    │ exposes:          │
│ ./CatalogPage    │    │ ./CheckoutPage    │
└──────────────────┘    └───────────────────┘
```

The vocabulary:

- A **remote** is an application that *exposes* modules to the outside (`exposes: { './CatalogPage': './src/...' }`). It builds into ordinary chunks plus one special file — **remoteEntry.js**: a small container manifest listing the exposed modules and the shared dependency declarations. Don't confuse things: remoteEntry is the table of contents, not the code; the code arrives as chunks on demand.
- A **host** is an application that knows the remoteEntry URLs of its remotes and loads their modules at runtime.
- The **container** is the JS object a remote presents itself as. It has two methods: `init(sharedScope)` — "here's the shared dependency scope, plug in" — and `get(moduleName)` — "hand me the module factory". The entire Module Federation API is essentially these two calls.

The full load sequence (the core of the chapter — read the diagram twice):

```
┌──────────────────────────────────────────────────────────────┐
│ the browser loads shell (host):                              │
│ its own bundle + the list of remoteEntry URLs                │
└──────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ host fetches the catalog's remoteEntry.js —                  │
│ a small container manifest, not the whole bundle             │
└──────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ container.init(sharedScope):                                 │
│ host and remote declare their react, react-dom, ... versions │
└──────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ shared negotiation: for every dependency                     │
│ one compatible instance is chosen                            │
└──────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ container.get("./CatalogPage") →                             │
│ the catalog module's chunks are fetched                      │
└──────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ CatalogPage renders inside the host's tree                   │
│ using that one negotiated react                              │
└──────────────────────────────────────────────────────────────┘
```

### Shared dependencies: singleton, strictVersion, eager

If every remote shipped its own react, a page with three remotes would load React four times. And that's not even the worst part (see question 4 at the end). So dependencies are declared **shared**. During `init` each side says "I need react ^18.2, I can provide 18.3.1". One instance satisfying everyone is then chosen in the shared scope.

Three flags govern the negotiation:

- **`singleton: true`** — only one instance may exist, even if the versions are formally incompatible (then a warning is logged and the already-loaded one is used). Mandatory for react, react-dom, the router, any library with global state or Context.
- **`strictVersion: true`** — an incompatibility becomes a runtime error instead of a warning. Harsh, but the mismatch is visible immediately rather than through a broken hook in production.
- **`eager: true`** — the dependency is put into the initial bundle instead of being loaded asynchronously. Needed on the host side for the most fundamental dependencies. It is tied to the classic "Shared module is not available for eager consumption" error, which we'll reproduce deliberately in chapter 11.

### Runtime vs build-time composition

The key mental shift: until now `import { CatalogPage } from '@mini-shop/catalog-feature'` was resolved **at build time**. The catalog code was compiled into shell's bundle, the version frozen forever, one deploy.

With MF the catalog module resolves **in the user's browser**: shell learns what CatalogPage is only at load time. Hence the superpower: deploy catalog, and every user gets the new catalog without rebuilding shell. Hence also the entire price: nobody at build time verified that the new catalog is compatible with the old shell.

### The alternatives you must know

- **Build-time composition** (our current mini-shop): monorepo imports, one artifact, one deploy. The default choice.
- **Composition by route**: `/catalog` and `/checkout` are separate single-page applications behind a reverse proxy, and switching between them is a full page reload. Cheap, reliable, independent deploys included. You sacrifice the seamless single-page feel and shared in-memory state.
- **iframe**: maximum isolation (styles, JS, failures), embedding third-party/legacy things; the price is postMessage communication, duplicated dependencies, pain with routing, modals and heights. Underrated for admin panels and widgets.
- **single-spa**: an orchestrator that runs the lifecycles of several single-page applications on one page. It answers "when to mount", while MF answers "where the code comes from". They're sometimes used together.

The selection rule has three branches. No need for independent deploys → build-time. Needed at the *page* level → composition by route. Needed inside one page, with a seamless single-page feel → Module Federation.

> **Versions.** MF was born in webpack 5. Nx can build federation with both webpack and rspack — the Rust implementation, noticeably faster, which recent Nx versions offer by default. For vite, federation means third-party plugins outside of mainline Nx support. That's why in chapter 10 our MF apps will be on webpack or rspack, not on vite like shell has been so far.

> **Module Federation 2.0.** Modern Nx versions use it (`@module-federation/enhanced`), with runtime plugins and type generation between host and remote. Older repos have the "native" webpack ModuleFederationPlugin without those.

## In a real-world monorepo

- `find . -name "module-federation.config.*" -not -path '*/node_modules/*'` — who's the host, who's a remote: the host config has `remotes: [...]`, a remote has `exposes: {...}`.
- Open your product's production → Network tab → filter "remoteEntry": how many remotes actually load, and from which domains and content delivery networks? What follows each remoteEntry in the waterfall?
- `curl -s https://<prod>/catalog/remoteEntry.js | head -c 400` — remoteEntry is readable: the container name and module map are visible right at the top.
- In the shared config, check react: is `singleton: true` there (its absence is a time bomb, chapter 11).
- The main audit: are the remotes *actually* deployed independently? If continuous integration (CI) builds and ships everything together, the team pays the full price of MF and gets none of its only benefit. That is a typical "archaeological find" of chapter 14.

## What we're adding to the project

Nothing — this chapter is preparation. In chapter 10 mini-shop becomes a federation. Shell turns into a host, catalog and checkout remotes appear, and everything from this chapter becomes lines of config.

## Practical exercise

No code — we design and answer in writing (these are the decisions that turn into configs in chapter 10).

1. **Architecture selection.** For three products choose: build-time / composition by route / MF / iframe — with a one-or-two-sentence justification:
   - (a) a startup, 6 frontend engineers in one team, releases twice a week;
   - (b) a banking portal: 5 teams, each owning a domain (payments, loans, investments), release cycles from a day to a month. A seamless single-page experience is mandatory;
   - (c) a SaaS (software as a service) dashboard where customers embed their own widgets with arbitrary code.
2. **Reading the load sequence.** Using the theory diagram, answer:
   - what does the user see if the content delivery network (CDN) hosting the catalog's remoteEntry is down? And where in the host must the protection live?
   - what happens at the negotiation step if shell was built with react 18.3 and catalog with react 19, given `singleton: true` without strictVersion? And with `strictVersion: true`?
3. **Designing mini-shop.** Write down three things. What catalog exposes and what checkout exposes (a module = a page? a component? a route?). The full shared list with flags. Where routing, layout and the design system (shared-ui) live, and why.

**Edge cases to think about:**

- Two remotes use different major versions of the design system. Is that a shared-negotiation problem or an organizational one?
- A remote wants its own Redux store. Where's the line between "the remote's own state" and "application-wide state"?
- How does MF coexist with server-side rendering (SSR) and search engine optimisation (SEO)?

## Worked solution

**1. Architecture selection.**

- (a) **Build-time** (a monorepo, like our mini-shop today). One team — there's nobody to deploy independently; MF would add its entire price to solve a nonexistent problem.
- (b) **Module Federation**. Many teams, independent release cycles, a seamless single-page experience: composition by route, with its page reloads, fails the requirements. This is precisely the MF profile. The monorepo stays — MF and a monorepo aren't competitors but layers (chapter 10 shows this literally).
- (c) **iframe**. Arbitrary third-party code on your page is an isolation and security question, not a module-composition one. MF executes a remote in the shared JS context, which is unacceptable for untrusted code.

**2. Reading the sequence.**

- An unreachable remoteEntry is a failure at step 2: the `container` never comes to exist, there's nobody to call `get()` on. Without protection the whole host goes down. The protection lives at the module-loading boundary. The dynamic `import()` of the remote module is wrapped in an error boundary with a fallback view: "Catalog is temporarily unavailable". The catalog route then degrades without killing the app. This is an architectural consequence of runtime composition: in build-time land this error cannot exist.
- With `singleton: true` and no strictVersion, one react remains in the shared scope: whichever loaded first, here the host's 18.3. A compatibility warning hits the console. Catalog, built against the react 19 API, then executes on 18.3. It may work, or it may break on the first use of an API that 18.3 doesn't have. With `strictVersion: true` you get an immediate runtime error at the negotiation step. That is harsher, but more honest than an "authService is undefined" somewhere deep inside.

**3. Designing mini-shop** (this becomes chapter 10's configs):

- catalog exposes `./CatalogPage`, checkout exposes `./CheckoutPage`. **A page or route is the right exposure granularity.** Exposing dozens of small components turns a remote into "an npm package delivered over HTTP" and drowns you in a compatibility matrix.
- shared: `react` and `react-dom` — `singleton: true`, mandatory; the router (once it appears) — also a singleton: an application has one navigation history.
- Routing and layout — in the host: that's literally its job (composition plus the cross-cutting user experience). The design system (shared-ui) is a workspace lib shared between remotes; how exactly it behaves under federation is the central plot of chapter 11.

**Edge cases.**

- Two remotes on different design-system majors: negotiation survives, because this is not a singleton and each brings its own copy. The styling and the user experience do not survive: the user sees two visual languages on one page. It's an organizational problem, solved by version management and upgrade discipline, not by webpack flags.
- A remote's internal state (catalog filters) is its own business — Redux, zustand, whatever. Application-wide state — the cart, the user — is an application-level contract. Either the host provides it via a shared singleton lib with events, or via an explicit API: props and callbacks passed into the exposed module. The rule is the same as chapter 06: shared things live in shared — as a deliberate contract, not "the remote reached into window".
- SSR + MF is possible (federation on the server), but the complexity jumps an order of magnitude: you must render negotiated-consistent versions on server and client. The honest answer: if SEO and SSR are critical, seriously consider per-page composition by route, or build-time, before dragging federation onto the server.

## Check yourself

1. State the single real reason for microfrontends. Why isn't "code sharing between teams" it?
2. What is remoteEntry.js, why is it small, and what are the container's two methods? What happens during each?
3. Describe shared negotiation: where the version candidates come from, who chooses, and how singleton, strictVersion and eager change the outcome.
4. Why do two react instances on a page break the application even when the versions are identical? Name the concrete mechanisms.
5. Which errors that build-time composition catches for free simply don't exist at MF build time — and what conventionally compensates for them?

<details>
<summary>Answers</summary>

1. Independent deployment by independent teams: the ability to ship your part of the interface without building or coordinating everyone else's release. Code sharing is solved by a monorepo or by packages, with zero runtime risk. If that's all you need, MF charges the full price of runtime integration for a problem that's already solved.
2. remoteEntry.js is the remote's container manifest: the name, the exposes module map, the shared declarations. It's small because it contains no module code — only the table of contents and a loader. The code itself arrives as on-demand chunks. The `init(sharedScope)` call plugs the remote into the common dependency scope: it declares its versions and learns the others'. The `get(name)` call returns the exposed module's factory, fetching its chunks along the way.
3. During `init` each side puts entries into the shared scope: "package → the version I can provide + the range I require". For every package an instance satisfying the requirements is chosen, typically the highest compatible one offered. The `singleton` flag forces a single instance even on conflict: a warning is logged and the already-loaded one wins. The `strictVersion` flag upgrades that conflict from a warning to an error. The `eager` flag puts the dependency into the initial bundle, removing the async load — and creating the async-boundary requirement for consumers (chapter 11).
4. React keeps per-instance global state, and it diverges in three places. (a) The hooks dispatcher: a component rendered by a "foreign" react calls hooks on the wrong dispatcher, which is "Invalid hook call". (b) Context: a `createContext` from instance A and a `useContext` from instance B are different objects, so the provider is "invisible". (c) Two ReactDOMs fight over events and reconciliation. Identical versions don't help. The problem is two module copies with separate state, which is why react is always `singleton: true`.
5. Three things go unchecked. The signatures and types of exposed modules, because the host builds without ever seeing the remote's real code. The compatibility of shared versions. The very existence of a module at the address. The compensation is a set of conventions. Type generation and checking between host and remote (MF 2.0, chapter 11). Contract and e2e tests of the pair. Canary deployments of remotes. Error boundaries with fallbacks at every remote attachment point.

</details>

## Common mistake

A developer from the single-app world brings the npm-package mental model into an MF project. It sounds like this: "catalog is a dependency of shell. Its version is pinned in some lock file, and nothing changes until I bump it".

With Module Federation this is wrong in the most important way. The remote arrives at runtime, and its "version" is **whatever is on the CDN right now** — not what existed when the host was built. Hence the classic bewilderment: "we didn't deploy anything, yet production broke". It broke because the neighbouring team deployed their remote.

Diagnosing such incidents starts not with your repo's git log but with the question "who deployed what in the last hour". That is a fundamental shift compared to a monolith.

The second mistake is dragging MF where a single team deploys, "because it's modern" or "to speed up builds". Build speed is solved by the cache and affected (chapters 04–05). A single team doesn't need independent deploys, so what remains is pure cost: runtime risks, implicit contracts, infrastructure for N artifacts.

Microfrontends are an organizational tool for an organizational problem. If the problem doesn't exist, the best MF is none.
