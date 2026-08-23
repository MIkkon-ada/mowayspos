"""Encryption boundary for AI provider credentials."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class AIConfigurationKeyError(RuntimeError):
    """Raised when the AI configuration encryption key or ciphertext is unusable."""


class AICredentialCipher:
    def __init__(self, key: str):
        if not key or not key.strip():
            raise AIConfigurationKeyError("AI configuration encryption key is required")
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise AIConfigurationKeyError("AI configuration encryption key is invalid") from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, ValueError, TypeError) as exc:
            raise AIConfigurationKeyError("AI credential ciphertext is invalid") from exc
