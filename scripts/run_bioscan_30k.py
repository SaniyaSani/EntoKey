#!/usr/bin/env python3
"""Run the resumable metadata-first BIOSCAN-5M Diptera 30k workflow."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def find_metadata(root: Path) -> Path:
    preferred = root / "bioscan5m" / "metadata" / "csv" / "BIOSCAN_5M_Insect_Dataset_metadata.csv"
    if preferred.exists():
        return preferred
    candidates = sorted(root.rglob("*metadata*.csv"))
    if not candidates:
        raise SystemExit(f"BIOSCAN metadata was not found under {root}")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/raw/bioscan")
    parser.add_argument("--max-records", type=int, default=30_000)
    parser.add_argument("--max-per-taxon", type=int, default=500)
    parser.add_argument("--min-rank", choices=("family", "genus", "species"), default="family")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--archive-config", default="configs/bioscan_archives_v06.json")
    parser.add_argument("--skip-metadata-download", action="store_true")
    parser.add_argument("--selection-only", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument(
        "--no-suffix-range",
        action="store_true",
        help="Fallback for proxies that reject HTTP suffix ranges (uses HEAD + absolute ranges)",
    )
    args = parser.parse_args()

    store = Path(args.root).expanduser().resolve()
    store.mkdir(parents=True, exist_ok=True)
    selection = store / "diptera_30k_selection.csv"
    selection_report = store / "diptera_30k_selection_report.json"
    images = store / "diptera_30k_images"
    downloaded = store / "diptera_30k_downloaded.csv"
    download_report = store / "diptera_30k_download_report.json"
    download_progress = store / "diptera_30k_progress.json"
    normalized = store / "bioscan_diptera_30k_manifest.parquet"

    if not args.skip_metadata_download:
        run(sys.executable, "scripts/download_bioscan.py", "--root", str(store), "--split", "all")
    metadata = find_metadata(store)
    print("BIOSCAN metadata:", metadata)

    if not selection.exists():
        run(
            sys.executable,
            "scripts/select_bioscan_diptera.py",
            "--metadata", str(metadata),
            "--out", str(selection),
            "--report", str(selection_report),
            "--image-dir", str(images),
            "--max-records", str(args.max_records),
            "--max-per-taxon", str(args.max_per_taxon),
            "--min-rank", args.min_rank,
            "--seed", str(args.seed),
        )
    else:
        print("Selection already exists; keeping it for reproducibility:", selection)

    if args.selection_only:
        print("Selection-only mode complete; no image bytes were downloaded.")
        return

    command = [
        sys.executable,
        "scripts/download_bioscan_subset.py",
        "--selection", str(selection),
        "--archive-config", str(Path(args.archive_config).expanduser().resolve()),
        "--image-dir", str(images),
        "--out-manifest", str(downloaded),
        "--report", str(download_report),
        "--progress", str(download_progress),
    ]
    if args.allow_partial:
        command.append("--allow-partial")
    if args.no_suffix_range:
        command.append("--no-suffix-range")
    run(*command)
    run(
        sys.executable,
        "scripts/ingest_bioscan.py",
        "--metadata", str(downloaded),
        "--out", str(normalized),
    )
    print("BIOSCAN 30k READY:", normalized)


if __name__ == "__main__":
    main()
