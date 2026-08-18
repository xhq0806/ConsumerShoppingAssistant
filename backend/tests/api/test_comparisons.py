"""M1-B 对比 API 契约和依赖替换测试。by AI.Coding"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_analysis_service,
    get_comparison_service,
    get_report_service,
)
from app.application.analysis_tasks import AnalysisProgressView
from app.application.comparisons import (
    ComparisonView,
    ConfirmDimensionsCommand,
    CreateComparisonCommand,
    DimensionSetView,
    DimensionView,
    ProductView,
    UpdatePreferencesCommand,
)
from app.application.report_generation import (
    ComparisonReportView,
    ReportClaimView,
)
from app.domain.comparisons.preferences import UserPreferences
from app.main import create_app


class _FakeComparisonService:
    """提供无数据库 API 契约测试所需的最小替身。by AI.Coding"""

    def __init__(self) -> None:
        """初始化用于断言路由映射结果的调用记录。by AI.Coding"""
        self.created: tuple[CreateComparisonCommand, str | None] | None = None
        self.updated_preferences: UpdatePreferencesCommand | None = None
        self.confirmed_dimensions: ConfirmDimensionsCommand | None = None
        self.comparison_id = uuid4()

    async def create_comparison(
        self, command: CreateComparisonCommand, *, idempotency_key: str | None
    ) -> ComparisonView:
        """记录创建请求并返回稳定空快照摘要。by AI.Coding"""
        # 路由测试不涉及 ORM，返回最小白名单视图以验证 schema 映射。
        self.created = (command, idempotency_key)
        return self._view()

    async def parse_products(self, _comparison_id: object) -> ComparisonView:
        """返回最小详情以覆盖解析路由注册。by AI.Coding"""
        return self._view()

    async def get_comparison(self, _comparison_id: object) -> ComparisonView:
        """返回最小详情以覆盖查询路由注册。by AI.Coding"""
        return self._view()

    async def confirm_products(self, _comparison_id: object, _command: object) -> ComparisonView:
        """返回最小详情以覆盖确认路由注册。by AI.Coding"""
        return self._view()

    async def update_preferences(
        self, _comparison_id: object, command: UpdatePreferencesCommand
    ) -> ComparisonView:
        """记录偏好替换命令并返回带规范化偏好的详情。by AI.Coding"""
        self.updated_preferences = command
        return self._view(
            preferences=UserPreferences.create(
                budget_min=command.budget_min,
                budget_max=command.budget_max,
                usage_scenarios=command.usage_scenarios,
                priority_concerns=command.priority_concerns,
                deal_breakers=command.deal_breakers,
            )
        )

    async def generate_dimension_recommendations(self, _comparison_id: object) -> DimensionSetView:
        """返回稳定的维度候选集合。by AI.Coding"""
        return self._dimension_set()

    async def get_dimensions(self, _comparison_id: object) -> DimensionSetView:
        """返回稳定的维度恢复集合。by AI.Coding"""
        return self._dimension_set()

    async def confirm_dimensions(
        self, _comparison_id: object, command: ConfirmDimensionsCommand
    ) -> DimensionSetView:
        """记录确认命令并返回 queued 集合。by AI.Coding"""
        self.confirmed_dimensions = command
        return self._dimension_set(status="queued")

    async def request_analysis(self, _comparison_id: object) -> AnalysisProgressView:
        """返回 queued 分析投递进度。by AI.Coding"""
        return self._analysis_progress()

    async def retry_analysis(self, _comparison_id: object) -> AnalysisProgressView:
        """返回重新排队后的分析进度。by AI.Coding"""
        return self._analysis_progress()

    async def get_analysis_progress(self, _comparison_id: object) -> AnalysisProgressView:
        """返回降级报告已完成的稳定进度。by AI.Coding"""
        return self._analysis_progress(status="partially_completed", progress=100)

    async def get_latest_report(self, _comparison_id: object) -> ComparisonReportView:
        """返回带来源 claim 的稳定降级报告。by AI.Coding"""
        report_id = uuid4()
        product_id = uuid4()
        snapshot_id = uuid4()
        return ComparisonReportView(
            id=report_id,
            comparison_id=self.comparison_id,
            version=1,
            status="partial",
            summary={
                "headline": "当前更适合预算优先选择",
                "recommended_product_id": str(product_id),
                "recommendation_claim_index": 0,
                "scenario_recommendations": [],
                "key_reason_claim_indexes": [0],
                "risk_claim_indexes": [],
                "confidence": 0.72,
            },
            differences=(
                {
                    "dimension_code": "price",
                    "dimension_name": "价格",
                    "claim_index": 0,
                },
            ),
            full_comparison={
                "products": [
                    {
                        "id": str(product_id),
                        "title": "云杉 S2",
                        "price": "3599.00",
                        "currency": "CNY",
                        "metrics": [],
                    }
                ],
                "dimensions": [],
                "task_metrics": [],
                "evidence_count": 0,
            },
            warnings=("云杉 S2 缺少品牌信息。",),
            generated_at=datetime.now(UTC),
            claims=(
                ReportClaimView(
                    id=uuid4(),
                    claim_type="recommendation",
                    text="基于当前预算和价格，更建议考虑云杉 S2。",
                    source_refs=(
                        {
                            "type": "product_snapshot",
                            "id": str(snapshot_id),
                            "field": "price",
                        },
                    ),
                    confidence=0.72,
                    display_order=0,
                ),
            ),
        )

    def _view(self, *, preferences: UserPreferences | None = None) -> ComparisonView:
        """构造无敏感字段的稳定应用视图。by AI.Coding"""
        # 固定空事件与快照，专注 API 路由而不复制领域或数据库测试职责。
        return ComparisonView(
            id=self.comparison_id,
            status="draft",
            review_window_days=30,
            progress=0,
            products=(
                ProductView(
                    id=uuid4(),
                    position=0,
                    platform="taobao",
                    external_product_id="10001",
                    parse_status="pending",
                    selected_sku_id=None,
                    latest_snapshot=None,
                    skus=(),
                ),
                ProductView(
                    id=uuid4(),
                    position=1,
                    platform="taobao",
                    external_product_id="10002",
                    parse_status="pending",
                    selected_sku_id=None,
                    latest_snapshot=None,
                    skus=(),
                ),
            ),
            events=(),
            preferences=preferences,
        )

    def _dimension_set(
        self, *, status: str = "awaiting_dimension_confirmation"
    ) -> DimensionSetView:
        """构造不暴露 config 的最小动态维度视图。by AI.Coding"""
        return DimensionSetView(
            comparison_id=self.comparison_id,
            status=status,
            category="手机",
            generated=True,
            dimensions=(
                DimensionView(
                    code="price",
                    name="价格",
                    source_type="product_fact",
                    selected=True,
                    position=0,
                    user_selected=False,
                    reason="候选商品在该维度存在差异",
                    data_risk="available",
                    has_difference=True,
                    affects_recommendation=True,
                    user_removable=True,
                    description="比较价格。",
                ),
            ),
        )

    def _analysis_progress(
        self, *, status: str = "queued", progress: int = 0
    ) -> AnalysisProgressView:
        """构造分析 API 路由测试所需的最小进度视图。by AI.Coding"""
        return AnalysisProgressView(
            comparison_id=self.comparison_id,
            status=status,
            progress=progress,
            stage="queued" if status == "queued" else "partially_completed",
            message="任务已排队。" if status == "queued" else "降级报告已生成。",
            fetched_review_count=0 if status == "queued" else 3,
            valid_review_count=0 if status == "queued" else 2,
            annotated_review_count=0 if status == "queued" else 1,
            annotation_count=0 if status == "queued" else 1,
            metric_count=0 if status == "queued" else 144,
            can_retry=False,
            polling_complete=status in {"completed", "partially_completed", "failed"},
        )


@pytest.fixture
def comparison_app() -> tuple[FastAPI, _FakeComparisonService]:
    """创建带 service override 的 FastAPI 应用。by AI.Coding"""
    fake_service = _FakeComparisonService()
    application = create_app()
    # 覆盖统一依赖工厂，证明路由可测试且不会自行访问 ORM 或 Provider。
    application.dependency_overrides[get_comparison_service] = lambda: fake_service
    application.dependency_overrides[get_analysis_service] = lambda: fake_service
    application.dependency_overrides[get_report_service] = lambda: fake_service
    return application, fake_service


@pytest.mark.asyncio
async def test_create_comparison_contract_and_idempotency_header(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """确认创建端点使用稳定 operation 契约并传递幂等键。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/comparisons",
            headers={"Idempotency-Key": "12345678"},
            json={
                "product_urls": [
                    "https://item.taobao.com/item.htm?id=10001",
                    "https://item.taobao.com/item.htm?id=10002",
                ],
                "review_window_days": 30,
            },
        )
    assert response.status_code == 201
    assert fake_service.created == (
        CreateComparisonCommand(
            (
                "https://item.taobao.com/item.htm?id=10001",
                "https://item.taobao.com/item.htm?id=10002",
            ),
            30,
        ),
        "12345678",
    )
    assert "canonical_url" not in response.text
    assert response.json()["products"][0]["position"] == 0


