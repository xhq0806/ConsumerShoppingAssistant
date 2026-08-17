"""M1-D 动态维度确定性推荐领域测试。by AI.Coding"""

from app.domain.dimensions import DimensionSourceType
from app.domain.dimensions.recommendation import (
    DimensionCandidate,
    DimensionDataRisk,
    recommend_dimensions,
)


def _candidate(
    code: str,
    *,
    priority: int,
    aliases: tuple[str, ...] = (),
    affects_recommendation: bool = True,
) -> DimensionCandidate:
    """创建推荐器所需的最小受控目录项。by AI.Coding"""
    return DimensionCandidate(
        code=code,
        name=code,
        source_type=DimensionSourceType.PRODUCT_FACT,
        default_priority=priority,
        affects_recommendation=affects_recommendation,
        user_removable=True,
        aliases=aliases,
        description=f"{code} 说明",
    )


def test_user_concern_and_product_difference_drive_stable_default_selection() -> None:
    """用户关注项置顶，差异项其次，且默认选择数量稳定在 5～10。by AI.Coding"""
    candidates = (
        _candidate("price", priority=0, aliases=("价格",)),
        _candidate("screen", priority=1, aliases=("屏幕",)),
        _candidate("storage", priority=2, aliases=("存储",)),
        _candidate("battery_life", priority=3, aliases=("续航", "电池")),
        _candidate("camera", priority=4, aliases=("拍照",)),
        _candidate("performance", priority=5, aliases=("性能",)),
        _candidate("weight", priority=6, aliases=("重量",)),
        _candidate("charging", priority=7, aliases=("充电",)),
        _candidate("after_sales", priority=8, aliases=("售后",)),
        _candidate("brand_founded_year", priority=99, affects_recommendation=False),
    )
    values = {
        "price": ("3999.00", "3599.00"),
        "screen": ("6.5 英寸", None),
        "storage": ("256GB", None),
        "battery_life": (None, None),
        "camera": (None, None),
        "performance": (None, None),
        "weight": (None, None),
        "charging": (None, None),
        "after_sales": ("7 天无理由", None),
        "brand_founded_year": (None, None),
    }

    first = recommend_dimensions(
        candidates,
        product_values=values,
        priority_concerns=("我最在意续航", "旅行拍照"),
    )
    second = recommend_dimensions(
        candidates,
        product_values=values,
        priority_concerns=("我最在意续航", "旅行拍照"),
    )

    assert first == second
    assert [item.code for item in first[:2]] == ["battery_life", "camera"]
    selected = [item for item in first if item.selected]
    assert len(selected) == 8
    assert [item.position for item in selected] == list(range(8))
    assert first[0].reason == "匹配用户明确关注点"
    price = next(item for item in first if item.code == "price")
    assert price.has_difference is True
    assert price.data_risk is DimensionDataRisk.AVAILABLE
    screen = next(item for item in first if item.code == "screen")
    assert screen.data_risk is DimensionDataRisk.PARTIAL
    founded_year = next(item for item in first if item.code == "brand_founded_year")
    assert founded_year.affects_recommendation is False
    assert founded_year.selected is False


def test_unavailable_dimension_without_user_match_stays_after_available_differences() -> None:
    """无数据且未命中关注点的维度排在有事实差异的维度之后。by AI.Coding"""
    recommendations = recommend_dimensions(
        (
            _candidate("camera", priority=0, aliases=("拍照",)),
            _candidate("price", priority=50, aliases=("价格",)),
        ),
        product_values={
            "camera": (None, None),
            "price": ("3999.00", "3599.00"),
        },
        priority_concerns=(),
    )

    assert [item.code for item in recommendations] == ["price", "camera"]
    assert recommendations[0].reason == "候选商品在该维度存在差异"
    assert recommendations[1].data_risk is DimensionDataRisk.UNAVAILABLE
