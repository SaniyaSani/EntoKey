from __future__ import annotations

import json
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from scripts.download_inat_metadata import extract_selected
from scripts.train_multidomain import balanced_weights, top_k_accuracy


def test_inat_archive_extracts_only_expected_files(tmp_path: Path):
    archive = tmp_path / "metadata.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name in ("folder/observations.csv.gz", "photos.csv.gz", "taxa.csv.gz", "observers.csv.gz", "ignore.txt"):
            payload = name.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            bundle.addfile(info, BytesIO(payload))
    out = tmp_path / "out"
    paths = extract_selected(archive, out)
    assert {path.name for path in paths} == {"observations.csv.gz", "photos.csv.gz", "taxa.csv.gz", "observers.csv.gz"}
    assert not (out / "ignore.txt").exists()


def test_multidomain_weights_and_topk():
    labels = np.array(["A", "A", "A", "B"])
    sources = np.array(["inat", "inat", "inat", "bioscan"])
    weights = balanced_weights(labels, sources)
    assert weights[-1] > weights[0]
    probabilities = np.array([[0.8, 0.2], [0.3, 0.7]])
    assert top_k_accuracy(np.array(["A", "B"]), probabilities, np.array(["A", "B"]), 1) == 1.0


def test_colab_notebook_is_valid_json():
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/Diptera_Training_Colab.ipynb").read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 5


def test_multidomain_trainer_writes_real_models(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    labels = ["Syrphidae"] * 6 + ["Muscidae"] * 6
    splits = ["train"] * 4 + ["val"] * 2 + ["train"] * 4 + ["val"] * 2
    frame = pd.DataFrame({
        "family": labels,
        "genus": ["Eristalis"] * 6 + ["Musca"] * 6,
        "species": ["Eristalis tenax"] * 6 + ["Musca domestica"] * 6,
        "source": ["iNaturalist", "BIOSCAN-5M"] * 6,
        "split": splits,
        "split_group": [f"g-{index}" for index in range(12)],
    })
    frame.to_csv(tmp_path / "embedded_manifest.csv", index=False)
    vectors = np.vstack([
        np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (6, 1)),
        np.tile(np.array([[0.0, 1.0]], dtype=np.float32), (6, 1)),
    ])
    np.save(tmp_path / "embeddings.npy", vectors)
    subprocess.run([
        sys.executable, str(root / "scripts/train_multidomain.py"),
        "--model-dir", str(tmp_path), "--min-images-per-class", "2",
    ], cwd=root, check=True)
    payload = joblib.load(tmp_path / "classifiers_multidomain.joblib")
    assert set(payload["models"]) == {"family", "genus", "species"}
    assert payload["metadata"]["evaluation"]["family"]["top1_accuracy"] == 1.0
