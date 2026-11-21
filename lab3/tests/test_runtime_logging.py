import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx


def test_normal_uvicorn_emits_correlated_json_without_sensitive_input(tmp_path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "logging_app.py").write_text(
        "from app.portal import create_app\n"
        "create_app()\n"
        "app = create_app()\n"
        "async def empty_snapshot(*args, **kwargs):\n"
        "    return {'generation':'synthetic','cards':[]}\n"
        "app.state.knowledge.call = empty_snapshot\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.update(
        PYTHONPATH=str(root),
        MCP_SERVICE_TOKEN="synthetic-service-token-12345678",
        PORTAL_ACCESS_TOKEN="synthetic-portal-token-12345678",
    )
    environment.pop("LLM7_API_KEY", None)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with (tmp_path / "server.log").open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "logging_app:app", "--app-dir", str(tmp_path),
             "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
            cwd=root, env=environment, stdout=output, stderr=output,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3, trust_env=False) as client:
                for _ in range(100):
                    assert process.poll() is None, "Uvicorn exited before the check"
                    try:
                        if client.get("/livez").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.05)
                else:
                    raise AssertionError("Uvicorn did not start")
                client.post("/api/login", json={"token": environment["PORTAL_ACCESS_TOKEN"]}).raise_for_status()
                response = client.post("/api/ask", json={"query": "sensitive-query-marker-92841"})
                response.raise_for_status()
                data = response.json()
                assert data["mode"] == "search_only"
                assert response.headers["x-request-id"] == data["request_id"]
        finally:
            process.terminate()
            process.wait(timeout=10)
    text = (tmp_path / "server.log").read_text(encoding="utf-8")
    records = [json.loads(line) for line in text.splitlines() if line.startswith("{")]
    generations = [r for r in records if r["event"] == "generation"]
    assert len(generations) == 1, "ordinary runtime did not emit exactly one generation event"
    assert generations[0]["request_id"] == data["request_id"]
    assert generations[0]["route"] == "search_only"
    assert generations[0]["cloud_calls"] == generations[0]["local_calls"] == 0
    http_records = [r for r in records if r["event"] == "request" and r["request_id"] == data["request_id"]]
    assert len(http_records) == 1 and http_records[0]["status"] == 200
    assert "sensitive-query-marker-92841" not in text
    assert environment["PORTAL_ACCESS_TOKEN"] not in text
    assert environment["MCP_SERVICE_TOKEN"] not in text
