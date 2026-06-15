# Chat System Design

## Requirements Clarification and scope

"Design a chat like WhatsApp/Slack" is too broad. A strong answer starts by narrowing the scope:

**Functional Requirements (for discussion, we pick 1:1 + small groups):**

```txt
- 1:1 messaging
- group chats (clarify: member limit — 10 people or 10,000,
  these are DIFFERENT architectural problems, see below)
- message history
- online/offline status, read receipts, typing indicator
- (clarify separately, "out of scope" for the first pass) voice/video,
  end-to-end encryption, files/media
```

**Non-Functional Requirements:**

```txt
- Message delivery latency: tens to hundreds of ms
- Messages must not be lost (durability) — a clear difference
  from a "like" or a presence status, which can be lost without disaster
- Support for millions of concurrent WebSocket connections
- Ordering: messages within a chat must arrive
  in a consistent order for all participants
```

The transport layer (WebSocket, the connection-pinning problem, Pub/Sub for cross-server delivery, presence via TTL) was already covered in [WebSockets and Realtime Systems] — here those mechanisms are taken as given, and the focus is on chat specifics: message storage, ordering, delivery, groups.

## Send Message Flow — the order of steps matters

```txt
User A → WebSocket → Chat Service
                          │
                          ▼
                 1. Persist to the DB (source of truth)
                          │
                          ▼
                 2. ACK to the sender ("delivered to server")
                          │
                          ▼
                 3. Attempt delivery to User B (if online)
                          │
                          ▼
                 4. If offline → a push notification via a queue
```

Why **persist strictly before ACK**, not the other way around: if you ACK first and then fail to write to the DB, the sender thinks the message was delivered, but it's lost forever. This is a direct application of "WebSocket is the transport, the DB is the source of truth" from the WebSocket topic. Any "optimization" that changes this order for latency's sake turns durability into "usually works."

## Message Ordering — why "just use a timestamp" doesn't work

The naive approach is to sort messages by `created_at`. The problem: under high load, multiple messages can get the **same timestamp** (especially if time is stored with millisecond precision and the DB ingests thousands of writes per second), and clocks across different servers drift slightly (clock skew).

```txt
Solution: a composite ordering key —

  (chat_id, sequence_number) — a monotonically increasing number
  WITHIN a specific chat, not global

  message_id = a snowflake-like ID:
    [timestamp][server_id][sequence] — ordered by creation time
    and globally unique without cross-server coordination
```

