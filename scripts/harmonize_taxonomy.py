#!/usr/bin/env python3
"""Canonicalize taxon strings and optionally apply a reviewed synonym table."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diptera_id.corpus.io import ManifestWriter, iter_table
from diptera_id.corpus.schema import canonical_taxon, clean, finalize_record


def synonym_map(path: str | None) -> dict[str, dict]:
    if not path:
        return {}
    mapping: dict[str, dict] = {}
    for chunk in iter_table(path):
        for row in chunk.to_dict(orient="records"):
            original = clean(row.get("original_name") or row.get("raw_name") or row.get("synonym"))
            if original:
                mapping[original.casefold()] = row
    return mapping


def harmonize(row: dict, synonyms: dict[str, dict]) -> dict:
    original = clean(row.get("original_scientific_name")) or clean(row.get("species"))
    row["family"] = canonical_taxon(row.get("family"), "family")
    row["genus"] = canonical_taxon(row.get("genus"), "genus")
    row["species"] = canonical_taxon(row.get("species") or original, "species")
    row["subspecies"] = canonical_taxon(row.get("subspecies"), "subspecies")
    accepted = synonyms.get(original.casefold()) or synonyms.get(clean(row.get("species")).casefold())
    if accepted:
        accepted_name = clean(accepted.get("accepted_name") or accepted.get("accepted_scientific_name"))
        if accepted_name:
            row["accepted_scientific_name"] = accepted_name
            row["species"] = canonical_taxon(accepted_name, "species")
            row["genus"] = clean(accepted.get("accepted_genus")) or row["species"].split()[0]
        row["family"] = clean(accepted.get("accepted_family")) or row["family"]
        row["taxon_id"] = clean(accepted.get("accepted_taxon_id")) or row.get("taxon_id", "")
    row["identification_level"] = ""
    preserve_exclusion = clean(row.get("exclusion_reason")) in {"missing_image_location", "corrupt_image"}
    row["eligible_supervised"] = ""
    result = finalize_record(row)
    if preserve_exclusion:
        result["eligible_supervised"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--synonyms", help="Reviewed CSV with original_name and accepted_name columns")
    parser.add_argument("--out", default="data/corpus/harmonized.parquet")
    parser.add_argument("--chunksize", type=int, default=100_000)
    args = parser.parse_args()

    synonyms = synonym_map(args.synonyms)
    with ManifestWriter(args.out) as writer:
        for chunk in iter_table(args.input, args.chunksize):
            writer.write([harmonize(row, synonyms) for row in chunk.to_dict(orient="records")])
            print(f"harmonized: {writer.rows_written}", end="\r")
        print(f"\nharmonized {writer.rows_written} rows -> {args.out}")


if __name__ == "__main__":
    main()
