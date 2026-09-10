from typing import Final


class E:
    # --- Auth ---
    USER_NOT_FOUND: Final = "user_not_found"
    INVALID_CREDENTIALS: Final = "invalid_credentials"
    ACCOUNT_INACTIVE: Final = "account_inactive"
    TOKEN_EXPIRED: Final = "token_expired"
    INVALID_TOKEN: Final = "invalid_token"
    NOT_AUTHENTICATED: Final = "not_authenticated"
    REFRESH_TOKEN_INVALID: Final = "refresh_token_invalid"
    REFRESH_TOKEN_REUSE: Final = "refresh_token_reuse"
    INVALID_OTP: Final = "invalid_otp"
    TOO_MANY_OTP_ATTEMPTS: Final = "too_many_otp_attempts"
    OTP_SEND_LIMIT: Final = "otp_send_limit"
    OTP_SEND_FAILED: Final = "otp_send_failed"
    INVALID_GOOGLE_TOKEN: Final = "invalid_google_token"
    GOOGLE_TOKEN_MISSING_ID: Final = "google_token_missing_id"
    GOOGLE_VERIFY_FAILED: Final = "google_verify_failed"
    GOOGLE_NOT_CONFIGURED: Final = "google_not_configured"
    INVALID_REDIRECT_URI: Final = "invalid_redirect_uri"
    GOOGLE_CODE_EXCHANGE_FAILED: Final = "google_code_exchange_failed"
    GOOGLE_NO_ID_TOKEN: Final = "google_no_id_token"
    GOOGLE_AUTH_TIMEOUT: Final = "google_auth_timeout"
    GOOGLE_COMM_FAILED: Final = "google_comm_failed"
    INVALID_OAUTH_STATE: Final = "invalid_oauth_state"
    CSRF_HEADER_MISSING: Final = "csrf_header_missing"
    EMAIL_OR_USERNAME_TAKEN: Final = "email_or_username_taken"
    RATE_LIMITED: Final = "rate_limited"
    ACCOUNT_LOCKED: Final = "account_locked"

    # --- User ---
    EMAIL_TAKEN: Final = "email_taken"
    PHONE_ALREADY_LINKED: Final = "phone_already_linked"
    GOOGLE_ALREADY_LINKED: Final = "google_already_linked"
    GOOGLE_EMAIL_ALREADY_LINKED: Final = "google_email_already_linked"

    # --- Store ---
    STORE_NOT_FOUND: Final = "store_not_found"
    MAX_STORES_REACHED: Final = "max_stores_reached"
    CANNOT_CHANGE_PRICE_UNIT: Final = "cannot_change_price_unit"
    PHONE_OR_EMAIL_REQUIRED: Final = "phone_or_email_required"
    MEMBER_ALREADY_EXISTS: Final = "member_already_exists"
    CANNOT_ADD_SELF: Final = "cannot_add_self"
    MEMBER_NOT_FOUND: Final = "member_not_found"
    CANNOT_REMOVE_SELF: Final = "cannot_remove_self"
    CANNOT_REMOVE_LAST_OWNER: Final = "cannot_remove_last_owner"

    # --- Product ---
    PRODUCT_NOT_FOUND: Final = "product_not_found"
    PRODUCT_TYPE_NOT_FOUND: Final = "product_type_not_found"
    ATTRIBUTE_NOT_FOUND: Final = "attribute_not_found"
    IMAGE_NOT_FOUND: Final = "image_not_found"
    VARIANT_NOT_FOUND: Final = "variant_not_found"
    PRICE_REQUIRED: Final = "price_required"
    SKU_REQUIRED: Final = "sku_required"

    # --- Admin ---
    LLM_MODEL_NOT_FOUND: Final = "llm_model_not_found"
    API_KEY_NOT_FOUND: Final = "api_key_not_found"
    EMBED_PROVIDER_INVALID: Final = "embed_provider_invalid"
    EMBED_MODEL_REQUIRED: Final = "embed_model_required"
    EMBED_MODEL_NOT_FOUND: Final = "embed_model_not_found"
    EMBED_TUNNEL_URL_REQUIRED: Final = "embed_tunnel_url_required"
    EMBED_API_KEY_REQUIRED: Final = "embed_api_key_required"
    EMBED_API_KEY_TOO_SHORT: Final = "embed_api_key_too_short"

    # --- Files ---
    INVALID_FILE_NAME: Final = "invalid_file_name"
    FILE_TOO_LARGE: Final = "file_too_large"
    FILE_EXTENSION_NOT_ALLOWED: Final = "file_extension_not_allowed"
    FILE_CONTENT_TYPE_NOT_ALLOWED: Final = "file_content_type_not_allowed"
    FILE_CONTENT_MISMATCH: Final = "file_content_mismatch"
    STORAGE_NOT_AVAILABLE: Final = "storage_not_available"
    FILE_NOT_FOUND: Final = "file_not_found"

    # --- AI ---
    AI_ENGINE_ERROR: Final = "ai_engine_error"
    AI_ENGINE_NOT_AVAILABLE: Final = "ai_engine_not_available"
    DESCRIPTION_GENERATION_FAILED: Final = "description_generation_failed"

    # --- Chat ---
    CHAT_NOT_AVAILABLE: Final = "chat_not_available"
    CONVERSATION_NOT_FOUND: Final = "conversation_not_found"
    CHAT_LIMIT_REACHED: Final = "chat_limit_reached"
    CONVERSATION_CLOSED: Final = "conversation_closed"
    MESSAGE_NOT_FOUND: Final = "message_not_found"
    CHAT_ENGINE_FAILED: Final = "chat_engine_failed"
    EMPTY_CONTENT: Final = "empty_content"
    MESSAGE_TOO_LARGE: Final = "message_too_large"
    MISSING_PRODUCT_ID: Final = "missing_product_id"
    INVALID_FRAME: Final = "invalid_frame"
    UNSUPPORTED_FRAME: Final = "unsupported_frame"

    # --- Authz ---
    ADMIN_ACCESS_REQUIRED: Final = "admin_access_required"
    INVALID_API_KEY: Final = "invalid_api_key"
    WEBSOCKET_AUTH_REQUIRED: Final = "websocket_auth_required"

    # --- Validation ---
    INVALID_PHONE: Final = "invalid_phone"
    VALIDATION_ERROR: Final = "validation_error"

    # --- Storage ---
    STORAGE_ERROR: Final = "storage_error"

    # --- Misc ---
    SERVICE_UNAVAILABLE: Final = "service_unavailable"
    INTERNAL_ERROR: Final = "internal_error"
    SERVER_SHUTTING_DOWN: Final = "server_shutting_down"
    NOT_FOUND: Final = "not_found"

    # --- Scrapers ---
    SCRAPER_HEADER_NOT_FOUND: Final = "scraper_header_not_found"
    SCRAPER_HEADER_INVALID: Final = "scraper_header_invalid"


