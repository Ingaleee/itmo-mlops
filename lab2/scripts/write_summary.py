"""A compact reviewer-facing index into preserved delivery evidence."""
import json
import os
from pathlib import Path


def main():
    rows = ["## Release verification", "", "| Environment | Index | Image digest | Quality |", "|---|---|---|---|"]
    for suffix in ("staging", "prod"):
        directory = Path(f"evidence/esolovev-search-{suffix}/normal/candidate")
        if not (directory / "meta.json").exists():
            continue
        meta = json.loads((directory / "meta.json").read_text())
        quality = json.loads((directory / "quality.json").read_text()) if (directory / "quality.json").exists() else {}
        rows.append(f"| {meta['environment']} | `{meta['index_version']}` | `{meta['image_digest']}` | MRR={quality.get('mrr', 'unavailable')}, hit rate={quality.get('hit_rate_at_3', 'unavailable')} |")
    rollback = Path("evidence/esolovev-search-prod/reverse/rollback.json")
    if rollback.exists():
        data = json.loads(rollback.read_text())
        rows += ["", f"Rollback verified: **{data['rollback_verified']}**; restored revision **{data['restored_revision']}**.",
                 f"Cause: `{data['cause']['kind']}`; restored digest: `{data['restored_digest']}`."]
    rows += ["", "The artifact contains API metadata, quality reports, manifests, Helm history, the rejected release and restored release checks."]
    with Path(os.environ.get("GITHUB_STEP_SUMMARY", "evidence/summary.md")).open("a", encoding="utf-8") as output:
        output.write("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
