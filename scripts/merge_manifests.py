#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="+")
    p.add_argument("--out", default="data/training_manifest.csv")
    args = p.parse_args()
    dfs = [pd.read_csv(path) for path in args.inputs]
    merged = pd.concat(dfs, ignore_index=True, sort=False).drop_duplicates(subset=["local_path", "image_url"], keep="first")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.out, index=False)
    print(f"Merged {len(merged)} rows -> {args.out}")


if __name__ == "__main__":
    main()
