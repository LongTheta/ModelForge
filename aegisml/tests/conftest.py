import pytest
from app.dependencies import classifier_dep
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_model_not_ready() -> TestClient:
    class _NotReady:
        is_ready = False

        def predict(self, _text: str) -> tuple[str, float, dict[str, float]]:
            raise RuntimeError("should not be called")

    def _override() -> _NotReady:
        return _NotReady()

    app.dependency_overrides[classifier_dep] = _override
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(classifier_dep, None)
