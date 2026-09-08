"""Security and credential encryption utilities for Inim Cloud integration."""
import base64
import hashlib
import logging
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Sensitive keys to redact in logs
SENSITIVE_KEYS = {
    "password",
    "username",
    "token",
    "pin",
    "key",
    "authorization",
    "secret",
}


def _get_encryption_key(hass: HomeAssistant) -> bytes:
    """Derive a deterministic 32-byte Fernet key from the Home Assistant instance UUID."""
    # Obtain instance unique ID or fallback to stable system salt
    instance_id = hass.data.get("core.uuid") or "inim_cloud_default_instance_salt"
    salt = b"inim_cloud_security_salt_v1"
    derived = hashlib.pbkdf2_hmac("sha256", instance_id.encode("utf-8"), salt, 100000)
    return base64.urlsafe_b64encode(derived)


def encrypt_credential(hass: HomeAssistant, plaintext: str) -> str:
    """Encrypt sensitive plaintext (e.g. password) using an instance-bound Fernet key."""
    if not plaintext:
        return ""
    try:
        fernet = Fernet(_get_encryption_key(hass))
        encrypted = fernet.encrypt(plaintext.encode("utf-8"))
        return f"enc:{encrypted.decode('utf-8')}"
    except Exception as ex:
        _LOGGER.error("Error encrypting credential at rest: %s", ex)
        return plaintext


def decrypt_credential(hass: HomeAssistant, ciphertext: str) -> str:
    """Decrypt ciphertext stored at rest."""
    if not ciphertext:
        return ""
    if not ciphertext.startswith("enc:"):
        # Not encrypted (legacy or unencrypted transition)
        return ciphertext
    try:
        fernet = Fernet(_get_encryption_key(hass))
        raw_token = ciphertext[4:].encode("utf-8")
        decrypted = fernet.decrypt(raw_token)
        return decrypted.decode("utf-8")
    except InvalidToken:
        _LOGGER.error("Failed to decrypt stored credential (instance key mismatch).")
        raise
    except Exception as ex:
        _LOGGER.error("Unexpected error during credential decryption: %s", ex)
        raise


def redact_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive keys in dictionaries or lists before logging."""
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            if any(s_key in str(key).lower() for s_key in SENSITIVE_KEYS):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_sensitive_data(value)
        return redacted
    if isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data