@pytest.mark.asyncio
async def test_comparison_routes_forbid_extra_input_and_publish_operation_ids(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """确认请求白名单和四个 OpenAPI operation ID 保持稳定。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        invalid = await client.post(
            "/api/v1/comparisons",
            json={
                "product_urls": ["a", "b"],
                "review_window_days": 30,
                "unexpected": True,
            },
        )
        detail = await client.get(f"/api/v1/comparisons/{fake_service.comparison_id}")
        openapi = (await client.get("/openapi.json")).json()
    assert invalid.status_code == 422
    assert detail.status_code == 200
    operation_ids = {
        operation["operationId"]
        for path in openapi["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert {
        "create_comparison",
        "parse_comparison_products",
        "get_comparison",
        "confirm_comparison_products",
        "update_comparison_preferences",
        "generate_comparison_dimension_recommendations",
        "get_comparison_dimensions",
        "confirm_comparison_dimensions",
        "start_comparison_analysis",
        "retry_comparison_analysis",
        "get_comparison_analysis_progress",
        "get_comparison_report",
    } <= operation_ids


@pytest.mark.asyncio
async def test_update_preferences_contract_maps_decimal_and_text_collections(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """偏好接口应映射金额、文本集合并返回稳定恢复结构。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.put(
            f"/api/v1/comparisons/{fake_service.comparison_id}/preferences",
            json={
                "review_window_days": 60,
                "budget_min": "3000.00",
                "budget_max": "4500.00",
                "usage_scenarios": ["日常通勤", "旅行拍照"],
                "priority_concerns": ["续航", "拍照"],
                "deal_breakers": ["机身过重"],
            },
        )

    assert response.status_code == 200
    assert fake_service.updated_preferences == UpdatePreferencesCommand(
        review_window_days=60,
        budget_min=Decimal("3000.00"),
        budget_max=Decimal("4500.00"),
        usage_scenarios=("日常通勤", "旅行拍照"),
        priority_concerns=("续航", "拍照"),
        deal_breakers=("机身过重",),
    )
    assert response.json()["preferences"] == {
        "budget_min": "3000.00",
        "budget_max": "4500.00",
        "usage_scenarios": ["日常通勤", "旅行拍照"],
        "priority_concerns": ["续航", "拍照"],
        "deal_breakers": ["机身过重"],
    }


@pytest.mark.asyncio
async def test_update_preferences_normalizes_before_text_and_count_limits(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """HTTP 层不得在领域规范化前误拒绝可折叠空白和重复文本。by AI.Coding"""
    application, fake_service = comparison_app
    raw_scenario = f"通勤{' ' * 100}拍照"
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.put(
            f"/api/v1/comparisons/{fake_service.comparison_id}/preferences",
            json={
                "review_window_days": 30,
                "budget_min": None,
                "budget_max": "4500.00",
                "usage_scenarios": [raw_scenario] * 6,
                "priority_concerns": ["续航"],
                "deal_breakers": [],
            },
        )

    assert response.status_code == 200
    assert response.json()["preferences"]["usage_scenarios"] == ["通勤 拍照"]


@pytest.mark.asyncio
async def test_dimension_routes_generate_query_and_confirm_ordered_codes(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """三个维度端点映射白名单响应并保持用户确认顺序。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        generated = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions/recommendations"
        )
        queried = await client.get(f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions")
        confirmed = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions/confirm",
            json={"dimension_codes": ["price", "storage"]},
        )

    assert generated.status_code == 200
    assert queried.json()["dimensions"][0]["data_risk"] == "available"
    assert "config" not in queried.text
    assert confirmed.json()["status"] == "queued"
    assert fake_service.confirmed_dimensions == ConfirmDimensionsCommand(("price", "storage"))


@pytest.mark.asyncio
async def test_dimension_confirmation_rejects_empty_and_extra_fields(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """HTTP Schema 在进入应用服务前拒绝空维度和额外字段。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        empty = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions/confirm",
            json={"dimension_codes": []},
        )
        extra = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/dimensions/confirm",
            json={"dimension_codes": ["price"], "unexpected": True},
        )

    assert empty.status_code == 422
    assert extra.status_code == 422


@pytest.mark.asyncio
async def test_analysis_routes_start_retry_and_return_progress_contract(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """分析端点返回持久化状态、计数和轮询完成标志。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        started = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/analysis/start"
        )
        retried = await client.post(
            f"/api/v1/comparisons/{fake_service.comparison_id}/analysis/retry"
        )
        progress = await client.get(
            f"/api/v1/comparisons/{fake_service.comparison_id}/analysis/progress"
        )

    assert started.json()["status"] == "queued"
    assert retried.status_code == 200
    assert progress.json() == {
        "comparison_id": str(fake_service.comparison_id),
        "status": "partially_completed",
        "progress": 100,
        "stage": "partially_completed",
        "message": "降级报告已生成。",
        "fetched_review_count": 3,
        "valid_review_count": 2,
        "annotated_review_count": 1,
        "annotation_count": 1,
        "metric_count": 144,
        "can_retry": False,
        "polling_complete": True,
    }


@pytest.mark.asyncio
async def test_report_route_returns_structured_blocks_and_safe_claim_sources(
    comparison_app: tuple[FastAPI, _FakeComparisonService],
) -> None:
    """报告端点返回四层结构和受控来源，不暴露 Prompt 或 reasoning。by AI.Coding"""
    application, fake_service = comparison_app
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/comparisons/{fake_service.comparison_id}/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["version"] == 1
    assert payload["summary"]["recommendation_claim_index"] == 0
    assert payload["differences"][0]["dimension_code"] == "price"
    assert payload["claims"][0]["source_refs"][0]["type"] == "product_snapshot"
    assert "prompt" not in response.text.casefold()
    assert "reasoning" not in response.text.casefold()
