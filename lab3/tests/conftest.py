from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture
def corpus():
    docs = []
    for i in range(36):
        archived = i == 34
        current = i == 35
        doc_id = "M-05" if archived or current else f"A-{i + 1:02}"
        docs.append(
            {
                "id": doc_id,
                "version": "1.1" if archived else "2.0" if current else "1.0",
                "title": "Synthetic search fixture " + doc_id,
                "status": "Архив" if archived else "Действует",
                "date": "2026-09-01" if archived else "2026-10-01",
                "owner": "Fixture",
                "visibility": "local_only" if i == 0 else "cloud_ok",
                "path": [],
                "replaces": "M-05@1.1" if current else None,
                "links": [],
                "sections": [
                    {
                        "anchor": "s01",
                        "title": "Fixture section",
                        "body": [
                            "Синтетический лимит канала 5000. Приглашения не занимают место."
                        ],
                    },
                    {
                        "anchor": "s02",
                        "title": "Second section",
                        "body": ["Synthetic second paragraph."],
                    },
                ],
            }
        )
    sections = []
    for s in range(6):
        section = {"title": f"Section {s}", "subsections": []}
        for sub in range(2):
            subset = docs[(s * 2 + sub) * 3 : (s * 2 + sub + 1) * 3]
            for doc in subset:
                doc["path"] = [section["title"], f"Subsection {sub}"]
            section["subsections"].append(
                {"title": f"Subsection {sub}", "documents": subset}
            )
        sections.append(section)
    return {
        "schema_version": 1,
        "title": "Synthetic fixture corpus",
        "sections": sections,
    }
