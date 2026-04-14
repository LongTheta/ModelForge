"""Minimal contract coverage: probes, prediction success, and validation errors."""

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz_returns_ready_when_model_loaded(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_predict_success_returns_label_scores_version(client: TestClient) -> None:
    r = client.post("/predict", json={"text": "production outage sev1 customer impact"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "incident"
    assert body["model_version"] == "ticket-triage-tfidf-2.0"
    assert abs(sum(body["scores"].values()) - 1.0) < 1e-5


def test_predict_invalid_body_returns_structured_validation_error(client: TestClient) -> None:
    r = client.post("/predict", json={"text": ""})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["detail"]


def test_predict_malformed_json_returns_422(client: TestClient) -> None:
    r = client.post(
        "/predict",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 422
