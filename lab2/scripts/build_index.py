import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
from sklearn.pipeline import FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.index_contract import MODEL_CONFIG, fingerprint


def document_text(document: dict) -> str:
    return " ".join([document["title"], document["body"], " ".join(document["tags"] * 2)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=Path, default=Path("data/documents.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()

    documents = json.loads(args.documents.read_text(encoding="utf-8"))
    contract = fingerprint(documents)
    texts = [document_text(document) for document in documents]
    vectorizer = FeatureUnion([
        ("word", TfidfVectorizer(lowercase=True, ngram_range=tuple(MODEL_CONFIG["word"]["ngram_range"]),
                                sublinear_tf=MODEL_CONFIG["word"]["sublinear_tf"])),
        ("char", TfidfVectorizer(lowercase=True, analyzer=MODEL_CONFIG["char"]["analyzer"],
                                ngram_range=tuple(MODEL_CONFIG["char"]["ngram_range"]), min_df=MODEL_CONFIG["char"]["min_df"])),
    ])
    matrix = normalize(vectorizer.fit_transform(texts), norm="l2")
    # sklearn caches id(stop_words) for validation. A process address is not
    # model state and would make identical builds produce different bytes.
    # transform() recomputes this cache when needed after deserialization.
    for _, transformer in vectorizer.transformer_list:
        transformer.__dict__.pop("_stop_words_id", None)

    args.output.mkdir(parents=True, exist_ok=True)
    artifact_path = args.output / "search-index.joblib"
    joblib.dump({"vectorizer": vectorizer, "matrix": matrix, "documents": documents}, artifact_path)
    metadata = {
        **contract,
        "model_name": "runbook-hybrid-tfidf",
        "model_type": "tfidf-word-char-cosine",
        "artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        "documents": len(documents),
        "features": int(matrix.shape[1]),
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
