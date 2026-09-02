#!/usr/bin/env python3
"""Create a reproducible, taxon-balanced pilot from the master manifest."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diptera_id.corpus.io import load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="data/corpus/pilot_manifest.csv")
    parser.add_argument("--rank", choices=["family", "genus", "species"], default="species")
    parser.add_argument("--max-per-taxon", type=int, default=250)
    parser.add_argument("--min-per-taxon", type=int, default=8)
    parser.add_argument("--max-per-source-taxon", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--include-ineligible", action="store_true")
    args = parser.parse_args()

    frame = load_manifest(args.input).fillna("")
    if not args.include_ineligible and "eligible_supervised" in frame:
        frame = frame[frame["eligible_supervised"].astype(str).str.lower().isin({"true", "1", "yes"})]
    frame = frame[frame[args.rank].astype(str).str.len() > 0].copy()
    counts = frame[args.rank].value_counts()
    allowed = counts[counts >= args.min_per_taxon].index
    frame = frame[frame[args.rank].isin(allowed)]

    # Cap each source first so one field-photo or museum domain cannot dominate a taxon.
    pieces = []
    for (_taxon, _source), group in frame.groupby([args.rank, "source"], sort=True):
        pieces.append(group.sample(min(len(group), args.max_per_source_taxon), random_state=args.seed))
    balanced = pd.concat(pieces, ignore_index=True) if pieces else frame.iloc[0:0]
    pieces = []
    for _taxon, group in balanced.groupby(args.rank, sort=True):
        pieces.append(group.sample(min(len(group), args.max_per_taxon), random_state=args.seed))
    pilot = pd.concat(pieces, ignore_index=True) if pieces else balanced
    pilot = pilot.sort_values([args.rank, "source", "record_id"]).reset_index(drop=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".parquet":
        pilot.astype(str).to_parquet(out, index=False, compression="zstd")
    else:
        pilot.to_csv(out, index=False)
    print(
        f"pilot: {len(pilot)} images | {pilot[args.rank].nunique()} {args.rank} taxa | "
        f"{pilot['source'].nunique()} sources -> {out}"
    )


if __name__ == "__main__":
    main()
