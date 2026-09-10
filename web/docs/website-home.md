# Public Website & Anonymous Chat

The **guest-facing home page** (`/` → locale root, route group `(website)`) —
no login required. It combines a marketing landing with a live **anonymous
chat** and a **random products slider**, all running against the same API the
dashboard uses.

## Route Group & Layout

```
src/app/[locale]/(website)/
├── layout.tsx             # WebsiteNavbar + footer shell (no dashboard guard)
├── page.tsx               # Public home: hero + AnonymousChatBox + RandomProductsSection
├── about/page.tsx         # About page
└── __tests__/             # website-pages.test.tsx
```

The `(website)` route group sits **outside** the `(dashboard)` group, so the
auth guard in `(dashboard)/layout.tsx` never runs — guests land on the home
page directly. `WebsiteNavbar` renders the brand, locale switcher, and a link
to the app (login/dashboard) without exposing account UI.

## Anonymous Chat (`AnonymousChatBox`)

The home page chat needs no account. Flow:

1. **Session bootstrap**: on mount, `useGetAnonymousChatSessionMutation`
   (`POST /chat/anonymous-session`, body `{locale}`) mints `{token,
conversation}` — a **10-minute anon JWT** (WebSocket-only; the API creates
   no Postgres user) plus a Mongo conversation with `need_title=false`.
2. **Socket**: `useChat` (shared with the admin AI Chat page) opens
   `ws(s)://{host}/ws/chat/{conversationId}` authenticated with the anon token passed as the
   **`Sec-WebSocket-Protocol` subprotocol** (`tokenOverride` feeds the token into the same hook
   used by authenticated chat; there is no `?token=` query fallback — authenticated sessions
   instead rely on the httpOnly cookie).
3. **Messages**: local React state (not Redux) renders user bubbles and assistant
   `AssistantBubble`s via the shared `ChatMessageList`. Stream accumulation and reconciliation
   live in `lib/chatReducer.ts` (`turnSaved` replaces the optimistic turn with the persisted
   messages after `message_saved`, carrying `search_context.intent`); `lib/chatStream.ts` only
   builds/parses WS frames.
4. **Intent theming**: `AssistantBubble` renders **intent-themed bubbles** —
   the bubble variant is driven by `search_context.intent`
   (`greeting` / `search` / `general`), and product-name chips appear for
   `search` intents (same theming as the admin chat).
5. **Find similar**: each product card's "similar" action calls
   `handleFindSimilar` → a `similar_request` WS frame → the API's `/similar`
   reply is persisted and rendered as a new assistant message with
   product snapshots.
6. **Product view**: `ProductViewDialog` opens the public product detail
   (`GET /stores/{store_id}/products/{product_id}` — public endpoint) in a
   bottom sheet; `useCloseOnBack` handles Android back-button closing
   (state + history entry keyed `"anonymous-chat"`).
7. **Debug**: messages with a debug trace open the shared `DebugDialog`.
8. **Layout**: collapsed state is a single chat input card; on submit it
   expands to a full-screen bottom `Sheet` with the conversation, logo
   header, back button, and `ChatInput`; while the session is minting, the list shows the
   `ChatMessageListLoading` "connecting" state.

## Random Products Slider (`RandomProductsSection`)

- `useGetRandomProductsQuery({limit: 20})` → `GET /public/products/random`
  (public endpoint, rate limited 60/min) — a random sample of active store
  products. Returns **`ProductListItem[]`** (16-field light cards; the server
  caches the response 1h in Redis under `product:random:{limit}`, fail-open to
  the DB).
- Rendered as a **Swiper carousel** (`swiper/react`): `loop` + `autoplay`
  (3000 ms, `disableOnInteraction: false` — swiping does not stop it; playback pauses only
  via a `visibilitychange` listener that stops/resumes autoplay when the tab hides/shows,
  `RandomProductsSection.tsx:28-44,75`) + clickable `pagination`
  dots (`.featured-products-pagination`), responsive breakpoints (1 → 3 → 5
  slides), and `dir` flipped for RTL locales (`ltr` for `en`, `rtl`
  otherwise).
- Each slide is a `HomeProductCard` (aspect 4/5 image, trilingual name,
  price, currency); clicking opens the same `ProductViewDialog` used by chat
  (bottom sheet on mobile, centered dialog on desktop). The dialog's
  `ProductView` fetches the full product detail itself
  (`useGetStoreProductQuery` on open) — cards carry only the light
  `ProductListItem` shape, no `initialData`.
- Skeleton shimmer grid while loading; the whole section hides when the
  endpoint returns nothing.

## Other Pieces

| Component                            | Purpose                                                                                                                      |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| `AnimatedBackground`                 | Decorative animated gradient/mesh behind the hero                                                                            |
| `WebsiteNavbar`                      | Brand, locale switcher, app link — no auth UI                                                                                |
| `HomeProductCard`                    | Compact product card for the slider                                                                                          |
| `useCloseOnBack(isOpen, close, key)` | Browser/Android back handling: pushes a history entry when opening, pops + closes on back — shared by chat and product views |

## i18n

New top-level namespaces in `messages/{en,ar,fa}.json`: `website.chat`
(connecting, placeholder, inputPlaceholder, back, send labels) and
`website.products` (title, etc.). All new error texts reuse the `errors`
namespace via `extractApiError`.

## Related

- API: `POST /chat/anonymous-session`, `GET /public/products/random`
  (`product-graph-api` docs — chat-system.md, api-reference.md).
- Chat protocol details: `docs/api-integration.md` §WebSocket Chat;
  `useChat` + `useChatSocket` in `src/hooks/`.
- Admin chat page shares `useChat`/`ChatMessageList`/`AssistantBubble`/`ProductGrid` —
  see `docs/component-map.md`.
