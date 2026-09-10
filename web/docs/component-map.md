# Component Map

## Component Hierarchy

```
Root Layout (src/app/layout.tsx)
└── [locale] Layout (src/app/[locale]/layout.tsx)
    ├── ThemeProvider         ← Dark/light mode
    ├── ReduxProvider         ← Redux store
    │   └── AuthBootstrap     ← Fires bootstrapAuth() on mount (renders null)
    ├── ErrorBoundary         ← Catch rendering errors
    ├── TooltipProvider       ← shadcn tooltips
    ├── DirectionSetter       ← Sets html dir (ltr/rtl); renders null
    ├── Toaster               ← Sonner toast notifications
    └── ScrollToTop           ← Back-to-top button after scroll threshold
    │
    ├── Public Website ((website)/page.tsx)     ← NO auth guard
    │   │                                       (website layout also renders the footer)
    │   ├── WebsiteNavbar         ← brand, locale switcher, app link
    │   ├── AnimatedBackground    ← hero decoration
    │   ├── AnonymousChatBox      ← anonymous chat (no account)
    │   │   ├── ChatInput         ← shared input
    │   │   ├── ChatMessageList   ← shared message renderer (loading/empty states)
    │   │   ├── AssistantBubble   ← intent-themed bubbles (greeting/search/general)
    │   │   ├── ProductGrid       ← chat product cards
    │   │   │   └── ChatProductCard + find-similar action
    │   │   ├── ProductViewDialog → product detail bottom sheet
    │   │   ├── DebugDialog       ← debug trace of a message
    │   │   └── Sheet (full-screen on submit) + useCloseOnBack
    │   └── RandomProductsSection ← Swiper slider (autoplay + dots, RTL-aware)
    │       └── HomeProductCard + ProductViewDialog
    │
    ├── Login Page ((auth)/login/page.tsx)
    │   ├── PhoneInput         ← Country selector + phone input + Google button
    │   └── OtpInput           ← 6-digit OTP input
    │
    ├── Dashboard Layout ((dashboard)/layout.tsx)
    │   ├── SidebarProvider    ← shadcn sidebar context
    │   ├── AppSidebar         ← Nav menu (11 admin + 4 seller items), lang/theme toggles, logout
    │   ├── DashboardHeader    ← User avatar, profile link
    │   └── Page Content
    │       │
    │       ├── Admin Dashboard (admin/page.tsx)      ← 7 gradient tiles (DashboardTile)
    │       ├── Catalog Data (admin/data/page.tsx)    ← CategoryAttributeTree
    │       ├── AI Chat (admin/product-search/page.tsx)
    │       │   ├── ChatSidebar          ← conversation list + new/delete chat
    │       │   │   └── ConversationList
    │       │   ├── ChatMessageList      ← shared renderer (also used by AnonymousChatBox)
    │       │   │   ├── AssistantBubble  ← intent-themed bubbles + product name
    │       │   │   ├── Markdown         ← assistant markdown rendering
    │       │   │   ├── CopyButton       ← copy message text
    │       │   │   ├── DebugButton → DebugDialog  ← search_context + debug trace
    │       │   │   └── ProductGrid
    │       │   │       └── ChatProductCard + find-similar
    │       │   └── ProductViewDialog → ProductView ← product detail from chat card
    │       ├── Search Evaluation (admin/search-eval/page.tsx)
    │       │   ├── metric cards (MRR@10/Recall@10, overall + en/ar)
    │       │   ├── query generation form
    │       │   ├── golden-set import textarea
    │       │   └── queries table + Judge dialog (search → mark relevant → save/skip)
    │       ├── Cron Report (admin/cron/page.tsx)    ← paginated table + detail Dialog
    │       ├── Conversations (admin/chats/page.tsx) ← user chat history + feedback
    │       ├── Admin Settings (admin/settings/)
    │       │   ├── LLM (llm/page.tsx)               ← models, API keys, default model
    │       │   ├── Prompts (prompts/page.tsx)       ← 6 template editors, single save
    │       │   ├── System (system/page.tsx)         ← cron toggle
    │       │   ├── AI Engine (ai-engine/page.tsx)   ← provider/tunnel config + embed test
    │       │   └── Scrapers (scrapers/page.tsx)     ← per-scraper header edit/clear
    │       ├── Seller Dashboard (seller/page.tsx)
    │       ├── Seller Data (seller/data/page.tsx)   ← re-exports CategoryAttributeTree
    │       ├── Seller Products (seller/products/page.tsx)
    │       │   └── ProductCard          ← `ProductListItem` light card; dialog fetches detail itself
    │       │
    │       ├── ProfilePage (admin/profile + seller/profile)
    │       │   ├── PhotoUploader        ← Crop & upload avatar
    │       │   ├── LocationPicker       ← Leaflet map with draggable marker
    │       │   ├── LinkPhoneDialog      ← Connect phone via OTP
    │       │   └── AlertDialog          ← Link success/error feedback
    │       │
    │       └── Store Pages (seller/stores/)
    │           ├── Store List (page.tsx)
    │           ├── Create Store (new/page.tsx)
    │           │   └── StoreForm        ← Shared form (create/edit)
    │           │       ├── PhotoUploader  ← Store logo (max 500px)
    │           │       ├── PhoneField     ← Country code + phone
    │           │       ├── TimePicker     ← Working hours
    │           │       ├── LocationPicker ← Store location
    │           │       └── InputGroup     ← Icon-wrapped inputs
    │           ├── Edit Store ([id]/edit/page.tsx)
    │           │   └── StoreForm        ← Same form with initialData
    │           │   └── StoreMembersSection ← Team members (add/remove owners/managers)
    │           └── Product Pages ([id]/products/)
    │               ├── Product Form (new + [productId]/edit)
    │               │   └── ProductForm             ← step wizard: BasicInfo, Attributes,
    │               │                                  Media, PriceInventory, Description, Review
    │               └── Generate Description ([productId]/generate-description)
    │                   └── Model selector + prompt editor + en/ar preview + history Dialog
    │
    └── Google Callback (auth/google/callback/page.tsx)
```

