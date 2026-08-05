from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.middleware import get_trace_id
from app.api.problem_details import FieldError, ProblemDetails
from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger(component="exception_handler")


def _response(problem: ProblemDetails) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            FieldError(
                field=".".join(str(part) for part in error["loc"]),
                message=str(error["msg"]),
                error_type=str(error["type"]),
            )
            for error in exc.errors()
        ]
        return _response(
            ProblemDetails(
                title="请求参数校验失败",
                status=422,
                code="VALIDATION_ERROR",
                detail="请求包含无效参数，请根据字段错误修正后重试。",
                trace_id=get_trace_id(request),
                field_errors=fields,
            )
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _response(
            ProblemDetails(
                title=exc.title,
                status=exc.status_code,
                code=exc.code,
                detail=exc.detail,
                trace_id=get_trace_id(request),
                metadata=exc.metadata,
            )
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = "HTTP_ERROR"
        if exc.status_code == 404:
            code = "NOT_FOUND"
        elif exc.status_code == 405:
            code = "METHOD_NOT_ALLOWED"
        return _response(
            ProblemDetails(
                title="HTTP 请求失败",
                status=exc.status_code,
                code=code,
                detail=str(exc.detail),
                trace_id=get_trace_id(request),
            )
        )

    @app.exception_handler(Exception)
    async def unknown_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            trace_id=get_trace_id(request),
            exception_type=type(exc).__name__,
        )
        return _response(
            ProblemDetails(
                title="服务内部错误",
                status=500,
                code="INTERNAL_ERROR",
                detail="服务暂时无法处理请求，请稍后重试。",
                trace_id=get_trace_id(request),
            )
        )
