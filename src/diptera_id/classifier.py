from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

RANKS = ("family", "genus", "species")


@dataclass
class ClassifierBundle:
    models: dict[str, Any]
    metadata: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "ClassifierBundle":
        payload = joblib.load(path)
        return cls(models=payload["models"], metadata=payload.get("metadata", {}))

    def predict_rank(self, rank: str, embedding: np.ndarray, top_k: int = 5) -> list[dict[str, float | str]]:
        model = self.models.get(rank)
        if model is None:
            return []
        probs = model.predict_proba(embedding.reshape(1, -1))[0]
        classes = model.classes_
        order = np.argsort(probs)[::-1][:top_k]
        return [
            {"taxon": str(classes[i]), "probability": float(probs[i])}
            for i in order
        ]

    def predict_all(self, embedding: np.ndarray, top_k: int = 5) -> dict[str, list[dict[str, float | str]]]:
        return {rank: self.predict_rank(rank, embedding, top_k=top_k) for rank in RANKS}
