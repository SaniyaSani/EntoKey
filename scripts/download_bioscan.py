#!/usr/bin/env python3
"""Download BIOSCAN-5M metadata only unless full images are explicitly requested.

The safe default is intentionally metadata-only.  Use
``select_bioscan_diptera.py`` followed by ``download_bioscan_subset.py`` to get
the 30k Diptera subset without downloading the complete image packages.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/raw/bioscan")
    parser.add_argument("--no-download", action="store_true", help="Open an existing package instead of downloading")
    parser.add_argument(
        "--full-images",
        action="store_true",
        help="Explicitly download complete cropped_256 image archives for the selected split",
    )
    parser.add_argument("--split", default="all", help="BIOSCAN split; metadata-only mode safely supports all")
    args = parser.parse_args()
    try:
        from bioscan_dataset import BIOSCAN5M
    except ImportError as exc:
        raise SystemExit("Install the official loader first: pip install bioscan-dataset") from exc

    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.full_images:
        dataset = BIOSCAN5M(
            str(root),
            split=args.split,
            modality=("image", "dna"),
            target_type=[],
            download=not args.no_download,
        )
        print(dataset)
    elif not args.no_download:
        # Calling BIOSCAN5M(...) would immediately load all 5M rows into a
        # DataFrame after downloading.  Download/extract the official metadata
        # resource directly so selection can remain streaming and RAM-safe.
        from torchvision.datasets.utils import check_integrity, download_and_extract_archive

        metadata_path = root / BIOSCAN5M.base_folder / BIOSCAN5M.meta["filename"]
        if check_integrity(str(metadata_path), BIOSCAN5M.meta["csv_md5"]):
            print("BIOSCAN metadata already downloaded and verified:", metadata_path)
        else:
            download_and_extract_archive(
                BIOSCAN5M.meta["urls"][0],
                str(root),
                md5=BIOSCAN5M.meta["archive_md5"],
            )
            if not check_integrity(str(metadata_path), BIOSCAN5M.meta["csv_md5"]):
                raise SystemExit("BIOSCAN metadata checksum failed after extraction")
            print("BIOSCAN metadata downloaded and verified:", metadata_path)
    metadata = sorted(root.rglob("*metadata*.csv"))
    print(f"BIOSCAN root: {root}")
    if metadata:
        for path in metadata:
            print(f"metadata candidate: {path}")
    else:
        print("No metadata CSV was auto-detected; inspect the package root and pass the official CSV to ingest_bioscan.py")
    if not args.full_images:
        print("Metadata-only mode: no BIOSCAN image archive was downloaded.")


if __name__ == "__main__":
    main()
