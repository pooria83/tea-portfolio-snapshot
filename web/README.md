# Product Graph — Web UI

Multilingual (AR/EN/FA) dashboard for managing stores, products, orders, and AI-powered features. Built with Next.js 16, React 19, Tailwind CSS v4, and shadcn/ui.

## Features

- **Public Website**: guest home page (`/`) with animated hero, **anonymous chat** (no account — ephemeral WS session, intent-themed bubbles, find-similar, product sheets), and a **random products slider** (autoplay + dots, RTL-aware)
- **Admin Dashboard**: Catalog data browser, AI Chat (RAG product search), conversations viewer, cron job reports, embedding cron (per-model status + re-index), LLM model & API key management, prompt template editor (6 templates), system settings, AI engine config, **Search Evaluation panel** (query generation, golden-set import, relevance judging, MRR@10/Recall@10 metrics)
- **AI Chat**: Conversational RAG product search with live WebSocket streaming, conversation history, product cards with detail dialog + similar-products, debug inspection
- **AI Description Generation**: Model selector, editable prompt, run/edit preview, history with version restore
- **Seller Dashboard**: Store/product CRUD, variant management, multi-piece products, color sets
- **Phone OTP + Google OAuth**: httpOnly-cookie auth (with CSRF protection) + Bearer tokens, refresh token rotation, RBAC (admin/seller), OAuth nonce flow
- **Role Switching**: Admin can switch to seller view with Redux-persisted preference

## Tech Stack

| Layer     | Technology                                                             |
| --------- | ---------------------------------------------------------------------- |
| Framework | Next.js 16 (App Router) + React 19                                     |
| Language  | TypeScript 5 (strict mode)                                             |
| Styling   | Tailwind CSS v4 + shadcn/ui (base-nova)                                |
| State     | Redux Toolkit + RTK Query                                              |
| i18n      | next-intl (ar, en, fa) + RTL                                           |
| Forms     | react-hook-form + zod                                                  |
| Testing   | Vitest + Playwright                                                    |
| Auth      | Phone OTP + Google OAuth (httpOnly cookies + Bearer, refresh rotation) |
| CI/CD     | GitHub Actions + Docker multi-stage build                              |

## Repository Structure

```
product-graph-web-ui/
├── docs/               # Documentation (detailed guides)
├── src/                # Application source code
├── messages/           # Translation files
├── e2e/                # Playwright end-to-end tests
├── certs/              # TLS trust material (Cloudflare origin CA for dev)
├── run/                # Local runtime artifacts (not committed)
├── Dockerfile          # Multi-stage image build (deps/dev/build/production)
├── docker-compose.yml  # Local containerized development
└── .github/workflows/  # CI pipeline + project board automation
```

## Quick Start

```bash
npm install
cp .env.example .env   # Configure API URL + port
npm run dev            # → http://localhost:8001 (PORT from .env)
```

> `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is **not** in `.env.example` — add it to `.env` manually (required by the login page and Google account linking). CI/Docker builds receive it as a build arg from the repo secret.

## Documentation

| Document                                                       | Description                                                                                   |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| [System Configuration](docs/system-config.md)                  | Environment variables, config files, Tailwind/shadcn theme, Google OAuth setup                |
| [Development Setup](docs/development.md)                       | Prerequisites, running locally, Docker Compose, IDE setup, git hooks                          |
| [Project Structure](docs/project-structure.md)                 | Directory tree, naming conventions, architecture decisions                                    |
| [Component Map](docs/component-map.md)                         | Component hierarchy, reusable components, shadcn/ui library, provider tree                    |
| [Product Definition System](docs/product-definition-system.md) | Catalog, attributes, categories, product form, variant generation                             |
| [Routing & Navigation](docs/routing.md)                        | App Router structure, route groups, auth guards, role-based access, locale routing            |
| [State Management](docs/state-management.md)                   | Redux store, auth slice state machine, localStorage persistence                               |
| [API Integration](docs/api-integration.md)                     | RTK Query endpoints, API envelope format, token refresh, error handling                       |
| [Authentication & Authorization](docs/auth.md)                 | Phone OTP flow, Google OAuth, JWT tokens, RBAC (admin/seller), account linking                |
| [Internationalization & RTL](docs/i18n.md)                     | next-intl config, locale negotiation, RTL handling, translation namespaces, error codes       |
| [Testing](docs/testing.md)                                     | Vitest config, unit test patterns, Playwright e2e tests, pre-commit quality gates             |
| [CI/CD Flow](docs/ci-cd.md)                                    | GitHub Actions pipeline, quality checks, Docker build, environment-specific configs           |
| [Deployment](docs/deployment.md)                               | Docker multi-stage build, Docker Compose, environments, build arguments                       |
| [Project Board Automation](docs/project-board-automation.md)   | Commit-to-board workflow: issue references, auto-tasks, skip marker                           |
| [Fashion AI RAG Architecture](docs/fashion-ai-rag-plan.md)     | RAG product search: embeddings, Qdrant filters, query parsing, chat streaming                 |
| [Public Website & Anonymous Chat](docs/website-home.md)        | Guest home page: anonymous chat session, intent bubbles, find-similar, random products slider |
| [Search Evaluation Panel](docs/search-eval.md)                 | Admin search-quality tool: query generation, golden-set import, judging, MRR@10/Recall@10     |

## Project Links

| Repo       | URL                                                    |
| ---------- | ------------------------------------------------------ |
| Web UI     | https://github.com/TEA-assist/product-graph-web-ui     |
| API        | https://github.com/TEA-assist/product-graph-api        |
| Mobile App | https://github.com/TEA-assist/product-graph-mobile-app |

## Environment URLs (Dev)

| Service      | URL                           |
| ------------ | ----------------------------- |
| Frontend     | https://portfolio.example.invalid    |
| Backend API  | https://portfolio.example.invalid     |
| File Storage | https://portfolio.example.invalid |

## License

Private — TEA-assist
