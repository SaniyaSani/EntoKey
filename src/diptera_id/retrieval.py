from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class RetrievalIndex:
    vectors: np.ndarray
    metadata: pd.DataFrame
    _faiss_index: object | None = None

    @classmethod
    def load(cls, model_dir: str | Path) -> "RetrievalIndex":
        model_dir = Path(model_dir)
        metadata = pd.read_csv(model_dir / "retrieval_metadata.csv")
        vectors = np.load(model_dir / "retrieval_vectors.npy").astype(np.float32)
        faiss_index = None
        index_path = model_dir / "retrieval.index"
        if index_path.exists():
            try:
                import faiss
                faiss_index = faiss.read_index(str(index_path))
            except Exception:
                faiss_index = None
        return cls(vectors=vectors, metadata=metadata, _faiss_index=faiss_index)

    def search(self, query: np.ndarray, k: int = 8) -> list[dict]:
        q = query.astype(np.float32)
        q = q / max(float(np.linalg.norm(q)), 1e-12)
        k = min(k, len(self.metadata))
        if k <= 0:
            return []

        if self._faiss_index is not None:
            scores, indices = self._faiss_index.search(q.reshape(1, -1), k)
            pairs = zip(indices[0], scores[0])
        else:
            scores = self.vectors @ q
            idx = np.argsort(scores)[::-1][:k]
            pairs = ((int(i), float(scores[i])) for i in idx)

        out = []
        for i, score in pairs:
            if i < 0:
                continue
            row = self.metadata.iloc[int(i)].to_dict()
            row["similarity"] = float(score)
            out.append(row)
        return out
