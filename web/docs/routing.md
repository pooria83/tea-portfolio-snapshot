# Routing & Navigation

## App Router Structure

The project uses Next.js App Router with a dynamic `[locale]` segment for i18n.

```
src/app/
├── layout.tsx                           # Root layout (html.dark)
├── page.tsx                             # / → redirect("/ar")
├── api/
│   └── health/route.ts                  # /api/health — edge runtime health probe
├── [locale]/
│   ├── layout.tsx                       # Providers + shared shell
│   ├── not-found.tsx                    # /[locale]/... 404 page
│   ├── (auth)/                          # Public (unauthenticated)
│   │   └── login/page.tsx              # /[locale]/login
│   ├── (website)/                       # Public guest pages — no guard
│   │   ├── layout.tsx                   # WebsiteNavbar + footer shell
│   │   ├── page.tsx                     # /[locale]/ → public home
│   │   ├── about/page.tsx               # /[locale]/about
│   │   └── __tests__/                   # website-pages.test.tsx
│   ├── (dashboard)/                     # Protected (authenticated)
│   │   ├── layout.tsx                   # Auth + role guard, sidebar shell
│   │   ├── admin/
│   │   │   ├── page.tsx                # /[locale]/admin
│   │   │   ├── data/page.tsx           # /[locale]/admin/data
│   │   │   ├── product-search/page.tsx # /[locale]/admin/product-search
│   │   │   ├── cron/page.tsx           # /[locale]/admin/cron
│   │   │   ├── cron/llm-product-description/page.tsx  # /[locale]/admin/cron/llm-product-description
│   │   │   ├── chats/page.tsx          # /[locale]/admin/chats
│   │   │   ├── profile/page.tsx        # /[locale]/admin/profile
│   │   │   └── settings/
│   │   │       ├── llm/page.tsx        # /[locale]/admin/settings/llm
│   │   │       ├── prompts/page.tsx    # /[locale]/admin/settings/prompts
│   │   │       ├── system/page.tsx     # /[locale]/admin/settings/system
│   │   │       ├── ai-engine/page.tsx  # /[locale]/admin/settings/ai-engine
│   │   │       └── scrapers/page.tsx   # /[locale]/admin/settings/scrapers
│   │   └── seller/
│   │       ├── page.tsx                # /[locale]/seller
│   │       ├── data/page.tsx           # /[locale]/seller/data
│   │       ├── products/page.tsx       # /[locale]/seller/products
│   │       ├── profile/page.tsx        # /[locale]/seller/profile
│   │       └── stores/
│   │           ├── page.tsx            # /[locale]/seller/stores
│   │           ├── new/page.tsx        # /[locale]/seller/stores/new
│   │           ├── [id]/edit/page.tsx  # /[locale]/seller/stores/{id}/edit
│   │           └── [id]/products/[productId]/
│   │               ├── edit/page.tsx   # /[locale]/seller/stores/{id}/products/{pid}/edit
│   │               └── generate-description/page.tsx  # /[locale]/.../generate-description
│   └── auth/
│       └── google/callback/page.tsx    # /[locale]/auth/google/callback
```

## Route Groups

| Group         | Purpose                          | Auth Required |
| ------------- | -------------------------------- | ------------- |
| `(auth)`      | Login page                       | No            |
| `(website)`   | Public guest pages (home, about) | No            |
| `(dashboard)` | All authenticated pages          | Yes           |

The dashboard layout (`(dashboard)/layout.tsx`) is the single guard for every authenticated
route: a hydration guard (via `useSyncExternalStore`), a loading skeleton while auth state is
restoring, a redirect to `/login` when `auth.step !== "authenticated"`, and a role check —
non-admin users visiting `/admin*` are redirected to `/seller`. The website layout
(`(website)/layout.tsx`) has **no guard** — guests land on the home page with anonymous chat +
random products slider (see [website-home.md](website-home.md)); it also renders the site
footer.

## Route Table

