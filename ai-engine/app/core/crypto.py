from __future__ import annotations

import os

from cryptography.fernet import Fernet
from loguru import logger


def decrypt_api_key(ciphertext: str, encryption_key: str | None) -> str:
    key = encryption_key or os.environ.get("LLM_ENCRYPTION_KEY")
    if not key:
        logger.warning("LLM_ENCRYPTION_KEY not set; cannot decrypt API keys from DB")
        raise ValueError("LLM_ENCRYPTION_KEY is required to decrypt API keys")
    cipher = Fernet(key.encode() if isinstance(key, str) else key)
    return cipher.decrypt(ciphertext.encode()).decode()
