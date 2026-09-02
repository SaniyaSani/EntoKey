#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diptera_id.embedding import DINOEmbedder
from diptera_id.corpus.io import load_manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="data/inat_pilot_manifest.csv")
    p.add_argument("--out-dir", default="models")
    p.add_argument("--model", default="facebook/dinov2-small")
    p.add_argument("--batch-size", type=int, default=16)
    args = p.parse_args()

    manifest = load_manifest(args.manifest).fillna("")
    if "eligible_supervised" in manifest.columns:
        eligible = manifest["eligible_supervised"].astype(str).str.lower().isin({"true", "1", "yes"})
        manifest = manifest[eligible].copy()
    manifest = manifest[manifest["local_path"].astype(str).str.len() > 0].copy()
    manifest = manifest[manifest["local_path"].map(lambda p: Path(p).exists())].reset_index(drop=True)
    if manifest.empty:
        raise SystemExit("No local images found. Run build_inat_pilot.py with --download, or provide your own manifest.")

    embedder = DINOEmbedder(args.model)
    vectors = []
    kept = []
    for start in range(0, len(manifest), args.batch_size):
        chunk = manifest.iloc[start:start + args.batch_size]
        images, valid_rows = [], []
        for idx, row in chunk.iterrows():
            try:
                images.append(Image.open(row["local_path"]).convert("RGB"))
                valid_rows.append(idx)
            except Exception as exc:
                print(f"skip {row['local_path']}: {exc}")
        if images:
            vectors.append(embedder.embed_images(images))
            kept.extend(valid_rows)
        print(f"embedded {min(start + args.batch_size, len(manifest))}/{len(manifest)}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    x = np.concatenate(vectors, axis=0).astype(np.float32)
    aligned = manifest.loc[kept].reset_index(drop=True)
    np.save(out / "embeddings.npy", x)
    aligned.to_csv(out / "embedded_manifest.csv", index=False)
    print(f"Saved {x.shape} embeddings -> {out}")


if __name__ == "__main__":
    main()
