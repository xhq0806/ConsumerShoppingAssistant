"""DTO 受控 ORM 构造令牌。by AI.Coding"""

from __future__ import annotations

from app.core.errors import DomainConflictError

_DTO_CONSTRUCTION_TOKEN = object()


def require_dto_construction_token(token: object | None) -> None:
    """拒绝普通应用代码直接构造受 DTO 白名单保护的 ORM 实体。by AI.Coding"""
    if token is not _DTO_CONSTRUCTION_TOKEN:
        raise DomainConflictError("该持久化实体只能通过 Repository DTO 入库入口创建")


def dto_construction_token() -> object:
    """仅向模型 factory 提供模块内受保护构造令牌。by AI.Coding"""
    return _DTO_CONSTRUCTION_TOKEN
