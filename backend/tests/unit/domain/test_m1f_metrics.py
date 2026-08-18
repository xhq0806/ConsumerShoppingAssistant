"""M1-F 评论注解确定性指标计算测试。by AI.Coding"""

from decimal import Decimal
from uuid import uuid4

from app.domain.metrics.calculation import (
    MetricAnnotation,
    MetricDimension,
    MetricReview,
    calculate_review_metrics,
)
from app.domain.reviews import ReviewSentiment


def test_metrics_calculate_product_and_task_counts_ratios_coverage_and_confidence() -> None:
    """同一批持久化输入应产生稳定的商品级和任务级指标。by AI.Coding"""
    product_a = uuid4()
    product_b = uuid4()
    dimension = MetricDimension(id=uuid4(), code="heating")
    reviews = (
        MetricReview(id=uuid4(), comparison_product_id=product_a),
        MetricReview(id=uuid4(), comparison_product_id=product_a),
        MetricReview(id=uuid4(), comparison_product_id=product_b),
    )
    annotations = (
        MetricAnnotation(
            id=uuid4(),
            review_id=reviews[0].id,
            dimension_id=dimension.id,
            sentiment=ReviewSentiment.NEGATIVE,
            confidence=0.8,
        ),
        MetricAnnotation(
            id=uuid4(),
            review_id=reviews[2].id,
            dimension_id=dimension.id,
            sentiment=ReviewSentiment.POSITIVE,
            confidence=1.0,
        ),
    )

    metrics = calculate_review_metrics(
        comparison_id=uuid4(),
        reviews=reviews,
        annotations=annotations,
        dimensions=(dimension,),
    )

    task_metrics = {
        item.metric_type: item for item in metrics if item.comparison_product_id is None
    }
    assert task_metrics["annotation_count"].numeric_value == Decimal("2.00000000")
    assert task_metrics["positive_count"].numeric_value == Decimal("1.00000000")
    assert task_metrics["negative_ratio"].numeric_value == Decimal("0.50000000")
    assert task_metrics["coverage_ratio"].numeric_value == Decimal("0.66666667")
    assert task_metrics["average_confidence"].numeric_value == Decimal("0.90000000")
    assert task_metrics["coverage_ratio"].sample_size == 3
    assert set(task_metrics["coverage_ratio"].review_ids) == {item.id for item in reviews}
    assert set(task_metrics["coverage_ratio"].annotation_ids) == {item.id for item in annotations}

    product_a_metrics = {
        item.metric_type: item for item in metrics if item.comparison_product_id == product_a
    }
    assert product_a_metrics["annotation_count"].numeric_value == Decimal("1.00000000")
    assert product_a_metrics["negative_ratio"].numeric_value == Decimal("1.00000000")
    assert product_a_metrics["coverage_ratio"].numeric_value == Decimal("0.50000000")


def test_metrics_emit_zero_values_for_review_scope_without_annotations() -> None:
    """有评论但无相关注解的作用域仍生成可复算零值指标。by AI.Coding"""
    product_id = uuid4()
    review = MetricReview(id=uuid4(), comparison_product_id=product_id)
    dimension = MetricDimension(id=uuid4(), code="signal_quality")

    metrics = calculate_review_metrics(
        comparison_id=uuid4(),
        reviews=(review,),
        annotations=(),
        dimensions=(dimension,),
    )

    assert len(metrics) == 18
    assert all(item.numeric_value == Decimal("0E-8") for item in metrics)
    assert all(item.review_ids == (review.id,) for item in metrics)
    assert all(item.annotation_ids == () for item in metrics)


def test_metrics_skip_empty_product_scope_and_return_empty_for_zero_reviews() -> None:
    """没有输入评论时不伪造来源引用或指标记录。by AI.Coding"""
    comparison_id = uuid4()
    dimension = MetricDimension(id=uuid4(), code="camera")

    assert (
        calculate_review_metrics(
            comparison_id=comparison_id,
            reviews=(),
            annotations=(),
            dimensions=(dimension,),
        )
        == ()
    )
