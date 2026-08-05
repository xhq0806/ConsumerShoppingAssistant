import pytest

from app.core.config import Settings
from app.core.errors import URLSecurityError
from app.providers.commerce.url_normalizer import TaobaoUrlNormalizer


def public_dns(_host: str) -> list[str]:
    return ["8.8.8.8"]


def normalizer(resolver=public_dns) -> TaobaoUrlNormalizer:
    return TaobaoUrlNormalizer(Settings(), resolver=resolver)


def test_normalizes_supported_taobao_url() -> None:
    result = normalizer().normalize(
        "https://item.taobao.com/item.htm?id=10001&spm=sensitive#reviews"
    )
    assert str(result.canonical_url) == "https://item.taobao.com/item.htm?id=10001"
    assert result.external_product_id == "10001"
    assert "spm" not in str(result.canonical_url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/item.htm?id=10001",
        "https://item.taobao.com.evil.example/item.htm?id=10001",
        "https://item.taobao.com@evil.example/item.htm?id=10001",
        "https://item.taobao.com./item.htm?id=10001",
        "file:///etc/passwd",
        "ftp://item.taobao.com/item.htm?id=10001",
        "https://item.taobao.com:8443/item.htm?id=10001",
        "https://item.taobao.com/item.htm?id=not-a-number",
    ],
)
def test_rejects_unsafe_or_unsupported_urls(url: str) -> None:
    with pytest.raises(URLSecurityError):
        normalizer().normalize(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"])
def test_rejects_taobao_host_resolving_to_unsafe_ip(address: str) -> None:
    with pytest.raises(URLSecurityError):
        normalizer(lambda _host: [address]).normalize("https://item.taobao.com/item.htm?id=10001")