A Snowflake ID (Twitter/Discord's approach) is essentially the same principle as the Ticket Server from the URL Shortener topic: each server generates IDs locally from its own range/namespace, without a blocking round trip to a central DB per message, while the resulting IDs remain time-ordered.

## Storing messages: schema and partitioning

```sql
messages (
  id           BIGINT PRIMARY KEY,  -- snowflake ID, used for sorting
  chat_id      BIGINT NOT NULL,
  sender_id    BIGINT NOT NULL,
  content      TEXT,
  created_at   TIMESTAMP,
  INDEX (chat_id, id)  -- main read pattern: "messages of chat X, in order"
)
```

The main read pattern — "the last N messages of chat X" — is almost always a **range scan on the `(chat_id, id)` index**, which makes PostgreSQL/MySQL a perfectly reasonable choice even at large volumes, as long as the data is properly indexed.

**Partitioning by `chat_id`** (not by time) becomes necessary once message volume exceeds a single node's capacity — a direct application of hash-based sharding from [Database Scaling]: shard key = `chat_id` guarantees all messages of one chat (the main read pattern) stay in the same shard, avoiding cross-shard queries for the most common operation.

## Group chats: fan-out — the topic's central senior question

This is the difference between "just deliver a message to one person" and the real complexity of group chat.

### Fan-out on write (push model)

```txt
A user sends a message to a group of 500 people
  → the Chat Service creates 500 "delivery records"
    (or publishes to all 500 participants' Pub/Sub channels)
  → each participant gets a push immediately upon connection
```

```txt
Pros: reading history is a simple "my messages" query (with a
      per-user inbox model), fast unread delivery
Cons: ONE message in a 500-person group = 500 write/publish operations.
      For very large groups (10,000+ members, like Telegram's
      public channels), this becomes a write bottleneck.
```

### Fan-out on read (pull model)

```txt
The message is written ONCE to the group's shared timeline
  → each participant, on connect/request, reads
    "messages of group X since my last_read_id"
```

```txt
Pros: O(1) write regardless of group size
Cons: reads are more expensive (need to compute
      "what haven't I seen yet" per user, per request)
```

**The practical solution used by large systems**: a hybrid — fan-out on write for small groups (most chats, up to a few hundred members — the write cost is acceptable), fan-out on read for huge channels/broadcast groups (Telegram channels with millions of subscribers — "push to everyone on every message" is unthinkable here, so readers pull new messages from the shared channel themselves).

This directly parallels Read-Heavy vs Write-Heavy from [System Design Fundamentals]: a small group is effectively read-heavy from each participant's perspective (they read their inbox more than they write), while a huge broadcast channel is structurally closer to "one writer, millions of readers," where the push model doesn't scale.

## Read Receipts and Typing Indicators — different durability needs

```txt
Read Receipts (read/delivered):
  STORED in the DB — this is part of the conversation history,
  and the user expects the "read" status to persist
  across sessions.

  message_status (message_id, user_id, status, updated_at)
  status: sent | delivered | read

Typing Indicator ("typing..."):
  NOT stored in the DB — this is ephemeral state with a TTL of
  a few seconds. Sent as a WebSocket event directly between
  clients (via the same Pub/Sub mechanism as messages).
  If the event is "lost," the consequence is nil
  (the indicator just doesn't appear/disappear a second early).
```

This illustrates a general principle: **not everything in a realtime system needs the same delivery guarantees**. Applying "message" durability (persist-then-ack-then-deliver) to a typing indicator is unnecessary complexity; applying "fire and forget" to the message itself is data loss.

## Offline Delivery and Push Notifications

```txt
User B is offline when the message is sent
  → the message is saved to the DB (status: sent)
  → the Chat Service publishes to a Notification Queue
  → a Push Worker → APNs/FCM → a push notification to the device

On User B's next connection:
  → the client requests "messages for chats X, Y, Z since last_synced_id"
  → catches up on what was missed, marks delivered/read
```

The queue for push here is again an application of the [Message Queues] pattern: sending a push notification can be slow/unreliable (an external APNs/FCM service), and it shouldn't block the main message flow.

## Final architecture

```txt
Clients
  ↓ (WebSocket)
Load Balancer (L4, passes through Upgrade headers)
  ↓
WebSocket Gateway servers (stateless for HTTP, but hold
                            long-lived connections)
  ↓                                    ↑
Chat Service ──→ PostgreSQL/MySQL    Redis Pub/Sub
  (persist,         (messages,        (cross-server delivery,
   sequence IDs)     chat_members,     presence — see the WebSocket topic)
                      message_status)
  ↓
Notification Queue → Push Worker → APNs/FCM
```

## Common interview mistakes

- **Not discussing the persist → ack → deliver order** — the most common "depth" follow-up, and skipping it looks like not understanding why messages aren't lost on failures.

- **Sorting by `created_at` without discussing timestamp collisions and clock skew** — not proposing a snowflake ID or composite `(chat_id, sequence)`.

- **Not distinguishing fan-out on write from fan-out on read for groups** — this is the central question for "what if the group has 100,000 members," and "just push to everyone" doesn't scale.

- **Storing typing indicators in the DB** — or, conversely, trying to make messages "fire and forget" like presence — confusing the durability requirements of different data types.

- **Partitioning messages by time instead of by `chat_id`** — this breaks the main read pattern, "history of a specific chat," requiring cross-shard queries for the most common operation.

- **Ignoring cross-server delivery** — designing as if all WebSocket connections live on one server, without Redis Pub/Sub/Kafka (see [WebSockets and Realtime Systems]).

- **Sending push notifications synchronously in the main flow** — blocking the response to the user on an external APNs/FCM API call.
