# Authentication & Security

Everything about identity: JWT lifecycle, refresh rotation, OTP, Google sign-in, API keys, RBAC, rate limiting, and the brute-force lockout.

## Identity Model

- `users` table holds email/username/password_hash/phone/google_id/role. `role` is a plain string: `"user"` (default) or `"admin"`.
- Credentials hashed with **bcrypt** (`app/core/password.py`).
- LLM API keys are a separate concern — see [LLM Management](llm-management.md) (Fernet, not user-facing).

## JWT

`app/core/jwt.py` — HS256, signed with `jwt_secret_key`.

All tokens are signed with `aud`/`iss` claims (`jwt_audience`/`jwt_issuer`, both default `product-graph-api`) that are validated on decode.

| Token | Lifetime | Claims | Purpose |
|---|---|---|---|
| access | 30 min (`access_token_expire_minutes`) | `sub` (user uuid), `role`, `type: "access"`, `exp`, `aud`, `iss` | every authenticated request |
| refresh | 7 days (`refresh_token_expire_days`) | `sub`, `jti`, `type: "refresh"`, `exp`, `aud`, `iss` | mint new access tokens |
| anon | 10 min | `sub` (random uuid), `role: "user"`, `type: "anon"`, `exp`, `aud`, `iss` | WebSocket-only identity for public anonymous chat — deliberately **no Postgres user**; `get_jwt_user`/`decode_access_token` reject any non-`access` type, so the token is useless outside the WS |

**Rotation** (`auth_service.refresh_access_token`):
1. Decode refresh token → look up by **hash** (`sha256`) in `refresh_tokens`.
2. Not found → `REFRESH_TOKEN_INVALID` only.
3. Found but already `revoked` → **reuse detected** → revoke *all* of the user's sessions and raise `REFRESH_TOKEN_REUSE`.
4. Else: revoke the presented token, insert a new hashed row, return a fresh pair.

Consequences: refresh tokens are single-use; a leaked token can't be replayed once rotated; the attacker who reuses the *newest* token trips reuse detection.

## Cookie Transport (httpOnly)

All auth responses (`register`, `login`, `refresh`, OTP verify, Google) set two
**httpOnly, SameSite=Lax** cookies alongside the JSON body (`app/core/cookies.py`):

| Cookie | Value | Lifetime |
|---|---|---|
| `access_token` | access JWT | 30 min (matches the token) |
| `refresh_token` | refresh JWT | 7 days (matches the token) |

- Browsers store the cookies automatically — no bearer header needed for
  cookie-mode clients (web app).
- **CSRF protection**: state-changing requests authenticated **by cookie**
  must send the `X-Requested-With: XMLHttpRequest` header; missing/mismatched
  header → `401 csrf_header_missing`. Bearer-header clients (mobile) are
  exempt — they never rely on ambient credentials.
- `clear_auth_cookies` removes both cookies (`POST /auth/logout`, refresh failure).
- Non-cookie clients keep using `Authorization: Bearer` — both transports
  work against the same endpoints.

## OTP (phone)

- `POST /auth/send-otp` → 6-digit code, TTL `otp_expire_seconds`, delivered via Twilio.
- Redis keys: `otp:{phone}` (code), `otp_send:{phone}` + `otp_verify:{phone}` (counters, 600s TTL) — caps `otp_max_send_per_phone` and `otp_max_verify_attempts`.
- `POST /auth/verify-otp` → compares, **auto-creates the user by phone** if unknown, returns tokens.
- Dev mode (`twilio_bypass`): code logged to console, magic code `123456` accepted.
- The same machinery powers phone linking: `POST /users/me/link/phone/send-otp` + `verify`.

## Session Endpoints

- `POST /auth/refresh` — rotation described above.
- `POST /auth/logout` — revokes the presented refresh token (body or
  `refresh_token` cookie) and clears both cookies; rate-limited 10/min.

## Google OAuth

