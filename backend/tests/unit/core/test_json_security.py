"""可持久化 JSON 敏感键安全测试。by AI.Coding"""

import pytest

from app.core.errors import InputError
from app.core.json_security import find_sensitive_json_keys, validate_no_sensitive_json_keys


def test_recursive_sensitive_key_detection_covers_nested_payloads() -> None:
    """典型 JSONB payload 中嵌套数组和对象的敏感键均可被定位。by AI.Coding"""
    payload = {
        "summary": {"title": "safe"},
        "differences": [
            {"field": "price", "details": {"Authorization": "Bearer x"}},
            {"field": "shop", "credentials": {"apiKey": "x"}},
        ],
    }
    assert find_sensitive_json_keys(payload) == (
        "$.differences[0].details.Authorization",
        "$.differences[1].credentials.apiKey",
    )
    with pytest.raises(InputError, match="敏感键"):
        validate_no_sensitive_json_keys(payload)


def test_typical_safe_persisted_json_payload_is_accepted() -> None:
    """任务偏好、规格、报告分块和来源 ID 等普通结构不被误报。by AI.Coding"""
    payload = {
        "preferences": {"budget": 3000, "features": ["quiet", "light"]},
        "specifications": {"weight": "1.2kg"},
        "warnings": [{"code": "LOW_SAMPLE", "sample_size": 3}],
        "source_refs": [{"type": "analysis_metric", "id": "safe-id"}],
    }
    assert find_sensitive_json_keys(payload) == ()
    assert validate_no_sensitive_json_keys(payload) is payload
