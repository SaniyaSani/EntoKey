#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from diptera_id.key_finder import KeyFinder


def main() -> None:
    parser = argparse.ArgumentParser(description="Find and rank identification keys for TaxaLens genus candidates")
    parser.add_argument("--family", default="")
    parser.add_argument("--genera", default="", help="Comma-separated top genus candidates")
    parser.add_argument("--region", default="Europe")
    parser.add_argument("--offline", action="store_true", help="Use only the curated local catalog")
    parser.add_argument("--out", help="Optional JSON output path")
    args = parser.parse_args()

    finder = KeyFinder(ROOT / "data/key_catalog_v09.json", ROOT / "data/key_cache")
    payload = finder.find(
        args.family,
        [value.strip() for value in args.genera.split(",") if value.strip()],
        region=args.region,
        live=not args.offline,
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        print(destination)
    else:
        print(text)


if __name__ == "__main__":
    main()