- `POST /auth/google` — `{"id_token", "client_type"}`; token verified against the configured per-platform client IDs (`google_web_client_id`, `google_android_client_id`, `google_ios_client_id`) via Google's discovery + JWKS.
- Branch on result: existing `google_id` → login; matching email → link (accounts merged); none → auto-register.
- `POST /auth/google/code` — OAuth authorization-code variant; callback redirect URIs must be in `ALLOWED_REDIRECT_URIS`.
- **`POST /auth/google/nonce`** — mints a one-time OAuth **state** value: stored in Redis under `google_oauth_state:{state}` (`SETEX`, TTL `oauth_state_expire_seconds`, default 600s). The client includes it in the authorization-code flow and the callback consumes it with a one-time `GETDEL` — a state can never be replayed, preventing CSRF on the OAuth callback.
- `POST /users/me/link/google` — attach `google_id` to the current account.
- `POST /users/me/link/google/mobile` — same linking for mobile clients.

## API Keys (service-to-service)

- `X-API-Key` checked by `get_api_key_user` against **two sources**: the global
  `settings.api_key`, or a **per-user key stored in `users.api_key`** (unique,
  indexed column). A per-user key authenticates as that user row.
- The AI Engine is the only current global-key consumer (every `AIEngineClient`
  call carries it).
- Admin endpoints also accept it (`get_admin_user` falls back to `get_api_key_user`).
- `get_current_user` resolves `X-API-Key` (global or per-user) → JWT bearer → cookie (CSRF-guarded), in that order.

## Webhook Auth

- `verify_webhook_secret` dependency guards AI Engine callbacks
  (`POST /webhook/embedding-result`): accepts the shared secret via the
  `X-Webhook-Secret` header or a `?token=` query parameter. When
  `webhook_secret` is unset, verification is disabled (local dev without an engine).

## RBAC

| Role/check | Enforcement |
|---|---|
| authenticated user | `Depends(get_authenticated_user)` — JWT required |
| admin | `Depends(get_admin_user)` — `role == "admin"` else `403 FORBIDDEN` |
| store owner | `_verify_store_owner` — `store.owner_id == user.id` (strict-owner routes) |
| store member (owner/manager) | `StoreMember` lookup (member-list view) |
| JWT-vs-API-key | `get_current_user` — `X-API-Key` (global or per-user) → user id, else JWT/cookie → token subject |

## Rate Limiting (`app/core/rate_limit.py` + `RateLimit` DI in `core/deps.py`)

`Depends(RateLimit(max_requests=N, window_seconds=W))` per route — an atomic
Lua `INCR`+`EXPIRE` script on `rl:{user_id}:{route}` (TTL set only on the first
increment; falls back to plain `INCR`+`EXPIRE` if the script fails). Over limit
→ `429 RATE_LIMITED` with `X-RateLimit-Remaining: 0`. Limits are per-route; see [API Reference §Rate Limits](api-reference.md).

**Login lockout** (progressive): `login_attempts:{email}` increments on failed password; after 5 failures the account locks for `15 min × 2^(n−1)` — 15, 30, 60, 120… minutes. Locked → `429 ACCOUNT_LOCKED`. Success resets the counter.

## WebSocket Auth

`_authenticate_ws` — token from `Sec-WebSocket-Protocol` subprotocol frame, the
`access_token` **cookie**, `?token=`, or `Authorization` header; failure →
`WEBSOCKET_AUTH_REQUIRED`. The accepted subprotocol is echoed back in the
handshake response (`accept(subprotocol=...)`), so clients must select one of
the advertised subprotocols. Sets `request_id_var` to `ws_{user_id}` for trace
continuity.

Anonymous chat sockets authenticate with an **anon** token (see [JWT](#jwt)) —
minted by `POST /chat/anonymous-session`, valid 10 minutes, WS-only.

## Transport & Headers

- `SecurityHeadersMiddleware` — sensible defaults (X-Content-Type-Options, frame options, CSP on HTML routes).
- TLS/secret handling is deployment-side; see [Deployment](deployment.md). Secrets never appear in logs (`logging.py` redacts).
