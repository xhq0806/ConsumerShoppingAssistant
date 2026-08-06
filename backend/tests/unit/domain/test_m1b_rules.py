"""M1-B 纯领域规则测试。by AI.Coding"""

from uuid import uuid4

import pytest

from app.core.errors import DomainConflictError, InputError
from app.domain.comparisons import (
    ComparableProduct,
    create_request_fingerprint,
    idempotency_key_hash,
    normalize_category,
    normalize_idempotency_key,
    validate_basic_comparability,
    validate_confirmation_set,
)
from app.providers.commerce.dto import NormalizedProductUrl


def _product_url(product_id: str) -> NormalizedProductUrl:
    """构造不触发网络访问的规范化测试商品 URL。by AI.Coding"""
    # 固定安全指纹使 fingerprint 测试只聚焦候选顺序和窗口。
    return NormalizedProductUrl(
        canonical_url=f"https://item.taobao.com/item.htm?id={product_id}",
        host="item.taobao.com",
        external_product_id=product_id,
        safe_url_fingerprint=product_id.zfill(64),
    )


def test_idempotency_key_is_trimmed_and_hashed_without_plaintext() -> None:
    """确认空白归一化后的同一幂等键得到相同摘要。by AI.Coding"""
    # 该摘要是唯一允许进入持久化层的幂等键表示。
    assert normalize_idempotency_key("  abcdefgh  ") == "abcdefgh"
    assert idempotency_key_hash("abcdefgh") == idempotency_key_hash("  abcdefgh  ")


@pytest.mark.parametrize("value", ["short", " " * 8, "x" * 129])
def test_idempotency_key_rejects_invalid_normalized_length(value: str) -> None:
    """确认非法幂等键在摘要前被稳定拒绝。by AI.Coding"""
    # 规范化后长度而非原始输入长度决定有效性。
    with pytest.raises(InputError):
        normalize_idempotency_key(value)


def test_request_fingerprint_preserves_order_and_review_window() -> None:
    """确认创建载荷摘要区分候选顺序和评论窗口。by AI.Coding"""
    first, second = _product_url("10001"), _product_url("10002")
    assert create_request_fingerprint([first, second], 30) != create_request_fingerprint(
        [second, first], 30
    )
    assert create_request_fingerprint([first, second], 30) != create_request_fingerprint(
        [first, second], 60
    )


def test_confirmation_set_requires_exactly_once_coverage() -> None:
    """确认确认集合拒绝重复、遗漏与任务外商品。by AI.Coding"""
    first, second, outside = uuid4(), uuid4(), uuid4()
    # 完整集合允许任意提交顺序，但每项只能出现一次。
    validate_confirmation_set({first, second}, [second, first])
    for submitted in ([first, first], [first], [first, outside]):
        with pytest.raises(InputError):
            validate_confirmation_set({first, second}, submitted)


def test_category_comparability_normalizes_text_and_warns_for_missing() -> None:
    """确认类别规则仅做确定性文本归一化且缺失时不阻断。by AI.Coding"""
    first, second = uuid4(), uuid4()
    # 全角字符、大小写与连续空白归一化后视为同一类别。
    assert normalize_category("  Ｐｈｏｎｅ\t Case ") == "phone case"
    assert (
        validate_basic_comparability(
            [
                ComparableProduct(first, "ＰＨＯＮＥ case"),
                ComparableProduct(second, " phone  CASE "),
            ]
        )
        == []
    )
    assert (
        validate_basic_comparability(
            [ComparableProduct(first, "phone case"), ComparableProduct(second, None)]
        )[0].code
        == "CATEGORY_INFORMATION_INCOMPLETE"
    )


def test_category_comparability_rejects_distinct_known_categories() -> None:
    """确认两个以上不同已知类别会阻断推进。by AI.Coding"""
    # 不引入模糊语义映射，规范化后不同即可稳定拒绝。
    with pytest.raises(DomainConflictError):
        validate_basic_comparability(
            [ComparableProduct(uuid4(), "phone"), ComparableProduct(uuid4(), "laptop")]
        )
