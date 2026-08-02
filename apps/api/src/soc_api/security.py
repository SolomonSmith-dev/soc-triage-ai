"""Password and API key hashing.

argon2id is used for both user passwords and API keys (OWASP-recommended,
memory-hard, resistant to GPU/ASIC attacks). Default argon2-cffi parameters
target ~50ms hash time on commodity hardware which is appropriate for
interactive auth.

API keys are random URL-safe tokens; only their argon2id hash is stored.
The plaintext key is shown to the operator exactly once at issuance.
"""
from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 12
API_KEY_BYTES = 32


def hash_password(plaintext: str) -> str:
    if len(plaintext) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    return _hasher.hash(plaintext)


def verify_password(stored_hash: str, plaintext: str) -> bool:
    try:
        return _hasher.verify(stored_hash, plaintext)
    except VerifyMismatchError:
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def generate_api_key() -> tuple[str, str]:
    plaintext = secrets.token_urlsafe(API_KEY_BYTES)
    return plaintext, _hasher.hash(plaintext)


def verify_api_key(stored_hash: str, plaintext: str) -> bool:
    try:
        return _hasher.verify(stored_hash, plaintext)
    except VerifyMismatchError:
        return False
