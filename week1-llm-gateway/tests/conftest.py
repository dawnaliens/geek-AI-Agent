from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def model_config_path(tmp_path: Path) -> Path:
    """一份与真实路由表结构一致、但完全本地可控的配置。"""
    path = tmp_path / "models.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "model-alpha": {
                        "adapter": "openai_responses",
                        "upstream_model": "upstream-alpha",
                        "base_url": "https://api.example.com/v1",
                        "api_key_env": "TEST_KEY_ALPHA",
                        "timeout": {"connect": 2, "read": 30},
                        "rate_limit": {"capacity": 5, "refill_per_sec": 1},
                    },
                    "model-beta": {
                        "adapter": "anthropic_messages",
                        "upstream_model": "upstream-beta",
                        "base_url": "https://api.example.com",
                        "api_key_env": "TEST_KEY_BETA",
                        "rate_limit": {"capacity": 10, "refill_per_sec": 2},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def client(model_config_path: Path) -> Iterator[TestClient]:
    settings = Settings(config_path=model_config_path, _env_file=None)
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