ERROR_CODES_MAP: dict[str, str] = {
    # Auth
    E.USER_NOT_FOUND: "User not found",
    E.INVALID_CREDENTIALS: "Invalid credentials",
    E.ACCOUNT_INACTIVE: "Account is inactive",
    E.TOKEN_EXPIRED: "Token expired",
    E.INVALID_TOKEN: "Invalid token",
    E.NOT_AUTHENTICATED: "Not authenticated",
    E.REFRESH_TOKEN_INVALID: "Invalid or expired refresh token",
    E.REFRESH_TOKEN_REUSE: "Refresh token reuse detected. All sessions revoked.",
    E.INVALID_OTP: "Invalid or expired OTP.",
    E.TOO_MANY_OTP_ATTEMPTS: "Too many verification attempts. Request a new OTP.",
    E.OTP_SEND_LIMIT: "OTP send limit reached. Try again later.",
    E.OTP_SEND_FAILED: "Failed to send OTP. Try again later.",
    E.INVALID_GOOGLE_TOKEN: "Invalid Google token",
    E.GOOGLE_TOKEN_MISSING_ID: "Google token missing user identifier.",
    E.GOOGLE_VERIFY_FAILED: "Failed to verify Google token. Please try again.",
    E.GOOGLE_NOT_CONFIGURED: "Google Sign-In is not configured.",
    E.INVALID_REDIRECT_URI: "Invalid redirect URI",
    E.GOOGLE_CODE_EXCHANGE_FAILED: "Failed to exchange Google authorization code",
    E.GOOGLE_NO_ID_TOKEN: "Google did not return an ID token",
    E.GOOGLE_AUTH_TIMEOUT: "Google authentication timed out. Please try again.",
    E.GOOGLE_COMM_FAILED: "Failed to communicate with Google. Please try again.",
    E.INVALID_OAUTH_STATE: "Invalid OAuth state",
    E.CSRF_HEADER_MISSING: "CSRF header missing",
    E.EMAIL_OR_USERNAME_TAKEN: "Email or username already taken",
    E.RATE_LIMITED: "Rate limit exceeded",
    E.ACCOUNT_LOCKED: "Account locked due to too many failed attempts.",
    # User
    E.EMAIL_TAKEN: "Email already taken",
    E.PHONE_ALREADY_LINKED: "This phone number is already linked to another account.",
    E.GOOGLE_ALREADY_LINKED: "This Google account is already linked to another user.",
    E.GOOGLE_EMAIL_ALREADY_LINKED: "This Google email is already linked to another user.",
    # Store
    E.STORE_NOT_FOUND: "Store not found",
    E.MAX_STORES_REACHED: "Maximum stores allowed per seller",
    E.CANNOT_CHANGE_PRICE_UNIT: "Cannot change price unit: store has active products",
    E.PHONE_OR_EMAIL_REQUIRED: "Either phone or email must be provided",
    E.MEMBER_ALREADY_EXISTS: "User is already a member of this store",
    E.CANNOT_ADD_SELF: "Cannot add yourself as a member",
    E.MEMBER_NOT_FOUND: "Store member not found",
    E.CANNOT_REMOVE_SELF: "Cannot remove yourself as a member. Transfer ownership first.",
    E.CANNOT_REMOVE_LAST_OWNER: "Cannot remove the last owner of the store",
    # Product
    E.PRODUCT_NOT_FOUND: "Product not found",
    E.PRODUCT_TYPE_NOT_FOUND: "Product type not found",
    E.ATTRIBUTE_NOT_FOUND: "Attribute not found",
    E.IMAGE_NOT_FOUND: "Image not found",
    E.VARIANT_NOT_FOUND: "Variant not found",
    E.PRICE_REQUIRED: "Price is required for active variants",
    E.SKU_REQUIRED: "SKU is required for active variants",
    # Admin
    E.LLM_MODEL_NOT_FOUND: "LLM model not found",
    E.API_KEY_NOT_FOUND: "API key not found",
    E.EMBED_PROVIDER_INVALID: "Invalid embedding provider",
    E.EMBED_MODEL_REQUIRED: "Embedding model is required",
    E.EMBED_MODEL_NOT_FOUND: "Embedding model not found",
    E.EMBED_TUNNEL_URL_REQUIRED: "TEI tunnel URL is required",
    E.EMBED_API_KEY_REQUIRED: "API key is required",
    E.EMBED_API_KEY_TOO_SHORT: "API key must be at least 5 characters",
    # Files
    E.INVALID_FILE_NAME: "Invalid file name",
    E.FILE_TOO_LARGE: "File too large.",
    E.FILE_EXTENSION_NOT_ALLOWED: "File extension is not allowed",
    E.FILE_CONTENT_TYPE_NOT_ALLOWED: "Content type is not allowed",
    E.FILE_CONTENT_MISMATCH: "File content does not match expected format",
    E.STORAGE_NOT_AVAILABLE: "Storage not available",
    E.FILE_NOT_FOUND: "File not found",
    # AI
    E.AI_ENGINE_ERROR: "AI Engine error",
    E.AI_ENGINE_NOT_AVAILABLE: "AI Engine client not available",
    E.DESCRIPTION_GENERATION_FAILED: "Description generation failed: AI Engine unavailable",
    # Chat
    E.CHAT_NOT_AVAILABLE: "Chat history is not available",
    E.CONVERSATION_NOT_FOUND: "Conversation not found",
    E.CHAT_LIMIT_REACHED: "You have reached the message limit for this conversation",
    E.CONVERSATION_CLOSED: "This conversation is closed",
    E.MESSAGE_NOT_FOUND: "Message not found",
    E.CHAT_ENGINE_FAILED: "Chat generation failed, please try again",
    E.EMPTY_CONTENT: "Message content is empty",
    E.MESSAGE_TOO_LARGE: "Message is too large",
    E.MISSING_PRODUCT_ID: "Missing product id",
    E.INVALID_FRAME: "Invalid frame",
    E.UNSUPPORTED_FRAME: "Unsupported frame",
    # Authz
    E.ADMIN_ACCESS_REQUIRED: "Admin access required",
    E.INVALID_API_KEY: "Invalid API key",
    E.WEBSOCKET_AUTH_REQUIRED: "WebSocket authentication required",
    # Validation
    E.INVALID_PHONE: "Invalid phone number format",
    E.VALIDATION_ERROR: "Validation failed",
    # Storage
    E.STORAGE_ERROR: "Storage error",
    # Misc
    E.SERVICE_UNAVAILABLE: "Service unavailable",
    E.INTERNAL_ERROR: "Internal server error",
    E.SERVER_SHUTTING_DOWN: "Server shutting down",
    E.NOT_FOUND: "Not found",
}
