from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np


def _candidate_rows(model: Any, gate: dict, embedding: np.ndarray, top_k: int) -> list[dict]:
    probabilities = model.predict_proba(embedding.reshape(1, -1))[0]
    order = np.argsort(probabilities)[::-1][:top_k]
    rows: list[dict] = []
    for index in order:
        taxon = str(model.classes_[index])
        gate_item = gate.get(taxon, {})
        centroid = np.asarray(gate_item.get("centroid", []), dtype=np.float32)
        similarity = float(centroid @ embedding) if centroid.size else None
        rows.append({
            "taxon": taxon,
            "probability": float(probabilities[index]),
            "centroid_similarity": similarity,
            "open_set_threshold": gate_item.get("threshold"),
        })
    return rows


def _rejected(candidate: dict | None) -> bool:
    if not candidate:
        return True
    similarity = candidate.get("centroid_similarity")
    threshold = candidate.get("open_set_threshold")
    return similarity is not None and threshold is not None and similarity < threshold


@dataclass
class HierarchicalClassifierBundle:
    family_model: Any
    genus_by_family: dict[str, Any]
    species_by_genus: dict[str, Any]
    gates: dict[str, Any]
    metadata: dict[str, Any]
    last_open_set: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "HierarchicalClassifierBundle":
        payload = joblib.load(path)
        models = payload["hierarchical_models"]
        return cls(
            family_model=models["family"],
            genus_by_family=models.get("genus_by_family", {}),
            species_by_genus=models.get("species_by_genus", {}),
            gates=payload.get("gates", {}),
            metadata=payload.get("metadata", {}),
        )

    def predict_all(self, embedding: np.ndarray, top_k: int = 5) -> dict[str, list[dict]]:
        embedding = embedding.astype(np.float32)
        embedding /= max(float(np.linalg.norm(embedding)), 1e-12)
        family = _candidate_rows(
            self.family_model,
            self.gates.get("family", {}),
            embedding,
            top_k,
        )
        predictions = {"family": family, "genus": [], "species": []}
        self.last_open_set = {"rejected": False, "rank": None, "taxon": None, "reason": None}
        if not family or _rejected(family[0]):
            self.last_open_set = {
                "rejected": True,
                "rank": "family",
                "taxon": family[0]["taxon"] if family else None,
                "reason": "embedding_outside_known_family_distribution",
            }
            return predictions

        family_name = family[0]["taxon"]
        genus_model = self.genus_by_family.get(family_name)
        if genus_model is None:
            return predictions
        genus = _candidate_rows(
            genus_model,
            self.gates.get("genus_by_family", {}).get(family_name, {}),
            embedding,
            top_k,
        )
        predictions["genus"] = genus
        if not genus or _rejected(genus[0]):
            self.last_open_set = {
                "rejected": True,
                "rank": "genus",
                "taxon": genus[0]["taxon"] if genus else None,
                "reason": "embedding_outside_known_genus_distribution",
            }
            return predictions

        genus_name = genus[0]["taxon"]
        key = f"{family_name}\x1f{genus_name}"
        species_model = self.species_by_genus.get(key)
        if species_model is None:
            return predictions
        species = _candidate_rows(
            species_model,
            self.gates.get("species_by_genus", {}).get(key, {}),
            embedding,
            top_k,
        )
        predictions["species"] = species
        if species and _rejected(species[0]):
            self.last_open_set = {
                "rejected": True,
                "rank": "species",
                "taxon": species[0]["taxon"],
                "reason": "embedding_outside_known_species_distribution",
            }
        return predictions


def load_classifier_bundle(path: str | Path):
    payload = joblib.load(path)
    if payload.get("bundle_type") == "hierarchical_v1":
        models = payload["hierarchical_models"]
        return HierarchicalClassifierBundle(
            family_model=models["family"],
            genus_by_family=models.get("genus_by_family", {}),
            species_by_genus=models.get("species_by_genus", {}),
            gates=payload.get("gates", {}),
            metadata=payload.get("metadata", {}),
        )
    from .classifier import ClassifierBundle

    return ClassifierBundle(models=payload["models"], metadata=payload.get("metadata", {}))
