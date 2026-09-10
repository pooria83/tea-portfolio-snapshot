# Project Structure

```
product-graph-web-ui/
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Environment template
├── .github/workflows/ci.yml      # GitHub Actions CI pipeline
├── .husky/
│   └── pre-commit                # Git hook: lint-staged + tsc
├── .prettierrc                   # Prettier config
├── Dockerfile                    # Multi-stage Docker build
├── README.md
├── components.json               # shadcn/ui registry config
├── docker-compose.yml            # Local dev with hot-reload
├── e2e/
│   ├── login-ar.spec.ts          # Playwright e2e — Arabic login
│   └── login-en.spec.ts          # Playwright e2e — English login
├── eslint.config.mjs             # ESLint flat config
├── messages/
│   ├── ar.json                   # Arabic translations
│   ├── en.json                   # English translations
│   └── fa.json                   # Farsi translations
├── next.config.ts                # Next.js config
├── package.json
├── playwright.config.ts          # Playwright config
├── postcss.config.mjs            # PostCSS + Tailwind v4
├── public/                       # Static assets
├── src/
│   ├── __tests__/
│   │   └── setup.ts              # Vitest global setup
│   ├── app/                      # Next.js App Router pages
│   ├── components/               # React components
│   ├── constants/                # App constants
│   ├── hooks/                    # Custom React hooks
│   ├── i18n/                     # next-intl config
│   ├── lib/                      # Utility functions
│   ├── store/                    # Redux store + RTK Query
│   └── types/                    # TypeScript type definitions
├── tsconfig.json
└── vitest.config.ts
```

## `src/` Directory Breakdown

### `src/app/` — App Router Pages

The Next.js App Router with a `[locale]` dynamic segment for i18n:

```
src/app/
├── [locale]/
│   ├── (auth)/login/page.tsx      # Login page
│   ├── (dashboard)/
│   │   ├── admin/
│   │   │   ├── page.tsx           # Admin dashboard (7 tiles)
│   │   │   ├── data/page.tsx      # Catalog data browser
│   │   │   ├── product-search/page.tsx  # AI Chat (WS streaming)
│   │   │   ├── cron/page.tsx      # Cron report
│   │   │   ├── cron/llm-product-description/page.tsx   # LLM description cron
│   │   │   ├── cron/embeding-product/page.tsx          # Embedding cron — per-model status, model/status filters, active-model banner, re-index
│   │   │   ├── chats/page.tsx     # Conversations viewer
│   │   │   ├── profile/page.tsx   # Admin profile
│   │   │   └── settings/          # llm, prompts, system, ai-engine, scrapers
│   │   └── seller/
│   │       ├── page.tsx           # Seller dashboard
│   │       ├── data/page.tsx      # Catalog data browser (re-exports CategoryAttributeTree)
│   │       ├── products/page.tsx  # Products list
│   │       ├── profile/page.tsx   # Seller profile
│   │       └── stores/
│   │           ├── page.tsx       # Store list
│   │           ├── new/page.tsx   # Create store
│   │           ├── [id]/edit/page.tsx  # Edit store
│   │           └── [id]/products/
│   │               ├── new/page.tsx   # Create product
│   │               └── [productId]/
│   │                   ├── edit/page.tsx                # Edit product
│   │                   └── generate-description/page.tsx  # AI description
│   ├── (website)/                  # Public guest pages — no auth guard
│   │   ├── layout.tsx              # WebsiteNavbar + footer shell
│   │   ├── page.tsx                # Public home: logo hero + AnonymousChatBox + RandomProductsSection
│   │   ├── about/page.tsx          # About page
│   │   └── __tests__/              # website-pages.test.tsx
│   ├── auth/google/callback/page.tsx  # Google OAuth callback
│   ├── layout.tsx                  # Locale layout (providers)
│   └── not-found.tsx               # Locale 404 page
├── api/
│   └── health/route.ts             # Health check (edge runtime; git_sha/environment/uptime)
├── globals.css                    # Tailwind + shadcn theme
├── layout.tsx                     # Root layout
└── page.tsx                       # Root → redirect to /ar
```

