"""Exercise real portal/MCP/model; cloud requests require a local privacy audit."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def facts(case, text):
    """Independent factual checks derived from the assignment's control table."""
    value = re.sub(r"\[\d+\]", "", text.lower())
    value = re.sub(r"(?<=\d)[\s\u00a0](?=\d{3}(?:\D|$))", "", value)
    expected = {
        "K01": [
            r"5000",
            r"приглашен",
            r"не (?:занима|расход|резервир|влия|учитыва)|без принятия",
        ],
        "K02": [r"1000", r"архив"],
        "K03": [
            r"публичн",
            r"не (?:запущ|вход|реализ)|за предел|ещ[её] не|не включ|не доступны|не работают|не откры",
            r"20000",
            r"гипотез|черновик|предложен",
        ],
        "K04": [
            r"86",
            r"120",
            r"39",
            r"70",
            r"50",
            r"удержан",
            r"активац",
            r"нет|не было|отсутств",
        ],
        "K05": [r"финансов", r"руководител.{0,8}продукт", r"резерв"],
        "K06": [r"4320", r"2160"],
        "K07": [
            r"firefox",
            r"дв(?:е|а|ух)|2",
            r"стабильн",
            r"ios",
            r"не (?:вход|участв|поддерж)|вне|отдельн|исследовательск",
        ],
        "K08": [
            r"не (?:указ|назнач|определ|запланир|зафиксир)|нет (?:дат|срок)|дата отсутств"
        ],
    }
    missing = [pattern for pattern in expected[case] if not re.search(pattern, value)]
    if case == "K06" and re.search(r"46500|6000", value):
        missing.append("Introduced changed support costs despite fixed assumptions")
    return missing


def main():
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:18081")
    p.add_argument("--portal-token-file", required=True, type=Path)
    p.add_argument("--route", choices=["cloud", "local"], required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--privacy-audit", type=Path, default=root / "evidence/privacy.json")
    p.add_argument(
        "--cases",
        nargs="*",
        help="Run only the named control IDs for a focused recheck",
    )
    args = p.parse_args()
    audit = json.loads(args.privacy_audit.read_text(encoding="utf-8"))
    assert (
        audit["status"] == "passed"
        and audit["external_requests"] == 0
        and audit["closed_quote_excluded"]
    )
    allowed = {row["id"]: row for row in audit["control_contexts"]}
    if args.route == "cloud":
        # Cloud calls need a local reconstruction before any external request.
        from app.generation import context, snapshot_hash
        from app.token_budget import Budget
        budget = Budget(root / "model/qwen3-tokenizer.json")
    cases = json.loads((root / "control-questions.json").read_text(encoding="utf-8"))
    if args.cases:
        assert set(args.cases) <= {c["id"] for c in cases}
        cases = [c for c in cases if c["id"] in args.cases]
    results = []
    with httpx.Client(timeout=200, trust_env=False, follow_redirects=False) as http:
        login = http.post(
            args.base_url + "/api/login",
            json={
                "token": args.portal_token_file.read_text(encoding="utf-8-sig").strip()
            },
        )
        login.raise_for_status()
        for case in cases:
            body = {
                "query": case["question"],
                "statuses": case["statuses"],
                "private": args.route == "local",
            }
            # Verify the actual MCP snapshot before an allowed public cloud call.
            response = http.post(args.base_url + "/api/search", json=body)
            response.raise_for_status()
            snapshot = response.json()
            proof = allowed[case["id"]]
            assert all(c["visibility"] == "cloud_ok" for c in snapshot["cards"])
            assert proof["generation"] == snapshot["generation"]
            if args.route == "cloud":
                sources = context(snapshot, case["question"], budget)
                assert proof["context_sha256"] == snapshot_hash(sources)
            response = http.post(args.base_url + "/api/ask", json=body)
            response.raise_for_status()
            data = response.json()
            # Bounded metadata makes a failed comparison diagnosable without
            # exporting the worker log or an unvalidated document snapshot.
            actual_hash = hashlib.sha256(json.dumps(
                data["sources"], ensure_ascii=False, sort_keys=True
            ).encode()).hexdigest()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.with_name("verification-stage.json").write_text(json.dumps({
                "case": case["id"],
                "generation_matches": data["generation"] == snapshot["generation"],
                "source_hash_matches_response": actual_hash == data["context_sha256"],
                "source_hash_matches_audit": actual_hash == proof["context_sha256"],
                "all_sources_cloud_ok": all(s["visibility"] == "cloud_ok" for s in data["sources"]),
                "source_count": len(data["sources"]),
                "prompt_tokens": data["prompt_tokens"],
                "audited_prompt_tokens": proof["prompt_tokens"],
                "route_matches": data["mode"] == args.route,
            }, indent=2) + "\n", encoding="utf-8")
            assert data["generation"] == snapshot["generation"]
            # The CPU path compares the actual response to the independently
            # audited context, without loading a second model tokenizer in Pod.
            assert actual_hash == data["context_sha256"] == proof["context_sha256"]
            assert all(s["visibility"] == "cloud_ok" for s in data["sources"])
            assert 2 <= len(data["sources"]) <= 4
            assert data["prompt_tokens"] == proof["prompt_tokens"] <= 1500
            missing = facts(case["id"], data.get("answer") or "")
            passed = data["mode"] == args.route and not missing
            # Reports intentionally contain only public control contexts and answers.
            results.append(
                {
                    "id": case["id"],
                    "status": "passed" if passed else "failed",
                    "missing_facts": missing,
                    "expected": case["expected"],
                    **data,
                }
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(
                    {
                        "status": "passed"
                        if all(r["status"] == "passed" for r in results)
                        else "failed",
                        "provider_route": args.route,
                        "cases": results,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {
                        "id": case["id"],
                        "status": "passed" if passed else "failed",
                        "route": data["mode"],
                        "reason": data["reason"],
                        "latency_ms": data["latency_ms"],
                        "missing_facts": missing,
                    }
                ),
                flush=True,
            )
    if not all(r["status"] == "passed" for r in results):
        raise SystemExit("One or more factual control checks failed; see the report")


if __name__ == "__main__":
    main()
