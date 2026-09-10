# Component Map

How the app is organized and how the pieces connect.

## Entry point

```
App.tsx
├── installGlobalHandlers()          # unhandled JS errors / rejections
├── initSentry()                     # Sentry SDK (skips if no DSN)
├── GoogleSignin.configure()         # from Config.GOOGLE_CLIENT_ID
├── SafeAreaProvider                 # react-native-safe-area-context root
├── QueryClientProvider              # react-query (retry: queries 2, mutations 0)
├── PaperProvider                    # theme (+ Portal host)
├── ErrorToast / SuccessToast        # global Snackbars (Portal)
└── AppErrorBoundary                 # react-error-boundary crash fallback
    └── RootNavigator                # useAuth switch + NavigationContainer; hides BootSplash on ready
```

## Navigation (`src/app/navigation`)

| File                | Role                                                                                     |
| ------------------- | ---------------------------------------------------------------------------------------- |
| `RootNavigator.tsx` | NavigationContainer + `useAuth` switch (`AuthStack`/`AppStack`); reports route name to `setLogContext`/`setSentryRoute`; hides the native BootSplash `onReady` |
| `AuthStack.tsx`     | `Phone` → `Otp` screens (unauthenticated)                                                |
| `AppStack.tsx`      | Stack: `Main` (tabs) → pushes `PermissionsScreen` (authenticated)                        |
| `MainTabs.tsx`      | Bottom tabs in order: `Profile`, `Favorites`, `Home` (AI chat) (authenticated)           |

## Screens (`src/app/screens`)

| Screen                    | What it does                                                                                     | Key deps                                                                                                              |
| ------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| `auth/PhoneScreen.tsx`    | Phone entry + Google Sign-In                                                                     | `useAuthMutations`, `GoogleSignin`                                                                                    |
| `auth/OtpScreen.tsx`      | OTP verification (SMS User Consent autofill)                                                     | `useAuthMutations`, auth store, `services/sms/smsOtp`                                                                 |
| `HomeScreen.tsx`          | AI Chat: conversation drawer, streaming answers, intent-themed bubbles, virtualized message list (FlatList with `getItemLayout`), queued send with idempotency keys, product grid | `useChatWebSocket`, `useChatMutations`, `ChatDrawer`, `Markdown`, `MessageBubble`, `ProductGrid`, `intentTheme`, `newIdempotencyKey` |
| `FavoritesScreen.tsx`     | Saved products grid (2-column), remove dialog, empty state                                      | `useFavorites`, `ProductCard`, `FavoriteRemoveDialog`                                                                 |
| `PermissionsScreen.tsx`   | App permission statuses (location, camera, microphone, notifications) + request buttons          | `usePermissions`, `checkLocationPermission`, `checkMicrophonePermission`, `permissions` i18n namespace                |
| `ProfileScreen.tsx`       | Edit name/address/location/language, avatar, link Google                                         | `useGetProfileQuery`, `useUpdateProfileMutation`, `PhotoUploader`, `LocationPicker`, `useErrorToastStore`             |

## Components (`src/components`)

| Component                          | Purpose                                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `avatar/Avatar.tsx`                | Image avatar with initials fallback                                                                                |
| `upload/PhotoUploader.tsx`         | Pick → crop (`react-native-image-crop-picker`) → upload → `onUploadComplete(url)`; shows toast + logs local errors |
| `map/LocationPicker.tsx`           | MapLibre (OpenFreeMap/OSM) map picker: tap to place, pin marker, locate-me + zoom +/- overlay buttons; GPS → network fallback via `ProfileScreen`; requests location permission at point of use |
| `feedback/ErrorToast.tsx`          | Global Snackbar rendering `toUserMessage(error, t)`                                                                |
| `feedback/SuccessToast.tsx`        | Global Snackbar rendering success messages from `successToastStore`                                                |
| `feedback/AppErrorBoundary.tsx`    | Crash fallback UI + `log.error` of component stack                                                                 |
| `chat/ChatDrawer.tsx`              | Conversation drawer (list, new chat, delete)                                                                       |
| `chat/Markdown.tsx`                | Renders assistant markdown answers                                                                                 |
| `chat/MessageBubble.tsx`           | Chat message row (user/assistant, error state, retry); intent-themed colors + product-name chip when `search_context.intent` is present |
| `chat/ProductGrid.tsx`             | Product result cards from chat; "similar" action per card                                                          |
| `chat/RetryingThumbnail.tsx`       | Product image via FastImage (cached); retry on load failure; URLs rewritten through the image optimizer (`Config.IMAGE_OPTIMIZER_URL`) |
| `chat/CopyButton.tsx`              | Copy message text                                                                                                  |
| `product/ProductCard.tsx`          | Product card (image, name, price, favorite toggle) — used by favorites grid                                       |
| `product/ProductViewModal.tsx`     | Product detail modal from a card                                                                                   |
| `product/FavoriteRemoveDialog.tsx` | Confirm remove-favorite dialog                                                                                     |

