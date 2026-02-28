# Hackathon Monorepo (SQLite + sqlite-vec)

## Prerequisites

- [mise](https://mise.jdx.dev/) for environment management
- [uv](https://docs.astral.sh/uv/) for Python (optional)

## Quick Start

```bash
mise install          # installs node, pnpm, python
pnpm install          # installs all JS dependencies
pnpm dev              # runs web + server in parallel
```

## Apps

| App | Command | Description |
|-----|---------|-------------|
| web | `pnpm dev:web` | React + Vite web app |
| mobile | `pnpm dev:mobile` | Expo React Native app |
| server-cli | `pnpm dev:server` | Hono local API server |

## Packages

| Package | Description |
|---------|-------------|
| `@hackathon/shared` | Shared types and utilities |
| `@hackathon/db` | SQLite + sqlite-vec + Drizzle ORM |
| `@hackathon/ai` | AWS Bedrock LLM integration |

## Database

Single SQLite database handles both relational data (via Drizzle) and
vector embeddings (via sqlite-vec). No separate vector DB needed.

```bash
cd packages/db
pnpm generate   # generate migrations
pnpm migrate    # apply migrations
pnpm studio     # open Drizzle Studio
```
