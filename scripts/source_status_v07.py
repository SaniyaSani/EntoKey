#!/usr/bin/env python3
"""Show which Whole-Fly v0.7 corpus inputs are present and what to do next."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def resolve(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def status(path: Path | None) -> str:
    if path is None:
        return "—"
    if path.exists():
        if path.is_dir():
            return f"OK dir ({sum(1 for _ in path.iterdir())} entries)"
        return f"OK {path.stat().st_size / (1024*1024):.1f} MB"
    return "MISSING"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/sources_wholefly_v07.example.json")
    args = parser.parse_args()
    config_path = resolve(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sources = config.get("sources", {})

    checks: list[tuple[str, str, Path | None]] = []
    inat = sources.get("inat", {})
    if inat.get("enabled"):
        for key in ("observations", "photos", "taxa", "observers"):
            checks.append(("iNaturalist", key, resolve(inat.get(key))))
    bioscan = sources.get("bioscan", {})
    if bioscan.get("enabled"):
        checks += [("BIOSCAN", "metadata", resolve(bioscan.get("metadata"))), ("BIOSCAN", "image_root", resolve(bioscan.get("image_root")))]
    gbif = sources.get("gbif", {})
    if gbif.get("enabled"):
        checks += [("GBIF", "occurrence", resolve(gbif.get("occurrence"))), ("GBIF", "multimedia", resolve(gbif.get("multimedia")))]
    dissco = sources.get("dissco", {})
    if dissco.get("enabled"):
        checks.append(("DiSSCo", "input", resolve(dissco.get("input"))))
    for index, value in enumerate(sources.get("normalized_manifests", []), start=1):
        checks.append(("normalized", f"manifest_{index}", resolve(value)))

    width = max([len(source) for source, _, _ in checks] + [8])
    print(f"{'SOURCE':<{width}}  FIELD             STATUS  PATH")
    print("-" * 100)
    missing = 0
    for source, field, path in checks:
        value = status(path)
        missing += value == "MISSING"
        print(f"{source:<{width}}  {field:<16} {value:<18} {path or ''}")
    print("-" * 100)
    if missing:
        print(f"Missing inputs: {missing}. Finish/download those sources before assembly.")
    else:
        print("All configured source inputs are present. Next: prepare_corpus.py --stage assemble")


if __name__ == "__main__":
    main()
