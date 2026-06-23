<!-- verified: 2026-06-23, corrections: 0 -->
# REST Principles

## What REST Actually Is

REST (Representational State Transfer) is not a protocol and not a standard. It is an **architectural style** described by Roy Fielding in his 2000 dissertation. Fielding was one of the authors of HTTP/1.1 and described REST as a set of constraints that, when satisfied, produce certain desirable properties: scalability, component independence, cacheability.

```txt
REST is NOT:
  ❌ HTTP API with JSON
  ❌ "CRUD over HTTP"
  ❌ a set of URL naming conventions
  ❌ an official standard with a specification

REST IS:
  ✅ a set of 6 architectural constraints
  ✅ a style that yields system properties when applied
  ✅ an idea about how a scalable distributed web system should look
```

Most APIs call themselves "RESTful" while satisfying 3–4 of the 6 constraints. That's fine — it's "practical REST" or "REST-ish." On interviews, the key is to distinguish theoretical REST from what gets built in practice.

---

## The Six Fielding Constraints — Explained Plainly

### 1. Client-Server

Client and server are separated: the client doesn't know about data storage, the server doesn't know about the user interface. This separation allows them to evolve independently.

```txt
What this enables:
  - Client (browser, mobile app) changes without touching the server
  - Server doesn't hold UI state — that's the client's responsibility
  - One API serves multiple clients (web, mobile, CLI)
```

### 2. Stateless

Every request contains all the information the server needs to process it. The server holds no context between requests.

```txt
What this enables:
  - Horizontal scaling: any server instance can handle any request
    (no sticky sessions required)
  - Fault tolerance: a crashed instance loses no session state
  - Visibility: every request is self-contained for logging/monitoring

The cost:
  - Client must send an auth token with every request
  - Slightly more bandwidth (repeated headers)
```

### 3. Cacheable

Responses must explicitly state whether they can be cached. Cacheable responses may be reused by the client or intermediaries (CDN, proxies).

```http
Cache-Control: max-age=3600, public   ← cacheable for 1 hour, including CDN
Cache-Control: no-store               ← do not cache (personal data)
ETag: "abc123"                        ← version token for conditional requests
```

### 4. Uniform Interface

The central constraint of REST. It consists of 4 sub-constraints:

```txt
4a. Resource Identification:
    Resources are identified by URIs: /users/42, /orders/100/items

4b. Resource Manipulation through Representations:
    Clients work with representations of resources (JSON, XML),
    not the resources directly. The resource is a concept;
    the representation is what travels over the wire.

4c. Self-Descriptive Messages:
    Each message contains enough information to be processed:
    Content-Type, status code, method semantics.

4d. HATEOAS:
    Clients transition between states by following links
    returned by the server. (More below.)
```

### 5. Layered System

The client doesn't know whether it's talking directly to a server, a CDN, a load balancer, or an API gateway. Intermediaries are transparent.

```txt
Client → CDN (cache hit, no backend involved)
Client → Load Balancer → one of N servers
Client → API Gateway → Microservice A or B
```

### 6. Code on Demand (optional)

The server may send executable code to the client (JavaScript). The only optional constraint — which is why browsers downloading JS is still "RESTful."

---

## Resource-Oriented URL Design

The central idea of REST: **URLs identify resources** (nouns), **HTTP methods describe the action** (verbs).

### Basic Rules

```txt
✅ Correct — nouns, resource hierarchy:
GET    /users            — list of users
GET    /users/42         — specific user
POST   /users            — create a user
PUT    /users/42         — replace a user entirely
PATCH  /users/42         — partial update
DELETE /users/42         — delete a user

GET    /users/42/orders          — orders belonging to user 42
GET    /users/42/orders/7        — a specific order of user 42
POST   /users/42/orders          — create an order for user 42

❌ Wrong — verbs in URLs (RPC style):
GET  /getUser?id=42
POST /createUser
POST /deleteUser/42
POST /updateUserEmail
```

### Collections and Individual Resources

