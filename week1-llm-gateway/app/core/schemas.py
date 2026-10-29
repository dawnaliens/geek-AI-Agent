"""统一契约：所有适配器只认这里的请求、响应与流事件。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Role
    content: str


class PromptRef(BaseModel):
    """提示词模板引用。M5 会用它去模板库里取版本并渲染。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    version: str = Field(default="latest", min_length=1)
    variables: dict[str, Any] = Field(default_factory=dict)


class ResponseFormat(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    type: Literal["text", "json_object", "json_schema"]
    name: str | None = None
    json_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    strict: bool = True

    @model_validator(mode="after")
    def _require_schema_fields(self) -> ResponseFormat:
        if self.type != "json_schema":
            return self
        if not self.name:
            raise ValueError("response_format.name is required when type=json_schema")
        if not self.json_schema:
            raise ValueError("response_format.schema is required when type=json_schema")
        return self


class ChatRequest(BaseModel):
    """对外契约。messages 与 prompt 二选一。"""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
    messages: list[Message] | None = None
    prompt: PromptRef | None = None
    stream: bool = False
    response_format: ResponseFormat | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exactly_one_input(self) -> ChatRequest:
        if (self.messages is None) == (self.prompt is None):
            raise ValueError("exactly one of 'messages' or 'prompt' must be provided")
        if self.messages is not None and not self.messages:
            raise ValueError("messages must not be empty")
        return self

    def to_canonical(self, messages: list[Message]) -> CanonicalRequest:
        """模板渲染完成后，把对外契约收敛成适配器契约。"""
        return CanonicalRequest(
            model=self.model,
            messages=messages,
            response_format=self.response_format,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=self.stream,
            metadata=self.metadata,
        )


class CanonicalRequest(BaseModel):
    """适配器契约：一定包含已渲染好的 messages，不再有 prompt。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    messages: list[Message]
    response_format: ResponseFormat | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _infer_total_tokens(cls, data: Any) -> Any:
        """上游偶尔只给分项，这里在构造前补齐总数，不修改原对象。"""
        if isinstance(data, dict) and not data.get("total_tokens"):
            input_tokens = data.get("input_tokens") or 0
            output_tokens = data.get("output_tokens") or 0
            if input_tokens or output_tokens:
                return {**data, "total_tokens": input_tokens + output_tokens}
        return data


class Latency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ttft_ms: float | None = Field(default=None, ge=0)
    total_ms: float = Field(ge=0)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    model: str
    adapter: str
    content: str
    finish_reason: str
    usage: Usage
    latency: Latency


class StreamEventType(str, Enum):
    START = "start"
    DELTA = "delta"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"


class StreamEvent(BaseModel):
    """统一流事件。适配器负责把上游的增量事件翻译成这五种。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event: StreamEventType
    data: dict[str, Any]

    @classmethod
    def start(cls, *, call_id: str, model: str, adapter: str) -> StreamEvent:
        return cls(
            event=StreamEventType.START,
            data={"id": call_id, "model": model, "adapter": adapter},
        )

    @classmethod
    def delta(cls, text: str) -> StreamEvent:
        return cls(event=StreamEventType.DELTA, data={"text": text})

    @classmethod
    def usage(cls, usage: Usage) -> StreamEvent:
        return cls(event=StreamEventType.USAGE, data=usage.model_dump())

    @classmethod
    def done(
        cls, *, finish_reason: str, usage: Usage, latency: Latency
    ) -> StreamEvent:
        return cls(
            event=StreamEventType.DONE,
            data={
                "finish_reason": finish_reason,
                "usage": usage.model_dump(),
                "latency": latency.model_dump(),
            },
        )

    @classmethod
    def error(cls, *, code: str, message: str) -> StreamEvent:
        return cls(event=StreamEventType.ERROR, data={"code": code, "message": message})
