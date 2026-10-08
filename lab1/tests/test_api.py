import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.main as service


@pytest.fixture
def client():
    with TestClient(service.app) as api:
        yield api


@pytest.mark.parametrize("features,expected", [([5.1, 3.5, 1.4, .2], 0), ([7., 3.2, 4.7, 1.4], 1), ([6.3, 3.3, 6., 2.5], 2)])
def test_all_classes(client, features, expected):
    response = client.post("/predict", json={"features": features})
    assert response.status_code == 200
    assert response.json() == {"class_id": expected, "model_version": "iris-v1"}


@pytest.mark.parametrize("payload", [
    {"features": [1, 2]}, {"features": [1, 2, 3, 4, 5]},
    {"features": ["NaN", 2, 3, 4]}, {"features": ["Infinity", 2, 3, 4]},
    {"features": [True, 2, 3, 4]}, {"features": [None, 2, 3, 4]},
    {"features": [1, 2, 3, 4], "unexpected": "value"},
])
def test_invalid_features_do_not_reach_model(client, payload):
    assert client.post("/predict", json=payload).status_code == 422


def test_liveness_and_readiness_are_distinct(client, monkeypatch):
    assert client.get("/health").status_code == 200
    monkeypatch.setattr(service, "model", None)
    assert client.get("/live").status_code == 200
    assert client.get("/health").status_code == 503
    assert client.post("/predict", json={"features": [1, 2, 3, 4]}).status_code == 503


def test_lifespan_releases_model():
    with TestClient(service.app):
        assert service.model is not None
    assert service.model is None
