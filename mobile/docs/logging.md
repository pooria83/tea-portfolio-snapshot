# Logging

Structured logging via [`react-native-logs`](https://github.com/onubo/react-native-logs) v5, defined in `src/services/logging/logger.ts`.

## Levels

| Level | Severity | Use for |
|---|---|---|
| `debug` | 0 | Request/response traces, dev diagnostics |
| `info` | 1 | Successful flows, state changes |
| `warn` | 2 | Expected failures (API errors, retries) |
| `error` | 3 | Unexpected failures, crashes, refresh failures |

Usage:

```ts
import {log} from '../../services/logging/logger';

log.debug('api request', {method, url, authenticated});
log.warn('updateProfile failed', classifyError(error));
log.error('token refresh failed', {error: classifyError(refreshError)});
```

## Severity gating

The logger only emits levels at or above `severity`:

- `production` builds → `info` (debug traces suppressed)
- everything else → `debug`

## Redaction

`redact()` walks every logged object and replaces any value whose key matches
`SENSITIVE_KEY_PATTERN` (`token|password|passwd|secret|authorization|id_token|refresh_token|access_token|api[_-]?key`) with `[REDACTED]`. This runs on every structured payload before it reaches any transport — including Sentry. Never log raw credentials manually either.

## Context enrichment

`setLogContext(update)` merges global context into every log line. Wired up in `App.tsx`:

- `useAuthStore.subscribe` → `{userId}` when the user signs in/out
- `RootNavigator` navigation state listener → `{route}` (current screen name)

Per-call data overrides context on key collisions.

## Transports

Both transports are registered in `logger.createLogger(...)`:

### Console transport

Custom transport that maps levels to `console.debug/info/warn/error` and appends the context + data object as a second argument, so the JS debugger shows `message {context, ...data}`.

### Sentry transport

- `warn`+ levels → `Sentry.addBreadcrumb` (attached to crash reports)
- `error` → `Sentry.captureMessage(msg, 'error')`
- `debug`/`info` are skipped (keep breadcrumbs useful)

This is why the 4 `no-console` lint warnings in `logger.ts` are intentional — the console transport *is* the `console` usage.

## Do not log

- Raw passwords, OTP codes, id_tokens, refresh/access tokens, API keys
- Full `AxiosError` objects (call `classifyError(error)` first — it extracts kind/status/translation key)
- The current screen's full navigation state (only the route name via `setLogContext`)

## API request tracing

`src/services/api/interceptors.ts` logs every request/response at `debug`:

```json
{"method": "post", "url": "/files/upload?max_size=400", "status": 201, "durationMs": 1343}
```

The interceptors themselves only log `error` in two spots: a request-interceptor
failure (`log.error('api request failed')`) and a failed token refresh
(`log.error('token refresh failed', ...)`). Non-401 response failures are
rejected **without logging** — they surface to the caller instead. The
`log.warn('… failed', classifyError(error))` pattern lives in the ~30 call sites
(hooks/services, e.g. `features/profile/useProfileMutations.ts`).

## Related

- [Error Handling](error-handling.md) — how errors flow from `catch` to log to toast
- [Sentry](sentry.md) — where `error` level logs end up
