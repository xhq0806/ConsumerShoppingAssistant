"""创建 T05 评论、指标、报告与模型审计数据模型。by AI.Coding

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建且仅创建 T05 的七张分析相关表。by AI.Coding"""
    # 模型运行先创建，以便评论注解通过可空外键引用并在删除时置空。
    op.create_table(
        "model_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=True),
        sa.Column("purpose", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=7), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('success', 'error')", name=op.f("ck_model_runs_status")),
        sa.CheckConstraint("latency_ms >= 0", name=op.f("ck_model_runs_latency_ms")),
        sa.CheckConstraint("attempts >= 1", name=op.f("ck_model_runs_attempts")),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0", name=op.f("ck_model_runs_input_tokens")
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name=op.f("ck_model_runs_output_tokens"),
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0", name=op.f("ck_model_runs_total_tokens")
        ),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["comparison_tasks.id"],
            name=op.f("fk_model_runs_comparison_id_comparison_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_runs")),
        sa.UniqueConstraint("event_id", name="uq_model_runs_event_id"),
    )
    op.create_index(op.f("ix_model_runs_comparison_id"), "model_runs", ["comparison_id"])
    op.create_index(
        "ix_model_runs_purpose_status_created", "model_runs", ["purpose", "status", "occurred_at"]
    )
    op.create_index(
        "ix_model_runs_comparison_occurred", "model_runs", ["comparison_id", "occurred_at"]
    )

    op.create_table(
        "raw_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_product_id", sa.UUID(), nullable=False),
        sa.Column("external_review_id", sa.String(length=255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("sku_text", sa.String(length=500), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5", name=op.f("ck_raw_reviews_rating")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source) = 'object' AND source ? 'provider' "
            "AND source ? 'source_id' AND source ? 'obtained_at' "
            "AND jsonb_typeof(source -> 'provider') = 'string' "
            "AND jsonb_typeof(source -> 'source_id') = 'string' "
            "AND jsonb_typeof(source -> 'obtained_at') = 'string' "
            "AND source - ARRAY['provider', 'source_id', 'obtained_at'] = '{}'::jsonb",
            name=op.f("ck_raw_reviews_source_reference"),
        ),
        sa.ForeignKeyConstraint(
            ["comparison_product_id"],
            ["comparison_products.id"],
            name=op.f("fk_raw_reviews_comparison_product_id_comparison_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_raw_reviews")),
        sa.UniqueConstraint(
            "comparison_product_id", "external_review_id", name="uq_raw_reviews_product_external_id"
        ),
    )
    op.create_index(
        op.f("ix_raw_reviews_comparison_product_id"), "raw_reviews", ["comparison_product_id"]
    )
    op.create_index("ix_raw_reviews_content_hash", "raw_reviews", ["content_hash"])
    op.create_index("ix_raw_reviews_fetched_at", "raw_reviews", ["fetched_at"])
    op.create_index("ix_raw_reviews_ingested_at", "raw_reviews", ["ingested_at"])

    op.create_unique_constraint(
        "uq_comparison_products_comparison_id_id",
        "comparison_products",
        ["comparison_id", "id"],
    )

    op.create_table(
        "analysis_metrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("comparison_product_id", sa.UUID(), nullable=True),
        sa.Column("dimension_id", sa.UUID(), nullable=False),
        sa.Column("metric_type", sa.String(length=100), nullable=False),
        sa.Column("numeric_value", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_refs", postgresql.JSONB(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "numeric_value IS NOT NULL OR text_value IS NOT NULL",
            name=op.f("ck_analysis_metrics_has_value"),
        ),
        sa.CheckConstraint("sample_size >= 0", name=op.f("ck_analysis_metrics_sample_size")),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'",
            name=op.f("ck_analysis_metrics_source_refs_array"),
        ),
        sa.CheckConstraint(
            "jsonb_array_length(source_refs) > 0",
            name=op.f("ck_analysis_metrics_source_refs_nonempty"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name=op.f("ck_analysis_metrics_confidence"),
        ),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["comparison_tasks.id"],
            name=op.f("fk_analysis_metrics_comparison_id_comparison_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["comparison_id", "comparison_product_id"],
            ["comparison_products.comparison_id", "comparison_products.id"],
            name="fk_analysis_metrics_product_belongs_to_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dimension_id"],
            ["dimension_definitions.id"],
            name=op.f("fk_analysis_metrics_dimension_id_dimension_definitions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_metrics")),
    )
    op.create_index(
        op.f("ix_analysis_metrics_comparison_id"), "analysis_metrics", ["comparison_id"]
    )
    op.create_index(
        op.f("ix_analysis_metrics_comparison_product_id"),
        "analysis_metrics",
        ["comparison_product_id"],
    )
    op.create_index(op.f("ix_analysis_metrics_dimension_id"), "analysis_metrics", ["dimension_id"])
    op.create_index(
        "ix_analysis_metrics_comparison_dimension",
        "analysis_metrics",
        ["comparison_id", "dimension_id"],
    )
    op.create_index(
        "uq_analysis_metrics_scope",
        "analysis_metrics",
        ["comparison_id", "comparison_product_id", "dimension_id", "metric_type"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )

    op.create_table(
        "comparison_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("differences", postgresql.JSONB(), nullable=False),
        sa.Column("full_comparison", postgresql.JSONB(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_comparison_reports_version")),
        sa.CheckConstraint(
            "status IN ('draft', 'generating', 'completed', 'partial', 'failed')",
            name=op.f("ck_comparison_reports_status"),
        ),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["comparison_tasks.id"],
            name=op.f("fk_comparison_reports_comparison_id_comparison_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comparison_reports")),
        sa.UniqueConstraint("comparison_id", "version", name="uq_comparison_reports_task_version"),
    )
    op.create_index(
        op.f("ix_comparison_reports_comparison_id"), "comparison_reports", ["comparison_id"]
    )
    op.create_index(
        "ix_comparison_reports_comparison_generated",
        "comparison_reports",
        ["comparison_id", "generated_at"],
    )

    op.create_table(
        "followup_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=9), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("answer_sources", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name=op.f("ck_followup_messages_role")),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["comparison_tasks.id"],
            name=op.f("fk_followup_messages_comparison_id_comparison_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_followup_messages")),
    )
    op.create_index(
        op.f("ix_followup_messages_comparison_id"), "followup_messages", ["comparison_id"]
    )
    op.create_index(
        "ix_followup_messages_comparison_created",
        "followup_messages",
        ["comparison_id", "created_at"],
    )

    op.create_table(
        "report_claims",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("claim_type", sa.String(length=14), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_refs", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "claim_type IN ('fact', 'advantage', 'disadvantage', 'recommendation', 'warning')",
            name=op.f("ck_report_claims_claim_type"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_refs) = 'array'", name=op.f("ck_report_claims_source_refs_array")
        ),
        sa.CheckConstraint(
            "jsonb_array_length(source_refs) > 0",
            name=op.f("ck_report_claims_source_refs_nonempty"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name=op.f("ck_report_claims_confidence"),
        ),
        sa.CheckConstraint("display_order >= 0", name=op.f("ck_report_claims_display_order")),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["comparison_reports.id"],
            name=op.f("fk_report_claims_report_id_comparison_reports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_claims")),
    )
    op.create_index(op.f("ix_report_claims_report_id"), "report_claims", ["report_id"])

    op.create_table(
        "review_annotations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("dimension_id", sa.UUID(), nullable=False),
        sa.Column("sentiment", sa.String(length=8), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("model_run_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sentiment IN ('positive', 'neutral', 'negative')",
            name=op.f("ck_review_annotations_sentiment"),
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name=op.f("ck_review_annotations_confidence")
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["raw_reviews.id"],
            name=op.f("fk_review_annotations_review_id_raw_reviews"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dimension_id"],
            ["dimension_definitions.id"],
            name=op.f("fk_review_annotations_dimension_id_dimension_definitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_run_id"],
            ["model_runs.id"],
            name=op.f("fk_review_annotations_model_run_id_model_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_annotations")),
        sa.UniqueConstraint(
            "review_id", "dimension_id", name="uq_review_annotations_review_dimension"
        ),
    )
    op.create_index(op.f("ix_review_annotations_review_id"), "review_annotations", ["review_id"])
    op.create_index(
        op.f("ix_review_annotations_dimension_id"), "review_annotations", ["dimension_id"]
    )
    op.create_index(
        op.f("ix_review_annotations_model_run_id"), "review_annotations", ["model_run_id"]
    )


def downgrade() -> None:
    """按依赖反向移除且仅移除 T05 七张表。by AI.Coding"""
    # 注解先移除以解除对评论、维度和模型运行的引用。
    op.drop_table("review_annotations")
    op.drop_table("report_claims")
    op.drop_table("followup_messages")
    op.drop_table("comparison_reports")
    op.drop_table("analysis_metrics")
    op.drop_constraint(
        "uq_comparison_products_comparison_id_id",
        "comparison_products",
        type_="unique",
    )
    op.drop_table("raw_reviews")
    op.drop_table("model_runs")
