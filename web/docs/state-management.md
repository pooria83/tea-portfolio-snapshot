# State Management

## Architecture

The app uses **Redux Toolkit** (`configureStore`) with **RTK Query** for API data fetching.

```
┌────────────────────────────────────────────────────────────┐
│                       Redux Store                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                     auth slice                        │  │
│  │ step | phone | user | preferredView | loading | error │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                 RTK Query API slices                  │  │
│  │  baseApi → profileApi | storeApi | productApi         │  │
│  │           chatApi | adminApi | anonymousApi | fileApi │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
          │                          │
          ▼                          ▼
   ┌─────────────┐          ┌──────────────┐
   │ httpOnly    │          │  React       │
   │ auth cookies│          │  Components  │
   └─────────────┘          └──────────────┘
```

There are **no token fields in Redux**. JWTs live exclusively in httpOnly cookies set by the API; the only browser storage the store touches is `tea_preferred_view` in `localStorage`.

## Store Configuration

`src/store/store.ts`:

```typescript
const logoutListener = createListenerMiddleware();
logoutListener.startListening({
  actionCreator: logout,
  effect: async (_action, listenerApi) => {
    try {
      await listenerApi.dispatch(baseApi.endpoints.logout.initiate()).unwrap();
    } catch (error) {
      console.warn("auth_logout_api_failed", error);
    }
    listenerApi.dispatch(baseApi.util.resetApiState());
  },
});

export const makeStore = () =>
  configureStore({
    reducer: {
      auth: authReducer,
      [baseApi.reducerPath]: baseApi.reducer,
    },
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware().prepend(logoutListener.middleware).concat(baseApi.middleware),
  });
```

The `logout` listener middleware centralizes sign-out side effects: when the `logout` action is dispatched anywhere (e.g. the sidebar), it calls `POST /auth/logout` to revoke the session server-side and then `resetApiState()` to drop all cached RTK Query data.

## Auth Slice (`src/store/slices/auth.ts`)

Manages the authentication lifecycle as a state machine.

### State

```typescript
interface AuthState {
  step: AuthStep; // "phone" | "otp" | "authenticated"
  phone: string;
  user: User | null;
  preferredView: UserRole; // "admin" | "seller"
  loading: boolean;
  error: string | null;
}
```

Tokens are never stored here — auth responses set httpOnly cookies and the slice only keeps the mapped `User` (`mapUser` normalizes `GET /users/me` into `{id, name, phone, role, email}`).

### Reducers

| Action             | Effect                                                            |
| ------------------ | ----------------------------------------------------------------- |
| `setPhone`         | Stores the phone number entered on step one                       |
| `logout`           | Resets to initial state (triggers the logout listener middleware) |
| `clearError`       | Clears `error` state                                              |
| `setPreferredView` | Sets admin/seller view preference, persists to localStorage       |

### Async Thunks

Thunks wrap `baseApi` endpoints; the login/restore thunks then load the user via `getMe`:

| Thunk                                          | HTTP Calls                                     | On Success                                                    |
| ---------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| `bootstrapAuth()`                              | `GET /users/me`                                | Sets user + `step: "authenticated"`, restores `preferredView` |
| `sendOtp(phone)`                               | `POST /auth/send-otp`                          | Stores phone, sets `step: "otp"`                              |
| `verifyOtp(otp)`                               | `POST /auth/verify-otp`, then `GET /users/me`  | Sets user + `step: "authenticated"`                           |
| `googleCodeAuth({code, redirect_uri, state?})` | `POST /auth/google/code`, then `GET /users/me` | Same as verifyOtp                                             |

### Session Restore on Mount

`src/components/providers/AuthBootstrap.tsx` is rendered inside `ReduxProvider`. On mount it dispatches `bootstrapAuth()`, which calls `GET /users/me`; the request is authenticated implicitly by the httpOnly cookie. On success the user lands in `step: "authenticated"` with `preferredView = stored tea_preferred_view ?? user.role`; on failure the app stays unauthenticated and the dashboard layout redirects to `/login`.

### Async Thunk States

Each thunk dispatches three actions:

