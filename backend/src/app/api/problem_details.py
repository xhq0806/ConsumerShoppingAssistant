from typing import Any

from pydantic import BaseModel, Field


class FieldError(BaseModel):
    field: str
    message: str
    error_type: str


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    trace_id: str
    field_errors: list[FieldError] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
