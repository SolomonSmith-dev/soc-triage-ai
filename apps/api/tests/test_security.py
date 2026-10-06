"""Tests for password and API key hashing."""
from __future__ import annotations

import pytest

from soc_api.security import (
    MIN_PASSWORD_LENGTH,
    generate_api_key,
    hash_password,
    needs_rehash,
    verify_api_key,
    verify_password,
)


class TestPasswordHashing:
    def test_round_trip(self) -> None:
        h = hash_password("correct horse battery")
        assert verify_password(h, "correct horse battery")

    def test_wrong_password_rejected(self) -> None:
        h = hash_password("correct horse battery")
        assert not verify_password(h, "wrong horse battery")

    def test_short_password_rejected(self) -> None:
        with pytest.raises(ValueError):
            hash_password("a" * (MIN_PASSWORD_LENGTH - 1))

    def test_minimum_length_accepted(self) -> None:
        h = hash_password("a" * MIN_PASSWORD_LENGTH)
        assert verify_password(h, "a" * MIN_PASSWORD_LENGTH)

    def test_hashes_unique_per_call(self) -> None:
        a = hash_password("correct horse battery")
        b = hash_password("correct horse battery")
        assert a != b
        assert verify_password(a, "correct horse battery")
        assert verify_password(b, "correct horse battery")

    def test_needs_rehash_false_for_current(self) -> None:
        h = hash_password("correct horse battery")
        assert not needs_rehash(h)


class TestApiKeyHashing:
    def test_generated_keys_round_trip(self) -> None:
        plaintext, h = generate_api_key()
        assert len(plaintext) >= 40
        assert verify_api_key(h, plaintext)

    def test_wrong_key_rejected(self) -> None:
        _, h = generate_api_key()
        other_plaintext, _ = generate_api_key()
        assert not verify_api_key(h, other_plaintext)

    def test_keys_unique(self) -> None:
        a, _ = generate_api_key()
        b, _ = generate_api_key()
        assert a != b
