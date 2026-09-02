#!/usr/bin/env python3
"""Create/append manifest rows for your own verified museum or microscope specimens."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diptera_id.corpus.schema import MASTER_COLUMNS, finalize_record

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image-dir", required=True)
    p.add_argument("--family", required=True)
    p.add_argument("--genus", default="")
    p.add_argument("--species", default="")
    p.add_argument("--collector", default="")
    p.add_argument("--voucher-prefix", default="LOCAL")
    p.add_argument("--specimen-id", default="", help="Use one shared ID when the folder contains multiple views of one specimen")
    p.add_argument("--out", default="data/local_specimens_manifest.csv")
    args = p.parse_args()

    image_dir = Path(args.image_dir)
    paths = sorted([p for p in image_dir.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
    rows = []
    for i, path in enumerate(paths, start=1):
        voucher = args.specimen_id or f"{args.voucher_prefix}-{i:05d}"
        rows.append(finalize_record({
            "source": "local_verified",
            "source_record_id": voucher,
            "source_image_id": path.name,
            "image_url": "",
            "local_path": str(path.resolve()),
            "basis_of_record": "PRESERVED_SPECIMEN",
            "is_preserved_specimen": True,
            "order": "Diptera",
            "family": args.family,
            "genus": args.genus,
            "species": args.species,
            "observer": args.collector,
            "image_license": "project-owned",
            "attribution": args.collector,
            "specimen_group_id": f"local:{voucher}",
            "label_quality": "A",
        }))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=MASTER_COLUMNS).to_csv(out, index=False)
    print(f"Wrote {len(rows)} local specimen rows -> {out}")


if __name__ == "__main__":
    main()
