from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config import ConfigError, load_gateway_config


def _write(path: Path, models: dict) -> Path:
    path.write_text(yaml.safe_dump({"models": models}), encoding="utf-8")
    return path


def _model(**overrides: object) -> dict:
    base = {
        "adapter": "openai_responses",
        "upstream_model": "upstream",
        "base_url": "https://api.example.com/v1",
        "api_key_env": "TEST_API_KEY",
        "rate_limit": {"capacity": 5, "refill_per_sec": 1},
    }
    base.update(overrides)
    return base


def test_loads_model_config(tmp_path: Path) -> None:
    path = _write(tmp_path / "models.yaml", {"m": _model()})
    config = load_gateway_config(path)
    model = config.models["m"]
    assert model.alias == "m"
    assert model.adapter == "openai_responses"
    assert model.timeout.connect == 5.0
    assert model.rate_limit.capacity == 5


def test_resolves_env_with_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MISSING_MODEL", raising=False)
    path = _write(
        tmp_path / "models.yaml",
        {"m": _model(upstream_model="${MISSING_MODEL:-fallback-model}")},
    )
    config = load_gateway_config(path)
    assert config.models["m"].upstream_model == "fallback-model"


def test_resolves_env_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RESOLVED_MODEL", "from-env")
    path = _write(
        tmp_path / "models.yaml",
        {"m": _model(upstream_model="${RESOLVED_MODEL}")},
    )
    config = load_gateway_config(path)
    assert config.models["m"].upstream_model == "from-env"


def test_missing_env_without_default_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("REQUIRED_MODEL", raising=False)
    path = _write(
        tmp_path / "models.yaml",
        {"m": _model(upstream_model="${REQUIRED_MODEL}")},
    )
    with pytest.raises(ConfigError, match="REQUIRED_MODEL"):
        load_gateway_config(path)


def test_invalid_adapter_fails(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "models.yaml", {"m": _model(adapter="not_a_real_adapter")}
    )
    with pytest.raises(ConfigError, match="adapter"):
        load_gateway_config(path)


def test_invalid_base_url_fails(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "models.yaml", {"m": _model(base_url="ftp://example.com")}
    )
    with pytest.raises(ConfigError, match="base_url"):
        load_gateway_config(path)


def test_base_url_trailing_slash_is_stripped(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "models.yaml",
        {"m": _model(base_url="https://api.example.com/v1/")},
    )
    config = load_gateway_config(path)
    assert config.models["m"].base_url == "https://api.example.com/v1"


def test_missing_models_key_fails(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text("foo: bar\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="models"):
        load_gateway_config(path)


def test_empty_models_fails(tmp_path: Path) -> None:
    path = _write(tmp_path / "models.yaml", {})
    with pytest.raises(ConfigError, match="至少需要一个模型"):
        load_gateway_config(path)


def test_credentials_configured_reflects_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(tmp_path / "models.yaml", {"m": _model(api_key_env="SOME_TEST_KEY")})
    config = load_gateway_config(path)
    monkeypatch.delenv("SOME_TEST_KEY", raising=False)
    assert config.models["m"].credentials_configured is False
    monkeypatch.setenv("SOME_TEST_KEY", "secret")
    assert config.models["m"].credentials_configured is True
