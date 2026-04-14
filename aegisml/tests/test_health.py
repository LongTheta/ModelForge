from fastapi.testclient import TestClient


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_when_loaded(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_readyz_503_when_not_ready(client_model_not_ready: TestClient) -> None:
    r = client_model_not_ready.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "model_not_ready"
    assert "message" in body["error"]


def test_metrics_prometheus(client: TestClient) -> None:
    client.get("/healthz")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    body = r.content
    assert b"aegisml_http_requests_total" in body
    assert b"aegisml_http_request_duration_seconds" in body
    assert b"aegisml_http_errors_total" in body


def test_metrics_includes_inference_counters(client: TestClient) -> None:
    client.post("/predict", json={"text": "production outage sev1 customer impact"})
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"aegisml_predictions_total" in r.content
    assert b"aegisml_inference_seconds" in r.content


def test_metrics_error_class_counter_on_4xx(client: TestClient) -> None:
    """4xx responses increment aegisml_http_errors_total{class="4xx"}."""
    r = client.post("/predict", json={"text": ""})
    assert r.status_code == 422
    m = client.get("/metrics").content
    assert b"aegisml_http_errors_total" in m
    assert b"4xx" in m