## Reusable Components

### Feature Components

| Component                         | File                                                    | Purpose                                                                                                                             |
| --------------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `StoreForm`                       | `src/components/store/StoreForm.tsx`                    | Shared create/edit form with all store fields                                                                                       |
| `ProfilePage`                     | `src/components/profile/ProfilePage.tsx`                | Full profile editor with all sections                                                                                               |
| `LinkPhoneDialog`                 | `src/components/profile/LinkPhoneDialog.tsx`            | Two-step phone linking dialog                                                                                                       |
| `LocationPicker`                  | `src/components/map/LocationPicker.tsx`                 | Leaflet map with draggable marker + geolocation                                                                                     |
| `PhotoUploader`                   | `src/components/upload/PhotoUploader.tsx`               | Image crop modal + API upload                                                                                                       |
| `PhoneInput`                      | `src/components/input/PhoneInput.tsx`                   | Login page phone + country + Google button                                                                                          |
| `PhoneField`                      | `src/components/input/PhoneField.tsx`                   | Reusable form phone field with country code                                                                                         |
| `OtpInput`                        | `src/components/input/OtpInput.tsx`                     | 6-digit OTP input with verification                                                                                                 |
| `AppSidebar`                      | `src/components/dashboard/AppSidebar.tsx`               | Role-based sidebar navigation                                                                                                       |
| `DashboardHeader`                 | `src/components/dashboard/DashboardHeader.tsx`          | Top bar with user menu                                                                                                              |
| `PageLayout`                      | `src/components/layout/PageLayout.tsx`                  | Wide/narrow page container                                                                                                          |
| `CategoryAttributeTree`           | `src/components/data/CategoryAttributeTree.tsx`         | Catalog data browser (types → categories → attributes)                                                                              |
| `ChatSidebar`                     | `src/components/chat/ChatSidebar.tsx`                   | Conversation list, new chat, delete dialog                                                                                          |
| `ConversationList`                | `src/components/chat/ConversationList.tsx`              | Chat sidebar conversation rows                                                                                                      |
| `ProductGrid`                     | `src/components/chat/ProductGrid.tsx`                   | Product cards grid (chat results)                                                                                                   |
| `RetryingThumbnail`               | `src/components/chat/RetryingThumbnail.tsx`             | Product image with retry on load failure                                                                                            |
| `Markdown`                        | `src/components/chat/Markdown.tsx`                      | Renders assistant markdown answers                                                                                                  |
| `CopyButton`                      | `src/components/chat/CopyButton.tsx`                    | Copy message text to clipboard                                                                                                      |
| `DebugButton`/`DebugDialog`       | `src/components/chat/DebugButton.tsx`/`DebugDialog.tsx` | Inspect search_context + debug trace                                                                                                |
| `AssistantBubble`                 | `src/components/chat/AssistantBubble.tsx`               | Intent-themed assistant bubble (greeting/search/general variants + product-name chip)                                               |
| `ChatMessageList`                 | `src/components/chat/ChatMessageList.tsx`               | Message renderer for both admin AI Chat and AnonymousChatBox (user bubbles, assistant bubbles, retry, scroll, loading/empty states) |
| `ChatInput`                       | `src/components/chat/ChatInput.tsx`                     | Shared chat composer (value, submit, send label, disabled states)                                                                   |
| `ProductViewDialog`/`ProductView` | `src/components/product/ProductViewDialog.tsx`          | Full product detail from a chat card                                                                                                |
| `WebsiteNavbar`                   | `src/components/website/WebsiteNavbar.tsx`              | Guest navbar — brand, locale switcher, app link                                                                                     |
| `AnimatedBackground`              | `src/components/website/AnimatedBackground.tsx`         | Hero decoration                                                                                                                     |
| `AnonymousChatBox`                | `src/components/website/AnonymousChatBox.tsx`           | No-account chat: anon session → WS → bubbles → sheet                                                                                |
| `RandomProductsSection`           | `src/components/website/RandomProductsSection.tsx`      | Swiper slider of public random products (autoplay + dots)                                                                           |
| `HomeProductCard`                 | `src/components/website/HomeProductCard.tsx`            | Compact `ProductListItem` card for the slider (image_url direct)                                                                    |
| `ProductCard`                     | `src/components/product/ProductCard.tsx`                | Seller list card over `ProductListItem`; opens `ProductViewDialog` (fetches its own detail)                                         |

