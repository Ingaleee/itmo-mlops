"""Real loopback HTTP faults, without any provider key or knowledge corpus."""

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest

from app.generation import ModelGateway


@pytest.fixture(scope="module")
def fault_provider():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "testing.cloud_mock:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(timeout=1, trust_env=False) as http:
            for _ in range(100):
                if process.poll() is not None:
                    raise AssertionError("Mock did not start")
                try:
                    if (
                        http.get(
                            base + "/inspection",
                            headers={"Authorization": "Bearer mock-key-not-secret"},
                        ).status_code
                        == 200
                    ):
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            else:
                raise AssertionError("Mock did not become ready")
        yield base
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("429", "cloud_rate_limit"),
        ("503", "cloud_server_error"),
        ("quota", "cloud_quota"),
        ("invalid", "cloud_invalid_response"),
        ("timeout", "cloud_transport"),
    ],
)
def test_real_http_fallback_and_recovery(fault_provider, monkeypatch, mode, reason):
    monkeypatch.setenv("CLOUD_QUOTA_CODES", "mock_confirmed_quota")

    async def scenario():
        async with httpx.AsyncClient(
            timeout=3,
            trust_env=False,
            headers={"Authorization": "Bearer mock-key-not-secret"},
        ) as http:
            await http.post(fault_provider + "/control", json={"mode": mode})
            gateway = ModelGateway()
            gateway.cloud_key = "mock-key-not-secret"
            gateway.cloud_url = fault_provider + "/v1"
            gateway.local_url = fault_provider + "/local/v1"
            if mode == "timeout":
                gateway.cloud_timeout = 0.1
            messages = [
                {
                    "role": "user",
                    "content": "Synthetic public question. Context generation fixture-1.",
                }
            ]
            result = await gateway.answer(messages, [{"status": "Действует"}])
            assert result[1:] == ("local", reason)
            inspection = (await http.get(fault_provider + "/inspection")).json()
            assert [r["local"] for r in inspection["requests"]] == [False, True]
            assert len({r["sha256"] for r in inspection["requests"]}) == 1
            # No second cloud attempt during the pause, even on another answer.
            assert (await gateway.answer(messages, [{"status": "Действует"}]))[
                1
            ] == "local"
            assert (
                sum(
                    not r["local"]
                    for r in (await http.get(fault_provider + "/inspection")).json()[
                        "requests"
                    ]
                )
                == 1
            )
            await http.post(fault_provider + "/control", json={"mode": "ok"})
            gateway.circuit.until = time.monotonic() - 0.01
            gateway.cloud_timeout = 2
            assert (await gateway.answer(messages, [{"status": "Действует"}]))[
                1
            ] == "cloud"
            assert gateway.circuit.reason == "cloud_available"

    asyncio.run(scenario())
