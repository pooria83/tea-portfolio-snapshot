# API Integration

All API communication uses **RTK Query** via `injectEndpoints`. Do not use raw `fetch` (the legacy `src/services/` directory has been removed).

## API Envelope Format

All backend responses follow a standard envelope:

### Success

```json
{
  "success": true,
  "data": { ... },
  "meta": { "total": 10, "page": 1 }
}
```

### Error

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "User not found",
    "translation_key": "user_not_found",
    "request_id": "abc123"
  }
}
```

Errors always include `translation_key` (see `docs/i18n.md`) — frontend maps it to the `errors` namespace via `extractTranslationKey()`.

## RTK Query Endpoint Pattern

### Query (GET)

```typescript
import { baseApi } from "./baseApi";

export const profileApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getProfile: builder.query<UserProfile, void>({
      query: () => "/users/me/profile",
      transformResponse: (res: ApiResponse<UserProfile>) => res.data,
      providesTags: ["Profile"],
    }),
  }),
});

export const { useGetProfileQuery } = profileApi;
```

### Mutation (POST/PUT/DELETE)

```typescript
updateProfile: builder.mutation<UserProfile, UserProfileUpdate>({
  query: (body) => ({
    url: "/users/me/profile",
    method: "PATCH",
    body,
  }),
  transformResponse: (res: ApiResponse<UserProfile>) => res.data,
  invalidatesTags: ["Profile"],
});
```

### File Upload (multipart/form-data)

```typescript
uploadFile: builder.mutation<{ url: string }, { file: File; maxSize?: number }>({
  query: ({ file, maxSize }) => {
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams();
    if (maxSize) params.set("max_size", String(maxSize));
    const queryString = params.toString();
    return {
      url: `/files/upload${queryString ? `?${queryString}` : ""}`,
      method: "POST",
      body: formData,
      formData: true,
    };
  },
  transformResponse: (res: ApiResponse<{ url: string }>) => res.data,
});
```

## Available Endpoints

> Full RTK Query hook tables (admin, product, chat) live in `AGENTS.md`. Key endpoints per API file:

### Profile API (`profileApi`)

| Hook                         | Method | Path                            | Description              |
| ---------------------------- | ------ | ------------------------------- | ------------------------ |
| `useGetProfileQuery`         | GET    | `/users/me/profile`             | Get current user profile |
| `useUpdateProfileMutation`   | PATCH  | `/users/me/profile`             | Update profile fields    |
| `useLinkPhoneMutation`       | POST   | `/users/me/link/phone/send-otp` | Send phone link OTP      |
| `useVerifyLinkPhoneMutation` | POST   | `/users/me/link/phone/verify`   | Verify phone link OTP    |
| `useLinkGoogleMutation`      | POST   | `/users/me/link/google`         | Link Google account      |

Avatar upload is **not** a profile endpoint — it goes through the file API: `useUploadFileMutation({file, maxSize: 400})` → `POST /files/upload?max_size=400`.

### Store API (`storeApi`)

| Hook                           | Method | Path                            | Description                             |
| ------------------------------ | ------ | ------------------------------- | --------------------------------------- |
| `useGetCategoriesQuery`        | GET    | `/categories?locale=`           | Get all categories (locale-aware)       |
| `useGetStoreTypesQuery`        | GET    | `/store-types?locale=`          | Get all store types (locale-aware)      |
| `useGetCountriesQuery`         | GET    | `/stores/countries?locale=`     | Country options (code + localized name) |
| `useGetCurrenciesQuery`        | GET    | `/stores/currencies?locale=`    | Currency options (code, name, symbol)   |
| `useGetMyStoresQuery`          | GET    | `/stores/my`                    | Get current seller's stores             |
| `useGetStoreQuery`             | GET    | `/stores/{id}`                  | Get store by ID                         |
| `useCreateStoreMutation`       | POST   | `/stores`                       | Create a new store                      |
| `useUpdateStoreMutation`       | PATCH  | `/stores/{id}`                  | Update existing store                   |
| `useDeleteStoreMutation`       | DELETE | `/stores/{id}`                  | Delete a store                          |
| `useGetStoreMembersQuery`      | GET    | `/stores/{id}/members`          | List store members (owner/manager)      |
| `useAddStoreMemberMutation`    | POST   | `/stores/{id}/members`          | Add member                              |
| `useRemoveStoreMemberMutation` | DELETE | `/stores/{id}/members/{userId}` | Remove member                           |

### Product API (`productApi`) — light lists + on-demand detail

| Hook                                    | Method | Path                                                           | Description                                                                                       |
| --------------------------------------- | ------ | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `useLazyGetMyProductsPageQuery`         | GET    | `/stores/my/products?skip=&limit=&q=&store_id=`                | Paginated **`ProductListItem[]`** (16-field light card — no variants/images/descriptions payload) |
| `useGetMyProductsStatsQuery`            | GET    | `/stores/my/products/stats`                                    | `{total, active}` counts (Redis-cached 60s server-side)                                           |
| `useGetStoreProductQuery`               | GET    | `/stores/{storeId}/products/{productId}`                       | Full `ProductResponse` detail (Redis-cached 5 min server-side)                                    |
| `useCreateStoreProductMutation`         | POST   | `/stores/{storeId}/products`                                   | Create product                                                                                    |
| `useUpdateStoreProductMutation`         | PUT    | `/stores/{storeId}/products/{productId}`                       | Update product                                                                                    |
| `useGenerateProductDescriptionMutation` | POST   | `/stores/{storeId}/products/{productId}/generate-descriptions` | Run AI description generation                                                                     |

There is no per-store paginated list hook and no delete mutation in this slice — `getMyProductsPage` accepts a `store_id` filter, and the only list export consumed by pages is the lazy query, fed into `useInfiniteProducts` (`seller/products`). The slice also exposes catalog lookups used by the product form (`getProductTypes`, `getAttributeGroups`, `getCategoryTree`, `getProductTypeAttributes`, `getImageViewTypes`, `getBrands`).

**Product-view modal loads its own detail.** List pages (`seller/products`, home slider) render `ProductListItem` cards and pass only `storeId` + `productId` to `ProductViewDialog` — the dialog's `ProductView` fetches the full `ProductResponse` via `useGetStoreProductQuery` on open. `initialData` is intentionally no longer passed from lists.

### Chat API (`chatApi`) — conversation metadata (messages stream over WebSocket)

| Hook                            | Method | Path                              | Description                                                  |
| ------------------------------- | ------ | --------------------------------- | ------------------------------------------------------------ |
| `useGetMyChatsQuery`            | GET    | `/chats`                          | List conversations (sidebar)                                 |
| `useCreateConversationMutation` | POST   | `/chats` (`{locale, create_new}`) | Start new conversation                                       |
| `useGetChatMessagesQuery`       | GET    | `/chats/{id}/messages`            | Load persisted message history (supports `cursor` + `limit`) |
| `useDeleteConversationMutation` | DELETE | `/chats/{id}`                     | Delete conversation                                          |

### Admin API (`adminApi`) — selected endpoints

> Full hook table lives in `AGENTS.md`. Notable additions:

| Hook                                                               | Method       | Path                            | Description                                                                                                                                |
| ------------------------------------------------------------------ | ------------ | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `useGetEmbedModelsQuery`                                           | GET          | `/admin/embed-models`           | Embedding model catalog                                                                                                                    |
| `useGetScraperHeadersQuery`                                        | GET          | `/admin/scraper-headers`        | Scraper header overrides                                                                                                                   |
| `useUpdateScraperHeaderMutation` / `useClearScraperHeaderMutation` | PUT / DELETE | `/admin/scraper-headers/{name}` | Set or clear a header override                                                                                                             |
| `useGetAdminChatsQuery`                                            | GET          | `/admin/chats?skip=&limit=`     | Paginated `{items: AdminConversationItem[], meta}` — rows carry `title` and `user_identifier` (rendered as an "anonymous" badge when null) |

### File API (`fileApi`)

| Hook                    | Method | Path                       | Description                                                           |
| ----------------------- | ------ | -------------------------- | --------------------------------------------------------------------- |
| `useUploadFileMutation` | POST   | `/files/upload?max_size=N` | Upload any file (`{file, maxSize?}`, optional `max_size` query param) |

### Anonymous API (`anonymousApi`) — public endpoints (no auth)

| Hook                                 | Method | Path                      | Description                                                                                                                          |
| ------------------------------------ | ------ | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `useGetAnonymousChatSessionMutation` | POST   | `/chat/anonymous-session` | Mint 10-min WS-only anon token + conversation (`{token, conversation}`)                                                              |
| `useGetRandomProductsQuery`          | GET    | `/public/products/random` | Random active products for the home slider (limit ≤ 20) — returns **`ProductListItem[]`** (light cards, server-side Redis-cached 1h) |

Used by the public home page only — see [website-home.md](website-home.md).

## WebSocket Chat (AI Chat page)

- URL: `wss(s)://{apiHost}/ws/chat/{conversationId}` (scheme derived from the API base URL)
- Hook: `useChatSocket` (`src/hooks/useChatSocket.ts`) — ping every 30 s, exponential backoff reconnect (max 30 s); `tokenOverride` for anonymous sessions; `onFrame` listener receives parsed frames
- Liveness: a ping with no received frame in response increments the missed counter — after **2 missed pings** (`MAX_MISSED_PINGS = 2`) the socket is force-closed to trigger a reconnect; any incoming frame resets the counter
- Tab visibility: on `visibilitychange` → visible, if the socket is `CLOSED`/`CLOSING` the hook reconnects immediately (backoff reset)
- Terminal close: close code **4001** sets status to `closed` and does **not** schedule a reconnect (any other close retries)
- Chat state: `useChat` (`src/hooks/useChat.ts`) + `chatReducer` in `src/lib/chatReducer.ts`
- Frames: `send_message` (client → server, with `idempotency_key`); `similar_request` (find-similar on a product card); `assistant_start`, `debug`, `text_chunk`, `product_cards`, `assistant_end`, `error`, `message_saved` (server → client)
- Streaming state managed by `chatReducer` in `src/lib/chatReducer.ts`
- Errors: server sends error frames with codes from `CHAT_ERROR_CODES` (`src/lib/chat.ts`)
- **Authentication**: anonymous sessions pass their token as the `Sec-WebSocket-Protocol` subprotocol value via `tokenOverride` (the browser requires the server to echo the exact subprotocol back). Logged-in chat sends **no token at all** — the connection is authenticated implicitly by the httpOnly `access_token` cookie during the WS handshake. There is no `?token=` query param or `Authorization` header fallback.

