"""Verify real CPU admission, HTTP cancellation and the filtered K01 answer."""

import argparse
import asyncio
import json
from pathlib import Path
import time

import httpx

from verify_portal import facts


async def verify(args):
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "control-questions.json").read_text(encoding="utf-8"))

    def body(case_id):
        case = next(case for case in cases if case["id"] == case_id)
        return {
            "query": case["question"],
            "statuses": case["statuses"],
            "private": True,
        }

    async with httpx.AsyncClient(
        base_url=args.base_url, trust_env=False, timeout=95
    ) as http:
        login = await http.post(
            "/api/login",
            json={
                "token": args.portal_token_file.read_text(encoding="utf-8-sig").strip()
            },
        )
        login.raise_for_status()
        pending = []
        try:
            pending.append(asyncio.create_task(http.post("/api/ask", json=body("K04"))))
            await asyncio.sleep(3)
            pending.append(asyncio.create_task(http.post("/api/ask", json=body("K01"))))
            await asyncio.sleep(1)
            response = await http.post("/api/ask", json=body("K01"))
            response.raise_for_status()
            overloaded = response.json()
            assert overloaded["mode"] == "search_only"
            assert overloaded["reason"] == "private_context:local_capacity"
            started = time.perf_counter()
            for request in pending:
                request.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            cancel_ms = round((time.perf_counter() - started) * 1000)
            await asyncio.sleep(1)
            filtered = body("K01")
            filtered["path"] = ["Чаты и каналы", "Группы и каналы"]
            response = await http.post("/api/ask", json=filtered)
            response.raise_for_status()
            data = response.json()
            missing = facts("K01", data.get("answer") or "")
            assert data["mode"] == "local" and not missing, (data["reason"], missing)
            assert all(card["path"] == filtered["path"] for card in data["cards"])
            assert all(source["visibility"] == "cloud_ok" for source in data["sources"])
            assert any(
                source["id"] == "M-05" and source["version"] == "2.0"
                for source in data["sources"]
            )
            report = {
                "status": "passed",
                "active_limit": 1,
                "waiting_limit": 1,
                "third_request": {
                    key: overloaded[key] for key in ("mode", "reason", "latency_ms")
                },
                "cancelled_positions": ["active", "waiting"],
                "client_cancel_ms": cancel_ms,
                "next_filtered_K01": {
                    "path": filtered["path"],
                    **{
                        key: data[key]
                        for key in (
                            "answer",
                            "mode",
                            "reason",
                            "latency_ms",
                            "request_id",
                            "context_sha256",
                        )
                    },
                    "sources": [
                        source["id"] + "@" + source["version"] + "#" + source["anchor"]
                        for source in data["sources"]
                    ],
                    "missing_facts": missing,
                },
                "measurement": "real HTTP disconnect followed by real CPU generation; server admission release also checked over TCP in regression tests",
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "third_request": overloaded["reason"],
                        "cancel_ms": cancel_ms,
                        "filtered_K01_ms": data["latency_ms"],
                    }
                ),
                flush=True,
            )
        finally:
            for request in pending:
                request.cancel()
            await asyncio.gather(*pending, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18081")
    parser.add_argument("--portal-token-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(verify(parser.parse_args()))
