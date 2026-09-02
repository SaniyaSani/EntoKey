#!/usr/bin/env python3
"""Export a bounded Diptera subset from the official bioscan-dataset package.

The exporter saves selected images plus a flat metadata CSV that can be passed
directly to ``ingest_bioscan.py``.  Defaults are deliberately pilot-sized.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "bioscan"


def find_column(frame: pd.DataFrame, *names: str) -> str | None:
    lookup = {str(column).lower(): str(column) for column in frame.columns}
    return next((lookup[name.lower()] for name in names if name.lower() in lookup), None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/raw/bioscan")
    parser.add_argument("--split", default="train", help="train/val/test/pretrain or an official held-out split")
    parser.add_argument("--image-package", default="cropped_256")
    parser.add_argument("--out-metadata", default="data/raw/bioscan/diptera_metadata.csv")
    parser.add_argument("--image-dir", default="data/raw/bioscan/diptera_images")
    parser.add_argument("--max-records", type=int, default=5000)
    parser.add_argument("--allow-unbounded", action="store_true", help="Required when max-records=0")
    parser.add_argument("--download", action="store_true", help="Allow official package downloads")
    args = parser.parse_args()
    if args.max_records == 0 and not args.allow_unbounded:
        raise SystemExit("Refusing an unbounded export; pass --allow-unbounded explicitly")

    try:
        from bioscan_dataset import BIOSCAN5M
    except ImportError as exc:
        raise SystemExit("Install the optional downloader: pip install -r requirements-downloaders.txt") from exc

    dataset = BIOSCAN5M(
        root=args.root,
        split=args.split,
        modality=("image", "dna"),
        image_package=args.image_package,
        target_type=["family", "genus", "species", "dna_bin"],
        target_format="text",
        output_format="dict",
        download=args.download,
    )
    metadata = dataset.metadata.copy().fillna("")
    order_column = find_column(metadata, "order", "taxon_order")
    if not order_column:
        raise SystemExit("BIOSCAN metadata does not expose an order column")
    mask = metadata[order_column].astype(str).str.casefold() == "diptera"
    selected = [position for position, keep in enumerate(mask.tolist()) if keep]
    if args.max_records:
        selected = selected[: args.max_records]

    image_dir = Path(args.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for position, index in enumerate(selected, start=1):
        sample = dataset[index]
        row = metadata.iloc[index].to_dict()
        process_id = str(
            row.get("processid")
            or row.get("process_id")
            or row.get("sampleid")
            or row.get("sample_id")
            or f"{args.split}-{index}"
        )
        path = image_dir / f"{safe_name(process_id)}.jpg"
        image = sample.get("image") if isinstance(sample, dict) else None
        if image is None:
            raise SystemExit("BIOSCAN sample did not contain image modality")
        if hasattr(image, "save"):
            image.convert("RGB").save(path, quality=95)
        else:
            from PIL import Image

            Image.fromarray(image).convert("RGB").save(path, quality=95)
        row["local_path"] = str(path.resolve())
        row["source_split"] = args.split
        row["split"] = args.split
        if isinstance(sample, dict) and sample.get("dna"):
            row["dna_barcode"] = sample["dna"]
        targets = sample.get("target", {}) if isinstance(sample, dict) else {}
        if isinstance(targets, dict):
            for key, value in targets.items():
                if value not in (None, ""):
                    row[key] = value
        rows.append(row)
        if position % 250 == 0:
            print(f"exported BIOSCAN Diptera: {position}/{len(selected)}", end="\r")

    out = Path(args.out_metadata)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nexported {len(rows)} BIOSCAN Diptera specimens -> {out}")


if __name__ == "__main__":
    main()
