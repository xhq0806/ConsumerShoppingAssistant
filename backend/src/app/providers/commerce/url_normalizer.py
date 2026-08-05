import hashlib
from urllib.parse import parse_qs, urlencode, urlunsplit

from app.core.config import Settings
from app.core.errors import URLSecurityError
from app.core.url_security import Resolver, validate_external_url
from app.providers.commerce.dto import NormalizedProductUrl

_ALLOWED_QUERY_KEYS = frozenset({"id"})


class TaobaoUrlNormalizer:
    def __init__(self, settings: Settings, resolver: Resolver | None = None) -> None:
        self._allowed_hosts = settings.taobao_allowed_hosts
        self._resolver = resolver

    def normalize(self, raw_url: str, *, resolve_dns: bool = True) -> NormalizedProductUrl:
        validated = validate_external_url(
            raw_url,
            allowed_hosts=self._allowed_hosts,
            resolver=self._resolver,
            resolve_dns=resolve_dns,
        )
        query = parse_qs(validated.parsed.query, keep_blank_values=False)
        product_ids = query.get("id", [])
        if len(product_ids) != 1 or not product_ids[0].strip():
            raise URLSecurityError("淘宝商品链接缺少唯一商品 ID。")
        product_id = product_ids[0].strip()
        if not product_id.isdigit():
            raise URLSecurityError("淘宝商品 ID 格式无效。")

        safe_query = urlencode({key: query[key][0] for key in _ALLOWED_QUERY_KEYS if key in query})
        canonical = urlunsplit(
            (
                "https",
                validated.normalized_host,
                validated.parsed.path or "/item.htm",
                safe_query,
                "",
            )
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return NormalizedProductUrl(
            canonical_url=canonical,
            host=validated.normalized_host,
            external_product_id=product_id,
            safe_url_fingerprint=fingerprint,
        )
