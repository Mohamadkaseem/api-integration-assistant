"""Encrypts and decrypts saved credentials.

Uses Fernet (from the `cryptography` library): AES encryption plus a tamper check.
The key comes from CREDENTIALS_KEY in .env, or from data/credentials.key, which is
created automatically the first time. Neither is ever committed to Git.
"""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CredentialDecryptError(Exception):
    """The stored secret cannot be read with the current key (key changed or lost)."""


@lru_cache
def get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.credentials_key.get_secret_value().strip()
    if not key:
        path = Path(settings.credentials_key_file)
        if path.exists():
            key = path.read_text().strip()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            key = Fernet.generate_key().decode()
            path.write_text(key)
            try:
                os.chmod(path, 0o600)  # owner-only on Mac/Linux; ignored on Windows
            except OSError:
                pass
            logger.warning("Created a new credentials encryption key at %s - back this file up.", path)
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise RuntimeError("CREDENTIALS_KEY is not a valid key. Remove it to let the app create one.") from exc


def encrypt_json(data: dict) -> str:
    return get_fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_json(token: str) -> dict:
    if not token:
        return {}
    try:
        return json.loads(get_fernet().decrypt(token.encode()))
    except InvalidToken as exc:
        raise CredentialDecryptError(
            "This credential cannot be decrypted - the encryption key changed or data/credentials.key was lost. "
            "Delete the credential and enter it again."
        ) from exc
