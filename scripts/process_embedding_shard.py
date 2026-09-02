#!/usr/bin/env python3
"""Stream one image shard through DINOv2 and write a resumable embedding shard.

Remote images are decoded in memory and discarded after embedding.  Only the
compact vectors, provenance manifest and failure report are persisted.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from diptera_id.corpus.io import load_manifest
from diptera_id.embedding import DINOEmbedder
from embed_multiview import crops_for, fuse_specimens, normalized_mean


USER_AGENT = "EntoKey-Foundation/0.5 (licensed biodiversity research; resumable embedding worker)"


def open_image(row: pd.Series, session: requests.Session, max_bytes: int) -> tuple[Image.Image, int]:
    local = Path(str(row.get("local_path", "")))
    if str(local) and local.is_file():
        size = local.stat().st_size
        if size > max_bytes:
            raise ValueError(f"local image exceeds {max_bytes} bytes")
        return Image.open(local).convert("RGB"), size
    url = str(row.get("image_url", ""))
    if not url.startswith(("http://", "https://")):
        raise ValueError("missing image URL")
    with session.get(url, stream=True, timeout=(30, 90)) as response:
        response.raise_for_status()
        declared = int(response.headers.get("content-length", "0") or 0)
        if declared and declared > max_bytes:
            raise ValueError(f"remote image exceeds {max_bytes} bytes")
        payload = bytearray()
        for block in response.iter_content(1024 * 1024):
            payload.extend(block)
            if len(payload) > max_bytes:
                raise ValueError(f"remote image exceeds {max_bytes} bytes")
    return Image.open(BytesIO(payload)).convert("RGB"), len(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model", default="facebook/dinov2-base")
    parser.add_argument("--image-size", type=int, default=518)
    parser.add_argument("--tile-grid", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--no-whole", action="store_true")
    parser.add_argument("--max-image-mb", type=int, default=30)
    parser.add_argument("--min-success-rate", type=float, default=0.80)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.image_size % 14:
        raise SystemExit("DINOv2 image-size must be divisible by 14")
    if not 1 <= args.tile_grid <= 4:
        raise SystemExit("tile-grid must be between 1 and 4")

    out_dir = Path(args.out_dir)
    complete_path = out_dir / "complete.json"
    if complete_path.exists() and not args.force:
        print(f"already complete: {out_dir}")
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    frame = load_manifest(args.manifest).fillna("").reset_index(drop=True)
    if frame.empty:
        raise SystemExit("embedding shard is empty")
    if "view_type" not in frame:
        frame["view_type"] = "habitus"
    frame.loc[frame["view_type"].astype(str).eq(""), "view_type"] = "habitus"

    embedder = DINOEmbedder(args.model, image_size=args.image_size)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    kept_rows: list[int] = []
    vectors: list[np.ndarray] = []
    failures: list[dict] = []
    downloaded_bytes = 0
    include_whole = not args.no_whole

    for start in range(0, len(frame), args.batch_size):
        chunk = frame.iloc[start:start + args.batch_size]
        flat_crops: list[Image.Image] = []
        counts: list[int] = []
        valid_indices: list[int] = []
        for index, row in chunk.iterrows():
            last_error: Exception | None = None
            for attempt in range(args.retries + 1):
                try:
                    image, byte_count = open_image(row, session, args.max_image_mb * 1024 * 1024)
                    downloaded_bytes += byte_count
                    item_crops = crops_for(image, args.tile_grid, include_whole)
                    flat_crops.extend(item_crops)
                    counts.append(len(item_crops))
                    valid_indices.append(index)
                    last_error = None
                    break
                except Exception as exc:  # individual bad media must not kill a large job
                    last_error = exc
                    if attempt < args.retries:
                        time.sleep(1.5 * (attempt + 1))
            if last_error is not None:
                failures.append({"record_id": str(row.get("record_id", "")), "image_url": str(row.get("image_url", "")), "error": f"{type(last_error).__name__}: {last_error}"})
        if flat_crops:
            embedded = embedder.embed_images(flat_crops)
            cursor = 0
            for index, count in zip(valid_indices, counts):
                vectors.append(normalized_mean(embedded[cursor:cursor + count]))
                kept_rows.append(index)
                cursor += count
        print(f"{Path(args.manifest).name}: {min(start + args.batch_size, len(frame))}/{len(frame)}")

    if not vectors:
        raise SystemExit("no images in shard could be embedded")
    view_frame = frame.loc[kept_rows].reset_index(drop=True)
    view_vectors = np.stack(vectors).astype(np.float32)
    specimen_frame, specimen_vectors = fuse_specimens(view_frame, view_vectors)
    np.save(out_dir / "view_embeddings.npy", view_vectors)
    view_frame.to_csv(out_dir / "embedded_views_manifest.csv", index=False)
    np.save(out_dir / "embeddings.npy", specimen_vectors)
    specimen_frame.to_csv(out_dir / "embedded_manifest.csv", index=False)
    (out_dir / "failures.json").write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")

    success_rate = len(kept_rows) / len(frame)
    status = {
        "manifest": str(args.manifest),
        "requested_images": int(len(frame)),
        "embedded_views": int(len(view_frame)),
        "fused_specimens": int(len(specimen_frame)),
        "failures": int(len(failures)),
        "success_rate": success_rate,
        "downloaded_bytes": downloaded_bytes,
        "embedding": {
            "backbone": args.model,
            "image_size": args.image_size,
            "tile_grid": args.tile_grid,
            "include_whole": include_whole,
        },
    }
    (out_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    if success_rate < args.min_success_rate:
        raise SystemExit(f"success rate {success_rate:.1%} is below {args.min_success_rate:.1%}; inspect failures.json")
    complete_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(f"complete: {len(view_frame)} views / {len(specimen_frame)} specimens -> {out_dir}")


if __name__ == "__main__":
    main()
