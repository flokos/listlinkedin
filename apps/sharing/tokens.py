"""Private ownership tokens. Only their SHA-256 digest is ever stored."""

import hashlib
import hmac
import secrets


def generate_owner_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def hash_owner_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_owner_token(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_owner_token(token), expected_hash)
