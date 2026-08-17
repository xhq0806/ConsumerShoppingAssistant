"""M1-E 分析调度、Fixture 评论采集和进度查询应用用例。by AI.Coding"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

from app.core.errors import (
    DomainConflictError,
    ProviderError,
    ResourceNotFoundError,
)
from app.domain.comparisons import ComparisonStatus, TaskEventType, TaskStage
from app.domain.reviews.cleaning import ReviewCleaningResult, clean_reviews
from app.infrastructure.db.analysis_repository import AnalysisRepository
from app.infrastructure.db.comparison_repository import ComparisonRepository
from app.infrastructure.db.models import ComparisonProduct, ComparisonTask
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.commerce.base import CommerceDataProvider
from app.providers.commerce.dto import (
    NormalizedProductUrl,
    ReviewFetchRequest,
    ReviewProviderResult,
)

_RETRYABLE_ANALYSIS_ERROR_CODES = frozenset({"PROVIDER_UNAVAILABLE", "PROVIDER_RATE_LIMITED"})
_POLLING_COMPLETE_STATUSES = frozenset(
    {
        ComparisonStatus.PROCESSING,
        ComparisonStatus.COMPLETED,
        ComparisonStatus.PARTIALLY_COMPLETED,
        ComparisonStatus.FAILED,
    }
)


class AnalysisTaskDispatcher(Protocol):
    """定义 API 到异步队列的最小投递边界。by AI.Coding"""

    def dispatch(self, comparison_id: UUID) -> None:
        """投递一个 comparison_id，不承担业务状态持久化。by AI.Coding"""
        ...


@dataclass(frozen=True)
class AnalysisProgressView:
    """定义分析进度 API 的受控恢复视图。by AI.Coding"""

    comparison_id: UUID
    status: str
    progress: int
    stage: str
    message: str
    fetched_review_count: int
    valid_review_count: int
    can_retry: bool
    polling_complete: bool


@dataclass(frozen=True)
class AnalysisExecutionResult:
    """表示 Worker 对单次异步消息的处理结果。by AI.Coding"""

    comparison_id: UUID
    outcome: str
    status: str
    fetched_review_count: int
    valid_review_count: int


@dataclass(frozen=True)
class _ReviewFetchTarget:
    """保存事务外评论获取所需的最小商品白名单。by AI.Coding"""

    comparison_product_id: UUID
    product_url: NormalizedProductUrl
    selected_external_sku_id: str | None


@dataclass(frozen=True)
class _ProductReviewBatch:
    """关联商品、Provider 计数和清洗结果。by AI.Coding"""

    comparison_product_id: UUID
    provider_result: ReviewProviderResult
    cleaning_result: ReviewCleaningResult


class AnalysisApplicationService:
    """编排分析投递、评论采集和进度恢复。by AI.Coding"""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        commerce_provider: CommerceDataProvider,
        *,
        dispatcher: AnalysisTaskDispatcher | None,
        max_reviews_per_product: int = 500,
    ) -> None:
        """注入短事务、受限 Provider 和可选队列调度器。by AI.Coding"""
        self._uow_factory = uow_factory
        self._commerce_provider = commerce_provider
        self._dispatcher = dispatcher
        self._max_reviews_per_product = max_reviews_per_product

    async def request_analysis(self, comparison_id: UUID) -> AnalysisProgressView:
        """对 queued 任务执行可重放投递，运行中或已完成阶段幂等返回。by AI.Coding"""
        async with self._uow_factory() as uow:
            task = await self._required_task(self._comparison_repository(uow), comparison_id)
            if task.status is ComparisonStatus.QUEUED:
                should_dispatch = True
            elif task.status in {
                ComparisonStatus.FETCHING,
                ComparisonStatus.PROCESSING,
                ComparisonStatus.COMPLETED,
                ComparisonStatus.PARTIALLY_COMPLETED,
            }:
                should_dispatch = False
            else:
                raise DomainConflictError("当前任务状态不允许启动分析")
        if should_dispatch:
            self._required_dispatcher().dispatch(comparison_id)
        return await self.get_analysis_progress(comparison_id)

    async def retry_analysis(self, comparison_id: UUID) -> AnalysisProgressView:
        """把可重试的分析失败重新排队，并在提交后再次投递。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._comparison_repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.FAILED:
                raise DomainConflictError("当前任务状态不允许重试分析")
            if not self._can_retry(task):
                raise DomainConflictError("当前分析失败不可重试")
            repository.transition(task, ComparisonStatus.QUEUED)
            task.progress = 0
            task.error_code = None
            task.error_message = None
            repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.QUEUED,
                event_type=TaskEventType.STATUS_CHANGED,
                progress=0,
                message="分析任务已重新排队。",
                details={"status": ComparisonStatus.QUEUED.value},
            )
        # UoW 已提交 queued 后再执行外部投递；投递失败时数据库仍可恢复。
        self._required_dispatcher().dispatch(comparison_id)
        return await self.get_analysis_progress(comparison_id)

    async def get_analysis_progress(self, comparison_id: UUID) -> AnalysisProgressView:
        """返回任务状态、阶段和不包含评论正文的进度计数。by AI.Coding"""
        async with self._uow_factory() as uow:
            task = await self._required_task(self._comparison_repository(uow), comparison_id)
            valid_count = await self._analysis_repository(uow).count_reviews_for_comparison(
                comparison_id
            )
            fetched_count = self._latest_fetched_count(task)
            stage, message = self._progress_copy(task.status)
            return AnalysisProgressView(
                comparison_id=task.id,
                status=task.status.value,
                progress=task.progress,
                stage=stage,
                message=message,
                fetched_review_count=fetched_count,
                valid_review_count=valid_count,
                can_retry=self._can_retry(task),
                polling_complete=task.status in _POLLING_COMPLETE_STATUSES,
            )

    async def process_comparison(self, comparison_id: UUID) -> AnalysisExecutionResult:
        """Worker 抢占 queued 任务，在事务外获取评论并原子保存清洗结果。by AI.Coding"""
        targets, review_window_days = await self._claim_for_fetching(comparison_id)
        if targets is None:
            progress = await self.get_analysis_progress(comparison_id)
            return AnalysisExecutionResult(
                comparison_id=comparison_id,
                outcome="ignored",
                status=progress.status,
                fetched_review_count=progress.fetched_review_count,
                valid_review_count=progress.valid_review_count,
            )
        batches: list[_ProductReviewBatch] = []
        try:
            for target in targets:
                provider_result = await self._commerce_provider.fetch_reviews(
                    ReviewFetchRequest(
                        product_url=target.product_url,
                        sku_id=target.selected_external_sku_id,
                        window_days=review_window_days,
                        max_reviews=self._max_reviews_per_product,
                    )
                )
                batches.append(
                    _ProductReviewBatch(
                        comparison_product_id=target.comparison_product_id,
                        provider_result=provider_result,
                        cleaning_result=clean_reviews(
                            provider_result.reviews,
                            window_days=review_window_days,
                            actual_end_at=provider_result.actual_end_at,
                        ),
                    )
                )
        except ProviderError as error:
            await self._mark_failed(comparison_id, error)
            return AnalysisExecutionResult(
                comparison_id=comparison_id,
                outcome="failed",
                status=ComparisonStatus.FAILED.value,
                fetched_review_count=0,
                valid_review_count=0,
            )
        return await self._persist_batches(comparison_id, batches)

    async def _claim_for_fetching(
        self, comparison_id: UUID
    ) -> tuple[tuple[_ReviewFetchTarget, ...] | None, int]:
        """通过任务根行锁让重复 Celery 消息只有一个进入 fetching。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._comparison_repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.QUEUED:
                return None, task.review_window_days
            repository.transition(task, ComparisonStatus.FETCHING)
            task.progress = 10
            task.error_code = None
            task.error_message = None
            repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.DATA_FETCHING,
                event_type=TaskEventType.STATUS_CHANGED,
                progress=10,
                message="开始获取近期评论。",
                details={"status": ComparisonStatus.FETCHING.value},
            )
            return self._fetch_targets(task.products), task.review_window_days

    async def _persist_batches(
        self, comparison_id: UUID, batches: Sequence[_ProductReviewBatch]
    ) -> AnalysisExecutionResult:
        """在全部 Provider 调用成功后原子写入有效评论并进入 processing。by AI.Coding"""
        fetched_count = sum(batch.cleaning_result.fetched_count for batch in batches)
        valid_count = sum(len(batch.cleaning_result.valid_reviews) for batch in batches)
        filtered_count = sum(batch.cleaning_result.filtered_out_count for batch in batches)
        duplicate_count = sum(batch.cleaning_result.duplicate_count for batch in batches)
        async with self._uow_factory() as uow:
            comparison_repository = self._comparison_repository(uow)
            analysis_repository = self._analysis_repository(uow)
            task = await self._required_task(comparison_repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.FETCHING:
                progress = await analysis_repository.count_reviews_for_comparison(comparison_id)
                return AnalysisExecutionResult(
                    comparison_id=comparison_id,
                    outcome="ignored",
                    status=task.status.value,
                    fetched_review_count=self._latest_fetched_count(task),
                    valid_review_count=progress,
                )
            for batch in batches:
                for review in batch.cleaning_result.valid_reviews:
                    analysis_repository.add_review_from_dto(
                        comparison_product_id=batch.comparison_product_id,
                        review=review,
                    )
            comparison_repository.transition(task, ComparisonStatus.PROCESSING)
            task.progress = 45
            comparison_repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.ANALYSIS,
                event_type=TaskEventType.STATUS_CHANGED,
                progress=45,
                message="近期评论已获取并清洗，等待后续分析。",
                details={
                    "code": "REVIEW_FETCH_COMPLETED",
                    "status": ComparisonStatus.PROCESSING.value,
                    "product_count": len(batches),
                    "fetched_review_count": fetched_count,
                    "valid_review_count": valid_count,
                    "filtered_review_count": filtered_count,
                    "duplicate_review_count": duplicate_count,
                },
            )
        return AnalysisExecutionResult(
            comparison_id=comparison_id,
            outcome="processed",
            status=ComparisonStatus.PROCESSING.value,
            fetched_review_count=fetched_count,
            valid_review_count=valid_count,
        )

    async def _mark_failed(self, comparison_id: UUID, error: ProviderError) -> None:
        """在独立事务把 fetching 任务标记为受控失败且不保存评论正文。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._comparison_repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.FETCHING:
                return
            repository.transition(task, ComparisonStatus.FAILED)
            task.error_code = error.code
            task.error_message = "近期评论获取失败。"
            repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.DATA_FETCHING,
                event_type=TaskEventType.ERROR,
                progress=task.progress,
                message="近期评论获取失败。",
                details={
                    "code": error.code,
                    "retryable": error.code in _RETRYABLE_ANALYSIS_ERROR_CODES,
                },
            )

    @staticmethod
    def _fetch_targets(
        products: Sequence[ComparisonProduct],
    ) -> tuple[_ReviewFetchTarget, ...]:
        """从已确认商品聚合构造 Provider 评论请求白名单。by AI.Coding"""
        targets: list[_ReviewFetchTarget] = []
        for product in sorted(products, key=lambda item: item.position):
            parsed = urlsplit(product.canonical_url)
            host = parsed.hostname
            assert host is not None
            selected_sku = next(
                (sku for sku in product.skus if sku.id == product.selected_sku_id),
                None,
            )
            targets.append(
                _ReviewFetchTarget(
                    comparison_product_id=product.id,
                    product_url=NormalizedProductUrl(
                        canonical_url=product.canonical_url,
                        platform=product.platform.value,
                        host=host,
                        external_product_id=product.external_product_id,
                        safe_url_fingerprint=product.safe_url_fingerprint,
                    ),
                    selected_external_sku_id=(
                        None if selected_sku is None else selected_sku.external_sku_id
                    ),
                )
            )
        return tuple(targets)

    @staticmethod
    def _latest_fetched_count(task: ComparisonTask) -> int:
        """从最新受控完成事件恢复 Provider 获取总数。by AI.Coding"""
        for event in sorted(task.events, key=lambda item: item.created_at, reverse=True):
            if event.details.get("code") == "REVIEW_FETCH_COMPLETED":
                value = event.details.get("fetched_review_count")
                return value if isinstance(value, int) else 0
        return 0

    @staticmethod
    def _progress_copy(status: ComparisonStatus) -> tuple[str, str]:
        """把持久化状态映射为稳定阶段和用户可见文案。by AI.Coding"""
        return {
            ComparisonStatus.QUEUED: ("queued", "任务已排队，等待评论采集。"),
            ComparisonStatus.FETCHING: ("fetching_reviews", "正在获取并清洗近期评论。"),
            ComparisonStatus.PROCESSING: (
                "review_data_ready",
                "近期评论已获取并清洗，等待后续分析。",
            ),
            ComparisonStatus.FAILED: ("failed", "评论采集失败。"),
            ComparisonStatus.COMPLETED: ("completed", "任务已完成。"),
            ComparisonStatus.PARTIALLY_COMPLETED: (
                "partially_completed",
                "任务已生成部分结果。",
            ),
        }.get(status, ("not_ready", "任务尚未进入分析阶段。"))

    @staticmethod
    def _can_retry(task: ComparisonTask) -> bool:
        """仅允许已确认维度且错误码可重试的分析失败重新排队。by AI.Coding"""
        return (
            task.status is ComparisonStatus.FAILED
            and task.error_code in _RETRYABLE_ANALYSIS_ERROR_CODES
            and any(item.selected for item in task.dimensions)
        )

    def _required_dispatcher(self) -> AnalysisTaskDispatcher:
        """取得 API 运行时调度器，Worker 侧调用投递方法时显式失败。by AI.Coding"""
        if self._dispatcher is None:
            raise RuntimeError("当前分析服务未配置任务调度器")
        return self._dispatcher

    @staticmethod
    def _comparison_repository(uow: UnitOfWork) -> ComparisonRepository:
        """从工作单元创建 ComparisonRepository。by AI.Coding"""
        assert uow.session is not None
        return ComparisonRepository(uow.session)

    @staticmethod
    def _analysis_repository(uow: UnitOfWork) -> AnalysisRepository:
        """从工作单元创建 AnalysisRepository。by AI.Coding"""
        assert uow.session is not None
        return AnalysisRepository(uow.session)

    @staticmethod
    async def _required_task(
        repository: ComparisonRepository,
        comparison_id: UUID,
        *,
        for_update: bool = False,
    ) -> ComparisonTask:
        """读取非删除任务，否则返回统一资源不存在错误。by AI.Coding"""
        task = await repository.get_detail(comparison_id, for_update=for_update)
        if task is None or task.status is ComparisonStatus.DELETED:
            raise ResourceNotFoundError("未找到对应的对比任务。")
        return task
