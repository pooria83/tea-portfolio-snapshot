# Authentication & Authorization

## Auth Flow Overview

The app uses a two-step phone OTP flow with optional Google OAuth. Authentication state is managed by the `auth` Redux slice. The web app has **login only — there is no register page or register endpoint call** (the backend exposes `/auth/register`, but the web UI never uses it).

```
                    ┌─────────┐
                    │  Login  │
                    │  Page   │
                    └────┬────┘
                    ┌────┴────┐
         ┌──────────┤  Phone  ├──────────┐
         │          └─────────┘          │
         ▼                               ▼
   ┌──────────┐                  ┌──────────────┐
   │ Send OTP │                  │ Google Sign-In│
   └────┬─────┘                  └──────┬───────┘
        │                               │
        ▼                               ▼
   ┌──────────┐                  ┌──────────────┐
   │ Verify   │                  │ Google       │
   │ OTP      │                  │ Callback     │
   └────┬─────┘                  └──────┬───────┘
        │                               │
        └───────────┬───────────────────┘
                    ▼
            ┌──────────────────┐
            │  Authenticated   │
            │ (cookie session) │
            └──────────────────┘
```

## Auth Slice State Machine

The `auth` slice defines three steps:

```typescript
type AuthStep = "phone" | "otp" | "authenticated";
```

| Step            | Description                                                       |
| --------------- | ----------------------------------------------------------------- |
| `phone`         | Initial state — user enters phone number                          |
| `otp`           | OTP sent — user enters 6-digit code                               |
| `authenticated` | Login successful — httpOnly session cookies set, user info loaded |

### State Shape

```typescript
interface AuthState {
  step: AuthStep;
  phone: string;
  user: User | null; // {id, name, phone, role, email}
  preferredView: UserRole; // "admin" | "seller"
  loading: boolean;
  error: string | null;
}
```

No token fields exist in the slice — JWTs live exclusively in httpOnly cookies.

### Async Thunks

| Thunk                                          | Trigger              | Side Effect                                                                                 |
| ---------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------- |
| `bootstrapAuth()`                              | App mount            | `GET /users/me` (cookie-authenticated) → restores `step: "authenticated"` + user on success |
| `sendOtp(phone)`                               | User submits phone   | POST `/auth/send-otp` → sets `step: "otp"`                                                  |
| `verifyOtp(otp)`                               | User submits OTP     | POST `/auth/verify-otp`, then `GET /users/me` → sets `step: "authenticated"`                |
| `googleCodeAuth({code, redirect_uri, state?})` | Google callback page | POST `/auth/google/code`, then `GET /users/me` → same as verifyOtp                          |

Thunks wrap `baseApi` endpoints; the login thunks follow up with `GET /users/me` and map that response into the slice's `User` shape. The login page consumes them via the `useLoginFlow` hook.

### Actions (Reducers)

| Action                   | Effect                                                                        |
| ------------------------ | ----------------------------------------------------------------------------- |
| `setPhone(phone)`        | Stores the phone number entered on step one                                   |
| `clearError()`           | Clears `error` state                                                          |
| `logout()`               | Resets to initial state; also triggers the store's logout listener middleware |
| `setPreferredView(view)` | Sets admin/seller view preference, persists to localStorage                   |

### Session Restore & Logout

- **Restore**: `AuthBootstrap` (`src/components/providers/AuthBootstrap.tsx`) is rendered inside `ReduxProvider` and dispatches `bootstrapAuth()` on mount. The `GET /users/me` request is authenticated implicitly by the cookie, so sessions survive reloads without any stored tokens.
- **Logout**: the sidebar dispatches `logout()`. A listener middleware in `store.ts` then calls `POST /auth/logout` (revokes the refresh token server-side) and `resetApiState()` to flush all cached RTK Query data. `tea_preferred_view` intentionally survives logout so an admin's view choice is restored on next login.

### Refresh Rotation

