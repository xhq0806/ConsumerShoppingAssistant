"""M1-G 报告结构化输出、来源目录和降级规则测试。by AI.Coding"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.errors import InputError
from app.domain.reports import ReportClaimType
from app.domain.reports.generation import (
    PurchaseReportOutput,
    ReportClaimOutput,
    ReportDifferenceOutput,
    ReportDimensionInput,
    ReportGenerationContext,
    ReportMetricInput,
    ReportPreferencesInput,
    ReportProductInput,
    ReportSourceRefOutput,
    ReportSummaryOutput,
    ScenarioRecommendationOutput,
    build_fake_purchase_report,
    determine_report_warnings,
    validate_purchase_report_output,
)


def _context() -> ReportGenerationContext:
    """构造包含商品事实、指标和评论证据的报告输入。by AI.Coding"""
    comparison_id = uuid4()
    product_a = ReportProductInput(
        id=uuid4(),
        snapshot_id=uuid4(),
        title="星河 X1",
        category="手机",
        brand="星河",
        shop_name="星河店",
        price=Decimal("3999.00"),
        currency="CNY",
        specifications={"存储": "256GB"},
        after_sales=("7 天无理由",),
        review_count=2,
    )
    product_b = ReportProductInput(
        id=uuid4(),
        snapshot_id=uuid4(),
        title="云杉 S2",
        category="手机",
        brand=None,
        shop_name="云杉店",
        price=Decimal("3599.00"),
        currency="CNY",
        specifications={},
        after_sales=(),
        review_count=0,
    )
    dimension = ReportDimensionInput(
        id=uuid4(),
        code="price",
        name="价格",
        min_sample_size=0,
    )
    metric = ReportMetricInput(
        id=uuid4(),
        comparison_product_id=product_a.id,
        dimension_id=dimension.id,
        dimension_code=dimension.code,
        metric_type="coverage_ratio",
        numeric_value=Decimal("0.50000000"),
        sample_size=2,
        confidence=0.9,
    )
    return ReportGenerationContext(
        comparison_id=comparison_id,
        products=(product_a, product_b),
        dimensions=(dimension,),
        metrics=(metric,),
        evidences=(),
        preferences=ReportPreferencesInput(
            budget_min=Decimal("3000.00"),
            budget_max=Decimal("4500.00"),
            usage_scenarios=("日常通勤",),
            priority_concerns=("价格",),
            deal_breakers=(),
        ),
    )


def test_report_output_requires_known_products_dimensions_claim_indexes_and_sources() -> None:
    """所有展示索引和来源都必须解析到当前任务输入目录。by AI.Coding"""
    context = _context()
    recommended = context.products[1]
    claim = ReportClaimOutput(
        claim_type=ReportClaimType.RECOMMENDATION,
        text="基于当前预算和已获取价格，更建议云杉 S2。",
        source_refs=[
            ReportSourceRefOutput(
                type="product_snapshot",
                id=recommended.snapshot_id,
                field="price",
            )
        ],
        confidence=0.8,
    )
    output = PurchaseReportOutput(
        claims=[claim],
        summary=ReportSummaryOutput(
            headline="预算优先可考虑云杉 S2",
            recommended_product_id=recommended.id,
            recommendation_claim_index=0,
            scenario_recommendations=[
                ScenarioRecommendationOutput(
                    scenario="日常通勤",
                    product_id=recommended.id,
                    claim_index=0,
                )
            ],
            key_reason_claim_indexes=[0],
            risk_claim_indexes=[],
            confidence=0.8,
        ),
        differences=[ReportDifferenceOutput(dimension_code="price", claim_index=0)],
    )

    validated = validate_purchase_report_output(context=context, output=output)

    assert validated.claims[0].source_refs == (
        {
            "type": "product_snapshot",
            "id": str(recommended.snapshot_id),
            "field": "price",
        },
    )
    assert validated.summary.recommended_product_id == recommended.id

    unknown_source = output.model_copy(deep=True)
    unknown_source.claims[0].source_refs[0].id = uuid4()
    with pytest.raises(InputError, match="来源"):
        validate_purchase_report_output(context=context, output=unknown_source)

    invalid_index = output.model_copy(deep=True)
    invalid_index.summary.recommendation_claim_index = 9
    with pytest.raises(InputError, match="claim index"):
        validate_purchase_report_output(context=context, output=invalid_index)


def test_report_output_rejects_unknown_scenario_dimension_and_absolute_language() -> None:
    """模型不得创建场景/维度或输出绝对化推荐。by AI.Coding"""
    context = _context()
    output = build_fake_purchase_report(context)

    unknown_scenario = output.model_copy(deep=True)
    unknown_scenario.summary.scenario_recommendations[0].scenario = "专业潜水"
    with pytest.raises(InputError, match="场景"):
        validate_purchase_report_output(context=context, output=unknown_scenario)

    unknown_dimension = output.model_copy(deep=True)
    unknown_dimension.differences[0].dimension_code = "invented"
    with pytest.raises(InputError, match="维度"):
        validate_purchase_report_output(context=context, output=unknown_dimension)

    absolute = output.model_copy(deep=True)
    absolute.claims[0].text = "云杉 S2 绝对最好。"
    with pytest.raises(InputError, match="绝对化"):
        validate_purchase_report_output(context=context, output=absolute)


def test_fake_report_is_deterministic_and_missing_data_requires_partial() -> None:
    """Fake 报告选择预算内低价商品，Fixture 缺失字段稳定触发降级。by AI.Coding"""
    context = _context()

    output = build_fake_purchase_report(context)
    validated = validate_purchase_report_output(context=context, output=output)
    warnings = determine_report_warnings(context)

    assert validated.summary.recommended_product_id == context.products[1].id
    assert validated.differences[0].dimension_code == "price"
    assert any("品牌" in warning for warning in warnings)
    assert any("有效评论" in warning for warning in warnings)
