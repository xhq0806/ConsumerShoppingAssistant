"""集中导入全部公共 ORM 模型以注册 metadata。by AI.Coding"""

from app.infrastructure.db.models.brand import BrandProfile, BrandSource
from app.infrastructure.db.models.comparison import ComparisonProduct, ComparisonTask, TaskEvent
from app.infrastructure.db.models.dimension import DimensionDefinition, TaskDimension
from app.infrastructure.db.models.metric import AnalysisMetric
from app.infrastructure.db.models.model_run import ModelRun
from app.infrastructure.db.models.product import ProductSku, ProductSnapshot
from app.infrastructure.db.models.report import ComparisonReport, FollowupMessage, ReportClaim
from app.infrastructure.db.models.review import RawReview, ReviewAnnotation

__all__ = [
    "AnalysisMetric",
    "BrandProfile",
    "BrandSource",
    "ComparisonProduct",
    "ComparisonReport",
    "ComparisonTask",
    "DimensionDefinition",
    "FollowupMessage",
    "ModelRun",
    "ProductSku",
    "ProductSnapshot",
    "RawReview",
    "ReportClaim",
    "ReviewAnnotation",
    "TaskDimension",
    "TaskEvent",
]
