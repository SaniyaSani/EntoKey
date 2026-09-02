from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from diptera_id.classifier import ClassifierBundle
from diptera_id.embedding import DINOEmbedder
from diptera_id.morphology import diagnostic_help
from diptera_id.retrieval import RetrievalIndex

MODEL_DIR = ROOT / os.getenv("DIPTERA_MODEL_DIR", "models")

app = FastAPI(title="Swiss Diptera ID Workbench", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")

_state = {"embedder": None, "classifiers": None, "retrieval": None}


def artifacts_ready() -> bool:
    return all((MODEL_DIR / name).exists() for name in [
        "classifiers.joblib", "retrieval_vectors.npy", "retrieval_metadata.csv"
    ])


def get_models():
    if not artifacts_ready():
        raise HTTPException(
            status_code=503,
            detail="Real ML artifacts are not trained yet. Run build/download → embed_dataset.py → train_classifiers.py → build_retrieval_index.py. No fake prediction is returned."
        )
    if _state["embedder"] is None:
        _state["embedder"] = DINOEmbedder("facebook/dinov2-small")
    if _state["classifiers"] is None:
        _state["classifiers"] = ClassifierBundle.load(MODEL_DIR / "classifiers.joblib")
    if _state["retrieval"] is None:
        _state["retrieval"] = RetrievalIndex.load(MODEL_DIR)
    return _state["embedder"], _state["classifiers"], _state["retrieval"]


@app.get("/")
def root():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/health")
def health():
    return {
        "ok": True,
        "artifacts_ready": artifacts_ready(),
        "model_dir": str(MODEL_DIR),
        "backbone": "facebook/dinov2-small"
    }


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
    embedding = embedder.embed_one(image)
    predictions = classifiers.predict_all(embedding, top_k=5)
    neighbours = retrieval.search(embedding, k=8)

    best_family = predictions.get("family", [{}])[0].get("taxon") if predictions.get("family") else None
    diagnostics = diagnostic_help(
        best_family,
        ROOT / "data" / "morphology_rules.json",
        ROOT / "data" / "key_references.json",
    )

    # Conservative stopping rule: report the finest rank whose top score crosses threshold.
    thresholds = {"family": 0.55, "genus": 0.60, "species": 0.72}
    accepted_rank = None
    accepted_taxon = None
    for rank in ("family", "genus", "species"):
        candidates = predictions.get(rank) or []
        if candidates and candidates[0]["probability"] >= thresholds[rank]:
            accepted_rank = rank
            accepted_taxon = candidates[0]["taxon"]
        else:
            break

    return {
        "accepted": {"rank": accepted_rank, "taxon": accepted_taxon},
        "predictions": predictions,
        "similar_specimens": neighbours,
        "diagnostics": diagnostics,
        "warnings": [
            "Probabilities are model scores, not taxonomic certainty.",
            "A species suggestion should be verified with morphology and an appropriate key.",
            "Pinned/microscope specimens may differ substantially from field-photo training data."
        ]
    }