| Path                                                               | Component             | Role   | Description                                                               |
| ------------------------------------------------------------------ | --------------------- | ------ | ------------------------------------------------------------------------- |
| `/[locale]/` (home)                                                | Public home page      | Public | Hero + AnonymousChatBox + RandomProductsSection slider                    |
| `/[locale]/about`                                                  | About page            | Public | About                                                                     |
| `/[locale]/login`                                                  | Login page            | Public | Phone OTP + Google sign-in                                                |
| `/[locale]/admin`                                                  | Admin dashboard       | Admin  | Admin home                                                                |
| `/[locale]/admin/data`                                             | CategoryAttributeTree | Admin  | Catalog data browser                                                      |
| `/[locale]/admin/product-search`                                   | AI Chat page          | Admin  | RAG product search with WS streaming                                      |
| `/[locale]/admin/search-eval`                                      | Search-eval page      | Admin  | Search-quality: generation, import, judging, MRR@10/Recall@10 metrics     |
| `/[locale]/admin/cron`                                             | Cron report page      | Admin  | Cron job reports + detail modal                                           |
| `/[locale]/admin/cron/llm-product-description`                     | LLM cron report page  | Admin  | LLM description cron report (same endpoints as `/admin/cron`)             |
| `/[locale]/admin/cron/embeding-product`                            | Embedding report page | Admin  | Per-model embedding status, model/status filters, active model + re-index |
| `/[locale]/admin/chats`                                            | Conversations page    | Admin  | View user chat history + feedback                                         |
| `/[locale]/admin/settings/llm`                                     | LLM settings          | Admin  | Models, API keys, default model                                           |
| `/[locale]/admin/settings/prompts`                                 | Prompts settings      | Admin  | 6 prompt template editors                                                 |
| `/[locale]/admin/settings/system`                                  | System settings       | Admin  | Cron toggle                                                               |
| `/[locale]/admin/settings/scrapers`                                | Scraper settings      | Admin  | Per-scraper header management (edit/clear)                                |
| `/[locale]/admin/settings/ai-engine`                               | AI Engine settings    | Admin  | Provider/tunnel config + embedding test                                   |
| `/[locale]/admin/profile`                                          | ProfilePage           | Admin  | Edit admin profile                                                        |
| `/[locale]/seller`                                                 | Seller dashboard      | Seller | Seller home (lists stores)                                                |
| `/[locale]/seller/data`                                            | CategoryAttributeTree | Seller | Catalog data browser (re-export of the shared component)                  |
| `/[locale]/seller/products`                                        | Products page         | Seller | Seller products list                                                      |
| `/[locale]/seller/profile`                                         | ProfilePage           | Seller | Edit seller profile                                                       |
| `/[locale]/seller/stores`                                          | Store list            | Seller | List my stores                                                            |
| `/[locale]/seller/stores/new`                                      | StoreForm (create)    | Seller | Create new store                                                          |
| `/[locale]/seller/stores/{id}/edit`                                | StoreForm (edit)      | Seller | Edit existing store                                                       |
| `/[locale]/seller/stores/{id}/products/{pid}/edit`                 | ProductForm           | Seller | Edit store product                                                        |
| `/[locale]/seller/stores/{id}/products/{pid}/generate-description` | Generate description  | Seller | AI description generation                                                 |
| `/[locale]/auth/google/callback`                                   | Callback handler      | Public | Google OAuth code exchange                                                |

## Navigation Components

### AppSidebar (`src/components/dashboard/AppSidebar.tsx`)

Role-based sidebar with 11 admin items + 4 seller items:

- **Dashboard link** — `/admin` or `/seller` depending on role
- **Role-specific links** — stores for seller, admin-specific pages for admin
- **Language switcher** — toggles locale (ar/en/fa)
- **Theme toggle** — dark/light mode
- **Logout button** — dispatches `logout()`, redirects to `/login`

### DashboardHeader (`src/components/dashboard/DashboardHeader.tsx`)

Top bar with:

- User avatar + name
- Profile link dropdown

## Locale Routing

Configuration in `src/i18n/routing.ts`:

```typescript
export const routing = defineRouting({
  locales: ["ar", "en", "fa"],
  defaultLocale: "ar",
  localePrefix: "always",
});
```

With `localePrefix: "always"` **every URL carries the locale prefix** — including the
default locale (`ar`):

- `/ar/login` → Arabic version (default locale, still prefixed)
- `/en/login` → English version
- `/fa/login` → Farsi version
- `/login` (no prefix) → middleware redirects to `/ar/login`

## Middleware (`src/proxy.ts`)

The next-intl middleware lives in `src/proxy.ts` — there is no `middleware.ts` in this repo.
It wraps `createMiddleware(routing)` for locale negotiation and redirect, with a matcher that
excludes API routes, tRPC, Next internals, Vercel internals, and static files (paths containing
a dot):

```typescript
import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  matcher: ["/((?!api|trpc|_next|_vercel|.*[.].*).*)"],
};
```

## Navigation Hooks

Use `next-intl` navigation primitives:

```typescript
import { useRouter, usePathname } from "@/i18n/routing";

// Locale-aware navigation
router.push("/seller/stores");

// Get current pathname (without locale prefix)
const pathname = usePathname();
```

## Auth-Based Route Protection

Protection is **centralized in `(dashboard)/layout.tsx`** — no per-page role checks. The
layout combines a hydration guard (so redirects only run after mount), a loading skeleton,
and two redirect rules:

```typescript
const hydrated = useSyncExternalStore(subscribe, getHydrationSnapshot, () => false);

useEffect(() => {
  if (hydrated && !loading && step !== "authenticated") {
    router.replace("/login");
    return;
  }
  if (hydrated && !loading && step === "authenticated" && user) {
    const wantsAdmin = pathname.startsWith("/admin");
    if (wantsAdmin && user.role !== "admin") {
      router.replace("/seller");
    }
  }
}, [hydrated, loading, step, router, pathname, user]);
```

- **Unauthenticated** (`step !== "authenticated"`) → redirected to `/login`
- **Non-admin on `/admin*`** → redirected to `/seller`

While `loading`, the layout renders a skeleton instead of children; before hydration it
renders nothing. Backend authorization is still enforced per-endpoint (`get_admin_user`
checks `user.role == "admin"`); the frontend guard only controls visibility and routing.