### Shared Components (`src/components/shared/`)

| Component          | File                                         | Purpose                                                 |
| ------------------ | -------------------------------------------- | ------------------------------------------------------- |
| `DashboardTile`    | `src/components/shared/DashboardTile.tsx`    | Gradient dashboard tile (icon, label, description)      |
| `LanguageSwitcher` | `src/components/shared/LanguageSwitcher.tsx` | Locale picker (Popover + Command with AR/EN/FA flags)   |
| `ScrollToTop`      | `src/components/shared/ScrollToTop.tsx`      | Back-to-top button past scroll threshold (mobile-aware) |
| `TableSkeleton`    | `src/components/shared/TableSkeleton.tsx`    | Row/column skeleton placeholder for data tables         |

### Product Form Editors (`src/components/product/`, `steps/`)

| Component                                  | File                                                        | Purpose                                      |
| ------------------------------------------ | ----------------------------------------------------------- | -------------------------------------------- |
| `ProductForm`                              | `src/components/product/ProductForm.tsx`                    | Step wizard driving the create/edit flow     |
| `BasicInfoStep`                            | `src/components/product/steps/BasicInfoStep.tsx`            | Names, brand, category, store fields         |
| `AttributesStep`                           | `src/components/product/steps/AttributesStep.tsx`           | Attribute values per group                   |
| `MediaStep`                                | `src/components/product/steps/MediaStep.tsx`                | Image upload/management                      |
| `PriceInventoryStep`                       | `src/components/product/steps/PriceInventoryStep.tsx`       | Pricing, stock, SKU                          |
| `DescriptionStep`                          | `src/components/product/steps/DescriptionStep.tsx`          | Short/long descriptions                      |
| `ReviewStep`                               | `src/components/product/steps/ReviewStep.tsx`               | Pre-save review of the payload               |
| `CompositeColorSetsEditor`                 | `src/components/product/steps/CompositeColorSetsEditor.tsx` | Composite-product color set editor           |
| `VariantGridEditor`/`VariantCard`          | `src/components/product/VariantGridEditor.tsx`              | Variant grid editing (per-variant cards)     |
| `AttributeFieldRenderer`                   | `src/components/product/AttributeFieldRenderer.tsx`         | Input per attribute input type               |
| `CompositionInput`                         | `src/components/product/CompositionInput.tsx`               | Material composition entries                 |
| `ProductImageUploader`                     | `src/components/product/ProductImageUploader.tsx`           | Image upload with variant linking            |
| `ProductInfoPanel`/`ProductDetailSections` | `src/components/product/ProductView.tsx`                    | Split sections rendered inside `ProductView` |

