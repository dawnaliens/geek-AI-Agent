"""统一错误码与错误信封。所有对外错误都从这里出口。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    UNKNOWN_MODEL = "unknown_model"
    PROMPT_NOT_FOUND = "prompt_not_found"
    PROMPT_VARIABLE_MISSING = "prompt_variable_missing"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UPSTREAM_AUTH_ERROR = "upstream_auth_error"
    UPSTREAM_BAD_REQUEST = "upstream_bad_request"
    UPSTREAM_RATE_LIMITED = "upstream_rate_limited"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_SERVER_ERROR = "upstream_server_error"
    UPSTREAM_STREAM_INTERRUPTED = "upstream_stream_interrupted"
    STRUCTURED_OUTPUT_INVALID = "structured_output_invalid"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class ErrorSpec:
    http_status: int
    retryable: bool


ERROR_SPECS: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.INVALID_REQUEST: ErrorSpec(400, False),
    ErrorCode.UNKNOWN_MODEL: ErrorSpec(404, False),
    ErrorCode.PROMPT_NOT_FOUND: ErrorSpec(404, False),
    ErrorCode.PROMPT_VARIABLE_MISSING: ErrorSpec(400, False),
    ErrorCode.RATE_LIMIT_EXCEEDED: ErrorSpec(429, False),
    ErrorCode.UPSTREAM_AUTH_ERROR: ErrorSpec(502, False),
    ErrorCode.UPSTREAM_BAD_REQUEST: ErrorSpec(502, False),
    ErrorCode.UPSTREAM_RATE_LIMITED: ErrorSpec(429, True),
    ErrorCode.UPSTREAM_TIMEOUT: ErrorSpec(504, True),
    ErrorCode.UPSTREAM_SERVER_ERROR: ErrorSpec(502, True),
    ErrorCode.UPSTREAM_STREAM_INTERRUPTED: ErrorSpec(502, False),
    ErrorCode.STRUCTURED_OUTPUT_INVALID: ErrorSpec(502, False),
    ErrorCode.CONFIGURATION_ERROR: ErrorSpec(500, False),
    ErrorCode.INTERNAL_ERROR: ErrorSpec(500, False),
}


class GatewayError(Exception):
    """业务错误的唯一出口，携带错误码与可重试语义。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self._retryable_override = retryable

    @property
    def http_status(self) -> int:
        return ERROR_SPECS[self.code].http_status

    @property
    def retryable(self) -> bool:
        spec = ERROR_SPECS[self.code]
        return spec.retryable if self._retryable_override is None else self._retryable_override

    def to_payload(self, request_id: str | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "request_id": request_id,
                "retryable": self.retryable,
                "details": self.details,
            }
        }
