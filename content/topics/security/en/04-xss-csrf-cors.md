# XSS, CSRF, and CORS

## The Most Popular Web Security Topic

Very frequently asked:

```txt
What is XSS?

What is CSRF?

What is CORS?

How are they different?
```

---

# XSS

Cross Site Scripting.

---

The most widespread web attack.

---

# The Attack Idea

An attacker tricks the browser into executing:

```html
<script>
malicious code
</script>
```

---

On your website.

---

# Example

A user writes a comment:

```html
<script>
alert('Hacked')
</script>
```

---

The site saves it to the database.

---

Another user opens the page.

---

The browser executes:

```html
<script>
...
</script>
```

---

# Result

```txt
XSS
```

---

# Why This is Dangerous

Can steal:

```txt
JWT

Cookies

LocalStorage

User Actions
```

---

# Stored XSS

The most dangerous variant.

---

Code is saved to the database.

---

Example:

```txt
Comments

Forum

Chat
```

---

# Flow

```txt
Attacker
 ↓
Database
 ↓
Victim
```

---

# Reflected XSS

Not stored.

---

Passed through the request.

---

For example:

```txt
/search?q=<script>...</script>
```

---

The server returns it back.

---

# DOM XSS

Occurs on the client.

---

Example:

```js
element.innerHTML =
 userInput;
```

---

Very popular question.

---

# How to Protect

The most important question.

---

# Never

```js
innerHTML
```

---

For user data.

---

# Better

```js
textContent
```

---

# React

A big advantage of React.

---

React automatically:

```txt
escaping
```

---

HTML.

---

Therefore:

```tsx
<div>{userInput}</div>
```

---

Is safe.

---

# Dangerous

```tsx
dangerouslySetInnerHTML
```

---

# CSP

Content Security Policy.

---

Very frequently asked.

---

Header:

```http
Content-Security-Policy
```

---

Restricts:

```txt
which scripts can be executed
```

---

# HttpOnly Cookies

Another protection.

---

Even during XSS:

```txt
JavaScript
cannot read the cookie
```

---

# CSRF

Cross Site Request Forgery.

---

The next popular attack.

---

# The Idea

A user is already authenticated.

---

An attacker tricks the browser into:

```txt
sending a request
on behalf of the user
```

---

# Example

The user has open:

```txt
bank.com
```

---

And simultaneously:

```txt
evil.com
```

---

On evil.com there is:

```html
<form
 action="bank.com/transfer"
 method="POST">
</form>
```

---

The browser automatically attaches:

```txt
Cookies
```

---

The bank thinks:

```txt
this is the real user
```

---

# Why JWT in Header Protects

Very popular question.

---

The browser automatically sends:

```txt
Cookies
```

---

But does not send:

```txt
Authorization Header
```

---

Therefore:

```txt
JWT Header
```

---

Greatly reduces CSRF risk.

---

# CSRF Token

Classic protection.

---

The server issues:

```txt
a random token
```

---

The frontend sends it back.

---

The server verifies.

---

# SameSite Cookie

Very popular question.

---

Modern protection.

---

```http
Set-Cookie:
SameSite=Strict
```

---

The browser will not send the cookie
from a foreign site.

---

# CORS

Very often confused with security.

---

In reality:

```txt
CORS
does NOT protect the server
```

---

# What is CORS

Cross-Origin Resource Sharing.

---

A browser policy.

---

# Example

Frontend:

```txt
localhost:3000
```

---

Backend:

```txt
api.com
```

---

This is:

```txt
Different Origin
```

---

The browser blocks the request.

---

If the server has not allowed it.

---

# Allowing It

```http
Access-Control-Allow-Origin:
https://my-site.com
```

---

# Preflight Request

Very frequently asked.

---

Before the request:

```http
OPTIONS
```

---

The browser asks:

```txt
is this allowed?
```

---

# Common Question

Does CORS protect the API?

Answer:

No.

---

It protects the browser.

---

The server can still be called via:

```txt
curl

Postman

another backend
```

---

# Common Question

What is the difference between XSS and CSRF?

Answer:

XSS tricks the browser into executing foreign JavaScript.

CSRF tricks the browser into sending a legitimate request on behalf of the user.

---

# Common Question

Why does HttpOnly help against XSS?

Answer:

JavaScript cannot read the cookie contents.

---

# Interview Answer

XSS allows injecting and executing malicious JavaScript on a website. CSRF tricks the browser into sending requests on behalf of an authenticated user. CORS is a browser mechanism that regulates cross-origin requests but is not a complete API protection mechanism.