```txt
/users          — collection (plural)
/users/42       — individual resource (identifier)
/users/42/posts — sub-collection (posts belonging to user 42)

Nesting depth: no more than 2–3 levels
/users/42/posts/7/comments — acceptable
/users/42/posts/7/comments/3/replies/1 — too deep;
  prefer: /comments/3/replies or /replies/1
```

### Actions That Don't Fit CRUD

Not everything in an API is CRUD. How to model actions:

```txt
Option 1 — Sub-resource (preferred):
POST /orders/42/cancel         — create a "cancellation" of the order
POST /users/42/password-reset  — trigger a password reset flow
POST /articles/7/publish       — publish the article

Option 2 — Field update via PATCH:
PATCH /orders/42
{ "status": "cancelled" }

Option 3 — Separate event collection:
POST /order-cancellations
{ "orderId": 42, "reason": "customer_request" }
```

### Filtering, Sorting, Pagination — Query Params

```txt
Filtering:
GET /users?role=admin&status=active

Sorting:
GET /users?sort=createdAt&order=desc
GET /users?sort=-createdAt          (minus prefix = desc — popular convention)

Pagination:
GET /users?page=2&limit=20          (offset-based)
GET /users?cursor=eyJpZCI6NDJ9&limit=20 (cursor-based)

Search:
GET /users?q=alice
GET /users?search=alice&fields=name,email

Sparse fieldsets:
GET /users?fields=id,name,email
```

---

## The Honest Picture: REST in Practice Is "RPC with Conventions"

Most "REST APIs" are actually RPC (Remote Procedure Call) over HTTP with JSON and some REST-ish conventions. Here's why:

```txt
Theoretical REST requires:
  1. HATEOAS — client follows links from responses, never hard-codes URLs
  2. Content negotiation — server returns JSON or XML based on Accept header
  3. Self-descriptive messages — every response carries full semantics

Reality:
  1. Clients hard-code URLs (baked into code or documentation)
  2. JSON and only JSON (XML is dead for most APIs)
  3. Documentation is OpenAPI/Swagger, not HATEOAS
```

This is fine. The Richardson Maturity Model maps this spectrum explicitly:

```txt
Level 0: One URL, one method (SOAP, XML-RPC)
  POST /api {"action": "getUser", "id": 42}

Level 1: Resources (different URLs, but single method)
  POST /users/42

Level 2: HTTP verbs (methods carry semantic meaning)
  GET /users/42   → read
  DELETE /users/42 → delete
  ↑ MOST "REST APIs" live here ↑

Level 3: HATEOAS (response contains links for next actions)
  ↑ rarely seen in real-world APIs ↑
```

---

## HATEOAS — Explained and Honestly Assessed

HATEOAS (Hypermedia As The Engine Of Application State) is the most radical and least-implemented REST constraint.

The idea: the client should not know URLs in advance. It gets an entry point (`/api`) and follows hyperlinks returned by the server — exactly like a person clicking links in a browser.

```json
// Response with HATEOAS (HAL format):
{
  "id": 42,
  "name": "Alice",
  "status": "active",
  "_links": {
    "self":    { "href": "/users/42" },
    "orders":  { "href": "/users/42/orders" },
    "suspend": { "href": "/users/42/suspend", "method": "POST" },
    "delete":  { "href": "/users/42", "method": "DELETE" }
  }
}
```

The client reads `_links` and discovers which actions are available right now — without knowing URLs in advance.

```txt
Theoretical advantages of HATEOAS:
  - Server can change URLs without breaking clients (client follows links)
  - Client can see which actions are available in the current state
    (suspend only shows up if status=active)
  - True client-server decoupling

Why almost nobody implements it fully:
  1. Clients still hard-code flow logic:
     "after POST /login, navigate to /dashboard"
  2. Parsing _links and building a UI dynamically is very complex
  3. Documentation (OpenAPI) provides the same discoverability,
     more simply
  4. Browsers follow links naturally. REST APIs are consumed by
     JavaScript code that needs predictability, not discovery
  5. No dominant standard: HAL, JSON:API, Siren, Collection+JSON
     are all incompatible formats
```

**Practical takeaway:** know what HATEOAS is for interviews, understand its theoretical purpose, but don't expect to see it in real projects.

