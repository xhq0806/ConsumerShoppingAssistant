"""M1-G 报告 Gateway profile 与安全审计契约测试。by AI.Coding"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.report_generation import GatewayPurchaseReportGenerator
from app.core.config import Settings
from app.domain.reports.generation import (
    ReportDimensionInput,
    ReportGenerationContext,
    ReportPreferencesInput,
    ReportProductInput,
)


@pytest.mark.asyncio
async def test_fake_report_generator_uses_report_profile_and_audits_no_prompt() -> None:
    """Fake 与 DeepSeek 共用 report Gateway，审计不包含偏好或商品正文。by AI.Coding"""
    first = ReportProductInput(
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
    second = ReportProductInput(
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
    context = ReportGenerationContext(
        comparison_id=uuid4(),
        products=(first, second),
        dimensions=(
            ReportDimensionInput(
                id=uuid4(),
                code="price",
                name="价格",
                min_sample_size=0,
            ),
        ),
        metrics=(),
        evidences=(),
        preferences=ReportPreferencesInput(
            budget_min=Decimal("3000.00"),
            budget_max=Decimal("4500.00"),
            usage_scenarios=("日常通勤",),
            priority_concerns=("价格",),
            deal_breakers=(),
        ),
    )

    invocation = await GatewayPurchaseReportGenerator(Settings()).generate(
        context=context,
        trace_id="trace-m1g-safe",
    )

    assert invocation.audit_event.purpose == "purchase_report"
    assert invocation.audit_event.provider == "fake"
    assert invocation.audit_event.prompt_version == "m1g-purchase-report-v1"
    assert invocation.audit_event.status == "success"
    assert invocation.report.summary.recommended_product_id == second.id
    audit_json = invocation.audit_event.model_dump_json()
    assert first.title not in audit_json
    assert "日常通勤" not in audit_json
    assert "reasoning" not in audit_json
