# React SPA — Keycloak Integration

## From protocol to a real React app

Articles 01-04 gave you the protocol foundation and what a correct backend looks like. This article covers what all that looks like from the other end of the wire: a React app that has to kick off login, survive a page refresh, refresh tokens without annoying the user, and handle logout correctly. This is where most real-world practical mistakes happen — not because React is hard, but because the fine print of browser mechanics (iframes, cookie policies) is poorly documented and almost never shows up during local development.

## Why Authorization Code + PKCE is the only option for an SPA

A React SPA is a **public client** by the definition from article 02: all the code runs in the user's browser, so any "secret" baked into the JS bundle is accessible to anyone who opens DevTools → Sources. The only protocol-correct flow for such a client is Authorization Code + PKCE (the full sequence is in article 01): no `client_secret` is needed at all, and `code_verifier` protects against authorization code interception without any secret. The Implicit Grant, historically used specifically for SPAs, is ruled out for the reasons covered in article 01 (the token traveling through the URL fragment — in the clear, in browser history) — today no modern adapter, `keycloak-js` included, offers Implicit as a default option.

## keycloak-js — the main adapter, step by step

`keycloak-js` is Keycloak's official JS library, implementing the Authorization Code + PKCE flow and token management for browser apps.

```typescript
// keycloak.ts — a single instance for the whole app
import Keycloak from 'keycloak-js';

export const keycloak = new Keycloak({
  url: 'https://keycloak.example.com',
  realm: 'myrealm',
  clientId: 'spa-client', // a public client, no secret
});
```

```typescript
// App.tsx — initialization at app startup
async function initAuth() {
  const authenticated = await keycloak.init({
    onLoad: 'check-sso', // see the breakdown below
    silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
    pkceMethod: 'S256', // explicitly enable PKCE (default in newer versions)
  });
  return authenticated;
}
```

### `onLoad: 'check-sso'` vs `'login-required'`

This is the first decision you have to make, and it shapes the whole app's UX:

```txt
onLoad: 'login-required':
  On loading ANY page of the app, if the user isn't authenticated —
  an immediate redirect to Keycloak login.
  Fits: apps where 100% of the functionality requires login
  (internal admin panels, dashboards) — there's no "anonymous" state.

onLoad: 'check-sso':
  On loading a page — a silent, invisible check for "maybe the user
  already has an active SSO session in Keycloak (logged in on
  another tab/app)?" with NO redirect if there's no session — the
  app stays in an unauthenticated state that's still usable visually
  (you can show a landing page, a "Log in" button).
  Fits: apps with mixed content — some public pages (a landing page,
  docs) and some pages that require login.
```

The `check-sso` mechanism is exactly where this topic's most notorious practical problem hides — covered below.

## silent-check-sso — how it works, and why it's fragile in the real world

To check "is there an active Keycloak session" without visibly redirecting the user to a different domain, `keycloak-js` uses a classic trick: an **invisible `<iframe>`** that loads a special page from Keycloak's domain, which in turn "tells" the parent window the result via `postMessage`.

```txt
1. The React app (https://app.example.com), on startup, creates an
   invisible iframe, src = https://keycloak.example.com/...&prompt=none

2. If the user DOES have an active session on the keycloak.example.com
   domain (Keycloak set its session cookie during a previous login) —
   Keycloak, inside the iframe, IMMEDIATELY hands back an authorization
   code, with no login form

3. The iframe redirects to silent-check-sso.html (also on the
   app.example.com domain — a static file served with the SPA), which
   passes the code to the parent window via postMessage

4. The parent window exchanges the code for tokens (back-channel,
   see article 01) — the user never saw a login form, or even the
   iframe itself
```

```html
<!-- public/silent-check-sso.html — a minimal static page -->
<!DOCTYPE html>
<html>
  <body>
    <script>
      parent.postMessage(location.href, location.origin);
    </script>
  </body>
</html>
```

The problem is in step 2: for Keycloak to "recognize" the user inside the iframe with no login form, the browser has to send Keycloak's session cookie **in the context of an iframe embedded in a domain that's foreign, from Keycloak's point of view — app.example.com** — that's a classic **third-party cookie** scenario from the browser's perspective (a cookie belonging to keycloak.example.com being sent while the user is physically on app.example.com).

```txt
Safari ITP (Intelligent Tracking Prevention):
  Blocks third-party cookies by default, and has for years.
  silent-check-sso SIMPLY DOESN'T WORK in Safari out of the box —
  the iframe loads, but Keycloak's session cookie isn't sent,
  Keycloak inside the iframe doesn't see the user as logged in,
  even if they have an active session in a neighboring tab.

Chrome, phasing out third-party cookies:
  The same end effect, rolled out gradually across every
  Chromium-based browser — third-party cookies stop being a
  reliable cross-domain identification mechanism at all.

The practical end result:
  A user CAN be genuinely logged into Keycloak (the session is
  alive, they just logged in on a sibling tab of the same SPA, or
  on a different client in the same realm) — but silent-check-sso
  silently "fails to find" the session, the app treats the user as
  unauthenticated, and they see a login screen even though they're
  formally already logged in.
  This looks like "the app randomly logs me out out of nowhere,"
  even though the real problem is in the CHECKING mechanism, not in logout.
```