---

## API Versioning

When an API changes incompatibly (breaking change), versioning is required. Three approaches:

### 1. Version in the URL (most common)

```txt
https://api.example.com/v1/users
https://api.example.com/v2/users
```

**Pros:**
- Immediately visible, no header inspection needed
- Easy to test in browser or curl
- Easy to cache (URL is unique)
- Easy to route at nginx/API gateway level

**Cons:**
- Violates REST: the URI should identify a resource, not an API version
- `/v1/users/42` and `/v2/users/42` represent the same resource
- Clients hard-code the version; migration requires code changes

### 2. Version in a Header (Accept or custom)

```http
GET /users/42 HTTP/1.1
Accept: application/vnd.myapi.v2+json

# Or a custom header:
GET /users/42 HTTP/1.1
API-Version: 2
```

**Pros:**
- URL stays clean — resource identification is correct
- Theoretically closer to REST (content negotiation)

**Cons:**
- Harder to test (curl/Postman needed, not a browser)
- Caching is tricky: one URL, different content per version
  (requires `Vary: Accept` header)
- Less obvious when reading client code

### 3. Version in a Query Parameter

```txt
GET /users/42?api-version=2
GET /users/42?v=2
```

**Pros:**
- Optional: without the parameter, default version is used
- Easy to bolt onto an existing API

**Cons:**
- Query params are conventionally for filtering, not versioning
- Creates confusion (`?version=2&status=active`)
- Some caches may ignore query params

### Comparison and Recommendation

```txt
┌──────────────────┬──────────┬──────────┬──────────┐
│                  │ URL /v1  │ Header   │ Query ?v │
├──────────────────┼──────────┼──────────┼──────────┤
│ Visibility       │ ✅ Immediate│ ❌ Hidden │ ✅ Visible │
│ Caching          │ ✅ Simple │ ❌ Complex│ ⚠️ Risky │
│ REST-correct     │ ❌ No    │ ✅ Yes    │ ❌ No    │
│ DX (ease of use) │ ✅ Simple │ ⚠️ Complex│ ✅ Simple│
│ Industry adoption│ ✅✅✅    │ ✅        │ ⚠️       │
└──────────────────┴──────────┴──────────┴──────────┘

Recommendation for most projects: /v1 in the URL.
Simpler, more robust, clearer for the team and consumers.
```

### Sunsetting Old Versions

```txt
1. Deprecation period: document the deprecation, set
   Deprecation/Sunset headers:

   Deprecation: true
   Sunset: Sat, 31 Dec 2026 23:59:59 GMT
   Link: <https://api.example.com/v2/users>; rel="successor-version"

2. Parallel versions: /v1 and /v2 run simultaneously
   for at least 6–12 months

3. Don't make /v1 immortal: old versions are technical debt
```

---

## Common Interview Traps

- **"REST is HTTP + JSON"** — no. REST is an architectural style with 6 constraints, independent of protocol. Theoretically REST could be implemented over FTP or email. In practice it runs over HTTP, but the substance is the constraints, not the protocol.

- **"Our API is RESTful"** — ask which level. Most APIs sit at Richardson Level 2 (resources + HTTP methods). HATEOAS (Level 3) is rare. Knowing this distinction signals depth of understanding.

- **"`POST /users/42/activate` violates REST"** — no, it's a valid sub-resource pattern. REST doesn't forbid actions — it says to think resource-first. "Activation" is the creation of an "active" state, or a sub-resource called "activation."

- **"Version in URL violates REST, should use headers"** — technically correct (URIs should identify resources), but URL versioning is the industry standard for caching, debugging, and simplicity reasons. Fielding himself said pragmatism matters more than purity.

- **"HATEOAS isn't needed at all"** — you need to understand why it exists. Its goal is true client-server decoupling: the ability to change URLs without recompiling clients. That this is usually solved by documentation and versioning instead is an honest answer.

- **"DELETE /users — delete all users"** — technically correct by REST rules (DELETE on a collection). In practice, almost never implemented due to obvious risk. The right answer: know the theory and understand why real-world APIs deviate from it.
