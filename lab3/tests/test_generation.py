import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from app.generation import (
    ModelGateway,
    ProviderFailure,
    CloudCircuit,
    retry_delay,
    valid_answer,
)

SOURCES = [{"status": "Действует"}]
MESSAGES = [{"role": "user", "content": "Synthetic public fixture"}]


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "header,expected",
    [("7", 7), ("-1", 0), (None, 60), ("NaN", 60), ("infinity", 60), ("broken", 60)],
)
def test_retry_seconds(header, expected):
    assert retry_delay(header, 60) == expected


def test_retry_http_date():
    future = format_datetime(
        datetime.now(timezone.utc) + timedelta(seconds=12), usegmt=True
    )
    assert 10 < retry_delay(future, 60) <= 12
    assert retry_delay("Fri, 13 Nov 2026 10:00:00", 60) == 60


@pytest.mark.parametrize("value", ["0", "181", "invalid"])
def test_invalid_operator_budget_stops_startup(monkeypatch, value):
    monkeypatch.setenv("LOCAL_BUDGET_SECONDS", value)
    with pytest.raises(ValueError):
        ModelGateway()


@pytest.mark.parametrize(
    "kind,status,code,pause,expected",
    [
        ("rate", 429, "rate_limit", 1, "cloud_rate_limit"),
        ("quota", 429, "mock_confirmed_quota", 1, "cloud_quota"),
        ("unknown_quota", 429, "quota_exceeded", 1, "cloud_rate_limit"),
        ("unauthorized", 401, "unauthorized", None, "cloud_configuration"),
        ("forbidden", 403, "forbidden", None, "cloud_configuration"),
        ("model", 404, "model_not_found", None, "cloud_configuration"),
        ("server", 503, "unavailable", None, "cloud_server_error"),
        ("invalid", 200, "", None, "cloud_invalid_response"),
        ("timeout", 200, "", None, "cloud_transport"),
        ("disconnect", 200, "", None, "cloud_transport"),
    ],
)
def test_provider_failure_one_attempt_same_context(
    monkeypatch, kind, status, code, pause, expected
):
    monkeypatch.setenv("CLOUD_QUOTA_CODES", "mock_confirmed_quota")
    actual_client = httpx.AsyncClient
    requests = []

    def handle(request):
        requests.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("synthetic", request=request)
        if kind == "disconnect":
            raise httpx.RemoteProtocolError("synthetic")
        if status == 200:
            return httpx.Response(200, json={"choices": []})
        return httpx.Response(
            status,
            json={"error": {"code": code}},
            headers={"Retry-After": str(pause)} if pause else {},
        )

    def factory(**kwargs):
        return actual_client(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)

    async def scenario():
        gateway = ModelGateway()
        gateway.cloud_key = "fake"
        local_messages = []

        async def local(messages):
            local_messages.append(messages)
            return "Synthetic public fixture [1]"

        gateway.local = local
        a = await gateway.answer(MESSAGES, SOURCES)
        assert a[1:] == ("local", expected)
        assert local_messages == [MESSAGES] and local_messages[0] is MESSAGES
        assert len(requests) == 1
        b = await gateway.answer(MESSAGES, SOURCES)
        assert b[1] == "local" and len(requests) == 1
        assert gateway.circuit.until > 0

    run(scenario())


def test_private_never_calls_cloud(monkeypatch):
    async def scenario():
        g = ModelGateway()
        g.cloud_key = "fake"

        async def generate(messages, local=False):
            assert local
            return "Synthetic private fixture [1]"

        g.generate = generate
        a = await g.answer(MESSAGES, SOURCES, private=True)
        assert a[1:] == ("local", "private_context") and g.calls["cloud"] == 0

    run(scenario())


def test_one_half_open_probe_and_recovery():
    async def scenario():
        c = CloudCircuit()
        await c.complete(ProviderFailure("test", 0.01))
        assert not await c.acquire()
        await asyncio.sleep(0.02)
        results = await asyncio.gather(*[c.acquire() for _ in range(8)])
        assert sum(results) == 1
        await c.complete()
        assert await c.acquire()

    run(scenario())


def test_local_capacity_and_cancellation_releases_both_positions():
    async def scenario():
        g = ModelGateway()
        started = asyncio.Event()
        release = asyncio.Event()

        async def generate(messages, local=False):
            started.set()
            await release.wait()
            return "done"

        g.generate = generate
        active = asyncio.create_task(g.local(MESSAGES))
        await started.wait()
        waiting = asyncio.create_task(g.local(MESSAGES))
        await asyncio.sleep(0.01)
        assert g.admitted == 2
        with pytest.raises(ProviderFailure, match="local_capacity"):
            await g.local(MESSAGES)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        assert g.admitted == 0 and g.local_slot._value == 1
        release.set()
        assert await g.local(MESSAGES) == "done"

    run(scenario())


@pytest.mark.parametrize(
    "answer",
    [
        "Fact [9]",
        "Fact without reference",
        "Fact https://example.org [1]",
        "<script> [1]",
        "",
    ],
)
def test_invalid_citations(answer):
    assert not valid_answer(answer, SOURCES)


def test_archive_must_be_explicit():
    assert not valid_answer("1000 [1]", [{"status": "Архив"}])
    assert valid_answer("Архив: 1000 [1]", [{"status": "Архив"}])
