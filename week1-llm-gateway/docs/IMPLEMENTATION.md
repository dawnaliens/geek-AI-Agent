# 实现日志

记录每一步的目标、关键决策和验证方式。按时间追加，不覆盖历史。

---

## 2026-10-29 · M1：骨架、统一契约、错误码、模型路由

### 目标

让服务能启动，并且能用 curl 看到第一个可验证的结果：模型路由表。本步不接任何真实上游。

### 本步完成

1. 项目骨架与依赖管理（`pyproject.toml`，uv）
2. 模型路由配置（`config/models.yaml`）与加载校验（`app/config.py`）
3. 统一契约（`app/core/schemas.py`）
4. 统一错误码与错误信封（`app/core/errors.py`）
5. 模型注册表与 `/v1/models` 接口
6. 统一异常出口与 request_id 中间件
7. 单元测试 + 集成测试

### 关键决策

- **契约分两层**：`ChatRequest` 是对外契约（`messages` 或 `prompt` 二选一），`CanonicalRequest` 是适配器契约（一定有渲染好的 `messages`）。模板渲染发生在两层之间，适配器永远看不到 `prompt`。
- **错误只有一个出口**：所有业务错误都抛 `GatewayError`，HTTP 状态码、是否可重试、响应结构都由 `ERROR_SPECS` 统一决定。
- **配置只存密钥的环境变量名**：`api_key_env` 存的是变量名，不是值；对外只暴露 `credentials_configured` 布尔值，不泄漏密钥，也不泄漏内部 `base_url`。
- **启动即校验**：YAML 结构、适配器名、URL、限流参数在启动时全部校验；缺少必需环境变量直接抛 `ConfigError`，不带着坏配置运行。
- **不可变模型**：配置和契约都使用 `frozen=True`，避免运行期被意外修改。

### 文件清单

| 文件 | 作用 |
|---|---|
| `pyproject.toml` | 依赖与 pytest 配置 |
| `.env.example` | 环境变量模板 |
| `config/models.yaml` | 模型别名 → 适配器/上游/超时/限流 |
| `app/config.py` | YAML 加载、`${VAR:-default}` 解析、启动校验 |
| `app/core/schemas.py` | 统一请求/响应/流事件 |
| `app/core/errors.py` | 错误码、HTTP 映射、可重试语义 |
| `app/adapters/registry.py` | 模型别名解析 |
| `app/api/routes_models.py` | `GET /v1/models`、`GET /v1/models/{id}` |
| `app/api/error_handlers.py` | 统一异常响应 |
| `app/main.py` | 应用工厂、request_id 中间件 |
| `tests/` | 契约、错误码、配置、模型接口测试 |

### 如何运行

```bash
cd week1-llm-gateway
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 如何验证

```bash
uv run pytest -q
```

```bash
curl -s http://127.0.0.1:8000/v1/models | jq
curl -s http://127.0.0.1:8000/v1/models/does-not-exist | jq
```

预期：前者返回两个模型的统一描述；后者返回 `404` + `error.code = "unknown_model"`，且 `request_id` 与响应头一致。

### 本步未做

- 没有 `POST /v1/chat`
- 没有真实/模拟上游适配器
- 没有提示词模板、限流、重试、观测
- 没有网关自身鉴权（`GATEWAY_API_KEY` 已预留但未启用）

### 下一步

M2：实现 `BaseAdapter` 与两个非流式适配器，先用 `mock_upstream` 打通，再接真实 OpenAI Responses / Anthropic Messages。
