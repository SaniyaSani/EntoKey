#!/usr/bin/env python3
"""Deduplicate cross-source images with a disk-backed, group-safe workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from diptera_id.corpus.io import ManifestWriter, iter_table
from diptera_id.corpus.schema import finalize_record, stable_id


QUALITY = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "": 5}
SOURCE = {"local_verified": 0, "BIOSCAN-5M": 1, "DiSSCo": 2, "iNaturalist": 3, "GBIF": 4}
OPEN = {"CC0", "CC-BY", "CC-BY-SA", "PROJECT-OWNED"}


def canonical_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    path = re.sub(r"/(square|small|thumb|medium|large)\.", "/original.", parsed.path, flags=re.I)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def duplicate_key(row: dict, hash_local: bool) -> str:
    for value in (row.get("image_url", ""), row.get("source_url", ""), row.get("observation_url", "")):
        match = re.search(r"/photos/(\d+)", str(value), re.I)
        if match:
            return f"inat-photo:{match.group(1)}"
    url = canonical_url(str(row.get("image_url", "")))
    if url:
        return f"url:{url}"
    local = Path(str(row.get("local_path", "")))
    if hash_local and local.is_file():
        digest = hashlib.sha256()
        with local.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return f"sha256:{digest.hexdigest()}"
    identity = row.get("record_id") or stable_id(row.get("source"), row.get("source_record_id"), row.get("source_image_id"))
    return f"unique:{identity}"


def priority(record: dict) -> str:
    licensed = 0 if record["image_license"] in OPEN else 1
    quality = QUALITY.get(record["label_quality"], 9)
    source = SOURCE.get(record["source"], 9)
    return f"{licensed:02d}:{quality:02d}:{source:02d}:{record['record_id']}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="data/corpus/master_deduplicated.parquet")
    parser.add_argument("--keep-all", action="store_true", help="Keep duplicate rows, but give them a shared duplicate/split group")
    parser.add_argument("--hash-local", action="store_true", help="SHA-256 local images when no URL is present")
    parser.add_argument("--chunksize", type=int, default=100_000)
    args = parser.parse_args()

    temp = tempfile.NamedTemporaryFile(prefix="diptera-dedup-", suffix=".sqlite", delete=False)
    temp.close()
    database = Path(temp.name)
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("CREATE TABLE items (row_id INTEGER PRIMARY KEY, dkey TEXT NOT NULL, priority TEXT NOT NULL, payload TEXT NOT NULL)")
    total = 0
    try:
        for chunk in iter_table(args.input, args.chunksize):
            batch = []
            for raw in chunk.to_dict(orient="records"):
                record = finalize_record(raw)
                key = duplicate_key(record, args.hash_local)
                batch.append((key, priority(record), json.dumps(record, ensure_ascii=False)))
            connection.executemany("INSERT INTO items(dkey, priority, payload) VALUES (?, ?, ?)", batch)
            connection.commit()
            total += len(batch)
            print(f"indexed for deduplication: {total}", end="\r")
        connection.execute("CREATE INDEX items_dkey_priority ON items(dkey, priority)")

        if args.keep_all:
            query = """
                SELECT i.payload, i.dkey, c.n
                FROM items i
                JOIN (SELECT dkey, COUNT(*) AS n FROM items GROUP BY dkey) c ON c.dkey = i.dkey
                ORDER BY i.row_id
            """
        else:
            query = """
                SELECT payload, dkey, n FROM (
                    SELECT payload, dkey, COUNT(*) OVER (PARTITION BY dkey) AS n,
                           ROW_NUMBER() OVER (PARTITION BY dkey ORDER BY priority) AS choice
                    FROM items
                ) WHERE choice = 1 ORDER BY dkey
            """

        duplicate_groups: set[str] = set()
        output_count = 0
        with ManifestWriter(args.out) as writer:
            cursor = connection.execute(query)
            while True:
                selected = cursor.fetchmany(args.chunksize)
                if not selected:
                    break
                output = []
                for payload, key, count in selected:
                    record = json.loads(payload)
                    if count > 1:
                        group = stable_id(key, prefix="dup")
                        record["duplicate_group_id"] = group
                        record["split_group"] = group
                        duplicate_groups.add(group)
                    output.append(record)
                writer.write(output)
                output_count += len(output)
        print(
            f"\nduplicate groups: {len(duplicate_groups)} | removed: {total - output_count} | "
            f"wrote: {output_count} -> {args.out}"
        )
    finally:
        connection.close()
        database.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
