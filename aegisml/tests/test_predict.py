from fastapi.testclient import TestClient


def test_predict_success(client: TestClient) -> None:
    r = client.post("/predict", json={"text": "production outage sev1 customer impact"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "incident"
    assert body["confidence"] > 0.0
    assert body["model_version"]
    scores = body["scores"]
    assert list(scores.keys()) == sorted(scores.keys())
    assert abs(sum(scores.values()) - 1.0) < 1e-5


def test_predict_validation_empty_text(client: TestClient) -> None:
    r = client.post("/predict", json={"text": ""})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["detail"]


def test_predict_validation_whitespace_only(client: TestClient) -> None:
    r = client.post("/predict", json={"text": "   \t  "})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_predict_validation_missing_body_field(client: TestClient) -> None:
    r = client.post("/predict", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_predict_validation_text_too_long(client: TestClient) -> None:
    r = client.post("/predict", json={"text": "a" * 8001})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_predict_validation_wrong_type(client: TestClient) -> None:
    r = client.post("/predict", json={"text": 123})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
