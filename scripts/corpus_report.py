#!/usr/bin/env python3
"""Audit source coverage, labels, licences and taxonomic breadth of a manifest."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diptera_id.corpus.io import iter_table
from diptera_id.corpus.schema import as_bool, finalize_record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-json", default="data/foundation_v05/corpus_report.json")
    parser.add_argument("--out-md", default="data/foundation_v05/corpus_report.md")
    parser.add_argument("--require-sources", default="iNaturalist,BIOSCAN-5M,GBIF,DiSSCo")
    parser.add_argument("--chunksize", type=int, default=100_000)
    args = parser.parse_args()

    counters = {name: Counter() for name in ("source", "license", "quality", "basis", "family", "genus", "species")}
    total = eligible = preserved = with_dna = 0
    for chunk in iter_table(args.input, args.chunksize):
        for raw in chunk.to_dict(orient="records"):
            row = finalize_record(raw)
            total += 1
            eligible += int(as_bool(row["eligible_supervised"]))
            preserved += int(bool(row["is_preserved_specimen"]))
            with_dna += int(bool(row["dna_barcode"] or row["dna_bin"]))
            counters["source"][row["source"]] += 1
            counters["license"][row["image_license"]] += 1
            counters["quality"][row["label_quality"] or "UNKNOWN"] += 1
            counters["basis"][row["basis_of_record"] or "UNKNOWN"] += 1
            for rank in ("family", "genus", "species"):
                if row[rank]:
                    counters[rank][row[rank]] += 1

    report = {
        "rows": total,
        "eligible_supervised": eligible,
        "preserved_specimens": preserved,
        "with_dna_or_bin": with_dna,
        "unique_families": len(counters["family"]),
        "unique_genera": len(counters["genus"]),
        "unique_species": len(counters["species"]),
        "by_source": dict(counters["source"]),
        "by_license": dict(counters["license"]),
        "by_label_quality": dict(counters["quality"]),
        "by_basis_of_record": dict(counters["basis"]),
    }
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    rows = [
        "# Foundation corpus audit",
        "",
        f"- Rows: **{total:,}**",
        f"- Eligible supervised: **{eligible:,}**",
        f"- Preserved specimens: **{preserved:,}**",
        f"- DNA/BIN records: **{with_dna:,}**",
        f"- Families / genera / species: **{len(counters['family']):,} / {len(counters['genus']):,} / {len(counters['species']):,}**",
        "",
        "## Sources",
        "",
        "| Source | Images |",
        "| --- | ---: |",
    ]
    rows.extend(f"| {source} | {count:,} |" for source, count in counters["source"].most_common())
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    required = [value.strip() for value in args.require_sources.split(",") if value.strip()]
    missing = [source for source in required if counters["source"][source] == 0]
    if missing:
        raise SystemExit(f"corpus is missing required sources: {', '.join(missing)}")


if __name__ == "__main__":
    main()
