#!/usr/bin/env python3
"""Download licensed manifest images into a deterministic local cache."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diptera_id.corpus.io import ManifestWriter, iter_table
from diptera_id.corpus.schema import finalize_record, normalize_license


UA = "SwissDipteraIDWorkbench/0.2 (licensed research image cache)"


def safe_source(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-") or "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", default="data/corpus/downloaded_manifest.parquet")
    parser.add_argument("--image-root", default="data/images/corpus")
    parser.add_argument("--licenses", default="CC0,CC-BY,CC-BY-SA")
    parser.add_argument("--max-images", type=int, default=1_000, help="Pilot safety cap; 0 requires --allow-unbounded")
    parser.add_argument("--allow-unbounded", action="store_true", help="Acknowledge storage, bandwidth and source-policy responsibility")
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--chunksize", type=int, default=10_000)
    args = parser.parse_args()
    if args.max_images == 0 and not args.allow_unbounded:
        raise SystemExit("Use --allow-unbounded together with --max-images 0 after reviewing source terms and storage")

    allowed = {normalize_license(value) for value in args.licenses.split(",")}
    root = Path(args.image_root)
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    attempted = downloaded = 0

    with ManifestWriter(args.out) as writer:
        stop = False
        for chunk in iter_table(args.manifest, args.chunksize):
            output = []
            for raw in chunk.to_dict(orient="records"):
                record = finalize_record(raw)
                if record["image_license"] not in allowed:
                    record["eligible_supervised"] = False
                    record["exclusion_reason"] = f"license:{record['image_license']}"
                    output.append(record)
                    continue
                if record["local_path"] and Path(record["local_path"]).is_file():
                    output.append(record)
                    continue
                if not record["image_url"]:
                    record["eligible_supervised"] = False
                    record["exclusion_reason"] = "missing_image_location"
                    output.append(record)
                    continue
                if args.max_images and attempted >= args.max_images:
                    stop = True
                    break
                attempted += 1
                destination = root / safe_source(record["source"]) / record["record_id"][:2] / f"{record['record_id']}.jpg"
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    response = session.get(record["image_url"], timeout=45)
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content)).convert("RGB")
                    image.save(destination, "JPEG", quality=94)
                    record["local_path"] = str(destination)
                    record["image_sha256"] = hashlib.sha256(destination.read_bytes()).hexdigest()
                    downloaded += 1
                except Exception as exc:
                    record["eligible_supervised"] = False
                    record["exclusion_reason"] = f"download_error:{type(exc).__name__}"
                output.append(record)
                if args.sleep:
                    time.sleep(args.sleep)
            writer.write(output)
            print(f"attempted: {attempted} | downloaded: {downloaded}", end="\r")
            if stop:
                break
        print(f"\ndownloaded {downloaded}/{attempted}; updated manifest -> {args.out}")


if __name__ == "__main__":
    main()
