#!/usr/bin/env python3
"""Merge resumable BIOSCAN manifests without duplicating specimen process IDs."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    frames = [pd.read_csv(path, dtype=str, keep_default_na=False) for path in args.inputs if Path(path).exists()]
    if not frames:
        raise SystemExit("no BIOSCAN manifests found to merge")
    merged = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    key = next((name for name in ("processid", "process_id", "sampleid", "sample_id") if name in merged.columns), None)
    if not key:
        raise SystemExit("BIOSCAN manifests have no process identifier column")
    merged = merged[merged[key].astype(str).str.len() > 0]
    merged = merged.drop_duplicates(subset=[key], keep="last").sort_values(key).reset_index(drop=True)
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, index=False)
    print(f"merged BIOSCAN manifests: {len(merged)} unique specimens -> {out}")


if __name__ == "__main__":
    main()
