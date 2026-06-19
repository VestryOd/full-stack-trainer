# Docker Essentials

## What Docker is (and what it is not)

**Docker** is a platform for building, shipping, and running applications in isolated, reproducible environments called **containers**. The core problem it solves: "it works on my machine" — the application behaves differently in development, CI, staging, and production because each environment has different OS versions, runtimes, installed libraries, and system configuration.

Docker is **not** a virtual machine (VM). This distinction matters:

```txt
Virtual Machine (VM):
  ┌──────────────────────────────────────────────┐
  │              Host OS (Linux/Windows)          │
  │  ┌──────────────────────────────────────────┐│
  │  │        Hypervisor (VMware, VirtualBox)    ││
  │  │  ┌──────────────┐  ┌──────────────┐      ││
  │  │  │  Guest OS    │  │  Guest OS    │      ││
  │  │  │  (full Linux)│  │  (full Linux)│      ││
  │  │  │  App + libs  │  │  App + libs  │      ││
  │  │  └──────────────┘  └──────────────┘      ││
  │  └──────────────────────────────────────────┘│
  └──────────────────────────────────────────────┘
  Each VM has its own full OS kernel — heavy, slow to start (minutes)

Docker Container:
  ┌──────────────────────────────────────────────┐
  │              Host OS (Linux kernel)           │
  │  ┌───────────────────────────────────────┐   │
  │  │     Docker Engine (runtime daemon)     │   │
  │  │  ┌──────────────┐ ┌──────────────┐   │   │
  │  │  │  Container A  │ │  Container B  │   │   │
  │  │  │  app + libs   │ │  app + libs   │   │   │
  │  │  │  (no OS kernel│ │  (no OS kernel│   │   │
  │  │  │  of its own)  │ │  of its own)  │   │   │
  │  │  └──────────────┘ └──────────────┘   │   │
  │  └───────────────────────────────────────┘   │
  └──────────────────────────────────────────────┘
  Containers share the host OS kernel — lightweight, start in milliseconds
```

Containers use Linux kernel features — **namespaces** (process isolation: each container has its own process tree, network stack, filesystem view) and **cgroups** (control groups: limits on CPU and memory usage) — to create the illusion of a separate machine without the overhead of a full OS.

## Image vs Container

This is the most fundamental distinction in Docker:

```txt
Image      = a blueprint — a read-only, layered snapshot of a filesystem
             with everything the application needs to run
             (runtime, dependencies, config files, compiled code)

Container  = a running instance of an image
             = image + a writable layer on top + an isolated process
```

The analogy: an image is a class definition in code; a container is an object instantiated from that class. You can run many containers from the same image simultaneously.

```bash
# Build an image from a Dockerfile (covered below)
docker build -t my-app:1.0 .

# Run a container from that image
docker run my-app:1.0

# Run multiple containers from the same image
docker run -d --name app-1 my-app:1.0
docker run -d --name app-2 my-app:1.0
docker run -d --name app-3 my-app:1.0

# List running containers
docker ps

# List all images
docker images
```

Key flags for `docker run`:

```bash
docker run \
  -d \                          # detached: run in the background
  -p 3000:3000 \                # port mapping: host:container
  -e NODE_ENV=production \      # environment variable
  -v ./data:/app/data \         # volume mount: host-path:container-path
  --name my-container \         # give the container a name
  --rm \                        # remove the container when it stops
  my-app:1.0
```

## Dockerfile

A **Dockerfile** is a text file containing a sequence of instructions that Docker executes to build an image. Each instruction creates a new **layer** in the image (more on layers below).

```dockerfile
# syntax=docker/dockerfile:1
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --only=production

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["node", "dist/server.js"]
```

### `FROM` — the base image

```dockerfile
FROM node:20-alpine
```

Every Dockerfile starts with `FROM`, which specifies the **base image** — the starting point your image builds on top of. Common choices for Node.js:

