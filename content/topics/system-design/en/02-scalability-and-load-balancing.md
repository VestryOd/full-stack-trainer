# Scalability and Load Balancing

## Scaling: a quick recap of vertical vs horizontal

The basic vertical vs horizontal scaling distinction is covered in [System Design Fundamentals]. The practical consequence to fix here: horizontal scaling is **impossible without a load balancer** — without one, you just have N independent servers that the client somehow has to choose between (or each gets its own DNS address), which doesn't scale and provides no fault tolerance.

So "add more servers" is only half an answer to a scaling question. The other half is **how traffic is distributed across them** and **what happens when one of them goes down**. That's the subject of Load Balancing.

## L4 vs L7 Load Balancer — decisions at different layers

This is one of the most important distinctions that often gets missed:

**L4 (Transport Layer) Load Balancer** operates at TCP/UDP — it sees only IP addresses and ports, never looks inside the request.

```txt
Routing decisions are based on:
  source IP, destination IP, source port, destination port

Pros: very fast (no payload parsing), low overhead
Limits: can't route by URL, headers, or cookies
```

**L7 (Application Layer) Load Balancer** operates at HTTP — it sees the URL, headers, cookies, request body.

```txt
Routing decisions are based on:
  path (/api/* → backend A, /static/* → CDN/backend B)
  headers (Authorization, User-Agent)
  cookies (sticky sessions)

Pros: flexible routing, A/B tests, canary deploys
Cons: higher latency (needs to terminate TLS and parse HTTP), more compute-expensive
```

Senior nuance: an L7 LB usually **terminates TLS** (HTTPS → HTTP inside the network), which is how it gets access to the request content, but it adds a decrypt/encrypt step on every request — that needs to be accounted for in the latency budget. Real systems often combine both layers: L4 (e.g., AWS NLB) at the edge for coarse distribution across regions/availability zones, and L7 (AWS ALB, Nginx, Envoy) internally for routing between services.

## Load balancing algorithms

| Algorithm | How it works | When it's good | When it's bad |
|---|---|---|---|
| **Round Robin** | In rotation: A → B → C → A → ... | Servers of equal capacity, requests of roughly equal "weight" | Doesn't account for current load — a slow server gets as many requests as a fast one |
| **Weighted Round Robin** | Like Round Robin, but with weights (a more powerful server gets more requests) | Servers of different capacity (e.g., a gradual canary rollout) | Weights are static, don't react to real-time load |
| **Least Connections** | The request goes to the server with the fewest active connections | Requests vary a lot in processing time | The LB needs to track connection state — slightly more expensive |
| **IP Hash / Consistent Hashing** | Routing is a function of a hash of the client IP (or another key) | Need "stickiness" without cookies, or cache-aware routing | With a plain hash (`hash % N`), adding/removing servers reshuffles **almost all** traffic |

### Consistent Hashing — why it's its own big topic

A plain `hash(key) % N` breaks when N changes: if you have 4 servers and add a fifth, `hash % N` changes for **most** keys, and they "move" to a different server — for a cache, that means a mass cache miss; for a sharded DB, a massive data rebalance.

**Consistent hashing** solves this by placing both servers and keys on the same hash "ring" — adding/removing a server only moves `~1/N` of the keys, not the whole set:

```ts
// Simplified consistent hashing with virtual nodes
class ConsistentHashRing {
  private ring = new Map<number, string>(); // hash -> server
  private sortedHashes: number[] = [];
  private readonly virtualNodesPerServer = 150; // reduces distribution skew

  addServer(serverId: string): void {
    for (let i = 0; i < this.virtualNodesPerServer; i++) {
      const hash = this.hash(`${serverId}#${i}`);
      this.ring.set(hash, serverId);
    }
    this.sortedHashes = [...this.ring.keys()].sort((a, b) => a - b);
  }

  getServer(key: string): string {
    const hash = this.hash(key);
    // find the first node on the ring with hash >= hash(key) (wrapping around)
    const index = this.sortedHashes.findIndex((h) => h >= hash);
    const ringIndex = index === -1 ? 0 : index;
    return this.ring.get(this.sortedHashes[ringIndex])!;
  }

  private hash(input: string): number {
    // a real implementation would use a stable hash function (e.g., MurmurHash)
    let h = 0;
    for (const char of input) h = (h * 31 + char.charCodeAt(0)) >>> 0;
    return h;
  }
}
```

**Virtual nodes** (multiple ring positions per real server) fix the uneven distribution that occurs with few servers — without them, one server could randomly end up owning a much larger slice of the ring than another.

This isn't just about load balancing — the same principle underlies sharding in Cassandra, DynamoDB, and distributed caches (memcached with client-side consistent hashing).

## Health Checks: active vs passive

The LB needs to know which backend instances are alive **before** sending them traffic.

```txt
Active health checks:
  The LB periodically sends a request itself (e.g., GET /health)
  The backend responds 200 OK if ready to take traffic
  If N checks fail in a row → the instance is removed from the pool

