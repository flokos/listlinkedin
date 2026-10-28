import base64
import secrets

SHORT_CODE_LENGTH = 16


def generate_short_code() -> str:
    """Return a 16-character URL-safe code carrying 96 bits of randomness."""
    random_bytes = secrets.token_bytes(12)
    return base64.urlsafe_b64encode(random_bytes).decode("ascii").rstrip("=")
