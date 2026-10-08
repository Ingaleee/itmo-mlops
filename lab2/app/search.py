import json
import hashlib
import re
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics.pairwise import linear_kernel
from sklearn.preprocessing import normalize

from app.index_contract import fingerprint


class SearchEngine:
    def __init__(self, artifact_dir: Path, ranking_mode: str = "normal") -> None:
        if ranking_mode not in ("normal", "reverse"):
            raise ValueError("unsupported ranking mode")
        self.metadata = json.loads((artifact_dir / "metadata.json").read_text(encoding="utf-8"))
        artifact_path = artifact_dir / "search-index.joblib"
        expected = self.metadata.get("artifact_sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != expected:
            raise ValueError("index artifact checksum mismatch")
        # The artifact is built from trusted source into the immutable image.
        # A checksum detects corruption; it does not make untrusted pickle safe.
        bundle = joblib.load(artifact_path)
        self.vectorizer = bundle["vectorizer"]
        self.matrix = bundle["matrix"]
        self.documents = bundle["documents"]
        self.ranking_mode = ranking_mode
        self.by_id = {document["id"]: index for index, document in enumerate(self.documents)}
        contract = fingerprint(self.documents)
        if any(self.metadata.get(key) != value for key, value in contract.items()):
            raise ValueError("index metadata contract mismatch")
        if self.matrix.shape != (len(self.documents), self.metadata["features"]) or self.metadata["documents"] != len(self.documents):
            raise ValueError("index dimensions mismatch")
        if not np.isfinite(self.matrix.data).all():
            raise ValueError("index contains non-finite scores")
        lengths = np.asarray(self.matrix.multiply(self.matrix).sum(axis=1)).ravel()
        if not np.allclose(lengths, 1.0, atol=1e-6):
            raise ValueError("index vectors must have unit length")

    def _rank(self, scores: np.ndarray) -> np.ndarray:
        if self.ranking_mode == "reverse":
            return np.argsort(scores, kind="stable")
        return np.argsort(-scores, kind="stable")

    def search(self, query: str, limit: int = 5) -> list[dict]:
        query_vector = normalize(self.vectorizer.transform([query]), norm="l2")
        scores = linear_kernel(query_vector, self.matrix).ravel()
        return [self._result(index, scores[index]) for index in self._rank(scores)[:limit]]

    def recommend(self, document_id: str, limit: int = 3) -> list[dict]:
        if document_id not in self.by_id:
            raise KeyError(document_id)
        index = self.by_id[document_id]
        scores = linear_kernel(self.matrix[index], self.matrix).ravel()
        ranked = [i for i in self._rank(scores) if i != index]
        return [self._result(i, scores[i]) for i in ranked[:limit]]

    def _result(self, index: int, score: float) -> dict:
        document = self.documents[int(index)]
        return {
            "id": document["id"],
            "title": document["title"],
            "tags": document["tags"],
            "score": round(float(score), 6),
            "summary": document["body"][:240],
        }
