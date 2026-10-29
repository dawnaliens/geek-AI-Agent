"""配置加载：环境变量 + YAML 模型路由表。"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "models.yaml"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

# pydantic-settings 只读取自己声明的字段，不会把 .env 写回 os.environ；
# 上游密钥和 ${VAR} 占位符都依赖 os.environ，所以这里显式加载一次。
load_dotenv(dotenv_path=DEFAULT_ENV_FILE, override=False)

AdapterName = Literal["openai_responses", "anthropic_messages"]

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class ConfigError(RuntimeError):
    """配置不合法，启动阶段直接失败。"""


class TimeoutConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    connect: float = Field(default=5.0, gt=0)
    read: float = Field(default=120.0, gt=0)


class RateLimitConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capacity: int = Field(gt=0)
    refill_per_sec: float = Field(gt=0)


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    alias: str
    adapter: AdapterName
    upstream_model: str
    base_url: str
    api_key_env: str
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    rate_limit: RateLimitConfig

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        return value.rstrip("/")

    @field_validator("api_key_env")
    @classmethod
    def _validate_api_key_env(cls, value: str) -> str:
        if not value.isidentifier():
            raise ValueError("api_key_env 必须是合法的环境变量名")
        return value

    @property
    def credentials_configured(self) -> bool:
        """只报告是否配置，绝不返回密钥本身。"""
        return bool(os.getenv(self.api_key_env))


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    models: dict[str, ModelConfig]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_prefix="GATEWAY_",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    api_key: str | None = None
    log_level: str = "INFO"
    config_path: Path = DEFAULT_CONFIG_PATH


def _resolve_env(value: str) -> str:
    """替换 ${VAR} 与 ${VAR:-default}；缺少且无默认值时抛 ConfigError。"""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        actual = os.getenv(name)
        if actual is not None:
            return actual
        if default is not None:
            return default
        raise ConfigError(f"缺少必需的环境变量: {name}")

    return _ENV_PATTERN.sub(replace, value)


def _resolve_tree(node: Any) -> Any:
    """递归解析配置树里的环境变量占位符，返回新对象，不修改入参。"""
    if isinstance(node, str):
        return _resolve_env(node)
    if isinstance(node, list):
        return [_resolve_tree(item) for item in node]
    if isinstance(node, dict):
        return {key: _resolve_tree(value) for key, value in node.items()}
    return node


def load_gateway_config(path: Path | str = DEFAULT_CONFIG_PATH) -> GatewayConfig:
    config_path = Path(path)
    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"模型配置文件不存在: {config_path}") from exc

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"模型配置不是合法 YAML: {config_path}: {exc}") from exc

    if not isinstance(raw, dict) or not isinstance(raw.get("models"), dict):
        raise ConfigError(f"模型配置缺少顶层 'models' 映射: {config_path}")

    resolved_models = _resolve_tree(raw["models"])
    models: dict[str, ModelConfig] = {}
    for alias, entry in resolved_models.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"模型 '{alias}' 的配置必须是对象")
        try:
            models[alias] = ModelConfig(alias=alias, **entry)
        except (ValidationError, TypeError) as exc:
            raise ConfigError(f"模型 '{alias}' 的配置不合法: {exc}") from exc

    if not models:
        raise ConfigError("模型配置为空，至少需要一个模型")

    return GatewayConfig(models=models)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
