import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.mcp_client import MCPClient
from app.portal import create_app


@pytest.fixture
def portal(monkeypatch):
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "synthetic-service-token-12345678")
    monkeypatch.setenv("PORTAL_ACCESS_TOKEN", "synthetic-portal-token-12345678")
    monkeypatch.setenv("LLM7_API_KEY", "synthetic-cloud-key")
    card = {
        "id": "X-01",
        "version": "1.0",
        "title": "Synthetic public fixture",
        "status": "Действует",
        "visibility": "cloud_ok",
        "path": ["A", "B"],
        "links": [],
        "rank": 1,
        "fragments": [
            {
                "anchor": "s01",
                "chunk_id": "x1",
                "heading": "First",
                "text": "First synthetic fact.",
                "rank": -2,
            },
            {
                "anchor": "s02",
                "chunk_id": "x2",
                "heading": "Second",
                "text": "Second synthetic fact.",
                "rank": -1,
            },
        ],
    }
    snapshot = {"generation": "synthetic-generation", "cards": [card]}

    async def call(self, name, arguments):
        return copy.deepcopy(snapshot)

    monkeypatch.setattr(MCPClient, "call", call)
    actual = httpx.AsyncClient
    captured = []

    def send(request):
        captured.append(request)
        content = json.dumps({"answer": "Synthetic fact. [1]"})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: actual(transport=httpx.MockTransport(send), **kwargs),
    )
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/login", json={"token": "synthetic-portal-token-12345678"}
        )
        assert response.status_code == 200
        yield client, snapshot, captured, app


def test_allowed_snapshot_goes_to_cloud(portal):
    client, snapshot, captured, app = portal
    response = client.post("/api/ask", json={"query": "Synthetic public question"})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "cloud" and len(captured) == 1
    assert data["generation"] == snapshot["generation"]
    assert data["prompt_tokens"] <= 1500 and len(data["sources"]) == 2
    assert all(s["url"].startswith("/docs/X-01/1.0#") for s in data["sources"])


@pytest.mark.parametrize(
    "private,label",
    [(True, "cloud_ok"), (False, "local_only"), (False, "unknown"), (False, None)],
)
def test_private_or_uncertain_context_never_leaves_local_route(portal, private, label):
    client, snapshot, captured, app = portal
    snapshot["cards"][0]["visibility"] = label
    response = client.post(
        "/api/ask", json={"query": "Synthetic private question", "private": private}
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "local"
    assert len(captured) == 1 and captured[0].headers["authorization"] == "Bearer local"
    assert app.state.gateway.calls["cloud"] == 0


def test_closed_card_outside_selected_snippets_still_blocks_cloud(portal):
    client, snapshot, captured, app = portal
    closed = copy.deepcopy(snapshot["cards"][0])
    closed.update(id="X-02", visibility="local_only", links=[])
    snapshot["cards"].append(closed)
    response = client.post("/api/ask", json={"query": "Synthetic question"})
    assert response.json()["mode"] == "local"
    assert app.state.gateway.calls["cloud"] == 0


def test_no_context_never_calls_either_model(portal):
    client, snapshot, captured, app = portal
    snapshot["cards"] = []
    response = client.post("/api/ask", json={"query": "No such information"})
    assert response.json()["mode"] == "search_only" and not captured


def test_auth_origin_and_validation_do_not_echo_input(portal):
    client, _, _, _ = portal
    response = client.post(
        "/api/ask", json={"query": "OK"}, headers={"Origin": "https://attacker.invalid"}
    )
    assert response.status_code == 403
    response = client.post(
        "/api/ask", json={"query": "OK", "unexpected": "sensitive-value"}
    )
    assert response.status_code == 422 and "sensitive-value" not in response.text
    client.post("/api/logout")
    assert client.get("/api/tree").status_code == 401
    assert (
        client.post(
            "/api/login", json={"token": "НеверныйКириллическийТокенДоступа"}
        ).status_code
        == 401
    )


def test_doc_page_is_shell_and_missing_exact_revision_is_not_substituted(
    portal, monkeypatch
):
    client, _, _, _ = portal

    async def missing(self, name, arguments):
        assert arguments == {"doc_id": "M-05", "version": "9.9"}
        raise ValueError("absent")

    monkeypatch.setattr(MCPClient, "call", missing)
    response = client.get("/docs/M-05/9.9")
    assert response.status_code == 200 and "document-view" in response.text
    assert client.get("/api/docs/M-05/9.9").status_code == 404
