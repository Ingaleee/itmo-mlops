import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["ARTIFACT_DIR"] = "artifacts"

from app.main import app  # noqa: E402
import app.main as service


def test_search_and_version() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/search",
            headers={"x-request-id": "test-request-42"},
            json={"query": "как вернуть предыдущую модель после плохого релиза", "limit": 3},
        )
        assert response.status_code == 200
        assert response.headers["x-request-id"] == "test-request-42"
        assert response.json()["request_id"] == "test-request-42"
        assert response.json()["results"][0]["id"] == "doc-rollback"
        assert client.get("/readyz").status_code == 200
        assert client.get("/meta").json()["model_type"] == "tfidf-word-char-cosine"
        assert "search_requests_total" in client.get("/metrics").text


def test_unknown_recommendation_document() -> None:
    with TestClient(app) as client:
        assert client.get("/v1/documents/missing/recommendations").status_code == 404


@pytest.mark.parametrize("payload", [
    {"query": "   "}, {"query": "q"}, {"query": "a" * 501},
    {"query": "rollback", "limit": 0}, {"query": "rollback", "limit": 11},
    {"query": "rollback", "unexpected": "value"},
])
def test_invalid_search_is_rejected(payload):
    with TestClient(app) as client:
        assert client.post("/v1/search", json=payload).status_code == 422


@pytest.mark.parametrize("limit", [0, 11])
def test_recommendation_limit_is_validated(limit):
    with TestClient(app) as client:
        assert client.get(f"/v1/documents/doc-rollback/recommendations?limit={limit}").status_code == 422


def test_oversized_request_id_is_replaced_consistently():
    with TestClient(app) as client:
        response = client.post("/v1/search", headers={"x-request-id": "x" * 256}, json={"query": "rollback"})
        assert response.status_code == 200
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert len(response.headers["x-request-id"]) <= 128


def test_unready_index_does_not_break_liveness(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(service, "engine", None)
        assert client.get("/livez").status_code == 200
        assert client.get("/readyz").status_code == 503
        assert client.post("/v1/search", json={"query": "rollback"}).status_code == 503
        assert "search_index_loaded 0" in client.get("/metrics").text


def test_meta_exposes_verified_artifact_and_lifespan_cleans_up():
    with TestClient(app) as client:
        metadata = client.get("/meta").json()
        assert len(metadata["artifact_sha256"]) == 64
        assert metadata["ranking_mode"] == "normal"
    assert service.engine is None


def test_unexpected_failure_keeps_request_id_without_exposing_details(monkeypatch):
    with TestClient(app) as client:
        def fail(*_):
            raise RuntimeError("private implementation detail")
        monkeypatch.setattr(service.engine, "search", fail)
        response = client.post("/v1/search", headers={"x-request-id": "failure-42"}, json={"query": "rollback"})
        assert response.status_code == 500
        assert response.headers["x-request-id"] == response.json()["request_id"] == "failure-42"
        assert "private implementation detail" not in response.text