```txt
node:20          — full Debian-based Node.js image (~350 MB)
node:20-alpine   — Alpine Linux-based Node.js image (~50 MB)
                   smaller and faster to pull, but uses musl libc instead of glibc
                   (can cause issues with native addons that assume glibc)
node:20-slim     — Debian-based but with many tools removed (~80 MB)
                   a middle ground between full and alpine
```

`FROM scratch` means starting from an empty image — used for minimal single-binary applications (Go binaries, etc.).

### `WORKDIR` — set the working directory

```dockerfile
WORKDIR /app
```

Sets the working directory inside the container for all subsequent instructions (`RUN`, `COPY`, `CMD`, etc.). Creates the directory if it does not exist. Equivalent to `mkdir -p /app && cd /app`.

### `COPY` — copy files from host to image

```dockerfile
COPY package.json package-lock.json ./
COPY . .
```

`COPY <src> <dest>` copies files from the **build context** (the directory passed to `docker build`) into the image filesystem. The `./` destination means the current `WORKDIR`.

`COPY . .` copies everything from the build context into `WORKDIR` — but only what is not excluded by `.dockerignore` (covered below).

`ADD` is similar to `COPY` but also supports URLs and automatically unpacks `.tar` archives. **Prefer `COPY`** — it is explicit and predictable. Use `ADD` only when you specifically need the auto-extract feature.

### `RUN` — execute a command during build

```dockerfile
RUN npm ci --only=production
```

`RUN` executes a shell command **at build time** and saves the result as a new image layer. Used for installing dependencies, compiling, generating files, etc.

**Best practice — chain commands to reduce layers:**

```dockerfile
# ❌ Creates 3 separate layers — unnecessary overhead
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# ✅ Creates 1 layer — combines related commands
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*
```

The final `rm -rf /var/lib/apt/lists/*` removes the package manager cache — if it were in a separate `RUN`, the cache would still be baked into the earlier layer, making the image larger.

### `EXPOSE` — document a port

```dockerfile
EXPOSE 3000
```

`EXPOSE` is **documentation only** — it does not actually publish the port. It tells the person reading the Dockerfile which port the containerized application listens on. The actual port mapping happens at `docker run` time with `-p`.

### `ENV` — set environment variables

```dockerfile
ENV NODE_ENV=production
ENV PORT=3000
```

Sets environment variables in the image. Unlike `-e` at runtime (which only applies to that container run), `ENV` is baked into the image and affects all containers created from it.

## `CMD` vs `ENTRYPOINT` — the critical difference

This is one of the most commonly misunderstood parts of Dockerfile syntax. Both define what runs when a container starts — but they play different roles.

### `CMD` — default command, easily overridable

```dockerfile
CMD ["node", "dist/server.js"]
```

`CMD` sets the **default command** to run when the container starts. It is easily replaced at runtime — anything you pass after the image name in `docker run` replaces `CMD` entirely:

```bash
docker run my-app:1.0                           # runs: node dist/server.js
docker run my-app:1.0 node dist/migrate.js      # CMD replaced — runs: node dist/migrate.js
docker run my-app:1.0 /bin/sh                   # CMD replaced — opens a shell
```

### `ENTRYPOINT` — fixed executable, arguments are appended

```dockerfile
ENTRYPOINT ["node"]
CMD ["dist/server.js"]
```

`ENTRYPOINT` sets a **fixed executable** that always runs. Arguments passed in `docker run` are **appended** to the `ENTRYPOINT`, not replacing it:

```bash
docker run my-app:1.0                    # runs: node dist/server.js
docker run my-app:1.0 dist/migrate.js   # runs: node dist/migrate.js
                                          # (argument appended to ENTRYPOINT)
```

To replace `ENTRYPOINT` at runtime, you need `--entrypoint`:

```bash
docker run --entrypoint /bin/sh my-app:1.0   # opens a shell
```

### Practical combination pattern

The most common pattern for application images:

