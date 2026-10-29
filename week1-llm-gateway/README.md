# week1-llm-gateway

LLM 统一调用服务：一个入口，按 `model` 路由到不同协议的适配器，并提供流式、结构化输出、提示词版本管理、可观测性与基础韧性。

## 进度

- [x] M1 骨架、统一契约、错误码、模型路由
- [ ] M2 两个非流式适配器
- [ ] M3 流式
- [ ] M4 结构化输出
- [ ] M5 提示词版本管理
- [ ] M6 可观测性
- [ ] M7 重试与限流
- [ ] M8 验证脚本与 README 补全

## 快速开始

```bash
cd week1-llm-gateway
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

M1 不访问上游，不需要 API key。后续接真实上游时，复制 `.env.example` 为 `.env` 并填入密钥。

## 当前可用接口

```bash
curl -s http://127.0.0.1:8000/v1/models | jq
curl -s http://127.0.0.1:8000/v1/models/deepseek-v4-pro | jq
curl -s http://127.0.0.1:8000/v1/models/does-not-exist | jq
```

未知模型会返回统一错误结构：

```json
{
  "error": {
    "code": "unknown_model",
    "message": "未知模型: does-not-exist",
    "request_id": "req_...",
    "retryable": false,
    "details": {
      "model": "does-not-exist",
      "available": ["deepseek-v4-flash", "deepseek-v4-pro"]
    }
  }
}
```

## 测试

```bash
uv run pytest -q
```

## 目录

```
app/api/            接入层：/v1/models
app/core/           统一契约、错误码
app/adapters/       模型注册表（后续放协议适配器）
app/prompts/        提示词模板（M5）
app/observability/  调用记录（M6）
app/storage/        存储接口
config/             模型路由表
mock_upstream/      本地模拟上游（M2）
scripts/            验证脚本（M8）
tests/              单元测试与集成测试
reports/            验证报告产物
docs/               实现日志
```

实现细节与决策记录见 [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md)。