Passive health checks:
  The LB observes real traffic
  If the error/timeout rate exceeds a threshold → the instance is temporarily removed
```

Senior nuance: the `/health` endpoint shouldn't be a trivial "always 200" — but it also shouldn't check **everything**. If it checks the DB connection and the DB gets temporarily overloaded, the health check might start pulling *all* instances out of the pool simultaneously — this is **cascading failure**, where a mechanism meant to protect the system actually brings it down. A good health check verifies exactly what an instance needs to serve requests, and nothing more.

## Sticky Sessions — when you actually need them

Sticky sessions (pinning a user to a specific server, usually via a cookie containing an instance ID) are almost always an anti-pattern under a stateless architecture (see [System Design Fundamentals]), but there are legitimate cases:

```txt
- WebSocket connections: the connection is physically held by one server,
  it can't be "switched" to another server without dropping it
- A per-process in-memory cache on a specific instance —
  but this needs explicit justification, Redis is usually better
```

If sticky sessions are used, you need to explicitly call out the consequences: if an instance goes down, all clients "stuck" to it lose their connection/state and must reconnect (for WebSocket, this means explicit client-side reconnect logic).

## CDN as "scaling at the network level"

A CDN (Content Delivery Network) is, in essence, a geographically distributed caching layer **in front of** your backend:

```txt
User (Berlin) → CDN edge (Frankfurt) → cache hit → response without hitting origin
User (Tokyo)  → CDN edge (Tokyo)     → cache miss → request to origin → cached
```

A CDN reduces load on the origin (static assets, images, video, sometimes entire HTML pages for SSG sites) and reduces latency through geographic proximity to the user. For a dynamic API, a CDN usually doesn't cache directly, but can be used for **edge compute** (auth checks, geo-routing, A/B tests before reaching the origin).

## Auto Scaling — not just "add a server when load is high"

```txt
Reactive scaling:
  metric (CPU > 70%, queue depth > 1000, p99 latency > 500ms)
  → scale-out (new instances)
  → cooldown period (e.g., 5 minutes — don't scale again
     until the new instances have "warmed up")

Predictive/scheduled scaling:
  known traffic patterns in advance (morning peak, Black Friday)
  → scale up BEFORE the peak, not in reaction to it
```

Senior nuances around auto scaling:

- **Cold start**: a new instance can take minutes to come up (especially if it needs to warm caches/DB connections) — reactive scaling "lags" during this window, and that's exactly when degradation happens. That's why predictable peaks (sales events) rely on scheduled scaling.
- **CPU isn't always the right signal** — for I/O-bound services (lots of waiting on DB/external API responses), CPU can stay low while the service is overloaded. More telling metrics: request queue depth, latency, active connection count.
- **DB connection limits** — if auto scaling adds app instances without limits, each one opens its own DB connection pool, and you can hit the DB's `max_connections` before app-server CPU becomes a bottleneck. This is a common practical "gotcha" that signals depth of understanding.

## Cache Layer as a scaling mechanism

```txt
Client → App Server → Redis (cache) → Database
                         ↑
                  cache hit: response in ~1ms, no DB round trip
                  cache miss: read from DB, then populate the cache
```

A cache isn't "speedup" — it's **offloading the DB**, which lets the same DB resources serve more requests. The details of caching strategies (cache-aside, write-through, TTL, invalidation) are covered separately in the caching topic — what matters here is that caching is one of the primary levers for horizontally scaling the system as a whole, not just a minor optimization.

## Common interview mistakes

- **Confusing L4 and L7 load balancing**, or not mentioning that L7 is needed for routing by URL/cookies/headers, while L4 is for fast, coarse transport-layer balancing.

- **Proposing `hash(key) % N` as "consistent hashing"** — not realizing that the reshuffling caused by changing N with that approach is exactly the problem consistent hashing solves.

- **Treating sticky sessions as "always bad"** — for WebSocket connections they're architecturally necessary (the connection is physically held by one instance); the point is knowing *when* they're needed, not rejecting the concept outright.

- **A health check that checks too much** — causing cascading failure, where a temporary issue in one dependency (the DB) pulls all instances out of the pool at once.

- **Auto scaling on CPU for I/O-bound services** — missing that a service can be overloaded (by latency/queue depth) while CPU stays low.

- **"A CDN solves the dynamic API problem"** — CDNs are effective for static and cacheable content; personalized/dynamic responses need a different approach (application-level caching, edge compute).

- **Ignoring DB connection limits when auto-scaling app servers** — a classic case where "scaling one layer" creates a bottleneck in another.
