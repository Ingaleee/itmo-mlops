import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.index_contract import fingerprint
from app.search import SearchEngine


def test_cosine_scores_and_stable_ties():
    engine = SearchEngine(Path("artifacts"))
    for query in ("rollback helm", "как откатить модель", "completely out of vocabulary 98765"):
        results = engine.search(query, 10)
        assert all(0 <= item["score"] <= 1 for item in results)
    assert engine._rank(np.zeros(4)).tolist() == [0, 1, 2, 3]


@pytest.mark.parametrize("mode", ["normal", "reverse"])
def test_recommendations_never_include_the_source_document(mode):
    engine = SearchEngine(Path("artifacts"), mode)
    results = engine.recommend("doc-rollback", 10)
    assert len(results) == 10
    assert "doc-rollback" not in {item["id"] for item in results}


def test_unknown_mode_fails_closed():
    with pytest.raises(ValueError, match="ranking mode"):
        SearchEngine(Path("artifacts"), "typo")


def test_corruption_is_rejected_before_deserialization(tmp_path, monkeypatch):
    shutil.copytree("artifacts", tmp_path / "index")
    artifact = tmp_path / "index/search-index.joblib"
    artifact.write_bytes(artifact.read_bytes() + b"corrupted")
    monkeypatch.setattr("app.search.joblib.load", lambda _: pytest.fail("corrupt artifact was deserialized"))
    with pytest.raises(ValueError, match="checksum"):
        SearchEngine(tmp_path / "index")


def test_metadata_cannot_claim_another_index(tmp_path):
    shutil.copytree("artifacts", tmp_path / "index")
    path = tmp_path / "index/metadata.json"
    metadata = json.loads(path.read_text())
    metadata["index_version"] = "000000000000"
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="contract"):
        SearchEngine(tmp_path / "index")


def test_corpus_identity_ignores_json_formatting_and_rejects_duplicate_ids():
    documents = json.loads(Path("data/documents.json").read_text())
    assert fingerprint(documents) == fingerprint(json.loads(json.dumps(documents, indent=4)))
    changed = json.loads(json.dumps(documents))
    changed[0]["body"] += " changed"
    assert fingerprint(changed)["index_version"] != fingerprint(documents)["index_version"]
    with pytest.raises(ValueError, match="duplicate"):
        fingerprint(documents + [documents[0]])


def test_index_build_is_reproducible(tmp_path):
    subprocess.run([sys.executable, "scripts/build_index.py", "--output", str(tmp_path)], check=True)
    assert json.loads((tmp_path / "metadata.json").read_text()) == json.loads(Path("artifacts/metadata.json").read_text())
