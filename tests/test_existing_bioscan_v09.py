from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_existing_bioscan_index_never_downloads_and_keeps_only_local_images(tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "KEEP-1.jpg").write_bytes(b"existing image bytes")
    selection = tmp_path / "selection.csv"
    pd.DataFrame([
        {"processid": "KEEP-1", "family": "Muscidae", "local_path": ""},
        {"processid": "MISSING-1", "family": "Tachinidae", "local_path": ""},
    ]).to_csv(selection, index=False)
    out = tmp_path / "downloaded.csv"
    report = tmp_path / "report.json"

    subprocess.run([
        sys.executable, str(ROOT / "scripts/index_existing_bioscan.py"),
        "--selection", str(selection), "--image-dir", str(image_dir),
        "--out-manifest", str(out), "--report", str(report), "--allow-partial",
    ], cwd=ROOT, check=True)

    indexed = pd.read_csv(out, dtype=str).fillna("")
    assert indexed["processid"].tolist() == ["KEEP-1"]
    assert indexed.iloc[0]["family"] == "Muscidae"
