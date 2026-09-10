from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.crypto import decrypt_api_key


def _make_key() -> str:
    return Fernet.generate_key().decode()


class TestDecryptApiKey:
    def test_decrypt_success(self) -> None:
        key = _make_key()
        fernet = Fernet(key.encode())
        plaintext = "sk-my-secret-key-12345"
        ciphertext = fernet.encrypt(plaintext.encode()).decode()

        result = decrypt_api_key(ciphertext, key)
        assert result == plaintext

    def test_raises_value_error_when_no_key(self) -> None:
        with pytest.raises(ValueError, match="LLM_ENCRYPTION_KEY is required"):
            decrypt_api_key("ciphertext", None)

    def test_falls_back_to_env_var(self) -> None:
        key = _make_key()
        fernet = Fernet(key.encode())
        plaintext = "sk-env-key"
        ciphertext = fernet.encrypt(plaintext.encode()).decode()

        with patch.dict(os.environ, {"LLM_ENCRYPTION_KEY": key}, clear=False):
            result = decrypt_api_key(ciphertext, None)
        assert result == plaintext

    def test_raises_when_env_var_also_missing(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="LLM_ENCRYPTION_KEY"),
        ):
            decrypt_api_key("ciphertext", None)

    def test_decrypt_with_bytes_key(self) -> None:
        key_bytes = Fernet.generate_key()
        key_str = key_bytes.decode()
        fernet = Fernet(key_bytes)
        plaintext = "sk-bytes-key"
        ciphertext = fernet.encrypt(plaintext.encode()).decode()

        result = decrypt_api_key(ciphertext, key_str)
        assert result == plaintext

    def test_invalid_ciphertext_raises(self) -> None:
        key = _make_key()
        with pytest.raises(InvalidToken):
            decrypt_api_key("not-valid-base64!!", key)
