# Scalability and Load Balancing

## Scaling: a quick recap of vertical vs horizontal

Horizontal scaling is **impossible without a load balancer**. Without one you just have N independent servers. The client then has to pick between them somehow, or each server gets its own DNS (domain name system) address. That doesn't scale and gives no fault tolerance. (The vertical-versus-horizontal distinction itself is covered in the System Design Fundamentals article.)

So "add more servers" is only half an answer to a scaling question. The other half is **how traffic is distributed across them** and **what happens when one of them goes down**. That is the subject of load balancing.

## L4 vs L7 Load Balancer — decisions at different layers

This is one of the most important distinctions, and it often gets missed. An **L4 (transport layer) load balancer** works at the level of TCP (transmission control protocol) and UDP (user datagram protocol). It sees only IP (internet protocol) addresses and ports, and never looks inside the request.

```txt
Routing decisions are based on:
  source IP, destination IP, source port, destination port

Pros: very fast (no payload parsing), low overhead
Limits: can't route by URL, headers, or cookies
```

An **L7 (application layer) load balancer** works at the level of HTTP. It sees the URL, headers, cookies and request body.

```txt
Routing decisions are based on:
  path (/api/* → backend A, /static/* → CDN/backend B)
  headers (Authorization, User-Agent)
  cookies (sticky sessions)

Pros: flexible routing, A/B tests, canary deploys
Cons: higher latency (needs to terminate TLS
      and parse HTTP), more compute-expensive
```

Senior nuance: an L7 load balancer usually **terminates TLS** (transport layer security), turning HTTPS (HTTP protected by encryption) into plain HTTP inside the network. That is how it gets access to the request content. The cost is a decrypt and encrypt step on every request, and it has to be accounted for in the latency budget.

Real systems often combine both layers. L4 sits at the edge for coarse distribution across regions and availability zones — for example AWS (Amazon Web Services) NLB, the network load balancer. L7 sits inside for routing between services: AWS ALB (application load balancer), Nginx, Envoy.

## Load balancing algorithms

| Algorithm | How it works | When it's good | When it's bad |
|---|---|---|---|
| **Round Robin** | In rotation: A → B → C → A → ... | Servers of equal capacity, requests of roughly equal "weight" | Doesn't account for current load — a slow server gets as many requests as a fast one |
| **Weighted Round Robin** | Like Round Robin, but with weights (a more powerful server gets more requests) | Servers of different capacity (e.g., a gradual canary rollout) | Weights are static, don't react to real-time load |
| **Least Connections** | The request goes to the server with the fewest active connections | Requests vary a lot in processing time | The balancer has to track connection state — slightly more expensive |
| **IP Hash / Consistent Hashing** | Routing is a function of a hash of the client IP (or another key) | Need "stickiness" without cookies, or cache-aware routing | With a plain hash (`hash % N`), adding or removing servers reshuffles **almost all** traffic |

### Consistent Hashing — why it's its own big topic

A plain `hash(key) % N` breaks when N changes. If you have 4 servers and add a fifth, `hash % N` changes for **most** keys, and they "move" to a different server. For a cache that means a mass cache miss; for a sharded database, a massive data rebalance.

**Consistent hashing** solves this by placing both servers and keys on the same hash "ring". Adding or removing a server then moves only `~1/N` of the keys, not the whole set:

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

**Virtual nodes** — multiple ring positions per real server — fix the uneven distribution that occurs when there are few servers. Without them, one server could randomly end up owning a much larger slice of the ring than another.

This isn't just about load balancing. The same principle underlies sharding in Cassandra and DynamoDB, and distributed caches (memcached with client-side consistent hashing).

## Health Checks: active vs passive

The load balancer needs to know which backend instances are alive **before** sending them traffic.

```txt
Active health checks:
  The balancer periodically sends a request itself
  (e.g., GET /health)
  The backend responds 200 OK if ready to take traffic
  If N checks fail in a row → the instance leaves the pool

Passive health checks:
  The balancer observes real traffic
  If the error or timeout rate crosses a threshold
  → the instance is temporarily removed
```

Senior nuance: the `/health` endpoint shouldn't be a trivial "always 200". But it also shouldn't check **everything**.

