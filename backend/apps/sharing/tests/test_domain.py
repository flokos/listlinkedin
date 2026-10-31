import pytest
from django.core.exceptions import ValidationError

from apps.sharing.domain import MAX_URL_LENGTH, normalize_destination_url
from apps.sharing.models import SharedList


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://example.com/a", "https://example.com/a"),
        ("  HTTPS://Example.COM/Path  ", "https://example.com/Path"),
        ("http://example.com:8080/x?b=2&a=1#Frag", "http://example.com:8080/x?b=2&a=1#Frag"),
        # RFC 3986 equivalences: empty path is "/", the default port is redundant.
        ("https://example.com", "https://example.com/"),
        ("https://Example.com:443", "https://example.com/"),
        ("http://example.com:80/a?x=1", "http://example.com/a?x=1"),
        ("http://example.com:443/", "http://example.com:443/"),  # not http's default
        ("http://[::1]:80/", "http://[::1]/"),
        ("https://example.com?q=1", "https://example.com/?q=1"),
        # Internationalized hosts are stored in ASCII (punycode) form; the path is untouched.
        ("https://Bücher.example/Straße", "https://xn--bcher-kva.example/Straße"),
        ("https://xn--bcher-kva.example/", "https://xn--bcher-kva.example/"),
        # Browsers keep ß and ς (IDNA2008/UTS46); the old IDNA2003 codec turned "faß" into
        # "fass", which is a different domain.
        ("https://faß.example/", "https://xn--fa-hia.example/"),
        ("https://ςοφία.example/", "https://xn--kxae4blv.example/"),
        ("https://example.com.:8443/", "https://example.com:8443/"),
    ],
)
def test_normalization_only_applies_meaning_preserving_rules(raw, expected):
    assert normalize_destination_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "ftp://example.com/file",
        "javascript:alert(1)",
        "example.com/no-scheme",
        "https://user:pass@example.com/",
        "https://user@example.com/",
        "https://",
        "https://exa mple.com/",
        "http://[::1",  # unclosed IPv6 bracket: used to crash with a 500
        "https://example.com:99999/",  # port out of range
        "https://example.com:abc/",
        "http://example.com:0/",
        # Other names this service answers to (ALLOWED_HOSTS in development).
        "http://127.0.0.1:8000/r/AAAAAAAAAAAAAAAA",
        "http://LOCALHOST:8000/l/x",
        "https://example.com/" + "a" * MAX_URL_LENGTH,
        "https://example.com/" + "😀" * 600,  # 600 characters but 2400 bytes
        "https://" + "ü" * 70 + ".example/",  # IDNA label longer than 63 characters
    ],
)
def test_rejects_invalid_destinations(raw):
    with pytest.raises(ValidationError):
        normalize_destination_url(raw)


def test_lists_store_no_owner_token():
    """V1 tested its 256-bit tokens and their SHA-256 digests here. Since task 9.6 no token is
    generated or stored: the column is gone (sharing.0011), and an account owns every list."""
    names = {field.name for field in SharedList._meta.get_fields()}
    assert "owner_token_hash" not in names
    assert not SharedList._meta.get_field("owner").null
