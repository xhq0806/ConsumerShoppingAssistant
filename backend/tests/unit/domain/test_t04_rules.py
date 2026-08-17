"""T04 品牌与维度领域纯规则测试。by AI.Coding"""

from dataclasses import dataclass

import pytest

from app.core.errors import DomainConflictError, InputError
from app.domain.brands import (
    BrandField,
    find_conflicting_brand_fields,
    normalize_brand_name,
    validate_brand_field_for_scoring,
    validate_confidence,
)
from app.domain.dimensions import (
    DimensionSourceType,
    normalize_dimension_code,
    validate_dimension_confirmation,
    validate_non_negative,
    validate_registered_dimension,
    validate_task_dimension_position,
)


@dataclass(frozen=True)
class SourceValue:
    """提供品牌冲突检测所需的最小测试结构。by AI.Coding"""

    field_name: BrandField
    value: object


def test_brand_name_normalization_is_deterministic() -> None:
    """品牌标准名统一 Unicode、大小写、标点和空白。by AI.Coding"""
    assert normalize_brand_name("  ACME（中国） Co., LTD. ") == "acme 中国 co ltd"
    assert normalize_brand_name("ＡＣＭＥ-中国 co ltd") == "acme 中国 co ltd"


def test_empty_normalized_brand_name_is_rejected() -> None:
    """只含标点的品牌名不能形成主档。by AI.Coding"""
    with pytest.raises(InputError, match="不能为空"):
        normalize_brand_name("---")


def test_conflicting_brand_sources_are_retained_and_detected() -> None:
    """同字段不同值不覆盖，纯规则返回冲突字段。by AI.Coding"""
    sources = [
        SourceValue(BrandField.FOUNDED_YEAR, 1998),
        SourceValue(BrandField.FOUNDED_YEAR, 2001),
        SourceValue(BrandField.PARENT_COMPANY, "同一公司"),
        SourceValue(BrandField.PARENT_COMPANY, "同一公司"),
    ]
    assert find_conflicting_brand_fields(sources) == {BrandField.FOUNDED_YEAR}


@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_confidence_accepts_closed_interval(confidence: float) -> None:
    """可信度接受 0 到 1 的闭区间。by AI.Coding"""
    assert validate_confidence(confidence) == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_rejects_outside_interval(confidence: float) -> None:
    """可信度拒绝区间外数值。by AI.Coding"""
    with pytest.raises(InputError, match="可信度"):
        validate_confidence(confidence)


def test_founded_year_can_never_be_auto_scored() -> None:
    """品牌成立年份即使有可靠值也只能展示。by AI.Coding"""
    with pytest.raises(DomainConflictError, match="只能展示"):
        validate_brand_field_for_scoring(
            BrandField.FOUNDED_YEAR, has_value=True, has_conflict=False
        )


@pytest.mark.parametrize(("has_value", "has_conflict"), [(False, False), (True, True)])
def test_unknown_or_conflicting_brand_field_cannot_be_scored(
    has_value: bool, has_conflict: bool
) -> None:
    """未知或冲突品牌事实不参与推荐计算。by AI.Coding"""
    with pytest.raises(DomainConflictError):
        validate_brand_field_for_scoring(
            BrandField.PARENT_COMPANY,
            has_value=has_value,
            has_conflict=has_conflict,
        )


def test_dimension_code_normalization_is_stable() -> None:
    """维度 code 统一为稳定 snake_case。by AI.Coding"""
    assert normalize_dimension_code(" Review-Quality ") == "review_quality"


@pytest.mark.parametrize("code", ["中文", "1price", "price!"])
def test_dimension_code_rejects_unstable_values(code: str) -> None:
    """维度 code 拒绝无法跨模型稳定引用的形式。by AI.Coding"""
    with pytest.raises(InputError, match="code"):
        normalize_dimension_code(code)


def test_registered_dimension_rejects_unknown_or_disabled_code() -> None:
    """业务 code 只能解析到已注册且 enabled 的目录记录。by AI.Coding"""
    dimension = object()
    assert validate_registered_dimension("review_quality", dimension, enabled=True) is dimension
    with pytest.raises(DomainConflictError, match="未注册"):
        validate_registered_dimension("unknown_code", None)
    with pytest.raises(DomainConflictError, match="停用"):
        validate_registered_dimension("review_quality", dimension, enabled=False)


def test_dimension_source_type_covers_five_sources() -> None:
    """维度来源类型完整覆盖规格要求的五种来源。by AI.Coding"""
    assert {item.value for item in DimensionSourceType} == {
        "product_fact",
        "brand_fact",
        "review_metric",
        "derived_metric",
        "user_preference",
    }


@pytest.mark.parametrize("value", [-1, -10])
def test_non_negative_dimension_values_reject_negative(value: int) -> None:
    """默认优先级和最小样本量拒绝负数。by AI.Coding"""
    with pytest.raises(InputError, match="不能为负"):
        validate_non_negative(value, field_name="测试字段")


@pytest.mark.parametrize(("selected", "position"), [(True, None), (False, 0), (True, -1)])
def test_task_dimension_position_rejects_invalid_state(
    selected: bool, position: int | None
) -> None:
    """任务维度排序与选中状态必须一致。by AI.Coding"""
    with pytest.raises(InputError):
        validate_task_dimension_position(selected=selected, position=position)


def test_dimension_confirmation_requires_unique_non_empty_codes() -> None:
    """维度确认拒绝空列表和规范化后重复 code。by AI.Coding"""
    assert validate_dimension_confirmation([" Review-Quality ", "price"]) == (
        "review_quality",
        "price",
    )
    with pytest.raises(InputError, match="至少"):
        validate_dimension_confirmation([])
    with pytest.raises(InputError, match="重复"):
        validate_dimension_confirmation(["review-quality", "review_quality"])