## Base API Configuration

`src/store/api/baseApi.ts`:

```typescript
const baseQuery = fetchBaseQuery({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  prepareHeaders: (headers) => {
    headers.set("X-Requested-With", "XMLHttpRequest");
    return headers;
  },
  credentials: "include",
});
```

- `credentials: "include"` lets the API read/write the httpOnly auth cookies on the cross-origin `NEXT_PUBLIC_API_URL` — **cookie-only auth, no `Authorization` header is ever attached**.
- `x-requested-with: XMLHttpRequest` satisfies the CSRF check the API applies to cookie-sourced auth.

### Token Refresh on 401

When a 401 is received, the base query attempts to refresh the session:

```typescript
const baseQueryWithReauth: BaseQueryFn = async (args, api, extraOptions) => {
  await mutex.waitForUnlock();
  let result = await baseQuery(args, api, extraOptions);
  if (result.error && result.error.status === 401) {
    if (mutex.isLocked()) {
      await mutex.waitForUnlock();
      result = await baseQuery(args, api, extraOptions);
    } else {
      const release = await mutex.acquire();
      try {
        const refreshResult = await baseQuery(
          { url: "/auth/refresh", method: "POST" },
          api,
          extraOptions,
        );
        if (refreshResult.data) {
          // Retry original request with the rotated cookie
          result = await baseQuery(args, api, extraOptions);
        } else {
          api.dispatch(logout());
        }
      } catch {
        api.dispatch(logout());
      } finally {
        release();
      }
    }
  }
  return result;
};
```

