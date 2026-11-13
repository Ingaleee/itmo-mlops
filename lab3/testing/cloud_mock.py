"""Isolated fault provider. Fake keys only; no real provider or corpus in image."""

import asyncio
import hashlib
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(docs_url=None, redoc_url=None)
state = {"mode": "ok", "requests": [], "active": 0, "peak": 0, "delay": 0.0}


@app.post("/control")
async def control(request: Request):
    if request.headers.get("authorization") != "Bearer mock-key-not-secret":
        raise HTTPException(403)
    config = await request.json()
    state.update(
        mode=config.get("mode", "ok"),
        delay=config.get("delay", 0.0),
        requests=[],
        active=0,
        peak=0,
    )
    return {"status": "ok"}


@app.get("/inspection")
async def inspection(request: Request):
    if request.headers.get("authorization") != "Bearer mock-key-not-secret":
        raise HTTPException(403)
    # Explicit diagnostic endpoint, bound only to localhost in the test harness.
    return state


@app.post("/v1/chat/completions")
@app.post("/local/v1/chat/completions")
async def chat(request: Request):
    local = request.url.path.startswith("/local/")
    expected = "local" if local else "mock-key-not-secret"
    if request.headers.get("authorization") != "Bearer " + expected:
        raise HTTPException(403)
    body = await request.json()
    raw = json.dumps(body["messages"], ensure_ascii=False, sort_keys=True).encode()
    state["requests"].append(
        {
            "local": local,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "messages": body["messages"],
        }
    )
    mode = state["mode"]
    if not local:
        if mode == "429":
            return JSONResponse(
                {"error": {"code": "rate_limit"}},
                status_code=429,
                headers={"Retry-After": "1"},
            )
        if mode == "quota":
            return JSONResponse(
                {"error": {"code": "mock_confirmed_quota"}},
                status_code=429,
                headers={"Retry-After": "1"},
            )
        if mode == "503":
            return JSONResponse({"error": {"code": "unavailable"}}, status_code=503)
        if mode == "401":
            return JSONResponse({"error": {"code": "unauthorized"}}, status_code=401)
        if mode == "invalid":
            return {"choices": [{"message": {"content": "invalid response"}}]}
        if mode == "timeout":
            await asyncio.sleep(10)
    if mode == "both_down" or local and mode == "local_down":
        return JSONResponse({"error": {"code": "unavailable"}}, status_code=503)
    state["active"] += 1
    state["peak"] = max(state["peak"], state["active"])
    try:
        if state["delay"]:
            await asyncio.sleep(state["delay"])
        content = json.dumps({"answer": "Synthetic test fact. [1]"})
        return {"choices": [{"message": {"content": content}}]}
    finally:
        state["active"] -= 1
