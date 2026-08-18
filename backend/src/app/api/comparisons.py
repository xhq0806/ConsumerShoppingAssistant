"""M1-B 对比草稿与商品确认 FastAPI 路由。by AI.Coding"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import get_analysis_service, get_comparison_service
from app.api.schemas.comparisons import (
    AnalysisProgressResponse,
    ComparabilityWarningResponse,
    ComparisonCreateRequest,
    ComparisonDetailResponse,
    ComparisonProductResponse,
    ComparisonSummaryResponse,
    ConfirmDimensionsRequest,
    ConfirmProductsRequest,
    DimensionRecommendationResponse,
    DimensionSetResponse,
    ProductSkuResponse,
    ProductSnapshotResponse,
    TaskEventResponse,
    UpdatePreferencesRequest,
    UserPreferencesResponse,
)
from app.application.analysis_tasks import AnalysisApplicationService, AnalysisProgressView
from app.application.comparisons import (
    ComparisonApplicationService,
    ComparisonView,
    ConfirmDimensionsCommand,
    ConfirmProductsCommand,
    CreateComparisonCommand,
    DimensionSetView,
    ProductConfirmation,
    ProductView,
    UpdatePreferencesCommand,
)

router = APIRouter(prefix="/api/v1/comparisons", tags=["comparisons"])


@router.post(
    "",
    response_model=ComparisonSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_comparison",
)
async def create_comparison(
    request: ComparisonCreateRequest,
    service: Annotated[ComparisonApplicationService, Depends(get_comparison_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ComparisonSummaryResponse:
    """创建安全规范化后的对比草稿或返回幂等重放摘要。by AI.Coding"""
    # 路由仅转换 HTTP 契约，不直接访问 session、提交事务或调用 Provider。
    view = await service.create_comparison(
        CreateComparisonCommand(tuple(request.product_urls), request.review_window_days),
        idempotency_key=idempotency_key,
    )
    return _summary_response(view)


@router.post(
    "/{comparison_id}/parse",
    response_model=ComparisonDetailResponse,
    operation_id="parse_comparison_products",
)
async def parse_comparison_products(
    comparison_id: UUID,
    service: Annotated[ComparisonApplicationService, Depends(get_comparison_service)],
) -> ComparisonDetailResponse:
    """同步启动 Fixture 商品解析并返回当前聚合详情。by AI.Coding"""
    # 解析的事务分段、Provider 调用和失败留痕全部由 application service 管理。
    return _detail_response(await service.parse_products(comparison_id))


@router.get(
    "/{comparison_id}",
    response_model=ComparisonDetailResponse,
    operation_id="get_comparison",
)
async def get_comparison(
    comparison_id: UUID,
    service: Annotated[ComparisonApplicationService, Depends(get_comparison_service)],
) -> ComparisonDetailResponse:
    """查询单个未删除对比任务的白名单聚合详情。by AI.Coding"""
    # 响应 mapper 排除原始 URL、Provider payload 与内部错误内容。
    return _detail_response(await service.get_comparison(comparison_id))


@router.post(
    "/{comparison_id}/confirm-products",
    response_model=ComparisonDetailResponse,
    operation_id="confirm_comparison_products",
)
async def confirm_comparison_products(
    comparison_id: UUID,
    request: ConfirmProductsRequest,
    service: Annotated[ComparisonApplicationService, Depends(get_comparison_service)],
) -> ComparisonDetailResponse:
    """原子确认全部候选商品的 SKU 并进行基础可比性检查。by AI.Coding"""
    # 将 API schema 映射为框架无关 command，领域失败统一交给 ProblemDetails handler。
    command = ConfirmProductsCommand(
        tuple(
            ProductConfirmation(item.comparison_product_id, item.selected_sku_id)
            for item in request.products
        )
    )
    return _detail_response(await service.confirm_products(comparison_id, command))


@router.put(
    "/{comparison_id}/preferences",
    response_model=ComparisonDetailResponse,
    operation_id="update_comparison_preferences",
)
async def update_comparison_preferences(
    comparison_id: UUID,
    request: UpdatePreferencesRequest,
    service: Annotated[ComparisonApplicationService, Depends(get_comparison_service)],
) -> ComparisonDetailResponse:
    """整体替换已确认任务的评论窗口和购买偏好。by AI.Coding"""
    # API 只负责类型映射，文本规范化、状态门禁和事务均由应用服务处理。
    command = UpdatePreferencesCommand(
        review_window_days=request.review_window_days,
        budget_min=request.budget_min,
        budget_max=request.budget_max,
        usage_scenarios=tuple(request.usage_scenarios),
        priority_concerns=tuple(request.priority_concerns),
        deal_breakers=tuple(request.deal_breakers),
    )
    return _detail_response(await service.update_preferences(comparison_id, command))


@router.post(
    "/{comparison_id}/dimensions/recommendations",
    response_model=DimensionSetResponse,
    operation_id="generate_comparison_dimension_recommendations",
)
async def generate_comparison_dimension_recommendations(
    comparison_id: UUID,
    service: Annotated[ComparisonApplicationService, Depends(get_comparison_service)],
) -> DimensionSetResponse:
    """首次生成并持久化当前任务的动态维度候选。by AI.Coding"""
    return _dimension_set_response(await service.generate_dimension_recommendations(comparison_id))


@router.get(
    "/{comparison_id}/dimensions",
    response_model=DimensionSetResponse,
    operation_id="get_comparison_dimensions",
)
async def get_comparison_dimensions(
    comparison_id: UUID,
    service: Annotated[ComparisonApplicationService, Depends(get_comparison_service)],
) -> DimensionSetResponse:
    """查询任务已生成的重点与其他可选维度。by AI.Coding"""
    return _dimension_set_response(await service.get_dimensions(comparison_id))


@router.post(
    "/{comparison_id}/dimensions/confirm",
    response_model=DimensionSetResponse,
    operation_id="confirm_comparison_dimensions",
)
async def confirm_comparison_dimensions(
    comparison_id: UUID,
    request: ConfirmDimensionsRequest,
    service: Annotated[ComparisonApplicationService, Depends(get_comparison_service)],
) -> DimensionSetResponse:
    """按用户当前顺序确认维度并推进到 queued 边界。by AI.Coding"""
    return _dimension_set_response(
        await service.confirm_dimensions(
            comparison_id,
            ConfirmDimensionsCommand(tuple(request.dimension_codes)),
        )
    )


@router.post(
    "/{comparison_id}/analysis/start",
    response_model=AnalysisProgressResponse,
    operation_id="start_comparison_analysis",
)
async def start_comparison_analysis(
    comparison_id: UUID,
    service: Annotated[AnalysisApplicationService, Depends(get_analysis_service)],
) -> AnalysisProgressResponse:
    """投递 queued 分析任务或幂等返回当前进度。by AI.Coding"""
    return _analysis_progress_response(await service.request_analysis(comparison_id))


@router.post(
    "/{comparison_id}/analysis/retry",
    response_model=AnalysisProgressResponse,
    operation_id="retry_comparison_analysis",
)
async def retry_comparison_analysis(
    comparison_id: UUID,
    service: Annotated[AnalysisApplicationService, Depends(get_analysis_service)],
) -> AnalysisProgressResponse:
    """把可重试的评论采集失败重新排队。by AI.Coding"""
    return _analysis_progress_response(await service.retry_analysis(comparison_id))


@router.get(
    "/{comparison_id}/analysis/progress",
    response_model=AnalysisProgressResponse,
    operation_id="get_comparison_analysis_progress",
)
async def get_comparison_analysis_progress(
    comparison_id: UUID,
    service: Annotated[AnalysisApplicationService, Depends(get_analysis_service)],
) -> AnalysisProgressResponse:
    """查询任务异步评论采集的持久化进度。by AI.Coding"""
    return _analysis_progress_response(await service.get_analysis_progress(comparison_id))


def _summary_response(view: ComparisonView) -> ComparisonSummaryResponse:
    """将应用摘要视图显式映射为创建端点响应。by AI.Coding"""
    # 共享候选 mapper 保证创建和详情端点不会意外暴露不同字段。
    return ComparisonSummaryResponse(
        id=view.id,
        status=view.status,
        review_window_days=view.review_window_days,
        progress=view.progress,
        products=[_product_response(product) for product in view.products],
        preferences=_preferences_response(view),
    )


def _detail_response(view: ComparisonView) -> ComparisonDetailResponse:
    """将应用详情视图显式映射为详情端点响应。by AI.Coding"""
    summary = _summary_response(view)
    return ComparisonDetailResponse(
        **summary.model_dump(),
        events=[
            TaskEventResponse(
                id=event.id,
                stage=event.stage,
                event_type=event.event_type,
                progress=event.progress,
                message=event.message,
                details=event.details,
                created_at=event.created_at,
            )
            for event in view.events
        ],
        warnings=[
            ComparabilityWarningResponse(code=warning.code, message=warning.message)
            for warning in view.warnings
        ],
    )


def _product_response(product: ProductView) -> ComparisonProductResponse:
    """将候选商品应用视图转换为 API schema。by AI.Coding"""
    # 显式逐层列举字段，避免 ORM 或 dataclass 自动序列化泄露未来新增字段。
    snapshot = product.latest_snapshot
    snapshot_response = None
    if snapshot is not None:
        snapshot_response = ProductSnapshotResponse(
            id=snapshot.id,
            title=snapshot.title,
            image_url=snapshot.image_url,
            brand=snapshot.brand,
            category=snapshot.category,
            shop_name=snapshot.shop_name,
            price=snapshot.price,
            currency=snapshot.currency,
            specifications=snapshot.specifications,
            after_sales=snapshot.after_sales,
            source_provider=snapshot.source_provider,
            source_id=snapshot.source_id,
            captured_at=snapshot.captured_at,
        )
    return ComparisonProductResponse(
        id=product.id,
        position=product.position,
        platform=product.platform,
        external_product_id=product.external_product_id,
        parse_status=product.parse_status,
        selected_sku_id=product.selected_sku_id,
        latest_snapshot=snapshot_response,
        skus=[
            ProductSkuResponse(
                id=sku.id,
                external_sku_id=sku.external_sku_id,
                name=sku.name,
                attributes=sku.attributes,
                price=sku.price,
                selectable=sku.selectable,
            )
            for sku in product.skus
        ],
    )


def _preferences_response(view: ComparisonView) -> UserPreferencesResponse | None:
    """将可空领域偏好转换为 API 恢复结构。by AI.Coding"""
    if view.preferences is None:
        return None
    return UserPreferencesResponse(
        budget_min=view.preferences.budget_min,
        budget_max=view.preferences.budget_max,
        usage_scenarios=list(view.preferences.usage_scenarios),
        priority_concerns=list(view.preferences.priority_concerns),
        deal_breakers=list(view.preferences.deal_breakers),
    )


def _dimension_set_response(view: DimensionSetView) -> DimensionSetResponse:
    """显式映射动态维度集合并排除目录原始 config。by AI.Coding"""
    return DimensionSetResponse(
        comparison_id=view.comparison_id,
        status=view.status,
        category=view.category,
        generated=view.generated,
        dimensions=[
            DimensionRecommendationResponse(
                code=item.code,
                name=item.name,
                source_type=item.source_type,
                selected=item.selected,
                position=item.position,
                user_selected=item.user_selected,
                reason=item.reason,
                data_risk=item.data_risk,
                has_difference=item.has_difference,
                affects_recommendation=item.affects_recommendation,
                user_removable=item.user_removable,
                description=item.description,
            )
            for item in view.dimensions
        ],
    )


def _analysis_progress_response(view: AnalysisProgressView) -> AnalysisProgressResponse:
    """显式映射异步分析进度和 M1-F 安全计数白名单。by AI.Coding"""
    return AnalysisProgressResponse(
        comparison_id=view.comparison_id,
        status=view.status,
        progress=view.progress,
        stage=view.stage,
        message=view.message,
        fetched_review_count=view.fetched_review_count,
        valid_review_count=view.valid_review_count,
        annotated_review_count=view.annotated_review_count,
        annotation_count=view.annotation_count,
        metric_count=view.metric_count,
        can_retry=view.can_retry,
        polling_complete=view.polling_complete,
    )
