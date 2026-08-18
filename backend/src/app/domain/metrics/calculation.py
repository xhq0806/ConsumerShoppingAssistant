"""M1-F 基于持久化评论注解的确定性指标计算。by AI.Coding"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.domain.reviews import ReviewSentiment

_SCALE = Decimal("0.00000001")
_METRIC_TYPES = (
    "annotation_count",
    "positive_count",
    "neutral_count",
    "negative_count",
    "positive_ratio",
    "neutral_ratio",
    "negative_ratio",
    "coverage_ratio",
    "average_confidence",
)


@dataclass(frozen=True)
class MetricReview:
    """表示指标计算所需的评论与商品归属。by AI.Coding"""

    id: UUID
    comparison_product_id: UUID


@dataclass(frozen=True)
class MetricAnnotation:
    """表示指标计算所需的已验证注解字段。by AI.Coding"""

    id: UUID
    review_id: UUID
    dimension_id: UUID
    sentiment: ReviewSentiment
    confidence: float


@dataclass(frozen=True)
class MetricDimension:
    """表示需要生成评论指标的任务已选维度。by AI.Coding"""

    id: UUID
    code: str


@dataclass(frozen=True)
class CalculatedReviewMetric:
    """表示尚未绑定 ORM 的可复算评论指标。by AI.Coding"""

    comparison_id: UUID
    comparison_product_id: UUID | None
    dimension_id: UUID
    metric_type: str
    numeric_value: Decimal
    sample_size: int
    confidence: float
    review_ids: tuple[UUID, ...]
    annotation_ids: tuple[UUID, ...]


def calculate_review_metrics(
    *,
    comparison_id: UUID,
    reviews: tuple[MetricReview, ...],
    annotations: tuple[MetricAnnotation, ...],
    dimensions: tuple[MetricDimension, ...],
) -> tuple[CalculatedReviewMetric, ...]:
    """为有评论输入的任务级与商品级作用域计算九类稳定指标。by AI.Coding"""
    if not reviews or not dimensions:
        return ()
    review_by_id = {review.id: review for review in reviews}
    valid_dimension_ids = {dimension.id for dimension in dimensions}
    valid_annotations = tuple(
        annotation
        for annotation in annotations
        if annotation.review_id in review_by_id and annotation.dimension_id in valid_dimension_ids
    )
    product_ids = sorted(
        {review.comparison_product_id for review in reviews},
        key=str,
    )
    scopes: tuple[UUID | None, ...] = (None, *product_ids)
    metrics: list[CalculatedReviewMetric] = []
    for scope_product_id in scopes:
        scope_reviews = tuple(
            review
            for review in reviews
            if scope_product_id is None or review.comparison_product_id == scope_product_id
        )
        if not scope_reviews:
            continue
        scope_review_ids = {review.id for review in scope_reviews}
        for dimension in dimensions:
            scope_annotations = tuple(
                annotation
                for annotation in valid_annotations
                if annotation.review_id in scope_review_ids
                and annotation.dimension_id == dimension.id
            )
            metrics.extend(
                _calculate_scope_metrics(
                    comparison_id=comparison_id,
                    comparison_product_id=scope_product_id,
                    dimension_id=dimension.id,
                    reviews=scope_reviews,
                    annotations=scope_annotations,
                )
            )
    return tuple(metrics)


def _calculate_scope_metrics(
    *,
    comparison_id: UUID,
    comparison_product_id: UUID | None,
    dimension_id: UUID,
    reviews: tuple[MetricReview, ...],
    annotations: tuple[MetricAnnotation, ...],
) -> tuple[CalculatedReviewMetric, ...]:
    """计算单个作用域和维度的计数、比例、覆盖率与平均置信度。by AI.Coding"""
    annotation_count = len(annotations)
    sentiment_counts = {
        sentiment: sum(annotation.sentiment is sentiment for annotation in annotations)
        for sentiment in ReviewSentiment
    }
    covered_review_count = len({annotation.review_id for annotation in annotations})
    average_confidence = (
        Decimal(0)
        if not annotations
        else sum(Decimal(str(annotation.confidence)) for annotation in annotations)
        / Decimal(annotation_count)
    )
    values = {
        "annotation_count": Decimal(annotation_count),
        "positive_count": Decimal(sentiment_counts[ReviewSentiment.POSITIVE]),
        "neutral_count": Decimal(sentiment_counts[ReviewSentiment.NEUTRAL]),
        "negative_count": Decimal(sentiment_counts[ReviewSentiment.NEGATIVE]),
        "positive_ratio": _ratio(
            sentiment_counts[ReviewSentiment.POSITIVE],
            annotation_count,
        ),
        "neutral_ratio": _ratio(
            sentiment_counts[ReviewSentiment.NEUTRAL],
            annotation_count,
        ),
        "negative_ratio": _ratio(
            sentiment_counts[ReviewSentiment.NEGATIVE],
            annotation_count,
        ),
        "coverage_ratio": _ratio(covered_review_count, len(reviews)),
        "average_confidence": average_confidence,
    }
    confidence = float(_quantize(average_confidence))
    review_ids = tuple(review.id for review in reviews)
    annotation_ids = tuple(annotation.id for annotation in annotations)
    return tuple(
        CalculatedReviewMetric(
            comparison_id=comparison_id,
            comparison_product_id=comparison_product_id,
            dimension_id=dimension_id,
            metric_type=metric_type,
            numeric_value=_quantize(values[metric_type]),
            sample_size=len(reviews),
            confidence=confidence,
            review_ids=review_ids,
            annotation_ids=annotation_ids,
        )
        for metric_type in _METRIC_TYPES
    )


def _ratio(numerator: int, denominator: int) -> Decimal:
    """以 Decimal 计算比例，并把零分母稳定映射为零。by AI.Coding"""
    if denominator == 0:
        return Decimal(0)
    return Decimal(numerator) / Decimal(denominator)


def _quantize(value: Decimal) -> Decimal:
    """统一以八位小数和 HALF_UP 规则持久化指标。by AI.Coding"""
    return value.quantize(_SCALE, rounding=ROUND_HALF_UP)
