# iOS Status

Honest snapshot of the iOS side (`ios/`). **Short version: this is an
unbuilt scaffold — the app is not buildable from a fresh clone, and several
release blockers are still open.**

## Current state

What is committed:

- `ios/Podfile` and `ios/.xcode.env`
- `ios/ProductGraphMobile.xcodeproj/` (project + shared scheme
  `ProductGraphMobile.xcscheme`)
- `ios/ProductGraphMobile/` sources: `AppDelegate.swift`,
  `BootSplash.storyboard`, `LaunchScreen.storyboard`, `Colors.xcassets`,
  `Images.xcassets`, `Info.plist`, `PrivacyInfo.xcprivacy`

What is **not** committed (and has therefore never been generated/installed):

- **No `Podfile.lock`** — CocoaPods has never been run on a committed state.
- **No `ProductGraphMobile.xcworkspace`** — without it Xcode cannot build the
  app at all.

Consequence: a fresh clone cannot build or run iOS. Getting there requires a
macOS machine plus `pod install` inside `ios/`, which generates both missing
artifacts locally. The Android app is the only deliverable that exists today.

## What the scaffold does configure

### Podfile

- Platform floor from RN's `min_ios_version_supported`.
- **Permission pods** from `react-native-permissions`, added manually by path:
  `Permission-LocationWhenInUse`, `Permission-Microphone`,
  `Permission-Notifications` (matching what `src/services/permissions/` uses).
  No `react-native.config.js` permissions block is needed since pods are
  declared directly.
- Standard `use_react_native!` wiring; New Architecture defaults, Mac Catalyst
  disabled.

### Info.plist

| Key | Value / note |
|---|---|
| `NSLocationWhenInUseUsageDescription` | Profile map location picking |
| `NSMicrophoneUsageDescription` | Voice chat messages |
| `NSPhotoLibraryUsageDescription` | Choosing a profile picture |
| `UISupportedInterfaceOrientations` (+ `~ipad`) | Portrait only |
| `NSAppTransportSecurity` | `NSAllowsArbitraryLoads=false`, `NSAllowsLocalNetworking=true` (local dev API over plain HTTP) |
| `UIAppFonts` | Material Icons / Community / Design icon fonts |
| Launch | BootSplash storyboard |

### PrivacyInfo.xcprivacy

Present: `NSPrivacyTracking=false`, no collected data types, accessed-API
reasons declared for file timestamp (C617.1), user defaults (CA92.1), system
boot time (35F9.1).

## Gaps blocking an iOS release

1. **No `CFBundleURLTypes`.** Google Sign-In needs its reverse-client-ID URL
   scheme registered to receive the OAuth redirect — with none declared,
   **Google auth cannot complete on iOS** even once the app builds. (The
   configured client today is the Android one; see AGENTS.md rule 7.)
2. **No entitlements** files committed (push, associated domains, etc. would
   each need one later).
3. **No signing story**: no team/bundle-ID/signing decisions recorded anywhere;
   [release-and-signing.md](release-and-signing.md) covers Android only.
4. **Detox references a nonexistent workspace**: `detox.config.ts` `ios.debug`
   builds via `-workspace ios/ProductGraphMobile.xcworkspace`, which only
   exists after a local `pod install` — iOS e2e is unusable as committed.
5. **No Sentry native source-map/symbol upload** for iOS (see
   [sentry.md](sentry.md)).

## Explicitly not implemented (repo-wide)

None of these exist on either platform; listed here so nobody looks for them:

- OTA updates (no CodePush / expo-updates)
- Deep linking into the app (the only `Linking` usage opens external URLs,
  e.g. product source links in `ProductViewModal`; no URL scheme/config)
- Push notifications infrastructure (permission checks only in
  `services/permissions`; no FCM/APNs/notifee/firebase)
- Store publishing pipeline / fastlane

## Related

- [Release & Signing](release-and-signing.md) — Android keystore contract
- [Android Build](android-build.md) / [Native Android](native-android.md)
