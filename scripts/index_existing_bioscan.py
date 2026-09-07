#!/usr/bin/env python3
"""Index BIOSCAN images already present on disk without downloading anything."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


PROCESS_ID_FIELDS = ("processid", "process_id", "sampleid", "sample_id", "specimen_id")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def first(row: dict, names: tuple[str, ...]) -> str:
    for name in names:
        value = str(row.get(name, "")).strip()
        if value and value.casefold() != "nan":
            return value
    return ""


def existing_image(row: dict, image_dir: Path) -> Path | None:
    supplied = str(row.get("local_path", "")).strip()
    if supplied and supplied.casefold() != "nan" and Path(supplied).expanduser().is_file():
        return Path(supplied).expanduser().resolve()
    process_id = first(row, PROCESS_ID_FIELDS)
    if not process_id:
        return None
    for suffix in IMAGE_EXTENSIONS:
        candidate = image_dir / f"{process_id}{suffix}"
        if candidate.is_file():
            return candidate.resolve()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--out-manifest", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    selection = Path(args.selection).expanduser().resolve()
    image_dir = Path(args.image_dir).expanduser().resolve()
    frame = pd.read_csv(selection, dtype=str).fillna("")
    existing_rows: list[dict] = []
    missing = 0
    for row in frame.to_dict(orient="records"):
        path = existing_image(row, image_dir)
        if path is None:
            missing += 1
            continue
        row["local_path"] = str(path)
        existing_rows.append(row)

    out = Path(args.out_manifest).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(existing_rows, columns=frame.columns).to_csv(out, index=False)
    report = {
        "mode": "reuse_existing_only",
        "network_downloads": 0,
        "selection_rows": len(frame),
        "existing_images": len(existing_rows),
        "missing_images": missing,
    }
    report_path = Path(args.report).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"existing BIOSCAN manifest -> {out}")
    if not existing_rows:
        raise SystemExit("no existing BIOSCAN images matched the selection")
    if missing and not args.allow_partial:
        raise SystemExit(f"{missing} selected BIOSCAN images are missing; use --allow-partial to index only existing files")


if __name__ == "__main__":
    main()
