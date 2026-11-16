"""Knowledge portal: browser -> authenticated backend -> MCP -> model gateway."""

import asyncio
import hmac
import json
import logging
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field

from app.contracts import Contract, Status
from app.generation import ModelGateway, context, prompt, snapshot_hash
from app.mcp_client import MCPClient, KnowledgeUnavailable
from app.token_budget import Budget

logger = logging.getLogger("knowledge-portal")
STATIC = Path(__file__).parent / "static"


class Query(Contract):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=5)
    path: list[str] | None = Field(default=None, min_length=1, max_length=2)
    statuses: list[Status] | None = Field(default=None, min_length=1, max_length=3)
    doc_id: str | None = Field(default=None, pattern=r"^[A-Z]-\d{2}$")
    version: str | None = Field(default=None, pattern=r"^\d+\.\d+$")
    private: bool = False


class Login(Contract):
    token: str = Field(min_length=24, max_length=256)


def create_app():
    app = FastAPI(
        title="Линия · Knowledge Portal", version="1.0.0", docs_url=None, redoc_url=None
    )
    client = MCPClient()
    gateway = ModelGateway()
    budget = Budget()
    access_token = os.environ["PORTAL_ACCESS_TOKEN"]
    if len(access_token) < 24:
        raise RuntimeError("Portal access token is too short")
    app.state.gateway = gateway
    app.state.knowledge = client

    @app.middleware("http")
    async def boundary(request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        if request.method == "POST" and request.headers.get("origin"):
            if urlsplit(request.headers["origin"]).netloc != request.headers.get(
                "host"
            ):
                return JSONResponse({"detail": "Origin rejected"}, status_code=403)
        protected = (
            request.url.path.startswith("/api/") and request.url.path != "/api/login"
        )
        if protected and not hmac.compare_digest(
            request.cookies.get("portal_session", "").encode(), access_token.encode()
        ):
            return JSONResponse(
                {"detail": "Войдите с токеном портала"}, status_code=401
            )
        started = time.perf_counter()
        response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            }
        )
        # No paths, query strings, questions, context, model responses or auth values.
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                }
            )
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(_, error):
        return JSONResponse(
            {"detail": [{"loc": e["loc"], "type": e["type"]} for e in error.errors()]},
            status_code=422,
        )

    @app.exception_handler(KnowledgeUnavailable)
    async def unavailable(request, error):
        logger.warning(
            json.dumps(
                {
                    "event": "mcp_unavailable",
                    "request_id": request.state.request_id,
                    "cause_type": type(error.__cause__).__name__,
                }
            )
        )
        return JSONResponse(
            {
                "detail": "База знаний временно недоступна",
                "request_id": request.state.request_id,
            },
            status_code=503,
        )

    @app.exception_handler(ValueError)
    async def rejected(_, error):
        return JSONResponse(
            {"detail": "Документ, редакция или параметры не найдены"}, status_code=404
        )

    @app.get("/livez")
    async def live():
        return {"status": "alive"}

    @app.get("/readyz")
    async def ready():
        tree = await client.call("list_sections", {})
        return {
            "status": "ready",
            "generation": tree["generation"],
            "models": "not required for search",
        }

    @app.post("/api/login")
    async def login(body: Login):
        if not hmac.compare_digest(body.token.encode(), access_token.encode()):
            raise HTTPException(401, "Неверный токен")
        response = JSONResponse({"status": "ok"})
        response.set_cookie(
            "portal_session",
            access_token,
            httponly=True,
            samesite="strict",
            secure=os.getenv("COOKIE_SECURE", "false") == "true",
            max_age=3600,
        )
        return response

    @app.post("/api/logout")
    async def logout():
        response = JSONResponse({"status": "ok"})
        response.delete_cookie("portal_session")
        return response

    @app.get("/api/tree")
    async def tree():
        return await client.call("list_sections", {})

    @app.get("/api/docs/{doc_id}/{version}")
    async def document(doc_id: str, version: str):
        if len(doc_id) > 10 or len(version) > 20:
            raise HTTPException(404)
        return await client.call("get_doc", {"doc_id": doc_id, "version": version})

    async def search(body):
        return await client.call(
            "search_docs", body.model_dump(exclude={"private"}, exclude_none=True)
        )

    @app.post("/api/search")
    async def find(body: Query):
        return await search(body)

    async def generate(body, request):
        snapshot = await search(body)
        sources = context(snapshot, body.query, budget)
        # Fail closed using ALL retrieved material, before making any cloud attempt.
        private = body.private or any(
            c.get("visibility") != "cloud_ok" for c in snapshot["cards"]
        )
        messages = prompt(body.query, sources)
        started = time.perf_counter()
        if len(sources) < 2 or budget.count(messages) > 1500:
            answer, mode, reason = None, "search_only", "insufficient_context"
        else:
            answer, mode, reason = await gateway.answer(
                messages, sources, private=private
            )
        logger.info(
            json.dumps(
                {
                    "event": "generation",
                    "request_id": request.state.request_id,
                    "route": mode,
                    "reason": reason,
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                    "cloud_calls": gateway.calls["cloud"],
                    "local_calls": gateway.calls["local"],
                }
            )
        )
        return {
            **snapshot,
            "answer": answer,
            "mode": mode,
            "reason": reason,
            "sources": sources,
            "context_sha256": snapshot_hash(sources),
            "prompt_tokens": budget.count(messages),
            "request_id": request.state.request_id,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }

    @app.post("/api/ask")
    async def ask(body: Query, request: Request):
        async def disconnected():
            # FastAPI has consumed the JSON body. Wait for the ASGI disconnect
            # directly: is_disconnected's cancelled polling cannot traverse
            # BaseHTTPMiddleware's receive task group reliably.
            while (await request.receive())["type"] != "http.disconnect":
                pass

        work = asyncio.create_task(generate(body, request))
        disconnect = asyncio.create_task(disconnected())
        try:
            async with asyncio.timeout(92):
                done, _ = await asyncio.wait(
                    {work, disconnect}, return_when=asyncio.FIRST_COMPLETED
                )
                if disconnect in done:
                    raise HTTPException(499, "Client disconnected")
                return await work
        finally:
            for task in (work, disconnect):
                if not task.done():
                    task.cancel()
            await asyncio.gather(work, disconnect, return_exceptions=True)

    @app.get("/")
    @app.get("/docs/{doc_id}/{version}")
    async def home():
        return FileResponse(STATIC / "index.html")

    @app.get("/static/{name}")
    async def asset(name: str):
        if name not in {"portal.js", "portal.css"}:
            raise HTTPException(404)
        return FileResponse(STATIC / name)

    return app
