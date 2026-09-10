# Error Handling

## Architecture overview

```
catch (error)
   │
   ├─ API failure? ──► log.warn('…failed', classifyError(error))   (mutation onError)
   │
   └─ UI layer: showError(error)   (errorToastStore → Snackbar via toUserMessage)
        │
        └─ local/programming error? ──► log.warn('…flow error', classifyError(error))
```

Two rules hold the whole thing together:

1. **Mutations log, callers surface.** React Query mutations log on `onError` (`log.warn('uploadFile failed', classifyError(error))`). They do **not** show toasts — the calling screen decides how to surface via `showError` in its own `catch`. This prevents double-toasts when the same error travels through both layers.
2. **UI catches surface via `showError(error)`**, which renders a localized message through the global toast. Local (non-API) errors in UI flows are also logged so they are not silent — guard with `!isAxiosError(error)` to avoid double-logging API errors.

## The error pipeline

### 1. Classify — `classifyError(error)` (`src/services/api/errors.ts`)

Turns any thrown value into a typed summary for **logging**:

| Condition | `kind` |
|---|---|
| Axios `ECONNABORTED` | `timeout` |
| Axios, no response | `offline` |
| HTTP 401 | `unauthorized` |
| HTTP 4xx | `validation` |
| HTTP 5xx | `server` |
| Anything else | `unknown` |

Also carries `status` and the backend `translation_key` (from the API error envelope `{error: {translation_key}}`) when available.

### 2. Present — `toUserMessage(error, t)` (`src/services/api/errors.ts`)

Turns the error into a **localized** message for the user. Priority:

1. Backend `translation_key` → `t(key, {ns: 'error'})` (keys in `src/i18n/locales/{en,ar,fa}/error.json`)
2. Error-kind key → `network` / `timeout` / `server` / `generic` / `not_authenticated`
3. Fallback → `extractApiError(error)` (envelope `error.message` → legacy `detail` string/array → `error.message`)

### 3. Surface — global toast (`src/features/errors/errorToastStore.ts` + `src/components/feedback/ErrorToast.tsx`)

- Zustand store holds a single `error` value; `showError(error)` sets it.
- `<ErrorToast>` (mounted once in `App.tsx` inside the Paper `Portal`) shows a 4000 ms `Snackbar` with `toUserMessage(error, t)`.

```ts
const showError = useErrorToastStore((s) => s.showError);
try {
  await updateProfile.mutateAsync(data);
} catch (error) {
  showError(error);   // + log locally if not an API error
}
```

## Crash recovery

### React render errors — `AppErrorBoundary` (`src/components/feedback/AppErrorBoundary.tsx`)

`react-error-boundary` around the root navigator. On error it logs
`log.error('unhandled render error', {error, componentStack})` and renders a
fallback screen (crash title/message + reload button — keys in the `error`
i18n namespace).

### JS errors & rejected promises — `installGlobalHandlers()` (`src/services/logging/globalHandlers.ts`)

Called at module scope in `App.tsx`:

- `ErrorUtils.setGlobalHandler` — logs every unhandled JS error, then delegates to the default handler
- guarded `unhandledrejection` listener — logs unhandled promise rejections

## Auth errors

`useAuthMutations` (`src/features/auth/useAuthMutations.ts`) logs `sendOtp/verifyOtp/googleAuth failed` with `classifyError` and stores the **localized** message (`toUserMessage(error, i18n.t)`) in the auth store, where the auth screens render it inline. The Google sign-in catch in `PhoneScreen` routes non-API errors through the same `toUserMessage` pipeline. Backend `translation_key`s from the auth endpoints are respected.

## Retry policy

- Queries: `retry: 2` (GETs are safe to retry)
- Mutations: `retry: false` (never blindly retry POST/PATCH — non-idempotent)

401s are handled by the refresh interceptor in `src/services/api/interceptors.ts`: one in-flight refresh, queued requests replayed, on refresh failure tokens are cleared and the user is logged out (logged at `error` level). The response interceptor does **not** log non-401 failures — the request owner (mutation `onError` / screen catch) is the single canonical log, so one failure is logged exactly once.

## Runtime validation (trust model)

There is **no schema-validation library** — no zod (or similar) dependency/import anywhere. Response safety is hand-rolled and partial:

- `unwrapEnvelope` (`src/services/api/envelope.ts`) only checks that the body is `{success: true, data}` and returns `data` as-is.
- `normalizeChatMessage` / `normalizeConversationItem` (`src/features/chat/normalize.ts`) coerce chat models field-by-field into safe shapes.
- `parseChatFrame` (`src/features/chat/chatStream.ts`) JSON-guards WS frames (must parse to a non-array object).
- Everything else trusts the payload: `errors.ts` casts response bodies via `as ApiErrorBody` after only a `typeof === 'object'` check, so a malformed body can still slip through with typed fields missing.

## Translation keys

Every user-facing message must exist in `src/i18n/locales/{en,ar,fa}/error.json`. Add new keys in all three files when adding backend `translation_key`s.

Currency vs. the backend catalog (87 `E.*` constants in `product-graph-api/app/core/error_codes.py`): `en/error.json` holds 85 keys, of which 76 match the catalog. 11 backend keys have no app translation yet — mostly admin/web flows the mobile app never triggers (`csrf_header_missing`, `invalid_oauth_state`, `embed_provider_invalid`, `embed_model_required`, `embed_model_not_found`, `embed_tunnel_url_required`, `embed_api_key_required`, `embed_api_key_too_short`, `message_not_found`, `scraper_header_not_found`, `scraper_header_invalid`); for those, `toUserMessage` falls back to the backend English `defaultValue`. Reverse drift: the app also carries `embedding_failed` (originates from the AI Engine chat router SSE) and `chat_failed` (sent literally by the API's `ws.py`) — neither is an `E.*` constant. On top of the matched keys there are the generic ones (`network`, `timeout`, `server`, `generic`, `crash*`).

## Related

- [Logging](logging.md) — where classified errors go
- [Sentry](sentry.md) — error-level logs + boundary crashes are sent there
- [Component Map](component-map.md) — which components use `showError`
