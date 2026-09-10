# Testing

The project uses **Vitest** for unit/component tests and **Playwright** for end-to-end tests. Current suite: **370 tests across 51 runtime test files**, plus 1 compile-time type-contract file (52 total).

## Running Tests

```bash
# Run all unit tests
npm test

# Run in watch mode
npm run test:watch

# Run with coverage (enforces thresholds)
npm run test:coverage

# Run e2e tests (requires dev server running)
npm run test:e2e

# Run e2e tests in UI mode
npx playwright test --ui
```

## Test Configuration

### Vitest (`vitest.config.ts`)

- **Environment:** jsdom (React component rendering)
- **Globals:** Enabled (`describe`, `it`, `expect` available without import)
- **Setup:** `src/__tests__/setup.ts`
- **Includes:** `src/**/*.test.{ts,tsx}`
- **Alias:** `@/` → `./src/`
- **Coverage (`npm run test:coverage`):** `v8` provider, `text` + `html` reporters, with enforced thresholds:

| Metric     | Threshold |
| ---------- | --------- |
| statements | 65%       |
| branches   | 55%       |
| functions  | 50%       |
| lines      | 65%       |

Dropping coverage below these numbers fails the run.

### Playwright (`playwright.config.ts`)

- **Test dir:** `e2e/`
- **Browser:** Chromium only
- **Base URL:** `http://localhost:3000`
- **Web server:** `npm run dev` (auto-started)
- **Retries:** 2 in CI, 0 locally; **trace** captured on first retry
- **Reporter:** `html`
- **CI extras:** `workers: 1`, `forbidOnly`

> ⚠️ **Port mismatch hazard**: Playwright hardcodes `http://localhost:3000` (both `baseURL` and `webServer.url`), but `npm run dev` binds the `PORT` from `.env` via dotenv-cli — `.env.example` sets `PORT=8001`. Following the setup verbatim makes e2e hang or fail against the wrong server. Workaround: set `PORT=3000` in `.env` when running e2e (or align both configs to one port).

## Unit Test Setup

`src/__tests__/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";

// Polyfill for components using ResizeObserver
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
```

## Unit Test Files (52 files — 51 runtime suites + 1 type-contract file, ~370 tests)

| File                                                          | What It Tests                                                         |
| ------------------------------------------------------------- | --------------------------------------------------------------------- |
| `store/slices/__tests__/auth.test.ts`                         | Auth reducer + thunk states (sendOtp, verifyOtp, googleCodeAuth)      |
| `store/__tests__/store.test.ts`                               | Store creation, localStorage rehydration, auth persistence            |
| `store/api/__tests__/baseApi.test.ts`                         | Endpoint injection, Bearer token injection, token-less requests       |
| `store/api/__tests__/adminApi.test.ts`                        | All admin endpoints (LLM, prompts, settings, cron, chats, embed)      |
| `store/api/__tests__/productApi.test.ts`                      | Product CRUD + generate-descriptions endpoints                        |
| `store/api/__tests__/profileApi.test.ts`                      | All 6 profile endpoints existence                                     |
| `store/api/__tests__/storeApi.test.ts`                        | All 7 store endpoints existence                                       |
| `store/api/__tests__/fileApi.test.ts`                         | File upload endpoint, query building with/without maxSize             |
| `hooks/__tests__/useLoginFlow.test.tsx`                       | Login flow: sendOtp → otp → authenticated, error handling             |
| `hooks/__tests__/useChatSocket.test.tsx`                      | WS connect/close, raw frame send, queue+flush, ping, 4001 terminal    |
| `hooks/__tests__/useChat.test.tsx`                            | Optimistic turns, stream frames, message_saved reconcile, retry, lock |
| `hooks/__tests__/useChatScroll.test.tsx`                      | Smart stick-to-bottom scroll, near-bottom threshold, jump-to-bottom   |
| `hooks/__tests__/useCloseOnBack.test.tsx`                     | History push/back navigation for the anonymous-chat Sheet             |
| `hooks/__tests__/useInfiniteProducts.test.ts`                 | Pagination hook: loadMore, deps via JSON.stringify                    |
| `hooks/__tests__/useProductFormData.test.tsx`                 | Product form data loading                                             |
| `hooks/__tests__/use-mobile.test.ts`                          | Mobile detection at breakpoint, resize listener                       |
| `components/input/__tests__/PhoneInput.test.tsx`              | Phone input render, onSubmit, error display, loading state            |
| `components/input/__tests__/OtpInput.test.tsx`                | OTP input render, back button, error display, loading state           |
| `components/providers/__tests__/DirectionProvider.test.tsx`   | Sets `dir` attribute per locale                                       |
| `components/providers/__tests__/ErrorBoundary.test.tsx`       | Error catch, fallback UI, retry recovery, custom fallback             |
| `components/layout/__tests__/PageLayout.test.tsx`             | Wide/narrow variants, className merging                               |
| `components/chat/__tests__/RetryingThumbnail.test.tsx`        | Image retry on load failure                                           |
| `components/chat/__tests__/ChatMessageList.test.tsx`          | Message list rendering, per-message RTL/LTR direction                 |
| `components/chat/__tests__/Markdown.test.tsx`                 | Markdown rendering, dir propagation to wrapper                        |
| `components/website/__tests__/AnonymousChatBox.test.tsx`      | Anon session minting → useChat tokenOverride, optimistic + saved msgs |
| `components/website/__tests__/RandomProductsSection.test.tsx` | Random products slider render (20 cards), product view dialog open    |
| `components/website/__tests__/WebsiteNavbar.test.tsx`         | Public navbar brand, home/about/login links                           |
| `components/product/__tests__/ProductCard.test.tsx`           | Product card rendering                                                |
| `components/product/__tests__/productFormValidation.test.ts`  | Product form Zod validation                                           |
| `components/shared/__tests__/ScrollToTop.test.tsx`            | Scroll restoration on navigation                                      |
| `lib/__tests__/utils.test.ts`                                 | `cn()` class merging with tailwind-merge                              |
| `lib/__tests__/api.test.ts`                                   | `extractApiError` / `extractTranslationKey` envelope parsing          |
| `lib/__tests__/weekdays.test.ts`                              | Locale-aware weekday names (ar/en/fa)                                 |
| `lib/__tests__/locale.test.ts`                                | Locale helpers                                                        |
| `lib/__tests__/icons.test.tsx`                                | Icon component registry                                               |
| `lib/__tests__/lazy.test.ts`                                  | Dynamic import helper                                                 |
| `lib/__tests__/product-form.test.ts`                          | Variant mapping / attribute parsing helpers                           |
| `lib/__tests__/url.test.ts`                                   | `safeHref` / `isSafeHref` scheme allowlisting (XSS-safe links)        |
| `lib/validation/__tests__/schemas.test.ts`                    | Runtime Zod schema behavior (fail-open validation)                    |
| `lib/validation/__tests__/schemas.test-d.ts`                  | Compile-time type contract tests                                      |
| `i18n/__tests__/messages.test.ts`                             | All messages in en/ar/fa parse as valid ICU MessageFormat             |
| `constants/__tests__/countries.test.ts`                       | Country lookup by code/dial code, data integrity                      |
| `app/[locale]/__tests__/login-page.test.tsx`                  | Login card, phone step, language/theme toggles                        |
| `app/[locale]/__tests__/home-page.test.tsx`                   | Locale index page                                                     |
| `app/[locale]/__tests__/dashboard-layout.test.tsx`            | Auth guard, hydration, loading state                                  |
| `app/[locale]/__tests__/google-callback.test.tsx`             | Link flow, success/error redirect, login flow                         |
| `app/[locale]/__tests__/stores-page.test.tsx`                 | Loading skeletons, empty state, store cards, locale names             |
| `app/[locale]/__tests__/seller-dashboard.test.tsx`            | Seller dashboard (product stats)                                      |
| `app/[locale]/__tests__/seller-products-page.test.tsx`        | Seller products list                                                  |
| `admin/product-search/__tests__/page.test.tsx`                | AI Chat page: conversation select, WS stream render, new/delete       |
| `admin/settings/prompts/__tests__/page.test.tsx`              | Prompts page: 6 editors load + single save                            |
| `app/[locale]/(website)/__tests__/website-pages.test.tsx`     | Public website pages: home logo, about title                          |

