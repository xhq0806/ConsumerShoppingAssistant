"""可持久化 JSON 的递归敏感键检测规则。by AI.Coding"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.errors import InputError

_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set_cookie",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "session_token",
        "password",
        "secret",
        "client_secret",
        "raw_payload",
        "prompt",
        "response",
    }
)


def normalize_json_key(key: object) -> str:
    """把 JSON 键规范化为便于安全比较的 snake_case。by AI.Coding"""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def find_sensitive_json_keys(value: Any, *, path: str = "$") -> tuple[str, ...]:
    """递归返回映射或数组中命中的敏感键路径。by AI.Coding"""
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = normalize_json_key(key)
            child_path = f"{path}.{key}"
            # 同时匹配精确键和常见带前后缀形式，避免 credentials.apiKey 等变体。
            if normalized in _SENSITIVE_KEYS or any(
                normalized.endswith(f"_{item}") for item in _SENSITIVE_KEYS
            ):
                matches.append(child_path)
            matches.extend(find_sensitive_json_keys(nested, path=child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, nested in enumerate(value):
            matches.extend(find_sensitive_json_keys(nested, path=f"{path}[{index}]"))
    return tuple(matches)


def validate_no_sensitive_json_keys(value: Any) -> Any:
    """拒绝包含敏感键的可持久化 JSON，并原样返回安全值。by AI.Coding"""
    matches = find_sensitive_json_keys(value)
    if matches:
        raise InputError(f"JSON 包含禁止持久化的敏感键：{', '.join(matches)}")
    return value
