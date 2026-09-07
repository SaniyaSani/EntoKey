from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from diptera_id.embedding import DINOEmbedder
from diptera_id.hierarchy import load_classifier_bundle
from diptera_id.key_finder import KeyFinder, candidate_genera
from diptera_id.morphology import diagnostic_help
from diptera_id.retrieval import RetrievalIndex

MODEL_DIR = ROOT / os.getenv("DIPTERA_MODEL_DIR", "models")

app = FastAPI(title="Swiss Diptera ID Workbench", version="0.9.0")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")

_state = {"embedder": None, "classifiers": None, "retrieval": None}
KEY_FINDER = KeyFinder(ROOT / "data" / "key_catalog_v09.json", ROOT / "data" / "key_cache")


def artifacts_ready() -> bool:
    return all((MODEL_DIR / name).exists() for name in [
        "classifiers.joblib", "retrieval_vectors.npy", "retrieval_metadata.csv"
    ])


def get_models():
    if not artifacts_ready():
        raise HTTPException(
            status_code=503,
            detail="Real ML artifacts are not trained yet. Run build/download → embeddings → classifier training → retrieval index. No fake prediction is returned."
        )
    if _state["classifiers"] is None:
        _state["classifiers"] = load_classifier_bundle(MODEL_DIR / "classifiers.joblib")
    if _state["embedder"] is None:
        embedding = _state["classifiers"].metadata.get("embedding", {})
        _state["embedder"] = DINOEmbedder(
            embedding.get("backbone", "facebook/dinov3-vits16-pretrain-lvd1689m"),
            image_size=int(embedding.get("image_size", 512)),
        )
    if _state["retrieval"] is None:
        _state["retrieval"] = RetrievalIndex.load(MODEL_DIR)
    return _state["embedder"], _state["classifiers"], _state["retrieval"]


@app.get("/")
def root():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/health")
def health():
    embedding_config = {}
    config_path = MODEL_DIR / "embedding_config.json"
    if config_path.exists():
        import json
        embedding_config = json.loads(config_path.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "artifacts_ready": artifacts_ready(),
        "model_dir": str(MODEL_DIR),
        "backbone": embedding_config.get("backbone", "facebook/dinov3-vits16-pretrain-lvd1689m"),
        "embedding_shards": embedding_config.get("embedding_shards", 0),
        "key_finder": "curated+Crossref+OpenAlex",
    }


@app.get("/keys/search")
def search_keys(
    family: str = "",
    genera: list[str] = Query(default=[]),
    region: str = "Europe",
    live: bool = True,
):
    """Find candidate identification keys for the model's top genus hypotheses."""
    if not family.strip() and not any(value.strip() for value in genera):
        raise HTTPException(400, "Provide a family or at least one genus candidate")
    return KEY_FINDER.find(family, genera, region=region, live=live)


@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file")
    raw = await file.read()
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Could not decode image")

    embedder, classifiers, retrieval = get_models()
    embedding_config = classifiers.metadata.get("embedding", {})
    tile_grid = int(embedding_config.get("tile_grid", 1))
    include_whole = bool(embedding_config.get("include_whole", True))
    embedding = (
        embedder.embed_multicrop(image, tile_grid=tile_grid, include_whole=include_whole)
        if tile_grid > 1
        else embedder.embed_one(image)
    )
    predictions = classifiers.predict_all(embedding, top_k=5)
    neighbours = retrieval.search(embedding, k=8)
    open_set = getattr(classifiers, "last_open_set", {"rejected": False})

    best_family = predictions.get("family", [{}])[0].get("taxon") if predictions.get("family") else None
    diagnostics = diagnostic_help(
        best_family,
        ROOT / "data" / "morphology_rules.json",
        ROOT / "data" / "key_references.json",
    )
    genus_candidates = candidate_genera(predictions.get("genus", []))
    key_suggestions = KEY_FINDER.find(best_family, genus_candidates, live=False)

    # Conservative stopping rule: report the finest rank whose top score crosses threshold.
    thresholds = {"family": 0.40, "genus": 0.50, "species": 0.65}
    accepted_rank = None
    accepted_taxon = None
    for rank in ("family", "genus", "species"):
        candidates = predictions.get(rank) or []
        if open_set.get("rejected") and open_set.get("rank") == rank:
            break
        if candidates and candidates[0]["probability"] >= thresholds[rank]:
            accepted_rank = rank
            accepted_taxon = candidates[0]["taxon"]
        else:
            break

    return {
        "accepted": {"rank": accepted_rank, "taxon": accepted_taxon},
        "predictions": predictions,
        "open_set": open_set,
        "similar_specimens": neighbours,
        "diagnostics": diagnostics,
        "key_suggestions": key_suggestions,
        "warnings": [
            "Probabilities are model scores, not taxonomic certainty.",
            "A species suggestion should be verified with morphology and an appropriate key.",
            "Field photos and preserved specimens are different visual domains; check similar specimens and uncertainty before accepting a fine-rank suggestion.",
            "Anatomy segmentation is not required by the v0.8 baseline; morphology modules are optional verification tools."
        ]
    }
