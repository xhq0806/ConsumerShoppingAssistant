"""M1-G 购买报告结构化契约、来源目录与确定性降级规则。by AI.Coding"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.errors import InputError
from app.domain.reports import (
    ClaimSourceRef,
    ClaimSourceType,
    ReportClaimType,
    parse_claim_source_ref,
)

_ABSOLUTE_PHRASES = ("绝对最好", "一定不会", "百分之百", "必然", "永远不会")


class _StrictReportSchema(BaseModel):
    """禁止报告模型输出契约外字段。by AI.Coding"""

    model_config = ConfigDict(extra="forbid")


class ReportSourceRefOutput(_StrictReportSchema):
    """定义模型可选择的三类报告来源引用。by AI.Coding"""

    type: Literal["product_snapshot", "analysis_metric", "raw_review"]
    id: UUID
    field: str | None = None
    evidence: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ReportSourceRefOutput:
        """复用 claim 来源白名单校验并拒绝类型不匹配字段。by AI.Coding"""
        parse_claim_source_ref(self.to_payload())
        return self

    def to_payload(self) -> dict[str, str]:
        """转换为领域来源解析器接受的最小 JSON。by AI.Coding"""
        payload = {"type": self.type, "id": str(self.id)}
        if self.field is not None:
            payload["field"] = self.field
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        return payload


class ReportClaimOutput(_StrictReportSchema):
    """定义带来源和置信度的单条报告结论。by AI.Coding"""

    claim_type: ReportClaimType
    text: str = Field(min_length=1, max_length=500)
    source_refs: list[ReportSourceRefOutput] = Field(min_length=1, max_length=5)
    confidence: float = Field(ge=0, le=1)


class ScenarioRecommendationOutput(_StrictReportSchema):
    """定义用户已声明场景下的推荐 claim 索引。by AI.Coding"""

    scenario: str = Field(min_length=1, max_length=80)
    product_id: UUID | None
    claim_index: int = Field(ge=0)


class ReportSummaryOutput(_StrictReportSchema):
    """定义决策摘要对 claim 列表的受控引用。by AI.Coding"""

    headline: str = Field(min_length=1, max_length=200)
    recommended_product_id: UUID | None
    recommendation_claim_index: int = Field(ge=0)
    scenario_recommendations: list[ScenarioRecommendationOutput] = Field(max_length=5)
    key_reason_claim_indexes: list[int] = Field(min_length=1, max_length=5)
    risk_claim_indexes: list[int] = Field(max_length=5)
    confidence: float = Field(ge=0, le=1)


class ReportDifferenceOutput(_StrictReportSchema):
    """定义关键差异维度与解释 claim 的关联。by AI.Coding"""

    dimension_code: str = Field(min_length=1, max_length=100)
    claim_index: int = Field(ge=0)


class PurchaseReportOutput(_StrictReportSchema):
    """定义 report profile 必须返回的完整结构。by AI.Coding"""

    claims: list[ReportClaimOutput] = Field(min_length=1, max_length=20)
    summary: ReportSummaryOutput
    differences: list[ReportDifferenceOutput] = Field(min_length=1, max_length=8)


@dataclass(frozen=True)
class ReportProductInput:
    """承载报告所需的当前任务商品事实。by AI.Coding"""

    id: UUID
    snapshot_id: UUID
    title: str
    category: str | None
    brand: str | None
    shop_name: str | None
    price: Decimal | None
    currency: str
    specifications: dict[str, str]
    after_sales: tuple[str, ...]
    review_count: int


@dataclass(frozen=True)
class ReportDimensionInput:
    """承载任务已选维度和确定性样本阈值。by AI.Coding"""

    id: UUID
    code: str
    name: str
    min_sample_size: int


@dataclass(frozen=True)
class ReportMetricInput:
    """承载模型可解释但不可修改的确定性指标。by AI.Coding"""

    id: UUID
    comparison_product_id: UUID | None
    dimension_id: UUID
    dimension_code: str
    metric_type: str
    numeric_value: Decimal | None
    sample_size: int
    confidence: float | None


@dataclass(frozen=True)
class ReportEvidenceInput:
    """承载已通过连续子串校验的代表性评论证据。by AI.Coding"""

    review_id: UUID
    comparison_product_id: UUID
    dimension_id: UUID
    dimension_code: str
    sentiment: str
    confidence: float
    evidence: str


@dataclass(frozen=True)
class ReportPreferencesInput:
    """承载报告场景化推荐所需的规范化用户偏好。by AI.Coding"""

    budget_min: Decimal | None
    budget_max: Decimal | None
    usage_scenarios: tuple[str, ...]
    priority_concerns: tuple[str, ...]
    deal_breakers: tuple[str, ...]


@dataclass(frozen=True)
class ReportGenerationContext:
    """聚合一次报告调用允许使用的全部当前任务输入。by AI.Coding"""

    comparison_id: UUID
    products: tuple[ReportProductInput, ...]
    dimensions: tuple[ReportDimensionInput, ...]
    metrics: tuple[ReportMetricInput, ...]
    evidences: tuple[ReportEvidenceInput, ...]
    preferences: ReportPreferencesInput


@dataclass(frozen=True)
class ValidatedReportClaim:
    """表示通过来源目录校验的报告 claim。by AI.Coding"""

    claim_type: ReportClaimType
    text: str
    source_refs: tuple[dict[str, str], ...]
    confidence: float


@dataclass(frozen=True)
class ValidatedReportSummary:
    """表示通过商品、场景和索引校验的决策摘要。by AI.Coding"""

    headline: str
    recommended_product_id: UUID | None
    recommendation_claim_index: int
    scenario_recommendations: tuple[ScenarioRecommendationOutput, ...]
    key_reason_claim_indexes: tuple[int, ...]
    risk_claim_indexes: tuple[int, ...]
    confidence: float


@dataclass(frozen=True)
class ValidatedReportDifference:
    """表示通过维度和 claim 索引校验的关键差异。by AI.Coding"""

    dimension_code: str
    claim_index: int


@dataclass(frozen=True)
class ValidatedPurchaseReport:
    """表示可安全持久化和发布的结构化报告。by AI.Coding"""

    claims: tuple[ValidatedReportClaim, ...]
    summary: ValidatedReportSummary
    differences: tuple[ValidatedReportDifference, ...]


def validate_purchase_report_output(
    *,
    context: ReportGenerationContext,
    output: PurchaseReportOutput,
) -> ValidatedPurchaseReport:
    """校验模型只能组合当前任务商品、维度、claim 和来源目录。by AI.Coding"""
    product_ids = {product.id for product in context.products}
    dimension_codes = {dimension.code for dimension in context.dimensions}
    allowed_scenarios = set(context.preferences.usage_scenarios)
    available_sources = {source.key() for source in available_report_sources(context)}
    claims = tuple(_validated_claim(claim, available_sources) for claim in output.claims)
    claim_count = len(claims)

    _validate_product_id(output.summary.recommended_product_id, product_ids)
    _validate_claim_index(output.summary.recommendation_claim_index, claim_count)
    if (
        claims[output.summary.recommendation_claim_index].claim_type
        is not ReportClaimType.RECOMMENDATION
    ):
        raise InputError("综合推荐必须引用 recommendation 类型 claim index")

    referenced_indexes = {
        output.summary.recommendation_claim_index,
        *output.summary.key_reason_claim_indexes,
        *output.summary.risk_claim_indexes,
    }
    scenarios: list[ScenarioRecommendationOutput] = []
    seen_scenarios: set[str] = set()
    for scenario in output.summary.scenario_recommendations:
        if scenario.scenario not in allowed_scenarios:
            raise InputError("报告返回了用户未声明的推荐场景")
        if scenario.scenario in seen_scenarios:
            raise InputError("分场景推荐不能包含重复场景")
        seen_scenarios.add(scenario.scenario)
        _validate_product_id(scenario.product_id, product_ids)
        _validate_claim_index(scenario.claim_index, claim_count)
        if claims[scenario.claim_index].claim_type is not ReportClaimType.RECOMMENDATION:
            raise InputError("分场景推荐必须引用 recommendation 类型 claim index")
        referenced_indexes.add(scenario.claim_index)
        scenarios.append(scenario)

    for index in output.summary.key_reason_claim_indexes:
        _validate_claim_index(index, claim_count)
        if claims[index].claim_type is ReportClaimType.WARNING:
            raise InputError("主要推荐理由不能引用 warning claim")
    for index in output.summary.risk_claim_indexes:
        _validate_claim_index(index, claim_count)
        if claims[index].claim_type not in {
            ReportClaimType.WARNING,
            ReportClaimType.DISADVANTAGE,
        }:
            raise InputError("主要风险必须引用 warning 或 disadvantage claim")

    differences: list[ValidatedReportDifference] = []
    seen_dimensions: set[str] = set()
    for difference in output.differences:
        if difference.dimension_code not in dimension_codes:
            raise InputError("报告返回了任务未选中的关键差异维度")
        if difference.dimension_code in seen_dimensions:
            raise InputError("关键差异不能包含重复维度")
        seen_dimensions.add(difference.dimension_code)
        _validate_claim_index(difference.claim_index, claim_count)
        if claims[difference.claim_index].claim_type not in {
            ReportClaimType.FACT,
            ReportClaimType.ADVANTAGE,
            ReportClaimType.DISADVANTAGE,
            ReportClaimType.RECOMMENDATION,
        }:
            raise InputError("关键差异引用了不允许的 claim 类型")
        referenced_indexes.add(difference.claim_index)
        differences.append(
            ValidatedReportDifference(
                dimension_code=difference.dimension_code,
                claim_index=difference.claim_index,
            )
        )
    if referenced_indexes != set(range(claim_count)):
        raise InputError("报告存在未被摘要或关键差异引用的 claim index")

    return ValidatedPurchaseReport(
        claims=claims,
        summary=ValidatedReportSummary(
            headline=output.summary.headline,
            recommended_product_id=output.summary.recommended_product_id,
            recommendation_claim_index=output.summary.recommendation_claim_index,
            scenario_recommendations=tuple(scenarios),
            key_reason_claim_indexes=tuple(output.summary.key_reason_claim_indexes),
            risk_claim_indexes=tuple(output.summary.risk_claim_indexes),
            confidence=output.summary.confidence,
        ),
        differences=tuple(differences),
    )


def available_report_sources(context: ReportGenerationContext) -> tuple[ClaimSourceRef, ...]:
    """生成模型可引用的当前任务事实、指标和已验证证据目录。by AI.Coding"""
    sources: list[ClaimSourceRef] = []
    for product in context.products:
        fields = {
            "title": product.title,
            "category": product.category,
            "brand": product.brand,
            "shop_name": product.shop_name,
            "price": product.price,
            "currency": product.currency,
            "specifications": product.specifications,
            "after_sales": product.after_sales,
        }
        for field, value in fields.items():
            if value is None or value == "" or value == {} or value == ():
                continue
            sources.append(
                ClaimSourceRef(
                    ClaimSourceType.PRODUCT_SNAPSHOT,
                    product.snapshot_id,
                    field=field,
                )
            )
    sources.extend(
        ClaimSourceRef(ClaimSourceType.ANALYSIS_METRIC, metric.id) for metric in context.metrics
    )
    sources.extend(
        ClaimSourceRef(
            ClaimSourceType.RAW_REVIEW,
            evidence.review_id,
            evidence=evidence.evidence,
        )
        for evidence in context.evidences
    )
    return tuple(sources)


def determine_report_warnings(context: ReportGenerationContext) -> tuple[str, ...]:
    """根据事实缺失、评论覆盖和样本阈值确定部分报告警告。by AI.Coding"""
    warnings: list[str] = []
    for product in context.products:
        missing: list[str] = []
        if product.brand is None:
            missing.append("品牌")
        if not product.specifications:
            missing.append("规格")
        if not product.after_sales:
            missing.append("售后")
        if missing:
            warnings.append(f"{product.title} 缺少{'、'.join(missing)}信息。")
        if product.review_count == 0:
            warnings.append(f"{product.title} 没有清洗后有效评论。")
    if not context.metrics:
        warnings.append("当前任务没有可用于报告的确定性评论指标。")
    product_ids = {product.id for product in context.products}
    for dimension in context.dimensions:
        if dimension.min_sample_size <= 0:
            continue
        samples_by_product = {
            metric.comparison_product_id: metric.sample_size
            for metric in context.metrics
            if metric.dimension_id == dimension.id
            and metric.comparison_product_id is not None
            and metric.metric_type == "annotation_count"
        }
        if any(
            samples_by_product.get(product_id, 0) < dimension.min_sample_size
            for product_id in product_ids
        ):
            warnings.append(
                f"{dimension.name} 的评论样本低于目录阈值 {dimension.min_sample_size}。"
            )
    return tuple(dict.fromkeys(warnings))


def build_fake_purchase_report(context: ReportGenerationContext) -> PurchaseReportOutput:
    """根据价格和受控来源生成可复现的 Fake 报告。by AI.Coding"""
    warnings = determine_report_warnings(context)
    recommended = _fake_recommended_product(context)
    source_refs = _fake_recommendation_sources(context)
    if recommended is None:
        recommendation_text = "基于当前已获取数据，暂时无法给出明确的单一商品推荐。"
        headline = "当前数据不足以形成明确胜者"
    else:
        recommendation_text = f"基于当前预算、价格和已获取数据，更建议考虑{recommended.title}。"
        headline = f"当前更适合考虑{recommended.title}"
    confidence = 0.62 if warnings else 0.85
    claim = ReportClaimOutput(
        claim_type=ReportClaimType.RECOMMENDATION,
        text=recommendation_text,
        source_refs=source_refs,
        confidence=confidence,
    )
    difference_dimension = next(
        (dimension for dimension in context.dimensions if dimension.code == "price"),
        context.dimensions[0],
    )
    difference_claim = _fake_difference_claim(context, difference_dimension)
    difference_code = (
        "price"
        if any(dimension.code == "price" for dimension in context.dimensions)
        else difference_dimension.code
    )
    return PurchaseReportOutput(
        claims=[claim, difference_claim],
        summary=ReportSummaryOutput(
            headline=headline,
            recommended_product_id=None if recommended is None else recommended.id,
            recommendation_claim_index=0,
            scenario_recommendations=[
                ScenarioRecommendationOutput(
                    scenario=scenario,
                    product_id=None if recommended is None else recommended.id,
                    claim_index=0,
                )
                for scenario in context.preferences.usage_scenarios
            ],
            key_reason_claim_indexes=[0],
            risk_claim_indexes=[],
            confidence=confidence,
        ),
        differences=[
            ReportDifferenceOutput(
                dimension_code=difference_code,
                claim_index=1,
            )
        ],
    )


def _validated_claim(
    claim: ReportClaimOutput,
    available_sources: set[tuple[ClaimSourceType, UUID, str | None, str | None]],
) -> ValidatedReportClaim:
    """校验 claim 文案和每个来源都来自输入目录。by AI.Coding"""
    if any(phrase in claim.text for phrase in _ABSOLUTE_PHRASES):
        raise InputError("报告结论不得使用绝对化表达")
    payloads: list[dict[str, str]] = []
    for source in claim.source_refs:
        payload = source.to_payload()
        parsed = parse_claim_source_ref(payload)
        if parsed.key() not in available_sources:
            raise InputError("报告 claim 引用了输入目录外的来源")
        payloads.append(parsed.to_payload())
    return ValidatedReportClaim(
        claim_type=claim.claim_type,
        text=claim.text,
        source_refs=tuple(payloads),
        confidence=claim.confidence,
    )


def _validate_product_id(product_id: UUID | None, allowed: set[UUID]) -> None:
    """拒绝任务外推荐商品。by AI.Coding"""
    if product_id is not None and product_id not in allowed:
        raise InputError("报告返回了当前任务之外的商品")


def _validate_claim_index(index: int, claim_count: int) -> None:
    """拒绝越界 claim index。by AI.Coding"""
    if not 0 <= index < claim_count:
        raise InputError("报告包含越界 claim index")


def _fake_recommended_product(
    context: ReportGenerationContext,
) -> ReportProductInput | None:
    """优先选择预算范围内价格最低的候选商品。by AI.Coding"""
    priced = [product for product in context.products if product.price is not None]
    within_budget = [
        product
        for product in priced
        if (
            context.preferences.budget_min is None
            or product.price is not None
            and product.price >= context.preferences.budget_min
        )
        and (
            context.preferences.budget_max is None
            or product.price is not None
            and product.price <= context.preferences.budget_max
        )
    ]
    candidates = within_budget or priced
    if not candidates:
        return None
    return min(candidates, key=lambda product: (product.price or Decimal(0), str(product.id)))


def _fake_recommendation_sources(
    context: ReportGenerationContext,
) -> list[ReportSourceRefOutput]:
    """为 Fake 推荐选择价格、指标或标题来源。by AI.Coding"""
    priced = [product for product in context.products if product.price is not None]
    if priced:
        return [
            ReportSourceRefOutput(
                type="product_snapshot",
                id=product.snapshot_id,
                field="price",
            )
            for product in priced[:5]
        ]
    if context.metrics:
        return [
            ReportSourceRefOutput(
                type="analysis_metric",
                id=context.metrics[0].id,
            )
        ]
    return [
        ReportSourceRefOutput(
            type="product_snapshot",
            id=context.products[0].snapshot_id,
            field="title",
        )
    ]


def _fake_difference_claim(
    context: ReportGenerationContext,
    dimension: ReportDimensionInput,
) -> ReportClaimOutput:
    """为关键差异生成与该维度来源语义一致的确定性 fact claim。by AI.Coding"""
    if dimension.code == "price":
        priced = [product for product in context.products if product.price is not None]
        if priced:
            values = "、".join(f"{product.title} ¥{product.price}" for product in priced)
            return ReportClaimOutput(
                claim_type=ReportClaimType.FACT,
                text=f"当前价格对比为：{values}。",
                source_refs=[
                    ReportSourceRefOutput(
                        type="product_snapshot",
                        id=product.snapshot_id,
                        field="price",
                    )
                    for product in priced[:5]
                ],
                confidence=0.95,
            )
    metrics = [
        metric
        for metric in context.metrics
        if metric.dimension_id == dimension.id
        and metric.metric_type
        in {
            "annotation_count",
            "coverage_ratio",
            "positive_ratio",
            "negative_ratio",
        }
    ]
    if metrics:
        sample_size = max(metric.sample_size for metric in metrics)
        return ReportClaimOutput(
            claim_type=ReportClaimType.FACT,
            text=(
                f"{dimension.name}维度的当前评论指标样本量最多为 {sample_size}，"
                "应结合覆盖率和数据警告谨慎比较。"
            ),
            source_refs=[
                ReportSourceRefOutput(
                    type="analysis_metric",
                    id=metric.id,
                )
                for metric in metrics[:5]
            ],
            confidence=0.7,
        )
    evidences = [
        evidence for evidence in context.evidences if evidence.dimension_id == dimension.id
    ]
    if evidences:
        return ReportClaimOutput(
            claim_type=ReportClaimType.FACT,
            text=f"{dimension.name}维度当前有 {len(evidences)} 条代表性评论证据。",
            source_refs=[
                ReportSourceRefOutput(
                    type="raw_review",
                    id=evidence.review_id,
                    evidence=evidence.evidence,
                )
                for evidence in evidences[:5]
            ],
            confidence=0.7,
        )
    return ReportClaimOutput(
        claim_type=ReportClaimType.FACT,
        text=f"{dimension.name}维度当前缺少可直接比较的数据。",
        source_refs=[
            ReportSourceRefOutput(
                type="product_snapshot",
                id=context.products[0].snapshot_id,
                field="title",
            )
        ],
        confidence=0.3,
    )