### `src/components/` — React Components

| Directory    | Description                                                                                                                                                                                                                                                                                                                                |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `auth/`      | AuthGuard                                                                                                                                                                                                                                                                                                                                  |
| `chat/`      | AI Chat UI: ChatSidebar, ConversationList, ChatMessageList (shared renderer), ProductGrid, Markdown, RetryingThumbnail, CopyButton, DebugButton/DebugDialog                                                                                                                                                                                |
| `dashboard/` | AppSidebar, DashboardHeader                                                                                                                                                                                                                                                                                                                |
| `data/`      | CategoryAttributeTree (catalog data browser)                                                                                                                                                                                                                                                                                               |
| `input/`     | PhoneInput, PhoneField, OtpInput + tests                                                                                                                                                                                                                                                                                                   |
| `layout/`    | PageLayout (wide/narrow container)                                                                                                                                                                                                                                                                                                         |
| `map/`       | LocationPicker (Leaflet)                                                                                                                                                                                                                                                                                                                   |
| `product/`   | ProductViewDialog, ProductView, ProductCard, ProductForm, ProductInfoPanel, ProductDetailSections, AttributeFieldRenderer, CompositionInput, ProductImageUploader, VariantCard, VariantGridEditor + `steps/` editors (BasicInfoStep, AttributesStep, MediaStep, PriceInventoryStep, DescriptionStep, ReviewStep, CompositeColorSetsEditor) |
| `profile/`   | ProfilePage, LinkPhoneDialog                                                                                                                                                                                                                                                                                                               |
| `providers/` | ReduxProvider, ThemeProvider, DirectionSetter, ErrorBoundary, AuthBootstrap                                                                                                                                                                                                                                                                |
| `shared/`    | DashboardTile, LanguageSwitcher, ScrollToTop, TableSkeleton                                                                                                                                                                                                                                                                                |
| `store/`     | StoreForm (shared create/edit), StoreMembersSection, WorkingHoursEditor                                                                                                                                                                                                                                                                    |
| `ui/`        | 38 shadcn/ui primitives                                                                                                                                                                                                                                                                                                                    |
| `upload/`    | PhotoUploader (crop + upload)                                                                                                                                                                                                                                                                                                              |

### `src/store/` — Redux State Management

```
src/store/
├── api/
│   ├── baseApi.ts          # RTK Query base — httpOnly-cookie auth (credentials: "include" + X-Requested-With header, cookie refresh rotation; no JWT/Bearer injection) with 18 tagTypes
│   ├── adminApi.ts         # Admin endpoints: LLM, prompts, settings, scrapers, cron, ai-engine, chats, search-eval
│   ├── anonymousApi.ts     # Public endpoints: anonymous chat session + random products
│   ├── chatApi.ts          # AI Chat conversations (getMyChats, createConversation, …)
│   ├── productApi.ts       # Product CRUD + generate-descriptions
│   ├── storeApi.ts         # Store CRUD + members
│   ├── profileApi.ts       # Profile endpoints
│   └── fileApi.ts          # File upload endpoint
├── slices/
│   ├── auth.ts             # Auth state machine + thunks
│   └── __tests__/auth.test.ts
├── hooks.ts                # Typed Redux hooks
├── index.ts                # Barrel exports
└── store.ts                # configureStore + persistence
```

### `src/constants/`

- `countries.ts` — 150+ countries with flag, dial code, names in AR/EN/FA
- `index.ts` — `APP_NAME`, `ROLES`, `ROUTES`, `API_PREFIX`

### `src/hooks/`

