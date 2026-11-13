"""Export permitted public records, replacing the complete closed record."""

import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.corpus import inspect


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpus", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    raw = args.corpus.read_bytes()
    inspect(raw)
    original = json.loads(raw.decode("utf-8-sig"))
    fixture = copy.deepcopy(original)
    closed = []
    replaced = 0
    for section in fixture["sections"]:
        for sub in section["subsections"]:
            for n, doc in enumerate(sub["documents"]):
                if doc["visibility"] == "cloud_ok":
                    continue
                closed.extend(
                    [doc["title"], *[p for s in doc["sections"] for p in s["body"]]]
                )
                # Keep only already-public identity/path needed by the strict
                # schema. No title, owner, date, links, quotes or derived text.
                sub["documents"][n] = {
                    "id": doc["id"],
                    "version": doc["version"],
                    "title": "Synthetic private document fixture",
                    "status": "Действует",
                    "date": "2026-01-01",
                    "owner": "Synthetic fixture",
                    "visibility": "local_only",
                    "path": [section["title"], sub["title"]],
                    "replaces": None,
                    "links": [],
                    "sections": [
                        {
                            "anchor": f"s{i:02}",
                            "title": f"Synthetic section {i}",
                            "body": [
                                "Synthetic private test content, generated for CI. Not an original document."
                            ],
                        }
                        for i in range(1, 6)
                    ],
                }
                replaced += 1
    assert replaced == 1
    fixture["title"] = (
        "Public acceptance fixture: 35 permitted records and one synthetic private record"
    )
    rendered = json.dumps(fixture, ensure_ascii=False, indent=2) + "\n"
    assert all(text not in rendered for text in closed)
    inspect(rendered.encode())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "passed",
                "public_records": 35,
                "synthetic_replacements": 1,
                "closed_original_title_and_paragraphs_absent": True,
            }
        )
    )


if __name__ == "__main__":
    main()