This isn't a hypothetical — it's a systemic production issue: discussions of "why doesn't keycloak-js check-sso work in Safari" are everywhere in issue trackers, and it's not a library bug, it's a fundamental conflict between iframe-based silent checking and modern browser policy against third-party cookies.

```txt
Practical mitigations (none of them remove the problem entirely):

  1. Accept "check-sso can wrongly show an unauthenticated state in
     Safari" as a fact, and make sure the UX for that case is fine
     (a visible, working "Log in" button, not a blank screen)

  2. Use 'login-required' instead of 'check-sso' if the app has no
     real anonymous content — then the silent-check-sso problem
     never comes up at all, because the redirect is explicit

  3. Move to the BFF pattern (article 06) — there, session
     identification happens through the app's own first-party
     cookie, not a cross-domain iframe trick, and the third-party
     cookie problem disappears architecturally, not through patches
```

## Login, logout, token refresh — the basic API

```typescript
// Trigger login — a full redirect to Keycloak (not an iframe)
function login() {
  keycloak.login({ redirectUri: window.location.origin + '/dashboard' });
}

// Logout — a redirect to Keycloak's logout endpoint (front-channel, see article 03)
function logout() {
  keycloak.logout({ redirectUri: window.location.origin });
}

// updateToken — refreshing the access token via the refresh token
// minValidity: refresh IF the token expires in fewer than N seconds
async function ensureFreshToken(): Promise<string> {
  try {
    const refreshed = await keycloak.updateToken(30);
    if (refreshed) {
      console.debug('Token was refreshed');
    }
    return keycloak.token!;
  } catch {
    // the refresh token is also invalid/expired — the only correct
    // way out is a full re-login, see the React Query section below
    keycloak.login();
    throw new Error('Session expired, redirecting to login');
  }
}
```

An important detail about `updateToken(minValidity)`: if you call it when the token is already fresh (more than `minValidity` seconds left), `keycloak-js` **makes no network call at all** — it just returns `false` ("no refresh needed"), so it's safe to call this method before every API request without risking flooding Keycloak with extra calls.

## Alternative: oidc-client-ts / react-oidc-context — portability over Keycloak-specific tooling

`keycloak-js` is convenient and well-documented for Keycloak specifically, but it carries Keycloak-specific API details (`updateToken`, the `onLoad` shape) that don't map directly onto a different OIDC provider. The alternative is **`oidc-client-ts`** (and its React wrapper, `react-oidc-context`) — a library implementing OIDC as a protocol standard, with no vendor lock-in.

```tsx
// An example with react-oidc-context — the config speaks in protocol
// terms, not Keycloak-specific ones
import { AuthProvider } from 'react-oidc-context';

const oidcConfig = {
  authority: 'https://keycloak.example.com/realms/myrealm', // also works for Auth0/Okta
  client_id: 'spa-client',
  redirect_uri: window.location.origin + '/callback',
  scope: 'openid profile email',
  automaticSilentRenew: true, // the same silent-iframe mechanism, same ITP limitations
};

function App() {
  return (
    <AuthProvider {...oidcConfig}>
      <Dashboard />
    </AuthProvider>
  );
}
```

```txt
When to pick keycloak-js:
  - The project is clearly and durably tied to Keycloak
  - You need Keycloak-specific features (Authorization Services from
    article 04 have their own JS helpers in the Keycloak ecosystem)
  - The team is already familiar with the adapter's Keycloak terminology

When to pick oidc-client-ts/react-oidc-context:
  - Vendor independence matters in principle (migrating to
    Auth0/Okta/Cognito shouldn't require rewriting the app's auth
    layer — see the comparison in [Keycloak vs Alternatives])
  - The team prefers thinking in protocol terms (OIDC) rather than
    a specific product's terms
  - A multi-provider strategy (different clients on different IdPs)

An important caveat: silent-check-sso / silent renew use the SAME
iframe + third-party cookie mechanism in BOTH libraries — switching
to oidc-client-ts does NOT solve the Safari ITP problem by itself,
it only changes the API you're wrapped in. The real fix for the
fragility is architectural (BFF, article 06), not a library swap.
```

## Wiring tokens into fetch/axios/React Query — doing it correctly

The token needs to be: (1) attached to every request, (2) refreshed on a `401`, (3) followed by a retry of the original request after the refresh, (4) gracefully given up on (a forced re-login) if the refresh fails.

