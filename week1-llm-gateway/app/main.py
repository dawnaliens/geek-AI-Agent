"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request

from app.adapters.registry import ModelRegistry
from app.api.error_handlers import register_exception_handlers
from app.api.routes_models import router as models_router
from app.config import Settings, get_settings, load_gateway_config

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings.log_level)

    gateway_config = load_gateway_config(settings.config_path)
    app = FastAPI(title="LLM Gateway", version="0.1.0")
    app.state.registry = ModelRegistry(gateway_config)
    app.state.settings = settings

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(app)
    app.include_router(models_router)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    logger.info("LLM Gateway 已加载 %d 个模型", len(gateway_config.models))
    return app


app = create_app()
