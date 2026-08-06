"""M1-B 对比业务应用用例与显式响应视图。by AI.Coding"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    DomainConflictError,
    ProviderError,
    ResourceNotFoundError,
)
from app.domain.comparisons import (
    ComparabilityWarning,
    ComparableProduct,
    ComparisonStatus,
    TaskEventType,
    TaskStage,
    create_request_fingerprint,
    idempotency_key_hash,
    validate_basic_comparability,
    validate_candidate_count,
    validate_confirmation_set,
    validate_unique_candidates,
)
from app.domain.products import ProductParseStatus
from app.infrastructure.db.comparison_repository import ComparisonRepository
from app.infrastructure.db.models import (
    ComparisonProduct,
    ComparisonTask,
    ProductSnapshot,
)
from app.infrastructure.db.transaction import UnitOfWork
from app.providers.commerce.base import CommerceDataProvider
from app.providers.commerce.dto import NormalizedProductUrl, ProductProviderResult, ProductRequest


@dataclass(frozen=True)
class CreateComparisonCommand:
    """承载创建对比草稿所需的框架无关输入。by AI.Coding"""

    product_urls: tuple[str, ...]
    review_window_days: int


@dataclass(frozen=True)
class ProductConfirmation:
    """承载单个候选商品的 SKU 确认选择。by AI.Coding"""

    comparison_product_id: UUID
    selected_sku_id: UUID | None


@dataclass(frozen=True)
class ConfirmProductsCommand:
    """承载一次覆盖所有候选的确认输入。by AI.Coding"""

    products: tuple[ProductConfirmation, ...]


@dataclass(frozen=True)
class SkuView:
    """定义 API 可安全暴露的 SKU 白名单视图。by AI.Coding"""

    id: UUID
    external_sku_id: str
    name: str
    attributes: dict[str, str]
    price: Decimal | None
    selectable: bool


@dataclass(frozen=True)
class SnapshotView:
    """定义 API 可安全暴露的最新商品快照视图。by AI.Coding"""

    id: UUID
    title: str
    image_url: str | None
    brand: str | None
    category: str | None
    shop_name: str | None
    price: Decimal | None
    currency: str
    specifications: dict[str, str]
    after_sales: list[str]
    source_provider: str
    source_id: str
    captured_at: datetime


@dataclass(frozen=True)
class ProductView:
    """定义 API 可安全暴露的候选商品聚合视图。by AI.Coding"""

    id: UUID
    position: int
    platform: str
    external_product_id: str
    parse_status: str
    selected_sku_id: UUID | None
    latest_snapshot: SnapshotView | None
    skus: tuple[SkuView, ...]


@dataclass(frozen=True)
class EventView:
    """定义 API 可安全暴露的脱敏事件视图。by AI.Coding"""

    id: UUID
    stage: str
    event_type: str
    progress: int | None
    message: str | None
    details: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class ComparisonView:
    """定义创建摘要和详情端点共享的对比任务视图。by AI.Coding"""

    id: UUID
    status: str
    review_window_days: int
    progress: int
    products: tuple[ProductView, ...]
    events: tuple[EventView, ...]
    warnings: tuple[ComparabilityWarning, ...] = ()


class ComparisonApplicationService:
    """编排 M1-B 草稿、解析、详情与确认的短事务流程。by AI.Coding"""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        commerce_provider: CommerceDataProvider,
    ) -> None:
        """注入可替换的事务工厂与受限 Commerce Provider。by AI.Coding"""
        self._uow_factory = uow_factory
        self._commerce_provider = commerce_provider

    async def create_comparison(
        self,
        command: CreateComparisonCommand,
        *,
        idempotency_key: str | None,
    ) -> ComparisonView:
        """在 URL 规范化后原子创建草稿或返回幂等重放结果。by AI.Coding"""
        normalized_urls = await self._normalize_urls(command.product_urls)
        fingerprint = create_request_fingerprint(normalized_urls, command.review_window_days)
        key_hash = None if idempotency_key is None else idempotency_key_hash(idempotency_key)
        try:
            async with self._uow_factory() as uow:
                repository = self._repository(uow)
                if key_hash is not None:
                    existing = await repository.get_by_idempotency_hash(key_hash)
                    if existing is not None:
                        return self._replayed_or_conflict(existing, fingerprint)
                task = ComparisonTask(
                    review_window_days=command.review_window_days,
                    idempotency_key_hash=key_hash,
                    create_request_fingerprint=None if key_hash is None else fingerprint,
                )
                session = self._session(uow)
                session.add(task)
                await session.flush()
                for position, normalized_url in enumerate(normalized_urls):
                    repository.add_candidate_from_dto(
                        comparison_id=task.id, position=position, product_url=normalized_url
                    )
                repository.add_event(
                    comparison_id=task.id,
                    stage=TaskStage.CREATED,
                    event_type=TaskEventType.STATUS_CHANGED,
                    progress=0,
                    message="对比草稿已创建。",
                    details={"status": ComparisonStatus.DRAFT.value},
                )
                await session.flush()
                loaded = await repository.get_detail(task.id)
                assert loaded is not None
                return self._to_view(loaded)
        except IntegrityError:
            # 唯一索引只在同 key 并发创建时被视为可恢复的幂等竞态。
            if key_hash is None:
                raise
            return await self._read_idempotency_winner(key_hash, fingerprint)

    async def parse_products(self, comparison_id: UUID) -> ComparisonView:
        """分段提交解析状态，在事务外调用 Fixture 并原子保存全部结果。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.DRAFT:
                raise DomainConflictError("当前任务状态不允许启动商品解析")
            repository.transition(task, ComparisonStatus.PARSING)
            for product in task.products:
                product.parse_status = ProductParseStatus.PARSING
            repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.PRODUCT_PARSING,
                event_type=TaskEventType.STATUS_CHANGED,
                progress=0,
                message="商品解析已启动。",
                details={"status": ComparisonStatus.PARSING.value},
            )

        results: list[ProductProviderResult] = []
        failed_product_id: UUID | None = None
        try:
            # 外部调用不位于 UoW 内，避免 Fixture 替换为真实适配器时长期占用写锁。
            for product in sorted(task.products, key=lambda item: item.position):
                failed_product_id = product.id
                normalized_url = NormalizedProductUrl(
                    canonical_url=product.canonical_url,
                    platform=product.platform.value,
                    host=product.canonical_url.split("/")[2],
                    external_product_id=product.external_product_id,
                    safe_url_fingerprint=product.safe_url_fingerprint,
                )
                results.append(
                    await self._commerce_provider.fetch_product(
                        ProductRequest(product_url=normalized_url)
                    )
                )
        except ProviderError as error:
            await self._mark_parse_failed(comparison_id, failed_product_id, error)
            metadata = dict(error.metadata)
            metadata["comparison_id"] = str(comparison_id)
            raise type(error)(error.detail, metadata=metadata) from error

        async with self._uow_factory() as uow:
            repository = self._repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.PARSING:
                raise DomainConflictError("任务解析状态已发生变化")
            products = sorted(task.products, key=lambda item: item.position)
            for product, result in zip(products, results, strict=True):
                repository.add_snapshot_from_dto(
                    comparison_product_id=product.id, product=result.product
                )
                for sku in result.skus:
                    repository.add_sku_from_dto(comparison_product_id=product.id, sku=sku)
                product.parse_status = (
                    ProductParseStatus.NEEDS_CONFIRMATION
                    if result.skus
                    else ProductParseStatus.PARSED
                )
            repository.transition(task, ComparisonStatus.AWAITING_PRODUCT_CONFIRMATION)
            task.progress = 100
            repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.PRODUCT_PARSING,
                event_type=TaskEventType.STATUS_CHANGED,
                progress=100,
                message="商品解析完成，等待商品确认。",
                details={"status": ComparisonStatus.AWAITING_PRODUCT_CONFIRMATION.value},
            )
            session = self._session(uow)
            await session.flush()
            task_id = task.id
            # 清除本会话先前加载的空关系缓存，再显式读取刚原子写入的快照和 SKU。
            session.expire_all()
            loaded = await repository.get_detail(task_id)
            assert loaded is not None
            return self._to_view(loaded)

    async def get_comparison(self, comparison_id: UUID) -> ComparisonView:
        """读取非删除任务的稳定排序聚合详情。by AI.Coding"""
        async with self._uow_factory() as uow:
            task = await self._required_task(self._repository(uow), comparison_id)
            return self._to_view(task)

    async def confirm_products(
        self, comparison_id: UUID, command: ConfirmProductsCommand
    ) -> ComparisonView:
        """原子校验所有 SKU 选择和类别可比性并推进任务。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            submitted_ids = [product.comparison_product_id for product in command.products]
            if task.status is not ComparisonStatus.AWAITING_PRODUCT_CONFIRMATION:
                if self._matches_current_selection(task, command):
                    return self._to_view(task)
                raise DomainConflictError("当前任务状态不允许确认商品")
            validate_confirmation_set({product.id for product in task.products}, submitted_ids)
            selections = {
                product.comparison_product_id: product.selected_sku_id
                for product in command.products
            }
            self._validate_sku_selections(task.products, selections)
            warnings = validate_basic_comparability(
                [
                    ComparableProduct(product.id, self._latest_snapshot(product).category)
                    for product in task.products
                ]
            )
            for product in task.products:
                product.selected_sku_id = selections[product.id]
            repository.transition(task, ComparisonStatus.AWAITING_DIMENSION_CONFIRMATION)
            repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.PRODUCT_CONFIRMATION,
                event_type=TaskEventType.STATUS_CHANGED,
                progress=100,
                message="商品与 SKU 已确认。",
                details={"status": ComparisonStatus.AWAITING_DIMENSION_CONFIRMATION.value},
            )
            for warning in warnings:
                repository.add_event(
                    comparison_id=task.id,
                    stage=TaskStage.PRODUCT_CONFIRMATION,
                    event_type=TaskEventType.WARNING,
                    progress=100,
                    message=warning.message,
                    details={"code": warning.code},
                )
            session = self._session(uow)
            await session.flush()
            task_id = task.id
            # 清除本会话先前加载的空关系缓存，再显式读取刚原子写入的快照和 SKU。
            session.expire_all()
            loaded = await repository.get_detail(task_id)
            assert loaded is not None
            return self._to_view(loaded, warnings=warnings)

    async def _normalize_urls(
        self, product_urls: Sequence[str]
    ) -> tuple[NormalizedProductUrl, ...]:
        """在事务外按输入顺序完成安全 URL 规范化与重复校验。by AI.Coding"""
        validate_candidate_count(list(product_urls))
        normalized_urls = tuple(
            [
                await self._commerce_provider.normalize_url(product_url)
                for product_url in product_urls
            ]
        )
        # 双重标识均校验，避免 URL 指纹或平台商品 ID 单侧变化绕过重复候选门禁。
        validate_unique_candidates(
            list(normalized_urls),
            key=lambda product: f"{product.platform}:{product.external_product_id}",
        )
        validate_unique_candidates(
            list(normalized_urls), key=lambda product: product.safe_url_fingerprint
        )
        return normalized_urls

    async def _read_idempotency_winner(self, key_hash: str, fingerprint: str) -> ComparisonView:
        """在唯一索引裁决并回滚后读取并发创建获胜任务。by AI.Coding"""
        async with self._uow_factory() as uow:
            task = await self._repository(uow).get_by_idempotency_hash(key_hash)
            if task is None:
                raise DomainConflictError("并发创建未能读取到幂等任务")
            return self._replayed_or_conflict(task, fingerprint)

    async def _mark_parse_failed(
        self, comparison_id: UUID, failed_product_id: UUID | None, error: ProviderError
    ) -> None:
        """在独立事务记录受控解析失败且不保存任何临时 Provider 结果。by AI.Coding"""
        async with self._uow_factory() as uow:
            repository = self._repository(uow)
            task = await self._required_task(repository, comparison_id, for_update=True)
            if task.status is not ComparisonStatus.PARSING:
                return
            for product in task.products:
                product.parse_status = (
                    ProductParseStatus.FAILED
                    if product.id == failed_product_id
                    else ProductParseStatus.PENDING
                )
            repository.transition(task, ComparisonStatus.FAILED)
            task.error_code = error.code
            task.error_message = "商品解析失败。"
            repository.add_event(
                comparison_id=task.id,
                stage=TaskStage.PRODUCT_PARSING,
                event_type=TaskEventType.ERROR,
                progress=0,
                message="商品解析失败。",
                details={"code": error.code},
            )

    @staticmethod
    def _session(uow: UnitOfWork) -> AsyncSession:
        """取得已进入上下文的异步会话以执行 flush。by AI.Coding"""
        # 保持 session 可空声明的类型安全，同时不绕过 UoW 的提交与回滚边界。
        assert uow.session is not None
        return uow.session

    @staticmethod
    def _repository(uow: UnitOfWork) -> ComparisonRepository:
        """从已进入上下文的 UoW 创建不提交事务的任务仓储。by AI.Coding"""
        # UnitOfWork 契约保证 __aenter__ 后 session 存在，断言防止静态类型掩盖生命周期错误。
        assert uow.session is not None
        return ComparisonRepository(uow.session)

    async def _required_task(
        self, repository: ComparisonRepository, comparison_id: UUID, *, for_update: bool = False
    ) -> ComparisonTask:
        """读取存在且非删除的任务，否则抛出统一 404 领域错误。by AI.Coding"""
        task = await repository.get_detail(comparison_id, for_update=for_update)
        if task is None or task.status is ComparisonStatus.DELETED:
            raise ResourceNotFoundError("未找到对应的对比任务。")
        return task

    @staticmethod
    def _replayed_or_conflict(task: ComparisonTask, fingerprint: str) -> ComparisonView:
        """按已持久化请求指纹区分幂等重放与冲突。by AI.Coding"""
        if task.create_request_fingerprint != fingerprint:
            raise DomainConflictError("幂等键已绑定不同的创建请求")
        return ComparisonApplicationService._to_view(task)

    @staticmethod
    def _latest_snapshot(product: ComparisonProduct) -> ProductSnapshot:
        """取得候选的最新快照，并拒绝不完整解析状态。by AI.Coding"""
        if not product.snapshots:
            raise DomainConflictError("候选商品尚未具有完整商品快照")
        return max(product.snapshots, key=lambda snapshot: snapshot.captured_at)

    def _validate_sku_selections(
        self, products: Sequence[ComparisonProduct], selections: dict[UUID, UUID | None]
    ) -> None:
        """校验每个商品的 SKU 存在、归属和可选性。by AI.Coding"""
        for product in products:
            selected_sku_id = selections[product.id]
            if product.parse_status not in {
                ProductParseStatus.PARSED,
                ProductParseStatus.NEEDS_CONFIRMATION,
            }:
                raise DomainConflictError("候选商品尚未解析成功")
            self._latest_snapshot(product)
            if not product.skus and selected_sku_id is not None:
                raise DomainConflictError("无 SKU 商品必须提交空选择")
            if product.skus and selected_sku_id is None:
                raise DomainConflictError("有 SKU 商品必须明确选择一个 SKU")
            if selected_sku_id is not None:
                selected_sku = next(
                    (sku for sku in product.skus if sku.id == selected_sku_id), None
                )
                if selected_sku is None or not selected_sku.selectable:
                    raise DomainConflictError("所选 SKU 不存在、不属于当前商品或不可选")

    @staticmethod
    def _matches_current_selection(task: ComparisonTask, command: ConfirmProductsCommand) -> bool:
        """判断终态重复确认是否与当前全部选择完全一致。by AI.Coding"""
        if len(command.products) != len(task.products):
            return False
        submitted = {
            product.comparison_product_id: product.selected_sku_id for product in command.products
        }
        return len(submitted) == len(command.products) and all(
            submitted.get(product.id) == product.selected_sku_id for product in task.products
        )

    @staticmethod
    def _to_view(
        task: ComparisonTask, *, warnings: Sequence[ComparabilityWarning] = ()
    ) -> ComparisonView:
        """用明确白名单将 ORM 聚合转换为稳定的对外视图。by AI.Coding"""
        # 仅暴露安全字段，刻意排除 canonical URL、原始请求、错误堆栈和 Provider payload。
        products = tuple(
            ComparisonApplicationService._product_to_view(product)
            for product in sorted(task.products, key=lambda item: item.position)
        )
        events = tuple(
            EventView(
                id=event.id,
                stage=event.stage.value,
                event_type=event.event_type.value,
                progress=event.progress,
                message=event.message,
                details=dict(event.details),
                created_at=event.created_at,
            )
            for event in sorted(task.events, key=lambda item: item.created_at)
        )
        return ComparisonView(
            id=task.id,
            status=task.status.value,
            review_window_days=task.review_window_days,
            progress=task.progress,
            products=products,
            events=events,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _product_to_view(product: ComparisonProduct) -> ProductView:
        """映射单个候选和其最新快照、SKU 到安全视图。by AI.Coding"""
        snapshot = (
            max(product.snapshots, key=lambda item: item.captured_at) if product.snapshots else None
        )
        snapshot_view = None
        if snapshot is not None:
            snapshot_view = SnapshotView(
                id=snapshot.id,
                title=snapshot.title,
                image_url=snapshot.image_url,
                brand=snapshot.brand,
                category=snapshot.category,
                shop_name=snapshot.shop_name,
                price=snapshot.price,
                currency=snapshot.currency,
                specifications=dict(snapshot.specifications),
                after_sales=list(snapshot.after_sales),
                source_provider=snapshot.source["provider"],
                source_id=snapshot.source["source_id"],
                captured_at=snapshot.captured_at,
            )
        return ProductView(
            id=product.id,
            position=product.position,
            platform=product.platform.value,
            external_product_id=product.external_product_id,
            parse_status=product.parse_status.value,
            selected_sku_id=product.selected_sku_id,
            latest_snapshot=snapshot_view,
            skus=tuple(
                SkuView(
                    id=sku.id,
                    external_sku_id=sku.external_sku_id,
                    name=sku.name,
                    attributes=dict(sku.attributes),
                    price=sku.price,
                    selectable=sku.selectable,
                )
                for sku in product.skus
            ),
        )
