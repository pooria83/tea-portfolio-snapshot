# Development Setup

## Prerequisites

- **Node.js** >= 24.x (CI pins Node 24 via `NODE_VERSION`, Docker uses `node:24-slim`; there is no `engines` field in `package.json`, so the version is by convention)
- **npm** >= 10.x
- **Docker** + **Docker Compose** (optional, for containerized development)
- **Backend API** running (local or remote) — see [product-graph-api](https://github.com/TEA-assist/product-graph-api)

## Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/TEA-assist/product-graph-web-ui.git
cd product-graph-web-ui

# 2. Install dependencies
npm ci   # matches CI and Docker; use npm install only when you intentionally changed deps

# 3. Copy environment file and configure
cp .env.example .env
# Edit .env with your backend URL, port, and Google client ID (see below)

# 4. Start the dev server
npm run dev
```

The app starts at `http://localhost:8001` (`PORT` from `.env`, default in `.env.example`).

> **Google client ID**: the code requires `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (login page + profile Google linking), but `.env.example` does not include it — add it to `.env` manually. In CI/Docker builds it is injected as a build argument from the `NEXT_PUBLIC_GOOGLE_CLIENT_ID` secret.

### How `npm run dev` actually works

```bash
NODE_EXTRA_CA_CERTS=$(pwd)/certs/cloudflare-origin-ca.pem dotenv -e .env -- next dev --turbopack
```

- **dotenv-cli** loads `.env` before Next.js starts, so the server port comes from `PORT` in `.env` (not a CLI flag).
- **Turbopack** is always enabled.
- **`certs/cloudflare-origin-ca.pem`** is a Cloudflare Origin CA certificate passed via `NODE_EXTRA_CA_CERTS`, so Node trusts the dev TLS chain when the app is reached through `portfolio.example.invalid` / `portfolio.example.invalid` (the allowed dev origins in `next.config.ts`).

## Available Scripts

| Script          | Command                                                        | Description                           |
| --------------- | -------------------------------------------------------------- | ------------------------------------- |
| `dev`           | `NODE_EXTRA_CA_CERTS=… dotenv -e .env -- next dev --turbopack` | Start dev server (port from `.env`)   |
| `build`         | `next build`                                                   | Production build                      |
| `build:analyze` | `ANALYZE=true next build`                                      | Production build with bundle analyzer |
| `start`         | `next start`                                                   | Start production server               |
| `lint`          | `eslint`                                                       | Run ESLint                            |
| `lint:fix`      | `eslint --fix`                                                 | Fix auto-fixable lint issues          |
| `typecheck`     | `tsc --noEmit`                                                 | TypeScript type checking              |
| `format`        | `prettier --write "src/**/*.{ts,tsx,json,css}"`                | Format source files with Prettier     |
| `format:check`  | `prettier --check "src/**/*.{ts,tsx,json,css}"`                | Check formatting of source files      |
| `test`          | `vitest run`                                                   | Run unit tests                        |
| `test:watch`    | `vitest`                                                       | Run unit tests in watch mode          |
| `test:coverage` | `vitest run --coverage`                                        | Run unit tests with coverage report   |
| `test:e2e`      | `playwright test`                                              | Run Playwright e2e tests              |
| `prepare`       | `husky`                                                        | Install git hooks on `npm install/ci` |

> **Lint/format scope**: `lint`/`lint:fix` are plain ESLint invocations (`next lint` is gone in Next.js 16). Prettier only touches the `src/**/*.{ts,tsx,json,css}` glob — root configs, `messages/*.json`, and `docs/` are excluded from formatting.

## Docker Compose (Development)

```bash
# Start with hot-reload (default: dev target)
docker compose up

# Start with custom port
PORT=3000 docker compose up

# Rebuild
docker compose build --no-cache
```

The `docker-compose.yml` mounts `src/`, `public/`, and `messages/` as volumes for hot reload inside the container.

## Git Hooks

[husky](https://typicode.github.io/husky/) is installed via the `prepare` script and configured with two hooks.

### Pre-commit (`.husky/pre-commit`)

Five stages, all of which must pass:

1. `npx lint-staged` — ESLint + Prettier on staged files
2. `npm run lint` — full ESLint pass
3. `npm run typecheck` — `tsc --noEmit`
4. `npm run format:check` — Prettier check
5. `npm test` — all unit tests

### Pre-push (`.husky/pre-push`)

A guard for pushes to `main`:

- Blocks force-pushes (non-fast-forward) and branch deletion of `main`
- Re-runs the full quality gate (`lint` → `format:check` → `typecheck` → `test`) before any `main` push leaves the machine

> [`git-setup.sh`](../git-setup.sh) is a one-time (idempotent) setup script that installs the guard: it runs `npm install`, makes `.husky/pre-push` executable, and verifies `core.hooksPath` points at `.husky/_`.

> **Policy**: No one — human or AI — may bypass these hooks. All commits must pass all five pre-commit checks.

## IDE Setup

### VS Code (Recommended)

Install the following extensions:

- **ESLint** — in-editor linting
- **Prettier** — format on save
- **Tailwind CSS IntelliSense** — class autocompletion
- **i18n Ally** — translation key autocompletion
- **GitLens** — git history/blame

Add to `.vscode/settings.json`:

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit"
  }
}
```

### WebStorm

Enable **Run eslint --fix on save** and **Prettier on save** in settings.

## Project Board Automation (how to commit)

Every push to `main` is processed by the **Project Sync** workflow — see
[docs/project-board-automation.md](project-board-automation.md) for the full
developer rules. In short:

1. **Create a GitHub issue** for the work before coding.
2. **Reference it in the commit message**: `fixes #12` / `closes #12`
   (completes it → board Status becomes Done), `refs #12` or `#12`
   (only touches it → Status untouched). The push then links to the existing
   issue instead of creating a duplicate task.
3. No reference → an auto-generated 🤖 task appears on the board.
4. `[skip-task]` in the message opts a push out of the board entirely.