- On any 401, RTK Query's `baseQueryWithReauth` calls `POST /auth/refresh` with an **empty body** — the refresh token travels in its httpOnly cookie. The response sets rotated cookies.
- An `async-mutex` prevents concurrent refresh requests.
- If the refresh fails, the base query dispatches `logout()` — the user is signed out automatically instead of looping on failing requests.

## Cookies & CSRF

- Auth responses set two httpOnly cookies: `access_token` and `refresh_token`.
- Cookie attributes: `HttpOnly`, `Secure` when `settings.cookie_secure`, `SameSite=Lax`, host-only (no `Domain`), path `/`.
- `POST /auth/logout` revokes the refresh token and clears both cookies.
- When auth is sourced from cookies, `get_current_user` requires the `X-Requested-With: XMLHttpRequest` header (CSRF protection). Requests without it fail with `E.CSRF_HEADER_MISSING`. The RTK Query `baseQuery` sends `credentials: "include"` and `x-requested-with: XMLHttpRequest` on all requests (cross-origin `NEXT_PUBLIC_API_URL`). No `Authorization` header is ever attached.
- Auth responses still include tokens in the JSON body for non-web clients, but the web app ignores them entirely.

## Google OAuth State

- `POST /auth/google/nonce` (public, no auth) returns `{state}` only — `secrets.token_urlsafe(32)` stored in Redis (`google_oauth_state:{state}`, consumed once via `GETDEL`, TTL = `oauth_state_expire_seconds`).
- The login page fetches it, stores the intended purpose (`login` / `link`) in `sessionStorage` under `google_oauth_<state>`, then redirects to Google with the `state` parameter (no nonce parameter).
- The callback page (`/auth/google/callback`) reads the returned `code` + `state`, looks up the purpose from `sessionStorage` (default `login`), and POSTs `/auth/google/code` with `{code, redirect_uri, state}` (link flow POSTs `/users/me/link/google` instead). `E.INVALID_OAUTH_STATE` is returned for missing/replayed states.
- Mobile uses a separate state-less flow: `POST /auth/google/mobile` (login) and `POST /users/me/link/google/mobile` (link).

## Role-Based Access Control (RBAC)

Two roles: **admin** and **seller**.

Authorization is enforced at two levels:

- `(dashboard)/admin/*` — Admin-only pages
- `(dashboard)/seller/*` — Seller pages (any authenticated user can navigate there)
- Backend `get_admin_user` re-checks `user.role == "admin"` on every admin request

### Dashboard Route Guard

`src/app/[locale]/(dashboard)/layout.tsx` centralizes both guards client-side:

1. **Hydration gate** — `useSyncExternalStore` returns `false` during SSR/first render so nothing flashes before hydration.
2. **Loading skeleton** — while `auth.loading` (e.g. `bootstrapAuth` in flight), a centered skeleton renders instead of the dashboard.
3. **Unauthenticated redirect** — once hydrated and not loading, `step !== "authenticated"` triggers `router.replace("/login")`.
4. **Client-side role guard** — an authenticated non-admin opening `/admin*` is redirected to `/seller`.

### Switch View (preferredView)

Admin users get a "Switch to Seller/Admin" button at the top of the sidebar:

- `effectiveRole = isAdmin ? preferredView : user.role` decides which nav set (`AppSidebar.tsx`) renders
- Dispatching `setPreferredView("seller" | "admin")` updates Redux and persists `tea_preferred_view` to `localStorage`
- `router.push()` switches between `/admin` and `/seller`
- Because `preferredView` survives logout (see above), the choice is restored on next login/session restore

## Account Linking

Users can link accounts from the profile page:

| Flow           | Endpoint                                                               | Dialog                                   |
| -------------- | ---------------------------------------------------------------------- | ---------------------------------------- |
| Phone → Google | `POST /auth/google/nonce` then redirect → `POST /users/me/link/google` | Redirect-based Google OAuth with `state` |
| Google → Phone | `POST /users/me/link/phone/send-otp` then `/verify`                    | LinkPhoneDialog                          |

Linking returns `409 Conflict` if the target identity is already claimed by another account.
