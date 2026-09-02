#!/usr/bin/env python3
"""Merge normalized source manifests and assign deterministic group splits."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diptera_id.corpus.io import ManifestWriter, iter_table
from diptera_id.corpus.schema import finalize_record


def split_for(group: str, train: int, val: int) -> str:
    bucket = int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < train:
        return "train"
    if bucket < train + val:
        return "val"
    return "test"


def protected_source_split(source: str, source_split: str) -> str:
    """Respect official BIOSCAN holdouts instead of leaking them into training."""
    if source != "BIOSCAN-5M":
        return ""
    split = source_split.strip().lower()
    if split in {"train", "pretrain"}:
        return "train"
    if split in {"val", "validation", "key_unseen", "val_unseen"}:
        return "val"
    if split in {"test", "test_unseen", "other_heldout"}:
        return "test"
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out", default="data/corpus/master_manifest.parquet")
    parser.add_argument("--chunksize", type=int, default=100_000)
    parser.add_argument("--train-percent", type=int, default=80)
    parser.add_argument("--val-percent", type=int, default=10)
    parser.add_argument("--include-ineligible", action="store_true")
    args = parser.parse_args()
    if args.train_percent + args.val_percent >= 100:
        raise SystemExit("train-percent + val-percent must be below 100")

    with ManifestWriter(args.out) as writer:
        for path in args.inputs:
            for chunk in iter_table(path, args.chunksize):
                output = []
                for raw in chunk.to_dict(orient="records"):
                    record = finalize_record(raw)
                    if not args.include_ineligible and not record["eligible_supervised"]:
                        continue
                    group = record["duplicate_group_id"] or record["specimen_group_id"] or record["split_group"]
                    record["split_group"] = group
                    record["split"] = protected_source_split(record["source"], record["source_split"]) or split_for(
                        group, args.train_percent, args.val_percent
                    )
                    output.append(record)
                writer.write(output)
            print(f"merged through {path}: {writer.rows_written} rows")
        print(f"master manifest: {writer.rows_written} rows -> {args.out}")


if __name__ == "__main__":
    main()
