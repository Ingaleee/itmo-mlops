"""Real server process and independent official SDK; synthetic corpus only."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import pytest

from app.mcp_client import MCPClient


def test_real_mcp_http_and_authentication(tmp_path, corpus):
    source = tmp_path / "corpus.json"
    source.write_text(json.dumps(corpus), encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    token = "synthetic-service-token-12345678"
    env = {
        **os.environ,
        "KB_CORPUS": str(source),
        "KB_DATABASE": str(tmp_path / "knowledge.db"),
        "MCP_SERVICE_TOKEN": token,
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.mcp_server:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(trust_env=False, timeout=1) as http:
            for _ in range(100):
                if process.poll() is not None:
                    raise AssertionError("MCP exited before readiness")
                try:
                    if http.get(base + "/readyz").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError("MCP did not start")
            assert http.post(base + "/mcp", json={}).status_code == 401
            assert (
                http.post(
                    base + "/mcp",
                    json={},
                    headers={
                        "Authorization": "Bearer " + token,
                        "Origin": "https://attacker.invalid",
                    },
                ).status_code
                == 403
            )

        async def check():
            async with httpx.AsyncClient(
                headers={"Authorization": "Bearer " + token}, trust_env=False
            ) as http:
                async with streamable_http_client(base + "/mcp", http_client=http) as (
                    read,
                    write,
                    _,
                ):
                    async with ClientSession(read, write) as session:
                        initialized = await session.initialize()
                        tools = (await session.list_tools()).tools
                        good = await session.call_tool(
                            "get_doc", {"doc_id": "M-05", "version": "1.1"}
                        )
                        bad = await session.call_tool(
                            "get_doc", {"doc_id": "M-05", "version": "9.9"}
                        )
            assert initialized.protocolVersion
            assert {t.name for t in tools} == {
                "list_sections",
                "search_docs",
                "get_doc",
            }
            assert all(t.outputSchema for t in tools)
            assert not good.isError and good.structuredContent["status"] == "Архив"
            assert bad.isError
            client = MCPClient(base + "/mcp", token)
            with pytest.raises(ValueError):
                await client.call("get_doc", {"doc_id": "M-05", "version": "9.9"})
            current = await client.call("search_docs", {"query": "M-05"})
            assert current["cards"][0]["version"] == "2.0"

        asyncio.run(check())
    finally:
        process.terminate()
        process.wait(timeout=10)