```dockerfile
# ENTRYPOINT = the fixed executable
# CMD        = the default argument (can be overridden easily)

ENTRYPOINT ["node"]
CMD ["dist/server.js"]       # default: start the server

# Then in CI or scripts:
# docker run my-app:1.0 dist/migrate.js   → runs migration
# docker run my-app:1.0                   → starts the server
```

### Exec form vs shell form

Both `CMD` and `ENTRYPOINT` have two syntaxes:

```dockerfile
# Exec form (JSON array) — PREFERRED
CMD ["node", "dist/server.js"]

# Shell form (string) — AVOID for CMD/ENTRYPOINT
CMD node dist/server.js
```

**Always use exec form for `CMD` and `ENTRYPOINT`.** Shell form wraps the command in `/bin/sh -c "..."`, which means your application runs as a child process of `sh`. This causes two problems:
1. The process does not receive OS signals (`SIGTERM`) directly — `sh` does, and it may not forward them. This breaks graceful shutdown.
2. The PID 1 problem: in a container, PID 1 has special responsibilities (reaping zombie processes). If your app runs as a child of `sh`, `sh` is PID 1 — and `sh` does not handle zombie reaping properly.

## Image layers and build cache

Every `RUN`, `COPY`, `ADD`, and `FROM` instruction in a Dockerfile creates a new **layer** in the image. Layers are stacked — each layer records only the diff (changes) relative to the layer beneath it.

```txt
Image "my-app:1.0"
  Layer 5: COPY . .  +  RUN npm run build        ← changes often
  Layer 4: RUN npm ci --only=production           ← changes when package-lock.json changes
  Layer 3: COPY package.json package-lock.json ./ ← changes when deps change
  Layer 2: WORKDIR /app                           ← stable
  Layer 1: FROM node:20-alpine                    ← stable
```

**Build cache** — Docker caches each layer. When you rebuild the image, Docker reuses cached layers from the top down, stopping at the first layer that changed (or whose input changed):

```txt
If you change a source file (src/server.ts):
  Layer 1 (FROM)   — cache HIT (unchanged)
  Layer 2 (WORKDIR)— cache HIT
  Layer 3 (COPY package.json) — cache HIT (package.json didn't change)
  Layer 4 (RUN npm ci) — cache HIT (package-lock.json didn't change)
  Layer 5 (COPY . .) — cache MISS (source files changed) → rebuild from here
```

This is why **order matters in a Dockerfile**: put the things that change least frequently at the top, and the things that change most frequently at the bottom.

```dockerfile
# ✅ Correct order — dependency installation is cached unless package-lock.json changes
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./    # copy only the lockfile first
RUN npm ci                                 # cached unless lockfile changes
COPY . .                                   # source files (change often) — copy after
RUN npm run build

# ❌ Wrong order — npm ci re-runs on every source file change
FROM node:20-alpine
WORKDIR /app
COPY . .          # source files and package.json copied together
RUN npm ci        # cache busted whenever any source file changes
RUN npm run build
```

## Multi-stage builds

A **multi-stage build** uses multiple `FROM` instructions in a single Dockerfile. Each `FROM` starts a new build stage. You can copy files from one stage into another — leaving the tools used to build behind.

This is the primary technique for keeping production images small:

```dockerfile
# syntax=docker/dockerfile:1

# ── Stage 1: builder ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci                              # installs ALL deps (incl. devDependencies)

COPY . .
RUN npm run build                       # produces dist/

# ── Stage 2: production image ─────────────────────────────────────
FROM node:20-alpine AS production

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev                   # installs ONLY production dependencies

COPY --from=builder /app/dist ./dist    # copy only the compiled output from builder

EXPOSE 3000
CMD ["node", "dist/server.js"]
```

What gets left behind in the `builder` stage (not in the final image):
- TypeScript compiler (`tsc`)
- All dev dependencies (test frameworks, build tools)
- Source TypeScript files
- Build tools (webpack, vite, esbuild)

