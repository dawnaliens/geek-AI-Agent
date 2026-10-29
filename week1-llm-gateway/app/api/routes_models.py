"""模型路由查询接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from app.adapters.registry import ModelRegistry
from app.config import ModelConfig

router = APIRouter(prefix="/v1/models", tags=["models"])


class RateLimitInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    capacity: int
    refill_per_sec: float


class TimeoutInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    connect: float
    read: float


class ModelInfo(BaseModel):
    """对外的模型描述。刻意不暴露 base_url，避免泄漏内部端点。"""

    model_config = ConfigDict(frozen=True)

    id: str
    object: Literal["model"] = "model"
    adapter: str
    upstream_model: str
    credentials_configured: bool
    rate_limit: RateLimitInfo
    timeout: TimeoutInfo


class ModelListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    object: Literal["list"] = "list"
    data: list[ModelInfo]


def _to_model_info(model: ModelConfig) -> ModelInfo:
    return ModelInfo(
        id=model.alias,
        adapter=model.adapter,
        upstream_model=model.upstream_model,
        credentials_configured=model.credentials_configured,
        rate_limit=RateLimitInfo(
            capacity=model.rate_limit.capacity,
            refill_per_sec=model.rate_limit.refill_per_sec,
        ),
        timeout=TimeoutInfo(connect=model.timeout.connect, read=model.timeout.read),
    )


@router.get("", response_model=ModelListResponse)
def list_models(request: Request) -> ModelListResponse:
    registry: ModelRegistry = request.app.state.registry
    return ModelListResponse(data=[_to_model_info(model) for model in registry.list()])


@router.get("/{model_id}", response_model=ModelInfo)
def get_model(model_id: str, request: Request) -> ModelInfo:
    registry: ModelRegistry = request.app.state.registry
    return _to_model_info(registry.resolve(model_id))