## Features & hooks

| Module                                    | Purpose                                                                                                                                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `features/auth/authStore.ts`              | Zustand: `AuthStep` (phone→otp→authenticated), `User`, tokens; persisted                                                                                      |
| `features/auth/useAuthMutations.ts`       | `sendOtp` / `verifyOtp` / `googleAuth` / `logout` mutations; inline auth errors                                                                               |
| `features/profile/useProfileMutations.ts` | `useGetProfileQuery` (`['profile']`), `updateProfile`, `uploadFile`, `linkGoogle` mutations; `onSuccess` syncs query cache + auth store                       |
| `features/errors/errorToastStore.ts`      | Zustand: single `error` slot + `showError`/`clearError`                                                                                                       |
| `features/feedback/successToastStore.ts`  | Zustand: success toast slot + `showSuccess`/`clearSuccess` (e.g. favorites added/removed)                                                                     |
| `features/chat/types.ts`                  | `ConversationItem`, `ChatMessage`, `ChatProduct`, `ChatMessageDebug`, `ConversationCreateRequest`                                                             |
| `features/chat/chatStream.ts`             | `ChatStreamState` reducer (start/debug/chunk/products/completed/failed/reset), `sendMessageFrame`, `sendSimilarRequestFrame`, `parseChatFrame`, `CHAT_ERROR_CODES` |
| `features/chat/useChatWebSocket.ts`       | WS connection (30 s ping, exponential backoff, max 5 retries, single-slot pending send incl. similar requests); maps wire frames into `ChatStreamState`        |
| `features/chat/useChatMutations.ts`       | `useGetConversationsQuery`, `useGetConversationMessagesQuery`, `useCreateConversationMutation`, `useDeleteConversationMutation` (React Query key `['chats']`) |
| `features/chat/intent.ts`                 | `intentTheme(intent)` — colors + icon for `greeting`/`search`/`general`/`error` intents                                                                       |
| `features/chat/normalize.ts`              | `normalizeChatMessage` / `normalizeConversationItem` — server → app shapes                                                                                    |
| `features/chat/locale.ts`                 | `localeValue()` (pick en/ar/fa) + `newIdempotencyKey()` (randomUUID) + `relativeTime()` (Intl relative timestamps for the drawer)                             |
| `features/favorites/favoritesApi.ts`      | `useGetFavoritesQuery`, `useAddFavoriteMutation`, `useRemoveFavoriteMutation` (React Query key `['favorites']`)                                               |
| `features/favorites/useFavorites.ts`      | Combines the API hooks + success toasts + query invalidation                                                                                                  |
| `features/favorites/types.ts`             | `Favorite` / favorites response types                                                                                                                         |
| `hooks/useAuth.ts`                        | AuthGate logic — which navigation to render                                                                                                                   |
| `hooks/usePermissions.ts`                 | Wraps `services/permissions/permissions.ts` for `PermissionsScreen` (statuses + request handlers)                                                             |
| `hooks/useFavoriteActions.ts`             | Shared add/remove favorite handlers (optimistic-ish, toast feedback)                                                                                          |

## Services (`src/services`)