### E2E Tests

| File                   | Description                                                           |
| ---------------------- | --------------------------------------------------------------------- |
| `e2e/login-en.spec.ts` | English login: render, invalid phone error, OTP transition, full flow |
| `e2e/login-ar.spec.ts` | Arabic login: same flow in Arabic locale                              |

## Writing Tests

### Store Slice Tests

Test reducers synchronously and thunk actions in isolation:

```typescript
describe("auth slice", () => {
  it("should handle setPhone", () => {
    const state = authReducer(initialState, setPhone("+971501234567"));
    expect(state.phone).toBe("+971501234567");
    expect(state.step).toBe("otp");
  });

  it("should handle sendOtp.fulfilled", () => {
    const state = authReducer(initialState, {
      type: sendOtp.fulfilled.type,
    });
    expect(state.step).toBe("otp");
    expect(state.loading).toBe(false);
  });
});
```

### Hook Tests

Wrap hooks in test renderer and mock Redux store:

```typescript
import { renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";

it("should transition to otp step", async () => {
  const store = configureStore({ reducer: { auth: authReducer } });
  const { result } = renderHook(() => useLoginFlow(), {
    wrapper: ({ children }) => <Provider store={store}>{children}</Provider>,
  });

  await act(async () => {
    await result.current.sendOtp("+971501234567");
  });

  expect(result.current.step).toBe("otp");
});
```

### Component Tests

Use `@testing-library/react` for rendering and user interactions; mock API hooks where needed.

### E2E Tests

Playwright tests use the bypass code `1234` — the specs fill the first **four** OTP slots with `1`–`4` (see `e2e/login-en.spec.ts` and `e2e/login-ar.spec.ts`; available when `TWILIO_BYPASS=true` on backend).

## Quality Gates (Pre-commit Hook)

The husky pre-commit hook runs **all five** stages before every commit:

1. **lint-staged** — ESLint + Prettier on staged files only
2. **npm run lint** — Full ESLint pass (zero errors, zero warnings)
3. **npm run typecheck** — Full TypeScript type check (`tsc --noEmit`)
4. **npm run format:check** — Prettier check (zero differences)
5. **npm test** — All unit tests (370)

> **Policy**: No one — human or AI — may bypass the pre-commit hook. All commits must pass all five stages.

### Chat Test Patterns

The AI Chat tests mock the WebSocket layer instead of a real connection:

```typescript
vi.mock("@/hooks/useChat", () => ({
  useChat: (options: {
    onMessageSaved?: (message: ChatMessage, conversationId: string) => void;
  }) => ({
    status: "open",
    stream: { content: "…", products: [], status: "completed", … },
    sendMessage: vi.fn(),
    resetStream: vi.fn(),
  }),
}));
```

- Emit a saved message by invoking the captured `options.onMessageSaved` callback
- Assert `sendMessage` was called with the expected content + idempotency key
- See `admin/product-search/__tests__/page.test.tsx` and `hooks/__tests__/useChat.test.tsx`

To add new files to lint-staged, update `package.json`:

```json
"lint-staged": {
  "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
  "*.{json,css,md}": ["prettier --write"]
}
```
