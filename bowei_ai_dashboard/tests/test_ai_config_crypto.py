from cryptography.fernet import Fernet
import pytest

from app.ai.crypto import AICredentialCipher, AIConfigurationKeyError


def test_cipher_round_trip_never_returns_plaintext_as_ciphertext():
    cipher = AICredentialCipher(Fernet.generate_key().decode())

    token = cipher.encrypt("secret-value")

    assert token != "secret-value"
    assert cipher.decrypt(token) == "secret-value"


def test_cipher_rejects_missing_or_invalid_key():
    with pytest.raises(AIConfigurationKeyError):
        AICredentialCipher("")
    with pytest.raises(AIConfigurationKeyError):
        AICredentialCipher("not-a-fernet-key")


def test_cipher_does_not_include_secret_in_decryption_error():
    cipher = AICredentialCipher(Fernet.generate_key().decode())

    with pytest.raises(AIConfigurationKeyError) as exc_info:
        cipher.decrypt("invalid-token-containing-secret-value")

    assert "secret-value" not in str(exc_info.value)
