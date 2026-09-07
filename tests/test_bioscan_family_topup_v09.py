from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def row(process_id: str, family: str, split: str = "train") -> dict:
    return {
        "processid": process_id,
        "order": "Diptera",
        "family": family,
        "genus": family.removesuffix("idae") + "genus",
        "species": family.removesuffix("idae") + "genus species",
        "split": split,
        "source_split": split,
        "chunk": "aa",
        "archive_group": "train",
        "archive_member": f"{split}/aa/{process_id}.jpg",
        "local_path": "",
    }


def test_target_family_topup_counts_existing_and_selects_only_missing_targets(tmp_path: Path):
    images = tmp_path / "images"
    images.mkdir()
    Image.new("RGB", (16, 16), "gray").save(images / "M-EXISTING.jpg")
    base_rows = [row("M-EXISTING", "Muscidae"), row("P-EXISTING", "Phoridae")]
    base = tmp_path / "base.csv"
    pd.DataFrame(base_rows).to_csv(base, index=False)
    metadata_rows = base_rows + [
        row("M-NEW", "Muscidae"),
        row("T-NEW-1", "Tachinidae"),
        row("T-NEW-2", "Tachinidae", "val"),
        row("S-NOT-TARGET", "Sciaridae"),
    ]
    metadata = tmp_path / "metadata.csv"
    pd.DataFrame(metadata_rows).to_csv(metadata, index=False)
    out = tmp_path / "topup.csv"
    report = tmp_path / "report.json"

    subprocess.run([
        sys.executable, str(ROOT / "scripts/select_bioscan_family_topup.py"),
        "--metadata", str(metadata), "--base-selection", str(base),
        "--image-dir", str(images), "--families", "Muscidae,Tachinidae",
        "--min-per-family", "2", "--max-per-taxon", "10",
        "--out", str(out), "--report", str(report), "--chunksize", "2",
    ], cwd=ROOT, check=True)

    selected = pd.read_csv(out, dtype=str, keep_default_na=False)
    assert selected.groupby("family").size().to_dict() == {"Muscidae": 2, "Tachinidae": 2}
    assert "S-NOT-TARGET" not in set(selected["processid"])
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["by_family"]["Muscidae"]["existing_valid"] == 1
    assert payload["network_downloads_during_selection"] == 0


def test_merge_bioscan_manifests_preserves_old_rows_and_deduplicates(tmp_path: Path):
    old = tmp_path / "old.csv"
    topup = tmp_path / "topup.csv"
    out = tmp_path / "merged.csv"
    pd.DataFrame([
        {"processid": "OLD-1", "family": "Phoridae"},
        {"processid": "M-1", "family": "Muscidae"},
    ]).to_csv(old, index=False)
    pd.DataFrame([
        {"processid": "M-1", "family": "Muscidae"},
        {"processid": "T-1", "family": "Tachinidae"},
    ]).to_csv(topup, index=False)
    subprocess.run([
        sys.executable, str(ROOT / "scripts/merge_bioscan_manifests.py"),
        str(old), str(topup), "--out", str(out),
    ], cwd=ROOT, check=True)
    assert set(pd.read_csv(out)["processid"]) == {"OLD-1", "M-1", "T-1"}
