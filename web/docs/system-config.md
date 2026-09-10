# System Configuration

## Environment Variables

| Variable                       | Required | Default       | Description                               |
| ------------------------------ | -------- | ------------- | ----------------------------------------- |
| `NODE_ENV`                     | No       | `development` | Node environment                          |
| `PORT`                         | No       | `8001`        | Dev server port                           |
| `DASHBOARD_PORT`               | No       | `8001`        | Dashboard port alias                      |
| `NEXT_PUBLIC_API_URL`          | Yes      | —             | Backend API base URL (includes `/api/v1`) |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Yes      | —             | Google OAuth web client ID                |

### Example `.env`

```env
NODE_ENV=development
PORT=8001
NEXT_PUBLIC_API_URL=https://portfolio.example.invalid/api/v1
NEXT_PUBLIC_GOOGLE_CLIENT_ID=<GOOGLE_CLIENT_ID>
```

> **Note:** `.env.example` does not currently list `NEXT_PUBLIC_GOOGLE_CLIENT_ID`,
> but the code requires it — Google login (`login/page.tsx`) and Google account
> linking (`ProfilePage.tsx`) silently no-op without it. Set it manually in your
> `.env`. CI injects it into Docker builds via `--build-arg` from the
> `NEXT_PUBLIC_GOOGLE_CLIENT_ID` secret.

### Docker-specific Environment Variables

| Variable           | Description                                                                       |
| ------------------ | --------------------------------------------------------------------------------- |
| `BUILD_TARGET`     | Docker build target (`dev`, `production`)                                         |
| `VOLUMES_SRC`      | Source directory for volume mount                                                 |
| `VOLUMES_PUBLIC`   | Public directory for volume mount                                                 |
| `VOLUMES_MESSAGES` | Messages directory for volume mount                                               |
| `GIT_SHA`          | Git commit SHA passed as build arg by CI; inlined at build time for `/api/health` |

## Key Configuration Files

| File                   | Purpose                                                                                                                                                                                                   |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `next.config.ts`       | Next.js config with next-intl plugin, React compiler, server external packages, allowed dev origins, CSP + security headers, `/website` redirect shim, image remote patterns, `GIT_SHA` build-time inline |
| `tsconfig.json`        | TypeScript strict mode, `@/*` path alias to `src/`, ES2017 target                                                                                                                                         |
| `eslint.config.mjs`    | ESLint flat config — Next.js core-web-vitals + TypeScript + custom rules                                                                                                                                  |
| `.prettierrc`          | Prettier — semicolons, double quotes, trailing commas, 100 print width, Tailwind plugin                                                                                                                   |
| `postcss.config.mjs`   | PostCSS with Tailwind v4 plugin                                                                                                                                                                           |
| `components.json`      | shadcn/ui config — base-nova style, lucide icons, CSS variables                                                                                                                                           |
| `vitest.config.ts`     | Vitest — jsdom, globals, `@/` alias, setup file                                                                                                                                                           |
| `playwright.config.ts` | Playwright — chromium, baseURL, CI retries                                                                                                                                                                |
| `.husky/pre-commit`    | Git hook — lint-staged + `tsc --noEmit`                                                                                                                                                                   |

## Security Headers & CSP (`next.config.ts`)

All responses get these headers (via `headers()`, source `/:path*`):

| Header                      | Value                                                                |
| --------------------------- | -------------------------------------------------------------------- |
| `X-Content-Type-Options`    | `nosniff`                                                            |
| `X-Frame-Options`           | `SAMEORIGIN`                                                         |
| `Referrer-Policy`           | `strict-origin-when-cross-origin`                                    |
| `Permissions-Policy`        | `camera=(), microphone=(), geolocation=(self)`                       |
| `Content-Security-Policy`   | built by `buildCsp()` (below)                                        |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` — **production only** |

The CSP builder:

- `script-src 'self' 'unsafe-inline'` (+ `'unsafe-eval'` in dev only)
- `img-src` allowlist: self, data/blob, `storage(.dev).portfolio.example.invalid`, `app(.dev).portfolio.example.invalid`, cdnjs, OpenStreetMap tile hosts
- `connect-src 'self'` + API origin + WS origin (derived from `NEXT_PUBLIC_API_URL`) + `tiles.openstreetmap.org`
- `style-src 'self' 'unsafe-inline'`, `font-src 'self' data:`, `object-src 'none'`, `base-uri`/`form-action`/`frame-ancestors 'self'`, `worker-src`/`media-src 'self' blob:`

Other `next.config.ts` additions:

- **Redirect shim**: permanent redirects `/→locale/website` → `/→locale` and `/→locale/website/:path*` → `/→locale/:path*` (public pages moved under the locale root)
- **Images**: `remotePatterns` for `storage-dev/storage/app-dev/portfolio.example.invalid` (https), `formats: ["image/webp"]`, sizes 64/128/256, 1-day minimum cache TTL
- **GIT_SHA**: inlined via `env` at build time so the edge-runtime health route can report it

## Health Check Endpoint

`GET /api/health` (edge runtime, `src/app/api/health/route.ts`) returns:

```json
{
  "status": "ok",
  "service": "product-graph-web-ui",
  "environment": "production",
  "git_sha": "651db44…",
  "uptime_seconds": 1234
}
```

`git_sha` comes from the build-time-inlined `GIT_SHA` env (falls back to `"dev"`). The Docker image's `HEALTHCHECK` curls this endpoint (`--interval=30s --timeout=5s --retries=3`).

## Tailwind v4 + shadcn/ui

Styling uses Tailwind CSS v4 with shadcn/ui (base-nova style). Theme CSS variables are defined in `src/app/globals.css`:

```css
:root {
  --background: hsl(0 0% 100%);
  --foreground: hsl(0 0% 3.9%);
  /* ... 40+ CSS variables for colors, radii, shadows */
}