- `POST /auth/refresh` carries an **empty body** — the refresh token travels in its httpOnly cookie, and the response sets the rotated cookies.
- A failed refresh dispatches `logout()` (auto sign-out; the store's logout listener then clears the server session and RTK Query cache).
- A `Mutex` from `async-mutex` prevents concurrent refresh attempts: parallel requests wait for the unlock, then simply retry.

## Tag-Based Cache Invalidation

`baseApi.ts` registers 18 tags. Each API file `providesTags`/`invalidatesTags` its own slice:

| Tag                                                             | Invalidated By                                                                                                                                                                                                                                                                                                                                                    |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Profile`                                                       | `updateProfile`, `verifyLinkPhone`, `linkGoogle`                                                                                                                                                                                                                                                                                                                  |
| `Store`                                                         | `createStore`, `updateStore`, `deleteStore`, member add/remove                                                                                                                                                                                                                                                                                                    |
| `Product`                                                       | `createStoreProduct`, `updateStoreProduct`, `generateProductDescription`                                                                                                                                                                                                                                                                                          |
| `LLMModels`, `LLMSettings`, `PromptTemplates`, `SystemSettings` | Admin settings mutations                                                                                                                                                                                                                                                                                                                                          |
| `EmbedModels`                                                   | Embedding model catalog (`GET /admin/embed-models`)                                                                                                                                                                                                                                                                                                               |
| `ScraperHeaders`                                                | Scraper header overrides — `GET /admin/scraper-headers`, `PUT`/`DELETE /admin/scraper-headers/{name}` (`useUpdateScraperHeaderMutation`, `useClearScraperHeaderMutation` in `adminApi.ts`)                                                                                                                                                                        |
| `CronProducts`, `EmbeddingCronProducts`                         | (report data, refreshed on demand). Embedding report is **per model** (`product_embeddings` rows) — list supports `status` + `model` filters, plus `GET /admin/cron/embedding-products/active-model` and `POST /admin/cron/embedding-products/reindex` for the re-index flow (`useGetActiveEmbeddingModelQuery`, `useReindexEmbeddingsMutation` in `adminApi.ts`) |
| `AdminChats`                                                    | Admin chats viewer queries (paginated list)                                                                                                                                                                                                                                                                                                                       |
| `Chats`                                                         | `createConversation`, `deleteConversation`; also invalidated from the chat page via `baseApi.util.invalidateTags(["Chats"])` when a WS message is saved                                                                                                                                                                                                           |
| `Order`, `Customer`, `Settings`                                 | (registered but never provided/invalidated — reserved for future use)                                                                                                                                                                                                                                                                                             |

## Error Handling

API errors are caught in components:

```typescript
const [updateProfile, { isLoading, error }] = useUpdateProfileMutation();

// error type: SerializedError | FetchBaseQueryError
// FetchBaseQueryError.data contains the API error envelope
const apiError = error as FetchBaseQueryError;
const key = extractTranslationKey(apiError); // → "user_not_found"
const message = extractApiError(apiError, fallback); // → envelope message or fallback
```

Never display raw server text without `extractApiError`. For localized messages, look up `translation_key` in the `errors` namespace via `useTranslations("errors")`. See `AGENTS.md` → "Error Handling & Translation Keys" and `docs/i18n.md`.
