import copy
import json

import pytest

from app.corpus import inspect
from app.knowledge import Knowledge, build


def write(tmp_path, corpus):
    source = tmp_path / "corpus.json"
    source.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    target = tmp_path / "knowledge.db"
    build(source, target)
    return source, Knowledge(target)


def test_filters_exact_versions_and_unique_cards(tmp_path, corpus):
    source, k = write(tmp_path, corpus)
    current = k.search("M-05")
    assert [(c["id"], c["version"]) for c in current["cards"]] == [("M-05", "2.0")]
    archive = k.search("M-05", statuses=["Архив"])
    assert archive["cards"][0]["version"] == "1.1"
    assert k.get("M-05", "1.1")["status"] == "Архив"
    with pytest.raises(ValueError):
        k.get("M-05", "9.9")
    result = k.search("лимиты каналов", path=["Section 0", "Subsection 0"])
    assert len(result["cards"]) == 3
    assert all(c["path"] == ["Section 0", "Subsection 0"] for c in result["cards"])
    assert len({(c["id"], c["version"]) for c in result["cards"]}) == 3


def test_failed_build_preserves_published_snapshot(tmp_path, corpus):
    source, k = write(tmp_path, corpus)
    before = k.metadata()
    corpus["sections"][0]["subsections"][0]["documents"][0]["visibility"] = "unknown"
    source.write_text(json.dumps(corpus), encoding="utf-8")
    with pytest.raises(ValueError):
        build(source, k.path)
    assert k.metadata() == before and k.get("M-05", "2.0")["version"] == "2.0"


@pytest.mark.parametrize(
    "mutation",
    [
        "visibility",
        "date",
        "duplicate_anchor",
        "duplicate_revision",
        "path",
        "reference",
    ],
)
def test_strict_source_rejects_invalid_input(corpus, mutation):
    doc = corpus["sections"][0]["subsections"][0]["documents"][0]
    if mutation == "visibility":
        doc.pop("visibility")
    elif mutation == "date":
        doc["date"] = "2026-02-30"
    elif mutation == "duplicate_anchor":
        doc["sections"][1]["anchor"] = "s01"
    elif mutation == "duplicate_revision":
        corpus["sections"][0]["subsections"][0]["documents"][1] = copy.deepcopy(doc)
    elif mutation == "path":
        doc["path"] = ["Wrong", "Path"]
    elif mutation == "reference":
        doc["links"] = ["Z-99@1.0"]
    with pytest.raises(ValueError):
        inspect(json.dumps(corpus).encode())


def test_escaped_duplicate_json_member_rejected(corpus):
    text = json.dumps(corpus).replace(
        '"schema_version": 1', '"schema_version": 1,"schema_versio\\u006e":1', 1
    )
    with pytest.raises(ValueError, match="duplicate JSON member"):
        inspect(text.encode())