Suppose it checks the database connection, and the database gets temporarily overloaded. The health check can then start pulling *all* instances out of the pool at once. This is **cascading failure**: a mechanism meant to protect the system brings it down instead. A good health check verifies exactly what an instance needs in order to serve requests, and nothing more.

## Sticky Sessions — when you actually need them

Sticky sessions pin a user to a specific server, usually via a cookie holding an instance id. Under a stateless architecture they are almost always an anti-pattern, as the System Design Fundamentals article explains. But there are legitimate cases:

```txt
- WebSocket connections: the connection is physically held
  by one server, and it can't be "switched" to another
  server without dropping it
- A per-process in-memory cache on a specific instance —
  but this needs explicit justification,
  Redis is usually better
```

If sticky sessions are used, you need to call out the consequences explicitly. When an instance goes down, every client stuck to it loses its connection and state, and has to reconnect. For WebSocket that means explicit client-side reconnect logic.

## CDN as "scaling at the network level"

A CDN (content delivery network) is, in essence, a geographically distributed caching layer **in front of** your backend:

```txt
User (Berlin) → CDN edge (Frankfurt) → cache hit
  → response without hitting origin
User (Tokyo)  → CDN edge (Tokyo) → cache miss
  → request to origin → cached
```

A CDN reduces load on the origin: static assets, images, video, and sometimes entire HTML pages for static site generation (SSG) sites. It also reduces latency through geographic proximity to the user.

For a dynamic API a CDN usually doesn't cache directly. But it can be used for **edge compute**: auth checks, geo-routing, and A/B tests before the request reaches the origin.

## Auto Scaling — not just "add a server when load is high"

```txt
Reactive scaling:
  metric (CPU > 70%, queue depth > 1000, p99 latency > 500ms)
  → scale-out (new instances)
  → cooldown period (e.g., 5 minutes — don't scale again
     until the new instances have "warmed up")

Predictive/scheduled scaling:
  known traffic patterns in advance (morning peak, Black Friday)
  → scale up ahead of the peak, not in reaction to it
```

Senior nuances around auto scaling:

- **Cold start**: a new instance can take minutes to come up, especially if it has to warm caches and database connections. Reactive scaling lags during that window, and that is exactly when degradation happens. This is why predictable peaks such as sales events rely on scheduled scaling.
- **Processor load isn't always the right signal.** For I/O-bound services — lots of waiting on database or external API responses — the CPU (processor) can stay idle while the service is overloaded. More telling metrics: request queue depth, latency, active connection count.
- **Database connection limits.** If auto scaling adds app instances without limits, each one opens its own database connection pool. You can hit the database's `max_connections` before app-server CPU becomes a bottleneck. This is a common practical trap, and mentioning it signals depth of understanding.

## Cache Layer as a scaling mechanism

```txt
Client → App Server → Redis (cache) → Database
                         ↑
      cache hit: response in ~1ms, no database round trip
      cache miss: read from the database,
                  then populate the cache
```

A cache isn't "speedup". It is **offloading the database**, which lets the same database resources serve more requests.

The details of caching strategies — cache-aside, write-through, TTL (time to live), invalidation — are covered in the caching article. What matters here is that caching is one of the primary levers for scaling the system as a whole, not a minor optimization.

## Common interview mistakes

- **Confusing L4 and L7 load balancing**, or not naming the distinction at all. L7 is needed for routing by URL, cookies and headers; L4 is for fast, coarse transport-layer balancing.

- **Proposing `hash(key) % N` as "consistent hashing".** With that approach, changing N reshuffles the keys — and that reshuffling is exactly the problem consistent hashing solves.

- **Treating sticky sessions as "always bad".** For WebSocket connections they are architecturally necessary, because the connection is physically held by one instance. The point is knowing *when* they're needed, not rejecting the concept outright.

- **A health check that checks too much**, causing cascading failure. A temporary issue in one dependency — the database — pulls all instances out of the pool at once.

- **Auto scaling on CPU for I/O-bound services** — missing that a service can be overloaded, by latency or queue depth, while the processor stays idle.

- **"A CDN solves the dynamic API problem".** CDNs are effective for static and cacheable content. Personalized or dynamic responses need a different approach: application-level caching or edge compute.

- **Ignoring database connection limits when auto-scaling app servers** — a classic case where "scaling one layer" creates a bottleneck in another.
