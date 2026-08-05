import ipaddress
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

from app.core.errors import URLSecurityError

Resolver = Callable[[str], Iterable[str]]


@dataclass(frozen=True, slots=True)
class ValidatedURL:
    parsed: SplitResult
    normalized_host: str


def _default_resolver(host: str) -> Iterable[str]:
    addresses: set[str] = set()
    for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
        addresses.add(str(item[4][0]))
    return addresses


def _is_forbidden_ip(value: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(value, ipaddress.IPv6Address) and value.ipv4_mapped is not None:
        value = value.ipv4_mapped
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    metadata = ipaddress.ip_network("169.254.169.254/32")
    return (
        value.is_loopback
        or value.is_private
        or value.is_link_local
        or value.is_unspecified
        or value.is_multicast
        or value.is_reserved
        or value in cgnat
        or value in metadata
    )


def _normalize_host(host: str) -> str:
    if host.endswith("."):
        raise URLSecurityError("链接域名不能使用尾随点形式。")
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise URLSecurityError("链接域名格式无效。") from exc


def _host_allowed(host: str, allowed_hosts: frozenset[str]) -> bool:
    return host in allowed_hosts


def validate_external_url(
    raw_url: str,
    *,
    allowed_hosts: Iterable[str],
    resolver: Resolver | None = None,
    resolve_dns: bool = True,
) -> ValidatedURL:
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError as exc:
        raise URLSecurityError("链接格式无效。") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise URLSecurityError("仅支持 HTTP 或 HTTPS 商品链接。")
    if not parsed.hostname:
        raise URLSecurityError("商品链接缺少有效域名。")
    if parsed.username is not None or parsed.password is not None:
        raise URLSecurityError("商品链接不能包含用户认证信息。")
    if port not in {None, 80, 443}:
        raise URLSecurityError("商品链接使用了不受支持的端口。")

    host = _normalize_host(parsed.hostname)
    normalized_allowed = frozenset(_normalize_host(item) for item in allowed_hosts)
    if not _host_allowed(host, normalized_allowed):
        raise URLSecurityError("当前版本仅支持已批准的淘宝商品域名。")

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        raise URLSecurityError("商品链接不能使用 IP 地址。")

    if resolve_dns:
        resolve = resolver or _default_resolver
        try:
            addresses = list(resolve(host))
        except OSError as exc:
            raise URLSecurityError("商品链接域名无法安全解析。") from exc
        if not addresses:
            raise URLSecurityError("商品链接域名没有可用地址。")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError as exc:
                raise URLSecurityError("商品链接解析结果无效。") from exc
            if _is_forbidden_ip(ip):
                raise URLSecurityError("商品链接解析到了不允许访问的网络地址。")

    return ValidatedURL(parsed=parsed, normalized_host=host)


def validate_redirect_target(
    target_url: str,
    *,
    allowed_hosts: Iterable[str],
    resolver: Resolver | None = None,
) -> ValidatedURL:
    return validate_external_url(
        target_url,
        allowed_hosts=allowed_hosts,
        resolver=resolver,
        resolve_dns=True,
    )
