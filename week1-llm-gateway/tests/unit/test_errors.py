from __future__ import annotations

import pytest

from app.core.errors import ERROR_SPECS, ErrorCode, GatewayError


def test_every_error_code_has_a_spec() -> None:
    missing = [code for code in ErrorCode if code not in ERROR_SPECS]
    assert missing == []


def test_upstream_server_error_is_retryable() -> None:
    error = GatewayError(ErrorCode.UPSTREAM_SERVER_ERROR, "boom")
    assert error.http_status == 502
    assert error.retryable is True


def test_retryable_can_be_overridden() -> None:
    error = GatewayError(ErrorCode.UPSTREAM_SERVER_ERROR, "boom", retryable=False)
    assert error.retryable is False


def test_payload_shape() -> None:
    error = GatewayError(
        ErrorCode.UNKNOWN_MODEL,
        "未知模型",
        details={"model": "x"},
    )
    assert error.to_payload("req-1") == {
        "error": {
            "code": "unknown_model",
            "message": "未知模型",
            "request_id": "req-1",
            "retryable": False,
            "details": {"model": "x"},
        }
    }


@pytest.mark.parametrize(
    ("code", "status", "retryable"),
    [
        (ErrorCode.INVALID_REQUEST, 400, False),
        (ErrorCode.UNKNOWN_MODEL, 404, False),
        (ErrorCode.RATE_LIMIT_EXCEEDED, 429, False),
        (ErrorCode.UPSTREAM_RATE_LIMITED, 429, True),
        (ErrorCode.UPSTREAM_TIMEOUT, 504, True),
        (ErrorCode.INTERNAL_ERROR, 500, False),
    ],
)
def test_error_specs(code: ErrorCode, status: int, retryable: bool) -> None:
    error = GatewayError(code, "x")
    assert error.http_status == status
    assert error.retryable is retryable