The final image contains only: Node.js runtime + production npm packages + compiled JS output.

```txt
Without multi-stage:    ~400 MB (all tools + devDeps + source)
With multi-stage:        ~80 MB (runtime + prodDeps + compiled output only)
```

Multi-stage builds can also be used for running tests in CI without polluting the production image:

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS test
COPY . .
RUN npm test          # if this fails, the build fails — tests run as part of the build

FROM deps AS builder
COPY . .
RUN npm run build

FROM node:20-alpine AS production
# ... (same as above)
```

## `.dockerignore`

`.dockerignore` works exactly like `.gitignore` but for the Docker build context. It tells Docker which files to exclude from the build context (the directory sent to the Docker daemon when `docker build` is run).

```txt
# .dockerignore
node_modules/          # never copy node_modules — always install fresh inside the image
.git/                  # git history has no place in an image
.env                   # NEVER include .env — it may contain secrets
dist/                  # will be rebuilt inside the image
coverage/
*.log
.DS_Store
README.md
```

Why it matters:
1. **Speed**: without `.dockerignore`, the entire `node_modules/` directory (potentially hundreds of MB) is sent to the Docker daemon on every `docker build`. This is slow and wastes network bandwidth in CI.
2. **Security**: `.env` files, local credentials, and private keys should never end up in a Docker image. Even if a `COPY . .` is followed by `RUN rm .env`, the `.env` file exists in the intermediate layer and can be extracted from the image with `docker history`.
3. **Correctness**: `COPY . .` without `.dockerignore` copies `node_modules/` from the host into the image, which may have been installed for a different OS (macOS native addons won't run on Linux).

## Non-root user and rootless containers

By default, processes inside a Docker container run as `root` (UID 0). This is a security risk: if an attacker exploits a vulnerability in your application and escapes the container, they do so as root — giving them maximum privileges on the host.

**Non-root user** means explicitly creating a user inside the container and switching to it:

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist

# Create a non-root user and group
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Change ownership of the app directory to the new user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

EXPOSE 3000
CMD ["node", "dist/server.js"]
```

The `node:20-alpine` base image already includes a `node` user (UID 1000). You can simply use it:

```dockerfile
# Simpler approach using the built-in node user
FROM node:20-alpine
WORKDIR /app
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --omit=dev
COPY --chown=node:node --from=builder /app/dist ./dist
USER node                   # switch to the built-in node user
CMD ["node", "dist/server.js"]
```

**Rootless containers** is a broader concept: running the entire Docker daemon itself as a non-root user on the host — so even if a container escapes, it escapes into the user space of the daemon's unprivileged user, not into root. This is a separate configuration of the Docker installation, not the Dockerfile.

```txt
In practice for a fullstack developer:
  → Add USER <non-root> to all production Dockerfiles
  → Use --chown in COPY to set correct file ownership
  → Do not use --privileged in docker run (grants full host access)
  → Do not mount /var/run/docker.sock unless absolutely necessary
     (access to the Docker socket = root-equivalent access to the host)
```

## Docker Compose basics

**Docker Compose** is a tool for defining and running multi-container applications. Instead of running multiple `docker run` commands with dozens of flags, you describe the entire application stack in a `docker-compose.yml` file and start it with one command.

```yaml
# docker-compose.yml
version: '3.9'

services:
  app:
    build: .                          # build image from Dockerfile in current dir
    ports:
      - '3000:3000'
    environment:
      NODE_ENV: development
      DATABASE_URL: postgres://postgres:password@db:5432/myapp
    depends_on:
      db:
        condition: service_healthy    # wait until db passes its health check
    volumes:
      - ./src:/app/src               # mount source for hot-reload in development

  db:
    image: postgres:16-alpine         # use official image, no build needed
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: myapp
    volumes:
      - postgres-data:/var/lib/postgresql/data   # named volume: persists between restarts
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U postgres']
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - '6379:6379'

volumes:
  postgres-data:     # declare named volumes here
```

