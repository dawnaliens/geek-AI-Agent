"""模型别名 -> 模型配置的路由表。M2 会在这里挂上适配器实例。"""

from __future__ import annotations

from app.config import GatewayConfig, ModelConfig
from app.core.errors import ErrorCode, GatewayError


class ModelRegistry:
    """启动时冻结路由表；解析失败统一抛 unknown_model。"""

    def __init__(self, config: GatewayConfig) -> None:
        self._models: dict[str, ModelConfig] = dict(config.models)

    def resolve(self, alias: str) -> ModelConfig:
        model = self._models.get(alias)
        if model is None:
            raise GatewayError(
                ErrorCode.UNKNOWN_MODEL,
                f"未知模型: {alias}",
                details={"model": alias, "available": sorted(self._models)},
            )
        return model

    def list(self) -> list[ModelConfig]:
        return sorted(self._models.values(), key=lambda model: model.alias)
