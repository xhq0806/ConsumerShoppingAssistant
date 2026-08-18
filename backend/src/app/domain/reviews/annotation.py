"""M1-F 评论智能注解结构化契约与纯语义校验。by AI.Coding"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import InputError
from app.domain.reviews import (
    ReviewSentiment,
    validate_confidence,
    validate_review_evidence,
)


class _StrictAnnotationSchema(BaseModel):
    """禁止模型输出契约外字段，避免解释文本混入业务结果。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")


class AnnotationOutput(_StrictAnnotationSchema):
    """定义单条评论与单个受控维度之间的模型注解。by AI.Coding"""

    dimension_code: str = Field(min_length=1, max_length=100)
    sentiment: ReviewSentiment
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1)


class ReviewAnnotationOutput(_StrictAnnotationSchema):
    """定义模型对一条输入评论的完整处理结果。by AI.Coding"""

    review_id: UUID
    annotations: list[AnnotationOutput]


class ReviewAnnotationBatchOutput(_StrictAnnotationSchema):
    """定义一次最多二十条评论的结构化模型响应。by AI.Coding"""

    review_results: list[ReviewAnnotationOutput] = Field(min_length=1, max_length=20)


@dataclass(frozen=True)
class AnnotationDimension:
    """承载模型可使用的任务已选维度白名单。by AI.Coding"""

    id: UUID
    code: str
    name: str
    description: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ReviewForAnnotation:
    """承载模型输入所需的最小评论字段。by AI.Coding"""

    id: UUID
    comparison_product_id: UUID
    content: str
    rating: int | None


@dataclass(frozen=True)
class ValidatedReviewAnnotation:
    """表示已经通过任务维度和原文证据校验的注解。by AI.Coding"""

    review_id: UUID
    dimension_id: UUID
    sentiment: ReviewSentiment
    confidence: float
    evidence: str


@dataclass(frozen=True)
class ValidatedAnnotationBatch:
    """表示可安全持久化的整批处理结果。by AI.Coding"""

    processed_review_ids: tuple[UUID, ...]
    annotations: tuple[ValidatedReviewAnnotation, ...]


def validate_annotation_output(
    *,
    reviews: tuple[ReviewForAnnotation, ...],
    dimensions: tuple[AnnotationDimension, ...],
    output: ReviewAnnotationBatchOutput,
) -> ValidatedAnnotationBatch:
    """校验批次完整覆盖、受控维度、唯一关系和连续原文证据。by AI.Coding"""
    if not reviews or len(reviews) > 20:
        raise InputError("单次评论注解批次必须包含 1 到 20 条评论")
    reviews_by_id = {review.id: review for review in reviews}
    dimensions_by_code = {dimension.code: dimension for dimension in dimensions}
    result_ids = [result.review_id for result in output.review_results]
    if len(result_ids) != len(set(result_ids)):
        raise InputError("模型结果包含重复评论")
    if set(result_ids) != set(reviews_by_id):
        raise InputError("模型结果必须恰好覆盖当前评论批次")

    validated: list[ValidatedReviewAnnotation] = []
    seen_pairs: set[tuple[UUID, UUID]] = set()
    for result in output.review_results:
        review = reviews_by_id[result.review_id]
        for annotation in result.annotations:
            dimension = dimensions_by_code.get(annotation.dimension_code)
            if dimension is None:
                raise InputError(f"模型返回了任务未选中的维度 {annotation.dimension_code}")
            pair = (review.id, dimension.id)
            if pair in seen_pairs:
                raise InputError("同一评论不能返回重复维度注解")
            seen_pairs.add(pair)
            validated.append(
                ValidatedReviewAnnotation(
                    review_id=review.id,
                    dimension_id=dimension.id,
                    sentiment=ReviewSentiment(annotation.sentiment),
                    confidence=_required_confidence(annotation.confidence),
                    evidence=validate_review_evidence(
                        content=review.content,
                        evidence=annotation.evidence,
                    ),
                )
            )
    # 按输入评论顺序和维度 code 稳定化，避免模型返回顺序影响持久化结果。
    review_position = {review.id: index for index, review in enumerate(reviews)}
    dimension_code_by_id = {dimension.id: dimension.code for dimension in dimensions}
    validated.sort(
        key=lambda item: (
            review_position[item.review_id],
            dimension_code_by_id[item.dimension_id],
        )
    )
    return ValidatedAnnotationBatch(
        processed_review_ids=tuple(review.id for review in reviews),
        annotations=tuple(validated),
    )


def build_fake_annotation_output(
    *,
    reviews: tuple[ReviewForAnnotation, ...],
    dimensions: tuple[AnnotationDimension, ...],
) -> ReviewAnnotationBatchOutput:
    """按受控 alias 和评分生成可复现的 Fake LLM 结构化输出。by AI.Coding"""
    if not reviews or len(reviews) > 20:
        raise InputError("单次评论注解批次必须包含 1 到 20 条评论")
    results: list[ReviewAnnotationOutput] = []
    for review in reviews:
        annotations: list[AnnotationOutput] = []
        for dimension in dimensions:
            evidence = _first_matching_evidence(review.content, dimension.aliases)
            if evidence is None:
                continue
            annotations.append(
                AnnotationOutput(
                    dimension_code=dimension.code,
                    sentiment=_fake_sentiment(
                        dimension_code=dimension.code,
                        content=review.content,
                        rating=review.rating,
                    ),
                    confidence=0.9,
                    evidence=evidence,
                )
            )
        results.append(ReviewAnnotationOutput(review_id=review.id, annotations=annotations))
    return ReviewAnnotationBatchOutput(review_results=results)


def _first_matching_evidence(content: str, aliases: tuple[str, ...]) -> str | None:
    """按声明顺序返回评论正文中首个逐字 alias。by AI.Coding"""
    normalized_content = unicodedata.normalize("NFKC", content).casefold()
    for alias in aliases:
        normalized_alias = unicodedata.normalize("NFKC", alias).casefold()
        index = normalized_content.find(normalized_alias)
        if index >= 0 and len(normalized_content) == len(content):
            return content[index : index + len(alias)]
        if alias in content:
            return alias
    return None


def _fake_sentiment(
    *,
    dimension_code: str,
    content: str,
    rating: int | None,
) -> ReviewSentiment:
    """使用稳定启发式生成测试情感，不执行评论中的任何指令。by AI.Coding"""
    normalized = unicodedata.normalize("NFKC", content).casefold()
    if dimension_code == "heating":
        if "不发热" in normalized or "不烫" in normalized:
            return ReviewSentiment.POSITIVE
        if "发热" in normalized or "烫" in normalized:
            return ReviewSentiment.NEGATIVE
    if any(marker in normalized for marker in ("很差", "不好", "断流", "失灵", "严重")):
        return ReviewSentiment.NEGATIVE
    if rating is not None:
        if rating >= 4:
            return ReviewSentiment.POSITIVE
        if rating <= 2:
            return ReviewSentiment.NEGATIVE
    return ReviewSentiment.NEUTRAL


def _required_confidence(value: float) -> float:
    """把可空通用校验结果收窄为注解必填置信度。by AI.Coding"""
    validated = validate_confidence(value)
    assert validated is not None
    return validated
