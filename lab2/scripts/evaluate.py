import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.search import SearchEngine
from app.evaluation import summarize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--eval", type=Path, default=Path("data/eval.json"))
    parser.add_argument("--ranking-mode", choices=["normal", "reverse"], default="normal")
    parser.add_argument("--min-mrr", type=float, default=0.85)
    parser.add_argument("--min-recall-at-3", type=float, default=0.90)
    args = parser.parse_args()

    engine = SearchEngine(args.artifact_dir, args.ranking_mode)
    cases = json.loads(args.eval.read_text(encoding="utf-8"))
    rankings = []
    for case in cases:
        ids = [item["id"] for item in engine.search(case["query"], 3)]
        if any(identifier not in engine.by_id for identifier in case["relevant"]):
            raise ValueError("evaluation labels refer to a missing document")
        rankings.append(ids)

    report = {
        "ranking_mode": args.ranking_mode,
        "index_version": engine.metadata["index_version"],
        "artifact_sha256": engine.metadata["artifact_sha256"],
        **summarize(cases, rankings),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["mrr"] < args.min_mrr or report["recall_at_3"] < args.min_recall_at_3:
        raise SystemExit("quality gate failed")


if __name__ == "__main__":
    main()