```bash
# Start all services (build images if needed)
docker compose up --build

# Start in detached mode (background)
docker compose up -d

# Stop all services and remove containers
docker compose down

# Stop and also remove volumes (WARNING: destroys db data)
docker compose down -v

# View logs
docker compose logs -f app

# Run a one-off command in a service
docker compose exec app sh
docker compose run --rm app node dist/migrate.js
```

Key Compose concepts:

```txt
services   → each key is a named container with its config
build      → path to Dockerfile or a build config object
image      → use a pre-built image instead of building
ports      → host:container port mapping
environment→ env vars passed to the container
volumes    → mount host paths or named volumes
depends_on → define start-order dependencies between services
networks   → by default, Compose creates one network and all services join it,
             so "db" in DATABASE_URL resolves to the db service's container IP
```

### Senior nuance: `depends_on` does not mean "ready"

`depends_on: db` only waits for the db *container to start* — not for PostgreSQL *inside the container* to be ready to accept connections. Your app may try to connect before the database is listening.

Solutions:
- Use `condition: service_healthy` with a `healthcheck` (shown above)
- Write retry logic in the application startup code
- Use a wait script (`wait-for-it.sh` or similar)

## Complete production Dockerfile example

```dockerfile
# syntax=docker/dockerfile:1

# ── Stage 1: Install dependencies ────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── Stage 2: Build ───────────────────────────────────────────────
FROM deps AS builder
COPY . .
RUN npm run build

# ── Stage 3: Production image ────────────────────────────────────
FROM node:20-alpine AS production

# Set production environment
ENV NODE_ENV=production

WORKDIR /app

# Install only production dependencies
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && \
    npm cache clean --force        # remove npm cache to reduce layer size

# Copy compiled output from builder
COPY --from=builder /app/dist ./dist

# Use the built-in non-root node user
RUN chown -R node:node /app
USER node

EXPOSE 3000

# Exec form — ensures SIGTERM is delivered directly to the node process
CMD ["node", "dist/server.js"]
```

## Common interview traps

- **"Image and container are the same thing"** — an image is a read-only blueprint; a container is a running instance of that image with a writable layer. Many containers can run from the same image simultaneously.

- **Using shell form for `CMD`** — `CMD node server.js` wraps the command in `/bin/sh -c`, making `sh` the process that receives `SIGTERM` during `docker stop`. Node never sees the signal and is killed hard after the grace period. Always use exec form: `CMD ["node", "server.js"]`.

- **Not understanding the difference between `CMD` and `ENTRYPOINT`** — a very common interview question. `CMD` provides defaults that are *replaced* when you pass arguments to `docker run`; `ENTRYPOINT` is the fixed executable that *receives* those arguments. They are designed to work together.

- **Copying `node_modules` into the image** — if `.dockerignore` doesn't exclude `node_modules/`, `COPY . .` copies them from the build machine into the image. macOS-compiled native addons will crash on Linux. Always install fresh inside the container.

- **Not using multi-stage builds for production images** — a production image with TypeScript compiler, test frameworks, and source `.ts` files included is a red flag in an interview. Multi-stage builds are the expected practice.

- **Putting secrets in `ENV` in a Dockerfile** — `ENV DATABASE_URL=postgres://admin:secret@...` bakes the secret into every image layer permanently. Even if you later overwrite it with a `RUN` command, it is recoverable from earlier layers with `docker history`. Secrets must be passed at runtime (`docker run -e`) or via a secrets manager, never baked into the image.

- **Assuming `depends_on` means the service is ready** — `depends_on` only waits for the container process to start, not for the service inside to be accepting connections. PostgreSQL, Redis, or any other service needs a health check for `condition: service_healthy` to work correctly.

- **Running production containers as root** — the absence of `USER` in a Dockerfile means the process runs as root inside the container. An interviewer who knows Docker will notice this immediately. Always add a `USER` instruction for production images.
