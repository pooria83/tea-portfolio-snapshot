# API Error Codes & Translation Keys

Every API error response includes a `translation_key` field that maps to a key in the frontend locale files under the `errors` namespace.

## Response Format

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "User not found",
    "translation_key": "user_not_found",
    "request_id": "abc-123"
  }
}
```

## Error Code Reference

### Auth & Authentication

| translation_key | HTTP | English message |
|---|---|---|
| `user_not_found` | 404 | User not found |
| `invalid_credentials` | 401 | Invalid credentials |
| `account_inactive` | 403 | Account is inactive |
| `token_expired` | 401 | Token expired |
| `invalid_token` | 401 | Invalid token |
| `not_authenticated` | 401 | Not authenticated |
| `refresh_token_invalid` | 401 | Invalid or expired refresh token |
| `refresh_token_reuse` | 401 | Refresh token reuse detected. All sessions revoked. |
| `invalid_otp` | 401 | Invalid or expired OTP. |
| `too_many_otp_attempts` | 401 | Too many verification attempts. Request a new OTP. |
| `otp_send_limit` | 503 | OTP send limit reached. Try again later. |
| `otp_send_failed` | 503 | Failed to send OTP. Try again later. |
| `invalid_google_token` | 401 | Invalid Google token |
| `google_token_missing_id` | 401 | Google token missing user identifier. |
| `google_verify_failed` | 503 | Failed to verify Google token. Please try again. |
| `google_not_configured` | 503 | Google Sign-In is not configured. |
| `invalid_redirect_uri` | 401 | Invalid redirect URI |
| `google_code_exchange_failed` | 401 | Failed to exchange Google authorization code |
| `google_no_id_token` | 401 | Google did not return an ID token |
| `google_auth_timeout` | 503 | Google authentication timed out. Please try again. |
| `google_comm_failed` | 503 | Failed to communicate with Google. Please try again. |
| `invalid_oauth_state` | 401 | Invalid OAuth state |
| `email_or_username_taken` | 409 | Email or username already taken |
| `rate_limited` | 429 | Rate limit exceeded |
| `account_locked` | 429 | Account locked due to too many failed attempts. |
| `csrf_header_missing` | 401 | CSRF header missing (`X-Requested-With: XMLHttpRequest` required for cookie-authenticated requests) |

### User Profile

| translation_key | HTTP | English message |
|---|---|---|
| `email_taken` | 409 | Email already taken |
| `phone_already_linked` | 409 | This phone number is already linked to another account. |
| `google_already_linked` | 409 | This Google account is already linked to another user. |
| `google_email_already_linked` | 409 | This Google email is already linked to another user. |

### Store & Members

| translation_key | HTTP | English message |
|---|---|---|
| `store_not_found` | 404 | Store not found |
| `max_stores_reached` | 409 | Maximum stores allowed per seller |
| `cannot_change_price_unit` | 409 | Cannot change price unit: store has active products |
| `phone_or_email_required` | 422 | Either phone or email must be provided |
| `member_already_exists` | 409 | User is already a member of this store |
| `cannot_add_self` | 409 | Cannot add yourself as a member |
| `member_not_found` | 404 | Store member not found |
| `cannot_remove_self` | 409 | Cannot remove yourself as a member. Transfer ownership first. |
| `cannot_remove_last_owner` | 409 | Cannot remove the last owner of the store |

### Product

| translation_key | HTTP | English message |
|---|---|---|
| `product_not_found` | 404 | Product not found |
| `product_type_not_found` | 404 | Product type not found |
| `attribute_not_found` | 404 | Attribute not found |
| `image_not_found` | 404 | Image not found |
| `variant_not_found` | 404 | Variant not found |
| `price_required` | 422 | Price is required for active variants |
| `sku_required` | 422 | SKU is required for active variants |

### Admin / LLM

| translation_key | HTTP | English message |
|---|---|---|
| `llm_model_not_found` | 404 | LLM model not found |
| `api_key_not_found` | 404 | API key not found |

### Admin / Embedding Config (system settings validation)

All raised by `system_setting_service` when `PUT /admin/system-settings` updates the `embedding_provider` setting.

| translation_key | HTTP | English message |
|---|---|---|
| `embed_provider_invalid` | 422 | Invalid embedding provider |
| `embed_model_required` | 422 | Embedding model is required |
| `embed_model_not_found` | 422 | Embedding model not found |
| `embed_tunnel_url_required` | 422 | TEI tunnel URL is required |
| `embed_api_key_required` | 422 | API key is required |
| `embed_api_key_too_short` | 422 | API key must be at least 5 characters |

### Chat (HTTP routes)

| translation_key | HTTP | English message |
|---|---|---|
| `chat_not_available` | 503 | Chat history is not available |
| `conversation_not_found` | 404 | Conversation not found |
| `chat_limit_reached` | 409 | Message limit reached |
| `conversation_closed` | 409 | Conversation is closed |
| `message_not_found` | 404 | Message not found |
| `chat_engine_failed` | 503 | Chat generation failed |

### Chat (WebSocket frame-level codes)

These are returned as `{"type": "error", "code": "...", "message": "..."}` frames on `/ws/chat/{conversation_id}` — never as HTTP responses. Some mirror the HTTP keys above (`conversation_not_found`, `chat_limit_reached`, `conversation_closed`, `chat_not_available`, plus `product_not_found`, `chat_failed`). The frame-only codes:

| code | Trigger |
|---|---|
| `empty_content` | `send_message` frame with blank content |
| `message_too_large` | frame exceeds the 10 KiB socket limit |
| `missing_product_id` | `similar_request` frame without `product_id` |
| `invalid_frame` | payload is not valid JSON |
| `unsupported_frame` | unknown frame type |

### Scrapers

| translation_key | HTTP | English message |
|---|---|---|
| `scraper_header_not_found` | 404 | Scraper header not found: {name} |
| `scraper_header_invalid` | 422 | (validation message from header parsing) |

### Files

| translation_key | HTTP | English message |
|---|---|---|
| `invalid_file_name` | 422 | Invalid file name |
| `file_too_large` | 422 | File too large. |
| `file_extension_not_allowed` | 422 | File extension is not allowed |
| `file_content_type_not_allowed` | 422 | Content type is not allowed |
| `file_content_mismatch` | 422 | File content does not match expected format |
| `storage_not_available` | 404 | Storage not available |
| `file_not_found` | 404 | File not found |

### AI Engine

| translation_key | HTTP | English message |
|---|---|---|
| `ai_engine_error` | 503 | AI Engine error |
| `ai_engine_not_available` | 503 | AI Engine client not available |
| `description_generation_failed` | 503 | Description generation failed: AI Engine unavailable |

### Authorization

| translation_key | HTTP | English message |
|---|---|---|
| `admin_access_required` | 403 | Admin access required |
| `invalid_api_key` | 403 | Invalid API key |
| `websocket_auth_required` | 401 | WebSocket authentication required |

### Internal / Misc

| translation_key | HTTP | English message |
|---|---|---|
| `invalid_phone` | 422 | Invalid phone number format |
| `validation_error` | 422 | Validation failed |
| `storage_error` | 500 | Storage error |
| `service_unavailable` | 503 | Service unavailable |
| `internal_error` | 500 | Internal server error |
| `server_shutting_down` | 503 | Server shutting down |
| `not_found` | 404 | Not found |

### Raw Code: `LAZY_LOAD_VIOLATION`

The global exception handler (`app/core/exception_handlers.py`) special-cases SQLAlchemy `MissingGreenlet` errors and emits a raw `code` of `"LAZY_LOAD_VIOLATION"` (with `translation_key: null`) — a developer-facing signal that a lazy load ran outside the async context. Fix the query with `selectinload`/`joinedload`; it is not part of the translation-key inventory.

## Frontend Usage

The frontend locale files (`messages/en.json`, `ar.json`, `fa.json`) each carry 89 keys under the `errors` namespace — a superset of every backend `translation_key` constant, so any key the API emits resolves in all three locales.

In the frontend, import `useTranslations` and look up the error key under the `errors` namespace:

```typescript
const t = useTranslations("errors");

// API returns: { error: { message: "User not found", translation_key: "user_not_found" } }
// Use translation_key for localized message, fall back to error.message (English)
function getErrorMessage(error: unknown): string {
  const key = extractTranslationKey(error);
  if (key) {
    const translated = t(key);
    if (translated !== key) return translated;
  }
  return extractMessage(error) ?? "An error occurred";
}
```
