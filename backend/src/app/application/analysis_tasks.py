"""M1-E 分析调度、Fixture 评论采集和进度查询应用用例。by AI.Coding"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from app.application.report_generation import ReportApplicationService
from app.application.review_analysis import (
    ReviewAnnotationAnalyzer,
    ReviewAnnotationInvocation,
    ReviewAnnotationInvocationFailure,
)
from app.core.errors import (
    DomainConflictError,
    LLMError,
    ProviderError,
    ResourceNotFoundError,
)
from app.domain.comparisons import ComparisonStatus, TaskEventType, TaskStage
from app.domain.metrics.calculation import (
    MetricAnnotation,
    MetricDimension,
    MetricReview,
    calculate_review_metrics,
)
from app.domain.reviews.annotation import (
    AnnotationDimension,
    ReviewForAnnotation,
)
from app.domain.reviews.cleaning import ReviewCleaningResult, clean_reviews
from app.infrastructure.db.analysis_repository import AnalysisRepository
from app.infrastructure.db.comparison_repository import ComparisonRepository
from app.infrastructure.db.model_run_repository import ModelRunRepository
from app.infrastructure.db.models import (
    ComparisonProduct,
    ComparisonTask,
    DimensionDefinition,
    RawReview,
    ReviewAnnotation,
)
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.commerce.base import CommerceDataProvider
from app.providers.commerce.dto import (
    NormalizedProductUrl,
    ReviewFetchRequest,
    ReviewProviderResult,
)
from app.providers.llm.base import LLMAuditEvent

_RETRYABLE_ANALYSIS_ERROR_CODES = frozenset(
    {
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_RATE_LIMITED",
        "LLM_TIMEOUT",
        "LLM_RATE_LIMITED",
        "LLM_PROVIDER_UNAVAILABLE",
        "LLM_STRUCTURED_OUTPUT_INVALID",
    }
)
_POLLING_COMPLETE_STATUSES = frozenset(
    {
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
    annotated_review_count: int
    annotation_count: int
    metric_count: int
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
    annotated_review_count: int
    annotation_count: int
    metric_count: int


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


@dataclass(frozen=True)
class _AnalysisWorkClaim:
    """表示 Worker 当前应获取评论、恢复注解或忽略消息。by AI.Coding"""

    mode: Literal["fetch", "resume", "ignored"]
    targets: tuple[_ReviewFetchTarget, ...]
    review_window_days: int


@dataclass(frozen=True)
class _AnnotationContext:
    """保存一次注解循环读取到的稳定任务输入和断点。by AI.Coding"""

    reviews: tuple[ReviewForAnnotation, ...]
    dimensions: tuple[AnnotationDimension, ...]
    processed_review_ids: frozenset[UUID]


class AnalysisApplicationService:
    """编排分析投递、评论采集和进度恢复。by AI.Coding"""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        commerce_provider: CommerceDataProvider,
        *,
        dispatcher: AnalysisTaskDispatcher | None,
        annotation_analyzer: ReviewAnnotationAnalyzer | None = None,
        report_service: ReportApplicationService | None = None,
        max_reviews_per_product: int = 500,
        annotation_batch_size: int = 20,
    ) -> None:
        """注入短事务、Provider、模型注解器和可选队列调度器。by AI.Coding"""
        if not 1 <= annotation_batch_size <= 20:
            raise ValueError("评论注解批次必须在 1 到 20 之间")
        self._uow_factory = uow_factory
        self._commerce_provider = commerce_provider
        self._dispatcher = dispatcher
        self._annotation_analyzer = annotation_analyzer
        self._report_service = report_service
        self._max_reviews_per_product = max_reviews_per_product
        self._annotation_batch_size = annotation_batch_size

    async def request_analysis(self, comparison_id: UUID) -> AnalysisProgressView:
        """投递 queued 或未到 75 的 processing 任务，支持容器重启后恢复。by AI.Coding"""
        async with self._uow_factory() as uow:
            task = await self._required_task(self._comparison_repository(uow), comparison_id)
            if task.status is ComparisonStatus.QUEUED or (
                task.status is ComparisonStatus.PROCESSING and task.progress < 100
            ):
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
        """把可重试的采集或模型失败重新排队，并保留已提交注解断点。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._comparison_repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.FAILED:
                raise DomainConflictError("当前任务状态不允许重试分析")
            if not self._can_retry(task):
                raise DomainConflictError("当前分析失败不可重试")
            repository.transition(task, ComparisonStatus.QUEUED)
            task.progress = self._retry_progress(task)
            task.error_code = None
            task.error_message = None
            repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.QUEUED,
                event_type=TaskEventType.STATUS_CHANGED,
                progress=task.progress,
                message="分析任务已重新排队。",
                details={
                    "status": ComparisonStatus.QUEUED.value,
                    "resuming_annotation": self._has_annotation_checkpoint(task),
                },
            )
        # UoW 已提交 queued 后再执行外部投递；投递失败时数据库仍可恢复。
        self._required_dispatcher().dispatch(comparison_id)
        return await self.get_analysis_progress(comparison_id)

    async def get_analysis_progress(self, comparison_id: UUID) -> AnalysisProgressView:
        """返回任务状态、阶段和不包含评论正文或模型内容的进度计数。by AI.Coding"""
        async with self._uow_factory() as uow:
            task = await self._required_task(self._comparison_repository(uow), comparison_id)
            analysis_repository = self._analysis_repository(uow)
            valid_count = await analysis_repository.count_reviews_for_comparison(comparison_id)
            annotated_review_count = (
                await analysis_repository.count_annotated_reviews_for_comparison(comparison_id)
            )
            annotation_count = await analysis_repository.count_annotations_for_comparison(
                comparison_id
            )
            metric_count = await analysis_repository.count_metrics_for_comparison(comparison_id)
            fetched_count = self._latest_fetched_count(task)
            stage, message = self._progress_copy(task)
            return AnalysisProgressView(
                comparison_id=task.id,
                status=task.status.value,
                progress=task.progress,
                stage=stage,
                message=message,
                fetched_review_count=fetched_count,
                valid_review_count=valid_count,
                annotated_review_count=annotated_review_count,
                annotation_count=annotation_count,
                metric_count=metric_count,
                can_retry=self._can_retry(task),
                polling_complete=task.status in _POLLING_COMPLETE_STATUSES,
            )

    async def process_comparison(self, comparison_id: UUID) -> AnalysisExecutionResult:
        """Worker 获取评论后继续执行可恢复的智能注解与确定性指标。by AI.Coding"""
        claim = await self._claim_work(comparison_id)
        if claim.mode == "ignored":
            return await self._execution_from_progress(comparison_id, outcome="ignored")
        batches: list[_ProductReviewBatch] = []
        if claim.mode == "fetch":
            try:
                for target in claim.targets:
                    provider_result = await self._commerce_provider.fetch_reviews(
                        ReviewFetchRequest(
                            product_url=target.product_url,
                            sku_id=target.selected_external_sku_id,
                            window_days=claim.review_window_days,
                            max_reviews=self._max_reviews_per_product,
                        )
                    )
                    batches.append(
                        _ProductReviewBatch(
                            comparison_product_id=target.comparison_product_id,
                            provider_result=provider_result,
                            cleaning_result=clean_reviews(
                                provider_result.reviews,
                                window_days=claim.review_window_days,
                                actual_end_at=provider_result.actual_end_at,
                            ),
                        )
                    )
            except ProviderError as error:
                await self._mark_provider_failed(comparison_id, error)
                return await self._execution_from_progress(comparison_id, outcome="failed")
            persisted = await self._persist_batches(comparison_id, batches)
            if not persisted:
                return await self._execution_from_progress(comparison_id, outcome="ignored")
        progress = await self.get_analysis_progress(comparison_id)
        if progress.status == ComparisonStatus.PROCESSING.value and progress.progress < 75:
            result = await self._process_annotations_and_metrics(comparison_id)
            if result.status != ComparisonStatus.PROCESSING.value:
                return result
        if self._report_service is None:
            return await self._execution_from_progress(comparison_id, outcome="processed")
        report_result = await self._report_service.generate_report(comparison_id)
        return await self._execution_from_progress(
            comparison_id,
            outcome=report_result.outcome,
        )

    async def _claim_work(self, comparison_id: UUID) -> _AnalysisWorkClaim:
        """通过任务根行锁决定获取评论、恢复注解或忽略重复消息。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._comparison_repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is ComparisonStatus.PROCESSING:
                if task.progress < 75 or (self._report_service is not None and task.progress < 100):
                    return _AnalysisWorkClaim("resume", (), task.review_window_days)
                return _AnalysisWorkClaim("ignored", (), task.review_window_days)
            if task.status is not ComparisonStatus.QUEUED:
                return _AnalysisWorkClaim("ignored", (), task.review_window_days)
            review_count = await self._analysis_repository(uow).count_reviews_for_comparison(
                comparison_id
            )
            repository.transition(task, ComparisonStatus.FETCHING)
            if review_count > 0:
                # retry 先经过 queued/fetching 合法状态，再立即恢复到已有评论的 processing。
                repository.transition(task, ComparisonStatus.PROCESSING)
                task.progress = self._resume_progress(task)
                repository.add_event(
                    comparison_id=task.id,
                    stage=TaskStage.ANALYSIS,
                    event_type=TaskEventType.STATUS_CHANGED,
                    progress=task.progress,
                    message="正在从已保存的评论注解断点继续分析。",
                    details={
                        "code": "REVIEW_ANNOTATION_RESUMED",
                        "status": ComparisonStatus.PROCESSING.value,
                        "processed_review_count": len(self._processed_review_ids(task)),
                    },
                )
                return _AnalysisWorkClaim("resume", (), task.review_window_days)
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
            return _AnalysisWorkClaim(
                "fetch",
                self._fetch_targets(task.products),
                task.review_window_days,
            )

    async def _persist_batches(
        self, comparison_id: UUID, batches: Sequence[_ProductReviewBatch]
    ) -> bool:
        """在全部 Provider 调用成功后原子写入评论并建立 M1-F 初始断点。by AI.Coding"""
        fetched_count = sum(batch.cleaning_result.fetched_count for batch in batches)
        valid_count = sum(len(batch.cleaning_result.valid_reviews) for batch in batches)
        filtered_count = sum(batch.cleaning_result.filtered_out_count for batch in batches)
        duplicate_count = sum(batch.cleaning_result.duplicate_count for batch in batches)
        async with self._uow_factory() as uow:
            comparison_repository = self._comparison_repository(uow)
            analysis_repository = self._analysis_repository(uow)
            task = await self._required_task(comparison_repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.FETCHING:
                return False
            for batch in batches:
                for review in batch.cleaning_result.valid_reviews:
                    analysis_repository.add_review_from_dto(
                        comparison_product_id=batch.comparison_product_id,
                        review=review,
                    )
            comparison_repository.transition(task, ComparisonStatus.PROCESSING)
            task.progress = 45
            task.partial_result = {
                "schema_version": 1,
                "phase": "annotation",
                "processed_review_ids": [],
                "annotated_review_count": 0,
                "annotation_count": 0,
            }
            comparison_repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.ANALYSIS,
                event_type=TaskEventType.STATUS_CHANGED,
                progress=45,
                message="近期评论已获取并清洗，开始智能注解。",
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
        return True

    async def _mark_provider_failed(self, comparison_id: UUID, error: ProviderError) -> None:
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

    async def _process_annotations_and_metrics(
        self,
        comparison_id: UUID,
    ) -> AnalysisExecutionResult:
        """逐批调用模型、提交断点，并在全部评论完成后计算指标。by AI.Coding"""
        analyzer = self._required_annotation_analyzer()
        while True:
            context = await self._load_annotation_context(comparison_id)
            remaining = tuple(
                review
                for review in context.reviews
                if review.id not in context.processed_review_ids
            )
            if not remaining:
                return await self._finalize_metrics(comparison_id)
            batch = remaining[: self._annotation_batch_size]
            try:
                invocation = await analyzer.annotate(
                    reviews=batch,
                    dimensions=context.dimensions,
                    trace_id=f"worker-{uuid4()}",
                )
            except ReviewAnnotationInvocationFailure as failure:
                await self._mark_llm_failed(
                    comparison_id,
                    failure.error,
                    failure.audit_event,
                )
                return await self._execution_from_progress(comparison_id, outcome="failed")
            await self._persist_annotation_batch(
                comparison_id,
                invocation,
                total_review_count=len(context.reviews),
            )

    async def _load_annotation_context(self, comparison_id: UUID) -> _AnnotationContext:
        """读取稳定评论、选中维度和已处理 ID，不跨 LLM 调用持有事务。by AI.Coding"""
        async with self._uow_factory() as uow:
            task = await self._required_task(self._comparison_repository(uow), comparison_id)
            if task.status is not ComparisonStatus.PROCESSING or task.progress >= 75:
                raise DomainConflictError("当前任务不在可执行评论注解的阶段")
            reviews = await self._analysis_repository(uow).list_reviews_for_comparison(
                comparison_id
            )
            dimensions = self._annotation_dimensions(task)
            if not dimensions:
                raise DomainConflictError("当前任务没有已选中的对比维度")
            return _AnnotationContext(
                reviews=tuple(self._review_for_annotation(review) for review in reviews),
                dimensions=dimensions,
                processed_review_ids=self._processed_review_ids(task),
            )

    async def _persist_annotation_batch(
        self,
        comparison_id: UUID,
        invocation: ReviewAnnotationInvocation,
        *,
        total_review_count: int,
    ) -> None:
        """在行锁下原子保存模型审计、当前批注解和断点进度。by AI.Coding"""
        async with self._uow_factory() as uow:
            comparison_repository = self._comparison_repository(uow)
            analysis_repository = self._analysis_repository(uow)
            task = await self._required_task(
                comparison_repository,
                comparison_id,
                for_update=True,
            )
            if task.status is not ComparisonStatus.PROCESSING or task.progress >= 75:
                return
            current_processed = self._processed_review_ids(task)
            pending_ids = frozenset(invocation.batch.processed_review_ids) - current_processed
            model_run = self._model_run_repository(uow).add_from_audit_event(
                invocation.audit_event,
                comparison_id=comparison_id,
            )
            await self._model_run_repository(uow).flush()
            if pending_ids:
                analysis_repository.add_annotations(
                    tuple(
                        annotation
                        for annotation in invocation.batch.annotations
                        if annotation.review_id in pending_ids
                    ),
                    model_run_id=model_run.id,
                )
                await analysis_repository.flush()
            reviews = await analysis_repository.list_reviews_for_comparison(comparison_id)
            merged = current_processed | pending_ids
            ordered_processed = [str(review.id) for review in reviews if review.id in merged]
            annotated_review_count = (
                await analysis_repository.count_annotated_reviews_for_comparison(comparison_id)
            )
            annotation_count = await analysis_repository.count_annotations_for_comparison(
                comparison_id
            )
            task.progress = self._annotation_progress(
                len(ordered_processed),
                total_review_count,
            )
            task.partial_result = {
                "schema_version": 1,
                "phase": "annotation",
                "processed_review_ids": ordered_processed,
                "annotated_review_count": annotated_review_count,
                "annotation_count": annotation_count,
            }
            comparison_repository.add_event(
                comparison_id=comparison_id,
                stage=TaskStage.ANALYSIS,
                event_type=TaskEventType.PROGRESS_UPDATED,
                progress=task.progress,
                message="评论智能注解批次已保存。",
                details={
                    "code": "REVIEW_ANNOTATION_BATCH_COMPLETED",
                    "processed_review_count": len(ordered_processed),
                    "total_review_count": total_review_count,
                    "annotated_review_count": annotated_review_count,
                    "annotation_count": annotation_count,
                },
            )

    async def _finalize_metrics(self, comparison_id: UUID) -> AnalysisExecutionResult:
        """在事务外计算纯指标，并在短事务中整体替换后推进到 75。by AI.Coding"""
        await self._mark_metrics_calculating(comparison_id)
        async with self._uow_factory() as uow:
            task = await self._required_task(self._comparison_repository(uow), comparison_id)
            analysis_repository = self._analysis_repository(uow)
            reviews = await analysis_repository.list_reviews_for_comparison(comparison_id)
            annotations = await analysis_repository.list_annotations_for_comparison(comparison_id)
            dimensions = self._selected_dimension_definitions(task)
        metrics = calculate_review_metrics(
            comparison_id=comparison_id,
            reviews=tuple(
                MetricReview(
                    id=review.id,
                    comparison_product_id=review.comparison_product_id,
                )
                for review in reviews
            ),
            annotations=tuple(self._metric_annotation(annotation) for annotation in annotations),
            dimensions=tuple(
                MetricDimension(id=dimension.id, code=dimension.code) for dimension in dimensions
            ),
        )
        async with self._uow_factory() as uow:
            comparison_repository = self._comparison_repository(uow)
            analysis_repository = self._analysis_repository(uow)
            task = await self._required_task(
                comparison_repository,
                comparison_id,
                for_update=True,
            )
            if task.status is not ComparisonStatus.PROCESSING or task.progress >= 75:
                ignored = True
            else:
                ignored = False
                current_reviews = await analysis_repository.list_reviews_for_comparison(
                    comparison_id
                )
                processed = self._processed_review_ids(task)
                if {review.id for review in current_reviews} - processed:
                    raise DomainConflictError("仍有评论尚未完成智能注解")
                await analysis_repository.replace_review_metrics(
                    comparison_id=comparison_id,
                    metrics=metrics,
                )
                await analysis_repository.flush()
                annotated_review_count = (
                    await analysis_repository.count_annotated_reviews_for_comparison(comparison_id)
                )
                annotation_count = await analysis_repository.count_annotations_for_comparison(
                    comparison_id
                )
                task.progress = 75
                task.partial_result = {
                    "schema_version": 1,
                    "phase": "metrics_ready",
                    "processed_review_ids": [str(review.id) for review in current_reviews],
                    "annotated_review_count": annotated_review_count,
                    "annotation_count": annotation_count,
                    "metric_count": len(metrics),
                }
                comparison_repository.add_event(
                    comparison_id=comparison_id,
                    stage=TaskStage.ANALYSIS,
                    event_type=TaskEventType.PROGRESS_UPDATED,
                    progress=75,
                    message="评论注解与确定性指标已准备，等待生成报告。",
                    details={
                        "code": "REVIEW_METRICS_COMPLETED",
                        "annotated_review_count": annotated_review_count,
                        "annotation_count": annotation_count,
                        "metric_count": len(metrics),
                    },
                )
        if ignored:
            return await self._execution_from_progress(comparison_id, outcome="ignored")
        return await self._execution_from_progress(comparison_id, outcome="processed")

    async def _mark_metrics_calculating(self, comparison_id: UUID) -> None:
        """提交 progress=70，使轮询端可观察确定性指标阶段。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._comparison_repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.PROCESSING or task.progress >= 70:
                return
            task.progress = 70
            repository.add_event(
                comparison_id=comparison_id,
                stage=TaskStage.ANALYSIS,
                event_type=TaskEventType.PROGRESS_UPDATED,
                progress=70,
                message="正在根据已验证注解计算确定性指标。",
                details={"code": "REVIEW_METRICS_CALCULATING"},
            )

    async def _mark_llm_failed(
        self,
        comparison_id: UUID,
        error: LLMError,
        audit_event: LLMAuditEvent,
    ) -> None:
        """保存安全模型审计，并把 processing 任务标记为受控失败。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._comparison_repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.PROCESSING or task.progress >= 75:
                return
            self._model_run_repository(uow).add_from_audit_event(
                audit_event,
                comparison_id=comparison_id,
            )
            repository.transition(task, ComparisonStatus.FAILED)
            task.error_code = error.code
            task.error_message = "评论智能注解失败。"
            repository.add_event(
                comparison_id=comparison_id,
                stage=TaskStage.ANALYSIS,
                event_type=TaskEventType.ERROR,
                progress=task.progress,
                message="评论智能注解失败。",
                details={
                    "code": error.code,
                    "retryable": error.code in _RETRYABLE_ANALYSIS_ERROR_CODES,
                },
            )

    @staticmethod
    def _annotation_dimensions(task: ComparisonTask) -> tuple[AnnotationDimension, ...]:
        """把任务已选目录维度映射为模型输入白名单。by AI.Coding"""
        return tuple(
            AnnotationDimension(
                id=dimension.id,
                code=dimension.code,
                name=dimension.name,
                description=(
                    str(dimension.config.get("description", ""))
                    if isinstance(dimension.config, dict)
                    else ""
                ),
                aliases=AnalysisApplicationService._dimension_aliases(dimension),
            )
            for dimension in AnalysisApplicationService._selected_dimension_definitions(task)
        )

    @staticmethod
    def _dimension_aliases(dimension: DimensionDefinition) -> tuple[str, ...]:
        """从受控目录 config 提取非空 alias，并补充维度名称。by AI.Coding"""
        raw_aliases = (
            dimension.config.get("aliases", []) if isinstance(dimension.config, dict) else []
        )
        if not isinstance(raw_aliases, list):
            raw_aliases = []
        aliases = [item.strip() for item in raw_aliases if isinstance(item, str) and item.strip()]
        if dimension.name not in aliases:
            aliases.append(dimension.name)
        return tuple(aliases)

    @staticmethod
    def _selected_dimension_definitions(
        task: ComparisonTask,
    ) -> tuple[DimensionDefinition, ...]:
        """按用户确认位置返回任务已选且仍启用的目录维度。by AI.Coding"""
        selected = sorted(
            (
                item
                for item in task.dimensions
                if item.selected and item.position is not None and item.dimension.enabled
            ),
            key=lambda item: item.position if item.position is not None else 0,
        )
        return tuple(item.dimension for item in selected)

    @staticmethod
    def _review_for_annotation(review: RawReview) -> ReviewForAnnotation:
        """把 ORM 评论显式映射为模型最小输入。by AI.Coding"""
        return ReviewForAnnotation(
            id=review.id,
            comparison_product_id=review.comparison_product_id,
            content=review.content,
            rating=review.rating,
        )

    @staticmethod
    def _metric_annotation(annotation: ReviewAnnotation) -> MetricAnnotation:
        """把 ORM 注解映射为纯指标计算输入。by AI.Coding"""
        return MetricAnnotation(
            id=annotation.id,
            review_id=annotation.review_id,
            dimension_id=annotation.dimension_id,
            sentiment=annotation.sentiment,
            confidence=annotation.confidence,
        )

    @staticmethod
    def _processed_review_ids(task: ComparisonTask) -> frozenset[UUID]:
        """从受控 partial_result 解析可恢复的已处理评论 UUID。by AI.Coding"""
        partial = task.partial_result
        if not isinstance(partial, dict) or partial.get("schema_version") != 1:
            return frozenset()
        raw_ids = partial.get("processed_review_ids")
        if not isinstance(raw_ids, list):
            return frozenset()
        parsed: set[UUID] = set()
        for raw_id in raw_ids:
            if not isinstance(raw_id, str):
                continue
            try:
                parsed.add(UUID(raw_id))
            except ValueError:
                continue
        return frozenset(parsed)

    @staticmethod
    def _has_annotation_checkpoint(task: ComparisonTask) -> bool:
        """判断失败任务是否已经进入 M1-F 注解阶段。by AI.Coding"""
        partial = task.partial_result
        return (
            isinstance(partial, dict)
            and partial.get("schema_version") == 1
            and partial.get("phase") in {"annotation", "metrics_ready"}
        )

    @staticmethod
    def _has_report_checkpoint(task: ComparisonTask) -> bool:
        """判断任务是否已经进入 M1-G 报告阶段。by AI.Coding"""
        partial = task.partial_result
        return (
            isinstance(partial, dict)
            and partial.get("schema_version") == 1
            and partial.get("phase") in {"reporting", "report_ready"}
        )

    @classmethod
    def _retry_progress(cls, task: ComparisonTask) -> int:
        """根据持久化断点决定 failed→queued 时保留的阶段进度。by AI.Coding"""
        if cls._has_report_checkpoint(task):
            return max(80, min(task.progress, 99))
        if cls._has_annotation_checkpoint(task):
            if (
                isinstance(task.partial_result, dict)
                and task.partial_result.get("phase") == "metrics_ready"
            ):
                return 75
            return max(45, min(task.progress, 69))
        return 0

    @classmethod
    def _resume_progress(cls, task: ComparisonTask) -> int:
        """把 queued 重试任务恢复到注解、指标或报告断点。by AI.Coding"""
        if cls._has_report_checkpoint(task):
            return max(80, min(task.progress, 99))
        if (
            isinstance(task.partial_result, dict)
            and task.partial_result.get("phase") == "metrics_ready"
        ):
            return 75
        return max(45, min(task.progress, 69))

    @staticmethod
    def _annotation_progress(processed_count: int, total_count: int) -> int:
        """把评论批次完成比例映射到 46..69 的稳定进度区间。by AI.Coding"""
        if total_count <= 0:
            return 69
        if processed_count <= 0:
            return 45
        return min(69, 45 + math.ceil(24 * processed_count / total_count))

    async def _execution_from_progress(
        self,
        comparison_id: UUID,
        *,
        outcome: str,
    ) -> AnalysisExecutionResult:
        """把当前持久化进度映射为 Worker 返回结果。by AI.Coding"""
        progress = await self.get_analysis_progress(comparison_id)
        return AnalysisExecutionResult(
            comparison_id=comparison_id,
            outcome=outcome,
            status=progress.status,
            fetched_review_count=progress.fetched_review_count,
            valid_review_count=progress.valid_review_count,
            annotated_review_count=progress.annotated_review_count,
            annotation_count=progress.annotation_count,
            metric_count=progress.metric_count,
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
    def _progress_copy(task: ComparisonTask) -> tuple[str, str]:
        """把持久化状态和进度映射为稳定阶段与用户可见文案。by AI.Coding"""
        status = task.status
        if status is ComparisonStatus.PROCESSING:
            if task.progress >= 80:
                return ("generating_report", "正在生成可追溯的购买决策报告。")
            if task.progress >= 75:
                return (
                    "metrics_ready",
                    "评论注解与确定性指标已准备，等待生成报告。",
                )
            if task.progress >= 70:
                return ("calculating_metrics", "正在计算确定性评论指标。")
            return ("annotating_reviews", "正在对近期评论执行维度与情感注解。")
        if status is ComparisonStatus.FAILED:
            if AnalysisApplicationService._has_report_checkpoint(task):
                return ("failed", "购买决策报告生成失败。")
            if task.error_code and task.error_code.startswith("LLM_"):
                return ("failed", "评论智能注解失败。")
            return ("failed", "评论采集失败。")
        return {
            ComparisonStatus.QUEUED: ("queued", "任务已排队，等待评论采集。"),
            ComparisonStatus.FETCHING: ("fetching_reviews", "正在获取并清洗近期评论。"),
            ComparisonStatus.COMPLETED: ("completed", "购买决策报告已生成。"),
            ComparisonStatus.PARTIALLY_COMPLETED: (
                "partially_completed",
                "部分数据不足，已生成可追溯的降级报告。",
            ),
        }.get(status, ("not_ready", "任务尚未进入分析阶段。"))

    @staticmethod
    def _can_retry(task: ComparisonTask) -> bool:
        """仅允许已确认维度且错误码属于受控集合的失败重新排队。by AI.Coding"""
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

    def _required_annotation_analyzer(self) -> ReviewAnnotationAnalyzer:
        """取得 Worker 运行所需模型注解器，API 侧误调用时显式失败。by AI.Coding"""
        if self._annotation_analyzer is None:
            raise RuntimeError("当前分析服务未配置评论注解器")
        return self._annotation_analyzer

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
    def _model_run_repository(uow: UnitOfWork) -> ModelRunRepository:
        """从工作单元创建模型运行仓储。by AI.Coding"""
        assert uow.session is not None
        return ModelRunRepository(uow.session)

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
