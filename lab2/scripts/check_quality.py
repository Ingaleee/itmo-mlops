"""Preserve both reports and require the negative candidate to fail for quality."""
import json
import subprocess
import sys
from pathlib import Path


def main():
    evidence = Path("evidence")
    evidence.mkdir(exist_ok=True)
    for mode in ("normal", "reverse"):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate.py", "--artifact-dir", "artifacts", "--ranking-mode", mode],
            text=True, encoding="utf-8", capture_output=True,
        )
        (evidence / f"quality-{mode}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        report = json.loads(result.stdout)
        (evidence / f"quality-{mode}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if mode == "normal":
            assert result.returncode == 0 and report["mrr"] >= .85 and report["recall_at_3"] >= .90, report
        else:
            assert result.returncode == 1 and "quality gate failed" in result.stderr, result.stderr
            assert report["mrr"] < .85 or report["recall_at_3"] < .90, report
        print(json.dumps({"mode": mode, "exit_code": result.returncode, "mrr": report["mrr"], "recall_at_3": report["recall_at_3"]}))


if __name__ == "__main__":
    main()
