from cryptography.fernet import Fernet
from loguru import logger

from app.core.config import settings

_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is not None:
        return _cipher
    key = settings.llm_encryption_key
    if key:
        _cipher = Fernet(key.encode() if isinstance(key, str) else key)
        return _cipher
    if settings.environment == "production":
        raise RuntimeError("LLM_ENCRYPTION_KEY is not set — refusing to start in production with an ephemeral key (stored LLM API keys would become undecryptable)")
    _cipher = Fernet(Fernet.generate_key())
    logger.warning("LLM_ENCRYPTION_KEY not set; using generated key (not persistent)")
    return _cipher


def encrypt_api_key(plaintext: str) -> str:
    return _get_cipher().encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    return _get_cipher().decrypt(ciphertext.encode()).decode()
