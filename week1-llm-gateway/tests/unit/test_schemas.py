from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.schemas import (
    ChatRequest,
    Latency,
    Message,
    ResponseFormat,
    Role,
    StreamEvent,
    StreamEventType,
    Usage,
)


def _messages() -> list[Message]:
    return [Message(role=Role.USER, content="hello")]


def test_messages_input_is_valid() -> None:
    request = ChatRequest(model="m", messages=_messages())
    assert request.prompt is None
    assert request.messages == _messages()


def test_prompt_input_is_valid() -> None:
    request = ChatRequest.model_validate(
        {"model": "m", "prompt": {"name": "greet", "variables": {"x": 1}}}
    )
    assert request.messages is None
    assert request.prompt is not None
    assert request.prompt.version == "latest"


@pytest.mark.parametrize(
    "payload",
    [
        {"model": "m"},
        {"model": "m", "messages": _messages(), "prompt": {"name": "p"}},
    ],
)
def test_exactly_one_input_is_required(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(payload)


def test_empty_messages_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(model="m", messages=[])


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {"model": "m", "messages": _messages(), "typo": True}
        )


def test_json_schema_requires_name_and_schema() -> None:
    with pytest.raises(ValidationError):
        ResponseFormat.model_validate(
            {"type": "json_schema", "schema": {"type": "object"}}
        )
    with pytest.raises(ValidationError):
        ResponseFormat.model_validate({"type": "json_schema", "name": "out"})


def test_response_format_accepts_schema_alias() -> None:
    fmt = ResponseFormat.model_validate(
        {"type": "json_schema", "name": "out", "schema": {"type": "object"}}
    )
    assert fmt.json_schema == {"type": "object"}
    assert fmt.strict is True


def test_to_canonical_preserves_settings() -> None:
    request = ChatRequest(
        model="m",
        prompt={"name": "greet"},
        stream=True,
        temperature=0.3,
        max_tokens=64,
        metadata={"trace": "abc"},
    )
    canonical = request.to_canonical(_messages())
    assert canonical.messages == _messages()
    assert canonical.stream is True
    assert canonical.temperature == 0.3
    assert canonical.max_tokens == 64
    assert canonical.metadata == {"trace": "abc"}


def test_usage_infers_total_tokens() -> None:
    usage = Usage(input_tokens=3, output_tokens=4)
    assert usage.total_tokens == 7


def test_usage_rejects_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        Usage(input_tokens=-1, output_tokens=1)


def test_stream_event_helpers() -> None:
    delta = StreamEvent.delta("hi")
    assert delta.event is StreamEventType.DELTA
    assert delta.data == {"text": "hi"}

    done = StreamEvent.done(
        finish_reason="stop",
        usage=Usage(input_tokens=1, output_tokens=2),
        latency=Latency(total_ms=12.5),
    )
    assert done.event is StreamEventType.DONE
    assert done.data["finish_reason"] == "stop"
    assert done.data["latency"]["total_ms"] == 12.5