```typescript
// An axios interceptor — attaching the token + retrying after a refresh
import axios from 'axios';
import { keycloak } from './keycloak';

const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use(async (config) => {
  await keycloak.updateToken(30); // makes no call if the token is still fresh
  config.headers.Authorization = `Bearer ${keycloak.token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true; // guards against an infinite retry loop
      try {
        await keycloak.updateToken(-1); // force a refresh
        originalRequest.headers.Authorization = `Bearer ${keycloak.token}`;
        return api(originalRequest); // retry the ORIGINAL request with the new token
      } catch {
        keycloak.login(); // the refresh also failed — full re-login
      }
    }
    return Promise.reject(error);
  },
);
```

```typescript
// React Query — global 401 handling without manually wrapping every useQuery
import { QueryClient, QueryCache } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      if (isAxios401(error)) {
        // the axios interceptor above already tried to refresh and retry —
        // if the error still made it here, a forced re-login has already
        // been triggered by the interceptor; here it's enough to just not
        // surface a raw 401 error in the UI
      }
    },
  }),
});
```

A key architectural point: **the "refresh → retry → give up and log out" logic lives in ONE place (the interceptor), not scattered across every API call** — this is exactly how the client side fulfills the obligation fixed in article 04 ("the backend doesn't refresh the token, that's the client's job") with concrete, testable code.

## Protected routes and a correct logout redirect cycle

```tsx
// ProtectedRoute — a wrapper for routes that require authentication
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { keycloak, initialized } = useKeycloak();

  if (!initialized) return <LoadingSpinner />; // check-sso is still in progress
  if (!keycloak.authenticated) {
    keycloak.login({ redirectUri: window.location.href }); // come back HERE after login
    return <LoadingSpinner />;
  }
  return <>{children}</>;
}
```

A common logout mistake is forgetting that `keycloak.logout()` triggers a **full browser redirect** (front-channel, article 03), not just a local state cleanup: if you don't pass `redirectUri`, the user can end up stuck on Keycloak's default page after logout instead of returning to the app. A second common bug is clearing local React state (the React Query cache, a Redux store) BEFORE triggering `keycloak.logout()` — by the time the browser has already started navigating to a different domain, extra re-renders of the app don't matter, but if the logout logic relies on an async cache-clear completing BEFORE the redirect, and the redirect synchronously takes the browser away before the promise resolves, part of the cleanup logic (sending logout analytics, say) might never finish.

```typescript
// The correct order — cleanup synchronously/quickly, THEN redirect
function handleLogout() {
  queryClient.clear(); // a synchronous React Query cache clear
  analytics.track('logout'); // fire-and-forget, doesn't block
  keycloak.logout({ redirectUri: window.location.origin }); // redirect — the last step
}
```

## Tying it together

```txt
[Auth Code + PKCE for an SPA]  →  the only correct flow for a public
                                 client — a direct consequence of the
                                 protocol constraints from article 01

[onLoad: check-sso vs
 login-required]                 →  the choice depends on whether the
                                 app has any anonymous content

[silent-check-sso + iframe]      →  an elegant mechanism that breaks
                                 against the third-party cookie
                                 restrictions of Safari/Chrome — a
                                 systemic, not an occasional, problem

[keycloak-js vs oidc-client-ts]  →  convenience vs portability; BOTH
                                 use the same fragile iframe mechanism
                                 under the hood

[axios/React Query wiring]       →  the refresh-retry-relogin logic
                                 lives in one place (the interceptor),
                                 not scattered across calls

[Logout redirect cycle]          →  logout is a redirect, not just a
                                 state clear; the order of cleanup vs
                                 redirect matters
```

The next article — [Token Storage and the BFF Pattern] — takes exactly the problem from this article (silent-check-sso's fragility, the need to trust browser-side token storage) and shows an architectural way out that fixes it by changing the model, not by patching around it.

## Common interview traps

- **"Implicit Grant is simpler for an SPA, so it's worth using if PKCE seems complicated"** — no, Implicit is a recognized insecure pattern (see article 01), and PKCE is entirely encapsulated inside `keycloak-js`/`oidc-client-ts` — PKCE's "complexity" never shows up in application code at all, so it's not a reason to fall back to a deprecated flow.

- **"check-sso always reliably tells you whether the user is logged in"** — no, it systematically breaks in Safari (ITP blocks third-party cookies) and is gradually breaking in Chrome — the app can wrongly treat a genuinely logged-in user as unauthenticated. A good answer mentions this fragility and knows at least one mitigation (`login-required` instead of `check-sso`, or the BFF pattern).

- **"oidc-client-ts fixes the silent-check-sso problem, because it's a more modern library"** — no, both libraries use the exact same iframe + third-party cookie mechanism under the hood; switching libraries doesn't remove the fundamental browser cookie-policy constraint, it just changes the API you're wrapped in.

- **"You can just keep the token in a variable and attach it to requests, we'll handle refresh separately if it comes up"** — an underestimate: without centralized retry logic in an interceptor, every single API call has to handle token expiry on its own, which almost guarantees duplicated code and missed cases (forgetting to handle a 401 in one of fifty call sites).

- **"Logout is just calling keycloak.logout(), nothing else to think about"** — misses: (1) the mandatory `redirectUri`, or the user gets stuck on a Keycloak page; (2) cleanup ordering — if the app relies on an async state clear completing BEFORE the redirect, the browser's synchronous navigation can cut it off.
