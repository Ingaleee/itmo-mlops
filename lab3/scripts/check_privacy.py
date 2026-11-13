"""Verify real retrieval provenance locally before any permitted cloud call."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.corpus import inspect
from app.generation import context, prompt, snapshot_hash
from app.knowledge import Knowledge, build, EXCLUDED_CONTEXT
from app.token_budget import Budget


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpus", type=Path)
    args = p.parse_args()
    raw = args.corpus.read_bytes()
    inspect(raw)
    corpus = json.loads(raw.decode("utf-8-sig"))
    docs = {
        (d["id"], d["version"]): d
        for s in corpus["sections"]
        for sub in s["subsections"]
        for d in sub["documents"]
    }
    root = Path(__file__).resolve().parents[1]
    target = root / "artifacts/knowledge.db"
    build(args.corpus, target)
    kb = Knowledge(target)
    budget = Budget(root / "model/qwen3-tokenizer.json")
    report = []
    for case in json.loads(
        (root / "control-questions.json").read_text(encoding="utf-8")
    ):
        snapshot = kb.search(case["question"], statuses=case["statuses"])
        assert all(c["visibility"] == "cloud_ok" for c in snapshot["cards"]), case["id"]
        sources = context(snapshot, case["question"], budget)
        for s in sources:
            original = docs[(s["id"], s["version"])]
            assert original["visibility"] == "cloud_ok"
            assert original["title"] == s["title"]
            assert (s["id"], s["version"], s["anchor"]) not in EXCLUDED_CONTEXT
            section = next(
                x for x in original["sections"] if x["anchor"] == s["anchor"]
            )
            assert any(
                s["text"] in " ".join(paragraph.split())
                for paragraph in section["body"]
            )
        pairs = {c["id"] + "@" + c["version"] for c in snapshot["cards"]}
        assert set(case.get("required_documents", [])) <= pairs, case["id"]
        assert not case.get("any_of_documents") or pairs & set(
            case["any_of_documents"]
        ), case["id"]
        report.append(
            {
                "id": case["id"],
                "generation": snapshot["generation"],
                "context_sha256": snapshot_hash(sources),
                "sources": [
                    s["id"] + "@" + s["version"] + "#" + s["anchor"] for s in sources
                ],
                "all_retrieved_and_selected_sources_cloud_ok": True,
                "prompt_tokens": budget.count(prompt(case["question"], sources)),
            }
        )
    closed = kb.search("S-06", doc_id="S-06")
    assert closed["cards"] and all(
        c["visibility"] == "local_only" for c in closed["cards"]
    )
    assert all(f["anchor"] != "s02" for c in closed["cards"] for f in c["fragments"])
    # Originals remain readable only via the exact authenticated document endpoint.
    assert any(s["anchor"] == "s02" for s in kb.get("S-06", "1.0")["sections"])
    output = {
        "status": "passed",
        "corpus_sha256": hashlib.sha256(raw).hexdigest(),
        "external_requests": 0,
        "control_contexts": report,
        "closed_quote_excluded": True,
        "synthetic_route_privacy_tests": "see tests/test_portal.py and evidence/tests.xml",
    }
    (root / "evidence").mkdir(exist_ok=True)
    (root / "evidence/privacy.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "public_control_contexts": len(report),
                "external_requests": 0,
                "closed_quote_excluded": True,
            }
        )
    )


if __name__ == "__main__":
    main()
