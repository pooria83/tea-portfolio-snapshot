# Mobile App Docs

Technical documentation for the TEA-assist React Native app.

## Contents

| Doc | What it covers |
|---|---|
| [Logging](logging.md) | `react-native-logs` setup, levels, redaction, context enrichment, console/Sentry transports |
| [Error Handling](error-handling.md) | `classifyError` / `toUserMessage`, toast store, mutations-log-callers-surface rule, boundaries, global handlers |
| [Sentry](sentry.md) | Crash reporting setup, environments, source-map upload, secrets, troubleshooting |
| [Component Map](component-map.md) | Every screen, component, service, feature and how they connect |
| [Chat Integration](chat-integration.md) | Chat HTTP endpoints, WebSocket streaming protocol, find-similar flow, intent theming |
| [Android Build](android-build.md) | Flavors, Maven mirrors, NDK pinning, memory tuning, DevTools sandbox fixes |
| [Release & Signing](release-and-signing.md) | keystore.properties contract, debug-signed-release risk, CI signing wiring, versionName/versionCode, store checklist |
| [Project Board Automation](project-board-automation.md) | Commit-to-board workflow: issue references, auto-tasks, skip marker |

## Cross-cutting conventions

- **Never surface raw API errors to the user** — run them through `toUserMessage(error, t)` (see [error-handling.md](error-handling.md)).
- **Never log secrets** — the logger redacts sensitive keys automatically, but don't log raw tokens by hand either (see [logging.md](logging.md)).
- **Every user-facing error needs a translation** in all three locales (`src/i18n/locales/{en,ar,fa}/error.json`).
- **Keep the gates green**: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test` — they run in pre-commit too.