| Module                            | Role                                                                                                                         |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `api/client.ts`                   | Axios instance (`API_BASE_URL`, 15 s timeout, JSON headers)                                                                  |
| `api/envelope.ts`                 | `unwrapEnvelope` — `{success, data}` check used by auth/profile/favorites/ProductViewModal (not by chat)                      |
| `sms/smsOtp.ts`                   | Android SMS User Consent OTP autofill: `extractOtp`, `subscribeSmsOtp` (DeviceEventEmitter), `startSmsOtpListening` (native `SmsOtp.startListening`); used by `OtpScreen`. Kotlin side under `android/app/src/main/java/com/tea/app/`: `SmsOtpModule.kt`, `SmsConsentActivity.kt`, `SmsUserConsentReceiver.kt` |
| `api/interceptors.ts`             | Bearer token attach, request/response `log.debug` traces, 401 single-flight refresh with queue; refresh failure → clear auth |
| `api/errors.ts`                   | `classifyError` (log) + `toUserMessage` (UI) + `extractApiError` / `extractTranslationKey`                                   |
| `logging/logger.ts`               | `log` instance (levels, redaction, context, console + Sentry transports)                                                     |
| `logging/sentry.ts`               | `initSentry`, `setSentryUser`, `setSentryRoute`                                                                              |
| `logging/globalHandlers.ts`       | `installGlobalHandlers` (ErrorUtils + unhandledrejection)                                                                    |
| `permissions/permissions.ts`      | `react-native-permissions` wrapper: `checkLocationPermission`/`requestLocationPermission` (point-of-use), `checkMicrophonePermission`, notification permission; logs + maps statuses |
| `storage.ts`                      | AsyncStorage token store                                                                                                     |

## i18n (`src/i18n`)

`react-i18next`, namespaces: `auth`, `chat`, `common`, `nav`, `profile`, `error`, `permissions` — locales `en`/`ar`/`fa`. Every new label must exist in all three locale files; every user-facing error key goes in `error.json` (see [error-handling.md](error-handling.md)). The `chat` namespace holds the AI Chat screen labels; `permissions` holds the permission screen labels.

## Theme (`src/theme`), constants (`src/constants/countries.ts`), types (`src/types`)

- `theme/index.ts` — Material 3 theme
- `countries.ts` — dial codes for `PhoneScreen`
- `types/api.ts` — API envelope (`ApiResponse<T>`), `User`, `UploadFileResponse` (raw, **no** envelope), error body
- `types/product.ts` — `Product` shape used by chat results + favorites
- `types/navigation.ts` — stack/tab param lists
- `types/env.d.ts` — react-native-config typing (`API_BASE_URL`, `ENV`, `GOOGLE_CLIENT_ID`, `SENTRY_DSN`, `IMAGE_OPTIMIZER_URL`)

## Key flows

### Avatar change

```
ProfileScreen → PhotoUploader
  pickImage (crop 800×800)
  → POST /files/upload?max_size=400  (multipart; returns RAW FileUploadResponse)
  → onUploadComplete(url) → local state → Save → PATCH /users/me/profile {avatar_url}
```

Note: `/files/upload` returns `{file_name, url, …}` **without** the `{success, data}` envelope — the upload mutation returns `response.data` directly. Other endpoints (profile GET/PATCH, auth) DO use the envelope; read them as `response.data.data`.

### Sign in

```
PhoneScreen (phone → sendOtp) → OtpScreen (verifyOtp) → authStore authenticated
   └── GoogleSignIn → POST /auth/google {id_token, client_type: 'android'}
```

### Chat message (see [chat-integration.md](chat-integration.md))

```
HomeScreen → useChatWebSocket (ws(s)://{host}/ws/chat/{conversationId}?token=…)
  send_message {content, idempotency_key, include_saved_message: true}
  ← assistant_start (search_context) → text_chunk* → product_cards → message_saved → assistant_end
  similar_request {product_id, product_name, idempotency_key} → streams a new message with its own product grid
```

### Product images

```
ProductCard / ProductGrid → RetryingThumbnail
  url = Config.IMAGE_OPTIMIZER_URL?url={encoded image url}
  FastImage (disk + memory cache, resizeMode) → on failure: retry, then placeholder
```

### Error surfacing

```
Any catch → mutations log via onError (classifyError)
          → UI: showError(error) → ErrorToast → toUserMessage → localized Snackbar
```

## Related

- [Logging](logging.md) · [Error Handling](error-handling.md) · [Sentry](sentry.md) · [Android Build](android-build.md) · [Chat Integration](chat-integration.md)