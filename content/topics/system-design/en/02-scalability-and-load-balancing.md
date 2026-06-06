# Scalability and Load Balancing

## Scaling

The most frequent System Design topic.

---

# Vertical Scaling

Scale Up.

---

Increase the server's resources.

---

```txt
8 CPU
 ↓
32 CPU
```

---

# Pros

```txt
simplicity
```

---

# Cons

```txt
there is a limit
```

---

# Horizontal Scaling

Scale Out.

---

Add new servers.

---

```txt
Server A

Server B

Server C
```

---

# Load Balancer

A very popular question.

---

Distributes requests.

---

Diagram:

```txt
Users
 ↓
Load Balancer
 ↓
Servers
```

---

# Round Robin

The simplest algorithm.

---

```txt
A
B
C
A
B
C
```

---

# Least Connections

Send the request to the server
with the fewest active connections.

---

# Health Checks

A very important topic.

---

The Load Balancer regularly checks:

```txt
whether the server is alive
```

---

If not:

```txt
traffic is not sent there
```

---

# Sticky Sessions

Interviewers love asking about this.

---

The user always lands
on the same server.

---

Problem:

```txt
hinders scaling
```

---

# Stateless Is Better

Therefore people more often use:

```txt
JWT

Redis Sessions
```

---

# CDN

The next level of scaling.

---

Diagram:

```txt
User
 ↓
CDN
 ↓
Origin
```

---

Reduces load
on the backend.

---

# Cache Layer

Another way to scale.

---

```txt
Client
 ↓
Redis
 ↓
Database
```

---

Fewer requests to the DB.

---

# Auto Scaling

Interviewers love asking about this.

---

For example:

```txt
CPU > 70%
```

---

We create:

```txt
a new server
```

---

Automatically.

---

# Common Question

When does vertical scaling stop working?

Answer:

When the server hits the physical limits of CPU, RAM, or disk.

---

# Common Question

Why is a Load Balancer needed?

Answer:

To distribute load and improve fault tolerance.

---

# Common Question

Why are Stateless services easier to scale?

Answer:

Because any request can be handled by any server.

---

# Interview Answer

Scaling can be vertical or horizontal. In modern systems horizontal scaling through a Load Balancer and multiple stateless application instances is more commonly used.