- `pending` → sets `loading: true`, clears `error` (except `bootstrapAuth`)
- `fulfilled` → sets `loading: false`, updates state based on response
- `rejected` → sets `loading: false`, sets `error` (thunks use `rejectWithValue(extractApiError(...))`)

## RTK Query API (`baseApi`)

`src/store/api/baseApi.ts` is the foundation for all API communication.

### Features

- **Base query** with `fetchBaseQuery` pointing to `NEXT_PUBLIC_API_URL` (fallback `http://localhost:8000/api/v1`)
- **Cookie-only auth**: `credentials: "include"` plus `X-Requested-With: XMLHttpRequest` (CSRF header) set in `prepareHeaders` — no `Authorization` header, no token injection from state
- **Automatic refresh** on 401 via `POST /auth/refresh` (empty body — the cookie carries the token), serialized with an `async-mutex`; a failed refresh dispatches `logout()`
- **18 tag types**: `Product`, `Order`, `Customer`, `Settings`, `Profile`, `Store`, `LLMModels`, `LLMSettings`, `EmbedModels`, `PromptTemplates`, `SystemSettings`, `ScraperHeaders`, `CronProducts`, `EmbeddingCronProducts`, `AdminChats`, `Chats`, `EvalQueries`, `EvalMetrics`

### Endpoints

Endpoints are injected into `baseApi` using `injectEndpoints`. `baseApi` itself defines the auth/user core (`sendOtp`, `verifyOtp`, `googleCodeAuth`, `googleNonce`, `logout`, `getMe`); feature slices add their own:

| API Slice      | Endpoints                                                                                                                                                                                                                                  | Tags                          |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| `profileApi`   | `getProfile` (GET `/users/me/profile`), `updateProfile` (PATCH), `linkPhone`, `verifyLinkPhone`, `linkGoogle`                                                                                                                              | `Profile`                     |
| `storeApi`     | `getCategories`, `getStoreTypes`, `getCountries`, `getCurrencies`, `getMyStores`, `getStore`, `createStore`, `updateStore`, `deleteStore`, `getStoreMembers`, `addStoreMember`, `removeStoreMember`                                        | `Store`                       |
| `productApi`   | catalog lookups (`getProductTypes`, `getCategoryTree`, `getProductTypeAttributes`, `getBrands`, …), `getMyProductsStats`, `getMyProductsPage`, `getStoreProduct`, `createStoreProduct`, `updateStoreProduct`, `generateProductDescription` | `Product`                     |
| `chatApi`      | `getMyChats`, `createConversation`, `getChatMessages`, `deleteConversation`                                                                                                                                                                | `Chats`                       |
| `adminApi`     | LLM models/keys/settings, embed models, prompt templates, system settings, scraper headers, cron products + embeddings, admin chats, search-eval                                                                                           | `LLMModels`, `EmbedModels`, … |
| `anonymousApi` | `getAnonymousChatSession` (public anon WS token), `getRandomProducts`                                                                                                                                                                      | —                             |
| `fileApi`      | `uploadFile({file, maxSize})` → `POST /files/upload?max_size=N`                                                                                                                                                                            | —                             |

## Typed Hooks

`src/store/hooks.ts`:

```typescript
export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();
export const useAppStore = useStore.withTypes<AppStore>();
```

Use these instead of raw `useDispatch`/`useSelector` for proper typing.

## Persistence

The Redux store itself is **not persisted** — sessions survive reloads because the httpOnly auth cookie is sent automatically and `bootstrapAuth()` rehydrates the user on mount.

The single `localStorage` key the store writes is `tea_preferred_view`:

- Written by the `setPreferredView` reducer
- Read when a login/session-restore thunk fulfills (`preferredView = getStoredPreferredView() ?? user.role`)
- Intentionally **not** cleared on logout, so an admin's view choice survives re-login

## Best Practices

- **All API calls** use RTK Query `injectEndpoints` — do not use raw `fetch`
- **Transform responses** with `transformResponse` to unwrap the `{success, data, meta}` API envelope
- **Invalidate tags** after mutations to auto-refetch relevant queries
- **Use typed hooks** (`useAppDispatch`, `useAppSelector`) everywhere
- **Keep slice reducers pure** — side effects belong in thunks or RTK Query