- `useLoginFlow.ts` — Auth state machine hook (sendOtp → verifyOtp)
- `useChatSocket.ts` — WS chat transport (connect, ping/backoff, one queued frame flush, `onFrame` listener)
- `useChat.ts` — Central chat state machine (optimistic turns, stream frames, `message_saved` reconciliation, retry with same idempotency key, similar chip, `mergeHistory`)
- `useChatScroll.ts` — Smart stick-to-bottom scroll for the message list
- `useCloseOnBack.ts` — Browser/Android back handling via history entries (chat sheet, product views)
- `useInfiniteProducts.ts` — Paginated product list (ref-stored callbacks, JSON.stringify deps)
- `useProductFormData.ts` — Product form data loading
- `usePaginationTable.ts` — Pagination state for DataTable
- `use-mobile.ts` — Mobile detection (< 768px)
- `store/hooks.ts` — Typed Redux dispatch/selector hooks
- `components/providers/ThemeProvider.tsx` — `useTheme()` hook

### `src/lib/`

- `utils.ts` — `cn()` utility (clsx + tailwind-merge)
- `api.ts` — `extractApiError()`, `extractTranslationKey()` (API error envelope parsing)
- `chat.ts` — `CHAT_ERROR_CODES`, `isChatErrorCode()`, `relativeTime()`
- `chatStream.ts` — WS frame builders/parsers: `sendMessageFrame()`, `sendSimilarRequestFrame()`, `parseChatFrame()`, `errorCodeFromFrame()`, per-turn stream accumulator (`chatStreamReducer`)
- `chatReducer.ts` — Central chat view reducer (optimistic turns, streaming, `turnSaved` reconciliation, `mergeHistory`, retry)
- `chatTypes.ts` — `ChatViewMessage`, `ChatViewTurn`, `ChatViewStatus`
- `chatIntent.ts` — Intent themes for assistant bubbles (`intentTheme()`)
- `icons.tsx` — Category icon map (react-icons)
- `locale.ts` — Locale helpers: `localeValue()` (trilingual pick), `localeDirection()` (rtl/ltr/auto)
- `store-schema.ts` — Zod schema for the store form
- `url.ts` — Safe URL helpers (`safeHref()`, `isSafeHref()`)
- `validation/` — Zod schemas + `withValidation()` helper (fail-open runtime validation)
- `product-form.ts` — Product form helpers (variant mapping, attribute parsing)
- `weekdays.ts` — Locale-aware weekday names
- `lazy.ts` — Dynamic import helper

### `src/types/`

- `api.ts` — Re-export barrel for all domain types
- `chat-history.ts` — `ChatMessage`, `ChatProduct`, `ConversationItem`, `AdminChatMessage`, `MessageFeedback`, `ChatMessageDebug`
- `search-eval.ts` — `EvalQueryItem`, generate/import requests, `EvalJudgmentsRequest`, `EvalSearchResponse`, `EvalMetricsResponse`
- `llm.ts` — `LLMModelItem`, `LLMApiKeyItem`, `LLMSettings*`, `PromptTemplate*` (6 fields), `SystemSetting*`, `EmbedText*`
- `cron.ts` — `CronProductItem/Detail`, `EmbeddingCronProductItem/Detail`, `PaginationMeta`
- `product.ts` — `ProductTypeOption`, `Attribute*`, `CategoryNode`, `BrandItem`, `Product*`
- `profile.ts` — `UserProfile`, `UserProfileUpdate`
- `store.ts` — `Store*`, `StoreMember*`, `WorkingHourInput`

## Naming Conventions

| Element       | Convention                    | Example                   |
| ------------- | ----------------------------- | ------------------------- |
| Directories   | `kebab-case`                  | `profile/`, `store-form/` |
| Components    | `PascalCase.tsx`              | `StoreForm.tsx`           |
| Hooks         | `camelCase` with `use` prefix | `useLoginFlow.ts`         |
| Utils         | `camelCase`                   | `weekdays.ts`, `utils.ts` |
| Store slices  | `camelCase`                   | `auth.ts`                 |
| API endpoints | `camelCase`                   | `profileApi.ts`           |
| Constants     | `UPPER_SNAKE_CASE`            | `APP_NAME`, `API_PREFIX`  |
| CSS classes   | Tailwind utility classes      | No custom CSS files       |
