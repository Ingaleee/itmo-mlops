"""Versioned, portable contract for the index built into the container image."""
import hashlib
import importlib.metadata
import json

SCHEMA = "runbook-search-index/v2"
MODEL_CONFIG = {
    "word": {"ngram_range": [1, 2], "sublinear_tf": True},
    "char": {"analyzer": "char_wb", "ngram_range": [3, 5], "min_df": 1},
    "text_recipe": "title-body-tags-twice/v1",
    "normalization": "joint-l2",
}


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validate_documents(documents) -> None:
    if not isinstance(documents, list) or not documents:
        raise ValueError("corpus must contain documents")
    identifiers = set()
    for document in documents:
        if not isinstance(document, dict) or any(not isinstance(document.get(key), str) or not document[key].strip()
                                                 for key in ("id", "title", "body")):
            raise ValueError("document id, title and body must be non-empty strings")
        if not isinstance(document.get("tags"), list) or any(not isinstance(tag, str) for tag in document["tags"]):
            raise ValueError("document tags must be a list of strings")
        if document["id"] in identifiers:
            raise ValueError("duplicate document id")
        identifiers.add(document["id"])


def fingerprint(documents) -> dict:
    validate_documents(documents)
    contract = {
        "artifact_schema": SCHEMA,
        "corpus_sha256": hashlib.sha256(canonical_bytes(documents)).hexdigest(),
        "model_config": MODEL_CONFIG,
        "dependencies": {name: importlib.metadata.version(name) for name in ("scikit-learn", "numpy", "scipy", "joblib")},
    }
    return {**contract, "index_version": hashlib.sha256(canonical_bytes(contract)).hexdigest()[:12]}
