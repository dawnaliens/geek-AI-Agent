"""统一异常出口：所有错误都变成同一种 JSON 结构。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import ErrorCode, GatewayError

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """只保留可安全序列化的字段，避免把异常对象带进响应。"""
    return [
        {
            "loc": [str(part) for part in error.get("loc", ())],
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        }
        for error in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GatewayError)
    async def _handle_gateway_error(request: Request, exc: GatewayError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=exc.to_payload(_request_id(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error = GatewayError(
            ErrorCode.INVALID_REQUEST,
            "请求参数不合法",
            details={"errors": _validation_errors(exc)},
        )
        return JSONResponse(
            status_code=error.http_status,
            content=error.to_payload(_request_id(request)),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未捕获异常 request_id=%s", _request_id(request))
        error = GatewayError(ErrorCode.INTERNAL_ERROR, "服务内部错误")
        return JSONResponse(
            status_code=error.http_status,
            content=error.to_payload(_request_id(request)),
        )
