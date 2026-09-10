# Product Graph Mobile App

React Native mobile app for the TEA-assist platform.

## Prerequisites

- Node.js >= 22.11.0 (the minimum for `react-native` 0.86's CLI; enforced by `engines` in package.json)
- React Native CLI (`npx @react-native-community/cli`)
- Android Studio + Android SDK (for Android builds)
- JDK 17 (Android Gradle Plugin requires it)
- Xcode + CocoaPods (for iOS builds)

### Android SDK requirements

The Gradle build expects these installed (install via `sdkmanager` or Android Studio SDK Manager):

- Platforms: `android-36`
- Build Tools: `35.0.0` and `36.0.0`
- NDK: `27.1.12297006`
- CMake: `3.22.1` (auto-installed on first build)

If any piece is missing, Gradle fails with `Failed to find Build Tools revision …` or an NDK error. Point Gradle at your SDK with `android/local.properties`:

```ini
sdk.dir=/path/to/your/android-sdk
```

(`local.properties` is gitignored — each developer sets their own path.)

### Maven mirror note (Iran)

Maven Central / Google / plugin downloads can be slow or blocked from inside
Iran. `android/settings.gradle` therefore rewrites those repository URLs to the
Iranian mirrors `https://en-mirror.ir/` (primary) and
`https://maven.devneeds.ir/` (fallback).

The rewrite is auto-disabled on GitHub Actions (`GITHUB_ACTIONS=true`) since
runners reach `google()`/`mavenCentral()` directly. Force a specific mode with
`-PuseIranMirrors=true|false`.

## Setup

```bash
npm install
cd ios && pod install && cd ..
cp .env.example .env   # API_BASE_URL=https://portfolio.example.invalid/api/v1
```

## Run

```bash
npm start                       # Metro dev server (keep this terminal running)
npm run android:dev             # build + install dev flavor on connected device
npm run ios                     # iOS dev
```

The project has three Gradle flavors (`dev`, `staging`, `production`, suffixing the applicationId: `com.tea.app.dev` etc.), so the plain `installDebug` task doesn't exist. Always use the flavor-specific commands:

```bash
npm run android:dev             # react-native run-android --mode=devDebug --appIdSuffix dev
# or directly: cd android && ./gradlew installDevDebug
```

The `--appIdSuffix dev` is required — without it the CLI launches `com.tea.app/.MainActivity` which doesn't exist in the dev flavor.

## Connecting the app to the backend

The dev backend is exposed through a Cloudflare Tunnel:

- `.env`: `API_BASE_URL=https://portfolio.example.invalid/api/v1` — works from anywhere (Wi-Fi, cellular), **no `adb reverse` needed**
- Alternative for local-only testing: run the API locally and use `adb reverse tcp:8000 tcp:8000` with `API_BASE_URL=http://localhost:8000/api/v1`

The tunnel (portfolio-review) maps `portfolio.example.invalid` → local FastAPI (port 8000), `portfolio.example.invalid` → dashboard (8001), `portfolio.example.invalid` → MinIO. See the [API repo tunnel docs](https://github.com/TEA-assist/product-graph-api/blob/main/docs/cloudflare-tunnel-dev.md).

## Build

```bash
# Android dev APK (dev flavor)
cd android && ./gradlew :app:assembleDevDebug
# → android/app/build/outputs/apk/dev/debug/app-dev-debug.apk

# Android release APK
cd android && ./gradlew assembleRelease

# iOS archive (via Xcode)
npx react-native run-ios --configuration Release
```

> Native Kotlin sources live under `android/app/src/main/java/com/tea/app/` (`MainApplication.kt`, `MainActivity.kt`) — keep the package `com.tea.app` in sync with `namespace`/`applicationId` in `android/app/build.gradle`; the AndroidManifest references `.MainApplication`/`.MainActivity` relative to that package.

> ⚠️ Run Gradle as your normal user, never with `sudo`/root. Root-owned builds
> leave build outputs owned by root, so your next user-owned build fails with
> permission errors (`Couldn't delete …`, `Permission denied` on `.cxx`/`R.jar`).
> If that happens, `chown -R` the project tree back to your user. The Gradle
> daemon heap is capped at 3 GB via `org.gradle.jvmargs=-Xmx3072m` in
> `android/gradle.properties`.

## Patches (`patch-package`)

`npm install` runs `patch-package` via `postinstall`, applying every diff in [`patches/`](patches/):

- `@maplibre+maplibre-react-native+11.3.6.patch` — `MLRNMapView.kt` claims the touch on `ACTION_DOWN` (`requestDisallowInterceptTouchEvent`) so an enclosing `ScrollView` can no longer intercept the map's gestures. **Re-check this patch after any MapLibre bump** (it targets a Kotlin file with line-sensitive hunks).

## Versioning & releases

Android `versionName` is **1.1** / `versionCode` is **2**, defined only in `android/app/build.gradle:39-40` (the `package.json` `"version"` field, 0.1.0, is unrelated and divergent). Release signing currently falls back to the debug keystore when `android/keystore.properties` is absent — i.e. today's release builds (local and CI) are debug-signed. Details, risks, and the store checklist: [docs/release-and-signing.md](docs/release-and-signing.md).

Native Android additions live under `android/app/src/main/java/com/tea/app/` — including the SMS OTP autofill feature (`SmsOtpModule.kt`, user-consent flow): see [docs/native-android.md](docs/native-android.md).

## Documentation

The full technical docs live in [`docs/`](docs/README.md):

| Doc | What it covers |
|---|---|
| [Logging](docs/logging.md) | structured logging, levels, redaction, context, transports |
| [Error Handling](docs/error-handling.md) | classify → localize → toast pipeline, crash recovery, retry policy |
| [Sentry](docs/sentry.md) | crash reporting, environments, source maps, secrets, troubleshooting |
| [Component Map](docs/component-map.md) | every screen/component/service and how they connect |
| [Chat Integration](docs/chat-integration.md) | chat HTTP endpoints, WebSocket protocol, find-similar flow, intent theming |
| [Android Build](docs/android-build.md) | flavors, mirrors, NDK pin, memory tuning, DevTools sandbox |
| [Release & Signing](docs/release-and-signing.md) | keystore.properties contract, debug-signed-release caveat, CI signing, version bumps, store checklist |
| [Native Android](docs/native-android.md) | native Kotlin modules (SMS OTP autofill, language preferences) |
| [Project Board Automation](docs/project-board-automation.md) | commit-to-board workflow: issue references, auto-tasks, skip marker |

## Test

```bash
npm test                  # Jest unit tests
```

### E2E (Detox) — scaffolding only, not currently runnable

`e2e/auth.test.ts` and a root `detox.config.ts` exist, but `detox build && detox test` **fails on a fresh clone**. Do not rely on it until:

- `detox` is actually added to devDependencies (it is absent from package.json and the lockfile — the `detox` command doesn't exist);
- the config is moved/named to a standard `.detoxrc.(js|json)` (nothing references the non-standard `detox.config.ts`, and Detox doesn't auto-load it);
- the `binaryPath`s are fixed for flavors: they expect pre-flavor outputs (`apk/debug/app-debug.apk`) while flavored builds land in `apk/dev/debug/app-dev-debug.apk` etc., and plain `assembleDebug` no longer exists;
- the iOS entry has a workspace: `ios/ProductGraphMobile.xcworkspace` appears only after `pod install` (never run; only `ProductGraphMobile.xcodeproj` is checked in).

## Lint & Typecheck

```bash
npm run lint
npm run typecheck
npm run format:check
```

## Tech Stack

| Concern | Choice |
|---|---|
| Framework | React Native 0.86 (bare) |
| UI | react-native-paper 5.15 (purple #9333EA) |
| Navigation | React Navigation 7 (native-stack) |
| State (client) | Zustand 5 |
| State (server) | TanStack React Query 5 |
| HTTP | Axios with JWT refresh interceptor |
| Images | FastImage (`@d11/react-native-fast-image`) + Next.js image optimizer (`IMAGE_OPTIMIZER_URL`) |
| Maps | MapLibre (`@maplibre/maplibre-react-native` — used by `LocationPicker`) |
| Secure storage | react-native-keychain |
| Location | @react-native-community/geolocation |
| Image picking | react-native-image-crop-picker |
| Splash screen | react-native-bootsplash |
| Markdown | @ronradtke/react-native-markdown-display |
| Clipboard | @react-native-clipboard/clipboard |
| i18n | i18next (ar, en, fa) |
| Icons | react-native-vector-icons |
| Env | react-native-config |
| Logging | react-native-logs (redaction + context, Sentry transport) |
| Crash reporting | Sentry (EU org `ask-tea`, project `ask-tea-mobile`) |
| Engine | Hermes (default) |

## Docs Index

All technical documentation: [docs/README.md](docs/README.md)