### Store Components (`src/components/store/`)

| Component             | File                                           | Purpose                                       |
| --------------------- | ---------------------------------------------- | --------------------------------------------- |
| `StoreForm`           | `src/components/store/StoreForm.tsx`           | Shared create/edit form with all store fields |
| `StoreMembersSection` | `src/components/store/StoreMembersSection.tsx` | Team members management (add/remove)          |
| `WorkingHoursEditor`  | `src/components/store/WorkingHoursEditor.tsx`  | Weekly working-hours editor used by StoreForm |

### Provider Components

| Component         | File                                             | Purpose                                                         |
| ----------------- | ------------------------------------------------ | --------------------------------------------------------------- |
| `ThemeProvider`   | `src/components/providers/ThemeProvider.tsx`     | Dark/light mode via CSS class                                   |
| `ReduxProvider`   | `src/components/providers/ReduxProvider.tsx`     | Client-side Redux Provider (mounts `AuthBootstrap` inside)      |
| `AuthBootstrap`   | `src/components/providers/AuthBootstrap.tsx`     | Dispatches `bootstrapAuth()` on mount; renders null             |
| `ErrorBoundary`   | `src/components/providers/ErrorBoundary.tsx`     | Catches render errors with retry                                |
| `DirectionSetter` | `src/components/providers/DirectionProvider.tsx` | Sets `dir` on `<html>` per locale; renders null (wraps nothing) |

## shadcn/ui Components

The project includes 38 shadcn/ui primitives in `src/components/ui/`:

| Component                                                       | File                    |
| --------------------------------------------------------------- | ----------------------- |
| Dialog, Alert Dialog, Sheet, Accordion                          | Modal/layout primitives |
| Button, Card, Separator, Skeleton, Spinner                      | Layout/display basics   |
| Input, Textarea, Select, Single Select, Multi Select, Input OTP | Form inputs             |
| Form Field, Label, Input Group                                  | Form helpers            |
| Table, Data Table, Pagination Bar, Badge, Avatar                | Data display            |
| Popover, Command, Time Picker, Color Picker                     | Pickers                 |
| Dropdown Menu                                                   | Menus                   |
| Sidebar, Tooltip                                                | Layout/overlay          |
| Sonner (Toast)                                                  | Overlays                |
| Switch, Checkbox, Slider                                        | Control primitives      |
| Bubble, Message                                                 | Chat message primitives |
| Alert, Image Crop Dialog                                        | Feedback/media          |

## Key Patterns

- **Feature components** are in `src/components/<feature>/` (e.g., `profile/`, `store/`, `map/`, `website/`, `chat/`)
- **Shared cross-feature components** are in `src/components/shared/` (`DashboardTile`, `LanguageSwitcher`, `ScrollToTop`, `TableSkeleton`) and used by dashboard pages, the sidebar, and the locale layout
- **UI primitives** are all in `src/components/ui/` and are not modified directly (shadcn re-generation safe)
- **Providers** are in `src/components/providers/` and wrap the app tree in `[locale]/layout.tsx` (order: ThemeProvider → ReduxProvider/AuthBootstrap → ErrorBoundary → TooltipProvider → DirectionSetter + Toaster + ScrollToTop)
- The **dashboard layout** `(dashboard)/layout.tsx` is the auth guard — unauthenticated users are redirected to login; the **website layout** `(website)/layout.tsx` has no guard (public home) and renders the footer
- **Chat components are shared**: `ChatMessageList` (with `ChatInput`, `AssistantBubble`, `ProductGrid`, `Markdown`, `ProductViewDialog`) is used by both the admin AI Chat page and the public `AnonymousChatBox`
- **ProductView gallery fallback chain** (commit 651db44, `ProductView.tsx:122-141`): when a color filter yields no variant-matched images it falls back to variant-unlinked images first, then to all images — color-matched → unlinked → all
