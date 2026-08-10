"""M1-C 用户偏好领域值对象测试。by AI.Coding"""

from decimal import Decimal

import pytest

from app.core.errors import InputError
from app.domain.comparisons.preferences import UserPreferences


def test_preferences_normalize_deduplicate_and_round_trip() -> None:
    """偏好应规范化文本、保持顺序去重并稳定往返 JSONB。by AI.Coding"""
    preferences = UserPreferences.create(
        budget_min=Decimal("3000.00"),
        budget_max=Decimal("4500.00"),
        usage_scenarios=["  日常　通勤 ", "日常 通勤", "旅行拍照"],
        priority_concerns=["续航", " 拍照 "],
        deal_breakers=["机身过重", "机身过重"],
    )

    assert preferences.usage_scenarios == ("日常 通勤", "旅行拍照")
    assert preferences.priority_concerns == ("续航", "拍照")
    assert preferences.deal_breakers == ("机身过重",)
    assert preferences.to_persisted() == {
        "budget_min": "3000.00",
        "budget_max": "4500.00",
        "usage_scenarios": ["日常 通勤", "旅行拍照"],
        "priority_concerns": ["续航", "拍照"],
        "deal_breakers": ["机身过重"],
    }
    assert UserPreferences.from_persisted(preferences.to_persisted()) == preferences


@pytest.mark.parametrize(
    ("budget_min", "budget_max"),
    [
        (Decimal("-0.01"), Decimal("100.00")),
        (Decimal("100.00"), Decimal("99.99")),
        (Decimal("0.001"), Decimal("100.00")),
        (None, Decimal("1000000.01")),
    ],
)
def test_preferences_reject_invalid_budget(
    budget_min: Decimal | None, budget_max: Decimal | None
) -> None:
    """预算应拒绝负数、倒置、超范围和超过两位小数。by AI.Coding"""
    with pytest.raises(InputError):
        UserPreferences.create(
            budget_min=budget_min,
            budget_max=budget_max,
            usage_scenarios=["日常使用"],
            priority_concerns=["续航"],
            deal_breakers=[],
        )


@pytest.mark.parametrize(
    ("usage_scenarios", "priority_concerns", "deal_breakers"),
    [
        ([], ["续航"], []),
        (["日常使用"], [], []),
        (["x" * 81], ["续航"], []),
        ([f"场景{index}" for index in range(6)], ["续航"], []),
        (["日常使用"], [f"关注点{index}" for index in range(9)], []),
        (["日常使用"], ["续航"], [f"禁忌{index}" for index in range(9)]),
    ],
)
def test_preferences_reject_invalid_text_collections(
    usage_scenarios: list[str],
    priority_concerns: list[str],
    deal_breakers: list[str],
) -> None:
    """偏好文本集合应满足必填、单项长度和数量限制。by AI.Coding"""
    with pytest.raises(InputError):
        UserPreferences.create(
            budget_min=None,
            budget_max=None,
            usage_scenarios=usage_scenarios,
            priority_concerns=priority_concerns,
            deal_breakers=deal_breakers,
        )
