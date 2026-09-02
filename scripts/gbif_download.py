#!/usr/bin/env python3
"""Request, inspect and fetch a GBIF preserved-Diptera occurrence download."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import zipfile
from pathlib import Path

import requests


API = "https://api.gbif.org/v1/occurrence/download"


def request_payload(email: str, taxon_key: str) -> dict:
    return {
        "notificationAddresses": [email],
        "sendNotification": True,
        "format": "DWCA",
        "predicate": {
            "type": "and",
            "predicates": [
                {"type": "equals", "key": "TAXON_KEY", "value": taxon_key},
                {"type": "equals", "key": "BASIS_OF_RECORD", "value": "PRESERVED_SPECIMEN"},
                {"type": "equals", "key": "MEDIA_TYPE", "value": "StillImage"},
            ],
        },
    }


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise SystemExit(f"unsafe path in GBIF archive: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=8 * 1024 * 1024)


def command_request(args: argparse.Namespace) -> None:
    email = os.getenv("GBIF_EMAIL", "")
    payload = request_payload(email or "YOUR_EMAIL@example.org", args.taxon_key)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote request -> {out}")
    if not args.submit:
        print("inspect it, then rerun with --submit")
        return
    username = os.getenv("GBIF_USER")
    password = os.getenv("GBIF_PASSWORD")
    if not username or not password or not email:
        raise SystemExit("Set GBIF_USER, GBIF_PASSWORD and GBIF_EMAIL before --submit")
    response = requests.post(f"{API}/request", auth=(username, password), json=payload, timeout=60)
    response.raise_for_status()
    print(response.text.strip())


def download_metadata(key: str) -> dict:
    response = requests.get(f"{API}/{key}", timeout=60)
    response.raise_for_status()
    return response.json()


def command_status(args: argparse.Namespace) -> None:
    metadata = download_metadata(args.key)
    print(json.dumps({
        "key": metadata.get("key", args.key),
        "status": metadata.get("status"),
        "totalRecords": metadata.get("totalRecords"),
        "size": metadata.get("size"),
        "downloadLink": metadata.get("downloadLink"),
    }, indent=2))


def command_fetch(args: argparse.Namespace) -> None:
    metadata = download_metadata(args.key)
    status = str(metadata.get("status", "")).upper()
    if status != "SUCCEEDED":
        raise SystemExit(f"GBIF download {args.key} is {status or 'not ready'}")
    url = metadata.get("downloadLink")
    if not url:
        raise SystemExit("GBIF response did not include downloadLink")
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    with requests.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_content(8 * 1024 * 1024):
                if chunk:
                    handle.write(chunk)
    partial.replace(destination)
    print(f"downloaded -> {destination}")
    if args.extract:
        safe_extract(destination, Path(args.extract))
        print(f"extracted -> {args.extract}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    request = subparsers.add_parser("request")
    request.add_argument("--taxon-key", default="811", help="GBIF Diptera key; verify against your checklist")
    request.add_argument("--out", default="data/requests/gbif_preserved_diptera.json")
    request.add_argument("--submit", action="store_true")
    request.set_defaults(function=command_request)

    status = subparsers.add_parser("status")
    status.add_argument("key")
    status.set_defaults(function=command_status)

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("key")
    fetch.add_argument("--out", default="data/raw/gbif/gbif_download.zip")
    fetch.add_argument("--extract", default="data/raw/gbif/extracted")
    fetch.set_defaults(function=command_fetch)

    args = parser.parse_args()
    args.function(args)


if __name__ == "__main__":
    main()