.dark {
  --background: hsl(0 0% 3.9%);
  --foreground: hsl(0 0% 98%);
  /* ... dark theme overrides */
}
```

Theme toggling is handled by a custom `ThemeProvider` (not `next-themes`), which swaps the `dark` class on the `<html>` element.

## Google OAuth

- A single web OAuth client is shared across all environments with 4 authorized redirect URIs (dev/staging/prod + localhost).
- The client ID is set via `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in `.env`.
- Android OAuth clients are configured per-flavor (dev/staging/production) with separate package names and debug SHA-256 fingerprints.

## Admin Settings Pages

All under `/[locale]/admin/settings/*`, i18n namespaces under `settings.*`, endpoints in `adminApi.ts`.

### LLM Management (`/settings/llm`)

- Models grouped by provider → model; each model lists its API keys
- Add key (name + secret) via Dialog, toggle/delete per key (AlertDialog confirm)
- Default model + user-communication model selects — dropdowns only offer models that have an active API key
- Hooks: `useGetLLMModelsQuery`, `useAddLLMApiKeyMutation`, `useToggleLLMApiKeyMutation`, `useDeleteLLMApiKeyMutation`, `useGetLLMSettingsQuery`, `useUpdateLLMSettingsMutation`

### Prompt Templates (`/settings/prompts`)

- Six editors: `pre_prompt`, `ending_prompt`, `chat_assistant`, `parse_query`, `summarize`, `title`
- Single Save button → `PUT /admin/llm/prompt-templates` (all fields at once)

### System Settings (`/settings/system`)

- One card with a Switch toggling the product AI generation cron
- Reads/writes the `product_ai_generation_cron` system setting via `GET/PUT /admin/system-settings`

### AI Engine Settings (`/settings/ai-engine`)

- **Current config** card — parses the `embedding_provider` system setting (plain string or JSON: `{provider, model, base_url, need_api_key, api_key_encrypted?, …}`)
- **Update to** form — provider Select (`sentence_transformer` / `tei` / `openrouter`). TEI mode adds: embedding-model Select (`useGetEmbedModelsQuery`), tunnel URL input (e.g. `https://xxx.trycloudflare.com/v1`), optional API key with stored-key hint. Apply goes through an AlertDialog confirm and writes `embedding_provider` (+ `tei_tunnel_url`) system settings
- **Embedding test** card — text ≤ 1000 chars → `POST /admin/ai-engine/embed-text` → shows model, dimensions, full vector in a read-only textarea + copy button

### Scraper Headers (`/settings/scrapers`)

Manages the raw request-header blocks (cookies, user agent, …) used by each scraper.

- Lists scrapers via `useGetScraperHeadersQuery` → `GET /admin/scraper-headers` (tag `ScraperHeaders`)
- One Card per scraper: mono-font name + status badge — destructive **Error** when `status === "error"`, default **Ready** when a header is set, secondary **Not configured** otherwise; `error_message` renders destructively under the title, else a header hint
- Raw-header draft in a 12-row mono `Textarea` per scraper; **Save** → `PUT /admin/scraper-headers/:name` body `{header}` (`useUpdateScraperHeaderMutation`)
- **Clear** → AlertDialog confirm → `DELETE /admin/scraper-headers/:name` (`useClearScraperHeaderMutation`)
- Type: `ScraperHeaderItem` (`id`, `name`, `header?`, `status: "ready" | "error"`, `error_message?`, `error_at?`, `updated_at`) in `types/llm.ts`
- Reachable from the sidebar item `nav.scraperHeaders` (`HiOutlineChip` icon) and a dashboard tile; i18n namespace `settings.scrapers`
