from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_models_returns_registry(client: TestClient) -> None:
    response = client.get("/v1/models")
    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "list"
    assert [item["id"] for item in payload["data"]] == ["model-alpha", "model-beta"]

    alpha, beta = payload["data"]
    assert alpha["adapter"] == "openai_responses"
    assert alpha["upstream_model"] == "upstream-alpha"
    assert alpha["credentials_configured"] is False
    assert alpha["rate_limit"] == {"capacity": 5, "refill_per_sec": 1.0}
    assert alpha["timeout"] == {"connect": 2.0, "read": 30.0}

    assert beta["adapter"] == "anthropic_messages"
    assert beta["timeout"] == {"connect": 5.0, "read": 120.0}


def test_get_single_model(client: TestClient) -> None:
    response = client.get("/v1/models/model-beta")
    assert response.status_code == 200
    assert response.json()["id"] == "model-beta"


def test_unknown_model_returns_unified_error(client: TestClient) -> None:
    response = client.get("/v1/models/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "unknown_model"
    assert body["error"]["retryable"] is False
    assert body["error"]["details"] == {
        "model": "does-not-exist",
        "available": ["model-alpha", "model-beta"],
    }
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_request_id_is_generated_and_returned(client: TestClient) -> None:
    response = client.get("/v1/models")
    request_id = response.headers["X-Request-ID"]
    assert request_id.startswith("req_")
    assert response.json()["data"]


def test_request_id_is_preserved(client: TestClient) -> None:
    response = client.get("/v1/models", headers={"X-Request-ID": "req-test-123"})
    assert response.headers["X-Request-ID"] == "req-test-123"
